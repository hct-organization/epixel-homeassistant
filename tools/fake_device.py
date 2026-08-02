#!/usr/bin/env python3
"""A fake ePiXeL display -- exercises the integration WITHOUT any firmware.

It does everything the real device does: connects to the address you give it
(instead of finding it over mDNS), generates a PIN, pairs, long-polls /view and
renders the pages in your terminal.

Usage:
    python3 tools/fake_device.py 192.168.1.40
    python3 tools/fake_device.py 192.168.1.40 --port 8123
    python3 tools/fake_device.py 192.168.1.40 --reset          # forget saved token

Diagnosing a switch that does nothing on the real display:

    python3 tools/fake_device.py 192.168.1.40 --toggle a1b2c3
    python3 tools/fake_device.py 192.168.1.40 --dim a1b2c3 up

Those send the same request the display sends. If they work, the server side
is sound and the fault is in the display; if they fail, the reply says why.
The key comes from the box listing this tool prints.

Standard library only -- nothing to install.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
import urllib.error
import urllib.request

STATE_FILE = os.path.join(os.path.dirname(__file__), ".fake_device_token")


def call(base: str, path: str, token: str | None = None,
         body: dict | None = None, timeout: int = 30):
    url = f"{base}{path}"
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(url, data=data, method="POST" if data else "GET")
    request.add_header("Content-Type", "application/json")
    if token:
        request.add_header("X-EPX-Token", token)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, json.loads(response.read() or b"{}")
    except urllib.error.HTTPError as err:
        raw = err.read()
        try:
            return err.code, json.loads(raw or b"{}")
        except ValueError:
            return err.code, {"raw": raw.decode(errors="replace")[:200]}
    except Exception as err:  # noqa: BLE001
        return 0, {"e": str(err)}


def pair(base: str) -> str:
    pin = f"{random.randint(0, 9999):04d}"
    session = f"{random.getrandbits(32):08x}"
    print(f"\n  ┌───────────────┐\n  │  CODE:  {pin}  │\n  └───────────────┘")
    print("  Home Assistant > Settings > Devices & Services > Add Integration > ePiXeL")
    print("  Enter this code there. Waiting...\n")

    deadline = time.time() + 180
    while time.time() < deadline:
        status, body = call(base, "/pair", body={
            "pin": pin, "session": session, "name": "Fake ePiXeL"})
        if status == 0:
            print(f"  ! connection error: {body.get('e')}")
        elif status == 404:
            print("  ! /pair returned 404 -- integration not installed, or HA not restarted")
        elif body.get("status") == "paired":
            print(f"  OK paired. Home Assistant name: {body.get('hass_name')}")
            return body["token"]
        elif body.get("status") == "busy":
            print("  ! server already has 3 pending requests, retrying")
        time.sleep(2)

    sys.exit("  FAILED: no pairing within 3 minutes")


def draw(view: dict) -> None:
    pages = view.get("pages", [])
    print(f"\n--- rev={view.get('rev')} · {len(pages)} page(s) " + "-" * 30)
    if not pages:
        print("  (no pages -- the device REMOVES the HA page from the carousel)")
    for index, page in enumerate(pages, 1):
        boxes = page.get("b", [])
        layout = {2: "1x2", 3: "2x2", 4: "2x2", 5: "2x3", 6: "2x3"}.get(len(boxes), "1x1")
        print(f"\n  [{index}] {page.get('t') or '(untitled)'}   {len(boxes)} boxes · {layout}")
        for box in boxes:
            mark = "*" if box.get("y") == "sw" else ("o" if box.get("y") == "bin" else " ")
            value = box.get("v")
            if box.get("y") in ("sw", "bin"):
                value = "ON" if value else "OFF"
            unit = f" {box['u']}" if box.get("u") else ""
            graph = "  [chart]" if box.get("g") else ""
            print(f"      {mark} {box.get('n',''):<24} {value}{unit:<6} "
                  f"[{box.get('i')}] {box.get('k')}{graph}")


def parse_target(raw: str, fallback_port: int) -> tuple[str, int]:
    """Accept 192.168.1.20, 192.168.1.20:8123 or http://192.168.1.20:8123/."""
    raw = raw.strip()
    for scheme in ("http://", "https://"):
        if raw.startswith(scheme):
            raw = raw[len(scheme):]
    raw = raw.split("/", 1)[0]
    if ":" in raw:
        host, _, port = raw.partition(":")
        try:
            return host, int(port)
        except ValueError:
            return host, fallback_port
    return raw, fallback_port


def wait_for_integration(base: str) -> dict:
    """Poll /ping until the integration answers.

    404 does NOT mean 'not installed'. Home Assistant does not load a
    config-flow-only integration until the user starts its config flow, so
    before the very first pairing the endpoints genuinely do not exist yet.
    Exiting here would tell the user something false; we wait instead.
    """
    deadline = time.time() + 300
    told = False
    while time.time() < deadline:
        status, body = call(base, "/ping")
        if status == 200:
            return body
        if status == 0:
            print(f"  ! cannot reach {base} -- {body.get('e')}")
            print("    Check the address. Home Assistant usually listens on port 8123.")
        elif status == 404 and not told:
            told = True
            print("  ! the ePiXeL endpoints are not up yet.\n")
            print("    In Home Assistant, open:")
            print("      Settings > Devices & Services > Add Integration > ePiXeL")
            print("    and leave the code dialog open. Home Assistant only loads the")
            print("    integration once that flow starts.\n")
            print("    If ePiXeL is not in the list, install it through HACS first")
            print("    and restart Home Assistant.\n")
            print("    Waiting...")
        time.sleep(3)
    sys.exit("FAILED: the integration never answered within 5 minutes")


def run_command(base: str, token: str, args) -> None:
    """Send one command and report exactly what came back.

    This exists to split a fault in half. When a switch on the display does
    nothing, the cause is either the display's command path or the server's.
    Running the same command from here answers which, without guessing.
    """
    if args.toggle:
        key, body = args.toggle, {"k": args.toggle, "a": "toggle"}
    else:
        key, action = args.dim[0], args.dim[1]
        if action in ("up", "down"):
            body = {"k": key, "a": action}
        else:
            try:
                body = {"k": key, "a": "set", "p": int(action)}
            except ValueError:
                sys.exit(f"dim: '{action}' up, down ya da 0-100 olmali")

    print(f"\n-> POST /cmd {json.dumps(body, ensure_ascii=False)}")
    status, reply = call(base, "/cmd", token=token, body=body)
    print(f"<- HTTP {status}  {json.dumps(reply, ensure_ascii=False)}")

    if status == 200 and reply.get("ok"):
        print(f"\nSERVER SIDE IS SOUND. The entity reached level {reply.get('v')}.")
        print("If the display still does nothing, the fault is in the display's")
        print("command path -- check the HA_UI / HA_SVC / HA_NET lines in its log.")
    elif status == 401:
        print("\n401: this token is no longer valid. Pair again.")
    elif status == 200:
        print(f"\nSERVER REFUSED: {reply.get('e')}")
        print("  entity_not_found -> the key is not on any page any more")
        print("  not_switchable   -> that entity cannot be switched")
        print("  service_failed   -> Home Assistant refused the service call")
    else:
        print(f"\nUNEXPECTED: HTTP {status}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("host", help="192.168.1.20, 192.168.1.20:8123 or a full URL")
    parser.add_argument("--port", type=int, default=8123)
    parser.add_argument("--reset", action="store_true", help="forget the saved token")
    parser.add_argument(
        "--toggle", metavar="KEY",
        help="send one toggle for a box key and exit -- splits a fault in half: "
             "if this works the server side is sound and the fault is in the display")
    parser.add_argument(
        "--dim", nargs=2, metavar=("KEY", "up|down|0-100"),
        help="send one dim command and exit")
    args = parser.parse_args()

    host, port = parse_target(args.host, args.port)
    base = f"http://{host}:{port}/api/epixel"
    print(f"Home Assistant: http://{host}:{port}")

    body = wait_for_integration(base)
    print(f"OK integration found: protocol v{body.get('ver')} · HA {body.get('hass')}")

    if args.reset and os.path.exists(STATE_FILE):
        os.remove(STATE_FILE)

    token = ""
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as handle:
            token = handle.read().strip()

    if token:
        status, _ = call(base, "/view?wait=0", token=token)
        if status == 401:
            print("! saved token rejected -- pairing again")
            token = ""

    if not token:
        token = pair(base)
        with open(STATE_FILE, "w") as handle:
            handle.write(token)

    if args.toggle or args.dim:
        run_command(base, token, args)
        return

    print("\nLong polling. Toggle a light in Home Assistant -- it should land instantly.")
    print("Ctrl+C to quit.\n")

    revision = 0
    idle = 0
    while True:
        status, view = call(base, f"/view?rev={revision}&wait=25", token=token, timeout=35)
        if status == 401:
            sys.exit("FAILED: token rejected")
        if status != 200:
            print(f"  ! /view {status}: {view}")
            time.sleep(5)
            continue
        new_revision = view.get("rev", revision)
        if new_revision == revision and revision != 0:
            # Long poll timed out with nothing new. Say so on one line rather
            # than redrawing the same page every 25 seconds.
            idle += 1
            print(f"  · no change ({idle})", flush=True)
            continue
        revision = new_revision
        idle = 0
        draw(view)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nstopped")
