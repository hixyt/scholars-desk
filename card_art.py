"""SVG pictures with the desk's own fonts built in, so they look the same everywhere,
even inside a GitHub README where outside fonts can't load.

build_site.py uses today_card() to write assets/today.svg every morning: a small card with the
latest papers that my GitHub profile shows, so the profile changes by itself each day.
"""

import base64
import html
import io
import logging
from copy import deepcopy
from functools import lru_cache
from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

FONTS = Path(__file__).resolve().parent / "assets" / "fonts"
logging.getLogger("fontTools").setLevel(logging.ERROR)  # it talks a lot while cutting fonts down
SPINES = ["#5E1C17", "#1F3A2B", "#22305A", "#4A3020", "#3B1F33", "#1E3B3F", "#5A4A1C", "#2D2A4A"]


@lru_cache(maxsize=None)
def _font(name, weight=None):
    f = TTFont(FONTS / name)
    if "fvar" in f:
        f = instancer.instantiateVariableFont(f, {"wght": weight or 400})
    return f


def text_width(name, size, text, weight=None):
    """Width of the text in pixels, without kerning (the SVG turns kerning off to match)."""
    f = _font(name, weight)
    cmap, hmtx, upm = f.getBestCmap(), f["hmtx"], f["head"].unitsPerEm
    return sum(hmtx[cmap.get(ord(c), cmap.get(32))][0] for c in text) * size / upm


def font_face(family, name, text, weight=None):
    """An @font-face rule with only the letters this picture needs, as a small WOFF inside the SVG."""
    f = deepcopy(_font(name, weight))
    options = subset.Options()
    options.flavor = "woff"
    options.layout_features = ["kern", "liga"]
    options.name_IDs = []
    sub = subset.Subsetter(options)
    sub.populate(text="".join(sorted(set(text + " "))))
    sub.subset(f)
    out = io.BytesIO()
    f.flavor = "woff"
    f.save(out)
    data = base64.b64encode(out.getvalue()).decode()
    return f"@font-face{{font-family:'{family}';src:url(data:font/woff;base64,{data}) format('woff')}}"


def esc(text):
    return html.escape(str(text or ""), quote=True)


def fit(text, name, size, max_width, weight=None):
    """Shorten the text with an ellipsis until it fits."""
    if text_width(name, size, text, weight) <= max_width:
        return text
    while text and text_width(name, size, text + "…", weight) > max_width:
        text = text[:-1].rstrip()
    return text + "…"


def today_card(date_label, books, proven, checked, site_url):
    """The latest day's papers as books on a shelf, with the proof count. books: [(short title, topic label)]."""
    W, H = 900, 300
    books = books[:6]
    kicker = f"FROM THE DESK · {date_label.upper()}"
    n = len(books)
    title = {1: "One new AI paper", 2: "Two new AI papers", 3: "Three new AI papers", 4: "Four new AI papers",
             5: "Five new AI papers", 6: "Six new AI papers"}.get(n, f"{n} new AI papers")
    stat = f"{proven}/{checked}"

    spine_w, gap, x0, shelf_y = 62, 10, 44, 252
    parts, labels = [], ""
    for i, (name, topic) in enumerate(books):
        h = 196 + (i * 37) % 28
        x = x0 + i * (spine_w + gap)
        y = shelf_y - h
        label = fit(name.upper(), "Cinzel.ttf", 12, h - 46, 700)
        labels += label + topic.upper()
        cx = x + spine_w / 2
        parts.append(
            f'<g class="bk" style="animation-delay:{0.15 + i * 0.12:.2f}s">'
            f'<rect x="{x}" y="{y}" width="{spine_w}" height="{h}" rx="3" fill="{SPINES[i % len(SPINES)]}"/>'
            f'<rect x="{x}" y="{y}" width="{spine_w}" height="{h}" rx="3" fill="url(#sheen)"/>'
            f'<rect x="{x + 6}" y="{y + 14}" width="{spine_w - 12}" height="2" fill="#CFAE6B" opacity=".8"/>'
            f'<rect x="{x + 6}" y="{y + h - 16}" width="{spine_w - 12}" height="2" fill="#CFAE6B" opacity=".8"/>'
            f'<text x="{cx}" y="{y + h / 2}" transform="rotate(-90 {cx} {y + h / 2})" class="sp" text-anchor="middle" dominant-baseline="central">{esc(label)}</text>'
            f'</g>')

    words = kicker + title + stat + "LINES PROVEN" + labels
    fonts = (font_face("SDDisplay", "PlayfairDisplay-Italic.ttf", title + stat, 600)
             + font_face("SDCaps", "Cinzel.ttf", words.upper() + "·", 700)
             + font_face("SDBody", "Spectral-Italic.ttf", "against each paper’s own abstract. Read them at hixyt.github.io/scholars-desk"))
    tx = 520
    dust = "".join(
        f'<circle class="dust" cx="{x}" cy="{y}" r="{r}" style="animation-delay:{d}s;animation-duration:{t}s"/>'
        for x, y, r, d, t in [(470, 230, 1.6, 0, 7), (640, 250, 1.2, 1.5, 9), (780, 210, 1.8, 3, 8), (860, 260, 1.1, 4.5, 10),
                              (560, 190, 1.3, 2.2, 8.5), (720, 120, 1.0, 5.1, 9.5), (300, 60, 1.2, 3.6, 8), (150, 40, 1.0, 6, 9)])
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="{esc(title)} on The Scholar's Desk, {esc(date_label)}. {proven} of {checked} lines proven.">
<style>
{fonts}
.k{{font:700 12px SDCaps,Georgia,serif;letter-spacing:2.5px;fill:#CFAE6B}}
.t{{font:600 38px SDDisplay,Georgia,serif;font-style:italic;fill:#EDE3CC}}
.s{{font:600 64px SDDisplay,Georgia,serif;font-style:italic;fill:#EBD29B}}
.b{{font:400 17px SDBody,Georgia,serif;font-style:italic;fill:#A3957E}}
.l{{font:700 12px SDCaps,Georgia,serif;letter-spacing:2.5px;fill:#CFAE6B}}
.sp{{font:700 12px SDCaps,Georgia,serif;letter-spacing:1.2px;fill:#EBD29B}}
.bk{{opacity:0;animation:rise .7s cubic-bezier(.2,.8,.2,1) forwards}}
@keyframes rise{{from{{opacity:0;transform:translateY(-26px)}}to{{opacity:1;transform:none}}}}
.dust{{fill:#F4DFA6;opacity:0;animation:float linear infinite}}
@keyframes float{{0%{{opacity:0;transform:translateY(0)}}20%{{opacity:.8}}100%{{opacity:0;transform:translateY(-120px)}}}}
.seal{{transform-origin:842px 172px;animation:stamp .6s 1.1s cubic-bezier(.3,1.5,.5,1) both}}
@keyframes stamp{{0%{{opacity:0;transform:scale(2) rotate(-25deg)}}100%{{opacity:1;transform:scale(1) rotate(-8deg)}}}}
@media (prefers-reduced-motion:reduce){{.bk,.seal{{animation:none;opacity:1}}.dust{{display:none}}}}
</style>
<defs>
<radialGradient id="bg" cx=".3" cy="0" r="1.1"><stop offset="0" stop-color="#22180F"/><stop offset=".7" stop-color="#0B0907"/></radialGradient>
<linearGradient id="sheen" x1="0" x2="1"><stop offset="0" stop-color="#000" stop-opacity=".35"/><stop offset=".3" stop-color="#fff" stop-opacity=".08"/><stop offset="1" stop-color="#000" stop-opacity=".4"/></linearGradient>
<linearGradient id="wood" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#6A4326"/><stop offset="1" stop-color="#2A190D"/></linearGradient>
</defs>
<rect width="{W}" height="{H}" rx="14" fill="url(#bg)"/>
<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="14" fill="none" stroke="#CFAE6B" stroke-opacity=".25"/>
{dust}
{"".join(parts)}
<rect x="28" y="{shelf_y}" width="{x0 + n * (spine_w + gap) + 6}" height="12" rx="2" fill="url(#wood)"/>
<text x="{tx}" y="64" class="k">{esc(kicker)}</text>
<text x="{tx}" y="112" class="t">{esc(title)}</text>
<text x="{tx}" y="196" class="s">{esc(stat)}</text>
<text x="{tx + text_width("PlayfairDisplay-Italic.ttf", 64, stat, 600) + 14}" y="174" class="l">LINES</text>
<text x="{tx + text_width("PlayfairDisplay-Italic.ttf", 64, stat, 600) + 14}" y="194" class="l">PROVEN</text>
<text x="{tx}" y="226" class="b">against each paper’s own abstract.</text>
<text x="{tx}" y="266" class="b" style="fill:#CFAE6B">Read them at hixyt.github.io/scholars-desk</text>
<g class="seal"><polygon points="{seal_points(842, 172, 30)}" fill="#7A2620"/><circle cx="842" cy="172" r="23" fill="#62201B"/>
<text x="842" y="180" text-anchor="middle" class="s" style="font-size:22px;fill:#EBD29B">SD</text></g>
</svg>
'''


def seal_points(cx, cy, r, n=72):
    import math
    pts = []
    for i in range(n):
        a = i / n * math.pi * 2
        rr = r * (1 + (2.4 * math.sin(a * 9) + 1.3 * math.sin(a * 21 + 0.7)) / 45)
        pts.append(f"{cx + rr * math.cos(a):.1f},{cy + rr * math.sin(a):.1f}")
    return " ".join(pts)
