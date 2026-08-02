"""Maps a Home Assistant device_class (or unit, or domain) to an ePiXeL icon name.

WHY NOT mdi: Home Assistant's mdi icon namespace has 7000+ names and cannot fit
on the device. `device_class` is a small, stable vocabulary -- binding the
mapping to it keeps working for years without firmware changes.

The returned name MUST come from the fixed set in PROTOCOL.md. Returning
anything else would draw an empty box on the screen, so unknown inputs fall
back to "dot".
"""

FALLBACK = "dot"

# Must stay identical to the icon list in PROTOCOL.md. A name whose glyph is not
# in the device font does NOT belong here -- generate the font first, then grow
# this set. The reverse order shows empty squares to the user.
VALID = frozenset({
    "dot", "bulb", "plug", "temp", "hum", "power", "energy", "battery",
    "motion", "door", "window", "lock", "water", "fire", "gas", "co2",
    "lux", "press", "fan", "wind", "rain", "signal", "clock", "person",
    "tv", "music", "cool", "heat", "valve", "sun", "moon", "shield",
})

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
    "switch": "plug",
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
    "switch": "plug",
    "fan": "fan",
    "input_boolean": "dot",
    "binary_sensor": "dot",
    "sensor": "dot",
    "media_player": "tv",
    "climate": "heat",
    "cover": "window",
    "lock": "lock",
}


def pick(domain: str, device_class: str | None, unit: str | None = None) -> str:
    """Choose an icon for a box. The result is always a member of VALID."""
    for candidate in (
        BY_DEVICE_CLASS.get(device_class or ""),
        BY_UNIT.get((unit or "").strip()),
        BY_DOMAIN.get(domain),
    ):
        if candidate and candidate in VALID:
            return candidate
    return FALLBACK
