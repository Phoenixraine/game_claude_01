"""The 18 tileable PBR materials of TASK-008. Each recipe: (n, rng) -> maps.Material. All sizes are fractions of the tile,
so the same recipe works at 2048 or at the 256 px used by the tests. Visible features are noise/Voronoi/line based and seamless."""
import numpy as np

from . import noise as nz
from .maps import Material

F32 = np.float32


def mix(a, b, t):
    t = t[..., None] if a.ndim == 3 and t.ndim == 2 else t
    return a * (1 - t) + b * t


def col(r, g, b):
    return np.array([r, g, b], dtype=F32)


def solid(n, c):
    return np.broadcast_to(np.array(c, dtype=F32), (n, n, 3)).copy()


def edge_wear(h, radius=3.0, gain=6.0):
    """Convex edges (height above its blurred surroundings), 0..1."""
    return np.clip((h - nz.blur(h, radius)) * gain, 0, 1).astype(F32)


def sw(n, w):
    """Line width in pixels scaled with the resolution (min 1)."""
    return max(1.0, w * n / 2048.0)


# ------------------------------------------------------------------------------------------------ hard-surface armour
def graphite_armor_worn(n, rng):
    groove, u, v = nz.grid_cells(n, 4, 4, seam=0.018, bevel=0.03)
    macro = nz.fbm(n, rng, 2.4, 1, 9)
    micro = nz.fbm(n, rng, 1.0, 60, n / 3)
    scr = nz.lines(n, rng, 320, (0.04, 0.35), (sw(n, 0.7), sw(n, 1.6)), bright=(0.3, 1.0), curvy=0.2)
    d1, _ = nz.worley(n, rng, 40, 1.0)
    chips = nz.smoothstep(nz.fbm(n, rng, 1.6, 4, 60), 0.82, 0.9) * (1 - nz.smoothstep(d1, 0.2, 0.5))
    h = 0.55 - 0.3 * groove + 0.035 * micro - 0.08 * chips - 0.03 * scr
    wear = np.clip(edge_wear(h, 2.5, 7.0) * 0.9 + scr * 0.7 + chips + groove * 0.15, 0, 1)
    paint = nz.ramp(macro, [(0, (0.045, 0.047, 0.052)), (0.6, (0.07, 0.073, 0.08)), (1, (0.11, 0.115, 0.125))])
    steel = solid(n, (0.42, 0.43, 0.45))
    base = mix(paint, steel, wear)
    rough = 0.42 + 0.22 * macro + 0.1 * micro - 0.28 * wear
    metal = 0.75 + 0.25 * wear
    return Material("graphite_armor_worn", base, h, rough, metal, ao=1 - 0.5 * groove, normal_strength=3.0)


def ceramic_gray_panels(n, rng):
    groove, u, v = nz.grid_cells(n, 3, 3, seam=0.02, bevel=0.03)
    _, _, cid = nz.worley(n, rng, 3, 0.0, True)
    macro = nz.fbm(n, rng, 2.2, 1, 8)
    speck = nz.fbm(n, rng, 0.2, 80, n / 2)
    stains = nz.smoothstep(nz.fbm(n, rng, 2.6, 4, 30), 0.62, 0.95)
    scr = nz.lines(n, rng, 160, (0.03, 0.2), (sw(n, 0.6), sw(n, 1.2)), bright=(0.2, 0.7))
    h = 0.6 - 0.28 * groove + 0.02 * speck - 0.02 * scr
    tint = (cid - 0.5) * 0.06
    c = 0.58 + 0.08 * macro + tint + 0.05 * (speck - 0.5)
    base = np.stack([c, c * 1.005, c * 1.02], -1).astype(F32)
    base = mix(base, base * 0.7, stains * 0.35)
    base = mix(base, solid(n, (0.12, 0.12, 0.13)), groove * 0.7)
    base = mix(base, solid(n, (0.78, 0.78, 0.78)), scr * 0.4)
    rough = 0.55 + 0.15 * macro + 0.1 * stains - 0.1 * scr
    return Material("ceramic_gray_panels", base, h, rough, np.zeros((n, n), F32) + 0.02, ao=1 - 0.5 * groove, normal_strength=2.2)


def dark_metal_scratched(n, rng):
    brushed = nz.fbm(n, rng, 0.6, 2, n / 2, aniso=(1.0, 40.0))
    fine = nz.fbm(n, rng, 1.0, 40, n / 2)
    scr = nz.lines(n, rng, 700, (0.03, 0.4), (sw(n, 0.5), sw(n, 1.3)), bright=(0.2, 1.0), curvy=0.1)
    scr2 = nz.lines(n, rng, 120, (0.1, 0.5), (sw(n, 1.5), sw(n, 3.0)), bright=(0.5, 1.0), angle=0.4)
    macro = nz.fbm(n, rng, 2.6, 1, 8)
    h = 0.5 + 0.03 * (brushed - 0.5) + 0.02 * fine - 0.05 * scr - 0.09 * scr2
    base = nz.ramp(macro * 0.6 + brushed * 0.4, [(0, (0.022, 0.023, 0.026)), (1, (0.06, 0.062, 0.07))])
    base = mix(base, solid(n, (0.35, 0.36, 0.38)), np.clip(scr * 0.55 + scr2 * 0.8, 0, 1))
    rough = 0.34 + 0.2 * brushed + 0.12 * macro - 0.15 * scr
    return Material("dark_metal_scratched", base, h, rough, 0.92 + 0 * h, normal_strength=2.0)


def basalt_armor_worn(n, rng):
    """Enemy variant: darker basalt panels, small dark-red technical marks."""
    groove, u, v = nz.grid_cells(n, 4, 4, seam=0.018, bevel=0.03)
    macro = nz.fbm(n, rng, 2.4, 1, 9)
    crystals = nz.worley(n, rng, 120, 1.0)[0]
    micro = nz.fbm(n, rng, 1.0, 60, n / 3)
    scr = nz.lines(n, rng, 300, (0.04, 0.3), (sw(n, 0.7), sw(n, 1.5)), bright=(0.3, 1.0), curvy=0.2)
    h = 0.55 - 0.3 * groove + 0.03 * micro + 0.015 * crystals - 0.03 * scr
    wear = np.clip(edge_wear(h, 2.5, 7.0) * 0.8 + scr * 0.6, 0, 1)
    base = nz.ramp(macro, [(0, (0.022, 0.021, 0.024)), (0.6, (0.036, 0.034, 0.038)), (1, (0.06, 0.056, 0.058))])
    base = base * (0.85 + 0.3 * (1 - crystals[..., None]))
    # dark-red marks: a few bars and ticks, aligned to the panel grid
    marks = np.zeros((n, n), F32)
    yy, xx = np.meshgrid(np.arange(n) / n, np.arange(n) / n, indexing="ij")
    for _ in range(9):
        cx, cy = rng.integers(0, 4) / 4 + 0.07, rng.integers(0, 4) / 4 + rng.uniform(0.06, 0.18)
        w, hh = rng.uniform(0.05, 0.11), rng.uniform(0.008, 0.016)
        marks = np.maximum(marks, ((np.abs(xx - cx) < w) & (np.abs(yy - cy) < hh)).astype(F32))
    marks = np.clip(nz.blur(marks, 0.8) * 1.4, 0, 1) * (1 - 0.6 * nz.fbm(n, rng, 1.8, 20, 150) * (n > 0))
    base = mix(base, solid(n, (0.42, 0.04, 0.045)), marks * 0.95)
    base = mix(base, solid(n, (0.3, 0.29, 0.3)), wear * 0.8)
    rough = 0.5 + 0.2 * macro - 0.25 * wear
    metal = 0.55 + 0.4 * wear
    return Material("basalt_armor_worn", base, h, rough, metal, ao=1 - 0.5 * groove, normal_strength=3.0)


def hydraulic_steel(n, rng):
    ring = nz.fbm(n, rng, 0.3, 4, n / 2, aniso=(1.0, 60.0))
    fine = nz.fbm(n, rng, 1.0, 50, n / 2)
    streak = nz.fbm(n, rng, 2.0, 1, 10, aniso=(0.25, 1.0))
    oil = nz.smoothstep(streak, 0.55, 0.9)
    scr = nz.lines(n, rng, 180, (0.03, 0.2), (sw(n, 0.5), sw(n, 1.0)), bright=(0.3, 1.0), angle=0.0)
    h = 0.5 + 0.015 * ring + 0.01 * fine - 0.02 * scr
    base = nz.ramp(0.7 * ring + 0.3 * fine, [(0, (0.55, 0.57, 0.6)), (1, (0.78, 0.8, 0.83))])
    base = mix(base, solid(n, (0.06, 0.05, 0.035)), oil * 0.45)
    rough = 0.16 + 0.15 * ring + 0.25 * oil
    return Material("hydraulic_steel", base, h, rough, 1.0 - 0.1 * oil + 0 * h, normal_strength=1.2)


def rubber_black(n, rng):
    grain = nz.fbm(n, rng, 0.9, 30, n / 2)
    bumps = nz.fbm(n, rng, 2.2, 3, 60)
    cr = nz.lines(n, rng, 90, (0.04, 0.2), (sw(n, 0.8), sw(n, 1.6)), bright=(0.5, 1.0), curvy=0.4)
    h = 0.5 + 0.05 * grain + 0.05 * bumps - 0.12 * cr
    base = nz.ramp(0.6 * grain + 0.4 * bumps, [(0, (0.010, 0.010, 0.011)), (1, (0.05, 0.05, 0.052))])
    rough = 0.82 + 0.12 * grain - 0.05 * cr
    return Material("rubber_black", base, h, rough, np.zeros((n, n), F32), normal_strength=2.5)


# --------------------------------------------------------------------------------------------------- city surfaces
def _concrete_base(n, rng):
    macro = nz.fbm(n, rng, 2.6, 1, 8)
    agg = nz.fbm(n, rng, 0.8, 24, n / 2)
    pits = 1 - nz.smoothstep(nz.worley(n, rng, 90, 1.0)[0], 0.0, 0.1)
    pits = pits * nz.smoothstep(nz.fbm(n, rng, 1.5, 3, 40), 0.55, 0.8)
    return macro, agg, pits


def concrete_weathered(n, rng):
    macro, agg, pits = _concrete_base(n, rng)
    stain = nz.smoothstep(nz.fbm(n, rng, 2.4, 2, 14, aniso=(1.0, 0.35)), 0.5, 0.9)
    seams = nz.grid_cells(n, 2, 2, seam=0.012, bevel=0.02)[0]
    h = 0.55 + 0.05 * agg + 0.03 * macro - 0.08 * pits * 0.8 - 0.15 * seams
    base = nz.ramp(0.5 * macro + 0.5 * agg, [(0, (0.32, 0.32, 0.31)), (1, (0.55, 0.55, 0.53))])
    base = mix(base, solid(n, (0.16, 0.16, 0.15)), stain * 0.5)
    base = mix(base, solid(n, (0.12, 0.12, 0.12)), pits * 0.5)
    rough = 0.8 + 0.12 * agg - 0.1 * stain
    return Material("concrete_weathered", base, h, rough, np.zeros((n, n), F32), normal_strength=3.0)


def _crack_network(n, rng, cells, width, warpamt):
    d1, d2, = nz.worley(n, rng, cells, 1.0)
    edge = d2 - d1
    edge = nz.warp(edge, rng, warpamt, 2.4, 14)
    return 1.0 - nz.smoothstep(edge, 0.0, width)


def concrete_cracked(n, rng):
    macro, agg, pits = _concrete_base(n, rng)
    cr = _crack_network(n, rng, 7, 0.07, 0.025)
    fine = _crack_network(n, rng, 19, 0.035, 0.02) * nz.smoothstep(nz.fbm(n, rng, 2, 1, 6), 0.55, 0.8)
    cracks = np.clip(cr + fine * 0.8, 0, 1)
    h = 0.55 + 0.04 * agg - 0.35 * cracks - 0.06 * pits
    base = nz.ramp(0.5 * macro + 0.5 * agg, [(0, (0.3, 0.3, 0.29)), (1, (0.53, 0.53, 0.51))])
    base = mix(base, solid(n, (0.04, 0.04, 0.04)), cracks * 0.85)
    rough = 0.82 + 0.1 * agg
    return Material("concrete_cracked", base, h, rough, np.zeros((n, n), F32), normal_strength=4.0)


def _asphalt(n, rng):
    stones = nz.worley(n, rng, 160, 1.0)[0]
    grain = nz.fbm(n, rng, 0.7, 30, n / 2)
    macro = nz.fbm(n, rng, 2.4, 1, 8)
    return stones, grain, macro


def asphalt_wet(n, rng):
    stones, grain, macro = _asphalt(n, rng)
    puddle = nz.smoothstep(nz.fbm(n, rng, 2.8, 1, 7), 0.52, 0.66)
    h = 0.5 + 0.05 * grain - 0.04 * stones * (1 - puddle) - 0.02 * puddle
    base = nz.ramp(0.5 * grain + 0.5 * macro, [(0, (0.03, 0.03, 0.032)), (1, (0.075, 0.075, 0.08))])
    base = base * (1 - 0.35 * puddle[..., None])
    rough = (0.78 + 0.12 * grain) * (1 - puddle) + (0.06 + 0.05 * grain) * puddle
    return Material("asphalt_wet", base, h, rough, np.zeros((n, n), F32), normal_strength=2.2)


def asphalt_cracked(n, rng):
    stones, grain, macro = _asphalt(n, rng)
    cr = _crack_network(n, rng, 6, 0.05, 0.03)
    patch = nz.smoothstep(nz.fbm(n, rng, 2.8, 1, 6), 0.6, 0.64)
    h = 0.5 + 0.05 * grain - 0.03 * stones - 0.3 * cr + 0.03 * patch
    base = nz.ramp(0.5 * grain + 0.5 * macro, [(0, (0.04, 0.04, 0.042)), (1, (0.1, 0.1, 0.105))])
    base = mix(base, solid(n, (0.02, 0.02, 0.02)), cr * 0.9)
    base = mix(base, solid(n, (0.022, 0.022, 0.024)), patch * 0.7)
    rough = 0.8 + 0.12 * grain
    return Material("asphalt_cracked", base, h, rough, np.zeros((n, n), F32), normal_strength=3.0)


def sidewalk_tiles(n, rng):
    groove, u, v = nz.grid_cells(n, 8, 8, seam=0.06, bevel=0.05)
    _, _, cid = nz.worley(n, rng, 8, 0.0, True)
    wear = nz.fbm(n, rng, 2.0, 2, 40)
    chips = nz.smoothstep(nz.worley(n, rng, 60, 1.0)[0], 0.0, 0.15)
    h = 0.62 - 0.35 * groove + 0.03 * wear - 0.05 * (1 - chips)
    c = 0.45 + (cid - 0.5) * 0.12 + 0.06 * wear
    base = np.stack([c, c, c * 0.98], -1).astype(F32)
    base = mix(base, solid(n, (0.1, 0.1, 0.09)), groove * 0.85)
    rough = 0.78 + 0.1 * wear
    return Material("sidewalk_tiles", base, h, rough, np.zeros((n, n), F32), ao=1 - 0.4 * groove, normal_strength=3.0)


def brick_facade(n, rng):
    rows, cols = 16, 8
    y, x = np.meshgrid((np.arange(n) + 0.5) / n, (np.arange(n) + 0.5) / n, indexing="ij")
    row = np.floor(y * rows).astype(int)
    xo = x * cols + (row % 2) * 0.5
    u = xo % 1.0
    v = (y * rows) % 1.0
    cell = (np.floor(xo).astype(int) % cols) + row * cols
    rnd = nz.rng_for("brick_ids").random(rows * cols * 2)[cell % (rows * cols * 2)].astype(F32)
    mu = 1.0 - nz.smoothstep(np.minimum(u, 1 - u), 0.02, 0.045)
    mv = 1.0 - nz.smoothstep(np.minimum(v, 1 - v), 0.07, 0.13)
    mortar = np.maximum(mu, mv)
    wear = nz.fbm(n, rng, 2.0, 2, 60)
    speck = nz.fbm(n, rng, 0.5, 40, n / 2)
    h = 0.62 - 0.3 * mortar + 0.04 * speck + 0.03 * wear
    brick = nz.ramp(rnd * 0.7 + 0.3 * wear, [(0, (0.28, 0.1, 0.07)), (0.5, (0.42, 0.17, 0.11)), (1, (0.5, 0.26, 0.17))])
    base = mix(brick * (0.85 + 0.3 * speck[..., None]), solid(n, (0.36, 0.35, 0.32)) * (0.8 + 0.4 * wear[..., None]), mortar)
    soot = nz.smoothstep(nz.fbm(n, rng, 2.4, 1, 8, aniso=(1.0, 0.4)), 0.55, 0.9)
    base = mix(base, base * 0.45, soot * 0.5)
    rough = 0.85 + 0.1 * speck
    return Material("brick_facade", base, h, rough, np.zeros((n, n), F32), ao=1 - 0.4 * mortar, normal_strength=3.5)


def glass_curtain_wall(n, rng):
    gx, gy = 4, 8
    y, x = np.meshgrid((np.arange(n) + 0.5) / n, (np.arange(n) + 0.5) / n, indexing="ij")
    uf, vf = (x * gx) % 1.0, (y * gy) % 1.0
    frame = 1.0 - nz.smoothstep(np.minimum(np.minimum(uf, 1 - uf), np.minimum(vf, 1 - vf)), 0.02, 0.045)
    _, _, cid = nz.worley(n, rng, 4, 0.0, True)
    cellid = (np.floor(x * gx).astype(int) + np.floor(y * gy).astype(int) * gx) % 16
    rnd = nz.rng_for("glass_ids").random(16)[cellid].astype(F32)
    refl = nz.fbm(n, rng, 2.4, 1, 6)
    dirt = nz.smoothstep(nz.fbm(n, rng, 2.2, 2, 30, aniso=(1.0, 0.3)), 0.6, 0.9)
    h = 0.6 - 0.12 * frame
    glass = nz.ramp(0.5 * refl + 0.5 * rnd, [(0, (0.015, 0.03, 0.04)), (1, (0.05, 0.1, 0.13))])
    base = mix(glass, solid(n, (0.2, 0.21, 0.22)), frame)
    base = mix(base, base + 0.08, dirt * 0.5)
    rough = (0.05 + 0.18 * dirt) * (1 - frame) + 0.35 * frame
    metal = frame * 0.9
    return Material("glass_curtain_wall", base, h, rough, metal, normal_strength=1.5)


def rusty_steel_plate(n, rng):
    rustmask = nz.smoothstep(nz.fbm(n, rng, 2.6, 1, 12), 0.5, 0.78)
    pit = nz.smoothstep(nz.worley(n, rng, 70, 1.0)[0], 0.0, 0.14)
    grain = nz.fbm(n, rng, 1.0, 20, n / 2)
    rng2 = nz.fbm(n, rng, 1.6, 6, 80)
    bolts = np.zeros((n, n), F32)
    yy, xx = np.meshgrid((np.arange(n) + 0.5) / n, (np.arange(n) + 0.5) / n, indexing="ij")
    for bx in (0.0625 + 0.125 * np.arange(8)):
        for by in (0.0625, 0.9375):
            bolts = np.maximum(bolts, np.clip(1 - np.sqrt((xx - bx) ** 2 + (yy - by) ** 2) / 0.018, 0, 1))
    h = 0.55 + 0.03 * grain - 0.1 * rustmask * (1 - pit * 0.5) + 0.12 * bolts
    steel = nz.ramp(grain, [(0, (0.14, 0.145, 0.15)), (1, (0.26, 0.27, 0.28))])
    rust = nz.ramp(rng2, [(0, (0.22, 0.08, 0.03)), (0.5, (0.4, 0.17, 0.06)), (1, (0.52, 0.27, 0.1))])
    base = mix(steel, rust, rustmask)
    base = mix(base, base * 0.5, (1 - pit) * 0.5)
    rough = 0.45 + 0.4 * rustmask + 0.1 * grain
    metal = 0.9 * (1 - rustmask) + 0.1
    return Material("rusty_steel_plate", base, h, rough, metal, normal_strength=3.0)


def _corrugated(n, rng, ribs=16):
    y, x = np.meshgrid((np.arange(n) + 0.5) / n, (np.arange(n) + 0.5) / n, indexing="ij")
    prof = 0.5 + 0.5 * np.sin(2 * np.pi * x * ribs)
    return prof.astype(F32)


def corrugated_metal(n, rng):
    prof = _corrugated(n, rng, 16)
    grain = nz.fbm(n, rng, 0.8, 20, n / 2)
    macro = nz.fbm(n, rng, 2.5, 1, 8)
    scr = nz.lines(n, rng, 160, (0.05, 0.4), (sw(n, 0.6), sw(n, 1.4)), bright=(0.3, 1.0), angle=1.5707)
    rust = nz.smoothstep(nz.fbm(n, rng, 2.4, 2, 20, aniso=(0.4, 1.0)) * 0.7 + (1 - prof) * 0.3, 0.55, 0.85)
    h = 0.35 + 0.5 * prof + 0.02 * grain
    paint = nz.ramp(macro, [(0, (0.16, 0.2, 0.19)), (1, (0.27, 0.31, 0.29))])
    base = mix(paint, solid(n, (0.35, 0.16, 0.07)), rust * 0.7)
    base = mix(base, solid(n, (0.5, 0.5, 0.5)), scr * 0.4)
    rough = 0.5 + 0.25 * rust + 0.1 * grain - 0.1 * scr
    return Material("corrugated_metal", base, h, rough, 0.5 + 0.4 * rust * 0, normal_strength=2.5)


def container_painted_worn(n, rng):
    prof = _corrugated(n, rng, 12)
    grain = nz.fbm(n, rng, 0.8, 20, n / 2)
    macro = nz.fbm(n, rng, 2.5, 1, 8)
    chips = nz.smoothstep(nz.fbm(n, rng, 1.5, 3, 60), 0.7, 0.85) * (0.4 + 0.6 * (1 - prof))
    scr = nz.lines(n, rng, 260, (0.05, 0.4), (sw(n, 0.6), sw(n, 1.4)), bright=(0.3, 1.0), curvy=0.1)
    streak = nz.smoothstep(nz.fbm(n, rng, 2.0, 1, 12, aniso=(0.2, 1.0)), 0.55, 0.9)
    h = 0.35 + 0.5 * prof + 0.015 * grain - 0.04 * chips
    paint = nz.ramp(macro, [(0, (0.2, 0.06, 0.05)), (1, (0.3, 0.1, 0.07))])
    paint = mix(paint, paint * 0.5, streak * 0.4)
    base = mix(paint, solid(n, (0.34, 0.15, 0.06)), chips)
    base = mix(base, solid(n, (0.45, 0.45, 0.45)), scr * 0.35)
    rough = 0.55 + 0.2 * grain + 0.15 * chips
    metal = chips * 0.6
    return Material("container_painted_worn", base, h, rough, metal, normal_strength=2.5)


def water_foam_mask(n, rng):
    bubbles = 1 - nz.smoothstep(nz.worley(n, rng, 42, 1.0)[0], 0.0, 0.5)
    fine = 1 - nz.smoothstep(nz.worley(n, rng, 110, 1.0)[0], 0.0, 0.5)
    lace = nz.fbm(n, rng, 1.8, 2, 40)
    big = nz.fbm(n, rng, 2.2, 1, 10)
    foam = np.clip(0.35 * bubbles + 0.2 * fine + 0.5 * lace + 0.5 * big - 0.3, 0, 1)
    foam = nz.smoothstep(foam, 0.2, 0.6)
    h = foam * 0.8 + 0.1 * lace
    base = np.stack([foam, foam, foam], -1)
    return Material("water_foam_mask", base, h, 0.55 + 0.35 * (1 - foam), np.zeros((n, n), F32), normal_strength=2.0,
                    note="white = foam; BaseColor doubles as the foam mask (grayscale)")


def gravel_rubble(n, rng):
    d1, d2, idv = nz.worley(n, rng, 38, 0.9, True)
    stone = 1 - nz.smoothstep(d1, 0.0, 0.62)
    shade = 0.3 + 0.5 * idv
    dust = nz.fbm(n, rng, 2.2, 2, 40)
    tint = nz.rng_for("gravel_tint").random(3)
    h = 0.2 + 0.7 * stone * (0.7 + 0.3 * idv) + 0.05 * dust
    base = np.stack([shade * (0.9 + 0.2 * tint[0]), shade * (0.9 + 0.2 * tint[1]), shade * (0.88 + 0.2 * tint[2])], -1).astype(F32) * (0.5 + 0.5 * stone[..., None])
    base = mix(base, solid(n, (0.35, 0.34, 0.32)), dust * 0.3)
    rough = 0.82 + 0.1 * dust
    return Material("gravel_rubble", base, h, rough, np.zeros((n, n), F32), normal_strength=5.0)


MATERIALS = [graphite_armor_worn, ceramic_gray_panels, dark_metal_scratched, basalt_armor_worn, hydraulic_steel, rubber_black,
             concrete_weathered, concrete_cracked, asphalt_wet, asphalt_cracked, sidewalk_tiles, brick_facade, glass_curtain_wall,
             rusty_steel_plate, corrugated_metal, container_painted_worn, water_foam_mask, gravel_rubble]


def build_material(fn, n):
    rng = nz.rng_for(fn.__name__)
    return fn(n, rng).finish()
