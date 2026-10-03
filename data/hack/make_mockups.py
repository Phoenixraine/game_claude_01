#!/usr/bin/env python3
"""Draws the three screens of the hack mini-game (path, rhythm, frequency) from REAL generated layouts (data/hack/hack_levels.json) as
SVG + PNG. One list of primitives feeds both back ends, so the PNG preview is exactly what the SVG says.

    python3 data/hack/make_mockups.py            # writes data/hack/mockups/*.svg and *.png
"""
import json
import math
import os
import sys

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "mockups")
W, H = 1920, 1080
P = json.load(open(os.path.join(HERE, "palette.json")))["colors"]
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_B = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


class Canvas:
    """Primitive list -> SVG text and PIL image."""

    def __init__(self):
        self.ops = []

    def rect(self, x, y, w, h, fill=None, stroke=None, sw=2, r=0, op=1.0):
        self.ops.append(("rect", x, y, w, h, fill, stroke, sw, r, op))

    def line(self, x0, y0, x1, y1, color, sw=2, op=1.0):
        self.ops.append(("line", x0, y0, x1, y1, color, sw, op))

    def poly(self, pts, fill=None, stroke=None, sw=2, op=1.0, closed=True):
        self.ops.append(("poly", list(pts), fill, stroke, sw, op, closed))

    def circle(self, cx, cy, r, fill=None, stroke=None, sw=2, op=1.0):
        self.ops.append(("circle", cx, cy, r, fill, stroke, sw, op))

    def arc(self, cx, cy, r, a0, a1, color, sw=6, op=1.0):
        self.ops.append(("arc", cx, cy, r, a0, a1, color, sw, op))

    def text(self, x, y, s, size=28, color="#ffffff", bold=False, anchor="start", op=1.0):
        self.ops.append(("text", x, y, s, size, color, bold, anchor, op))

    # -------------------------------------------------------------- SVG
    def svg(self):
        o = ['<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d" font-family="DejaVu Sans, sans-serif">' % (W, H, W, H)]
        for op in self.ops:
            k = op[0]
            if k == "rect":
                _, x, y, w, h, fill, stroke, sw, r, a = op
                o.append('<rect x="%g" y="%g" width="%g" height="%g" rx="%g" fill="%s" stroke="%s" stroke-width="%g" opacity="%g"/>' % (x, y, w, h, r, fill or "none", stroke or "none", sw, a))
            elif k == "line":
                _, x0, y0, x1, y1, c, sw, a = op
                o.append('<line x1="%g" y1="%g" x2="%g" y2="%g" stroke="%s" stroke-width="%g" opacity="%g" stroke-linecap="round"/>' % (x0, y0, x1, y1, c, sw, a))
            elif k == "poly":
                _, pts, fill, stroke, sw, a, closed = op
                tag = "polygon" if closed else "polyline"
                o.append('<%s points="%s" fill="%s" stroke="%s" stroke-width="%g" opacity="%g" stroke-linejoin="round"/>' % (tag, " ".join("%g,%g" % p for p in pts), fill or "none", stroke or "none", sw, a))
            elif k == "circle":
                _, cx, cy, r, fill, stroke, sw, a = op
                o.append('<circle cx="%g" cy="%g" r="%g" fill="%s" stroke="%s" stroke-width="%g" opacity="%g"/>' % (cx, cy, r, fill or "none", stroke or "none", sw, a))
            elif k == "arc":
                _, cx, cy, r, a0, a1, c, sw, a = op
                x0, y0 = cx + r * math.cos(math.radians(a0)), cy - r * math.sin(math.radians(a0))
                x1, y1 = cx + r * math.cos(math.radians(a1)), cy - r * math.sin(math.radians(a1))
                large = 1 if (a1 - a0) % 360 > 180 else 0
                o.append('<path d="M %g %g A %g %g 0 %d 0 %g %g" fill="none" stroke="%s" stroke-width="%g" opacity="%g" stroke-linecap="round"/>' % (x0, y0, r, r, large, x1, y1, c, sw, a))
            elif k == "text":
                _, x, y, s, size, c, bold, anchor, a = op
                o.append('<text x="%g" y="%g" font-size="%g" fill="%s" font-weight="%s" text-anchor="%s" opacity="%g">%s</text>' % (x, y, size, c, "bold" if bold else "normal", anchor, a, s))
        o.append("</svg>")
        return "\n".join(o)

    # -------------------------------------------------------------- PNG
    def png(self, path, scale=0.5):
        S = 2   # supersample
        img = Image.new("RGBA", (W * S, H * S), (0, 0, 0, 255))
        d = ImageDraw.Draw(img, "RGBA")

        def col(c, a=1.0):
            c = c.lstrip("#")
            return (int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16), int(255 * a))

        for op in self.ops:
            k = op[0]
            if k == "rect":
                _, x, y, w, h, fill, stroke, sw, r, a = op
                box = [x * S, y * S, (x + w) * S, (y + h) * S]
                if r:
                    d.rounded_rectangle(box, r * S, fill=col(fill, a) if fill else None, outline=col(stroke, a) if stroke else None, width=int(sw * S))
                else:
                    d.rectangle(box, fill=col(fill, a) if fill else None, outline=col(stroke, a) if stroke else None, width=int(sw * S))
            elif k == "line":
                _, x0, y0, x1, y1, c, sw, a = op
                d.line([x0 * S, y0 * S, x1 * S, y1 * S], fill=col(c, a), width=int(sw * S))
            elif k == "poly":
                _, pts, fill, stroke, sw, a, closed = op
                pp = [(x * S, y * S) for x, y in pts]
                if fill:
                    d.polygon(pp, fill=col(fill, a))
                if stroke:
                    d.line(pp + ([pp[0]] if closed else []), fill=col(stroke, a), width=int(sw * S), joint="curve")
            elif k == "circle":
                _, cx, cy, r, fill, stroke, sw, a = op
                d.ellipse([(cx - r) * S, (cy - r) * S, (cx + r) * S, (cy + r) * S], fill=col(fill, a) if fill else None, outline=col(stroke, a) if stroke else None, width=int(sw * S))
            elif k == "arc":
                _, cx, cy, r, a0, a1, c, sw, a = op
                d.arc([(cx - r) * S, (cy - r) * S, (cx + r) * S, (cy + r) * S], start=-a1, end=-a0, fill=col(c, a), width=int(sw * S))
            elif k == "text":
                _, x, y, s, size, c, bold, anchor, a = op
                f = ImageFont.truetype(FONT_B if bold else FONT, int(size * S))
                w = d.textlength(s, font=f)
                xx = x * S - (w / 2 if anchor == "middle" else w if anchor == "end" else 0)
                d.text((xx, y * S), s, font=f, fill=col(c, a), anchor="ls")
        img = img.convert("RGB").resize((int(W * scale), int(H * scale)), Image.LANCZOS)
        img.save(path, optimize=True)


def frame(c, title, stage_names, stage_i, heat, time_frac, alarm, hints):
    """Common chrome: glass background, timer, ICE heat, stage chain, hints bar, PiP slot for the enemy camera."""
    c.rect(0, 0, W, H, fill=P["glassDark"])
    for i in range(0, H, 6):                       # faint scan lines
        c.line(0, i, W, i, P["glassMid"], 1, 0.35)
    c.rect(40, 40, W - 80, H - 80, stroke=P["lineDim"], sw=2, r=18, op=0.8)
    for sx in (40, W - 40):                          # corner brackets
        for sy in (40, H - 40):
            dx, dy = (1 if sx == 40 else -1), (1 if sy == 40 else -1)
            c.poly([(sx, sy + 70 * dy), (sx, sy), (sx + 70 * dx, sy)], stroke=P["line"], sw=4, closed=False)
    # timer (top left): a thin bar split in seconds
    c.text(80, 118, "ВРЕМЯ", 26, P["lineDim"], True)
    c.rect(80, 134, 760, 22, stroke=P["lineDim"], sw=2, r=4)
    tc = P["timerLow"] if time_frac < 0.25 else P["timerFull"]
    c.rect(84, 138, 752 * time_frac, 14, fill=tc, r=3)
    for i in range(1, 25):
        c.line(80 + 760 * i / 25, 134, 80 + 760 * i / 25, 156, P["glassDark"], 2)
    # ICE heat (top right of the timer)
    c.text(920, 118, "ЛЁД", 26, P["lineDim"], True)
    c.rect(920, 134, 420, 22, stroke=P["lineDim"], sw=2, r=4)
    c.rect(924, 138, 412 * heat, 14, fill=P["warn"] if heat < 0.7 else P["threat"], r=3)
    c.line(920 + 420 * 0.7, 126, 920 + 420 * 0.7, 164, P["threat"], 3)        # the alarm level
    if alarm:
        c.text(1400, 152, "ТРЕВОГА", 30, P["threat"], True)
    # stage chain (left column)
    for i, name in enumerate(stage_names):
        y = 250 + i * 130
        done, cur = i < stage_i, i == stage_i
        c.circle(120, y, 34, fill=P["line"] if done else None, stroke=P["line"] if (done or cur) else P["lineFaint"], sw=4 if cur else 2)
        c.text(120, y + 10, str(i + 1), 30, P["glassDark"] if done else (P["ok"] if cur else P["lineDim"]), True, "middle")
        c.text(176, y + 10, name, 30, P["ok"] if cur else P["lineDim"], cur)
        if i + 1 < len(stage_names):
            c.line(120, y + 36, 120, y + 94, P["line"] if done else P["lineFaint"], 3)
    # slot for the enemy-hand camera (017): top right, a frame without a picture here
    c.rect(1480, 80, 360, 203, stroke=P["lineDim"], sw=2, op=0.7)
    c.text(1660, 188, "камера врага", 24, P["lineFaint"], False, "middle")
    # hints
    c.rect(300, H - 150, W - 600, 70, stroke=P["lineFaint"], sw=2, r=10, op=0.9)
    x = 330
    for keys, label in hints:
        for k in keys:
            c.rect(x, H - 138, 56, 46, stroke=P["line"], sw=2, r=8)
            c.text(x + 28, H - 105, k, 26, P["ok"], True, "middle")
            x += 66
        c.text(x + 6, H - 105, label, 26, P["lineDim"])
        x += 40 + 15 * len(label)


def hexagon(cx, cy, r):
    return [(cx + r * math.cos(math.radians(60 * i + 30)), cy + r * math.sin(math.radians(60 * i + 30))) for i in range(6)]


def path_screen(layout, taken_idx):
    c = Canvas()
    frame(c, "", ["ПУТЬ", "РИТМ", "ЧАСТОТА"], 0, 0.30, 0.62, False, [(["←", "↑", "↓", "→"], "шаг"), (["Z"], "назад"), (["Esc"], "выход")])
    w, h = layout["w"], layout["h"]
    cell = 112
    ox, oy = (W - w * cell) / 2 + 100, 300
    pos = lambda x, y: (ox + x * cell + cell / 2, oy + y * cell + cell / 2)
    keys = [tuple(k) for k in layout["keys"]]
    sol = layout["solution"]
    # reconstruct the route by replaying the solution through the same rules (blockers never entered; ice slides)
    x, y = layout["entry"]
    cells = layout["cells"]
    route = [(x, y)]
    for ch in sol:
        dx, dy = {"L": (-1, 0), "R": (1, 0), "U": (0, -1), "D": (0, 1)}[ch]
        x, y = x + dx, y + dy
        route.append((x, y))
        while cells[y][x] == "2" and 0 <= x + dx < w and 0 <= y + dy < h and cells[y + dy][x + dx] != "1":
            x, y = x + dx, y + dy
            route.append((x, y))
    # node links
    for yy in range(h):
        for xx in range(w):
            for ddx, ddy in ((1, 0), (0, 1)):
                if xx + ddx < w and yy + ddy < h:
                    a, b = pos(xx, yy), pos(xx + ddx, yy + ddy)
                    c.line(a[0], a[1], b[0], b[1], P["lineFaint"], 3)
    taken = route[: taken_idx + 1]
    for i in range(len(taken) - 1):
        a, b = pos(*taken[i]), pos(*taken[i + 1])
        c.line(a[0], a[1], b[0], b[1], P["line"], 9)
    for yy in range(h):
        for xx in range(w):
            cx, cy = pos(xx, yy)
            t = cells[yy][xx]
            if t == "1":
                c.poly(hexagon(cx, cy, 44), fill=P["blocker"], stroke=P["lineDim"], sw=3)
                c.line(cx - 22, cy - 22, cx + 22, cy + 22, P["lineDim"], 4)
                c.line(cx - 22, cy + 22, cx + 22, cy - 22, P["lineDim"], 4)
            elif t == "2":
                c.poly([(cx, cy - 46), (cx + 46, cy), (cx, cy + 46), (cx - 46, cy)], fill=None, stroke=P["ice"], sw=4)
                c.line(cx - 20, cy, cx + 20, cy, P["ice"], 3)
                c.line(cx, cy - 20, cx, cy + 20, P["ice"], 3)
            else:
                c.circle(cx, cy, 14, fill=P["glassMid"], stroke=P["lineDim"], sw=3)
    for i, k in enumerate(keys):
        cx, cy = pos(*k)
        got = k in taken
        c.circle(cx, cy, 40, fill=P["key"] if got else None, stroke=P["key"], sw=5)
        c.text(cx, cy + 14, str(i + 1), 40, P["glassDark"] if got else P["key"], True, "middle")
    ex, ey = pos(*layout["entry"])
    c.poly([(ex - 100, ey - 26), (ex - 56, ey), (ex - 100, ey + 26)], fill=P["line"])
    kx, ky = pos(*layout["core"])
    c.circle(kx, ky, 62, stroke=P["ok"], sw=5)
    c.circle(kx, ky, 38, stroke=P["ok"], sw=3)
    c.circle(kx, ky, 12, fill=P["ok"])
    hx, hy = pos(*taken[-1])
    c.circle(hx, hy, 24, fill=P["ok"])
    c.circle(hx, hy, 36, stroke=P["ok"], sw=3, op=0.6)
    c.text(300, 250, "ПУТЬ К ЯДРУ  ·  КЛЮЧИ ПО ПОРЯДКУ  ·  ЛЁД СКОЛЬЗИТ", 30, P["lineDim"])
    return c


def rhythm_screen(layout):
    c = Canvas()
    frame(c, "", ["ПУТЬ", "РИТМ", "ЧАСТОТА"], 1, 0.62, 0.48, True, [(["←", "↓", "↑", "→"], "дорожки"), (["␣"], "5-я дорожка"), (["Esc"], "выход")])
    lanes = layout["lanes"]
    lw = 190
    x0 = W / 2 + 100 - lanes * lw / 2
    top, hit, bottom = 330, 760, 850
    glyph = {0: "←", 1: "↓", 2: "↑", 3: "→", 4: "␣"}
    for i in range(lanes):
        x = x0 + i * lw
        c.rect(x + 8, top, lw - 16, bottom - top, stroke=P["lineFaint"], sw=2, r=6, op=0.9)
        c.text(x + lw / 2, top - 16, glyph[i], 44, P["line"], True, "middle")
    c.rect(x0, hit - 22, lanes * lw, 44, stroke=P["line"], sw=4, r=8)
    c.rect(x0 + 3, hit - 19, lanes * lw - 6, 38, fill="#12354a", r=6)
    imps = layout["impulses"]
    now = 232
    shown = 0
    for t, lane in imps:
        dt = t - now
        if dt < -40 or dt > 90:
            continue
        x = x0 + lane * lw + lw / 2
        y = hit - dt * (hit - top) / 90.0
        y = min(y, hit + 50)
        if dt < 0:      # already past the line: the first one hit, the next one missed
            hit_ok = shown == 0
            col = P["ok"] if hit_ok else P["threat"]
            c.poly([(x, y - 34), (x + 34, y), (x, y + 34), (x - 34, y)], stroke=col, sw=5, op=0.55)
            if hit_ok:
                c.circle(x, hit, 54, stroke=P["ok"], sw=4, op=0.7)
            else:
                c.line(x - 28, y - 28, x + 28, y + 28, P["threat"], 6)
                c.line(x - 28, y + 28, x + 28, y - 28, P["threat"], 6)
            shown += 1
        else:
            c.poly([(x, y - 34), (x + 34, y), (x, y + 34), (x - 34, y)], fill=P["line"] if dt > 6 else P["ok"], op=0.95)
            c.text(x, y + 14, glyph[lane], 36, P["glassDark"], True, "middle")
    c.text(300, 250, "ЖМИ ДОРОЖКУ, КОГДА ИМПУЛЬС НА ЛИНИИ", 30, P["lineDim"])
    return c


def freq_screen(layout):
    c = Canvas()
    frame(c, "", ["ПУТЬ", "РИТМ", "ЧАСТОТА"], 2, 0.40, 0.35, False, [(["␣"], "захват"), (["A"], "(геймпад)"), (["Esc"], "выход")])
    cx, cy, R = W / 2 + 100, 540, 250
    c.circle(cx, cy, R + 40, stroke=P["lineFaint"], sw=2)
    c.circle(cx, cy, R, stroke=P["lineDim"], sw=3)
    c.circle(cx, cy, R - 70, stroke=P["lineFaint"], sw=2)
    for i in range(72):
        a = math.radians(i * 5)
        L = 22 if i % 6 == 0 else 10
        c.line(cx + (R + 40) * math.cos(a), cy - (R + 40) * math.sin(a), cx + (R + 40 - L) * math.cos(a), cy - (R + 40 - L) * math.sin(a), P["lineDim"], 2)
    locks = layout["locks"]
    k = 2
    hw = layout["halfDeg"][k]
    centre = 38.0
    c.arc(cx, cy, R, centre - hw, centre + hw, P["threat"], 26)
    c.arc(cx, cy, R, centre - hw, centre + hw, P["ok"], 4)
    # the previous (wider) windows as ghosts
    for j in range(k):
        c.arc(cx, cy, R + 28 + 10 * j, centre - layout["halfDeg"][j], centre + layout["halfDeg"][j], P["threat"], 4, 0.4)
    ang = centre - 11.0
    nx, ny = cx + (R + 24) * math.cos(math.radians(ang)), cy - (R + 24) * math.sin(math.radians(ang))
    c.line(cx, cy, nx, ny, P["line"], 6)
    c.poly([(nx, ny), (cx + (R - 36) * math.cos(math.radians(ang + 2.4)), cy - (R - 36) * math.sin(math.radians(ang + 2.4))),
            (cx + (R - 36) * math.cos(math.radians(ang - 2.4)), cy - (R - 36) * math.sin(math.radians(ang - 2.4)))], fill=P["ok"])
    c.circle(cx, cy, 22, fill=P["line"])
    for i in range(locks):                     # lock pips
        px = cx - (locks - 1) * 34 + i * 68
        c.circle(px, cy + R + 80, 18, fill=P["ok"] if i < k else None, stroke=P["ok"], sw=3)
    c.text(300, 250, "СОВМЕСТИ СЕКТОР С ОКНОМ ЛЬДА  ·  ОКНО СУЖАЕТСЯ", 30, P["lineDim"])
    return c


def main():
    os.makedirs(OUT, exist_ok=True)
    data = json.load(open(os.path.join(HERE, "hack_levels.json")))
    sess = [s for s in data["sessions"] if s["level"] == 6][0]
    st = {s["kind"]: s for s in sess["stages"]}
    shots = {"hack_01_path": path_screen(st["path"], 9), "hack_02_rhythm": rhythm_screen(st["rhythm"]), "hack_03_frequency": freq_screen(st["frequency"])}
    for name, c in shots.items():
        open(os.path.join(OUT, name + ".svg"), "w", encoding="utf-8").write(c.svg())
        c.png(os.path.join(OUT, name + ".png"))
        print("wrote", name)


if __name__ == "__main__":
    sys.exit(main())
