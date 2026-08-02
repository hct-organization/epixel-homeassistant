# Changelog

## 0.2.0

Protocol v2.

- **Dimmable lights.** A light that reports a brightness capability gets a
  level control instead of a plain toggle. `up` and `down` are resolved against
  the light's live level, so a lamp changed at a wall switch does not jump on
  the first press; anything under five percent turns it off rather than leaving
  a level nobody can see.
- **Icons come from Material Design Icons** — the family Home Assistant itself
  uses, so an icon on the display matches the one beside the entity. 34 shapes,
  vendored with their upstream names; the firmware glyphs are generated from
  the same file, so preview and hardware cannot drift.
- **Icons can be chosen per entity** from a menu entry, defaulting to automatic
  detection. A stored choice the display cannot draw is discarded rather than
  sent.
- **Screen preview.** A link in the options menu renders the pages at the
  display's real resolution in a browser. Valid for one hour, replaced each
  time the menu is opened.
- **Display names are normalised** before they go on the wire: control
  characters and line breaks become spaces, whitespace collapses, ends are
  trimmed. `k` stays the only identifier; `n` is for the human alone.
- Self-test covering the page model, icon selection, name handling and the
  preview, running without a Home Assistant install.

## 0.1.0

First working version. Protocol v1.

- PIN pairing initiated by the display; no listening port on the device
- Page builder in Home Assistant's own UI (up to 8 pages, 6 boxes each)
- Long-polled `/view` endpoint — push-grade latency, no persistent socket
- On/off control for `switch`, `light`, `input_boolean`, `fan`
- 24-hour charts for numeric sensors, downsampled to 60 points server-side
- `tools/fake_device.py` — exercises the integration without any hardware

Known limitations: one display per Home Assistant instance; plain HTTP on the
local network only.
