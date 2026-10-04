"""Light points (>= 1500), palette policy report and the fog brightness maps of the cyberpunk layer (TASK-019).

Palette policy: neon is cyan / magenta / amber / red, lamps and windows are warm tungsten; every block uses 3 (sometimes 4) of the four neon hues, so a block
never shows more than five hues. Lights default to `shadow: false`; `priority` 1 (always on) ... 5 (first to be culled)."""
import math

from .cyber_data import NEON_NAMES, PALETTE
from .cyber_signs import block_palette
from .geom import bbox, point_in_poly
from .png import encode_png, encode_png_gray
from .raster import Canvas

FLICKER = {"flicker": 0.6, "pulse": 0.3, "cycle": 0.2, "scroll": 0.1}


def _r(v, n=1):
    return round(v, n)


def hue_of(color):
    return min(PALETTE, key=lambda k: sum((PALETTE[k][i] - color[i]) ** 2 for i in range(3)))


class Lights:
    def __init__(self, layout):
        self.out = []
        self.blocks = [(bbox([tuple(p) for p in b["polygon"]]), [tuple(p) for p in b["polygon"]], b["id"]) for b in layout.blocks]

    def block_at(self, x, y):
        for (x0, y0, x1, y1), poly, bid in self.blocks:
            if x0 <= x <= x1 and y0 <= y <= y1 and point_in_poly((x, y), poly):
                return bid
        best, bd = None, 1e18
        for (x0, y0, x1, y1), poly, bid in self.blocks:
            d = ((x0 + x1) / 2.0 - x) ** 2 + ((y0 + y1) / 2.0 - y) ** 2
            if d < bd:
                best, bd = bid, d
        return best

    def add(self, kind, typ, pos, color, inten, radius, flicker=0.0, priority=3, block=None, hz=None, size=None, direction=None):
        L = {"id": "light_%05d" % (len(self.out) + 1), "kind": kind, "type": typ, "pos": [_r(pos[0]), _r(pos[1]), _r(pos[2])], "color": [int(c) for c in color], "intensity_hint": _r(inten, 2),
             "radius": _r(radius), "flicker": _r(flicker, 2), "shadow": False, "priority": priority, "hue": hue_of(color), "block_id": block or self.block_at(pos[0], pos[1])}
        if flicker > 0:
            L["flicker_hz"] = _r(hz if hz else 2.0 + 10.0 * flicker, 1)
        if size:
            L["size"] = [_r(size[0]), _r(size[1])]
        if direction:
            L["dir"] = [round(direction[0], 3), round(direction[1], 3), round(direction[2], 3)]
        self.out.append(L)


def make_lights(layout, terrain, rng, buildings, props, signs, arena):
    r = rng.fork("cyber_lights")
    Lx = Lights(layout)
    # --- street lamps, traffic lights, small neon on facades ---------------------------------------------------------------------------
    for p in props:
        k = p["kind"]
        x, y, z = p["pos"]
        if k == "lamp":
            Lx.add("street", "point", (x, y, z + 7.5), PALETTE["tungsten"], 1.0, 14.0, 0.05 if r.chance(0.08) else 0.0, 3)
        elif k == "traffic_light":
            Lx.add("street", "point", (x, y, z + 5.5), PALETTE["cyan"] if r.chance(0.5) else PALETTE["red"], 0.5, 5.0, 0.0, 5)
        elif k == "sign" and p.get("emissive"):
            col = PALETTE[p["variant"]] if p["variant"] in PALETTE else PALETTE["magenta"]
            Lx.add("neon_sign", "point", (x, y, z), _snap(col, r), 0.6 + 0.8 * min(1.0, p["size"][0] * p["size"][1] / 20.0), 7.0, r.choice([0.0, 0.0, 0.1, 0.25]), 4)
        elif k == "vending" and r.chance(0.25):
            Lx.add("street", "point", (x, y, z + 1.4), PALETTE["cyan"] if r.chance(0.6) else PALETTE["tungsten"], 0.25, 3.0, 0.0, 5)
        elif k == "lantern" and r.chance(0.5):
            Lx.add("street", "point", (x, y, z + 2.6), PALETTE["red"], 0.3, 4.0, 0.08, 5)
        elif k == "torii_neon":
            hw = p["width_m"] / 2.0
            ang = math.radians(p["yaw_deg"])
            for q in range(9):
                f = -1.0 + 2.0 * q / 8.0
                Lx.add("neon_tube", "point", (x - math.sin(ang) * hw * f, y + math.cos(ang) * hw * f, z + p["height_m"] * (1.0 - 0.25 * abs(f))), PALETTE["red"] if q % 2 == 0 else PALETTE["magenta"], 1.4, 12.0, 0.1, 1)
            Lx.add("neon_tube", "rect", (x, y, z + p["height_m"]), PALETTE["red"], 2.0, 22.0, 0.0, 1, size=(p["width_m"], 0.4))
    # --- window blocks on tall buildings -----------------------------------------------------------------------------------------------
    for b in buildings:
        if b["height"] < 36.0 or (b["type"] != "generic" and b.get("hero_kind") not in ("glass_tower", "tower_lattice", "twin_tower_hall")):
            continue
        poly = b["footprint"]
        for k in range(len(poly)):
            if k % 2:
                continue
            a, c = poly[k], poly[(k + 1) % len(poly)]
            for zf in (0.28, 0.55, 0.82):
                if r.chance(0.55):
                    Lx.add("window_block", "rect", ((a[0] + c[0]) / 2.0, (a[1] + c[1]) / 2.0, b["base_z"] + b["height"] * zf), PALETTE["tungsten"] if r.chance(0.75) else PALETTE["cyan"], 0.4 + 0.5 * r.random(),
                           20.0, 0.0, 4, size=(8.0, 10.0))
    # --- glass tower crowns and under-lighting --------------------------------------------------------------------------------------------
    for b in buildings:
        fa = b.get("facade")
        if b.get("building_type") != "glass_tower" or not fa:
            continue
        cx = sum(p[0] for p in b["footprint"]) / len(b["footprint"])
        cy = sum(p[1] for p in b["footprint"]) / len(b["footprint"])
        z = b["base_z"] + b["height"]
        for rl in fa["rooftop_lights"]:
            Lx.add("beacon", "point", (cx + rl["pos"][0], cy + rl["pos"][1], z + 2.0), tuple(rl["color"]), 1.6 if rl["kind"] == "beacon" else 0.9, 25.0, 1.0 if rl["kind"] == "beacon" else 0.0, 2, hz=rl["blink_hz"])
        pal = block_palette(b["block_id"])
        for k in range(3):
            a = 2 * math.pi * (k + r.random()) / 3.0
            Lx.add("under_tower", "spot", (cx + math.cos(a) * 18.0, cy + math.sin(a) * 18.0, b["base_z"] + 1.0), PALETTE[pal[k % len(pal)]], 1.8, 60.0, 0.0, 3, direction=(-math.cos(a) * 0.2, -math.sin(a) * 0.2, 1.0))
    # --- mega signs: one face light + the neon tube of the frame ---------------------------------------------------------------------------
    for s in signs:
        w, h = s["size_m"]
        cx, cy, cz = s["pos"]
        nx, ny = s["normal"]
        tx, ty = -ny, nx
        cols = s["palette"]
        mean = cols[0]                       # the face glows in the main palette colour of the sign (a mix of two hues would leave the palette)
        fl = FLICKER[s["animation"]["kind"]]
        face_kind = "billboard" if s["style"] == "billboard_screen" else "neon_sign"
        Lx.add(face_kind, "rect", (cx + nx * 1.5, cy + ny * 1.5, cz), _snap(mean, r), s["emissive_intensity"] / 8.0, max(w, h) * 1.6, fl, 1, size=(w, h), block=s["block_id"], hz=2.0 + 6.0 * s["animation"]["speed"])
        per = 2.0 * (w + h)
        n = max(6, min(16, int(per / 9.0)))
        for k in range(n):
            f = k / n * per
            if f < w:
                dx, dz = f - w / 2.0, -h / 2.0
            elif f < w + h:
                dx, dz = w / 2.0, f - w - h / 2.0
            elif f < 2 * w + h:
                dx, dz = w / 2.0 - (f - w - h), h / 2.0
            else:
                dx, dz = -w / 2.0, h / 2.0 - (f - 2 * w - h)
            Lx.add("neon_tube", "point", (cx + tx * dx + nx * 1.0, cy + ty * dx + ny * 1.0, cz + dz), _snap(cols[k % len(cols)], r), 1.0 + 0.05 * s["emissive_intensity"], 10.0 + 0.1 * max(w, h), fl * 0.5, 2, block=s["block_id"])
    # --- shopfront vertical signs and the neon corridor of the street ------------------------------------------------------------------------
    for b in buildings:
        fa = b.get("facade")
        if b.get("building_type") != "shopfront_row" or not fa:
            continue
        poly = b["footprint"]
        cx = sum(p[0] for p in poly) / len(poly)
        cy = sum(p[1] for p in poly) / len(poly)
        pal = block_palette(b["block_id"])
        sign = 1.0 if fa["street_side"] == "east" else -1.0
        for k in range(fa["vertical_signs"]):
            Lx.add("neon_sign", "point", (max(p[0] for p in poly) + 0.8 if sign > 0 else min(p[0] for p in poly) - 0.8, cy + (k - 1) * 3.0, 5.0 + 3.0 * k), PALETTE[pal[(k + 1) % len(pal)]], 1.2, 9.0, r.choice([0.0, 0.2, 0.4]), 2, block=b["block_id"])
        Lx.add("neon_tube", "rect", (cx + sign * 10.0, cy, 3.2), PALETTE[pal[0]], 0.9, 10.0, 0.0, 3, size=(fa["bay_width_m"], 0.6), block=b["block_id"])
    if layout.strip:
        pts = [tuple(p) for p in layout.road_by_id(layout.strip["road"])["points"]]
        total = sum(math.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1]) for i in range(len(pts) - 1))
        s, k = 4.0, 0
        while s < total:
            x, y, ux, uy = _at(pts, s)
            for side in (-1, 1):
                Lx.add("neon_tube", "point", (x - uy * side * 3.5, y + ux * side * 3.5, 5.5), PALETTE[NEON_NAMES[(k + (side > 0)) % 4]], 1.1, 11.0, 0.05 if k % 5 == 0 else 0.0, 3)
            s += 6.0
            k += 1
    # --- plaza ring --------------------------------------------------------------------------------------------------------------------------
    pc = layout.plaza["center"]
    half = layout.plaza["size"] / 2.0
    for k in range(16):
        a = 2 * math.pi * k / 16
        Lx.add("plaza", "rect", (pc[0] + math.cos(a) * (half - 6.0), pc[1] + math.sin(a) * (half - 6.0), 3.0), PALETTE["tungsten"] if k % 2 else PALETTE["cyan"], 1.2, 45.0, 0.0, 2, size=(12.0, 0.4))
    # --- scramble billboards (screen walls of TASK-015) -----------------------------------------------------------------------------------------
    for b in buildings:
        if b.get("hero_kind") == "scramble_crossing":
            for part in b["parts"]:
                if part["kind"] == "screen_wall":
                    a, c = part["a"], part["b"]
                    Lx.add("billboard", "rect", ((a[0] + c[0]) / 2.0, (a[1] + c[1]) / 2.0, (part["z0"] + part["z1"]) / 2.0), PALETTE["cyan"], 2.5, 50.0, 0.15, 1, size=(math.hypot(c[0] - a[0], c[1] - a[1]), part["z1"] - part["z0"]))
    return Lx.out


def _snap(color, rng):
    """Palette colour with a little brightness jitter (the hue stays the one of the palette)."""
    f = rng.uniform(0.92, 1.0)
    return [int(c * f) for c in color]


def _at(pts, s):
    acc = 0.0
    for i in range(len(pts) - 1):
        l = math.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1])
        if acc + l >= s or i == len(pts) - 2:
            t = max(0.0, min(1.0, (s - acc) / l)) if l > 0 else 0.0
            return (pts[i][0] + (pts[i + 1][0] - pts[i][0]) * t, pts[i][1] + (pts[i + 1][1] - pts[i][1]) * t, (pts[i + 1][0] - pts[i][0]) / l, (pts[i + 1][1] - pts[i][1]) / l)
        acc += l
    return (pts[-1][0], pts[-1][1], 1.0, 0.0)


def light_report(lights, blocks):
    by_kind, by_type, by_prio, hues = {}, {}, {}, {}
    per_block = {}
    for L in lights:
        by_kind[L["kind"]] = by_kind.get(L["kind"], 0) + 1
        by_type[L["type"]] = by_type.get(L["type"], 0) + 1
        by_prio[str(L["priority"])] = by_prio.get(str(L["priority"]), 0) + 1
        hues[L["hue"]] = hues.get(L["hue"], 0) + 1
        pb = per_block.setdefault(L["block_id"], {"total": 0, "neon_hues": {}, "tungsten": 0})
        pb["total"] += 1
        if L["kind"] in ("neon_sign", "neon_tube", "billboard") and L["hue"] != "tungsten":
            pb["neon_hues"][L["hue"]] = pb["neon_hues"].get(L["hue"], 0) + 1
        elif L["hue"] == "tungsten":
            pb["tungsten"] += 1
    dominant = {}
    for bid, pb in per_block.items():
        tot = sum(pb["neon_hues"].values())
        dominant[bid] = sorted(h for h, c in pb["neon_hues"].items() if c >= 0.1 * max(1, tot))
    return {"total": len(lights), "by_kind": by_kind, "by_type": by_type, "by_priority": by_prio, "hue_share": {k: round(v / len(lights), 3) for k, v in sorted(hues.items())},
            "dominant_neon_hues_per_block": dominant, "max_dominant_hues_in_a_block": max((len(v) + (1 if per_block[b]["tungsten"] else 0) for b, v in dominant.items()), default=0),
            "shadow_default": False, "palette": {k: list(v) for k, v in PALETTE.items()}}


# ---- fog maps ------------------------------------------------------------------------------------------------------------------------------------------------
FOG_RES = 512
FOG_X = (-800.0, 800.0)
FOG_Y = (0.0, 1200.0)


def make_fog(layout, terrain, lights, props, doc_roads):
    """fog_density.png (8-bit grey: 0 = clear, 255 = thickest) and fog_glow.png (RGB: colour of the neon halo in the fog). 512 x 512 over the arena
    (x 3.125 m, y 2.34 m per pixel). Fog is thicker over water and in the plaza / alleys with vents, thinner in the streets; halos sit round neon and billboards."""
    W = H = FOG_RES
    sx, sy = (FOG_X[1] - FOG_X[0]) / W, (FOG_Y[1] - FOG_Y[0]) / H

    def px(x, y):
        return ((x - FOG_X[0]) / sx, H - (y - FOG_Y[0]) / sy)

    roads = Canvas(W, H, (0, 0, 0))
    for rd in doc_roads:
        pts = [px(*p) for p in rd["points"]]
        hw = rd["width"] / 2.0 / ((sx + sy) / 2.0)
        for i in range(len(pts) - 1):
            roads.thick_line(pts[i], pts[i + 1], max(0.8, hw), (255, 255, 255))
    dens = [[0.0] * W for _ in range(H)]
    for j in range(H):
        y = FOG_Y[0] + (H - j - 0.5) * sy
        row = dens[j]
        for i in range(W):
            x = FOG_X[0] + (i + 0.5) * sx
            z = terrain.height(x, y)
            d = 0.46
            if z < 0.5:
                d += 0.20                                  # fog lies on the water and the canal
            if roads.buf[(j * W + i) * 3]:
                d -= 0.15                                  # streets are clearer
            row[i] = d
    pc = layout.plaza["center"]
    for (cx, cy, rad, amp) in [(pc[0], pc[1], 95.0, 0.10)] + [(p["pos"][0], p["pos"][1], 16.0, 0.16) for p in props if p["kind"] == "steam_vent"]:
        ci, cj = px(cx, cy)
        ri, rj = rad / sx, rad / sy
        for j in range(max(0, int(cj - rj)), min(H, int(cj + rj) + 1)):
            for i in range(max(0, int(ci - ri)), min(W, int(ci + ri) + 1)):
                q = ((i - ci) / ri) ** 2 + ((j - cj) / rj) ** 2
                if q < 1.0:
                    dens[j][i] += amp * (1.0 - q) ** 2
    glow = [[0.0, 0.0, 0.0] for _ in range(W * H)]
    for L in lights:
        if L["kind"] not in ("neon_sign", "neon_tube", "billboard", "plaza", "beacon"):
            continue
        ci, cj = px(L["pos"][0], L["pos"][1])
        rad = min(34.0, 10.0 + 0.5 * L["radius"])
        ri, rj = rad / sx, rad / sy
        amp = 0.05 * L["intensity_hint"] * (0.6 if L["priority"] > 2 else 1.0)
        for j in range(max(0, int(cj - rj)), min(H, int(cj + rj) + 1)):
            for i in range(max(0, int(ci - ri)), min(W, int(ci + ri) + 1)):
                q = ((i - ci) / ri) ** 2 + ((j - cj) / rj) ** 2
                if q < 1.0:
                    g = amp * (1.0 - q) ** 2
                    cell = glow[j * W + i]
                    cell[0] += L["color"][0] / 255.0 * g
                    cell[1] += L["color"][1] / 255.0 * g
                    cell[2] += L["color"][2] / 255.0 * g
    gray = bytearray(W * H)
    rgb = bytearray(W * H * 3)
    for j in range(H):
        for i in range(W):
            g = glow[j * W + i]
            lum = (g[0] + g[1] + g[2]) / 3.0
            d = dens[j][i] + 0.25 * (1.0 - math.exp(-lum * 3.0))      # fog is brighter / thicker where it is lit
            gray[j * W + i] = max(0, min(255, int(d * 255.0)))
            k = (j * W + i) * 3
            for c in range(3):
                rgb[k + c] = max(0, min(255, int(255.0 * (1.0 - math.exp(-g[c] * 2.5)))))
    meta = {"density": "fog_density.png", "glow": "fog_glow.png", "resolution": [W, H], "extent": {"x_min": FOG_X[0], "x_max": FOG_X[1], "y_min": FOG_Y[0], "y_max": FOG_Y[1]},
            "row_order": "y_descending (row 0 = y_max)", "meters_per_pixel": [round(sx, 3), round(sy, 3)],
            "encoding": "density: 0 = clear air, 255 = densest; glow: sRGB colour of the neon halo (add to the fog scattering colour, scale by density)"}
    return encode_png_gray(W, H, gray), encode_png(W, H, rgb), meta, gray, rgb
