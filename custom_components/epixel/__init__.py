"""Bridge between Home Assistant and an ePiXeL information display.

This integration creates no entities in Home Assistant. Its only job is to
serve the entities you pick to an ePiXeL screen on your local network, and to
accept on/off commands coming back from that screen.

DIRECTION: the device makes the first move. It finds Home Assistant, pairs, and
tells us where to reach it. From then on WE push: the moment a tracked entity
changes, the new view goes straight to the screen.

That reversal is the whole point. The display used to ask every three seconds,
which is twenty round trips a minute for a screen that usually has nothing new
on it -- and the constrained side of that exchange was never Home Assistant, it
was the device. Now nothing crosses the network until something actually
changes. The device still polls, but only as a fallback: pushing depends on an
address that DHCP can change underneath us, and a push into nowhere fails
silently. See PROTOCOL.md.
"""

from __future__ import annotations

import asyncio
import logging

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .model import build_view, pages_of, tracked_entities
from .views import async_register_views

_LOGGER = logging.getLogger(__name__)

# There is nothing to configure in YAML -- the display is paired from the UI.
# async_setup still exists so the endpoints are up before the first config
# entry is created; this schema tells Home Assistant that is deliberate.
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


def ensure_data(hass: HomeAssistant) -> dict:
    """Process-wide shared state.

    Pairing records have to exist *before* any config entry does, which is why
    this lives outside of async_setup_entry.
    """
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {
            "rev": 1,                  # monotonic revision -- the heart of long polling
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
    """Advance the revision and send the new view to the display.

    The revision is what the device compares against to know whether the thing
    it is holding is current; the push is what makes it current.
    """
    data = ensure_data(hass)
    data["rev"] += 1
    _schedule_push(hass)


# How long to wait before pushing, so one scene becomes one packet.
#
# Turning on a room lights six bulbs, and Home Assistant reports each one
# separately. Sending on every report would put six packets on the wire for a
# single press, and the display would redraw six times. Waiting a moment
# collapses the burst into one message with the final state in it.
#
# Long enough to catch a scene, short enough that nobody sees it.
PUSH_DEBOUNCE_S = 0.25

# Give up quickly. The display is on the same LAN; if it does not answer in a
# couple of seconds it is gone, and holding the connection would only delay the
# next update.
PUSH_TIMEOUT_S = 3


@callback
def _schedule_push(hass: HomeAssistant) -> None:
    """Queue one push, coalescing whatever else arrives meanwhile."""
    data = hass.data.get(DOMAIN) or {}
    if not data.get("device"):
        return
    task = data.get("push_task")
    if task and not task.done():
        # One is already waiting out its debounce. It will read the state when
        # it wakes, so it will carry this change too -- queueing a second task
        # would send the same view twice.
        return
    data["push_task"] = hass.async_create_task(_push_after_debounce(hass))


async def _push_after_debounce(hass: HomeAssistant) -> None:
    await asyncio.sleep(PUSH_DEBOUNCE_S)

    data = hass.data.get(DOMAIN) or {}
    device = data.get("device")
    entry = next(iter(hass.config_entries.async_entries(DOMAIN)), None)
    if not device or entry is None:
        return

    session = async_get_clientsession(hass)
    url = f"http://{device['ip']}:{device['port']}/push"
    try:
        async with session.post(
            url,
            json=build_view(hass, entry),
            headers={"X-EPX-Push": device["secret"]},
            timeout=aiohttp.ClientTimeout(total=PUSH_TIMEOUT_S),
        ) as response:
            if response.status == 401:
                # The display restarted and made a new secret. Its next
                # announcement, a minute away at most, brings the new one.
                _LOGGER.debug("display rejected the push secret; awaiting announce")
                data.pop("device", None)
            elif response.status >= 400:
                _LOGGER.debug("display answered %s to a push", response.status)
    except (aiohttp.ClientError, asyncio.TimeoutError):
        # Almost always a display that moved to a new address or went off.
        # Not worth a warning: it polls as a fallback and re-announces itself,
        # so this heals on its own within the silence window.
        _LOGGER.debug("could not reach the display at %s", url)
