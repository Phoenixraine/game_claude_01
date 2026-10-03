"""Seamless (periodic) procedural noise on n x n float32 grids. Everything wraps around by construction (FFT synthesis,
wrapped Worley cells, wrapped line drawing), so the tile seam is exact. Deterministic: every function takes a numpy Generator."""
import math

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage
from scipy.fft import irfft2, rfft2, rfftfreq, fftfreq

F32 = np.float32


def rng_for(*parts):
    """Stable generator from strings/ints (zlib.crc32 of the joined parts)."""
    import zlib
    return np.random.default_rng(zlib.crc32("|".join(str(p) for p in parts).encode()))


def _norm01(a, lo=1.0, hi=99.0):
    l, h = np.percentile(a, [lo, hi])
    return np.clip((a - l) / max(h - l, 1e-9), 0, 1).astype(F32)


def _kgrid(n):
    ky = fftfreq(n)[:, None] * n
    kx = rfftfreq(n)[None, :] * n
    return np.sqrt(kx * kx + ky * ky)


def fbm(n, rng, beta=2.0, kmin=1.0, kmax=None, aniso=(1.0, 1.0)):
    """Spectral noise 1/k^beta between kmin and kmax (cycles per tile), normalised to 0..1. `aniso` = (x, y) frequency stretch:
    (1, 8) gives strongly horizontal streaks."""
    kmax = kmax or n / 2
    ky = fftfreq(n)[:, None] * n * aniso[1]
    kx = rfftfreq(n)[None, :] * n * aniso[0]
    k = np.sqrt(kx * kx + ky * ky)
    w = rng.standard_normal((n, n)).astype(F32)
    Fk = rfft2(w)
    amp = np.where((k >= kmin) & (k <= kmax), np.maximum(k, 1e-6) ** (-beta / 2.0), 0.0)
    amp[0, 0] = 0
    return _norm01(irfft2(Fk * amp, s=(n, n)))


def blur(a, sigma):
    """Periodic gaussian blur (sigma in pixels) via FFT."""
    n = a.shape[0]
    k = _kgrid(n) / n
    g = np.exp(-2 * (math.pi * sigma * k) ** 2)
    return irfft2(rfft2(a) * g, s=a.shape).astype(F32)


def worley(n, rng, cells, jitter=1.0, return_id=False):
    """Periodic cellular noise: returns F1 distance (0..~1, in cell units), F2, and optionally a random value per cell id."""
    cells = int(cells)
    ci, cj = np.meshgrid(np.arange(cells), np.arange(cells), indexing="ij")
    px = (ci + 0.5 + (rng.random((cells, cells)) - 0.5) * jitter) / cells
    py = (cj + 0.5 + (rng.random((cells, cells)) - 0.5) * jitter) / cells
    vid = rng.random((cells, cells)).astype(F32)
    y, x = np.meshgrid((np.arange(n) + 0.5) / n, (np.arange(n) + 0.5) / n, indexing="ij")
    cy = np.floor(y * cells).astype(int)
    cx = np.floor(x * cells).astype(int)
    d1 = np.full((n, n), 9.0, dtype=F32)
    d2 = np.full((n, n), 9.0, dtype=F32)
    idv = np.zeros((n, n), dtype=F32)
    for oy in (-1, 0, 1):
        for ox in (-1, 0, 1):
            gy, gx = (cy + oy), (cx + ox)
            wy, wx = gy % cells, gx % cells
            ppx = px[wx, wy] + (gx - wx) / cells
            ppy = py[wx, wy] + (gy - wy) / cells
            d = np.sqrt((x - ppx) ** 2 + (y - ppy) ** 2).astype(F32) * cells
            closer = d < d1
            d2 = np.where(closer, d1, np.minimum(d2, d))
            idv = np.where(closer, vid[wx, wy], idv)
            d1 = np.where(closer, d, d1)
    if return_id:
        return d1, d2, idv
    return d1, d2


def warp(a, rng, amount=0.03, beta=2.6, kmax=12):
    """Periodic domain warp of a (n, n[, c]) image by smooth noise; `amount` as a fraction of the tile."""
    n = a.shape[0]
    dx = (fbm(n, rng, beta, 1, kmax) - 0.5) * 2 * amount * n
    dy = (fbm(n, rng, beta, 1, kmax) - 0.5) * 2 * amount * n
    yy, xx = np.meshgrid(np.arange(n), np.arange(n), indexing="ij")
    coords = [yy + dy, xx + dx]
    if a.ndim == 2:
        return ndimage.map_coordinates(a, coords, order=1, mode="grid-wrap").astype(F32)
    return np.stack([ndimage.map_coordinates(a[..., c], coords, order=1, mode="grid-wrap") for c in range(a.shape[2])], -1).astype(F32)


def lines(n, rng, count, length=(0.1, 0.5), width=(1.0, 2.0), angle=None, bright=(0.4, 1.0), curvy=0.0):
    """Anti-aliased random line segments drawn with wrap-around (scratches, cracks). Returns 0..1 float image."""
    s = 2
    im = Image.new("L", (n * s, n * s), 0)
    d = ImageDraw.Draw(im)
    for _ in range(count):
        x0, y0 = rng.random() * n, rng.random() * n
        ang = rng.uniform(0, math.pi) if angle is None else angle + rng.normal(0, 0.15)
        ln = rng.uniform(*length) * n
        w = rng.uniform(*width)
        v = int(255 * rng.uniform(*bright))
        pts = [(x0, y0)]
        steps = 6 if curvy else 1
        for k in range(1, steps + 1):
            a = ang + (rng.normal(0, curvy) if curvy else 0)
            pts.append((pts[-1][0] + math.cos(a) * ln / steps, pts[-1][1] + math.sin(a) * ln / steps))
        for ox in (-n, 0, n):
            for oy in (-n, 0, n):
                d.line([((x + ox) * s, (y + oy) * s) for x, y in pts], fill=v, width=max(1, int(w * s)))
    im = im.resize((n, n), Image.LANCZOS)
    return np.asarray(im, dtype=F32) / 255.0


def blobs(n, rng, count, radius=(0.01, 0.05), soft=0.6):
    """Soft round blobs with wrap-around (stains, pits). 0..1."""
    out = np.zeros((n, n), dtype=F32)
    yy, xx = np.meshgrid(np.arange(n), np.arange(n), indexing="ij")
    for _ in range(count):
        cx, cy = rng.random() * n, rng.random() * n
        r = rng.uniform(*radius) * n
        dx = np.minimum(np.abs(xx - cx), n - np.abs(xx - cx))
        dy = np.minimum(np.abs(yy - cy), n - np.abs(yy - cy))
        m = np.clip(1.0 - np.sqrt(dx * dx + dy * dy) / r, 0, 1)
        out = np.maximum(out, m ** soft * rng.uniform(0.4, 1.0))
    return out


def smoothstep(a, lo, hi):
    t = np.clip((a - lo) / max(hi - lo, 1e-9), 0, 1)
    return (t * t * (3 - 2 * t)).astype(F32)


def ramp(t, stops):
    """Gradient map: t in 0..1 (n, n) -> (n, n, 3) from [(pos, (r, g, b)), ...] (values 0..1)."""
    pos = np.array([p for p, _ in stops], dtype=F32)
    cols = np.array([c for _, c in stops], dtype=F32)
    out = np.stack([np.interp(t, pos, cols[:, c]) for c in range(3)], -1)
    return out.astype(F32)


def grid_cells(n, nx, ny, seam=0.02, bevel=0.03):
    """Panel layout: (groove mask 0..1, u, v). `seam`/`bevel` are fractions of a cell (0.02 = 2 % of the cell width). Tileable for integer nx, ny."""
    y, x = np.meshgrid((np.arange(n) + 0.5) / n, (np.arange(n) + 0.5) / n, indexing="ij")
    u = (x * nx) % 1.0
    v = (y * ny) % 1.0
    e = np.minimum(np.minimum(u, 1 - u), np.minimum(v, 1 - v))      # distance to the nearest cell edge, in cell units (0..0.5)
    groove = 1.0 - smoothstep(e, seam, seam + bevel)
    return groove.astype(F32), u.astype(F32), v.astype(F32)
