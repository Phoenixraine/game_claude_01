"""Previews of the cyberpunk layer (TASK-019): plan, mega sign map with visibility rays, light heat map, a bird's-eye oblique view of the street with the signs,
palette histogram. Software rasteriser only (no PIL)."""
import math
import os

from . import tokyo_render as TR
from .cyber_data import NEON_NAMES, PALETTE
from .png import write_png
from .raster import Canvas
from .render import ASPHALT, _lerp
from .terrain import X0, X1

BG = (10, 12, 22)


def _P(y_top=1200.0):
    return lambda x, y: (x - X0, y_top - y)


def render_plan(doc, terrain):
    plaza = doc["arena"]["plaza"]
    signs = doc["mega_signs"]

    def overlay(cv, P):
        pts = [P(*p) for p in plaza["polygon"]]
        cv.polygon(pts, (255, 255, 255), 0.25)
        cv.outline(pts, (255, 255, 255), 3)
        st = doc["arena"].get("street")
        if st:
            road = next(r for r in doc["roads"] if r["id"] == st["road_id"])
            p2 = [P(*p) for p in road["points"]]
            for i in range(len(p2) - 1):
                cv.thick_line(p2[i], p2[i + 1], 6.0, (255, 120, 200))
        for s in signs:
            x, y = P(s["pos"][0], s["pos"][1])
            col = tuple(s["palette"][0])
            r = 5 if s["monster"] else 3
            cv.disc(x, y, r, col)
            cv.outline([(x - r - 1, y - r - 1), (x + r + 1, y - r - 1), (x + r + 1, y + r + 1), (x - r - 1, y + r + 1)], (0, 0, 0), 1)

    title = "%s ARENA  SEED %d  GLASS TOWERS + NEON  (SEA AT THE BOTTOM)" % (doc["arena"]["name"].upper().replace("_", " "), doc["seed"])
    return TR.render_topdown(doc, terrain, title=title, overlay=overlay,
                             legend_extra=[("GLASS TOWER", TR.TYPE_COLORS["glass_tower"]), ("SHOPFRONT ROW", TR.TYPE_COLORS["shopfront_row"]), ("BATTLE PLAZA 180 M", (255, 255, 255)),
                                           ("PEDESTRIAN STREET 12 M", (255, 120, 200)), ("MEGA SIGN (BIG = 40 M+)", (60, 230, 255))])


def render_signs(doc, terrain):
    W, H = 1600, 1200
    cv = Canvas(W, H, BG)
    P = _P()
    for b in doc["blocks"]:
        cv.polygon([P(*p) for p in b["polygon"]], (22, 24, 36))
    for r in doc["roads"]:
        pts = [P(*p) for p in r["points"]]
        for i in range(len(pts) - 1):
            cv.thick_line(pts[i], pts[i + 1], r["width"] / 2.0, (34, 36, 50))
    for b in doc["buildings"]:
        if b["type"] == "hero" and b["hero_kind"] in ("expressway", "suspension_bridge"):
            continue
        t = min(1.0, b["height"] / 300.0)
        cv.polygon([P(*p) for p in b["footprint"]], _lerp((46, 50, 70), (110, 120, 160), t))
        cv.outline([P(*p) for p in b["footprint"]], (20, 22, 32), 1)
    pc = doc["arena"]["plaza"]["center"]
    cx, cy = P(*pc)
    pp = [P(*p) for p in doc["arena"]["plaza"]["polygon"]]
    cv.outline(pp, (255, 255, 255), 2)
    for s in doc["mega_signs"]:
        x, y = P(s["pos"][0], s["pos"][1])
        cv.line((cx, cy), (x, y), (30, 90, 50), 1)
    for s in doc["mega_signs"]:
        x, y = P(s["pos"][0], s["pos"][1])
        n = s["normal"]
        L = 14.0 + s["size_m"][0] * 0.5
        col = tuple(s["palette"][0])
        w = 5 if s["monster"] else 3
        cv.line((x, y), (x + n[0] * L, y - n[1] * L), col, w)
        cv.disc(x, y, 3 if s["monster"] else 2, (255, 255, 255))
    cv.disc(cx, cy, 6, (255, 230, 40))
    mon = sum(1 for s in doc["mega_signs"] if s["monster"])
    cv.rect(12, 12, 640, 150, (6, 8, 14))
    cv.text(20, 20, "MEGA SIGN MAP  (%s)" % doc["arena"]["name"].upper().replace("_", " "), (255, 255, 255), 2)
    cv.text(20, 48, "%d SIGNS  %d MONSTERS (40 M+)  ALL FACE THE PLAZA" % (len(doc["mega_signs"]), mon), (230, 230, 240), 2)
    cv.text(20, 76, "BAR = FACADE NORMAL  COLOUR = PALETTE  WHITE BOX = BATTLE PLAZA", (200, 200, 215), 2)
    cv.text(20, 104, "GREEN RAY = CLEAR 2D LINE OF SIGHT AT 40 M FROM THE PLAZA CENTRE", (110, 220, 140), 2)
    cv.text(20, 126, "STYLES: BANNER / BILLBOARD / TUBE / HOLO / SPHERE", (200, 200, 215), 1)
    return cv


def render_lights(doc, terrain):
    W, H = 1600, 1200
    cv = Canvas(W, H, BG)
    P = _P()
    cell = 8
    gw, gh = W // cell + 1, H // cell + 1
    grid = [[0.0] * gw for _ in range(gh)]
    for L in doc["lights"]:
        x, y = P(L["pos"][0], L["pos"][1])
        gx, gy = int(x // cell), int(y // cell)
        wgt = 1.0 if L["priority"] <= 2 else 0.5
        for dj in range(-3, 4):
            for di in range(-3, 4):
                a, b = gx + di, gy + dj
                if 0 <= a < gw and 0 <= b < gh:
                    grid[b][a] += wgt * math.exp(-(di * di + dj * dj) / 3.5)
    mx = max(max(r) for r in grid)
    for b in doc["blocks"]:
        cv.polygon([P(*p) for p in b["polygon"]], (16, 18, 28))
    for j in range(gh):
        for i in range(gw):
            v = grid[j][i] / mx
            if v < 0.015:
                continue
            v = min(1.0, v ** 0.6)
            col = _lerp((40, 10, 80), (255, 120, 40), v) if v < 0.7 else _lerp((255, 120, 40), (255, 255, 230), (v - 0.7) / 0.3)
            cv.rect(i * cell, j * cell, i * cell + cell - 1, j * cell + cell - 1, col)
    for L in doc["lights"]:
        x, y = P(L["pos"][0], L["pos"][1])
        cv.px(int(x), int(y), tuple(L["color"]))
    for b in doc["buildings"]:
        if b["type"] == "hero" and b["hero_kind"] in ("expressway", "suspension_bridge"):
            continue
        cv.outline([P(*p) for p in b["footprint"]], (70, 74, 100), 1)
    pp = [P(*p) for p in doc["arena"]["plaza"]["polygon"]]
    cv.outline(pp, (255, 255, 255), 2)
    rep = doc["light_report"]
    cv.rect(12, 12, 700, 150, (6, 8, 14))
    cv.text(20, 20, "LIGHT HEAT MAP  %d LIGHTS (SHADOWS OFF BY DEFAULT)" % rep["total"], (255, 255, 255), 2)
    cv.text(20, 48, "BY KIND: " + "  ".join("%s %d" % (k.upper(), v) for k, v in sorted(rep["by_kind"].items(), key=lambda kv: -kv[1])[:4]), (230, 230, 240), 1)
    cv.text(20, 62, "         " + "  ".join("%s %d" % (k.upper(), v) for k, v in sorted(rep["by_kind"].items(), key=lambda kv: -kv[1])[4:]), (230, 230, 240), 1)
    cv.text(20, 84, "BRIGHT = MANY LIGHTS   DOT COLOUR = LIGHT COLOUR   WHITE BOX = BATTLE PLAZA", (200, 200, 215), 1)
    cv.text(20, 100, "PRIORITY 1 (ALWAYS ON) .. 5 (CULLED FIRST): " + " ".join("P%s=%d" % (k, v) for k, v in sorted(rep["by_priority"].items())), (200, 200, 215), 1)
    return cv


def render_birdseye(doc, terrain):
    """Oblique view from the south over the street and the plaza: extruded buildings, mega signs as glowing quads on the facades."""
    W, H = 1600, 900
    cv = Canvas(W, H, (14, 14, 28))
    plaza = doc["arena"]["plaza"]
    st = doc["arena"].get("street")
    cx = plaza["center"][0]
    cy = (plaza["center"][1] - 330.0) if st else plaza["center"][1] - 200.0
    s = 1.5
    ky, kz = 0.52, 0.92

    def proj(x, y, z):
        return (W / 2.0 + (x - cx) * s, H * 0.90 - (y - cy) * s * ky - z * s * kz)

    # fog gradient and ground
    for yy in range(H):
        cv.hline(0, W - 1, yy, _lerp((24, 18, 44), (70, 40, 90), yy / H))
    reach = 420.0
    def vis(x, y):
        return abs(x - cx) < 520 and -110 < y - cy < 480
    for r in doc["roads"]:
        pts = r["points"]
        for i in range(len(pts) - 1):
            a, b = pts[i], pts[i + 1]
            if not (vis(*a) or vis(*b)):
                continue
            dx, dy = b[0] - a[0], b[1] - a[1]
            ln = math.hypot(dx, dy)
            nx, ny = -dy / ln * r["width"] / 2.0, dx / ln * r["width"] / 2.0
            quad = [proj(a[0] + nx, a[1] + ny, 0), proj(b[0] + nx, b[1] + ny, 0), proj(b[0] - nx, b[1] - ny, 0), proj(a[0] - nx, a[1] - ny, 0)]
            cv.polygon(quad, (46, 48, 66) if r["kind"] != "pedestrian" else (80, 56, 92))
    pq = [proj(p[0], p[1], 0) for p in plaza["polygon"]]
    cv.polygon(pq, (70, 70, 96))
    cv.outline(pq, (255, 255, 255), 2)
    # buildings, far to near
    bs = [b for b in doc["buildings"] if not (b["type"] == "hero" and b["hero_kind"] in ("expressway", "suspension_bridge", "scramble_crossing"))]
    bs = [b for b in bs if vis(*(sum(p[0] for p in b["footprint"]) / len(b["footprint"]), sum(p[1] for p in b["footprint"]) / len(b["footprint"])))]
    bs.sort(key=lambda b: -sum(p[1] for p in b["footprint"]) / len(b["footprint"]))
    palette_of = {s_["host"]: s_ for s_ in doc["mega_signs"]}
    base_col = {"glass_tower": (70, 150, 190), "shopfront_row": (160, 90, 130), "office_tower": (90, 100, 140), "apartment_tower": (130, 110, 100), "low_shop": (120, 110, 90),
                "parking": (90, 90, 100)}
    for b in bs:
        fp = b["footprint"]
        z0, h = b["base_z"], b["height"]
        col = base_col.get(b["building_type"], (100, 100, 120))
        n = len(fp)
        c = (sum(p[0] for p in fp) / n, sum(p[1] for p in fp) / n)
        for i in range(n):
            a, e = fp[i], fp[(i + 1) % n]
            mx_, my_ = (a[0] + e[0]) / 2.0 - c[0], (a[1] + e[1]) / 2.0 - c[1]
            nl = math.hypot(mx_, my_)
            if my_ / max(1e-6, nl) > 0.15:       # facing away from the viewer in the south
                continue
            shade = 0.55 + 0.35 * (-my_ / max(1e-6, nl)) + 0.1 * (mx_ / max(1e-6, nl))
            sc = tuple(int(v * max(0.35, min(1.0, shade))) for v in col)
            quad = [proj(a[0], a[1], z0), proj(e[0], e[1], z0), proj(e[0], e[1], z0 + h), proj(a[0], a[1], z0 + h)]
            cv.polygon(quad, sc)
            # window bands
            if b["building_type"] in ("glass_tower", "office_tower"):
                for k in range(1, int(h // 12)):
                    zz = z0 + k * 12.0
                    cv.line(proj(a[0], a[1], zz), proj(e[0], e[1], zz), tuple(min(255, v + 30) for v in sc), 1)
        top = [proj(p[0], p[1], z0 + h) for p in fp]
        cv.polygon(top, tuple(min(255, int(v * 0.9) + 25) for v in col))
        cv.outline(top, (12, 12, 20), 1)
    # mega signs
    for sg in doc["mega_signs"]:
        if not vis(sg["pos"][0], sg["pos"][1]):
            continue
        w, h = sg["size_m"]
        x, y, z = sg["pos"]
        nx, ny = sg["normal"]
        tx, ty = -ny, nx
        col = tuple(sg["palette"][0])
        quad = [proj(x - tx * w / 2, y - ty * w / 2, z - h / 2), proj(x + tx * w / 2, y + ty * w / 2, z - h / 2), proj(x + tx * w / 2, y + ty * w / 2, z + h / 2), proj(x - tx * w / 2, y - ty * w / 2, z + h / 2)]
        if ny > 0.3:
            continue                                    # seen from behind
        cv.polygon(quad, col, 0.5)
        cv.polygon([proj(x - tx * w * 0.4, y - ty * w * 0.4, z - h * 0.4), proj(x + tx * w * 0.4, y + ty * w * 0.4, z - h * 0.4), proj(x + tx * w * 0.4, y + ty * w * 0.4, z + h * 0.4),
                    proj(x - tx * w * 0.4, y - ty * w * 0.4, z + h * 0.4)], tuple(min(255, int(v * 1.05)) for v in col), 0.9)
        cv.outline(quad, (255, 255, 255), 1)
    for L in doc["lights"]:
        if L["kind"] in ("neon_tube", "neon_sign", "beacon") and vis(L["pos"][0], L["pos"][1]):
            x, y = proj(*L["pos"])
            if 0 <= x < W and 0 <= y < H:
                cv.blend(int(x), int(y), tuple(L["color"]), 0.9)
                cv.blend(int(x) + 1, int(y), tuple(L["color"]), 0.5)
                cv.blend(int(x), int(y) + 1, tuple(L["color"]), 0.5)
    cv.rect(12, 12, 760, 78, (6, 8, 14))
    cv.text(20, 18, "BIRD EYE VIEW FROM THE SEA SIDE  %s" % doc["arena"]["name"].upper().replace("_", " "), (255, 255, 255), 2)
    cv.text(20, 46, "GLASS TOWERS (12 SILHOUETTES) FRAME THE PLAZA  SHOP ROWS ALONG THE STREET  NEON SIGNS GLOW", (200, 200, 220), 1)
    cv.text(20, 62, "OBLIQUE PROJECTION, NO LIGHTING MODEL - A LAYOUT CHECK, NOT A RENDER", (150, 150, 170), 1)
    return cv


def render_palette(doc):
    W, H = 1600, 900
    cv = Canvas(W, H, BG)
    rep = doc["light_report"]
    cv.text(30, 24, "NEON PALETTE POLICY  CYAN / MAGENTA / AMBER / RED + WARM TUNGSTEN", (255, 255, 255), 2)
    cv.text(30, 54, "EVERY BLOCK USES 3 (SOMETIMES 4) NEON HUES, AT MOST 5 HUES WITH THE TUNGSTEN LAMPS", (190, 190, 210), 1)
    names = list(PALETTE)
    mx = max(rep["hue_share"].values())
    cv.text(30, 100, "SHARE OF ALL %d LIGHTS BY HUE" % rep["total"], (230, 230, 240), 2)
    for k, nme in enumerate(names):
        v = rep["hue_share"].get(nme, 0.0)
        y = 140 + k * 50
        cv.text(30, y + 8, nme.upper(), (230, 230, 240), 2)
        cv.rect(190, y, 190 + int(560 * v / mx), y + 34, PALETTE[nme])
        cv.text(200 + int(560 * v / mx), y + 8, "%.1f%%" % (100 * v), (255, 255, 255), 2)
    cv.text(30, 420, "LIGHTS BY KIND", (230, 230, 240), 2)
    kinds = sorted(rep["by_kind"].items(), key=lambda kv: -kv[1])
    kmx = kinds[0][1]
    for k, (nme, v) in enumerate(kinds):
        y = 460 + k * 38
        cv.text(30, y + 8, nme.upper(), (200, 200, 215), 1)
        cv.rect(190, y, 190 + int(560 * v / kmx), y + 26, (110, 130, 200))
        cv.text(200 + int(560 * v / kmx), y + 8, "%d" % v, (255, 255, 255), 1)
    cv.text(840, 100, "DOMINANT NEON HUES PER BLOCK (AT LEAST 10 PCT OF ITS NEON)", (230, 230, 240), 2)
    dom = rep["dominant_neon_hues_per_block"]
    ids = sorted(dom)
    cols = 4
    for k, bid in enumerate(ids):
        x = 840 + (k % cols) * 185
        y = 140 + (k // cols) * 34
        cv.text(x, y + 6, bid.replace("block_", "B"), (190, 190, 210), 1)
        for m, hn in enumerate(dom[bid]):
            cv.rect(x + 42 + m * 26, y, x + 42 + m * 26 + 22, y + 22, PALETTE[hn])
    cv.text(840, H - 40, "MAX %d NEON HUES IN ONE BLOCK + TUNGSTEN = %d" % (max(len(v) for v in dom.values()), rep["max_dominant_hues_in_a_block"]), (255, 230, 120), 2)
    return cv


def render_all(doc, terrain, out_dir):
    for name, fn in (("plan.png", lambda: render_plan(doc, terrain)), ("signs_map.png", lambda: render_signs(doc, terrain)), ("light_map.png", lambda: render_lights(doc, terrain)),
                     ("birdseye.png", lambda: render_birdseye(doc, terrain)), ("palette.png", lambda: render_palette(doc))):
        cv = fn()
        write_png(os.path.join(out_dir, name), cv.w, cv.h, cv.buf)
