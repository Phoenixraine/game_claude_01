"""Glass crack masks: four procedural 1024x1024 greyscale PNGs (white cracks on black), radial fractures from an impact point with branches and a few concentric rings."""
import math
import random
import struct
import zlib

import numpy as np

N = 1024


def _line(img, x0, y0, x1, y1, w, val):
    steps = int(max(abs(x1 - x0), abs(y1 - y0))) + 1
    for i in range(steps + 1):
        t = i / steps
        x, y = x0 + (x1 - x0) * t, y0 + (y1 - y0) * t
        r = max(0, int(w / 2))
        xi, yi = int(round(x)), int(round(y))
        x_lo, x_hi, y_lo, y_hi = max(0, xi - r), min(N, xi + r + 1), max(0, yi - r), min(N, yi + r + 1)
        if x_lo < x_hi and y_lo < y_hi:
            sub = img[y_lo:y_hi, x_lo:x_hi]
            np.maximum(sub, val, out=sub)


def make_mask(seed, cracks=18, rings=3):
    rng = random.Random(seed)
    img = np.zeros((N, N), np.uint8)
    cx, cy = rng.uniform(0.25, 0.75) * N, rng.uniform(0.25, 0.75) * N
    for k in range(cracks):
        ang = 2 * math.pi * k / cracks + rng.uniform(-0.15, 0.15)
        x, y = cx, cy
        L = rng.uniform(0.2, 0.7) * N
        w = rng.uniform(2.0, 4.0)
        steps = int(L / 14)
        for s in range(steps):
            ang += rng.uniform(-0.25, 0.25)
            nx, ny = x + math.cos(ang) * 14, y + math.sin(ang) * 14
            _line(img, x, y, nx, ny, w, 255)
            if rng.random() < 0.22 and s > 2:                     # a side branch
                bx, by, ba = nx, ny, ang + rng.choice((-1, 1)) * rng.uniform(0.5, 1.0)
                for q in range(rng.randint(3, 9)):
                    ba += rng.uniform(-0.3, 0.3)
                    ex, ey = bx + math.cos(ba) * 12, by + math.sin(ba) * 12
                    _line(img, bx, by, ex, ey, max(1.0, w * 0.5), 200)
                    bx, by = ex, ey
            x, y = nx, ny
            w = max(1.0, w * 0.97)
    for r in range(rings):
        rad = (r + 1) * rng.uniform(55, 95)
        a0 = rng.uniform(0, 2 * math.pi)
        arc = rng.uniform(1.2, 2.6)
        pts = 40
        for q in range(pts):
            a = a0 + arc * q / pts
            b = a0 + arc * (q + 1) / pts
            _line(img, cx + math.cos(a) * rad, cy + math.sin(a) * rad, cx + math.cos(b) * rad, cy + math.sin(b) * rad, 1.5 + (rings - r) * 0.4, 170)
    return img


def png_gray(img):
    h, w = img.shape
    raw = b"".join(b"\x00" + img[y].tobytes() for y in range(h))

    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 0, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b"")


def write_masks(out_dir):
    import os
    os.makedirs(out_dir, exist_ok=True)
    paths = []
    for k in range(4):
        data = png_gray(make_mask(1000 + 17 * k, cracks=14 + 4 * k, rings=2 + k % 3))
        p = os.path.join(out_dir, "Glass_Crack_Mask_%02d.png" % k)
        with open(p, "wb") as f:
            f.write(data)
        paths.append((p, len(data)))
    return paths
