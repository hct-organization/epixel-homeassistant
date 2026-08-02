<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/images/epixel-logo-dark.png">
    <img src="docs/images/epixel-logo-light.png" alt="ePiXeL" width="280">
  </picture>
</p>

<h1 align="center">ePiXeL Display — Home Assistant Integration</h1>

<p align="center">
  <b>Your lights, sockets and sensors on a real screen.<br>Touch to switch. Tap to chart. Nothing leaves your network.</b>
</p>

<p align="center">
  <a href="https://github.com/hct-organization/epixel-homeassistant/actions/workflows/hassfest.yaml"><img src="https://github.com/hct-organization/epixel-homeassistant/actions/workflows/hassfest.yaml/badge.svg" alt="hassfest"></a>
  <a href="https://github.com/hct-organization/epixel-homeassistant/actions/workflows/hacs.yaml"><img src="https://github.com/hct-organization/epixel-homeassistant/actions/workflows/hacs.yaml/badge.svg" alt="HACS validation"></a>
  <a href="https://hacs.xyz"><img src="https://img.shields.io/badge/HACS-custom-41BDF5.svg" alt="HACS custom"></a>
  <a href="https://www.home-assistant.io"><img src="https://img.shields.io/badge/Home%20Assistant-2026.7%2B-03A9F4.svg" alt="Home Assistant 2026.7+"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="MIT"></a>
</p>

---

**ePiXeL** is a networked information display designed and manufactured by
**HCT Bilişim**. It sits on a desk or a wall and cycles through live market data,
news, weather, radio and more — and with this integration, through your
Home Assistant.

You choose which entities appear and how they are grouped into pages, using
Home Assistant's own interface. The display simply draws them.

> **Looking for the device itself?** See [The ePiXeL display](#the-epixel-display)
> further down, or the product page at
> **[epixel.app](https://epixel.app/en/products/epixel-ekran)**. It is a business
> product, not a retail one — [epixel@hctbilisim.com](mailto:epixel@hctbilisim.com).

---

## Table of contents

- [What this integration does](#what-this-integration-does)
- [How it works](#how-it-works)
- [Installation](#installation)
- [Pairing](#pairing)
- [Building pages](#building-pages)
- [Privacy](#privacy)
- [Try it without the hardware](#try-it-without-the-hardware)
- [Troubleshooting](#troubleshooting)
- [The ePiXeL display](#the-epixel-display)
- [Ordering](#ordering)

---

## What this integration does

- **Live values** — sensors update the moment they change in Home Assistant.
  Not a polling delay you can feel.
- **Touch to switch** — lights, sockets, fans and helpers toggle from the screen.
- **Tap for a chart** — any numeric sensor with recorder history draws a
  24-hour graph.
- **Pages you design** — 2, 4 or 6 boxes per page, up to 8 pages. The layout
  follows how many entities you pick.
- **Joins the carousel** — Home Assistant pages take their turn alongside the
  display's other content, with a dwell time you control.
- **Local only** — no cloud account, no relay, no telemetry about your home.

### See it before it ships

The integration serves a **live preview of the device screen** at
`http://<your-home-assistant>:8123/api/epixel/preview`. It renders your pages at
the display's real resolution, so you can adjust a layout without walking over
to the device. Open it from the integration's **Configure** screen.

---

## How it works

```
   Home Assistant                                     ePiXeL display
   ─────────────────                                  ────────────────
   you build the pages    ◀── HTTP, local network ──   draws the pages
   you pick the entities       (device initiated)      sends touch commands
```

Every connection is made **by the display, towards Home Assistant**. The display
opens no listening port, so it adds no attack surface to your network. Updates
arrive over a long-polled HTTP request — push-grade latency without a
permanently open socket.

The complete wire format is documented in **[PROTOCOL.md](PROTOCOL.md)**.

### Requirements

- Home Assistant **2026.7** or newer
- An ePiXeL display on the same local network
- `recorder` enabled (it is by default) if you want charts

---

## Installation

### HACS — recommended

1. HACS → three-dot menu → **Custom repositories**
2. Repository: `https://github.com/hct-organization/epixel-homeassistant`
   Type: **Integration**
3. Find **ePiXeL Display** in HACS → **Download**
4. **Restart Home Assistant**

[![Open HACS repository](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=hct-organization&repository=epixel-homeassistant&category=integration)

### Manual

Copy `custom_components/epixel` into your Home Assistant `config/custom_components/`
directory and restart.

---

## Pairing

1. On the display: **Settings → Home Assistant → Find server**, then pick your server
2. The display shows a **4-digit code**, valid for 3 minutes
3. In Home Assistant: **Settings → Devices & Services → Add Integration → ePiXeL**
4. Enter the code

[![Add integration](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=epixel)

The code travels in one direction only — from the screen in front of you to the
browser you are already logged into. Nothing sensitive is typed on a touch
keyboard, and no long-lived access token has to be created by hand.

Pairing is protected by three limits working together: a **180-second window**,
at most **5 attempts**, and at most **3 pending requests**.

---

## Building pages

**Settings → Devices & Services → ePiXeL → Configure**

Add a page, give it a title, and select the entities. The layout follows the
number of entities you choose:

| Entities | Layout |
|---|---|
| 2 | side by side |
| 3–4 | 2 × 2 |
| 5–6 | 2 × 3 |

Up to **8 pages**, **6 boxes** each. Changes reach the display the moment you save.

### Supported entities

| Domain | On the display |
|---|---|
| `sensor` | value + unit, chart when history is available |
| `binary_sensor` | on / off, read-only |
| `switch` · `light` · `input_boolean` · `fan` | on / off, **touchable** |

Read-only boxes are drawn differently from actionable ones, so nobody presses a
box expecting something to happen.

---

## Privacy

- All traffic stays on your local network. There is **no cloud component** in
  this integration.
- The display sees **only the entities you selected** — not the rest of your home.
- The display's own platform credentials and serial identity are **never sent**
  to Home Assistant.
- Home Assistant data — entity names, states, history — is **never forwarded**
  to ePiXeL servers. Device telemetry carries counters only.
- The display connects to **private IP addresses only**; public addresses are refused.
- Revoke access at any time by deleting the integration.

The pairing token travels over plain HTTP on your LAN. That is a deliberate
trade-off: Wi-Fi is already encrypted by WPA2, the token's authority is limited
to the entities you picked, and revocation is one click. Support for TLS-only
Home Assistant installations is on the roadmap.

---

## Try it without the hardware

A terminal-based fake display is included. It pairs, long-polls and renders your
pages as text — useful for checking a layout before mounting anything.

```bash
python3 tools/fake_device.py 192.168.1.40
```

Standard library only; nothing to install.

---

## Troubleshooting

| Symptom | Check |
|---|---|
| No logo beside the entry in Devices & Services | Expected for now — Home Assistant loads artwork from its own brands repository. See [brands/](brands/) |
| Display says "integration not found" | Did Home Assistant restart after installing? |
| Code not accepted | Codes expire after 3 minutes — generate a new one on the display |
| "Already configured" | One display per Home Assistant in this version; remove the existing entry first |
| A box shows `—` | The entity is unavailable or was deleted in Home Assistant |
| No chart on a sensor | The sensor needs a `state_class` and recorder history |

Logs: **Settings → System → Logs**, filter for `custom_components.epixel`.

---

# The ePiXeL display

ePiXeL is a 4-inch networked information display built by **HCT Bilişim**. It is
a finished, in-production product: the firmware is complete, the management
platform is live, and units are manufactured in series.

It is designed for **banks, brokerage houses and foreign-exchange firms** to give
to their clients as a branded desktop device. It keeps the institution's name and
market data in front of the customer all day, and gives the institution a
channel back to that customer.

## Capabilities

### Market data

- **Live prices for 7,000+ instruments** across crypto, foreign exchange and
  Borsa İstanbul
- **Borsa İstanbul** — equities, gainers, losers, most-traded, order-book depth
- **Global indices**, FX pairs and CFDs
- **Cryptocurrencies** — full symbol coverage plus top gainers and losers
- **Company financials** — the latest published balance sheets
- **Economic calendar** — scheduled releases across several countries, with
  importance filtering
- **Price alarms** — per-symbol thresholds with configurable conditions,
  raised on the device with sound and a visual alert
- **Symbol card** — pull up any tracked instrument on demand, from any market

### Information

- **News** from multiple sources, refreshed continuously
- **Weather** by city
- **Prayer times** by city, with optional audible call
- **Horoscopes**
- **Trending topics**

### Personal tools

- **Calendar** — create and edit events on the device, synchronised with the platform
- **Reminders** and **notes**
- **Daily and recurring alarms**
- **Calculator**

### Communication

- **Device-to-device intercom.** Units talk to each other push-to-talk, like a
  walkie-talkie: named rooms, invitations, buddy lists, moderation. Audio is
  carried as Opus over UDP with per-room encryption keys, so the server relays
  without opening the audio.
- **Voice assistant.** Wake-word activation, spoken replies, and control over
  the device itself — open a page, set an alarm, add a reminder, start the radio.

### Media

- **Internet radio** — hundreds of stations
- **Photo album** — the user scans a QR code on the screen and uploads photos
  from their phone; the display then shows them as an album
- **Pushed media** — the operator can send an image or an audio file to a
  single device or a whole fleet

### Management platform

The panel is what turns a screen into a channel:

- **Surveys and questions** pushed to devices, with answers collected back
- **Images and audio** delivered to selected devices or the whole fleet
- **Page control** — which pages a device may show, and **how long each page
  stays on screen**, chosen per device
- **Remote configuration**, brightness, volume, language
- **Signed over-the-air updates** with staged rollout
- **Fleet health telemetry** — connectivity, memory, uptime, faults

### Smart home

- **Home Assistant integration** — this repository. Lights, sockets and sensors
  on the display, controlled by touch, entirely over the local network.

### Languages

Turkish and English.

## Hardware

| | |
|---|---|
| **Processor** | ESP32 |
| **Display** | 4-inch 320 × 480 IPS, portrait, SPI interface |
| **Touch** | Capacitive multi-touch panel, I²C, hardware interrupt line |
| **Audio out** | I²S digital audio into a class-D amplifier and integrated speaker |
| **Audio in** | I²S digital MEMS microphone, enabled only on user action |
| **Network** | 2.4 GHz Wi-Fi, 802.11 b/g/n, WPA2 / WPA3 compatible |
| **Storage** | Internal flash with an encrypted credential store and a dual-slot update layout |
| **Mounting** | Desk stand or wall bracket |

Mechanical dimensions, power figures, certification files and branding options
are supplied on request in a separate hardware datasheet.

## Firmware and platform engineering

The firmware runs natively on a real-time operating system, drawing the interface
on a dedicated task while network, audio and sensor work proceed on separate
ones. Real-time data and remote commands arrive over **MQTT with TLS**; bulk
transfers use HTTPS against **pinned root certificates**, and the build contains
no path that disables certificate verification.

Each unit carries a **hardware-unique identity derived from a factory-burned
eFuse**, so identity cannot be forged by copying firmware. Credentials are held
in **encrypted storage**. Firmware images are **elliptic-curve signed** and
verified on the device before installation, with downgrade prevention and
automatic rollback if a new version fails to come up healthy. The device runs no
listening service, management port, remote shell or default password — every
session is device-initiated.

Quality is enforced mechanically rather than by convention: the build is gated by
more than twenty automated checks covering layering, resource lifetimes, lock
ordering, touch-target sizes and release integrity, and each device can run a
**built-in self-test** across its own subsystems on request.

---

## Ordering

The display is **not sold at retail** and **does not operate on its own** — it
depends on the ePiXeL platform for market data, messaging, updates and
management.

| | |
|---|---|
| **Minimum order** | **500 units** |
| **Management panel** | provided under a lease, alongside the hardware |
| **Customisation** | client branding, page selection and content policy |
| **Product page** | **[epixel.app/en/products/epixel-ekran](https://epixel.app/en/products/epixel-ekran)** |
| **Contact** | **[epixel@hctbilisim.com](mailto:epixel@hctbilisim.com)** |

For pricing, lead times, branding and pilot programmes, get in touch by e-mail.

*Product photography and video coming soon.*

---

## Documentation

| Document | Contents |
|---|---|
| **[PROTOCOL.md](PROTOCOL.md)** | The wire contract between this integration and the display: five endpoints, field by field |
| **[docs/architecture.html](docs/architecture.html)** | System architecture, services, network topology and security posture — Turkish and English |
| **[SECURITY.md](SECURITY.md)** | Disclosure address, design notes for researchers, accepted risks |
| **[CHANGELOG.md](CHANGELOG.md)** | Release history |
| **[brands/](brands/)** | Artwork prepared for the Home Assistant brands repository |

## Contributing

Issues and pull requests are welcome. The wire format is documented in
**[PROTOCOL.md](PROTOCOL.md)** — please read it before changing anything the
display consumes, since firmware already in the field is written against it.

## License

Source code in this repository is released under the **MIT License** — see
[LICENSE](LICENSE).

*ePiXeL* is a trademark of **HCT Bilişim**. The licence covers this integration's
source code only; it grants no rights to the ePiXeL name, logo, firmware,
management platform or hardware design.
