"""Noise toolkit (numpy only): FFT-filtered 2D fractal noise (texture space) and hashed 3D value noise (world space, continuous across UV islands)."""
import numpy as np


def fbm2(shape, seed, base=4, octaves=5, persistence=0.55, aniso=(1.0, 1.0)):
    """Band-limited random field built in the frequency domain; `base` = lowest frequency (cycles over the image), result in 0..1."""
    rng = np.random.default_rng(seed)
    h, w = shape
    fy = np.fft.fftfreq(h)[:, None] * h
    fx = np.fft.rfftfreq(w)[None, :] * w
    r = np.sqrt((fy / aniso[0]) ** 2 + (fx / aniso[1]) ** 2) + 1e-6
    spec = np.zeros((h, w // 2 + 1), dtype=np.complex64)
    amp = 1.0
    f = float(base)
    for _ in range(octaves):
        band = np.exp(-((np.log2(r) - np.log2(f)) ** 2) * 1.6) * amp
        phase = rng.uniform(0, 2 * np.pi, band.shape).astype(np.float32)
        spec += (band * np.exp(1j * phase)).astype(np.complex64)
        amp *= persistence
        f *= 2.0
    img = np.fft.irfft2(spec, s=shape).astype(np.float32)
    img -= img.min()
    img /= max(float(img.max()), 1e-6)
    return img


def _hash3(ix, iy, iz, seed):
    h = (ix * 73856093) ^ (iy * 19349663) ^ (iz * 83492791) ^ (seed * 2654435761 & 0x7FFFFFFF)
    h = (h ^ (h >> 13)) * 1274126177
    h = h ^ (h >> 16)
    return (h & 0xFFFF).astype(np.float32) / 65535.0


def vnoise3(p, seed=0):
    """Value noise at points p (N,3), trilinear with smoothstep; returns N values in 0..1."""
    p = np.asarray(p, dtype=np.float32)
    i = np.floor(p).astype(np.int64)
    f = p - i
    f = f * f * (3 - 2 * f)
    out = 0.0
    for dx in (0, 1):
        for dy in (0, 1):
            for dz in (0, 1):
                w = (f[:, 0] if dx else 1 - f[:, 0]) * (f[:, 1] if dy else 1 - f[:, 1]) * (f[:, 2] if dz else 1 - f[:, 2])
                out = out + w * _hash3(i[:, 0] + dx, i[:, 1] + dy, i[:, 2] + dz, seed)
    return out


def fbm3(p, seed=0, octaves=4, persistence=0.5, scale=(1.0, 1.0, 1.0)):
    """Fractal 3D value noise; `scale` stretches the lattice per axis (e.g. (1,1,0.06) gives vertical streaks)."""
    p = np.asarray(p, dtype=np.float32) * np.asarray(scale, dtype=np.float32)
    tot, amp, norm = 0.0, 1.0, 0.0
    for o in range(octaves):
        tot = tot + amp * vnoise3(p * (2.0 ** o), seed + 17 * o)
        norm += amp
        amp *= persistence
    return tot / norm


def smoothstep(a, b, x):
    t = np.clip((x - a) / (b - a + 1e-9), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def blur(img, r):
    """Separable box-ish blur by FFT-free cumulative sums (3 passes ~ gaussian). img (H,W) or (H,W,C)."""
    if r < 1:
        return img
    out = img.astype(np.float32)
    for _ in range(3):
        for ax in (0, 1):
            k = int(r)
            c = np.cumsum(np.pad(out, [(k + 1, k) if a == ax else (0, 0) for a in range(out.ndim)], mode="edge"), axis=ax, dtype=np.float64)
            sl_hi = [slice(None)] * out.ndim
            sl_lo = [slice(None)] * out.ndim
            sl_hi[ax] = slice(2 * k + 1, None)
            sl_lo[ax] = slice(0, -(2 * k + 1))
            out = ((c[tuple(sl_hi)] - c[tuple(sl_lo)]) / (2 * k + 1)).astype(np.float32)
    return out


def dilate(mask, r):
    """Binary dilation by a square of radius r (separable max)."""
    m = mask.astype(np.uint8)
    for ax in (0, 1):
        acc = m.copy()
        for s in range(1, r + 1):
            acc = np.maximum(acc, np.roll(m, s, ax))
            acc = np.maximum(acc, np.roll(m, -s, ax))
        m = acc
    return m.astype(bool)


def erode(mask, r):
    return ~dilate(~mask, r)


def height_to_normal(h, strength=1.0):
    """Tangent-space normal (OpenGL, +Y up in the image) from a height field in texture space; returns (H,W,3) float 0..1."""
    dx = (np.roll(h, -1, 1) - np.roll(h, 1, 1)) * 0.5
    dy = (np.roll(h, 1, 0) - np.roll(h, -1, 0)) * 0.5     # image row 0 is the top: +v is up
    n = np.stack([-dx * strength, -dy * strength, np.ones_like(h)], -1)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    return n * 0.5 + 0.5
