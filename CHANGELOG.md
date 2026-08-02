# Changelog

## 0.1.0 — unreleased

First working version. Protocol v1.

- PIN pairing initiated by the display; no listening port on the device
- Page builder in Home Assistant's own UI (up to 8 pages, 6 boxes each)
- Long-polled `/view` endpoint — push-grade latency, no persistent socket
- On/off control for `switch`, `light`, `input_boolean`, `fan`
- 24-hour charts for numeric sensors, downsampled to 60 points server-side
- `tools/fake_device.py` — exercises the integration without any hardware

Known limitations: one display per Home Assistant instance; plain HTTP on the
local network only.
