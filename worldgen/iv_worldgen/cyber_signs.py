"""Mega signs (TASK-019): building-sized neon signs on tower facades. Placement is rule based and checked against the battle plaza: a sign is only put on
a facade that faces the plaza centre with a clear 2D ray at 40 m eye height (no building of >= 40 m in between)."""
import math

from .cyber_data import NEON_NAMES, PALETTE
from .geom import bbox, centroid, norm, point_in_poly, segments_intersect

EYE_Z = 40.0
SKIP_HEROES = {"expressway", "suspension_bridge", "scramble_crossing", "tower_lattice", "temple_gate", "port_crane", "sphere_building"}
STYLES = ["vertical_banner", "billboard_screen", "neon_tube_kanji", "holo_ad", "logo_sphere"]
ANIMATIONS = {"vertical_banner": ["scroll", "pulse", "cycle"], "billboard_screen": ["cycle", "scroll", "flicker"], "neon_tube_kanji": ["flicker", "pulse"], "holo_ad": ["cycle", "pulse"],
              "logo_sphere": ["pulse", "cycle"]}


def block_palette(block_id):
    """Three of the four neon hues for a block (stable per id); tungsten is reserved for lamps and windows."""
    h = 0
    for ch in str(block_id):
        h = (h * 131 + ord(ch)) & 0xFFFFFFFF
    skip = h % 4
    cols = [n for k, n in enumerate(NEON_NAMES) if k != skip]
    return cols if (h >> 3) % 3 else NEON_NAMES[:]       # a third of the blocks keeps all four


def _seg_hits_poly(a, b, poly):
    x0, y0, x1, y1 = bbox(poly)
    if max(a[0], b[0]) < x0 or min(a[0], b[0]) > x1 or max(a[1], b[1]) < y0 or min(a[1], b[1]) > y1:
        return False
    n = len(poly)
    for i in range(n):
        if segments_intersect(a, b, poly[i], poly[(i + 1) % n]):
            return True
    return point_in_poly(a, poly) or point_in_poly(b, poly)


def clear_ray(view, target, polys_with_height, skip_index):
    """True when no building (height >= EYE_Z) other than `skip_index` crosses the 2D segment view -> target."""
    for i, (poly, h) in enumerate(polys_with_height):
        if i == skip_index or h < EYE_Z:
            continue
        if _seg_hits_poly(view, target, poly):
            return False
    return True


def facade_candidates(buildings, view):
    """All facade edges (>= 12 m long, building >= 40 m) that face `view` with a clear ray. Returns dicts with building index and geometry."""
    polys = [([tuple(p) for p in b["footprint"]], b["height"]) for b in buildings]
    out = []
    for bi, b in enumerate(buildings):
        if b["height"] < 40.0 or b.get("hero_kind") in SKIP_HEROES or b["building_type"] in ("parking", "temple", "crane"):
            continue
        poly = polys[bi][0]
        c = centroid(poly)
        n = len(poly)
        for i in range(n):
            a, e = poly[i], poly[(i + 1) % n]
            length = math.hypot(e[0] - a[0], e[1] - a[1])
            if length < 12.0:
                continue
            mid = ((a[0] + e[0]) / 2.0, (a[1] + e[1]) / 2.0)
            nrm = norm((mid[0] - c[0], mid[1] - c[1]))
            if (view[0] - mid[0]) * nrm[0] + (view[1] - mid[1]) * nrm[1] <= 2.0:        # facing away from the plaza
                continue
            tgt = (mid[0] + nrm[0] * 0.6, mid[1] + nrm[1] * 0.6)
            if not clear_ray(view, tgt, polys, bi):
                continue
            d = math.hypot(view[0] - mid[0], view[1] - mid[1])
            out.append({"bi": bi, "a": a, "b": e, "length": length, "normal": nrm, "mid": mid, "dist": d})
    return out


def _glyphs(rng, sets, style):
    def pick(name, n):
        g = sets[name]
        return [g[rng.below(len(g))]["id"] for _ in range(n)]
    if style == "vertical_banner":
        return "kanji_like", pick("kanji_like", rng.randint(4, 9)), "vertical"
    if style == "billboard_screen":
        return "mixed", pick("pictograms", rng.randint(1, 3)) + pick("kana_like", rng.randint(4, 9)), "horizontal"
    if style == "neon_tube_kanji":
        return "kanji_like", pick("kanji_like", rng.randint(2, 5)), "horizontal"
    if style == "holo_ad":
        return "mixed", pick("pictograms", rng.randint(1, 3)) + pick("digits_like", rng.randint(0, 3)), "stack"
    return "pictograms", pick("pictograms", 1), "single"


def place_mega_signs(buildings, layout, rng, view, glyph_sets, target=96, monster_share=0.30):
    """Returns the sign list. `view` is the plaza centre. Monsters (>= 40 m tall) go first onto the tallest visible facades."""
    sets = {k: v for k, v in glyph_sets["sets"].items()}
    polys_all = [([tuple(p) for p in b["footprint"]], b["height"]) for b in buildings]
    cands = facade_candidates(buildings, view)
    cands.sort(key=lambda c: (-buildings[c["bi"]]["height"], c["dist"]))
    by_building = {}
    for c in cands:
        by_building.setdefault(c["bi"], []).append(c)
    signs = []
    used = {}                 # (building index, edge a) -> number of signs already placed on that facade

    def make(c, style, monster):
        b = buildings[c["bi"]]
        H = b["height"]
        L = c["length"]
        nrm = c["normal"]
        k = used.get((c["bi"], c["a"]), 0)
        slots = 3 if L >= 36.0 else 2 if L >= 22.0 else 1
        if k >= slots:
            return False
        t = (k + 0.5) / slots + rng.uniform(-0.04, 0.04)
        slot_len = L / slots
        if style == "vertical_banner":
            w = rng.uniform(5.0, min(14.0, slot_len * 0.7))
            h = rng.uniform(46.0, min(180.0, H * 0.78)) if monster else rng.uniform(16.0, min(60.0, H * 0.6))
        elif style == "billboard_screen":
            w = rng.uniform(14.0, min(60.0, slot_len * 0.92))
            h = rng.uniform(40.0, min(60.0, H * 0.5)) if monster else rng.uniform(9.0, 30.0)
        elif style == "neon_tube_kanji":
            w = rng.uniform(7.0, min(24.0, slot_len * 0.8))
            h = rng.uniform(8.0, 28.0) if not monster else rng.uniform(40.0, 52.0)
        elif style == "holo_ad":
            w = rng.uniform(10.0, min(22.0, slot_len * 0.8))
            h = rng.uniform(20.0, 50.0)
        else:
            w = h = rng.uniform(10.0, min(30.0, slot_len * 0.8))
            if monster:
                w = h = max(w, 40.0) if slot_len * 0.9 >= 40.0 else w
        if monster and h < 40.0:
            return False
        if w < 4.0 or h > H - 6.0:
            return False
        z0 = rng.uniform(6.0, max(6.0, H - h - 4.0))
        if style == "vertical_banner" and monster:
            z0 = rng.uniform(6.0, max(6.0, min(H - h - 4.0, H * 0.3)))
        zc = b["base_z"] + z0 + h / 2.0
        off = 0.8 if style not in ("holo_ad", "logo_sphere") else (4.0 if style == "holo_ad" else h / 2.0 + 1.0)
        px = c["a"][0] + (c["b"][0] - c["a"][0]) * t + nrm[0] * off
        py = c["a"][1] + (c["b"][1] - c["a"][1]) * t + nrm[1] * off
        pal = block_palette(b["block_id"])
        colors = [pal[rng.below(len(pal))] for _ in range(2)]
        if colors[0] == colors[1] and len(pal) > 1:
            colors[1] = pal[(pal.index(colors[0]) + 1) % len(pal)]
        gset, glyphs, layout_hint = _glyphs(rng, sets, style)
        kind = rng.choice(ANIMATIONS[style])
        # visibility from the plaza centre with the sign's real centre (ray at eye height checked against the buildings between)
        used[(c["bi"], c["a"])] = k + 1
        cand = ({"id": "mega_%03d" % (len(signs) + 1), "host": b["id"], "block_id": b["block_id"], "style": style, "size_m": [round(w, 1), round(h, 1)],
                      "pos": [round(px, 1), round(py, 1), round(zc, 1)], "yaw_deg": round(math.degrees(math.atan2(nrm[1], nrm[0])), 1), "normal": [round(nrm[0], 3), round(nrm[1], 3)],
                      "offset_m": round(off, 1), "palette": [list(PALETTE[n]) for n in colors], "palette_names": colors, "emissive_intensity": round(rng.uniform(14.0, 34.0) if monster else rng.uniform(5.0, 16.0), 1),
                      "animation": {"kind": kind, "speed": round(rng.uniform(0.3, 1.6), 2), "phase": round(rng.random(), 3)},
                      "glyph_set": gset, "text_glyphs": glyphs, "glyph_layout": layout_hint, "monster": h >= 40.0})
        if not _visible(cand, polys_all, c["bi"], view):
            return False
        signs.append(cand)
        return True

    n_monster = int(round(target * monster_share))
    # pass 1: monsters on the tallest facades (one per building first, spread over the sky line)
    order = [bi for bi, _ in sorted(by_building.items(), key=lambda kv: -buildings[kv[0]]["height"])]
    monster_styles = ["vertical_banner", "vertical_banner", "billboard_screen", "neon_tube_kanji", "logo_sphere", "vertical_banner"]
    k = 0
    for rounds in range(3):
        for bi in order:
            if sum(1 for s in signs if s["monster"]) >= n_monster:
                break
            if buildings[bi]["height"] < 80.0:
                continue
            for c in by_building[bi]:
                st = monster_styles[(k + rounds) % len(monster_styles)]
                k += 1
                if make(c, st, True):
                    break
    # pass 2: everything else, tall to low, round robin over the visible facades
    styles = ["billboard_screen", "vertical_banner", "neon_tube_kanji", "holo_ad", "billboard_screen", "logo_sphere", "vertical_banner", "neon_tube_kanji"]
    k = 0
    for rounds in range(4):
        for bi in order:
            if len(signs) >= target:
                break
            for c in by_building[bi]:
                st = styles[k % len(styles)]
                k += 1
                if make(c, st, False):
                    break
    # renumber by position along the sky line for stable ids
    for i, s in enumerate(signs):
        s["id"] = "mega_%03d" % (i + 1)
    return signs


def _visible(sign, polys, host, view):
    nrm = sign["normal"]
    c = sign["pos"]
    if (view[0] - c[0]) * nrm[0] + (view[1] - c[1]) * nrm[1] <= 0:
        return False
    tgt = (c[0] - nrm[0] * (sign["offset_m"] - 0.6), c[1] - nrm[1] * (sign["offset_m"] - 0.6))
    return clear_ray(view, tgt, polys, host)


def sign_visible(sign, buildings, view):
    """Independent re-check used by the tests: 2D ray at 40 m from `view` to the sign centre, facing included."""
    polys = [([tuple(p) for p in b["footprint"]], b["height"]) for b in buildings]
    host = next(i for i, b in enumerate(buildings) if b["id"] == sign["host"])
    return _visible(sign, polys, host, view)
