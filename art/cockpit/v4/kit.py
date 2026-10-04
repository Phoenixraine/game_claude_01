"""Helpers for the v3 cockpit: panel frames, control widgets (buttons, dials, toggles, sliders, LED bars), greebles.
Blender axes: +X forward, +Y left, +Z up, eye at the origin, metres. Material classes (UV1.y, see M_Cockpit):
 0 dark metal, 1 painted grey, 2 orange paint, 3 rubber/fabric, 4 cyan display, 5 orange LED, 6 off display / black glass,
 7 red LED, 8 hazard stripes, 9 white LED, 10 chrome / brass, 11 green LED, 12 suit fabric, 13 suit armour plate, 14 glowing core (cyan hot)
"""
import math, random
from mathutils import Vector, Matrix, Euler

CLS = dict(metal=0, grey=1, orange=2, rubber=3, cyan=4, amber=5, black=6, red=7, hazard=8, white=9, chrome=10, green=11, suit=12, plate=13, core=14)


class Frame:
    """A local frame on a surface: ux along the surface, uy across (n x ux), n = outward normal. Positions are (u, v, t)."""

    def __init__(self, o, ux, n):
        self.o = Vector(o)
        self.n = Vector(n).normalized()
        ux = Vector(ux)
        ux = (ux - self.n * ux.dot(self.n)).normalized()
        self.ux = ux
        self.uy = self.n.cross(self.ux).normalized()
        self.m = Matrix((self.ux, self.uy, self.n)).transposed()
        self.rot = self.m.to_euler("XYZ")

    def pt(self, u, v, t=0.0):
        return self.o + self.ux * u + self.uy * v + self.n * t

    def box(self, b, u, v, t, sw, sh, st, cls=0, bevel=0.0, yaw=0.0):
        r = self.m
        if yaw:
            r = self.m @ Matrix.Rotation(yaw, 3, "Z")
        e = r.to_euler("XYZ")
        return b.box(self.pt(u, v, t + st / 2), (sw, sh, st), rot=tuple(e), cls=cls, bevel=bevel)

    def cyl(self, b, u, v, t0, t1, r0, r1=None, cls=0, seg=14):
        return b.cyl(self.pt(u, v, t0), self.pt(u, v, t1), r0, r1, cls=cls, seg=seg)


# --------------------------------------------------------------------------------------------------- widgets
def button(b, f, u, v, size=0.028, cls=5, h=0.014, rr=None):
    f.box(b, u, v, 0.0, size * 1.25, size * 1.25, 0.006, cls=0)
    f.box(b, u, v, 0.006, size, size, h, cls=cls, bevel=0.003 if size > 0.03 else 0.0)


def round_button(b, f, u, v, r=0.016, cls=5, h=0.012):
    f.cyl(b, u, v, 0.0, 0.006, r * 1.3, cls=0, seg=10)
    f.cyl(b, u, v, 0.006, 0.006 + h, r, cls=cls, seg=12)


def button_grid(b, f, u0, v0, nu, nv, pitch, rr, size=0.026, palette=(5, 0, 0, 5, 9, 7, 11)):
    for i in range(nu):
        for j in range(nv):
            cls = rr.choice(palette)
            if rr.random() < 0.2:
                continue
            if rr.random() < 0.3:
                round_button(b, f, u0 + i * pitch, v0 + j * pitch, size * 0.55, cls)
            else:
                button(b, f, u0 + i * pitch, v0 + j * pitch, size, cls)


def toggle(b, f, u, v, rr, lit=None):
    f.cyl(b, u, v, 0.0, 0.012, 0.016, cls=10, seg=10)
    ang = rr.choice((-0.5, 0.5))
    p0 = f.pt(u, v, 0.012)
    d = f.n * math.cos(ang) + f.uy * math.sin(ang)
    b.cyl(p0, p0 + d * 0.034, 0.005, 0.0045, cls=10, seg=8)
    b.sphere(p0 + d * 0.036, 0.007, cls=0, seg=8)
    if lit is not None:
        f.box(b, u, v + 0.03, 0.0, 0.01, 0.01, 0.005, cls=lit)


def toggle_bank(b, f, u, v, n, rr, pitch=0.045):
    f.box(b, u, v, 0.0, n * pitch + 0.02, 0.07, 0.008, cls=0, bevel=0.003)
    for i in range(n):
        toggle(b, f, u - (n - 1) * pitch / 2 + i * pitch, v, rr, lit=rr.choice((5, 11, 7, 0)))


def dial(b, f, u, v, r=0.045, rr=None, cls=4):
    f.cyl(b, u, v, 0.0, 0.016, r * 1.18, cls=0, seg=24)
    f.cyl(b, u, v, 0.016, 0.02, r, cls=cls, seg=24)
    f.cyl(b, u, v, 0.02, 0.026, r * 0.14, cls=10, seg=8)
    ang = (rr.uniform(-2.2, 2.2) if rr else 0.5)
    p0 = f.pt(u, v, 0.024)
    d = f.ux * math.cos(ang) + f.uy * math.sin(ang)
    b.box(p0 + d * r * 0.4, (r * 0.8, 0.004, 0.004), rot=tuple((Matrix((d, f.n.cross(d), f.n)).transposed()).to_euler()), cls=7, bevel=0)


def knob(b, f, u, v, r=0.022, rr=None):
    f.cyl(b, u, v, 0.0, 0.01, r * 1.4, cls=0, seg=14)
    f.cyl(b, u, v, 0.01, 0.034, r, cls=3, seg=14)
    f.box(b, u, v, 0.034, r * 1.6, 0.004, 0.003, cls=9)


def slider(b, f, u, v, length, rr, vertical=False):
    if vertical:
        f.box(b, u, v, 0.0, 0.012, length, 0.006, cls=0)
        pos = rr.uniform(-0.4, 0.4) * length
        f.box(b, u, v + pos, 0.006, 0.03, 0.018, 0.02, cls=10, bevel=0.002)
    else:
        f.box(b, u, v, 0.0, length, 0.012, 0.006, cls=0)
        pos = rr.uniform(-0.4, 0.4) * length
        f.box(b, u + pos, v, 0.006, 0.018, 0.03, 0.02, cls=10, bevel=0.002)


def led_bar(b, f, u, v, n, rr, pitch=0.014, vertical=False, cls_on=11, level=None):
    lvl = rr.randint(1, n) if level is None else level
    for i in range(n):
        cls = cls_on if i < lvl else 0
        if i > n * 0.75 and i < lvl:
            cls = 7
        uu, vv = (u, v + i * pitch) if vertical else (u + i * pitch, v)
        f.box(b, uu, vv, 0.0, 0.011 if not vertical else 0.026, 0.026 if not vertical else 0.011, 0.007, cls=cls)


def vent(b, f, u, v, w, h, n=8, horizontal=True):
    f.box(b, u, v, 0.0, w, h, 0.006, cls=0)
    for i in range(n):
        if horizontal:
            f.box(b, u, v - h / 2 + (i + 0.5) * h / n, 0.006, w * 0.9, h / n * 0.45, 0.01, cls=0)
        else:
            f.box(b, u - w / 2 + (i + 0.5) * w / n, v, 0.006, w / n * 0.45, h * 0.9, 0.01, cls=0)
    f.box(b, u, v, 0.001, w * 0.92, h * 0.92, 0.003, cls=6)


def guarded_switch(b, f, u, v, rr):
    f.box(b, u, v, 0.0, 0.06, 0.06, 0.008, cls=8)
    f.cyl(b, u, v, 0.008, 0.03, 0.016, cls=7, seg=12)
    # flip-up cover
    f.box(b, u, v + 0.012, 0.03, 0.05, 0.006, 0.026, cls=1, bevel=0.002)


def bolts(b, f, u0, v0, nu, nv, du, dv, r=0.006, cls=10):
    for i in range(nu):
        for j in range(nv):
            f.cyl(b, u0 + i * du, v0 + j * dv, 0.0, 0.006, r, cls=cls, seg=6)


def hazard_strip(b, f, u, v, w, h, t=0.0):
    f.box(b, u, v, t, w, h, 0.004, cls=8)


def plate_with_bolts(b, f, u, v, w, h, cls=1, th=0.02, rr=None, bolt=True):
    f.box(b, u, v, 0.0, w, h, th, cls=cls, bevel=0.004)
    if bolt:
        for sx in (-1, 1):
            for sy in (-1, 1):
                f.cyl(b, u + sx * (w / 2 - 0.016), v + sy * (h / 2 - 0.016), th, th + 0.006, 0.007, cls=10, seg=6)


def greeble_patch(b, f, u, v, w, h, count, rr, hmax=0.035, palette=(0, 1, 0, 0, 5, 8)):
    for _ in range(count):
        du, dv = rr.uniform(-w / 2, w / 2), rr.uniform(-h / 2, h / 2)
        sw, sh = rr.uniform(0.02, 0.09), rr.uniform(0.02, 0.07)
        t = rr.uniform(0.006, hmax)
        cls = rr.choice(palette)
        kind = rr.random()
        if kind < 0.6:
            f.box(b, u + du, v + dv, 0.0, sw, sh, t, cls=cls, bevel=0.002 if t > 0.015 else 0.0)
        elif kind < 0.85:
            f.cyl(b, u + du, v + dv, 0.0, t, min(sw, sh) * 0.5, cls=cls, seg=10)
        else:
            f.box(b, u + du, v + dv, 0.0, sw * 1.6, sh * 0.35, t, cls=cls)


def torus_pts(center, R, z, n, a0=0.0, a1=2 * math.pi):
    return [(center[0] + R * math.cos(a0 + (a1 - a0) * i / n), center[1] + R * math.sin(a0 + (a1 - a0) * i / n), z) for i in range(n + 1)]


def ring(b, center, R, z, r, n=36, cls=1, a0=0.0, a1=2 * math.pi, caps=False):
    pts = torus_pts(center, R, z, n, a0, a1)
    for p, q in zip(pts[:-1], pts[1:]):
        b.cyl(p, q, r, cls=cls, seg=8, caps=True)
    for p in pts[1:-1]:
        b.sphere(p, r * 1.02, cls=cls, seg=8)
