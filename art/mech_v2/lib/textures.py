"""PBR synthesis for the per-material atlases: BaseColor / Normal / ORM / Emissive 2048^2 for every mech material, with wear driven by the
BAKED geometry maps (curvature from world position/normal, ambient occlusion, thickness, per-object random id):
paint chipped to bare metal on convex edges, dirt in crevices, vertical streaks (oil, rust, salt), rust at joints, soot near the reactor,
patchwork paint (blue-grey steel, white, light grey, orange, red), hazard stripes and numeral/emblem stencils (placeholders, no words).
Two palettes: the player's BASTION ("player") and the black-basalt enemy ("enemy")."""
import math
import os

import numpy as np

from . import noise as nz
from .noise import smoothstep as ss

TAG_STRIP = 0.025


# ---------------------------------------------------------------------------------------------------- stencils
_SEG = {"0": "abcdef", "1": "bc", "2": "abdeg", "3": "abcdg", "4": "bcfg", "5": "acdfg", "6": "acdefg", "7": "abc", "8": "abcdefg", "9": "abcdfg"}


def _box(u, v, u0, u1, v0, v1):
    return (u >= u0) & (u <= u1) & (v >= v0) & (v <= v1)


def glyph_digits(u, v, text, h=1.0, w=0.55, thick=0.16, gap=0.25):
    """7-segment numerals (placeholders: numbers only, no readable words). u,v in units of the stencil height; origin = lower-left."""
    out = np.zeros(u.shape, dtype=bool)
    for k, ch in enumerate(text):
        x0 = k * (w + gap)
        uu = u - x0
        t = thick
        seg = {"a": _box(uu, v, 0, w, h - t, h), "b": _box(uu, v, w - t, w, h / 2, h), "c": _box(uu, v, w - t, w, 0, h / 2),
               "d": _box(uu, v, 0, w, 0, t), "e": _box(uu, v, 0, t, 0, h / 2), "f": _box(uu, v, 0, t, h / 2, h), "g": _box(uu, v, 0, w, h / 2 - t / 2, h / 2 + t / 2)}
        for s in _SEG[ch]:
            out |= seg[s]
    return out


def glyph_emblem(u, v, kind):
    """Abstract emblems: 0 = ring with a chevron, 1 = three bars, 2 = diamond with a dot, 3 = double chevron."""
    r = np.sqrt((u - 0.5) ** 2 + (v - 0.5) ** 2)
    if kind == 0:
        ring = (r > 0.36) & (r < 0.48)
        chev = (np.abs((u - 0.5)) * 1.1 + 0.1 < (0.5 - np.abs(v - 0.45)) * 0.9) & (np.abs(v - 0.45) < 0.22) & (np.abs(u - 0.5) < 0.3)
        return ring | (chev & ~((np.abs(u - 0.5) * 1.1 + 0.02) < (0.5 - np.abs(v - 0.45)) * 0.9 - 0.1))
    if kind == 1:
        return _box(u, v, 0.05, 0.95, 0.12, 0.3) | _box(u, v, 0.05, 0.95, 0.42, 0.58) | _box(u, v, 0.05, 0.6, 0.7, 0.88)
    if kind == 2:
        d = np.abs(u - 0.5) + np.abs(v - 0.5)
        return ((d > 0.34) & (d < 0.48)) | (r < 0.1)
    c1 = np.abs(u - 0.5) * 0.9 + 0.12 < (0.5 - (v - 0.2) * 0.9)
    c2 = np.abs(u - 0.5) * 0.9 + 0.12 < (0.5 - (v - 0.2) * 0.9) - 0.16
    c3 = np.abs(u - 0.5) * 0.9 + 0.12 < (0.5 - (v - 0.2) * 0.9) - 0.3
    return (c1 & ~c2 & (v > 0.15)) | (c2 & ~c3 & (v > 0.15))


# centre (world, m), outward axis, up hint, height (m), what
STENCILS_PLAYER = [
    ((-27.5, 0.2, 66.0), (-1, 0, 0), (0, 0, 1), 7.0, "07"), ((27.5, 0.2, 66.0), (1, 0, 0), (0, 0, 1), 7.0, "01"),
    ((-15.0, -9.5, 56.0), (0, -1, 0), (0, 0, 1), 5.0, "e0"), ((9.0, -17.2, 54.0), (0, -1, 0), (0, 0, 1), 6.0, "e1"),
    ((-9.0, -17.2, 50.0), (0, -1, 0), (0, 0, 1), 4.0, "e2"), ((0.0, -8.0, 41.0), (0, -1, 0), (0, 0, 1), 3.4, "e3"),
    ((-18.0, -6.0, 31.0), (-1, 0, 0), (0, 0, 1), 4.0, "114"), ((18.0, -6.0, 31.0), (1, 0, 0), (0, 0, 1), 4.0, "114"),
    ((-12.0, -7.6, 14.0), (0, -1, 0), (0, 0, 1), 3.2, "03"), ((12.0, -7.6, 14.0), (0, -1, 0), (0, 0, 1), 3.2, "04"),
    ((0.0, 17.5, 62.0), (0, 1, 0), (0, 0, 1), 5.0, "e1"), ((0.0, 10.0, 41.0), (0, 1, 0), (0, 0, 1), 3.4, "0021"),
    ((-23.0, -5.0, 40.0), (-1, 0, 0), (0, 0, 1), 4.0, "e0"), ((23.0, -5.0, 40.0), (1, 0, 0), (0, 0, 1), 4.0, "e3"),
]
STENCILS_ENEMY = [(c, a, u, h, t) for (c, a, u, h, t) in STENCILS_PLAYER]


def apply_stencils(img_rgb, pos, nrm, ext, stencils, color, strength=0.9, tol=0.55):
    """Paint the stencils into img_rgb (H,W,3) wherever the surface faces the stencil axis near its centre. Returns the stencil mask."""
    H, W = ext.shape
    mask = np.zeros((H, W), dtype=bool)
    for centre, axis, upv, h, text in stencils:
        c = np.array(centre, np.float32)
        a = np.array(axis, np.float32)
        a /= np.linalg.norm(a)
        up = np.array(upv, np.float32)
        t1 = np.cross(up, a)
        t1 /= np.linalg.norm(t1) + 1e-9
        t2 = np.cross(a, t1)
        w_text = (len(text) * 0.8) * h * (0.58 if not text.startswith("e") else 1.0)
        near = ext & (np.einsum("hwc,c->hw", nrm, a) > 0.78)
        d = pos - c
        near &= (np.abs(np.einsum("hwc,c->hw", d, a)) < 5.0)
        lu = np.einsum("hwc,c->hw", d, t1)
        lv = np.einsum("hwc,c->hw", d, t2)
        near &= (np.abs(lu) < w_text * 0.75) & (np.abs(lv) < h * 0.75)
        if not near.any():
            continue
        if text.startswith("e"):
            u = (lu + h / 2) / h
            v = (lv + h / 2) / h
            g = glyph_emblem(u, v, int(text[1:]) % 4) & (u > 0) & (u < 1) & (v > 0) & (v < 1)
        else:
            u = (lu + w_text / 2) / h
            v = (lv + h / 2) / h
            g = glyph_digits(u, v, text, 1.0, 0.55, 0.15, 0.22)
        g &= near
        mask |= g
    for ch in range(3):
        img_rgb[..., ch] = np.where(mask, img_rgb[..., ch] * (1 - strength) + color[ch] * strength, img_rgb[..., ch])
    return mask


# ---------------------------------------------------------------------------------------------------- palettes
PALETTES = {
    "player": dict(
        ceramic=[("steel_blue", (0.17, 0.23, 0.31), 0.30), ("white", (0.70, 0.69, 0.64), 0.26), ("light_grey", (0.46, 0.48, 0.50), 0.18),
                 ("orange", (0.86, 0.34, 0.07), 0.15), ("red", (0.50, 0.08, 0.06), 0.06), ("dark_blue", (0.09, 0.12, 0.18), 0.05)],
        graphite=(0.05, 0.055, 0.068), dark=(0.03, 0.03, 0.034), rubber=(0.022, 0.022, 0.024), orange=(0.9, 0.36, 0.06), stripe=(0.025, 0.025, 0.025),
        stencil=(0.04, 0.04, 0.045), metal=(0.42, 0.43, 0.45), rust=(0.32, 0.13, 0.05), soot=0.5, wear=1.0, glow=(0.25, 0.65, 1.0), glow_back=(0.25, 0.65, 1.0), lamp=(1.0, 0.95, 0.85)),
    "enemy": dict(
        ceramic=[("basalt", (0.050, 0.052, 0.056), 0.50), ("dark_grey", (0.095, 0.098, 0.104), 0.22), ("charcoal", (0.026, 0.027, 0.030), 0.12),
                 ("dark_red", (0.25, 0.03, 0.03), 0.12), ("rust_red", (0.34, 0.10, 0.05), 0.04)],
        graphite=(0.028, 0.030, 0.034), dark=(0.02, 0.02, 0.022), rubber=(0.018, 0.018, 0.02), orange=(0.45, 0.04, 0.03), stripe=(0.02, 0.02, 0.02),
        stencil=(0.40, 0.04, 0.035), metal=(0.30, 0.30, 0.31), rust=(0.30, 0.10, 0.04), soot=0.8, wear=1.25, glow=(1.0, 0.12, 0.08), glow_back=(1.0, 0.18, 0.08), lamp=(1.0, 0.25, 0.15)),
}


class Feat:
    """Per-material feature bundle derived from the baked maps."""

    def __init__(self, maps, res):
        self.res = res
        self.ext = maps["cover"] > 0.5                     # texels with baked data (island + dilation margin)
        self.valid = maps["cover0"] > 0.5                  # exact island coverage
        pos = (maps["pos"] - 0.5) * 200.0
        self.pos = pos.astype(np.float32)
        n = maps["nrm"] * 2 - 1
        n /= np.maximum(np.linalg.norm(n, axis=-1, keepdims=True), 1e-6)
        self.nrm = n.astype(np.float32)
        self.ao_s = maps["ao_s"].astype(np.float32)
        self.ao_l = maps["ao_l"].astype(np.float32)
        self.thk = maps["thk"][..., 0].astype(np.float32) if maps["thk"].ndim == 3 else maps["thk"].astype(np.float32)
        self.rid = maps["rid"][..., 0].astype(np.float32) if maps["rid"].ndim == 3 else maps["rid"].astype(np.float32)
        self.idx = np.nonzero(self.ext.ravel())[0]
        self.strip = np.zeros(self.ext.shape, dtype=bool)
        self.strip[: int(round(TAG_STRIP * res)) + 1, :] = True      # row 0 = v 1.0 (top of the atlas): shared UVs of bolts / hidden faces
        # curvature from the baked world position: -(laplacian . n): > 0 convex edge, < 0 concave
        inner = nz.erode(self.valid, 2)
        p = self.pos
        lap = (np.roll(p, 1, 0) + np.roll(p, -1, 0) + np.roll(p, 1, 1) + np.roll(p, -1, 1) - 4 * p)
        c = -np.einsum("hwc,hwc->hw", lap, self.nrm)
        texel = 0.16
        c = np.where(inner, c, 0.0)
        self.cvx = np.clip(c / (texel * 0.55), 0, 1).astype(np.float32)
        self.ccv = np.clip(-c / (texel * 0.55), 0, 1).astype(np.float32)
        self.cvx = np.maximum(self.cvx, nz.blur(self.cvx, 1) * 1.2).clip(0, 1)

    def f3(self, seed, scale, octaves=4, stretch=(1, 1, 1), offset=(0, 0, 0)):
        """World-space fractal noise sampled on the covered texels, as an (H,W) array."""
        out = np.zeros(self.ext.shape, dtype=np.float32).ravel()
        p = self.pos.reshape(-1, 3)[self.idx] + np.asarray(offset, np.float32)
        out[self.idx] = nz.fbm3(p * (1.0 / scale), seed, octaves, 0.5, stretch)
        return out.reshape(self.ext.shape)


# ---------------------------------------------------------------------------------------------------- per material
def _pick_scheme(rid, schemes):
    """Per-object colour scheme from the object's random id (a plate keeps one paint over its whole surface)."""
    cum = np.cumsum([s[2] for s in schemes])
    cum /= cum[-1]
    k = np.searchsorted(cum, np.clip(rid, 0, 0.9999))
    cols = np.array([s[1] for s in schemes], np.float32)
    return k, cols[k]


def synth(M, maps, res, faction="player", seed=1):
    """Return dict(basecolor uint8 (H,W,3), normal uint8, orm uint8, emissive uint8) for material M."""
    pal = PALETTES[faction]
    F = Feat(maps, res)
    H = W = res
    rng = np.random.default_rng(seed)
    ext, valid = F.ext, F.valid
    n_lo = nz.fbm2((H, W), seed + 1, 3, 4)
    n_mid = nz.fbm2((H, W), seed + 2, 24, 3)
    n_hi = nz.fbm2((H, W), seed + 3, 120, 3)
    n_scr1 = nz.fbm2((H, W), seed + 4, 60, 3, 0.6, aniso=(1.0, 14.0))      # horizontal scratches (stretched along x)
    n_scr2 = nz.fbm2((H, W), seed + 5, 60, 3, 0.6, aniso=(14.0, 1.0))
    streak = F.f3(seed + 6, 1.0, 3, stretch=(2.2, 2.2, 0.07))            # vertical streaks in world space
    blotch = F.f3(seed + 7, 6.0, 4)
    vertical = ss(0.1, 0.8, 1.0 - np.abs(F.nrm[..., 2]))                   # 1 on vertical walls
    cav = np.clip(1.0 - F.ao_s, 0, 1)
    cav = np.clip((cav - 0.12) / 0.6, 0, 1)
    gl_cav = np.clip(1.0 - F.ao_l, 0, 1)
    edge = F.cvx
    wear = pal["wear"]
    chip_noise = ss(0.55 - 0.1 * wear, 0.78 - 0.1 * wear, n_hi * 0.6 + n_mid * 0.5 + n_lo * 0.2)
    chips = np.clip(edge * 1.4 * chip_noise + ss(0.88 - 0.05 * wear, 0.93, n_mid) * 0.5 * (0.3 + edge), 0, 1)
    scr = np.maximum(ss(0.80 - 0.03 * wear, 0.9, n_scr1), ss(0.80 - 0.03 * wear, 0.9, n_scr2)) * (0.35 + 0.65 * (1 - gl_cav))
    rust = np.clip(ss(0.5, 0.78, blotch) * (0.25 + 0.9 * cav + 1.2 * chips) * wear * 0.9, 0, 1)
    grime = np.clip(cav * 0.8 + gl_cav * 0.35 + ss(0.5, 0.85, streak) * vertical * 0.5 * wear + (n_mid - 0.5) * 0.2, 0, 1)
    oil = ss(0.62, 0.82, F.f3(seed + 8, 3.0, 3)) * (0.4 + 0.6 * vertical) * ss(0.3, 0.9, cav + gl_cav * 0.6 + 0.2)
    emis = np.zeros((H, W, 3), np.float32)

    if M == "M_CeramicGray":
        k, base = _pick_scheme(F.rid, pal["ceramic"])
        alb = base.copy()
        alb = alb * (0.88 + 0.24 * n_lo[..., None]) * (0.92 + 0.16 * n_mid[..., None])
        names = [s[0] for s in pal["ceramic"]]
        is_or = np.isin(k, [i for i, n_ in enumerate(names) if n_ in ("orange",)])
        is_red = np.isin(k, [i for i, n_ in enumerate(names) if n_ in ("red", "dark_red", "rust_red")])
        # hazard stripes on a share of orange plates, hazard borders on a share of white/grey ones
        stripe_phase = (F.pos[..., 0] * 0.7 + F.pos[..., 2] * 0.9 + F.pos[..., 1] * 0.5) / 1.4
        stripes = (stripe_phase % 1.0) > 0.5
        hz_plate = is_or & (np.mod(F.rid * 997.0, 1.0) > 0.45)
        alb = np.where((hz_plate & stripes)[..., None], np.array(pal["stripe"], np.float32), alb)
        border = nz.dilate(edge > 0.35, 7) & ~nz.erode(edge > 0.35, 0)
        hz_border = (~is_or) & (np.mod(F.rid * 313.0, 1.0) > 0.86) & border & (np.abs(F.nrm[..., 2]) < 0.9)
        alb = np.where((hz_border & stripes)[..., None], np.array(pal["orange"], np.float32), alb)
        alb = np.where((hz_border & ~stripes)[..., None], np.array(pal["stripe"], np.float32), alb)
        # repainted rectangles (patchwork): a lighter / darker patch on some plates
        patch = ss(0.62, 0.66, F.f3(seed + 9, 9.0, 2)) * (np.mod(F.rid * 71.0, 1.0) > 0.55)
        alb = alb * (1 - patch[..., None] * 0.45) + patch[..., None] * 0.45 * (alb * 1.35 + 0.02)
        stencil_mask = apply_stencils(alb, F.pos, F.nrm, ext, STENCILS_PLAYER if faction == "player" else STENCILS_ENEMY, pal["stencil"], 0.92)
        paint = np.clip(1.0 - chips, 0, 1)
        metal_col = np.array(pal["metal"], np.float32)
        alb = alb * paint[..., None] + metal_col * (1 - paint[..., None]) * (0.7 + 0.5 * n_hi[..., None])
        alb = alb * (1 - 0.5 * grime[..., None]) * (1 - 0.35 * oil[..., None])
        rust_c = np.array(pal["rust"], np.float32) * (0.7 + 0.6 * n_mid[..., None])
        alb = alb * (1 - rust[..., None] * 0.8) + rust_c * rust[..., None] * 0.8
        scr_m = np.clip(scr * (1 - 0.5 * is_red), 0, 1) * 0.6
        alb = alb * (1 - scr_m[..., None]) + metal_col * scr_m[..., None]
        metallic = np.clip(1 - paint, 0, 1) * (1 - rust * 0.7) + scr_m * 0.4
        rough = 0.56 + 0.18 * n_hi - 0.22 * metallic + 0.18 * grime
        rough = np.where(oil > 0.5, 0.18, rough)
        height = -0.9 * nz.blur(1 - paint, 1) + 0.08 * (n_hi - 0.5) + 0.12 * (n_mid - 0.5) - 0.35 * scr_m - 0.2 * rust + 0.25 * stencil_mask * 0.0
        height += 0.12 * np.abs(n_lo - 0.5)
        nstr = 2.2
    elif M == "M_Graphite":
        alb = np.broadcast_to(np.array(pal["graphite"], np.float32), (H, W, 3)).copy() * (0.8 + 0.5 * n_mid[..., None])
        metal_col = np.array(pal["metal"], np.float32)
        wornm = np.clip(edge * 1.2 * chip_noise + scr * 0.5, 0, 1)
        alb = alb * (1 - wornm[..., None]) + metal_col * 0.55 * wornm[..., None]
        alb = alb * (1 - 0.4 * grime[..., None])
        rust_c = np.array(pal["rust"], np.float32) * (0.6 + 0.7 * n_mid[..., None])
        alb = alb * (1 - rust[..., None] * 0.7) + rust_c * rust[..., None] * 0.7
        metallic = np.clip(0.75 + 0.25 * wornm - 0.5 * rust, 0, 1)
        rough = 0.42 + 0.25 * n_hi + 0.25 * grime - 0.2 * wornm
        rough = np.where(oil > 0.45, 0.12, rough)
        height = 0.1 * (n_hi - 0.5) + 0.2 * (n_mid - 0.5) - 0.3 * scr - 0.25 * rust
        nstr = 1.6
    elif M == "M_DarkMetal":
        alb = np.broadcast_to(np.array(pal["dark"], np.float32), (H, W, 3)).copy() * (0.8 + 0.6 * n_mid[..., None])
        wornm = np.clip(edge * 1.1 * chip_noise + scr * 0.4, 0, 1)
        alb = alb * (1 - wornm[..., None]) + np.array(pal["metal"], np.float32) * 0.45 * wornm[..., None]
        soot = np.clip(F.f3(seed + 10, 12.0, 3) * 1.4 - 0.2, 0, 1) * pal["soot"]
        alb = alb * (1 - 0.5 * soot[..., None])
        rust_c = np.array(pal["rust"], np.float32) * (0.5 + 0.8 * n_mid[..., None])
        alb = alb * (1 - rust[..., None] * 0.55) + rust_c * rust[..., None] * 0.55
        metallic = np.clip(0.85 + 0.15 * wornm - 0.5 * rust, 0, 1)
        rough = 0.4 + 0.3 * n_hi + 0.3 * grime
        height = 0.1 * (n_hi - 0.5) + 0.1 * (n_mid - 0.5) - 0.2 * scr
        # bolt-head tile (top strip, left): plain steel with slightly worn rims
        bolt = F.strip & (np.arange(W)[None, :] < 0.3 * W)
        alb = np.where(bolt[..., None], np.array(pal["metal"], np.float32) * (0.35 + 0.35 * n_hi[..., None]), alb)
        metallic = np.where(bolt, 1.0, metallic)
        rough = np.where(bolt, 0.45, rough)
        nstr = 1.4
    elif M == "M_Hydraulic":
        alb = np.broadcast_to(np.array((0.76, 0.78, 0.8), np.float32), (H, W, 3)).copy() * (0.78 + 0.3 * n_mid[..., None])
        alb = alb * (1 - 0.55 * grime[..., None]) * (1 - 0.5 * oil[..., None])
        rust_c = np.array(pal["rust"], np.float32)
        rr = rust * 0.6
        alb = alb * (1 - rr[..., None]) + rust_c * rr[..., None]
        sc = scr * 0.6
        alb = alb * (1 - sc[..., None] * 0.4)
        metallic = np.clip(1.0 - rust * 0.6, 0, 1)
        rough = 0.14 + 0.22 * scr + 0.3 * grime + 0.2 * rust
        rough = np.where(oil > 0.5, 0.35, rough)
        height = 0.06 * (n_hi - 0.5) - 0.3 * scr - 0.2 * rust
        nstr = 1.2
    elif M == "M_AccentOrange":
        stripe_phase = (F.pos[..., 0] * 0.8 + F.pos[..., 2] * 0.9 + F.pos[..., 1] * 0.4) / 1.2
        stripes = (stripe_phase % 1.0) > 0.5
        base = np.array(pal["orange"], np.float32)
        alb = np.where(stripes[..., None] & (np.mod(F.rid * 53.0, 1.0)[..., None] > 0.35), np.array(pal["stripe"], np.float32), base) * (0.85 + 0.3 * n_lo[..., None])
        paint = np.clip(1.0 - chips * 1.1, 0, 1)
        alb = alb * paint[..., None] + np.array(pal["metal"], np.float32) * (1 - paint[..., None]) * 0.8
        alb = alb * (1 - 0.5 * grime[..., None])
        rust_c = np.array(pal["rust"], np.float32)
        alb = alb * (1 - rust[..., None] * 0.7) + rust_c * rust[..., None] * 0.7
        metallic = (1 - paint) * 0.9
        rough = 0.5 + 0.2 * n_hi - 0.2 * metallic
        height = -0.7 * nz.blur(1 - paint, 1) + 0.08 * (n_hi - 0.5) - 0.2 * rust
        nstr = 1.8
    elif M == "M_Rubber":
        alb = np.broadcast_to(np.array(pal["rubber"], np.float32), (H, W, 3)).copy() * (0.7 + 0.8 * n_mid[..., None])
        dust = ss(0.5, 0.8, F.f3(seed + 11, 4.0, 3)) * 0.12
        alb = alb + dust[..., None]
        cracks = ss(0.9, 0.96, np.maximum(n_scr1, n_scr2))
        alb = alb * (1 - 0.5 * cracks[..., None])
        metallic = np.zeros((H, W), np.float32)
        rough = 0.82 + 0.15 * n_hi - 0.2 * oil
        height = 0.2 * (n_hi - 0.5) - 0.5 * cracks
        nstr = 1.6
    elif M == "M_Glass_Sensor":
        alb = np.broadcast_to(np.array((0.015, 0.03, 0.045), np.float32), (H, W, 3)).copy() * (0.8 + 0.5 * n_lo[..., None])
        smudge = ss(0.55, 0.9, n_mid) * 0.5
        alb = alb + smudge[..., None] * 0.02
        metallic = np.zeros((H, W), np.float32)
        rough = 0.06 + 0.3 * smudge + 0.2 * grime
        height = 0.02 * (n_hi - 0.5)
        nstr = 0.5
        emis = np.broadcast_to(np.array(pal["glow"], np.float32), (H, W, 3)) * 0.0
    else:   # M_Emissive_Status
        alb = np.broadcast_to(np.array((0.03, 0.03, 0.032), np.float32), (H, W, 3)).copy() * (0.8 + 0.6 * n_mid[..., None])
        metallic = np.zeros((H, W), np.float32)
        rough = 0.35 + 0.2 * n_hi
        height = 0.02 * (n_hi - 0.5)
        nstr = 0.6
        p = F.pos
        glow = np.array(pal["glow"], np.float32)
        gb = np.array(pal["glow_back"], np.float32)
        lamp = np.array(pal["lamp"], np.float32)
        chest = (np.abs(p[..., 0]) < 6) & (p[..., 1] < -5) & (p[..., 2] > 50) & (p[..., 2] < 64)
        back = (p[..., 1] > 8) & (p[..., 2] > 50) & (p[..., 2] < 66)
        head = (p[..., 2] > 70.5) & (p[..., 1] < -6.5) & (p[..., 2] < 76)
        lamps = (np.abs(p[..., 0]) > 7.5) & (np.abs(p[..., 0]) < 11) & (p[..., 2] > 68) & (p[..., 2] < 72.5) & (p[..., 1] < -6)
        col = np.where(chest[..., None], glow, np.where(back[..., None], gb, np.where(head[..., None], glow * 0.9 + 0.1, np.where(lamps[..., None], lamp, np.array((1.0, 0.55, 0.15), np.float32)))))
        pulse = 0.75 + 0.5 * n_mid
        emis = col * pulse[..., None] * (1 - 0.3 * grime[..., None])
        alb = np.where(((chest | back | head | lamps))[..., None], col * 0.5, alb)

    # fill the area outside the islands with the material's mean colour so that mip bleeding stays sane
    mean = alb[ext].mean(0) if ext.any() else np.zeros(3, np.float32)
    alb = np.where(ext[..., None], alb, mean)
    ao = np.clip(F.ao_s * 0.55 + F.ao_l * 0.45, 0, 1)
    ao = np.where(ext, ao, 1.0)
    height = np.where(ext, height, 0.0)
    nrm_t = nz.height_to_normal(height.astype(np.float32), nstr * (res / 2048.0) ** -1 * 6.0 * 0.5)
    orm = np.stack([ao, np.clip(rough, 0.04, 1.0), np.clip(metallic, 0, 1)], -1)
    to8 = lambda a: np.clip(a * 255.0 + 0.5, 0, 255).astype(np.uint8)
    return dict(basecolor=to8(np.clip(alb, 0, 1)), normal=to8(nrm_t), orm=to8(orm), emissive=to8(np.clip(emis, 0, 1)))


def save_set(out_dir, prefix, mat, tex):
    from PIL import Image
    os.makedirs(out_dir, exist_ok=True)
    names = {"basecolor": "BaseColor", "normal": "Normal", "orm": "ORM", "emissive": "Emissive"}
    files = {}
    for k, arr in tex.items():
        fn = "T_%s_%s_%s.png" % (prefix, mat.replace("M_", ""), names[k])
        Image.fromarray(arr).save(os.path.join(out_dir, fn), optimize=False, compress_level=6)
        files[k] = fn
    return files
