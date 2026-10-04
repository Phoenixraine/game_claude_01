"""Raster layers made with numpy (seeded, deterministic): gauge masks, crack / soot / glitch / rain textures, alarm frame."""
import math

import numpy as np
from PIL import Image


def _save(arr, path, mode):
    Image.fromarray(arr, mode).save(path, optimize=True)


def gauge_mask(kind, size=256):
    """RGBA 256 x 256. R = progress along the 270-degree ring (0 at the start, 255 at the end) so the material can threshold R < fill; A = ring / tick shape; G = 255 on the 'frame' pixels
    (inner ring); B = 0. kind: armor (24 blocks), stability (smooth), heat (smooth + outer ticks), energy (12 blocks)."""
    ss = 2
    S = size * ss
    y, x = np.mgrid[0:S, 0:S].astype(np.float32)
    cx = cy = S / 2.0
    dx, dy = x + 0.5 - cx, y + 0.5 - cy
    r = np.hypot(dx, dy) / ss
    ang = (np.degrees(np.arctan2(dy, dx)) - 135.0) % 360.0     # 0 at the lower left start, clockwise on screen
    inside = ang <= 270.0
    prog = np.clip(ang / 270.0, 0, 1)
    ring = (np.abs(r - 98.0) <= 5.5) & inside
    segs = {"armor": 24, "energy": 12}.get(kind, 0)
    if segs:
        seg = 270.0 / segs
        ring &= (ang % seg) <= seg * 0.82
    inner = np.abs(r - 70.0) <= 0.8
    alpha = (ring | inner).astype(np.float32)
    if kind == "heat":
        k = np.round(ang / (270.0 / 27.0))
        near = np.abs(ang - k * (270.0 / 27.0)) <= 1.0
        alpha = np.maximum(alpha, ((r >= 106) & (r <= np.where(k % 3 == 0, 114, 110)) & near & inside).astype(np.float32))
    out = np.zeros((S, S, 4), np.float32)
    out[..., 0] = prog * 255.0 * ring
    out[..., 1] = inner * 255.0
    out[..., 3] = alpha * 255.0
    out = out.reshape(size, ss, size, ss, 4).mean(axis=(1, 3))
    return np.clip(out + 0.5, 0, 255).astype(np.uint8)


def crack_mask(seed, size=1024, cracks=14, rings=2):
    """Greyscale glass crack mask: radial cracks with kinks and branches from an impact point plus broken concentric arcs. White = crack."""
    rs = np.random.RandomState(seed)
    img = np.zeros((size, size), np.uint8)
    cx, cy = rs.uniform(0.25, 0.75) * size, rs.uniform(0.25, 0.75) * size

    def line(x0, y0, x1, y1, w, v):
        n_ = int(max(abs(x1 - x0), abs(y1 - y0)) * 1.2) + 2
        for t in np.linspace(0, 1, n_):
            x, y = x0 + (x1 - x0) * t, y0 + (y1 - y0) * t
            xi, yi = int(x), int(y)
            r = int(math.ceil(w))
            y_lo, y_hi, x_lo, x_hi = max(0, yi - r), min(size, yi + r + 1), max(0, xi - r), min(size, xi + r + 1)
            if y_lo >= y_hi or x_lo >= x_hi:
                continue
            yy, xx = np.mgrid[y_lo:y_hi, x_lo:x_hi]
            d = np.hypot(xx - x, yy - y)
            img[y_lo:y_hi, x_lo:x_hi] = np.maximum(img[y_lo:y_hi, x_lo:x_hi], (np.clip(1.2 - d / w, 0, 1) * v).astype(np.uint8))

    def crack(x, y, a, length, w, depth):
        px, py = x, y
        done = 0.0
        while done < length:
            seg = rs.uniform(18, 46)
            a += rs.uniform(-0.28, 0.28)
            nx, ny = px + math.cos(a) * seg, py + math.sin(a) * seg
            line(px, py, nx, ny, w, 255)
            if depth > 0 and rs.rand() < 0.22:
                crack(nx, ny, a + rs.choice([-1, 1]) * rs.uniform(0.5, 1.1), length * rs.uniform(0.2, 0.4), max(0.8, w * 0.7), depth - 1)
            px, py, done = nx, ny, done + seg
            w = max(0.8, w * 0.97)
    for k in range(cracks):
        crack(cx, cy, 2 * math.pi * k / cracks + rs.uniform(-0.15, 0.15), rs.uniform(0.18, 0.55) * size, rs.uniform(1.0, 1.7), 1)
    for r in range(rings):
        rad = (r + 1) * size * rs.uniform(0.07, 0.11)
        a0 = rs.uniform(0, 6.28)
        for q in range(14):
            if rs.rand() < 0.65:
                a1 = a0 + rs.uniform(0.15, 0.5)
                line(cx + math.cos(a0) * rad, cy + math.sin(a0) * rad, cx + math.cos(a1) * rad, cy + math.sin(a1) * rad, 1.2, 170)
            a0 += rs.uniform(0.25, 0.55)
    return img


def _value_noise(rs, size, octaves=5):
    out = np.zeros((size, size), np.float32)
    amp, tot = 1.0, 0.0
    for o in range(octaves):
        n_ = 4 * 2 ** o
        g = rs.rand(n_ + 1, n_ + 1).astype(np.float32)
        t = np.linspace(0, n_, size, endpoint=False)
        i0 = t.astype(int)
        f = (t - i0)
        f = f * f * (3 - 2 * f)
        gx = g[:, i0] * (1 - f) + g[:, i0 + 1] * f           # (n+1, size)
        gy = gx[i0, :] * (1 - f)[:, None] + gx[i0 + 1, :] * f[:, None]
        out += gy * amp
        tot += amp
        amp *= 0.55
    return out / tot


def soot_mask(seed, size=1024):
    """Greyscale soot smudge: dense in one corner, noisy cloud edge. White = soot (multiply-darkens the glass)."""
    rs = np.random.RandomState(seed)
    nz = _value_noise(rs, size)
    y, x = np.mgrid[0:size, 0:size].astype(np.float32) / size
    corner = [(0, 1), (1, 1), (0, 0), (1, 0)][seed % 4]
    d = np.hypot(x - corner[0], y - corner[1])
    v = np.clip(1.15 - d * 1.35 + (nz - 0.5) * 0.9, 0, 1)
    return (np.clip(v ** 1.4, 0, 1) * 255).astype(np.uint8)


def glitch_strip(seed, w=1024, h=64):
    """RGBA glitch band: horizontal blocks shifted in cyan / red with scanline dropouts, for additive blending."""
    rs = np.random.RandomState(seed)
    img = np.zeros((h, w, 4), np.uint8)
    for _ in range(rs.randint(5, 10)):
        y0 = rs.randint(0, h - 4)
        hh = rs.randint(2, 14)
        x0 = rs.randint(0, w - 40)
        ww = rs.randint(40, w // 2)
        col = [(127, 228, 255), (255, 74, 61), (232, 251, 255)][rs.randint(0, 3)]
        img[y0:y0 + hh, x0:x0 + ww, :3] = col
        img[y0:y0 + hh, x0:x0 + ww, 3] = rs.randint(60, 200)
        if rs.rand() < 0.6:
            img[y0:y0 + hh, x0 + ww // 2:x0 + ww // 2 + 3, 3] = 0
    img[::4, :, 3] = (img[::4, :, 3] * 0.5).astype(np.uint8)
    return img


def rain_atlas(seed=11, size=1024, cells=4):
    """RGBA atlas of water drops, cells x cells. R,G = refraction offset (128 = none), B = highlight, A = drop mask. Drops are round or tear-shaped."""
    rs = np.random.RandomState(seed)
    cs = size // cells
    img = np.zeros((size, size, 4), np.uint8)
    img[..., 0] = img[..., 1] = 128
    yy, xx = np.mgrid[0:cs, 0:cs].astype(np.float32)
    for j in range(cells):
        for i in range(cells):
            rad = cs * rs.uniform(0.16, 0.36)
            stretch = rs.uniform(1.0, 1.9) if (i + j) % 2 else 1.0
            dx, dy = (xx - cs / 2) / rad, (yy - cs / 2) / (rad * stretch)
            r2 = dx * dx + dy * dy
            m = np.clip((1.0 - np.sqrt(r2)) * rad * 0.9, 0, 1)
            nx = np.where(r2 < 1, dx / np.maximum(np.sqrt(r2), 1e-3), 0) * np.clip(np.sqrt(r2), 0, 1) ** 2
            ny = np.where(r2 < 1, dy / np.maximum(np.sqrt(r2), 1e-3), 0) * np.clip(np.sqrt(r2), 0, 1) ** 2
            hl = np.clip(1.0 - np.hypot(dx + 0.35, dy + 0.4) * 2.4, 0, 1)
            tile = img[j * cs:(j + 1) * cs, i * cs:(i + 1) * cs]
            tile[..., 0] = (128 + nx * 90 * m).astype(np.uint8)
            tile[..., 1] = (128 + ny * 90 * m).astype(np.uint8)
            tile[..., 2] = (hl * 255 * m).astype(np.uint8)
            tile[..., 3] = (m * 255).astype(np.uint8)
    return img


def alarm_frame(w=1024, h=576):
    """RGBA red edge vignette (the 'alarm frame'): transparent in the middle 70 %, red + alpha toward the borders, with a thin bright inner border line. Premultiplied-friendly."""
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    nx, ny = np.abs(x / (w - 1) * 2 - 1), np.abs(y / (h - 1) * 2 - 1)
    d = np.maximum(nx ** 3, ny ** 3)
    a = np.clip((d - 0.40) / 0.60, 0, 1) ** 1.4
    line = np.exp(-((np.maximum(nx, ny * 1.0) - 0.965) / 0.012) ** 2)
    img = np.zeros((h, w, 4), np.float32)
    img[..., 0] = 255
    img[..., 1] = 74 + 120 * line
    img[..., 2] = 61 + 100 * line
    img[..., 3] = np.clip(a * 200 + line * 90, 0, 255)
    return img.astype(np.uint8)


def save_rgba(arr, path):
    _save(arr, path, "RGBA")


def save_gray(arr, path):
    _save(arr, path, "L")
