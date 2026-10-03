"""Decals (RGBA, straight alpha, alpha = 0 on the border). Kinds: albedo decals (RGB colour + A), normal decals (RGB tangent normal,
A = mask), each saved with an optional roughness map. Sizes are fractions of the decal canvas so any resolution works."""
import math

import numpy as np
from PIL import Image, ImageDraw

from . import noise as nz
from . import maps

F32 = np.float32


def edge_fade(n, margin=0.06):
    y, x = np.meshgrid((np.arange(n) + 0.5) / n, (np.arange(n) + 0.5) / n, indexing="ij")
    d = np.minimum(np.minimum(x, 1 - x), np.minimum(y, 1 - y))
    f = nz.smoothstep(d, 0.0, margin)
    f[0, :] = f[-1, :] = f[:, 0] = f[:, -1] = 0
    return f.astype(F32)


class Decal:
    def __init__(self, name, rgb, alpha, rough=None, kind="albedo", note=""):
        self.name, self.kind, self.note = name, kind, note
        n = alpha.shape[0]
        self.alpha = np.clip(alpha * edge_fade(n), 0, 1).astype(F32)
        self.rgb = np.clip(rgb, 0, 1).astype(F32)
        self.rough = rough

    def write(self, out_dir):
        d = out_dir
        rgba = np.concatenate([self.rgb, self.alpha[..., None]], -1)
        files = {"RGBA": {"file": "out/decals/%s.png" % self.name, "colorspace": "sRGB" if self.kind == "albedo" else "Linear"}}
        maps.save_png("%s/%s.png" % (d, self.name), rgba)
        if self.rough is not None:
            maps.save_png("%s/%s_Roughness.png" % (d, self.name), np.clip(self.rough, 0, 1))
            files["Roughness"] = {"file": "out/decals/%s_Roughness.png" % self.name, "colorspace": "Linear"}
        return files


def _rng(name):
    return nz.rng_for("decal", name)


def scratches(n):
    out = []
    for i, (cnt, ln, wd) in enumerate([(14, (0.3, 0.9), (1.0, 2.0)), (60, (0.05, 0.3), (0.6, 1.4)), (6, (0.2, 0.7), (2.5, 5.0)), (120, (0.02, 0.15), (0.6, 1.0))]):
        rng = _rng("scratch%d" % i)
        s = nz.lines(n * 2, rng, cnt, ln, (wd[0] * n / 512 * 2, wd[1] * n / 512 * 2), bright=(0.4, 1.0), curvy=0.2 + 0.1 * i)
        s = np.asarray(Image.fromarray((s * 255).astype(np.uint8)).resize((n, n), Image.LANCZOS), dtype=F32) / 255.0
        a = np.clip(s * 1.4, 0, 1)
        rgb = np.stack([0.62 + 0.2 * s, 0.63 + 0.2 * s, 0.66 + 0.2 * s], -1)
        out.append(Decal("scratch_%02d" % (i + 1), rgb, a, rough=0.25 + 0 * a, note="bright bare-metal scratches"))
    return out


def dents(n):
    out = []
    for i in range(4):
        rng = _rng("dent%d" % i)
        y, x = np.meshgrid((np.arange(n) + 0.5) / n, (np.arange(n) + 0.5) / n, indexing="ij")
        h = np.zeros((n, n), F32)
        count = [1, 3, 5, 2][i]
        for _ in range(count):
            cx, cy = (0.5 if count == 1 else rng.uniform(0.25, 0.75)), (0.5 if count == 1 else rng.uniform(0.25, 0.75))
            r = rng.uniform(0.12, 0.3) if count > 1 else 0.34
            rr = np.sqrt((x - cx) ** 2 + (y - cy) ** 2) / r
            h -= (np.clip(1 - rr ** 2, 0, 1) ** 1.5) * rng.uniform(0.5, 1.0) * (0.6 if i == 3 else 1.0)
            h += 0.25 * np.exp(-((rr - 1.05) / 0.12) ** 2)      # raised rim
        mask = np.clip(nz.blur((np.abs(h) > 0.03).astype(F32), 3.0) * 1.5, 0, 1)
        h += 0.02 * (nz.fbm(n, rng, 1.8, 2, 40) - 0.5) * mask            # surface noise only inside the dent
        nrm = maps.encode_normal(maps.normal_from_height(nz.blur((h - h.min()) / max(h.max() - h.min(), 1e-6), 1.5), 3.0))
        out.append(Decal("dent_%02d_normal" % (i + 1), nrm, mask, kind="normal", note="tangent-space normal in RGB, alpha = mask; blend as DBuffer normal"))
    return out


def burns(n):
    out = []
    for i in range(4):
        rng = _rng("burn%d" % i)
        y, x = np.meshgrid((np.arange(n) + 0.5) / n, (np.arange(n) + 0.5) / n, indexing="ij")
        r = np.sqrt((x - 0.5) ** 2 + (y - 0.5) ** 2) / (0.42 - 0.03 * i)
        nzr = nz.fbm(n, rng, 2.0, 2, 40)
        core = np.clip(1 - r + (nzr - 0.5) * 0.9, 0, 1)
        streak = nz.fbm(n, rng, 1.6, 1, 14, aniso=(0.3, 1.0)) if i % 2 else 0 * core
        a = np.clip(core ** 0.7 * 1.3 + streak * 0.2 * core, 0, 1)
        t = nz.fbm(n, rng, 1.2, 8, 120)
        rgb = nz.ramp(a * 0.5 + t * 0.5, [(0, (0.01, 0.01, 0.01)), (0.6, (0.04, 0.035, 0.03)), (1, (0.12, 0.09, 0.06))])
        rgb[..., 2] += 0.0
        # rainbow oxide fringe in the transition band
        fringe = np.exp(-((r - 0.78) / 0.07) ** 2)
        rgb = rgb + fringe[..., None] * np.array([0.12, 0.05, 0.0], F32)
        out.append(Decal("burn_%02d" % (i + 1), rgb, a * 0.95, rough=0.8 + 0 * a, note="soot / scorch"))
    return out


def fluids(n):
    out = []
    for i, (colr, sheen) in enumerate([((0.03, 0.025, 0.02), 0.2), ((0.04, 0.12, 0.1), 0.15), ((0.02, 0.02, 0.025), 0.1), ((0.1, 0.06, 0.02), 0.25)]):
        rng = _rng("fluid%d" % i)
        y, x = np.meshgrid((np.arange(n) + 0.5) / n, (np.arange(n) + 0.5) / n, indexing="ij")
        a = np.zeros((n, n), F32)
        for _ in range(3 + i):
            cx = rng.uniform(0.2, 0.8)
            w = rng.uniform(0.01, 0.035)
            top = rng.uniform(0.1, 0.4)
            ln = rng.uniform(0.3, 0.75)
            wob = 0.01 * np.sin(y * rng.uniform(8, 20) + rng.uniform(0, 6))
            stripe = np.exp(-(((x - cx - wob) / w) ** 2)) * nz.smoothstep(y, top, top + 0.05) * (1 - nz.smoothstep(y, top + ln, top + ln + 0.1))
            a = np.maximum(a, stripe)
        pool = np.clip(1 - np.sqrt((x - 0.5) ** 2 + (y - 0.82) ** 2) / (0.12 + 0.03 * i), 0, 1)
        pool = pool ** 0.6 * nz.fbm(n, rng, 1.5, 3, 30)
        a = np.clip(np.maximum(a * 0.8, pool * 1.2), 0, 1)
        rgb = np.broadcast_to(np.array(colr, F32), (n, n, 3)).copy()
        out.append(Decal("fluid_%02d" % (i + 1), rgb, a * 0.85, rough=0.08 + 0 * a, note=["oil", "coolant (green-teal)", "hydraulic fluid", "rusty water"][i]))
    return out


def salt_streaks(n):
    out = []
    for i in range(4):
        rng = _rng("salt%d" % i)
        y, x = np.meshgrid((np.arange(n) + 0.5) / n, (np.arange(n) + 0.5) / n, indexing="ij")
        base = nz.fbm(n, rng, 1.2, 4, 90, aniso=(0.5 + i * 0.6, 14.0))
        thresh = 0.5 + 0.04 * i
        a = nz.smoothstep(base, thresh, thresh + 0.2) * nz.smoothstep(y, 0.0, 0.25 + 0.2 * (3 - i) / 3)
        crust = nz.fbm(n, rng, 0.8, 30, n / 2)
        rgb = np.stack([0.7 + 0.2 * crust, 0.72 + 0.2 * crust, 0.72 + 0.2 * crust], -1)
        out.append(Decal("salt_streak_%02d" % (i + 1), rgb, a * (0.35 + 0.1 * i), rough=0.9 + 0 * a, note="salt crust and rain streaks, run top to bottom"))
    return out


def _shape_canvas(n):
    im = Image.new("L", (n * 2, n * 2), 0)
    return im, ImageDraw.Draw(im)


def _finish_shape(im, n):
    return np.asarray(im.resize((n, n), Image.LANCZOS), dtype=F32) / 255.0


def marks(n):
    """Technical marks without readable text: arrows, chevrons, ring, crosshair, triangle, double bar (all orange/white)."""
    out = []
    N = n * 2
    c = N // 2
    shapes = {}
    im, d = _shape_canvas(n)
    d.polygon([(c, N * 0.15), (N * 0.78, N * 0.55), (N * 0.6, N * 0.55), (N * 0.6, N * 0.85), (N * 0.4, N * 0.85), (N * 0.4, N * 0.55), (N * 0.22, N * 0.55)], fill=255)
    shapes["arrow_up"] = im
    im, d = _shape_canvas(n)
    for k in range(3):
        y0 = N * (0.2 + 0.2 * k)
        d.polygon([(N * 0.2, y0 + N * 0.12), (c, y0), (N * 0.8, y0 + N * 0.12), (N * 0.8, y0 + N * 0.2), (c, y0 + N * 0.08), (N * 0.2, y0 + N * 0.2)], fill=255)
    shapes["chevrons"] = im
    im, d = _shape_canvas(n)
    d.ellipse([N * 0.15, N * 0.15, N * 0.85, N * 0.85], outline=255, width=int(N * 0.06))
    d.ellipse([N * 0.4, N * 0.4, N * 0.6, N * 0.6], fill=255)
    shapes["ring_dot"] = im
    im, d = _shape_canvas(n)
    d.rectangle([N * 0.46, N * 0.1, N * 0.54, N * 0.9], fill=255)
    d.rectangle([N * 0.1, N * 0.46, N * 0.9, N * 0.54], fill=255)
    d.ellipse([N * 0.3, N * 0.3, N * 0.7, N * 0.7], outline=255, width=int(N * 0.04))
    shapes["crosshair"] = im
    im, d = _shape_canvas(n)
    d.polygon([(c, N * 0.12), (N * 0.88, N * 0.82), (N * 0.12, N * 0.82)], outline=255, width=int(N * 0.07))
    d.rectangle([N * 0.47, N * 0.38, N * 0.53, N * 0.62], fill=255)
    d.ellipse([N * 0.47, N * 0.68, N * 0.53, N * 0.74], fill=255)
    shapes["warning_triangle"] = im
    im, d = _shape_canvas(n)
    for k in range(5):
        d.rectangle([N * (0.12 + 0.16 * k), N * 0.3, N * (0.12 + 0.16 * k + 0.08), N * 0.7], fill=255)
    shapes["tick_bars"] = im
    for i, (name, im) in enumerate(shapes.items()):
        a = _finish_shape(im, n)
        col = (0.9, 0.38, 0.05) if i % 2 == 0 else (0.82, 0.82, 0.8)
        rng = _rng("mark_" + name)
        worn = 1 - 0.5 * nz.smoothstep(nz.fbm(n, rng, 2.0, 4, 60), 0.5, 0.85)
        out.append(Decal("mark_" + name, np.broadcast_to(np.array(col, F32), (n, n, 3)).copy(), a * worn, rough=0.6 + 0 * a, note="marking without text"))
    return out


def hazard_stripes(n):
    out = []
    for i, (w, ang) in enumerate([(0.1, 1.0), (0.06, 1.0), (0.14, -1.0)]):
        y, x = np.meshgrid((np.arange(n) + 0.5) / n, (np.arange(n) + 0.5) / n, indexing="ij")
        t = ((x + ang * y) / w) % 2.0
        st = (t < 1.0).astype(F32)
        st = nz.blur(st, 0.8)
        rng = _rng("hazard%d" % i)
        wear = nz.smoothstep(nz.fbm(n, rng, 2.0, 3, 80), 0.55, 0.85)
        a = st * (1 - 0.6 * wear)
        out.append(Decal("hazard_stripes_%02d" % (i + 1), np.broadcast_to(np.array((0.9, 0.38, 0.05), F32), (n, n, 3)).copy(), a, rough=0.65 + 0 * a, note="orange marking stripes"))
    return out


def panel_seams(n):
    out = []
    for i in range(3):
        rng = _rng("seam%d" % i)
        y, x = np.meshgrid((np.arange(n) + 0.5) / n, (np.arange(n) + 0.5) / n, indexing="ij")
        h = np.zeros((n, n), F32)
        if i == 0:
            h -= np.exp(-(((y - 0.5) / 0.012) ** 2))
        elif i == 1:
            h -= np.exp(-(((y - 0.5) / 0.012) ** 2)) + (np.exp(-(((x - 0.5) / 0.012) ** 2)))
        else:
            h -= np.exp(-(((np.abs(x - 0.5) + np.abs(y - 0.5) - 0.3) / 0.012) ** 2))
        for k in range(8):   # rivets along the seam
            t = 0.1 + 0.8 * k / 7
            cx, cy = (t, 0.5 + 0.035) if i == 0 else ((t, 0.5 + 0.035) if i == 1 else (0.5, t))
            h += 0.5 * np.exp(-(((x - cx) ** 2 + (y - cy) ** 2) / 0.0002))
        a = np.clip(np.abs(h) * 3, 0, 1)
        nrm = maps.encode_normal(maps.normal_from_height(nz.blur((h - h.min()) / max(h.max() - h.min(), 1e-6), 0.8), 2.5))
        out.append(Decal("panel_seam_%02d_normal" % (i + 1), nrm, np.clip(nz.blur(a, 2.0) * 2.0, 0, 1), kind="normal", note="panel seam with rivets"))
    return out


def vents(n):
    out = []
    for i, (cols, rows) in enumerate([(1, 8), (4, 6), (6, 3)]):
        y, x = np.meshgrid((np.arange(n) + 0.5) / n, (np.arange(n) + 0.5) / n, indexing="ij")
        a = np.zeros((n, n), F32)
        for r in range(rows):
            for c in range(cols):
                x0 = 0.12 + 0.76 * c / cols + 0.01
                x1 = 0.12 + 0.76 * (c + 1) / cols - 0.01
                y0 = 0.15 + 0.7 * r / rows + 0.1 / rows
                y1 = 0.15 + 0.7 * (r + 1) / rows - 0.1 / rows
                a = np.maximum(a, ((x > x0) & (x < x1) & (y > y0) & (y < y1)).astype(F32))
        frame = ((x > 0.08) & (x < 0.92) & (y > 0.11) & (y < 0.89)).astype(F32) - ((x > 0.11) & (x < 0.89) & (y > 0.13) & (y < 0.87)).astype(F32)
        a = nz.blur(a, 1.0)
        out.append(Decal("vent_grille_%02d" % (i + 1), np.stack([0.02 + 0.5 * frame] * 3, -1), np.clip(a * 0.95 + frame, 0, 1), rough=0.5 + 0 * a, note="dark vent slots in a frame"))
    return out


def plates(n):
    """Blank number plates (no characters): frame, panel, two screws, grime."""
    out = []
    for i, (bg, fg) in enumerate([((0.78, 0.78, 0.76), (0.1, 0.1, 0.1)), ((0.85, 0.65, 0.1), (0.1, 0.1, 0.1)), ((0.12, 0.2, 0.5), (0.9, 0.9, 0.9))]):
        rng = _rng("plate%d" % i)
        y, x = np.meshgrid((np.arange(n) + 0.5) / n, (np.arange(n) + 0.5) / n, indexing="ij")
        inside = ((x > 0.08) & (x < 0.92) & (y > 0.3) & (y < 0.7)).astype(F32)
        border = inside - ((x > 0.1) & (x < 0.9) & (y > 0.32) & (y < 0.68)).astype(F32)
        grime = nz.fbm(n, rng, 2.2, 3, 80)
        rgb = np.broadcast_to(np.array(bg, F32), (n, n, 3)).copy() * (0.8 + 0.25 * grime[..., None])
        rgb = rgb * (1 - border[..., None]) + np.array(fg, F32) * border[..., None]
        for sx in (0.14, 0.86):
            m = np.clip(1 - np.sqrt((x - sx) ** 2 + (y - 0.5) ** 2) / 0.018, 0, 1)
            rgb = rgb * (1 - m[..., None]) + np.array((0.3, 0.3, 0.3), F32) * m[..., None]
        out.append(Decal("plate_blank_%02d" % (i + 1), rgb, nz.blur(inside, 1.0), rough=0.5 + 0 * inside, note="blank plate, no characters"))
    return out


def all_decals(n):
    d = []
    for f in (scratches, dents, burns, fluids, salt_streaks, marks, hazard_stripes, panel_seams, vents, plates):
        d += f(n)
    return d
