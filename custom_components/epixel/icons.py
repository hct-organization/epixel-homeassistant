"""Chooses which of the display's icons represents an entity.

WHY NOT PASS mdi NAMES THROUGH: Home Assistant's icon namespace runs to several
thousand names; the display carries a fixed set. `device_class` is a small,
stable vocabulary, so binding the mapping to it keeps working for years without
a firmware change.

The set itself lives in `icon_paths.py` -- one place, so the picker, the
on-screen preview and the glyphs embedded in the firmware cannot drift apart.
A user can override the choice per entity when building a page.
"""

from __future__ import annotations

from .icon_paths import ICON_PATHS

FALLBACK = "dot"
AUTO = "auto"

#: Every icon the display can draw. Single source of truth.
VALID = frozenset(ICON_PATHS)

#: Same set, in the order the picker lists them -- related shapes stay together
#: so the dropdown can be scanned instead of read.
ICON_ORDER = tuple(ICON_PATHS)

BY_DEVICE_CLASS = {
    "temperature": "temp",
    "humidity": "hum",
    "moisture": "water",
    "water": "water",
    "power": "power",
    "voltage": "power",
    "current": "power",
    "power_factor": "power",
    "energy": "energy",
    "battery": "battery",
    "motion": "motion",
    "occupancy": "person",
    "presence": "person",
    "door": "door",
    "garage_door": "door",
    "opening": "door",
    "window": "window",
    "lock": "lock",
    "smoke": "fire",
    "heat": "fire",
    "gas": "gas",
    "carbon_monoxide": "gas",
    "carbon_dioxide": "co2",
    "pm25": "gas",
    "pm10": "gas",
    "pm1": "gas",
    "nitrogen_dioxide": "gas",
    "volatile_organic_compounds": "gas",
    "aqi": "gas",
    "illuminance": "lux",
    "irradiance": "sun",
    "uv_index": "sun",
    "pressure": "press",
    "atmospheric_pressure": "press",
    "wind_speed": "wind",
    "precipitation": "rain",
    "precipitation_intensity": "rain",
    "signal_strength": "signal",
    "connectivity": "signal",
    "timestamp": "clock",
    "duration": "clock",
    "sound_pressure": "music",
    "running": "fan",
    "problem": "shield",
    "safety": "shield",
    "tamper": "shield",
    "outlet": "plug",
    "plug": "plug",
    "switch": "switch",
}

BY_UNIT = {
    "°C": "temp", "°F": "temp", "K": "temp",
    "%": "hum",
    "W": "power", "kW": "power", "V": "power", "A": "power", "mA": "power",
    "kWh": "energy", "Wh": "energy", "MWh": "energy",
    "lx": "lux",
    "hPa": "press", "mbar": "press", "bar": "press", "Pa": "press", "psi": "press",
    "ppm": "co2",
    "dB": "music", "dBA": "music",
    "km/h": "wind", "m/s": "wind", "mph": "wind",
    "mm": "rain",
    "dBm": "signal",
}

BY_DOMAIN = {
    "light": "bulb",
    "switch": "switch",
    "input_boolean": "switch",
    "fan": "fan",
    "binary_sensor": "dot",
    "sensor": "dot",
    "media_player": "tv",
    "climate": "heat",
    "cover": "window",
    "lock": "lock",
}


def supports_brightness(attrs) -> bool:
    """True when a light can be dimmed rather than only switched.

    Read from the entity's own capability report, not from a list of models --
    a light that gains dimming after a firmware update is picked up on its own.
    """
    modes = attrs.get("supported_color_modes") or ()
    dimmable = {"brightness", "color_temp", "hs", "rgb", "rgbw", "rgbww", "xy", "white"}
    return any(str(mode) in dimmable for mode in modes)


def pick(domain: str, attrs) -> str:
    """Choose an icon for a box. The result is always a member of VALID."""
    if domain == "light":
        return "dimmer" if supports_brightness(attrs) else "bulb"

    for candidate in (
        BY_DEVICE_CLASS.get(str(attrs.get("device_class") or "")),
        BY_UNIT.get(str(attrs.get("unit_of_measurement") or "").strip()),
        BY_DOMAIN.get(domain),
    ):
        if candidate and candidate in VALID:
            return candidate
    return FALLBACK


def normalise(name: str | None) -> str | None:
    """Accept a stored override only if the display can actually draw it.

    A name that survived from an older release, or a typo in a restored
    backup, would otherwise reach the device and draw an empty square.
    """
    if not name or name == AUTO:
        return None
    return name if name in VALID else None
