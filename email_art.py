"""Draws the picture at the top of the morning email: today's five papers as books on a desk.

Uses Pillow and the fonts in assets/fonts. If either is missing, the email simply goes without it.
"""

import io
import math
import random
from pathlib import Path

FONTS = Path(__file__).parent / "assets" / "fonts"
W, H = 1200, 540          # drawn at 2x, shown at 600 x 270 in the email
DESK_Y = 430              # where the books stand
SPINES = ["#5E1C17", "#1F3A2B", "#22305A", "#4A3020", "#3B1F33"]
ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"]


def rgb(hex_color):
    h = hex_color.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def mix(a, b, t):
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def font(name, size, weight=None):
    from PIL import ImageFont
    f = ImageFont.truetype(str(FONTS / name), size)
    if weight:
        f.set_variation_by_axes([weight])
    return f


def seal_points(cx, cy, r, n=140):
    pts = []
    for i in range(n):
        a = i / n * math.tau
        rr = r * (1 + (2.4 * math.sin(a * 9) + 1.3 * math.sin(a * 21 + 0.7)) / 45)
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    return pts


def glow(size, color, strength):
    """A soft round light, as an RGBA image."""
    from PIL import Image, ImageDraw, ImageFilter
    g = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(g).ellipse((size * 0.2, size * 0.2, size * 0.8, size * 0.8), fill=color + (strength,))
    return g.filter(ImageFilter.GaussianBlur(size * 0.16))


def spine_label(title):
    """Short name for a spine: the part before the colon, or the first few words."""
    name = title.split(":")[0].strip()
    words = name.split()
    while len(" ".join(words)) > 18 and len(words) > 1:
        words.pop()
    return " ".join(words)


def draw_book(img, x, w, h, color, numeral, label, f_num, f_label):
    from PIL import Image, ImageDraw
    base = rgb(color)
    spine = Image.new("RGBA", (w, h))
    d = ImageDraw.Draw(spine)
    for i in range(w):  # round the spine: dark edges, light middle
        t = i / (w - 1)
        shade = 0.55 + 0.6 * math.sin(t * math.pi) ** 0.8
        d.line([(i, 0), (i, h)], fill=tuple(min(255, round(c * shade)) for c in base) + (255,))
    gold = rgb("#D9BC7A")
    for y in (26, 36, h - 40, h - 30):  # raised bands with gold tooling
        d.rectangle((0, y - 3, w, y + 3), fill=mix(base, (0, 0, 0), 0.45) + (255,))
        d.line([(4, y - 7), (w - 4, y - 7)], fill=gold + (230,), width=2)
    d.text((w / 2, 64), numeral, font=f_num, fill=gold, anchor="mm")

    room = h - 150  # between the numeral and the lower bands
    words = Image.new("RGBA", (room, w), (0, 0, 0, 0))
    wd = ImageDraw.Draw(words)
    text, size = label.upper(), 22
    f = f_label(size)
    while wd.textlength(text, font=f) > room - 12 and size > 14:
        size -= 1
        f = f_label(size)
    wd.text((room / 2, w / 2 + 1), text, font=f, fill=gold + (255,), anchor="mm")
    spine.alpha_composite(words.rotate(90, expand=True), (0, 88))
    img.alpha_composite(spine, (x, DESK_Y - h))


def banner_png(papers, day_label, issue_line, seed=7):
    """Return the banner as PNG bytes, or None if Pillow or the fonts are not available."""
    try:
        from PIL import Image, ImageDraw, ImageFilter
        f_title = font("PlayfairDisplay-Italic.ttf", 74, 600)
        f_small = font("Cinzel.ttf", 22, 600)
        f_num = font("Cinzel.ttf", 22, 700)
        f_label = lambda size: font("Cinzel.ttf", size, 600)
        f_note = font("Spectral-Italic.ttf", 25)
        f_seal = font("PlayfairDisplay-Italic.ttf", 40, 700)
    except Exception:
        return None

    rnd = random.Random(seed)
    img = Image.new("RGBA", (W, H), rgb("#0B0907") + (255,))
    d = ImageDraw.Draw(img)

    for y in range(DESK_Y):  # wall: a little warmer towards the desk
        d.line([(0, y), (W, y)], fill=mix(rgb("#0B0907"), rgb("#1E150D"), (y / DESK_Y) ** 1.6) + (255,))
    over = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(over)
    for x in range(0, W, 150):  # faint wall panels
        od.line([(x, 0), (x, DESK_Y)], fill=(255, 220, 170, 9), width=2)
    img.alpha_composite(over)

    img.alpha_composite(glow(760, (255, 160, 70), 70), (W - 600, DESK_Y - 520))  # candle light on the wall

    for y in range(DESK_Y, H):  # the desk
        t = (y - DESK_Y) / (H - DESK_Y)
        d.line([(0, y), (W, y)], fill=mix(rgb("#6A4326"), rgb("#1E120A"), t ** 0.7) + (255,))
    over = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(over)
    for _ in range(30):  # wood grain
        y0, amp, ph, k = rnd.uniform(DESK_Y + 6, H), rnd.uniform(1, 3), rnd.uniform(0, 6), rnd.uniform(70, 170)
        pts = [(x, y0 + amp * math.sin(x / k + ph)) for x in range(0, W + 20, 20)]
        od.line(pts, fill=(0, 0, 0, rnd.randint(20, 45)), width=1)
    od.line([(0, DESK_Y), (W, DESK_Y)], fill=(255, 214, 170, 70), width=2)
    img.alpha_composite(over)

    # today's books, with their shadows
    x = 64
    for i, p in enumerate(papers[:5]):
        w, h = rnd.randint(68, 84), rnd.randint(300, 350)
        shadow = Image.new("RGBA", (w + 40, 40), (0, 0, 0, 0))
        ImageDraw.Draw(shadow).ellipse((0, 8, w + 40, 30), fill=(0, 0, 0, 150))
        img.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(6)), (x - 20, DESK_Y - 14))
        draw_book(img, x, w, h, SPINES[i % len(SPINES)], ROMAN[i], spine_label(p["title"]), f_num, f_label)
        x += w + 6

    # the candle on the right
    cx = W - 92
    d.rectangle((cx - 15, DESK_Y - 150, cx + 15, DESK_Y - 22), fill=rgb("#EFE6CF"))
    d.rectangle((cx - 15, DESK_Y - 150, cx - 8, DESK_Y - 22), fill=rgb("#D9CBAA"))
    d.ellipse((cx - 44, DESK_Y - 30, cx + 44, DESK_Y - 8), fill=rgb("#B8893A"))
    d.ellipse((cx - 30, DESK_Y - 30, cx + 30, DESK_Y - 18), fill=rgb("#E8C57A"))
    d.line([(cx, DESK_Y - 150), (cx, DESK_Y - 160)], fill=rgb("#2A1D14"), width=3)
    img.alpha_composite(glow(160, (255, 190, 100), 150), (cx - 80, DESK_Y - 260))
    flame = Image.new("RGBA", (40, 70), (0, 0, 0, 0))
    ImageDraw.Draw(flame).ellipse((10, 8, 30, 66), fill=(255, 236, 190, 255))
    img.alpha_composite(flame.filter(ImageFilter.GaussianBlur(2.5)), (cx - 20, DESK_Y - 222))

    # wax seal, title and date
    tx = 560 + (W - 140 - 560) / 2
    d.polygon(seal_points(tx, 92, 44), fill=rgb("#7A2620"))
    d.ellipse((tx - 35, 57, tx + 35, 127), fill=rgb("#62201B"))
    d.text((tx, 94), "SD", font=f_seal, fill=rgb("#C26A5C"), anchor="mm")
    d.text((tx, 196), "The Scholar’s Desk", font=f_title, fill=rgb("#E3C78A"), anchor="mm")
    d.line([(tx - 180, 258), (tx - 30, 258)], fill=rgb("#CFAE6B"), width=2)
    d.line([(tx + 30, 258), (tx + 180, 258)], fill=rgb("#CFAE6B"), width=2)
    d.regular_polygon((tx, 258, 7), 4, rotation=45, fill=rgb("#CFAE6B"))
    d.text((tx, 296), day_label.upper(), font=f_small, fill=rgb("#EDE3CC"), anchor="mm")
    d.text((tx, 338), issue_line, font=f_note, fill=rgb("#A3957E"), anchor="mm")

    over = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(over)
    for _ in range(60):  # a little gold dust in the air
        px, py, r = rnd.uniform(0, W), rnd.uniform(0, DESK_Y - 10), rnd.choice([1, 1, 1.5, 2])
        a = rnd.randint(50, 170)
        od.ellipse((px - r, py - r, px + r, py + r), fill=(244, 223, 166, a))
        if r == 2:
            od.line([(px - 7, py), (px + 7, py)], fill=(244, 223, 166, a // 2))
            od.line([(px, py - 7), (px, py + 7)], fill=(244, 223, 166, a // 2))
    img.alpha_composite(over)

    out = io.BytesIO()
    img.convert("RGB").save(out, "PNG", optimize=True)
    return out.getvalue()
