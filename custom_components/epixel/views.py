"""The five HTTP endpoints the device talks to. Contract: PROTOCOL.md

This module imports NOTHING from __init__ (that would be circular); it reaches
shared state through hass.data[DOMAIN].
"""

from __future__ import annotations

import asyncio
import functools
import hmac
import logging
import time
from datetime import timedelta

from homeassistant.components.http import KEY_HASS, HomeAssistantView
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import __version__ as HA_VERSION
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .const import (
    API_BASE,
    CONF_TOKEN,
    DOMAIN,
    HISTORY_MAX_HOURS,
    HISTORY_POINTS,
    LONGPOLL_MAX_S,
    PAIR_MAX_PENDING,
    PAIR_TTL_S,
    PROTOCOL_VERSION,
    SWITCHABLE_DOMAINS,
)
from .model import build_view, key_map

_LOGGER = logging.getLogger(__name__)

_ACTIONS = {"toggle": "toggle", "on": "turn_on", "off": "turn_off"}


def async_register_views(hass: HomeAssistant) -> None:
    """Register the endpoints once. A second call is a no-op, so reloading the
    config entry does not register duplicates."""
    data = hass.data.get(DOMAIN)
    if data is None or data.get("views_ok"):
        return
    for view in (PingView(), PairView(), StateView(), CmdView(), HistoryView()):
        hass.http.register_view(view)
    data["views_ok"] = True
    _LOGGER.debug("ePiXeL endpoints registered under %s", API_BASE)


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
    """On/off. The device updates its UI optimistically and REVERTS on ok:false."""

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
        if domain not in SWITCHABLE_DOMAINS:
            return self.json({"ok": False, "e": "not_switchable"})

        service = _ACTIONS.get(str(body.get("a", "toggle")))
        if service is None:
            return self.json({"ok": False, "e": "bad_action"})

        try:
            await hass.services.async_call(
                domain, service, {"entity_id": entity_id}, blocking=True
            )
        except Exception as err:  # noqa: BLE001 -- service calls raise many types
            _LOGGER.warning("ePiXeL command failed (%s.%s): %s", domain, service, err)
            return self.json({"ok": False, "e": "service_failed"})

        state = hass.states.get(entity_id)
        return self.json({"ok": True, "v": 1 if state and state.state == "on" else 0})


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
