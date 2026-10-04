"""Procedural night-city backdrop (numpy, seeded) so the previews show the HUD over something photo-like: dusk sky, fog layers of towers with lit windows, wet street, rain."""
import numpy as np


def city(W=1920, H=1080, seed=4, enemy=None):
    """Returns an RGB float32 array 0..1. enemy = (cx, cy, h) in pixels draws a dark mech silhouette with red-lit visor."""
    rs = np.random.RandomState(seed)
    y, x = np.mgrid[0:H, 0:W].astype(np.float32)
    t = y / H
    sky = np.zeros((H, W, 3), np.float32)
    top, mid, hor = np.array([0.02, 0.04, 0.10]), np.array([0.20, 0.12, 0.26]), np.array([0.85, 0.38, 0.28])
    f1 = np.clip(t / 0.55, 0, 1)[..., None]
    sky[:] = top * (1 - f1) + mid * f1
    f2 = np.clip((t - 0.45) / 0.25, 0, 1)[..., None] ** 1.5
    sky = sky * (1 - f2) + hor * f2
    img = sky.copy()
    horizon = int(H * 0.62)
    for layer, (base, hmax, win_col, fog) in enumerate([(0.70, 0.38, (0.3, 0.45, 0.6), 0.55), (0.78, 0.50, (0.9, 0.6, 0.3), 0.30), (0.90, 0.62, (0.5, 0.8, 1.0), 0.0)]):
        x0 = 0
        body = np.array([0.05, 0.06, 0.10]) * (1 + layer * 0.15)
        while x0 < W:
            w = int(rs.uniform(70, 190) * (1 + layer * 0.5))
            h = int(H * rs.uniform(0.12, hmax) * (0.6 + 0.5 * rs.rand()))
            top_y = horizon - h + int(layer * 20)
            top_y = max(0, top_y)
            img[top_y:horizon + 40, x0:x0 + w] = img[top_y:horizon + 40, x0:x0 + w] * 0.0 + body * (1 - fog) + hor * 0.5 * fog * 0.35
            # lit windows on a grid
            step = 14 + layer * 6
            yy = np.arange(top_y + 8, horizon + 30, step)
            xx = np.arange(x0 + 6, min(x0 + w - 6, W - 12), step)
            on = rs.rand(len(yy), len(xx)) < 0.35
            for iy, py in enumerate(yy):
                for ix, px in enumerate(xx):
                    if on[iy, ix]:
                        c = np.array(win_col) * rs.uniform(0.5, 1.0)
                        img[py:py + 4 + layer, px:px + 5 + layer] = c * (1 - 0.5 * fog) + body * 0.5 * fog
            x0 += w + int(rs.uniform(0, 14))
    # wet street with reflected neon streaks
    ground = np.clip((y - horizon) / (H - horizon), 0, 1)[..., None]
    g = np.array([0.03, 0.04, 0.07]) * (1 - ground) + np.array([0.01, 0.015, 0.03]) * ground
    img = np.where((y >= horizon)[..., None], g + 0.08 * np.array([1.0, 0.45, 0.3]) * (np.sin(x / 37.0 + 3 * rs.rand()) * 0.5 + 0.5)[..., None] * (1 - ground) ** 2, img)
    for _ in range(40):
        sx = rs.randint(0, W)
        col = np.array([[1.0, 0.4, 0.3], [0.4, 0.8, 1.0], [1.0, 0.8, 0.4]][rs.randint(0, 3)])
        wlen = rs.randint(60, 340)
        img[horizon + 4:horizon + 4 + wlen // 3, sx:sx + 3] += col * 0.25
    # fog haze near the horizon
    haze = np.exp(-((y - horizon) / 90.0) ** 2)[..., None] * np.array([0.45, 0.28, 0.30]) * 0.5
    img = img + haze
    if enemy is not None:
        cx, cy, h = enemy
        _mech(img, cx, cy, h)
    # rain streaks
    for _ in range(900):
        sx, sy = rs.randint(0, W), rs.randint(0, H)
        ln = rs.randint(14, 40)
        for k in range(ln):
            xx, yy = sx - k // 6, sy + k
            if 0 <= xx < W and 0 <= yy < H:
                img[yy, xx] += 0.10 * (1 - k / ln)
    return np.clip(img, 0, 1).astype(np.float32)


def _mech(img, cx, cy, h):
    """A blocky dark mech silhouette (torso, shoulders, arms, legs) centred at cx with feet at cy."""
    H, W = img.shape[:2]
    u = h / 540.0
    body = np.array([0.04, 0.045, 0.06])
    boxes = [(-60, -440, 60, -300), (-110, -450, -62, -380), (62, -450, 110, -380), (-78, -520, 78, -450), (-52, -300, 52, -230),
             (-150, -420, -112, -250), (112, -420, 150, -250), (-70, -230, -22, -10), (22, -230, 70, -10)]
    for x0, y0, x1, y1 in boxes:
        xa, xb, ya, yb = int(cx + x0 * u * 0.8), int(cx + x1 * u * 0.8), int(cy + y0 * u), int(cy + y1 * u)
        img[max(0, ya):max(0, yb), max(0, xa):max(0, xb)] = body
    vx, vy = int(cx), int(cy - 490 * u)
    img[vy - 3:vy + 3, vx - int(30 * u):vx + int(30 * u)] = np.array([1.0, 0.25, 0.2])
