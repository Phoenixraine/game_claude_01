"""2D geometry helpers (metres)."""
import math


def rot(p, yaw, origin=(0.0, 0.0)):
    c, s = math.cos(yaw), math.sin(yaw)
    x, y = p[0] - origin[0], p[1] - origin[1]
    return (origin[0] + x * c - y * s, origin[1] + x * s + y * c)


def rect_poly(cx, cy, w, d, yaw=0.0):
    """Rectangle w (local x) by d (local y) centred at (cx, cy), CCW."""
    hw, hd = w / 2.0, d / 2.0
    pts = [(-hw, -hd), (hw, -hd), (hw, hd), (-hw, hd)]
    return [(cx + rot(p, yaw)[0], cy + rot(p, yaw)[1]) for p in pts]


def area(poly):
    a = 0.0
    for i in range(len(poly)):
        x0, y0 = poly[i]
        x1, y1 = poly[(i + 1) % len(poly)]
        a += x0 * y1 - x1 * y0
    return a / 2.0


def centroid(poly):
    a = area(poly)
    if abs(a) < 1e-9:
        return (sum(p[0] for p in poly) / len(poly), sum(p[1] for p in poly) / len(poly))
    cx = cy = 0.0
    for i in range(len(poly)):
        x0, y0 = poly[i]
        x1, y1 = poly[(i + 1) % len(poly)]
        f = x0 * y1 - x1 * y0
        cx += (x0 + x1) * f
        cy += (y0 + y1) * f
    return (cx / (6 * a), cy / (6 * a))


def bbox(poly):
    xs = [p[0] for p in poly]
    ys = [p[1] for p in poly]
    return (min(xs), min(ys), max(xs), max(ys))


def point_in_poly(pt, poly):
    x, y = pt
    inside = False
    n = len(poly)
    for i in range(n):
        x0, y0 = poly[i]
        x1, y1 = poly[(i + 1) % n]
        if (y0 > y) != (y1 > y):
            xi = x0 + (y - y0) * (x1 - x0) / (y1 - y0)
            if x < xi:
                inside = not inside
    return inside


def _orient(a, b, c):
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def segments_intersect(p1, p2, p3, p4):
    d1 = _orient(p3, p4, p1)
    d2 = _orient(p3, p4, p2)
    d3 = _orient(p1, p2, p3)
    d4 = _orient(p1, p2, p4)
    return ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0)) and d1 != 0 and d2 != 0 and d3 != 0 and d4 != 0


def polys_intersect(a, b):
    """True when two simple polygons overlap (edges cross or one contains the other)."""
    ba, bb = bbox(a), bbox(b)
    if ba[2] < bb[0] or bb[2] < ba[0] or ba[3] < bb[1] or bb[3] < ba[1]:
        return False
    na, nb = len(a), len(b)
    for i in range(na):
        for j in range(nb):
            if segments_intersect(a[i], a[(i + 1) % na], b[j], b[(j + 1) % nb]):
                return True
    return point_in_poly(a[0], b) or point_in_poly(b[0], a)


def convex_hull(points):
    pts = sorted(set((round(p[0], 6), round(p[1], 6)) for p in points))
    if len(pts) <= 2:
        return pts

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower = []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    upper = []
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def nearest_on_segment(p, a, b):
    abx, aby = b[0] - a[0], b[1] - a[1]
    l2 = abx * abx + aby * aby
    t = 0.0 if l2 == 0 else max(0.0, min(1.0, ((p[0] - a[0]) * abx + (p[1] - a[1]) * aby) / l2))
    return (a[0] + abx * t, a[1] + aby * t)


def dist_to_poly_edges(p, poly):
    best = (1e18, p)
    n = len(poly)
    for i in range(n):
        q = nearest_on_segment(p, poly[i], poly[(i + 1) % n])
        d = math.hypot(q[0] - p[0], q[1] - p[1])
        if d < best[0]:
            best = (d, q)
    return best


def norm(v):
    l = math.hypot(v[0], v[1])
    return (v[0] / l, v[1] / l) if l > 1e-12 else (0.0, 0.0)


def angle_between(a, b):
    """Angle in degrees between two 2D vectors."""
    na, nb = norm(a), norm(b)
    d = max(-1.0, min(1.0, na[0] * nb[0] + na[1] * nb[1]))
    return math.degrees(math.acos(d))


def dist_point_polyline(p, line):
    best = 1e18
    for i in range(len(line) - 1):
        q = nearest_on_segment(p, line[i], line[i + 1])
        best = min(best, math.hypot(q[0] - p[0], q[1] - p[1]))
    return best


def poly_inset_rect(poly, margin):
    """Axis-aligned inset of a polygon's bbox (blocks are warped quads: use centroid-scaled shrink)."""
    c = centroid(poly)
    out = []
    for p in poly:
        v = norm((p[0] - c[0], p[1] - c[1]))
        out.append((p[0] - v[0] * margin, p[1] - v[1] * margin))
    return out
