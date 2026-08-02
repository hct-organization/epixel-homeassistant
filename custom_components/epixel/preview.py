"""Renders the pages as they will appear on the display.

WHY THIS EXISTS: laying out a page in a form and then walking to the device to
see whether it reads well is a slow loop, and the person building the page
often is not standing next to the screen. This draws the same pages at the
display's real resolution in a browser.

It is a mirror, not a second implementation: the boxes come from the same
`build_view` the device consumes, so a layout that looks right here is the
layout the device receives. The only thing reproduced separately is the paint.
"""

from __future__ import annotations

from html import escape

from .const import SCREEN_H, SCREEN_W
from .icon_paths import svg

# Box count decides the grid. Same rule as the firmware; stated once here and
# once in PROTOCOL.md, nowhere else.
_GRID = {1: (1, 1), 2: (1, 2), 3: (2, 2), 4: (2, 2), 5: (2, 3), 6: (2, 3)}

_TEXT = {
    "tr": {
        "title": "Ekran önizlemesi",
        "lead": "Sayfalar cihazın gerçek çözünürlüğünde çiziliyor. Bu sayfa {n} saniyede bir kendini yeniler.",
        "empty": "Henüz sayfa yok. Yapılandır ekranından sayfa ekleyin.",
        "on": "AÇIK",
        "off": "KAPALI",
        "layout": "kutu",
        "chart": "grafik",
        "gone": "veri yok",
        "note": "Yazı tipi ve renkler cihazdakine yakındır, birebir aynı değildir. Yerleşim, kutu sayısı ve içerik birebir aynıdır.",
    },
    "en": {
        "title": "Screen preview",
        "lead": "Pages are drawn at the display's real resolution. This page refreshes every {n} seconds.",
        "empty": "No pages yet. Add one from the Configure screen.",
        "on": "ON",
        "off": "OFF",
        "layout": "boxes",
        "chart": "chart",
        "gone": "no data",
        "note": "Type and colour are close to the device, not identical. Layout, box count and content are identical.",
    },
}

REFRESH_S = 15


def render(view: dict, language: str, device_name: str) -> str:
    lang = "tr" if str(language or "").lower().startswith("tr") else "en"
    t = _TEXT[lang]
    pages = view.get("pages", [])

    screens = "".join(_screen(page, index, len(pages), t) for index, page in enumerate(pages, 1))
    if not pages:
        screens = f'<p class="empty">{escape(t["empty"])}</p>'

    return f"""<!doctype html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="{REFRESH_S}">
<title>{escape(t["title"])} — {escape(device_name)}</title>
<style>
  *,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
  :root{{
    --page:#f2f4f7; --ink:#131a23; --muted:#5b6672; --line:#c9d2dc;
    --scr:#0d1622; --scr-2:#16202e; --scr-line:#243141;
    --scr-ink:#e8edf3; --scr-muted:#7d8b9b;
    --accent:#2f6fed; --on:#3fbf7f; --off:#5a6675; --warn:#e0a33c;
  }}
  @media (prefers-color-scheme:dark){{
    :root{{ --page:#0a0f16; --ink:#e7ecf2; --muted:#93a0ae; --line:#26313f }}
  }}
  body{{
    background:var(--page); color:var(--ink); padding:32px 24px 56px;
    font:15px/1.6 ui-sans-serif,-apple-system,"Segoe UI",Roboto,sans-serif;
    -webkit-font-smoothing:antialiased;
  }}
  .wrap{{max-width:1180px;margin:0 auto}}
  h1{{font-size:1.3rem;letter-spacing:-.02em;margin-bottom:6px}}
  .lead,.note{{color:var(--muted);font-size:.9rem;max-width:66ch}}
  .note{{margin-top:28px;font-size:.82rem}}
  .empty{{color:var(--muted);margin-top:24px}}
  .rack{{display:flex;flex-wrap:wrap;gap:32px;margin-top:28px}}
  .unit{{display:flex;flex-direction:column;gap:9px}}
  .cap{{
    font:600 .7rem/1.4 ui-monospace,Menlo,monospace;letter-spacing:.12em;
    text-transform:uppercase;color:var(--muted);
  }}

  /* --- the screen itself --- */
  .scr{{
    width:{SCREEN_W}px;height:{SCREEN_H}px;flex:0 0 auto;
    background:var(--scr);color:var(--scr-ink);
    border:1px solid var(--scr-line);border-radius:6px;overflow:hidden;
    display:flex;flex-direction:column;
    box-shadow:0 10px 26px rgba(0,0,0,.22);
  }}
  .bar{{
    height:34px;flex:0 0 auto;display:flex;align-items:center;gap:8px;
    padding:0 12px;border-bottom:1px solid var(--scr-line);background:var(--scr-2);
  }}
  .bar .ttl{{font-size:13px;font-weight:600;letter-spacing:-.01em;
    white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
  .bar .pos{{margin-left:auto;font:600 10px/1 ui-monospace,Menlo,monospace;
    letter-spacing:.1em;color:var(--scr-muted)}}
  .foot{{
    height:26px;flex:0 0 auto;display:flex;align-items:center;justify-content:center;
    gap:22px;border-top:1px solid var(--scr-line);color:var(--scr-muted);
  }}
  .foot span{{width:12px;height:2px;background:currentColor;opacity:.5;border-radius:1px}}

  .grid{{flex:1 1 auto;display:grid;gap:1px;background:var(--scr-line);padding:1px}}
  .box{{
    background:var(--scr);padding:10px 11px;
    display:flex;flex-direction:column;gap:4px;min-width:0;overflow:hidden;
  }}
  .box.act{{background:linear-gradient(180deg,var(--scr-2),var(--scr))}}
  .box .top{{display:flex;align-items:center;gap:7px;color:var(--scr-muted)}}
  .box .top svg{{flex:0 0 auto}}
  .box.on .top{{color:var(--accent)}}
  .box .nm{{
    font-size:11px;line-height:1.25;color:var(--scr-muted);
    display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;
  }}
  .box .val{{margin-top:auto;font-size:20px;font-weight:650;letter-spacing:-.02em;
    font-variant-numeric:tabular-nums;white-space:nowrap}}
  .box .val .u{{font-size:12px;font-weight:500;color:var(--scr-muted);margin-left:3px}}
  .box .st{{margin-top:auto;display:flex;align-items:center;gap:6px;
    font:600 12px/1 ui-sans-serif,sans-serif;letter-spacing:.04em}}
  .dotm{{width:8px;height:8px;border-radius:50%;flex:0 0 auto}}
  .on .dotm{{background:var(--on);box-shadow:0 0 0 3px rgba(63,191,127,.18)}}
  .off .dotm{{background:var(--off)}}
  .on .st{{color:var(--on)}} .off .st{{color:var(--scr-muted)}}
  .bar-l{{height:4px;border-radius:2px;background:var(--scr-line);margin-top:5px;overflow:hidden}}
  .bar-l i{{display:block;height:100%;background:var(--accent)}}
  .chip{{
    align-self:flex-start;font:600 8px/1 ui-monospace,Menlo,monospace;
    letter-spacing:.12em;text-transform:uppercase;color:var(--warn);
    border:1px solid currentColor;border-radius:2px;padding:2px 4px;
  }}
  .txtv{{margin-top:auto;font-size:13px;color:var(--scr-ink);
    display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}}
</style>
</head>
<body>
<div class="wrap">
  <h1>{escape(t["title"])} — {escape(device_name)}</h1>
  <p class="lead">{escape(t["lead"].format(n=REFRESH_S))}</p>
  <div class="rack">{screens}</div>
  <p class="note">{escape(t["note"])}</p>
</div>
</body>
</html>
"""


def _screen(page: dict, index: int, total: int, t: dict) -> str:
    boxes = page.get("b", [])
    cols, rows = _GRID.get(len(boxes), (2, 3))
    cells = "".join(_cell(box, t) for box in boxes)
    # Unused cells keep the grid honest: six-box geometry with five boxes
    # leaves a gap on the device too, and the preview must show that.
    cells += '<div class="box"></div>' * max(0, cols * rows - len(boxes))

    return f"""
    <div class="unit">
      <div class="scr">
        <div class="bar">
          <div class="ttl">{escape(page.get("t") or "")}</div>
          <div class="pos">{index}/{total}</div>
        </div>
        <div class="grid" style="grid-template-columns:repeat({cols},1fr);grid-template-rows:repeat({rows},1fr)">{cells}</div>
        <div class="foot"><span></span><span></span><span></span><span></span><span></span></div>
      </div>
      <div class="cap">{len(boxes)} {escape(t["layout"])} · {cols}&times;{rows}</div>
    </div>"""


def _cell(box: dict, t: dict) -> str:
    kind = box.get("y")
    icon = svg(box.get("i", "dot"), 18)
    name = escape(str(box.get("n", "")))
    chart = f'<div class="chip">{escape(t["chart"])}</div>' if box.get("g") else ""

    if kind in ("sw", "bin"):
        lit = bool(box.get("v"))
        cls = "box act on" if lit else "box act off"
        if kind == "bin":
            cls = "box on" if lit else "box off"
        label = t["on"] if lit else t["off"]
        body = f'<div class="st"><i class="dotm"></i>{escape(label)}</div>'

    elif kind == "dim":
        level = int(box.get("v") or 0)
        lit = level > 0
        cls = "box act on" if lit else "box act off"
        shown = f"{level}%" if lit else t["off"]
        body = (
            f'<div class="st"><i class="dotm"></i>{escape(shown)}</div>'
            f'<div class="bar-l"><i style="width:{level}%"></i></div>'
        )

    elif kind == "num":
        cls = "box"
        unit = box.get("u")
        suffix = f'<span class="u">{escape(str(unit))}</span>' if unit else ""
        body = f'<div class="val">{escape(str(box.get("v", "")))}{suffix}</div>'

    else:  # txt, and anything a future firmware does not yet understand
        cls = "box"
        value = str(box.get("v", ""))
        body = f'<div class="txtv">{escape(value if value != "—" else t["gone"])}</div>'

    return (
        f'<div class="{cls}"><div class="top">{icon}</div>'
        f'<div class="nm">{name}</div>{body}{chart}</div>'
    )
