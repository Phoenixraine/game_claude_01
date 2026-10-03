"""Hard-surface trim sheet: 16 horizontal strips (each tileable along U) with panel lines, bevels, rivets, slots, cable channels,
screws, hazard stripes, tread plate. One sheet = BaseColor + Normal + ORM + Height, plus a JSON of UV regions."""
import math

import numpy as np

from . import maps
from . import noise as nz

F32 = np.float32

STRIPS = [  # name, relative height, description
    ("panel_line_wide", 1.0, "wide recessed panel line with chamfered walls"),
    ("panel_line_narrow", 0.6, "narrow recessed panel line"),
    ("bevel_soft", 1.0, "soft rounded edge strip"),
    ("bevel_hard", 1.0, "hard 45 degree chamfer strip"),
    ("rivets_small", 0.6, "row of small domed rivets"),
    ("rivets_large", 1.0, "row of large bolts"),
    ("slots_vent", 1.0, "rounded vent slots"),
    ("cable_channel", 1.2, "channel with three cables"),
    ("screw_heads", 0.8, "hex screw heads"),
    ("hazard_stripe", 0.8, "orange/graphite diagonal stripes"),
    ("plain_graphite", 1.0, "plain worn graphite"),
    ("plain_ceramic", 1.0, "plain ceramic gray"),
    ("grille", 1.0, "fine grille"),
    ("tread_plate", 1.0, "diamond tread"),
    ("seam_double", 0.8, "double seam with rivets"),
    ("handle_rail", 1.2, "recessed handle rail"),
]


def _smooth_edge(x, w):
    return nz.smoothstep(x, 0.0, w)


def build_trim(n):
    rng = nz.rng_for("trim_sheet")
    H = np.zeros((n, n), F32) + 0.5
    base = np.zeros((n, n, 3), F32)
    rough = np.zeros((n, n), F32) + 0.5
    metal = np.zeros((n, n), F32) + 0.8
    tot = sum(s[1] for s in STRIPS)
    y0 = 0
    regions = []
    macro_all = nz.fbm(n, rng, 2.0, 2, 24)
    fine_all = nz.fbm(n, rng, 1.0, 40, n / 3)
    graph = np.stack([0.06 + 0.04 * macro_all, 0.062 + 0.04 * macro_all, 0.068 + 0.045 * macro_all], -1).astype(F32)
    ceram = np.stack([0.5 + 0.1 * fine_all] * 3, -1).astype(F32)
    for si, (name, rel, desc) in enumerate(STRIPS):
        hpx = int(round(n * rel / tot)) if si < len(STRIPS) - 1 else n - y0
        y1 = y0 + hpx
        sl = slice(y0, y1)
        yy, xx = np.meshgrid((np.arange(hpx) + 0.5) / hpx, (np.arange(n) + 0.5) / n, indexing="ij")
        asp = n / hpx                                     # strip aspect: u spans n px, v spans hpx px
        h = np.zeros((hpx, n), F32) + 0.55
        col = graph[sl].copy()
        rg = np.full((hpx, n), 0.45, F32)
        mt = np.full((hpx, n), 0.8, F32)
        v = yy
        if name.startswith("panel_line"):
            w = 0.12 if name.endswith("wide") else 0.06
            d = np.abs(v - 0.5)
            h -= 0.35 * (1 - nz.smoothstep(d, w * 0.5, w))
            h += 0.1 * np.exp(-(((d - w * 1.2) / 0.05) ** 2))
            col = np.where((d < w)[..., None], col * 0.4, col)
        elif name == "bevel_soft":
            h = 0.3 + 0.5 * np.sin(np.clip(v, 0, 1) * math.pi / 2) ** 2
        elif name == "bevel_hard":
            h = np.where(v < 0.5, 0.25 + v * 1.0, 0.75)
            col = np.where((v < 0.5)[..., None], col * 1.8 + 0.03, col)
        elif name.startswith("rivets"):
            count = 40 if name.endswith("small") else 20
            r = 0.3 if name.endswith("small") else 0.38
            ux = ((xx * count) % 1.0 - 0.5) * (n / count) / hpx          # in strip-height units
            vy = v - 0.5
            dd = np.sqrt(ux * ux + vy * vy) / r
            dome = np.clip(1 - dd ** 2, 0, 1) ** 0.6
            h += 0.4 * dome
            ring = np.exp(-(((dd - 1.15) / 0.1) ** 2))
            h -= 0.12 * ring
            col = np.where((dd < 1.0)[..., None], np.array([0.3, 0.3, 0.32], F32) * (0.6 + 0.4 * dome[..., None]), col)
            rg = np.where(dd < 1.0, 0.35, rg)
        elif name == "slots_vent":
            count = 16
            ux = ((xx * count) % 1.0 - 0.5) * (n / count) / hpx
            vy = v - 0.5
            slot = (np.abs(ux) < 0.55 - np.abs(vy) * 0.2) & (np.abs(vy) < 0.3)
            h = np.where(slot, 0.15, h + 0.0)
            col = np.where(slot[..., None], 0.012, col)
        elif name == "cable_channel":
            d = np.abs(v - 0.5)
            h -= 0.3 * (1 - nz.smoothstep(d, 0.4, 0.46))
            for k, c in enumerate((0.3, 0.5, 0.7)):
                wob = 0.015 * np.sin(xx * 2 * math.pi * (3 + k))
                dd = np.abs(v - c - wob) / 0.09
                cab = np.clip(1 - dd ** 2, 0, 1) ** 0.5
                h += 0.4 * cab * (d < 0.45)
                col = np.where(((dd < 1) & (d < 0.45))[..., None], np.array([0.02, 0.02, 0.022], F32) * (0.8 + 0.4 * k * 0.3), col)
                rg = np.where(dd < 1, 0.8, rg)
                mt = np.where(dd < 1, 0.0, mt)
        elif name == "screw_heads":
            count = 24
            ux = ((xx * count) % 1.0 - 0.5) * (n / count) / hpx
            vy = v - 0.5
            dd = np.sqrt(ux * ux + vy * vy) / 0.32
            hexa = np.maximum(np.abs(ux) * 0.866 + np.abs(vy) * 0.5, np.abs(vy)) / 0.3
            head = (hexa < 1.0)
            h += 0.3 * head - 0.15 * ((np.abs(vy) < 0.04) & head)
            col = np.where(head[..., None], np.array([0.33, 0.33, 0.35], F32), col)
        elif name == "hazard_stripe":
            t = ((xx * 24 * asp / asp + v * 0.0 + (v * hpx / n) * 24) % 1.0)
            st = (t < 0.5)
            col = np.where(st[..., None], np.array([0.9, 0.38, 0.05], F32), np.array([0.05, 0.05, 0.055], F32))
            rg = np.where(st, 0.55, 0.6)
            mt = np.where(st, 0.0, 0.5)
        elif name == "plain_graphite":
            h += 0.01 * (macro_all[sl] - 0.5)
        elif name == "plain_ceramic":
            col = ceram[sl].copy()
            mt = np.full((hpx, n), 0.02, F32)
            rg = np.full((hpx, n), 0.6, F32)
            h += 0.01 * (macro_all[sl] - 0.5)
        elif name == "grille":
            lines = 0.5 + 0.5 * np.sin(v * hpx / 6.0 * math.pi)
            lines = (lines > 0.5).astype(F32)
            h = 0.25 + 0.4 * lines
            col = np.where((lines < 0.5)[..., None], 0.01, col)
        elif name == "tread_plate":
            cx = (xx * 40 * 1.0) % 1.0
            cy = (v * hpx / n * 40 * 1.0) % 1.0
            a = np.abs(((cx + cy) % 1.0) - 0.5) < 0.12
            b = np.abs(((cx - cy) % 1.0) - 0.5) < 0.12
            h = 0.4 + 0.3 * (a | b).astype(F32)
        elif name == "seam_double":
            d = np.abs(v - 0.5)
            h -= 0.3 * np.exp(-(((d - 0.2) / 0.05) ** 2)) + 0.3 * np.exp(-(((d + 0.0) / 0.05) ** 2))
            ux = ((xx * 48) % 1.0 - 0.5) * (n / 48) / hpx
            dd = np.sqrt(ux * ux + (v - 0.8) ** 2) / 0.1
            h += 0.3 * np.clip(1 - dd ** 2, 0, 1)
        elif name == "handle_rail":
            d = np.abs(v - 0.5)
            h -= 0.3 * (1 - nz.smoothstep(d, 0.34, 0.42))
            rail = np.clip(1 - np.abs(v - 0.5) / 0.16, 0, 1) ** 0.5
            mask = ((xx > 0.1) & (xx < 0.9))
            h += 0.45 * rail * mask
            col = np.where((rail > 0)[..., None] & mask[..., None], np.array([0.5, 0.5, 0.52], F32), col)
            mt = np.where((rail > 0) & mask, 1.0, mt)
            rg = np.where((rail > 0) & mask, 0.25, rg)
        # seamless guarantee: all patterns are periodic in x; add worn edges via fine noise
        H[sl], base[sl], rough[sl], metal[sl] = h, col, rg, mt
        regions.append({"name": name, "desc": desc, "pixels": [0, y0, n, y1],
                        "uv_top_left": [0.0, round(y0 / n, 6), 1.0, round(y1 / n, 6)],
                        "uv_bottom_left": [0.0, round(1 - y1 / n, 6), 1.0, round(1 - y0 / n, 6)]})
        y0 = y1
    mat = maps.Material("trim_sheet", base, H, rough, metal, normal_strength=3.0)
    mat.finish()
    return mat, regions
