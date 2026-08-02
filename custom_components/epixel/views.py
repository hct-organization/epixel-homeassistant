"""The HTTP endpoints the display talks to, plus the browser preview.

Contract: PROTOCOL.md

This module imports NOTHING from __init__ (that would be circular); it reaches
shared state through hass.data[DOMAIN].
"""

from __future__ import annotations

import asyncio
import functools
import hmac
import logging
import secrets
import time
from datetime import timedelta

from homeassistant.components.http import KEY_HASS, HomeAssistantView
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import __version__ as HA_VERSION
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from . import preview as preview_page
from .const import (
    API_BASE,
    CONF_DEVICE_NAME,
    CONF_TOKEN,
    DIM_MIN,
    DIM_STEP,
    DOMAIN,
    HISTORY_MAX_HOURS,
    HISTORY_POINTS,
    LONGPOLL_MAX_S,
    PAIR_MAX_PENDING,
    PAIR_TTL_S,
    PREVIEW_TTL_S,
    PROTOCOL_VERSION,
    SWITCHABLE_DOMAINS,
)
from .icons import supports_brightness
from .model import build_view, key_map

_LOGGER = logging.getLogger(__name__)

_SWITCH_ACTIONS = {"toggle": "toggle", "on": "turn_on", "off": "turn_off"}
_DIM_ACTIONS = ("set", "up", "down")


def async_register_views(hass: HomeAssistant) -> None:
    """Register the endpoints once. A second call is a no-op, so reloading the
    config entry does not register duplicates."""
    data = hass.data.get(DOMAIN)
    if data is None or data.get("views_ok"):
        return
    for view in (
        PingView(),
        PairView(),
        StateView(),
        CmdView(),
        HistoryView(),
        PreviewView(),
    ):
        hass.http.register_view(view)
    data["views_ok"] = True
    _LOGGER.debug("ePiXeL endpoints registered under %s", API_BASE)


def new_preview_key(hass: HomeAssistant) -> str:
    """Mint a fresh capability key for the screen preview.

    The preview shows entity names and current states, so it is not public. A
    new key is issued each time the options flow opens and the previous one
    stops working, which keeps a link pasted into a chat from staying useful.
    """
    key = secrets.token_urlsafe(16)
    hass.data[DOMAIN]["preview"] = {
        "key": key,
        "expires": time.monotonic() + PREVIEW_TTL_S,
    }
    return key


def _entry(hass: HomeAssistant) -> ConfigEntry | None:
    entries = hass.config_entries.async_entries(DOMAIN)
    return entries[0] if entries else None


def _authed(hass: HomeAssistant, request) -> ConfigEntry | None:
    """Return the config entry when the token is valid, otherwise None.
    Comparison is constant time."""
    entry = _entry(hass)
    if entry is None:
        return None
    supplied = request.headers.get("X-EPX-Token", "")
    expected = entry.data.get(CONF_TOKEN, "")
    if not supplied or not expected:
        return None
    return entry if hmac.compare_digest(supplied, expected) else None


# ---------------------------------------------------------------- 1. ping


class PingView(HomeAssistantView):
    """Discovery. Unauthenticated -- its only job is to answer "is the ePiXeL
    integration installed here?".

    Deliberately MINIMAL: it leaks no instance name, location or entity count.
    This is the least that can be said to an unauthenticated caller.
    """

    url = f"{API_BASE}/ping"
    name = "api:epixel:ping"
    requires_auth = False

    async def get(self, request):
        return self.json({"epixel": 1, "ver": PROTOCOL_VERSION, "hass": HA_VERSION})


# ---------------------------------------------------------------- 2. pair


class PairView(HomeAssistantView):
    """Pairing. Called every 2 seconds while the code is on the device screen.

    Unauthenticated by necessity (the device has no token yet). Three
    safeguards work together: a 180 s window, at most 3 pending requests, and
    at most 5 wrong-code entries (enforced in the config flow).
    """

    url = f"{API_BASE}/pair"
    name = "api:epixel:pair"
    requires_auth = False

    async def post(self, request):
        hass: HomeAssistant = request.app[KEY_HASS]
        data = hass.data.get(DOMAIN)
        if data is None:
            return self.json({"status": "waiting"})

        try:
            body = await request.json()
        except ValueError:
            return self.json({"e": "bad_json"}, status_code=400)

        pin = str(body.get("pin", "")).strip()[:8]
        session = str(body.get("session", "")).strip()[:32]
        name = str(body.get("name", "ePiXeL Display")).strip()[:40] or "ePiXeL Display"
        if not pin or not session:
            return self.json({"e": "bad_request"}, status_code=400)

        now = time.monotonic()
        pending: dict = data["pending"]
        for stale in [s for s, rec in pending.items() if rec["expires"] < now]:
            pending.pop(stale, None)

        record = pending.get(session)
        if record is None:
            if len(pending) >= PAIR_MAX_PENDING:
                return self.json({"status": "busy"}, status_code=429)
            record = {"pin": pin, "name": name, "expires": now + PAIR_TTL_S, "token": None}
            pending[session] = record
            _LOGGER.info("ePiXeL pairing request received: %s", name)
        else:
            record["pin"] = pin
            record["name"] = name

        if record["token"]:
            token = record["token"]
            pending.pop(session, None)          # a token is handed out exactly once
            data["attempts"] = 0
            _LOGGER.info("ePiXeL paired: %s", name)
            return self.json(
                {
                    "status": "paired",
                    "token": token,
                    "hass_name": hass.config.location_name or "Home Assistant",
                }
            )

        return self.json({"status": "waiting"})


# ---------------------------------------------------------------- 3. view


class StateView(HomeAssistantView):
    """Pages, boxes and current values in a single document. Long-poll capable."""

    url = f"{API_BASE}/view"
    name = "api:epixel:view"
    requires_auth = False

    async def get(self, request):
        hass: HomeAssistant = request.app[KEY_HASS]
        entry = _authed(hass, request)
        if entry is None:
            return self.json({"e": "unauthorized"}, status_code=401)

        data = hass.data[DOMAIN]
        try:
            since = int(request.query.get("rev", "0"))
            wait = int(request.query.get("wait", "0"))
        except ValueError:
            since, wait = 0, 0
        wait = max(0, min(wait, LONGPOLL_MAX_S))

        # When the device already holds the current revision we hold the
        # request open. A change releases it immediately -- push-grade latency
        # with no persistent socket.
        if wait and since == data["rev"]:
            waiter = data["changed"]
            try:
                await asyncio.wait_for(waiter.wait(), wait)
            except asyncio.TimeoutError:
                pass

        return self.json(build_view(hass, entry))


# ---------------------------------------------------------------- 4. cmd


class CmdView(HomeAssistantView):
    """Switching and dimming. The device updates its UI optimistically and
    REVERTS on ok:false."""

    url = f"{API_BASE}/cmd"
    name = "api:epixel:cmd"
    requires_auth = False

    async def post(self, request):
        hass: HomeAssistant = request.app[KEY_HASS]
        entry = _authed(hass, request)
        if entry is None:
            return self.json({"ok": False, "e": "unauthorized"}, status_code=401)

        try:
            body = await request.json()
        except ValueError:
            return self.json({"ok": False, "e": "bad_json"}, status_code=400)

        entity_id = key_map(entry).get(str(body.get("k", "")))
        if not entity_id:
            return self.json({"ok": False, "e": "entity_not_found"})

        domain = entity_id.split(".", 1)[0]
        action = str(body.get("a", "toggle"))

        if action in _DIM_ACTIONS:
            return await self._dim(hass, entity_id, domain, action, body)

        if domain not in SWITCHABLE_DOMAINS:
            return self.json({"ok": False, "e": "not_switchable"})

        service = _SWITCH_ACTIONS.get(action)
        if service is None:
            return self.json({"ok": False, "e": "bad_action"})

        if not await self._call(hass, domain, service, {"entity_id": entity_id}):
            return self.json({"ok": False, "e": "service_failed"})

        state = hass.states.get(entity_id)
        return self.json({"ok": True, "v": 1 if state and state.state == "on" else 0})

    async def _dim(self, hass, entity_id: str, domain: str, action: str, body: dict):
        """Set, raise or lower a light's level.

        `up` and `down` are resolved against the light's CURRENT level rather
        than a level the device believes in. A device that missed an update, or
        a light someone changed from a wall switch, would otherwise jump to the
        wrong value on the first press.
        """
        state = hass.states.get(entity_id)
        if domain != "light" or state is None or not supports_brightness(state.attributes):
            return self.json({"ok": False, "e": "not_dimmable"})

        current = 0
        if state.state == "on":
            raw = state.attributes.get("brightness")
            current = 100 if raw is None else max(1, round(int(raw) * 100 / 255))

        if action == "set":
            try:
                target = int(body.get("p"))
            except (TypeError, ValueError):
                return self.json({"ok": False, "e": "bad_level"})
        elif action == "up":
            target = current + DIM_STEP
        else:
            target = current - DIM_STEP

        target = max(0, min(100, target))

        # Anything under the floor is off, not "very dim". Sending
        # brightness_pct=2 leaves a light that looks off but reports on, and
        # the next press then raises it from 2 instead of from zero.
        if target < DIM_MIN:
            ok = await self._call(hass, "light", "turn_off", {"entity_id": entity_id})
            return self.json({"ok": ok, "v": 0} if ok else {"ok": False, "e": "service_failed"})

        ok = await self._call(
            hass, "light", "turn_on", {"entity_id": entity_id, "brightness_pct": target}
        )
        if not ok:
            return self.json({"ok": False, "e": "service_failed"})
        return self.json({"ok": True, "v": target})

    @staticmethod
    async def _call(hass, domain: str, service: str, payload: dict) -> bool:
        try:
            await hass.services.async_call(domain, service, payload, blocking=True)
        except Exception as err:  # noqa: BLE001 -- service calls raise many types
            _LOGGER.warning("ePiXeL command failed (%s.%s): %s", domain, service, err)
            return False
        return True


# ------------------------------------------------------------ 5. history


class HistoryView(HomeAssistantView):
    """Chart series. The heavy lifting happens here: raw history can run to
    megabytes, while the device receives 60 points (~400 bytes)."""

    url = f"{API_BASE}/history"
    name = "api:epixel:history"
    requires_auth = False

    async def get(self, request):
        hass: HomeAssistant = request.app[KEY_HASS]
        entry = _authed(hass, request)
        if entry is None:
            return self.json({"e": "unauthorized"}, status_code=401)

        key = str(request.query.get("k", ""))
        entity_id = key_map(entry).get(key)
        if not entity_id:
            return self.json({"e": "entity_not_found"}, status_code=404)

        try:
            hours = int(request.query.get("h", "24"))
        except ValueError:
            hours = 24
        hours = max(1, min(hours, HISTORY_MAX_HOURS))

        try:
            from homeassistant.components.recorder import get_instance, history
        except ImportError:
            return self.json({"e": "no_history"}, status_code=404)

        start = dt_util.utcnow() - timedelta(hours=hours)
        job = functools.partial(
            history.state_changes_during_period,
            hass,
            start,
            None,
            entity_id,
            no_attributes=True,
            include_start_time_state=True,
        )
        try:
            raw = await get_instance(hass).async_add_executor_job(job)
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("ePiXeL history unavailable (%s): %s", entity_id, err)
            return self.json({"e": "no_history"}, status_code=404)

        series: list[tuple[float, float]] = []
        for state in raw.get(entity_id, []):
            try:
                series.append((state.last_updated.timestamp(), float(state.state)))
            except (TypeError, ValueError, AttributeError):
                continue

        if len(series) < 2:
            return self.json({"e": "no_history"}, status_code=404)

        points = _downsample(series, HISTORY_POINTS)
        current = hass.states.get(entity_id)
        unit = ""
        if current:
            unit = str(current.attributes.get("unit_of_measurement") or "")[:8]

        return self.json(
            {
                "k": key,
                "u": unit,
                "min": round(min(points), 1),
                "max": round(max(points), 1),
                "n": len(points),
                "p": [int(round(value * 10)) for value in points],
            }
        )


# ------------------------------------------------------------ 6. preview


class PreviewView(HomeAssistantView):
    """The pages as the display will draw them, in a browser.

    Not part of the device protocol -- the display never calls this. It exists
    so the person building a page can see the result without walking over to
    the screen.
    """

    url = f"{API_BASE}/preview"
    name = "api:epixel:preview"
    requires_auth = False

    async def get(self, request):
        hass: HomeAssistant = request.app[KEY_HASS]
        data = hass.data.get(DOMAIN) or {}
        record = data.get("preview") or {}
        supplied = str(request.query.get("k", ""))

        valid = (
            record.get("key")
            and supplied
            and hmac.compare_digest(supplied, record["key"])
            and record.get("expires", 0) > time.monotonic()
        )
        if not valid:
            return self.json({"e": "unauthorized"}, status_code=401)

        entry = _entry(hass)
        if entry is None:
            return self.json({"e": "not_configured"}, status_code=404)

        html = preview_page.render(
            build_view(hass, entry),
            hass.config.language,
            entry.data.get(CONF_DEVICE_NAME) or "ePiXeL",
        )
        return web_response(html)


def web_response(html: str):
    from aiohttp import web

    return web.Response(text=html, content_type="text/html", charset="utf-8")


def _downsample(series: list[tuple[float, float]], count: int) -> list[float]:
    """Average into time-equal buckets; an empty bucket carries the last value.

    Buckets are cut by TIME, not by sample count. Event frequency varies wildly
    between entities (a motion sensor fires per second, a temperature sensor
    per minute), and count-equal buckets would distort the chart.
    """
    first, last = series[0][0], series[-1][0]
    if last <= first:
        return [series[-1][1]] * count

    step = (last - first) / count
    out: list[float] = []
    index = 0
    carried = series[0][1]

    for bucket in range(count):
        edge = first + step * (bucket + 1)
        total, seen = 0.0, 0
        while index < len(series) and series[index][0] <= edge:
            total += series[index][1]
            seen += 1
            index += 1
        if seen:
            carried = total / seen
        out.append(carried)

    return out
