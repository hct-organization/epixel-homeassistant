#!/usr/bin/env python3
"""Exercises the page model, the icon picker and the preview WITHOUT Home Assistant.

The parts that decide what a display shows -- name handling, layout, icon
choice, brightness conversion -- are plain functions over entity state. They do
not need a running Home Assistant to be checked, and waiting for one is how
regressions reach a device.

Only the type annotations reference Home Assistant, and they are never
evaluated, so two stub modules are enough to import the real code.

    python3 tools/selftest.py

Exits non-zero on the first failure so it can gate a build.
"""

from __future__ import annotations

import pathlib
import sys
import types

ROOT = pathlib.Path(__file__).resolve().parent.parent
COMPONENT = ROOT / "custom_components" / "epixel"

# Stand in for the package itself rather than running its __init__, which wires
# up Home Assistant. The modules under test only need the package to exist so
# their relative imports resolve.
_pkg = types.ModuleType("epixel")
_pkg.__path__ = [str(COMPONENT)]
sys.modules["epixel"] = _pkg

# Home Assistant appears only in type annotations, which are never evaluated.
for name in ("homeassistant", "homeassistant.config_entries", "homeassistant.core"):
    sys.modules.setdefault(name, types.ModuleType(name))
sys.modules["homeassistant.config_entries"].ConfigEntry = object
sys.modules["homeassistant.core"].HomeAssistant = object

from epixel import icons, preview  # noqa: E402
from epixel.const import CONF_ICONS, CONF_PAGES, DOMAIN  # noqa: E402
from epixel.icon_paths import ICON_PATHS  # noqa: E402
from epixel.model import build_view, clean_text, key_of, tracked_entities  # noqa: E402

FAILED: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  {'pass' if ok else 'FAIL'}  {label}{'' if ok else '  -> ' + detail}")
    if not ok:
        FAILED.append(label)


# --------------------------------------------------------------- fakes


class FakeState:
    def __init__(self, entity_id: str, state: str, **attrs):
        self.entity_id = entity_id
        self.state = state
        self.attributes = attrs


class FakeHass:
    def __init__(self, states):
        self.states = types.SimpleNamespace(get=lambda eid: states.get(eid))
        self.data = {DOMAIN: {"rev": 7}}
        self.config = types.SimpleNamespace(language="tr", location_name="Evim")


class FakeEntry:
    def __init__(self, pages):
        self.options = {CONF_PAGES: pages}
        self.data = {"device_name": "ePiXeL"}


STATES = {
    "light.strip_a": FakeState(
        "light.strip_a", "on",
        friendly_name="VitrinLedleri LED Şerit 1",
        supported_color_modes=["brightness"], brightness=128),
    "light.strip_b": FakeState(
        "light.strip_b", "off",
        friendly_name="VitrinLedleri LED Şerit 2",
        supported_color_modes=["brightness"]),
    "light.plain": FakeState(
        "light.plain", "on", friendly_name="Hol Lamba",
        supported_color_modes=["onoff"]),
    "switch.socket": FakeState(
        "switch.socket", "off", friendly_name="Ofis Priz", device_class="outlet"),
    "sensor.temp": FakeState(
        "sensor.temp", "22.4", friendly_name="Salon\tSıcaklık\n",
        device_class="temperature", unit_of_measurement="°C",
        state_class="measurement"),
    "sensor.text": FakeState(
        "sensor.text", "kapalı", friendly_name="Mod"),
    "binary_sensor.door": FakeState(
        "binary_sensor.door", "on", friendly_name="Giriş Kapısı", device_class="door"),
    "sensor.gone": None,
    "sensor.unavail": FakeState("sensor.unavail", "unavailable", friendly_name="Bozuk"),
}
STATES = {k: v for k, v in STATES.items() if v is not None}


# --------------------------------------------------------------- tests


def test_icon_set() -> None:
    print("\nikon seti")
    check("34 ikon tanimli", len(ICON_PATHS) == 34, str(len(ICON_PATHS)))
    check("VALID ile ICON_PATHS ayni", icons.VALID == frozenset(ICON_PATHS))
    check("her ikonun yol verisi var", all(d for _, d in ICON_PATHS.values()))
    check("her ikonun ust kaynak adi var", all(m for m, _ in ICON_PATHS.values()))
    from epixel.icon_paths import svg
    check("bilinmeyen ad dot'a duser", svg("yokboyle") == svg("dot"))
    check("svg tek path uretir", svg("temp").count("<path") == 1)
    check("gecersiz secim reddedilir", icons.normalise("yokboyle") is None)
    check("auto secimi None doner", icons.normalise("auto") is None)
    check("gecerli secim korunur", icons.normalise("fire") == "fire")


def test_names() -> None:
    print("\nad temizligi")
    check("sekme ve satir sonu bosluga doner",
          clean_text("Salon\tSıcaklık\n") == "Salon Sıcaklık")
    check("art arda bosluk teke iner", clean_text("a   b") == "a b")
    check("uclar kirpilir", clean_text("  x  ") == "x")
    check("kontrol karakteri silinir", "\x07" not in clean_text("zil\x07sesi"))
    check("None bos dize olur", clean_text(None) == "")
    check("turkce harfler korunur", clean_text("Işık Ğüçü") == "Işık Ğüçü")


def test_layout_and_types() -> None:
    print("\nsayfa modeli")
    pages = [{"title": "Salon", "entities": list(STATES)}]
    view = build_view(FakeHass(STATES), FakeEntry(pages))
    check("rev tasiniyor", view["rev"] == 7)
    boxes = view["pages"][0]["b"]
    check("sayfa basina 6 kutu tavani", len(boxes) == 6, str(len(boxes)))

    by_key = {b["k"]: b for b in boxes}
    strip_a = by_key[key_of("light.strip_a")]
    strip_b = by_key[key_of("light.strip_b")]
    plain = by_key[key_of("light.plain")]
    socket = by_key[key_of("switch.socket")]
    temp = by_key[key_of("sensor.temp")]

    check("kisilabilir isik dim tipinde", strip_a["y"] == "dim", strip_a["y"])
    check("parlaklik 128/255 -> 50", strip_a["v"] == 50, str(strip_a["v"]))
    check("kapali kisilabilir isik 0", strip_b["v"] == 0, str(strip_b["v"]))
    check("kisilamayan isik sw tipinde", plain["y"] == "sw", plain["y"])
    check("kisilabilir isik dimmer ikonu", strip_a["i"] == "dimmer", strip_a["i"])
    check("kisilamayan isik bulb ikonu", plain["i"] == "bulb", plain["i"])
    check("outlet prize esler", socket["i"] == "plug", socket["i"])
    check("sicaklik num tipinde", temp["y"] == "num", temp["y"])
    check("birim tasiniyor", temp.get("u") == "°C", str(temp.get("u")))
    check("measurement grafik acar", temp.get("g") == 1)
    check("adlarda kontrol karakteri yok",
          all(all(ord(c) >= 32 for c in b["n"]) for b in boxes))
    check("kesme sonrasi adlar ayirt edilebilir",
          strip_a["n"] != strip_b["n"], f'{strip_a["n"]!r} / {strip_b["n"]!r}')
    check("hicbir ad 22 karakteri gecmiyor",
          all(len(b["n"]) <= 22 for b in boxes))
    check("entity_id tel uzerinde YOK",
          not any("light.strip_a" in str(v) for b in boxes for v in b.values()))


def test_edge_cases() -> None:
    print("\nkenar durumlar")
    hass = FakeHass(STATES)

    view = build_view(hass, FakeEntry([]))
    check("sayfa yoksa bos liste", view["pages"] == [])

    view = build_view(hass, FakeEntry([{"title": "Bos", "entities": []}]))
    check("bos sayfa atlanir", view["pages"] == [])

    view = build_view(hass, FakeEntry([{"title": "X", "entities": ["sensor.yok_boyle"]}]))
    box = view["pages"][0]["b"][0]
    check("silinmis varlik kutusu kalir", box["y"] == "txt" and box["v"] == "—")

    view = build_view(hass, FakeEntry([{"title": "X", "entities": ["sensor.unavail"]}]))
    check("erisilemez varlik — gosterir", view["pages"][0]["b"][0]["v"] == "—")

    pages = [{"title": "Y", "entities": ["sensor.temp"], CONF_ICONS: {"sensor.temp": "fire"}}]
    view = build_view(hass, FakeEntry(pages))
    check("kullanici ikonu otomatigi ezer", view["pages"][0]["b"][0]["i"] == "fire")

    pages = [{"title": "Y", "entities": ["sensor.temp"], CONF_ICONS: {"sensor.temp": "yok"}}]
    view = build_view(hass, FakeEntry(pages))
    check("gecersiz ikon otomatige duser", view["pages"][0]["b"][0]["i"] == "temp")

    many = [{"title": f"S{i}", "entities": ["sensor.temp"]} for i in range(12)]
    view = build_view(hass, FakeEntry(many))
    check("8 sayfa tavani", len(view["pages"]) == 8, str(len(view["pages"])))

    dup = [{"title": "D", "entities": ["sensor.temp", "sensor.temp"]}]
    check("tekrarli varlik tek kez izlenir",
          len(tracked_entities(FakeEntry(dup))) == 1)


def test_preview() -> None:
    print("\nonizleme")
    pages = [{"title": "Salon", "entities": list(STATES)[:4]}]
    view = build_view(FakeHass(STATES), FakeEntry(pages))
    html = preview.render(view, "tr", "Evim")

    check("tam belge", html.lstrip().startswith("<!doctype html>"))
    check("html kapali", html.rstrip().endswith("</html>"))
    check("gercek ekran genisligi", "width:320px" in html)
    check("gercek ekran yuksekligi", "height:480px" in html)
    check("4 kutu 2x2 cizer", "repeat(2,1fr)" in html)
    check("ikon svg gomulu", html.count("<svg") >= 4)
    check("turkce metin secildi", "Ekran önizlemesi" in html)
    check("kisma cubugu var", "bar-l" in html)

    en = preview.render(view, "en-GB", "Home")
    check("ingilizce metin secildi", "Screen preview" in en)

    empty = preview.render({"rev": 1, "pages": []}, "tr", "Evim")
    check("sayfasiz onizleme cokmez", "Henüz sayfa yok" in empty)

    # A friendly name containing markup must not become markup.
    nasty = {"rev": 1, "pages": [{"t": "<script>x</script>", "b": [
        {"k": "aaa", "n": '<img src=x onerror=1>', "y": "sw", "v": 1, "i": "dot"}]}]}
    out = preview.render(nasty, "tr", "Evim")
    check("baslik kacislanir", "<script>" not in out)
    check("kutu adi kacislanir", "<img src=x" not in out)


def main() -> int:
    print("ePiXeL entegrasyon oz-testi")
    test_icon_set()
    test_names()
    test_layout_and_types()
    test_edge_cases()
    test_preview()

    print()
    if FAILED:
        print(f"BASARISIZ: {len(FAILED)} kontrol")
        for name in FAILED:
            print(f"  - {name}")
        return 1
    print("hepsi gecti")
    return 0


if __name__ == "__main__":
    sys.exit(main())
