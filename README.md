<p align="center">
  <img src="docs/images/hero.png" alt="ePiXeL display showing a Home Assistant page" width="640">
</p>

<h1 align="center">ePiXeL Display — Home Assistant Integration</h1>

<p align="center">
  <b>Your lights, sockets and sensors on a real screen. Touch to switch. Tap to chart.</b>
</p>

<p align="center">
  <a href="https://github.com/hct-organization/epixel-homeassistant/actions/workflows/hassfest.yaml"><img src="https://github.com/hct-organization/epixel-homeassistant/actions/workflows/hassfest.yaml/badge.svg" alt="hassfest"></a>
  <a href="https://github.com/hct-organization/epixel-homeassistant/actions/workflows/hacs.yaml"><img src="https://github.com/hct-organization/epixel-homeassistant/actions/workflows/hacs.yaml/badge.svg" alt="HACS validation"></a>
  <a href="https://hacs.xyz"><img src="https://img.shields.io/badge/HACS-custom-41BDF5.svg" alt="HACS custom"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="MIT"></a>
</p>

---

The **ePiXeL** information display is a wall- or desk-mounted 4-inch touch screen
that cycles through the things a household or a business cares about — currency
rates, weather, news, prayer times, radio, intercom. This integration adds one
more thing to that carousel: **your home.**

You choose which entities appear, and how they are grouped into pages, from
Home Assistant's own interface. The screen simply draws them.

## What it does

- **Live values** — sensors update the moment they change in Home Assistant.
  No polling delay you can feel.
- **Touch to switch** — lights, sockets, fans and helpers toggle straight from
  the screen.
- **Tap for a chart** — any numeric sensor with recorder history shows a 24-hour
  graph.
- **Pages you design** — 2, 4 or 6 boxes per page, up to 8 pages. Layout is
  derived from how many entities you pick.
- **Fits the carousel** — Home Assistant pages take their turn alongside the
  screen's other content, or you can pin them.
- **Nothing leaves your network.** No cloud account, no relay, no telemetry
  about your home.

## Screenshots

| Pairing | Page builder | On the screen |
|:--:|:--:|:--:|
| <img src="docs/images/pairing.png" width="240"> | <img src="docs/images/page-builder.png" width="240"> | <img src="docs/images/device-page.jpg" width="240"> |

## How it works

```
   Home Assistant                                ePiXeL display
   ─────────────────                             ────────────────
   you build the pages   ◀── HTTP, local only ──   draws the pages
   you pick the entities      (device initiated)   sends touch commands
```

Every connection is made **by the display, towards Home Assistant**. The display
opens no listening port, so it adds no attack surface to your network. Updates
arrive over a long-polled HTTP request, which gives push-grade latency without a
permanently open socket.

## Requirements

- Home Assistant **2026.7** or newer
- An ePiXeL display on the same local network
- `recorder` enabled (default) if you want charts

## Installation

### HACS (recommended)

1. HACS → three-dot menu → **Custom repositories**
2. Repository: `https://github.com/hct-organization/epixel-homeassistant` · Type: **Integration**
3. Find **ePiXeL Display** in HACS → **Download**
4. **Restart Home Assistant**

[![Open HACS repository](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=hct-organization&repository=epixel-homeassistant&category=integration)

### Manual

Copy `custom_components/epixel` into your Home Assistant `config/custom_components/`
directory and restart.

## Pairing

1. On the display: **Settings → Home Assistant → Find server**, then pick your server
2. The display shows a **4-digit code**, valid for 3 minutes
3. In Home Assistant: **Settings → Devices & Services → Add Integration → ePiXeL**
4. Enter the code

[![Add integration](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=epixel)

The code travels in one direction only — from the screen you are looking at, to
the browser you are logged into. Nothing sensitive is typed on the touch keyboard.

## Building pages

**Settings → Devices & Services → ePiXeL → Configure**

Add a page, give it a title, and select the entities. The layout follows the
number of entities you choose:

| Entities | Layout |
|---|---|
| 2 | side by side |
| 3–4 | 2 × 2 |
| 5–6 | 2 × 3 |

Up to **8 pages**, **6 boxes** each. Changes reach the screen as soon as you save.

### Supported entities

| Domain | On the screen |
|---|---|
| `sensor` | value + unit, chart when history is available |
| `binary_sensor` | on / off, read-only |
| `switch` · `light` · `input_boolean` · `fan` | on / off, **touchable** |

Read-only boxes are drawn differently from actionable ones, so nobody presses a
box expecting it to do something.

## Privacy

- All traffic stays on your local network. There is **no cloud component**.
- The display sees **only the entities you selected** — not the rest of your home.
- The display's own cloud credentials and serial identity are **never sent** to
  Home Assistant.
- Home Assistant data is **never forwarded** to ePiXeL servers.
- Revoke access at any time by deleting the integration.

The pairing token is carried over plain HTTP on your LAN. That is a deliberate
trade-off: Wi-Fi is already encrypted, the token's authority is limited to the
entities you picked, and revocation is one click. TLS-only Home Assistant
installations are on the roadmap.

## Try it without the hardware

A terminal-based fake display is included. It pairs, long-polls and renders your
pages as text — useful for checking your layout before mounting anything.

```bash
python3 tools/fake_device.py 192.168.1.40
```

Standard library only; nothing to install.

## Troubleshooting

| Symptom | Check |
|---|---|
| Display says "integration not found" | Did Home Assistant restart after installing? |
| Code not accepted | Codes expire after 3 minutes — generate a new one on the display |
| "Already configured" | One display per Home Assistant in this version; remove the existing entry first |
| Box shows `—` | The entity is unavailable or was deleted in Home Assistant |
| No chart on a sensor | The sensor needs a `state_class` and recorder history |

Logs: `Settings → System → Logs`, filter for `custom_components.epixel`.

## Roadmap

- [ ] More than one display per Home Assistant instance
- [ ] `climate`, `cover` and `scene` support
- [ ] TLS-only Home Assistant installations (certificate pinning)
- [ ] Diagnostic sensor showing display connectivity
- [ ] Submission to the HACS default store

---

## About the ePiXeL display

<img src="docs/images/device.jpg" align="right" width="260" alt="ePiXeL display">

ePiXeL is a commercial information display built for shops, offices, lobbies and
homes. It runs custom firmware on an ESP32-S3 with an 8 MB PSRAM budget, a 4-inch
touch panel, speaker and microphone, and it is managed remotely with signed
over-the-air updates.

Out of the box it shows currency and market data, weather, news, prayer times,
horoscopes, internet radio and a push-to-talk intercom. With this integration it
also shows your Home Assistant.

**Ordering.** The display is produced in batches, with a **minimum order of 500
units**. For pricing, lead times, branding and distribution please get in touch
through our website:

### 👉 **[epixel.app](https://epixel.app)**

*(Product video and photo gallery coming soon.)*

---

## Contributing

Issues and pull requests are welcome. The wire format is documented in
**[PROTOCOL.md](PROTOCOL.md)** — please read it before changing anything the
display consumes, since firmware in the field is written against it.

## License

Source code in this repository is released under the **MIT License** — see
[LICENSE](LICENSE).

*ePiXeL* and the ePiXeL logo are trademarks of HCT. The licence covers this
integration's source code only; it grants no rights to the ePiXeL name, logo,
firmware or hardware design.
