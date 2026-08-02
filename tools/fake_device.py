#!/usr/bin/env python3
"""A fake ePiXeL display -- exercises the integration WITHOUT any firmware.

It does everything the real device does: connects to the address you give it
(instead of finding it over mDNS), generates a PIN, pairs, long-polls /view and
renders the pages in your terminal.

Usage:
    python3 tools/fake_device.py 192.168.1.40
    python3 tools/fake_device.py 192.168.1.40 --port 8123
    python3 tools/fake_device.py 192.168.1.40 --reset      # forget saved token

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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("host")
    parser.add_argument("--port", type=int, default=8123)
    parser.add_argument("--reset", action="store_true", help="forget the saved token")
    args = parser.parse_args()

    base = f"http://{args.host}:{args.port}/api/epixel"

    status, body = call(base, "/ping")
    if status != 200:
        sys.exit(
            f"FAILED: /ping returned {status} -- is the integration installed "
            f"and was Home Assistant restarted?\n  {body}"
        )
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

    print("\nLong polling. Toggle a light in Home Assistant -- it should land instantly.")
    print("Ctrl+C to quit.\n")

    revision = 0
    while True:
        status, view = call(base, f"/view?rev={revision}&wait=25", token=token, timeout=35)
        if status == 401:
            sys.exit("FAILED: token rejected")
        if status != 200:
            print(f"  ! /view {status}: {view}")
            time.sleep(5)
            continue
        revision = view.get("rev", revision)
        draw(view)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nstopped")
