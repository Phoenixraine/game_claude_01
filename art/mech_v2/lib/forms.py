"""Organic hard-surface forms for BASTION v2: lofted tubes with super-elliptic sections, ellipsoids, conforming armour shells
(stepped chamfer, variable width) and hydraulic cylinders. All functions add geometry to an `hs.Part` (see hs.py)."""
import math

import bpy  # noqa: F401  (must come before mathutils/bmesh when used as a module)

import bmesh
import numpy as np
from mathutils import Matrix, Vector

from . import hs


def V(*a):
    return Vector(a[0] if len(a) == 1 else a)


# ----------------------------------------------------------------------------------------------------- sections
def superellipse(n, rx, ry, power=2.6, phase=0.0, flat_front=0.0):
    """n points of a super-ellipse (power 2 = ellipse, 4 = rounded rectangle). `flat_front` pulls the -Y side flat (bib plate)."""
    pts = []
    for i in range(n):
        t = phase + 2 * math.pi * i / n
        c, s = math.cos(t), math.sin(t)
        x = rx * math.copysign(abs(c) ** (2.0 / power), c)
        y = ry * math.copysign(abs(s) ** (2.0 / power), s)
        if flat_front and y < 0:
            y *= 1.0 - flat_front * (abs(s) ** 4)
        pts.append((x, y))
    return pts


class Sec:
    """One cross-section of a tube: a centre, two radii, the rounding, an in-plane twist and an optional (x, y) skew of the points."""

    def __init__(self, center, rx, ry=None, power=2.6, twist=0.0, flat_front=0.0, shift=(0.0, 0.0)):
        self.c = Vector(center)
        self.rx = rx
        self.ry = rx if ry is None else ry
        self.power = power
        self.twist = twist
        self.flat_front = flat_front
        self.shift = shift

    def lerp(self, o, t):
        return Sec(self.c.lerp(o.c, t), self.rx + (o.rx - self.rx) * t, self.ry + (o.ry - self.ry) * t, self.power + (o.power - self.power) * t,
                   self.twist + (o.twist - self.twist) * t, self.flat_front + (o.flat_front - self.flat_front) * t,
                   (self.shift[0] + (o.shift[0] - self.shift[0]) * t, self.shift[1] + (o.shift[1] - self.shift[1]) * t))


def _basis(tangent, ref):
    t = tangent.normalized()
    u = ref - t * ref.dot(t)
    if u.length < 1e-6:
        u = Vector((1, 0, 0)) - t * t.x
    u.normalize()
    v = t.cross(u)
    return u, v


SUBDIV = 2          # extra rings between the given sections (smooth Catmull-Rom profile)
RADIAL = 1.4        # multiplier of the number of points around each ring


def _cr(p0, p1, p2, p3, t):
    return 0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3)


class Tube:
    """A lofted solid along a polyline of sections. Section planes are perpendicular to the local axis; the basis is parallel-transported
    so that `ref` (default +X) stays the first radius direction (rx) along the whole tube."""

    def __init__(self, secs, n=24, ref=(1, 0, 0)):
        self.secs = secs
        self.n = max(8, int(round(n * RADIAL / 2.0)) * 2)
        self.ref = Vector(ref)
        self.bases = []
        prev_u = None
        for i, s in enumerate(secs):
            a = secs[max(i - 1, 0)].c
            b = secs[min(i + 1, len(secs) - 1)].c
            tang = b - a
            u, v = _basis(tang, prev_u if prev_u is not None else self.ref)
            self.bases.append((u, v))
            prev_u = u

    def _interp(self, t):
        k = len(self.secs) - 1
        x = min(max(t, 0.0), 1.0) * k
        i = min(int(x), k - 1)
        f = x - i
        S = self.secs
        a, b, c, d = S[max(i - 1, 0)], S[i], S[i + 1], S[min(i + 2, k)]
        s = Sec(_cr(a.c, b.c, c.c, d.c, f), max(0.05, _cr(a.rx, b.rx, c.rx, d.rx, f)), max(0.05, _cr(a.ry, b.ry, c.ry, d.ry, f)),
                max(1.6, _cr(a.power, b.power, c.power, d.power, f)), _cr(a.twist, b.twist, c.twist, d.twist, f), max(0.0, _cr(a.flat_front, b.flat_front, c.flat_front, d.flat_front, f)),
                (_cr(a.shift[0], b.shift[0], c.shift[0], d.shift[0], f), _cr(a.shift[1], b.shift[1], c.shift[1], d.shift[1], f)))
        u0, v0 = self.bases[i]
        u1, v1 = self.bases[i + 1]
        u = (u0 * (1 - f) + u1 * f).normalized()
        v = (v0 * (1 - f) + v1 * f).normalized()
        return s, u, v

    def point(self, t, theta):
        s, u, v = self._interp(t)
        c, sn = math.cos(theta + math.radians(s.twist)), math.sin(theta + math.radians(s.twist))
        x = s.rx * math.copysign(abs(c) ** (2.0 / s.power), c)
        y = s.ry * math.copysign(abs(sn) ** (2.0 / s.power), sn)
        if s.flat_front and y < 0:
            y *= 1.0 - s.flat_front * (abs(sn) ** 4)
        x += s.shift[0]
        y += s.shift[1]
        return s.c + u * x + v * y

    def center(self, t):
        return self._interp(t)[0].c

    def normal(self, t, theta, eps=1e-3):
        p = self.point(t, theta)
        dt = self.point(min(1.0, t + eps), theta) - self.point(max(0.0, t - eps), theta)
        dth = self.point(t, theta + eps) - self.point(t, theta - eps)
        n = dth.cross(dt)
        if n.length < 1e-9:
            return (p - self.center(t)).normalized()
        n.normalize()
        if n.dot(p - self.center(t)) < 0:
            n = -n
        return n

    def rings(self, subdiv=None):
        sub = SUBDIV if subdiv is None else subdiv
        k = len(self.secs) - 1
        out = []
        for q in range(k * sub + 1):
            t = q / float(k * sub)
            out.append([self.point(t, 2 * math.pi * j / self.n) for j in range(self.n)])
        return out


# --------------------------------------------------------------------------------------------------- Part ops
def _add_vert(bm, p):
    if p[2] < 0.0:                      # nothing of the mech goes below the ground plane (Catmull-Rom overshoot, normals at the sole)
        p = type(p)((p[0], p[1], 0.0))
    return bm.verts.new(p)


def _face(bm, vs, mi, tag=0):
    """New face with material index; `tag` marks faces that get shared/collapsed UVs: 1 = bolt head, 2 = hidden underside."""
    try:
        f = bm.faces.new(vs)
        f.material_index = mi
        if tag:
            f[bm.faces.layers.int["tag"]] = tag
        return f
    except ValueError:
        return None


def add_rings(part, rings, close_start=True, close_end=True, mat=None, tag=0):
    """Quad strips between consecutive rings (all the same length), optional fan caps."""
    bm = part.bm
    mi = part._mi(mat or part.mat)
    vr = [[_add_vert(bm, p) for p in ring] for ring in rings]
    n = len(rings[0])
    for a in range(len(vr) - 1):
        for j in range(n):
            _face(bm, [vr[a][j], vr[a][(j + 1) % n], vr[a + 1][(j + 1) % n], vr[a + 1][j]], mi, tag)
    if close_start:
        _face(bm, list(reversed(vr[0])), mi, tag)
    if close_end:
        _face(bm, vr[-1], mi, tag)
    return vr


def add_tube(part, tube, close=True, mat=None):
    return add_rings(part, tube.rings(), close, close, mat)


def add_ellipsoid(part, center, radii, rot=(0, 0, 0), lat=10, lon=20, z_cut=(-1.0, 1.0), power=2.0, mat=None, squash_back=0.0):
    """Ellipsoid (or super-ellipsoid), axis along local Z, centred at `center`, rotated by `rot` degrees. z_cut limits the latitude range
    (-1..1): (-0.3, 1.0) gives a dome with a flat underside."""
    a, b, c = radii
    secs = []
    lo, hi = z_cut
    ph0 = math.acos(max(-1.0, min(1.0, hi)))
    ph1 = math.acos(max(-1.0, min(1.0, lo)))
    for i in range(lat + 1):
        ph = ph0 + (ph1 - ph0) * i / lat
        r = max(math.sin(ph), 0.02)
        secs.append(Sec((0, 0, c * math.cos(ph)), a * r, b * r, power, shift=(0.0, squash_back * (1 - math.cos(ph)))))
    tube = Tube(secs, lon)
    M = Matrix.Translation(Vector(center)) @ hs.Euler(tuple(math.radians(x) for x in rot), "XYZ").to_matrix().to_4x4()
    rings = [[M @ p for p in ring] for ring in tube.rings()]
    add_rings(part, rings, True, True, mat)
    return tube, M


def add_capsule(part, p0, p1, r0, r1=None, n=14, power=2.0, mat=None, bulge=1.0):
    """A tapered rod with rounded ends between two points (cables, fingers, pistons' sleeves)."""
    r1 = r0 if r1 is None else r1
    p0, p1 = Vector(p0), Vector(p1)
    secs = [Sec(p0 + (p1 - p0) * 0.0, r0 * 0.3, power=power), Sec(p0 + (p1 - p0) * 0.02, r0 * 0.8, power=power)]
    for k in range(1, 6):
        t = k / 6.0
        secs.append(Sec(p0.lerp(p1, t), (r0 + (r1 - r0) * t) * (1 + 0.04 * (bulge - 1)), power=power))
    secs += [Sec(p0.lerp(p1, 0.98), r1 * 0.8, power=power), Sec(p1, r1 * 0.3, power=power)]
    add_tube(part, Tube(secs, n), True, mat)


def add_patch(part, surf, u0, u1, v0, v1, offset, thick, cham=(0.5, 0.5, 0.5, 0.5), nu=6, nv=6, mat=None, fn_point=None, fn_normal=None, grow=1.0):
    """Armour shell conforming to a surface: surf is a Tube (u = along the axis 0..1, v = angle in radians) or any object with
    point(u, v) / normal(u, v). The shell floats `offset` above the surface, is `thick` thick and has a stepped chamfer whose width
    per edge is `cham` (in the same units as u/v, relative to the patch size: u0, u1, v0, v1 sides)."""
    bm = part.bm
    mi = part._mi(mat or part.mat)

    def P(u, v, h):
        return surf.point(u, v) + surf.normal(u, v) * h

    du, dv = (u1 - u0), (v1 - v0)
    cu0, cu1, cv0, cv1 = [c * 0.18 for c in cham]
    # inner (underside) grid at `offset`, rim loop at 45 % of the thickness, top grid shrunk by the chamfer
    def grid(ua, ub, va, vb, h):
        return [[_add_vert(bm, P(ua + (ub - ua) * i / nu, va + (vb - va) * j / nv, h)) for j in range(nv + 1)] for i in range(nu + 1)]

    top = grid(u0 + du * cu0, u1 - du * cu1, v0 + dv * cv0, v1 - dv * cv1, offset + thick)
    bot = grid(u0, u1, v0, v1, offset)
    # rim: border of the full domain at mid height
    rim_pts = []
    for i in range(nu + 1):
        rim_pts.append((i, 0))
    for j in range(1, nv + 1):
        rim_pts.append((nu, j))
    for i in range(nu - 1, -1, -1):
        rim_pts.append((i, nv))
    for j in range(nv - 1, 0, -1):
        rim_pts.append((0, j))
    rim = [_add_vert(bm, P(u0 + du * i / nu, v0 + dv * j / nv, offset + thick * 0.45)) for i, j in rim_pts]
    topb = [top[i][j] for i, j in rim_pts]
    botb = [bot[i][j] for i, j in rim_pts]
    m = len(rim_pts)
    for i in range(nu):
        for j in range(nv):
            _face(bm, [top[i][j], top[i + 1][j], top[i + 1][j + 1], top[i][j + 1]], mi)
            _face(bm, [bot[i][j + 1], bot[i + 1][j + 1], bot[i + 1][j], bot[i][j]], mi)
    for k in range(m):
        k2 = (k + 1) % m
        _face(bm, [topb[k], topb[k2], rim[k2], rim[k]], mi)          # chamfer slope
        _face(bm, [rim[k], rim[k2], botb[k2], botb[k]], mi)          # side wall
    return top, bot


class Sphere:
    """Surface adapter for an ellipsoid shell (u = latitude 0..1 from the pole, v = longitude)."""

    def __init__(self, center, radii, rot=(0, 0, 0)):
        self.c = Vector(center)
        self.r = radii
        self.M = hs.Euler(tuple(math.radians(x) for x in rot), "XYZ").to_matrix()

    def point(self, u, v):
        ph = u * math.pi
        a, b, c = self.r
        p = Vector((a * math.sin(ph) * math.cos(v), b * math.sin(ph) * math.sin(v), c * math.cos(ph)))
        return self.c + self.M @ p

    def normal(self, u, v):
        ph = u * math.pi
        a, b, c = self.r
        n = Vector((math.sin(ph) * math.cos(v) / a, math.sin(ph) * math.sin(v) / b, math.cos(ph) / c))
        return (self.M @ n).normalized()


def hydraulic(part_sleeve, part_rod, a, b, r=0.9, mat_sleeve="M_DarkMetal", mat_rod="M_Hydraulic", ext=0.45, rings=2):
    """Hydraulic cylinder between a (sleeve end) and b (rod end): sleeve with collars, rod, eye brackets on both ends."""
    A, B = Vector(a), Vector(b)
    d = B - A
    ln = d.length
    dn = d.normalized()
    s_end = A + d * (0.55 * ext + 0.1)
    add_capsule(part_sleeve, A, s_end, r, r * 0.95, 12, 3.0, mat_sleeve)
    for k in range(rings):
        c = A.lerp(s_end, 0.25 + 0.45 * k / max(1, rings - 1))
        add_capsule(part_sleeve, c - dn * 0.15, c + dn * 0.15, r * 1.25, r * 1.25, 12, 3.0, mat_sleeve)
    add_capsule(part_rod, s_end - dn * 0.3, B - dn * r * 1.2, r * 0.5, r * 0.5, 10, 2.0, mat_rod)
    for end, part in ((A - dn * r * 0.9, part_sleeve), (B, part_rod)):
        # eye bracket: a short block with a cross pin
        up = Vector((0, 0, 1)) if abs(dn.z) < 0.9 else Vector((1, 0, 0))
        side = dn.cross(up).normalized()
        add_capsule(part, end - dn * r * 0.9, end + dn * r * 0.3, r * 0.75, r * 0.75, 10, 3.0, mat_sleeve)
        add_capsule(part, end - side * r * 1.1, end + side * r * 1.1, r * 0.35, r * 0.35, 8, 2.0, mat_rod)


def hose(part_cable_fn, points, radius, sag=0.8, res=6):
    """Hose through `points` with a catenary-like sag between each pair (the curve helper of hs adds the Cable_ object)."""
    pts = []
    for i in range(len(points) - 1):
        a, b = Vector(points[i]), Vector(points[i + 1])
        pts.append(tuple(a))
        mid = a.lerp(b, 0.5)
        mid.z -= sag * (b - a).length * 0.12
        pts.append(tuple(mid))
    pts.append(tuple(points[-1]))
    return part_cable_fn(pts, radius)
