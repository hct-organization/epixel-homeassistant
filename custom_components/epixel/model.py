"""Page/box model -- builds the `/view` payload.

Kept in its own module because both __init__ and views need it; putting it in
either one would create a circular import.

TWO IDENTIFIERS, ON PURPOSE
---------------------------
`k` is what the machine uses: a short hex digest of the entity_id. It is
opaque, fixed length, and contains nothing but [0-9a-f] -- no spaces, no
accented characters, no punctuation. Commands and chart requests carry it
back and are resolved here.

`n` is what the human reads. It may contain anything the user typed in Home
Assistant, so it is sanitised before it goes on the wire and it is never used
to identify anything.

Keeping them apart is what makes a friendly name like "Salon Işık / 2. kat"
harmless to a device that has to parse, store and log it.
"""

from __future__ import annotations

import hashlib
import unicodedata
from collections import Counter

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from . import icons
from .const import (
    CONF_ICONS,
    CONF_PAGES,
    DIM_MIN,
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


def clean_text(raw: object) -> str:
    """Make a user-supplied string safe to put on the wire and on the screen.

    Home Assistant lets a friendly name contain anything: tabs, newlines pasted
    from a spreadsheet, zero-width joiners, control characters from a badly
    behaved integration. The display renders text into a fixed-width box and
    writes it to its log, so it is cleaned once, here, rather than defended
    against in three places later.

    Line breaks and control characters become spaces, runs of whitespace
    collapse to one, and the ends are trimmed.
    """
    text = str(raw or "")
    text = unicodedata.normalize("NFC", text)
    text = "".join(
        " " if unicodedata.category(ch)[0] == "C" else ch
        for ch in text
    )
    return " ".join(text.split())


def build_view(hass: HomeAssistant, entry: ConfigEntry) -> dict:
    pages: list[dict] = []
    for page in pages_of(entry)[:MAX_PAGES]:
        overrides = page.get(CONF_ICONS) or {}
        boxes = [
            _box(hass, entity_id, overrides.get(entity_id))
            for entity_id in page.get("entities", [])[:MAX_BOXES_PER_PAGE]
        ]
        if boxes:
            _fit_names(boxes)
            pages.append({"t": clean_text(page.get("title"))[:NAME_MAX], "b": boxes})
    return {"rev": hass.data[DOMAIN]["rev"], "pages": pages}


def _fit_names(boxes: list[dict]) -> None:
    """Shorten box titles to the screen width without destroying what tells
    them apart.

    Cutting at a fixed width is not enough: "Display LED Strip 1" and
    "Display LED Strip 2" both become "Display LED Strip" and the user is left
    with two identical boxes and no way to know which is which. Where a
    collision appears only *because* of truncation, keep both ends instead.
    """
    full = [box["n"] for box in boxes]
    short = [name[:NAME_MAX] for name in full]

    # Collisions are counted BEFORE anything is rewritten. Counting against a
    # list that is being mutated fixes the first of a colliding pair and then
    # sees the second as unique, leaving it truncated and still ambiguous.
    collisions = Counter(short)

    for index, name in enumerate(full):
        collides = collisions[short[index]] > 1
        distinct = full.count(name) == 1
        if collides and distinct and len(name) > NAME_MAX:
            head = NAME_MAX // 2 - 1
            tail = NAME_MAX - head - 1
            short[index] = name[:head] + "…" + name[-tail:]

    for box, name in zip(boxes, short):
        box["n"] = name


def _box(hass: HomeAssistant, entity_id: str, icon_override: str | None = None) -> dict:
    key = key_of(entity_id)
    domain = entity_id.split(".", 1)[0]
    state = hass.states.get(entity_id)
    chosen = icons.normalise(icon_override)

    # The entity may have been deleted in Home Assistant. The box does NOT
    # disappear -- it says so. Silently dropping it would read as "my page
    # broke" to the user.
    if state is None:
        return {
            "k": key,
            "n": clean_text(entity_id.split(".")[-1].replace("_", " ")),
            "y": "txt",
            "v": "—",
            "i": chosen or icons.FALLBACK,
        }

    attrs = state.attributes
    # Full name here; _fit_names shortens once the whole page is known, so a
    # collision between two boxes can be resolved instead of baked in.
    box = {
        "k": key,
        "n": clean_text(attrs.get("friendly_name") or entity_id),
        "i": chosen or icons.pick(domain, attrs),
    }

    if state.state in ("unavailable", "unknown"):
        box["y"] = "txt"
        box["v"] = "—"
        return box

    on = state.state == "on"

    # A dimmable light gets its own type so the display can offer a level
    # control instead of a plain toggle.
    if domain == "light" and icons.supports_brightness(attrs):
        box["y"] = "dim"
        box["v"] = _brightness_percent(attrs) if on else 0
        return box

    if domain in SWITCHABLE_DOMAINS:
        box["y"] = "sw"
        box["v"] = 1 if on else 0
        return box

    if domain == "binary_sensor":
        box["y"] = "bin"
        box["v"] = 1 if on else 0
        return box

    try:
        float(state.state)
    except (TypeError, ValueError):
        box["y"] = "txt"
        box["v"] = clean_text(state.state)[:NAME_MAX]
        return box

    box["y"] = "num"
    box["v"] = str(state.state)
    unit = clean_text(attrs.get("unit_of_measurement"))
    if unit:
        box["u"] = unit[:8]
    if attrs.get("state_class") in GRAPHABLE_STATE_CLASSES:
        box["g"] = 1
    return box


def _brightness_percent(attrs) -> int:
    """Home Assistant reports brightness 0-255; the wire carries 0-100.

    A lit lamp never reports 0 percent: rounding 1/255 down would show "off"
    on a light that is visibly on, so the floor is DIM_MIN.
    """
    raw = attrs.get("brightness")
    if raw is None:
        return 100
    try:
        percent = round(int(raw) * 100 / 255)
    except (TypeError, ValueError):
        return 100
    return max(DIM_MIN, min(100, percent))
