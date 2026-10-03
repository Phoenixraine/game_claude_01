"""Hash-based value noise (deterministic, no tables)."""
import math


def _hash(ix, iy, seed):
    h = (ix * 374761393 + iy * 668265263 + seed * 2147483647) & 0xFFFFFFFF
    h = ((h ^ (h >> 13)) * 1274126177) & 0xFFFFFFFF
    h ^= h >> 16
    return h / 4294967295.0


def _smooth(t):
    return t * t * (3.0 - 2.0 * t)


def value2(x, y, seed):
    """Smooth value noise in [0, 1]."""
    ix = math.floor(x)
    iy = math.floor(y)
    fx = _smooth(x - ix)
    fy = _smooth(y - iy)
    a = _hash(ix, iy, seed)
    b = _hash(ix + 1, iy, seed)
    c = _hash(ix, iy + 1, seed)
    d = _hash(ix + 1, iy + 1, seed)
    return (a + (b - a) * fx) + ((c + (d - c) * fx) - (a + (b - a) * fx)) * fy


def fbm2(x, y, seed, octaves=3, lacunarity=2.0, gain=0.5):
    """Fractal noise normalised to [-1, 1]."""
    total = 0.0
    amp = 1.0
    norm = 0.0
    for o in range(octaves):
        total += (value2(x, y, seed + o * 101) * 2.0 - 1.0) * amp
        norm += amp
        x *= lacunarity
        y *= lacunarity
        amp *= gain
    return total / norm


def value1(x, seed):
    return value2(x, 0.37, seed)
