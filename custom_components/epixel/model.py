"""Page/box model -- builds the `/view` payload.

Kept in its own module because both __init__ and views need it; putting it in
either one would create a circular import.

DESIGN: the device never sees an `entity_id`. Every entity gets an opaque key
`k` (a short digest of its entity_id); commands and chart requests come back
carrying that key and are resolved here. As a result the device knows nothing
about Home Assistant's domain/service semantics -- if HA gains a new entity
type tomorrow, the firmware does not change.
"""

from __future__ import annotations

import hashlib

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from . import icons
from .const import (
    CONF_PAGES,
    DOMAIN,
    GRAPHABLE_STATE_CLASSES,
    MAX_BOXES_PER_PAGE,
    MAX_PAGES,
    NAME_MAX,
    SWITCHABLE_DOMAINS,
)


def pages_of(entry: ConfigEntry) -> list[dict]:
    return list((entry.options or {}).get(CONF_PAGES, []))


def tracked_entities(entry: ConfigEntry) -> list[str]:
    """Unique entity_ids used across all pages, in page order."""
    seen: list[str] = []
    for page in pages_of(entry):
        for entity_id in page.get("entities", []):
            if entity_id not in seen:
                seen.append(entity_id)
    return seen


def key_of(entity_id: str) -> str:
    return hashlib.sha1(entity_id.encode("utf-8")).hexdigest()[:6]


def key_map(entry: ConfigEntry) -> dict[str, str]:
    """k -> entity_id. At most 48 boxes exist, so rebuilding per request is cheap."""
    return {key_of(entity_id): entity_id for entity_id in tracked_entities(entry)}


def build_view(hass: HomeAssistant, entry: ConfigEntry) -> dict:
    pages: list[dict] = []
    for page in pages_of(entry)[:MAX_PAGES]:
        boxes = [
            _box(hass, entity_id)
            for entity_id in page.get("entities", [])[:MAX_BOXES_PER_PAGE]
        ]
        if boxes:
            pages.append({"t": str(page.get("title") or "")[:NAME_MAX], "b": boxes})
    return {"rev": hass.data[DOMAIN]["rev"], "pages": pages}


def _box(hass: HomeAssistant, entity_id: str) -> dict:
    key = key_of(entity_id)
    domain = entity_id.split(".", 1)[0]
    state = hass.states.get(entity_id)

    # The entity may have been deleted in Home Assistant. The box does NOT
    # disappear -- it says so. Silently dropping it would read as "my page
    # broke" to the user.
    if state is None:
        return {
            "k": key,
            "n": entity_id.split(".")[-1].replace("_", " ")[:NAME_MAX],
            "y": "txt",
            "v": "—",
            "i": icons.FALLBACK,
        }

    attrs = state.attributes
    box = {
        "k": key,
        "n": str(attrs.get("friendly_name") or entity_id)[:NAME_MAX],
        "i": icons.pick(domain, attrs.get("device_class"), attrs.get("unit_of_measurement")),
    }

    if state.state in ("unavailable", "unknown"):
        box["y"] = "txt"
        box["v"] = "—"
        return box

    if domain in SWITCHABLE_DOMAINS:
        box["y"] = "sw"
        box["v"] = 1 if state.state == "on" else 0
        return box

    if domain == "binary_sensor":
        box["y"] = "bin"
        box["v"] = 1 if state.state == "on" else 0
        return box

    try:
        float(state.state)
    except (TypeError, ValueError):
        box["y"] = "txt"
        box["v"] = str(state.state)[:NAME_MAX]
        return box

    box["y"] = "num"
    box["v"] = str(state.state)
    unit = attrs.get("unit_of_measurement")
    if unit:
        box["u"] = str(unit)[:8]
    if attrs.get("state_class") in GRAPHABLE_STATE_CLASSES:
        box["g"] = 1
    return box
