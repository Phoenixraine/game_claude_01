"""VFX flipbooks: 8 x 8 = 64 frames, RGBA premultiplied alpha. Animation comes from simulation (semi-Lagrangian advection of a
density field in a curl-noise flow with buoyancy, particle integration with gravity, expanding shells with noise erosion), not from
rotating one image. `f` = frame size in pixels (256 at full quality). Every generator returns (64, f, f, 4) float32."""
import math

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

from . import noise as nz

F32 = np.float32
T = 64


def _coords(f):
    yy, xx = np.meshgrid(np.arange(f, dtype=F32), np.arange(f, dtype=F32), indexing="ij")
    return yy, xx


def _flow(f, rng, scale=6, strength=1.0):
    """Divergence-free-ish velocity field from the curl of a smooth noise potential (periodic, fine for a 256 px frame)."""
    p = nz.fbm(f, rng, 2.6, 1, scale).astype(F32)
    dy, dx = np.gradient(p)
    return (dy * f * strength).astype(F32), (-dx * f * strength).astype(F32)      # (vy, vx) in px per unit


def _advect(d, vy, vx, yy, xx, dt):
    return ndimage.map_coordinates(d, [yy - vy * dt, xx - vx * dt], order=1, mode="constant", cval=0.0).astype(F32)


def _premul(rgb, a):
    a = np.clip(a, 0, 1).astype(F32)
    return np.concatenate([np.clip(rgb, 0, 1) * a[..., None], a[..., None]], -1).astype(F32)


def _fade_ends(a, t, fi=3, fo=10):
    k = min(1.0, (t + 1) / fi) * min(1.0, (T - t) / fo)
    return a * k


def smoke(f, name, dark=True, rise=1.0, width=0.12, spread=1.0, heat=0.0, seed=0):
    rng = nz.rng_for("vfx", name, seed)
    yy, xx = _coords(f)
    vy0, vx0 = _flow(f, rng, 5, 0.9 * spread)
    vy1, vx1 = _flow(f, rng, 9, 0.5 * spread)
    d = np.zeros((f, f), F32)
    detail = nz.fbm(f, rng, 1.3, 4, f / 3)
    frames = np.zeros((T, f, f, 4), F32)
    src = np.exp(-(((xx - f / 2) / (f * width)) ** 2 + ((yy - f * 0.8) / (f * 0.07)) ** 2))
    for t in range(T):
        if t < T * 0.55:
            d = d + src * (0.7 + 0.3 * math.sin(t * 0.3)) * 1.1 * (1 - t / (T * 0.55) * 0.5)
        sw = 1.0 + 0.4 * math.sin(t * 0.17)
        vy = vy0 * sw + vy1 * (1 - sw * 0.5) - rise * f * 0.012 * (1.0 + (1 - yy / f))
        vx = vx0 * sw * 0.8 + vx1
        d = _advect(d, vy, vx, yy, xx, 1.0 + 0.5 * spread)
        d = ndimage.gaussian_filter(d, 0.6) * 0.985
        det = np.roll(detail, (t * 2, t), (0, 1))
        a = nz.smoothstep(d * 2.4 * (0.45 + 1.0 * det) - 0.1, 0.0, 0.85) * 0.9
        m = f * 0.06
        a = a * nz.smoothstep(xx, 1, m) * nz.smoothstep(f - 1 - xx, 1, m) * nz.smoothstep(yy, 1, m) * nz.smoothstep(f - 1 - yy, 1, m)
        light = np.clip(0.5 + (np.gradient(d, axis=0) + 0.5 * np.gradient(d, axis=1)) * 6, 0.2, 1.0)
        if dark:
            base = np.stack([0.05 + 0.1 * light] * 3, -1)
            if heat:
                glow = np.clip(d * heat * (1 - yy / f), 0, 1)[..., None]
                base = base + glow * np.array([0.7, 0.25, 0.05], F32)
        else:
            base = np.stack([0.55 + 0.4 * light, 0.56 + 0.4 * light, 0.58 + 0.4 * light], -1)
        frames[t] = _premul(base, _fade_ends(a, t))
    return frames


def collapse_dust(f):
    """Wide billowing dust cloud rolling outward from the base."""
    rng = nz.rng_for("vfx", "dust")
    yy, xx = _coords(f)
    d = np.zeros((f, f), F32)
    detail = nz.fbm(f, rng, 1.6, 3, f / 3)
    vy0, vx0 = _flow(f, rng, 4, 1.2)
    frames = np.zeros((T, f, f, 4), F32)
    for t in range(T):
        if t < 44:
            ring = np.exp(-(((xx - f / 2) / (f * (0.08 + 0.006 * t))) ** 2 + ((yy - f * 0.86) / (f * 0.06)) ** 2))
            d += ring * 0.9 * (1 - t / 52.0)
        vx = vx0 * 0.6 + np.sign(xx - f / 2) * np.exp(-np.abs(xx - f / 2) / (f * 0.5)) * f * 0.006 * max(0.0, 1 - t / 60)
        vy = vy0 * 0.8 - (1 - yy / f) * f * 0.008
        d = _advect(d, vy, vx, yy, xx, 1.2)
        d = ndimage.gaussian_filter(d, 0.8) * 0.996
        a = np.clip(d * (0.7 + 0.6 * np.roll(detail, (t, 2 * t), (0, 1))) * 1.6, 0, 1)
        m = f * 0.1
        a *= nz.smoothstep(xx, 1, m) * nz.smoothstep(f - 1 - xx, 1, m) * nz.smoothstep(yy, 1, m) * nz.smoothstep(f - 1 - yy, 1, m)
        shade = 0.45 + 0.25 * nz.fbm(f, rng, 2.0, 2, 20)
        rgb = np.stack([shade * 1.02, shade * 0.97, shade * 0.9], -1)
        frames[t] = _premul(rgb, _fade_ends(a, t, 2, 14))
    return frames


def steam(f):
    fr = smoke(f, "steam", dark=False, rise=2.2, width=0.05, spread=0.7)
    fr[..., :3] *= 1.0
    return fr


def _glow(img, s):
    return ndimage.gaussian_filter(img, s)


def sparks(f):
    rng = nz.rng_for("vfx", "sparks")
    n = 70
    pos = np.tile(np.array([f * 0.5, f * 0.6], F32), (n, 1)) + rng.normal(0, 3, (n, 2)).astype(F32)
    ang = rng.uniform(-math.pi, 0, n)
    spd = rng.uniform(1.2, 4.2, n) * f / 256 * 2.2
    vel = np.stack([np.cos(ang) * spd * 1.2, np.sin(ang) * spd - 0.8], -1).astype(F32)
    life = rng.uniform(26, 62, n)
    birth = rng.uniform(0, 14, n)
    frames = np.zeros((T, f, f, 4), F32)
    p = pos.copy()
    v = vel.copy()
    for t in range(T):
        canvas = Image.new("L", (f * 2, f * 2), 0)
        d = ImageDraw.Draw(canvas)
        for i in range(n):
            if t < birth[i] or t > birth[i] + life[i]:
                continue
            q0 = p[i].copy()
            v[i, 1] += 0.09 * f / 256 * 2.0
            v[i] *= 0.985
            p[i] += v[i]
            age = (t - birth[i]) / life[i]
            br = int(255 * (1 - age) ** 0.8)
            d.line([(q0[0] * 2, q0[1] * 2), (p[i][0] * 2, p[i][1] * 2)], fill=br, width=max(1, int(2 * f / 256)))
        im = np.asarray(canvas.resize((f, f), Image.LANCZOS), dtype=F32) / 255.0
        hot = np.clip(im * 1.5, 0, 1)
        glow = _glow(im, 2.0 * f / 256) * 1.5
        a = np.clip(hot + glow * 0.5, 0, 1)
        rgb = np.stack([np.ones_like(a), 0.6 + 0.35 * hot, 0.15 + 0.6 * hot ** 3], -1)
        frames[t] = _premul(rgb, a)
    return frames


def water_splash(f, impact=True):
    """Impact crown (droplets on parabolas + a central column) or a broad splash."""
    rng = nz.rng_for("vfx", "splash", impact)
    n = 160 if impact else 110
    ang = rng.uniform(0.15, math.pi - 0.15, n)
    spd = rng.uniform(0.8, 3.4 if impact else 2.4, n) * f / 256 * 2.5
    vx = np.cos(ang) * spd * (0.8 if impact else 1.4)
    vy = -np.sin(ang) * spd * (1.6 if impact else 0.9)
    start = np.stack([f / 2 + rng.normal(0, f * 0.03, n), np.full(n, f * 0.82)], -1)
    size = rng.uniform(1.0, 3.5, n) * f / 256
    frames = np.zeros((T, f, f, 4), F32)
    yy, xx = _coords(f)
    for t in range(T):
        a = np.zeros((f, f), F32)
        canvas = Image.new("L", (f * 2, f * 2), 0)
        dr = ImageDraw.Draw(canvas)
        for i in range(n):
            tt = t * 0.9
            x = start[i, 0] + vx[i] * tt
            y = start[i, 1] + vy[i] * tt + 0.055 * f / 256 * 2.2 * tt * tt
            if y > f * 0.9 or not (0 <= x < f):
                continue
            r = size[i] * (1 - t / (T * 1.3))
            dr.ellipse([(x - r) * 2, (y - r) * 2, (x + r) * 2, (y + r) * 2], fill=int(255 * (1 - t / T) ** 0.7))
        a += np.asarray(canvas.resize((f, f), Image.LANCZOS), dtype=F32) / 255.0
        if impact:
            col = np.exp(-(((xx - f / 2) / (f * 0.045 * (1 + 0.02 * t))) ** 2)) * nz.smoothstep(yy, f * (0.82 - 0.0095 * min(t, 24) * 2.2), f * 0.82) \
                * (yy < f * 0.84) * max(0.0, 1 - t / 34.0)
            a = np.maximum(a, col * 0.8)
        # rising mist
        mist = nz.fbm(f, rng, 2.2, 3, 30)
        m = np.exp(-(((xx - f / 2) / (f * 0.25)) ** 2 + ((yy - f * 0.75) / (f * 0.14)) ** 2)) * mist * max(0.0, 1 - t / 40.0) * 0.5
        a = np.clip(a + m, 0, 1)
        shade = 0.82 + 0.15 * (1 - yy / f)
        rgb = np.stack([shade * 0.88, shade * 0.95, shade], -1)
        frames[t] = _premul(rgb, a)
    return frames


def fire(f):
    rng = nz.rng_for("vfx", "fire")
    yy, xx = _coords(f)
    d = np.zeros((f, f), F32)
    vy0, vx0 = _flow(f, rng, 7, 0.8)
    detail = nz.fbm(f, rng, 1.5, 3, f / 3)
    frames = np.zeros((T, f, f, 4), F32)
    smoke_d = np.zeros((f, f), F32)
    for t in range(T):
        src = np.exp(-(((xx - f / 2) / (f * 0.15)) ** 2 + ((yy - f * 0.82) / (f * 0.06)) ** 2)) * (1.0 + 0.3 * math.sin(t * 0.9))
        d = np.maximum(d * 0.97, src)
        d = _advect(d, vy0 * 0.6 - f * 0.03, vx0, yy, xx, 1.0)
        d = ndimage.gaussian_filter(d, 0.7) * 0.975
        smoke_d = _advect(smoke_d + d * 0.2, vy0 * 0.7 - f * 0.012, vx0, yy, xx, 1.0) * 0.99
        fl = np.clip(d * (0.7 + 0.8 * np.roll(detail, (0, t * 2), (0, 1))), 0, 1)
        temp = nz.ramp(np.clip(fl * 1.3, 0, 1), [(0, (0.0, 0.0, 0.0)), (0.3, (0.55, 0.06, 0.02)), (0.6, (1.0, 0.45, 0.05)), (0.85, (1.0, 0.8, 0.3)), (1, (1.0, 1.0, 0.85))])
        sm = np.clip(smoke_d * 2.0, 0, 0.7)
        a_f = np.clip(fl * 2.0, 0, 1)
        a = np.clip(a_f + sm * (1 - a_f), 0, 1)
        rgb = (temp * a_f[..., None] + np.array([0.06, 0.06, 0.065], F32) * (sm * (1 - a_f))[..., None]) / np.maximum(a, 1e-3)[..., None]
        a = a * nz.smoothstep(xx, 2, 10) * nz.smoothstep(f - 1 - xx, 2, 10) * nz.smoothstep(yy, 2, 10) * nz.smoothstep(f - 1 - yy, 2, 10)
        frames[t] = _premul(rgb, _fade_ends(a, t, 2, 8))
    return frames


def electric_arc(f):
    rng = nz.rng_for("vfx", "arc")
    frames = np.zeros((T, f, f, 4), F32)
    for t in range(T):
        canvas = Image.new("L", (f * 2, f * 2), 0)
        d = ImageDraw.Draw(canvas)
        r = np.random.default_rng(nz.rng_for("arcframe", t).integers(1 << 30))
        flash = 1.0 if (t % 7) < 5 else 0.25
        def bolt(x0, y0, x1, y1, depth, width, br):
            pts = [(x0, y0)]
            segs = 14
            for k in range(1, segs):
                tt = k / segs
                jit = (1 - abs(2 * tt - 1) * 0.3) * f * 0.045
                pts.append((x0 + (x1 - x0) * tt + r.normal(0, jit), y0 + (y1 - y0) * tt + r.normal(0, jit * 0.5)))
            pts.append((x1, y1))
            d.line([(p[0] * 2, p[1] * 2) for p in pts], fill=int(255 * br), width=max(1, int(width * 2 * f / 256)))
            if depth > 0:
                for _ in range(r.integers(1, 3)):
                    k = r.integers(3, segs - 3)
                    ang = r.normal(0, 0.9)
                    L = f * r.uniform(0.1, 0.25)
                    bolt(pts[k][0], pts[k][1], pts[k][0] + math.sin(ang) * L, pts[k][1] + math.cos(ang) * L * 0.8, depth - 1, width * 0.6, br * 0.7)
        if t < 60:
            bolt(f * 0.5 + r.normal(0, 4), f * 0.08, f * 0.5 + r.normal(0, 6), f * 0.92, 1, 2.2, flash)
        im = np.asarray(canvas.resize((f, f), Image.LANCZOS), dtype=F32) / 255.0
        glow = ndimage.gaussian_filter(im, 3.0 * f / 256) * 2.0 + ndimage.gaussian_filter(im, 9.0 * f / 256) * 1.2
        a = np.clip(im * 1.5 + glow * 0.6, 0, 1)
        core = np.clip(im * 2, 0, 1)
        rgb = np.stack([0.4 + 0.6 * core, 0.6 + 0.4 * core, np.ones_like(a)], -1)
        frames[t] = _premul(rgb, a)
    return frames


def glass_shards(f):
    rng = nz.rng_for("vfx", "shards")
    n = 46
    pos = np.tile([f / 2, f / 2], (n, 1)).astype(F32) + rng.normal(0, f * 0.03, (n, 2)).astype(F32)
    ang = rng.uniform(0, 2 * math.pi, n)
    spd = rng.uniform(0.6, 3.6, n) * f / 256 * 2
    vel = np.stack([np.cos(ang) * spd, np.sin(ang) * spd - 0.8], -1)
    rot = rng.uniform(0, 6.28, n)
    spin = rng.normal(0, 0.25, n)
    size = rng.uniform(3, 12, n) * f / 256
    tri = rng.uniform(0.4, 1.0, (n, 3))
    frames = np.zeros((T, f, f, 4), F32)
    p = pos.copy()
    v = vel.copy()
    for t in range(T):
        canvas = Image.new("L", (f * 2, f * 2), 0)
        edge = Image.new("L", (f * 2, f * 2), 0)
        d, de = ImageDraw.Draw(canvas), ImageDraw.Draw(edge)
        for i in range(n):
            v[i, 1] += 0.06 * f / 256 * 2
            p[i] += v[i]
            rot[i] += spin[i]
            life = 1 - t / (T + 8)
            pts = []
            for k in range(3):
                a = rot[i] + k * 2.1 + tri[i, k]
                pts.append(((p[i][0] + math.cos(a) * size[i] * tri[i, k]) * 2, (p[i][1] + math.sin(a) * size[i] * tri[i, k]) * 2))
            d.polygon(pts, fill=int(255 * 0.55 * life))
            de.line(pts + [pts[0]], fill=int(255 * life), width=max(1, int(f / 128)))
        a = np.asarray(canvas.resize((f, f), Image.LANCZOS), dtype=F32) / 255.0
        e = np.asarray(edge.resize((f, f), Image.LANCZOS), dtype=F32) / 255.0
        al = np.clip(a + e * 0.9, 0, 1)
        rgb = np.stack([0.75 + 0.25 * e, 0.88 + 0.12 * e, 0.95 + 0.05 * e], -1)
        frames[t] = _premul(rgb, al)
    return frames


def missile_explosion(f):
    """Fireball + shock ring + debris, ends in a low dark cloud (no mushroom)."""
    rng = nz.rng_for("vfx", "missile")
    yy, xx = _coords(f)
    detail = nz.fbm(f, rng, 1.6, 2, f / 4)
    detail2 = nz.fbm(f, rng, 2.2, 1, 12)
    frames = np.zeros((T, f, f, 4), F32)
    cx, cy = f / 2, f * 0.62
    r_d = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
    dn = np.random.default_rng(3)
    debris = [(dn.uniform(0, 6.28), dn.uniform(0.8, 2.6)) for _ in range(40)]
    smoke_d = np.zeros((f, f), F32)
    vy0, vx0 = _flow(f, rng, 5, 0.8)
    for t in range(T):
        R = f * 0.38 * (1 - math.exp(-t / 7.0)) + f * 0.02
        edge = R * (1 + 0.35 * (np.roll(detail, (t, -t), (0, 1)) - 0.5))
        ball = np.clip(1 - r_d / np.maximum(edge, 1), 0, 1) ** 0.6
        cool = np.clip(t / 38.0, 0, 1)
        ballv = ball * max(0.0, 1 - t / 44.0)
        ring = np.exp(-(((r_d - R * 1.25) / (f * 0.012 + 0.0)) ** 2)) * max(0.0, 1 - t / 22.0) * 0.6
        smoke_d = _advect(smoke_d + ball * 0.05 * (t < 30), vy0 * 0.5 - f * 0.004, vx0, yy, xx, 1.0) * 0.99
        temp = nz.ramp(np.clip(ballv * 1.4 * (1 - 0.4 * cool), 0, 1), [(0, (0.05, 0.03, 0.02)), (0.3, (0.6, 0.12, 0.03)), (0.6, (1.0, 0.5, 0.08)), (0.85, (1.0, 0.85, 0.4)), (1, (1.0, 1.0, 0.9))])
        a_f = np.clip(ballv * 1.5, 0, 1)
        sm = np.clip(smoke_d * 1.6 * (0.6 + 0.6 * detail2), 0, 0.8)
        a = np.clip(a_f + sm * (1 - a_f) + ring, 0, 1)
        rgb = (temp * a_f[..., None] + np.array([0.07, 0.065, 0.06], F32) * (sm * (1 - a_f))[..., None] + np.array([1.0, 0.9, 0.7], F32) * ring[..., None]) / np.maximum(a, 1e-3)[..., None]
        canvas = Image.new("L", (f * 2, f * 2), 0)
        dd = ImageDraw.Draw(canvas)
        for ang, sp in debris:
            x = cx + math.cos(ang) * sp * t * f / 128
            y = cy + math.sin(ang) * sp * t * f / 128 + 0.04 * t * t * f / 256
            if 0 <= x < f and 0 <= y < f and t < 50:
                dd.rectangle([x * 2 - 2, y * 2 - 2, x * 2 + 2, y * 2 + 2], fill=int(255 * (1 - t / 50)))
        deb = np.asarray(canvas.resize((f, f), Image.LANCZOS), dtype=F32) / 255.0
        a = np.clip(a + deb * 0.8, 0, 1)
        a = a * nz.smoothstep(xx, 1, 6) * nz.smoothstep(f - 1 - xx, 1, 6) * nz.smoothstep(yy, 1, 6) * nz.smoothstep(f - 1 - yy, 1, 6)
        frames[t] = _premul(np.clip(rgb, 0, 1), _fade_ends(a, t, 1, 10))
    return frames


def rain_drops(f):
    """Ripples on a wet surface: rings spawning at random spots over the sequence."""
    rng = nz.rng_for("vfx", "rain")
    n = 14
    spots = [(rng.uniform(0.15, 0.85) * f, rng.uniform(0.15, 0.85) * f, rng.uniform(0, 44), rng.uniform(0.7, 1.2)) for _ in range(n)]
    yy, xx = _coords(f)
    frames = np.zeros((T, f, f, 4), F32)
    for t in range(T):
        a = np.zeros((f, f), F32)
        for x, y, t0, sc in spots:
            age = t - t0
            if age < 0 or age > 26:
                continue
            r = age * 0.55 * f / 128 * sc + 1.0
            dd = np.sqrt((xx - x) ** 2 + (yy - y) ** 2)
            a = np.maximum(a, np.exp(-(((dd - r) / (1.2 * f / 256 + 0.04 * r)) ** 2)) * (1 - age / 26) * 0.9)
            if age < 3:
                a = np.maximum(a, np.exp(-(dd / (2.2 * f / 256)) ** 2))
        rgb = np.stack([0.85, 0.92, 1.0] * 1 + [], -1) if False else np.broadcast_to(np.array([0.85, 0.92, 1.0], F32), (f, f, 3))
        frames[t] = _premul(rgb, a)
    return frames


def wave_ring(f):
    rng = nz.rng_for("vfx", "wave")
    yy, xx = _coords(f)
    r = np.sqrt((xx - f / 2) ** 2 + (yy - f / 2) ** 2)
    ang = np.arctan2(yy - f / 2, xx - f / 2)
    wob = nz.fbm(f, rng, 2.2, 2, 20)
    frames = np.zeros((T, f, f, 4), F32)
    for t in range(T):
        R = f * 0.47 * (1 - math.exp(-t / 22.0)) + 2
        th = f * (0.05 + 0.02 * t / T)
        rr = R * (1 + 0.04 * (np.roll(wob, t, 1) - 0.5) * 2)
        a = np.exp(-(((r - rr) / th) ** 2)) * (1 - t / T) ** 1.2 * (0.6 + 0.4 * np.roll(wob, (t, 0), (0, 1)))
        foam = np.exp(-(((r - rr - th * 0.4) / (th * 0.5)) ** 2)) * nz.fbm(f, rng, 1.4, 6, f / 3) * (1 - t / T)
        al = np.clip(a * 0.6 + foam * 0.7, 0, 1)
        rgb = np.stack([0.8 + 0.2 * foam, 0.9 + 0.1 * foam, np.ones_like(al)], -1)
        frames[t] = _premul(rgb, al)
    return frames


def projectile_trail(f):
    rng = nz.rng_for("vfx", "trail")
    yy, xx = _coords(f)
    d = np.zeros((f, f), F32)
    vy0, vx0 = _flow(f, rng, 8, 0.7)
    frames = np.zeros((T, f, f, 4), F32)
    for t in range(T):
        hx = f * (0.1 + 0.8 * min(1.0, t / 40.0))
        if t < 42:
            core = np.exp(-(((yy - f / 2) / (f * 0.025)) ** 2 + ((xx - hx) / (f * 0.03)) ** 2))
            d = d + core * 0.5
        d = _advect(d, vy0 * 0.5, vx0 * 0.5 - f * 0.002, yy, xx, 1.0)
        d = ndimage.gaussian_filter(d, 0.7) * 0.965
        head = np.exp(-(((yy - f / 2) / (f * 0.03)) ** 2 + ((xx - hx) / (f * 0.05)) ** 2)) * (t < 44)
        a = np.clip(d * 1.4 + head, 0, 1)
        hot = np.clip(head + d * 0.25, 0, 1)
        rgb = np.stack([0.55 + 0.45 * hot, 0.55 + 0.35 * hot, 0.55 + 0.1 * hot], -1)
        frames[t] = _premul(rgb, _fade_ends(a, t, 1, 8))
    return frames


ATLASES = {
    "smoke_dark": dict(fn=lambda f: smoke(f, "smoke_dark", True, 1.0, 0.12, 1.0), blend="alpha", fps=24, loop=False, note="dense dark smoke column"),
    "smoke_light": dict(fn=lambda f: smoke(f, "smoke_light", False, 0.8, 0.14, 1.1), blend="alpha", fps=24, loop=False, note="light grey smoke"),
    "collapse_dust": dict(fn=collapse_dust, blend="alpha", fps=24, loop=False, note="dust rolling out from a collapse base"),
    "coolant_steam": dict(fn=steam, blend="alpha", fps=30, loop=False, note="thin fast white steam"),
    "sparks": dict(fn=sparks, blend="additive", fps=30, loop=False, note="spark fountain with gravity"),
    "water_splash_impact": dict(fn=lambda f: water_splash(f, True), blend="alpha", fps=30, loop=False, note="impact crown"),
    "water_splash_wide": dict(fn=lambda f: water_splash(f, False), blend="alpha", fps=30, loop=False, note="wide splash"),
    "fire_smoke": dict(fn=fire, blend="alpha", fps=24, loop=False, note="flames with dark smoke above"),
    "electric_arc": dict(fn=electric_arc, blend="additive", fps=30, loop=True, note="flickering arc with branches"),
    "glass_shards": dict(fn=glass_shards, blend="alpha", fps=30, loop=False, note="flying glass fragments"),
    "missile_explosion": dict(fn=missile_explosion, blend="alpha", fps=30, loop=False, note="fireball, shock ring, debris, low smoke"),
    "rain_drops": dict(fn=rain_drops, blend="additive", fps=24, loop=True, note="ripple rings on wet ground"),
    "wave_ring": dict(fn=wave_ring, blend="alpha", fps=24, loop=False, note="expanding ring wave with foam"),
    "projectile_trail": dict(fn=projectile_trail, blend="alpha", fps=30, loop=False, note="projectile with smoky trail"),
}


def to_atlas(frames):
    t, f = frames.shape[0], frames.shape[1]
    out = np.zeros((8 * f, 8 * f, 4), F32)
    for i in range(t):
        r, c = divmod(i, 8)
        out[r * f:(r + 1) * f, c * f:(c + 1) * f] = frames[i]
    return out
