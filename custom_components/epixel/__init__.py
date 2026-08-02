"""Bridge between Home Assistant and an ePiXeL information display.

This integration creates no entities in Home Assistant. Its only job is to
serve the entities you pick to an ePiXeL screen on your local network, and to
accept on/off commands coming back from that screen.

DIRECTION: every connection is made *by the device, towards Home Assistant*.
Home Assistant never connects to the device, and the device opens no listening
port. See PROTOCOL.md.
"""

from __future__ import annotations

import asyncio
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .model import pages_of, tracked_entities
from .views import async_register_views

_LOGGER = logging.getLogger(__name__)


def ensure_data(hass: HomeAssistant) -> dict:
    """Process-wide shared state.

    Pairing records have to exist *before* any config entry does, which is why
    this lives outside of async_setup_entry.
    """
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {
            "rev": 1,                  # monotonic revision -- the heart of long polling
            "changed": asyncio.Event(),
            "pending": {},             # session -> {pin, name, expires, token}
            "attempts": 0,             # wrong-code entries
            "views_ok": False,
        }
    return hass.data[DOMAIN]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    # Endpoints open here, so that the moment a user starts the config flow the
    # component loads and the device's /pair polling finds someone home.
    ensure_data(hass)
    async_register_views(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    ensure_data(hass)
    async_register_views(hass)

    entity_ids = tracked_entities(entry)

    @callback
    def _state_changed(_event: Event) -> None:
        bump(hass)

    if entity_ids:
        entry.async_on_unload(
            async_track_state_change_event(hass, entity_ids, _state_changed)
        )

    # Editing pages must reach the screen immediately, not on the next poll.
    entry.async_on_unload(entry.add_update_listener(_options_updated))

    bump(hass)
    _LOGGER.info(
        "ePiXeL bridge ready: %d page(s), %d entit(ies)",
        len(pages_of(entry)),
        len(entity_ids),
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    # Endpoints stay registered so a reload does not make the device see 404s.
    # Authorisation reads the config entry, so with no entry every request
    # already answers 401.
    bump(hass)
    return True


async def _options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


@callback
def bump(hass: HomeAssistant) -> None:
    """Advance the revision and release any device waiting in a long poll.

    The Event OBJECT is replaced on purpose: an Event that has been set never
    blocks again, so reusing it would make the next long poll return instantly
    -- burning CPU and network for nothing.
    """
    data = ensure_data(hass)
    data["rev"] += 1
    previous = data["changed"]
    data["changed"] = asyncio.Event()
    previous.set()
