"""Part builders of cockpit v2 (pure numpy). Every builder returns a Part (named mesh with material slots) and may add Empties (effect sockets)."""
import math

import numpy as np

from . import geo
from .geo import MB, V, add_box, add_cyl, add_sphere, add_tube, frame_from, rot_axis, unit


class Part:
    def __init__(self, name, mb, kind, visible=True, group="", meta=None):
        self.name, self.mb, self.kind, self.visible, self.group, self.meta = name, mb, kind, visible, group, meta or {}


class Empty:
    def __init__(self, name, pos, kind, direction=(0.0, 0.0, 1.0), meta=None):
        self.name, self.pos, self.kind, self.dir, self.meta = name, np.asarray(pos, float), kind, unit(direction), meta or {}


class Panel:
    """A planar surface frame: origin o, ux/uy in the plane (uy = n x ux), n the outward normal. pt(u, v, t) in metres."""

    def __init__(self, o, ux, n):
        self.o = np.asarray(o, float)
        self.n = unit(n)
        ux = np.asarray(ux, float)
        self.ux = unit(ux - self.n * float(np.dot(ux, self.n)))
        self.uy = unit(np.cross(self.n, self.ux))
        self.R = np.stack([self.ux, self.uy, self.n], axis=1)

    def pt(self, u, v, t=0.0):
        return self.o + self.ux * u + self.uy * v + self.n * t

    @staticmethod
    def from_axes(o, ux, uy):
        """Panel whose normal is ux x uy (outward = towards whoever looks at it)."""
        return Panel(o, ux, np.cross(np.asarray(ux, float), np.asarray(uy, float)))


# ------------------------------------------------------------------------------------------------------------------ pipes
def pipe_part(name, path, radius, rng, steam=False, valve=None):
    """Hose / pipe with an insulation sleeve, flanges with bolts, clamps and an optional valve wheel."""
    mb = MB(["M_Pipe", "M_Insulation", "M_Metal", "M_MetalDark", "M_PaintOrange"])
    path = np.asarray(path, float)
    L = geo.path_length(path)
    seg = 6 if radius < 0.02 else 8 if radius < 0.04 else 10 if radius < 0.07 else 12
    # resample to ~7 cm steps so bends stay smooth
    n = max(4, int(L / 0.07) + 1)
    pts = np.array([geo.point_on(path, L * k / (n - 1))[0] for k in range(n)])
    add_tube(mb, pts, radius, seg=seg, mat="M_Pipe")
    # insulation sleeves
    if radius >= 0.025 and rng.random() < 0.6:
        for _ in range(rng.randint(1, 2)):
            s0 = rng.uniform(0.1, max(0.12, L - 0.5))
            s1 = min(L - 0.05, s0 + rng.uniform(0.25, 0.6))
            if s1 - s0 > 0.1:
                sp = geo.sub_path(pts, s0, s1, 0.06)
                add_tube(mb, sp, np.full(len(sp), radius * 1.38), seg=seg, mat="M_Insulation")
    # flanges with bolts
    nf = max(1, int(L / 0.55))
    for k in range(nf):
        s = L * (k + 0.5 + rng.uniform(-0.15, 0.15)) / nf
        p, t = geo.point_on(pts, s)
        add_cyl(mb, p - t * 0.014, p + t * 0.014, radius * 1.45, radius * 1.45, seg=max(8, seg), mat="M_Metal")
        F = frame_from(t)
        for b in range(4):
            a = math.pi / 2 * b + math.pi / 4
            q = p + (F[:, 1] * math.cos(a) + F[:, 2] * math.sin(a)) * radius * 1.45
            add_box(mb, q, (0.012, 0.01, 0.01), F, "M_MetalDark")
    # clamps
    nc = int(L / 0.9)
    for k in range(nc):
        s = L * (k + 0.5) / max(1, nc)
        p, t = geo.point_on(pts, s)
        add_cyl(mb, p - t * 0.01, p + t * 0.01, radius * 1.22, radius * 1.22, seg=max(8, seg), mat="M_MetalDark")
    if valve is None:
        valve = radius >= 0.035 and rng.random() < 0.55
    if valve:
        s = L * rng.uniform(0.35, 0.65)
        p, t = geo.point_on(pts, s)
        F = frame_from(t)
        up = F[:, 2]
        add_cyl(mb, p, p + up * (radius * 1.2 + 0.05), 0.012, 0.012, seg=8, mat="M_Metal")
        top = p + up * (radius * 1.2 + 0.05)
        for a in range(4):
            ang = math.pi / 4 * a
            d = F[:, 1] * math.cos(ang) + t * math.sin(ang)
            add_cyl(mb, top - d * 0.045, top + d * 0.045, 0.006, 0.006, seg=6, mat="M_PaintOrange")
    return Part(name, mb, "Pipe", meta={"radius": round(radius, 4), "length": round(L, 3), "steam": steam})


def pipe_burst_part(name, path, radius, rng):
    """The same pipe with a torn gap (0.10-0.16 m): flared petals, ragged insulation, hanging clamp. Returns (Part, leak position, leak direction)."""
    mb = MB(["M_Pipe", "M_Insulation", "M_Metal", "M_MetalDark", "M_PaintOrange", "M_Scorch"])
    path = np.asarray(path, float)
    L = geo.path_length(path)
    seg = 6 if radius < 0.02 else 8 if radius < 0.04 else 10 if radius < 0.07 else 12
    n = max(4, int(L / 0.07) + 1)
    pts = np.array([geo.point_on(path, L * k / (n - 1))[0] for k in range(n)])
    s_mid = L * rng.uniform(0.35, 0.65)
    gap = rng.uniform(0.10, 0.16)
    a = geo.sub_path(pts, 0.0, s_mid - gap / 2, 0.06)
    b = geo.sub_path(pts, s_mid + gap / 2, L, 0.06)
    add_tube(mb, a, radius, seg=seg, mat="M_Pipe", caps=(True, False))
    add_tube(mb, b, radius, seg=seg, mat="M_Pipe", caps=(False, True))
    for end, sgn in ((a[-1], 1), (b[0], -1)):
        pt, t = (a[-1], unit(a[-1] - a[-2])) if sgn == 1 else (b[0], unit(b[0] - b[1]))
        F = frame_from(t)
        petals = 6
        for k in range(petals):
            ang = 2 * math.pi * k / petals + rng.uniform(-0.2, 0.2)
            d = F[:, 1] * math.cos(ang) + F[:, 2] * math.sin(ang)
            ang2 = 2 * math.pi * (k + 1) / petals
            d2 = F[:, 1] * math.cos(ang2) + F[:, 2] * math.sin(ang2)
            tip = pt + t * rng.uniform(0.02, 0.06) + d * radius * rng.uniform(1.5, 2.0)
            mb.tri(mb.vert(pt + d * radius), mb.vert(pt + d2 * radius), mb.vert(tip), "M_Pipe")
            mb.tri(mb.vert(pt + d * radius), mb.vert(tip), mb.vert(pt + d2 * radius), "M_Pipe")      # two-sided petal
        for k in range(5):                                         # scorched / ragged insulation stubs
            ang = rng.uniform(0, 2 * math.pi)
            d = F[:, 1] * math.cos(ang) + F[:, 2] * math.sin(ang)
            add_box(mb, pt + d * radius * 1.3 - t * 0.02, (0.04, 0.012, 0.03), frame_from(d, t), "M_Scorch")
    leak_p, t = geo.point_on(pts, s_mid)
    F = frame_from(t)
    ang = rng.uniform(0, 2 * math.pi)
    leak_dir = unit(F[:, 1] * math.cos(ang) + F[:, 2] * math.sin(ang))
    return Part(name, mb, "Pipe_Burst", visible=False, meta={"radius": round(radius, 4)}), leak_p, leak_dir


# ------------------------------------------------------------------------------------------------------------------ wires
def wire_path(top, bottom, sag, rng, wobble=0.03, n=14):
    top, bottom = np.asarray(top, float), np.asarray(bottom, float)
    pts = []
    side = unit(np.cross(bottom - top, [0.0, 0.0, 1.0]) + np.array([1e-3, 0, 0]))
    ph = rng.uniform(0, 6.28)
    for k in range(n):
        f = k / (n - 1)
        p = top + (bottom - top) * f
        p = p + np.array([0, 0, -sag * 4.0 * f * (1 - f)]) + side * wobble * math.sin(ph + f * 5.0) * f
        pts.append(p)
    return np.array(pts)


def wire_part(name, path, radius, rng, bundle=False):
    mb = MB(["M_Wire", "M_WireTape", "M_Copper", "M_Metal"])
    path = np.asarray(path, float)
    L = geo.path_length(path)
    n = max(5, int(L / 0.08) + 1)
    pts = np.array([geo.point_on(path, L * k / (n - 1))[0] for k in range(n)])
    if bundle:
        tan, nor = geo.tube_frames(pts)
        for c in range(3):
            off = []
            for i in range(n):
                b = np.cross(tan[i], nor[i])
                ang = 2 * math.pi * c / 3 + i * 0.35
                off.append(pts[i] + (nor[i] * math.cos(ang) + b * math.sin(ang)) * radius * 0.55)
            add_tube(mb, np.array(off), radius * 0.6, seg=6, mat="M_Wire")
        for s in (0.08 * L, 0.5 * L, 0.92 * L):                       # tape / cable ties
            p, t = geo.point_on(pts, s)
            add_cyl(mb, p - t * 0.015, p + t * 0.015, radius * 1.75, radius * 1.75, seg=8, mat="M_WireTape")
    else:
        add_tube(mb, pts, radius, seg=5, mat="M_Wire")
        p, t = geo.point_on(pts, L - 0.03)
        add_cyl(mb, p, p + t * 0.03, radius * 1.5, radius * 1.5, seg=6, mat="M_Metal")          # terminal
        p, t = geo.point_on(pts, 0.04)
        add_cyl(mb, p - t * 0.02, p + t * 0.02, radius * 1.8, radius * 1.8, seg=6, mat="M_WireTape")
    return Part(name, mb, "Wire", meta={"radius": round(radius, 4), "length": round(L, 3), "bundle": bundle}), pts


def wire_snapped_part(name, pts, radius, rng, bundle=False):
    """Wire torn off at 45-70 % of its length: frayed copper strands. Returns (Part, break point, break direction)."""
    mb = MB(["M_Wire", "M_WireTape", "M_Copper", "M_Metal"])
    L = geo.path_length(pts)
    cut = L * rng.uniform(0.45, 0.7)
    head = geo.sub_path(pts, 0.0, cut, 0.07)
    if bundle:
        for c in range(3):
            tan, nor = geo.tube_frames(head)
            off = []
            for i in range(len(head)):
                b = np.cross(tan[i], nor[i])
                ang = 2 * math.pi * c / 3 + i * 0.35
                off.append(head[i] + (nor[i] * math.cos(ang) + b * math.sin(ang)) * radius * 0.55)
            add_tube(mb, np.array(off), radius * 0.6, seg=6, mat="M_Wire")
    else:
        add_tube(mb, head, radius, seg=5, mat="M_Wire")
    end, t = head[-1], unit(head[-1] - head[-2])
    F = frame_from(t)
    for k in range(4):
        ang = 2 * math.pi * k / 4 + rng.uniform(-0.4, 0.4)
        d = unit(t * 0.5 + (F[:, 1] * math.cos(ang) + F[:, 2] * math.sin(ang)) * rng.uniform(0.5, 1.0) + np.array([0, 0, -0.5]))
        strand = np.array([end, end + d * rng.uniform(0.03, 0.06), end + d * rng.uniform(0.06, 0.1)])
        add_tube(mb, strand, max(0.0012, radius * 0.25), seg=4, mat="M_Copper")
    return Part(name, mb, "Wire_Snapped", visible=False, meta={"radius": round(radius, 4)}), end, t


# ------------------------------------------------------------------------------------------------------------------ controls
def button_part(name, panel, u, v, kind, rng):
    """One control in the panel frame: kinds push_square, push_round, toggle, rocker, lever, selector."""
    mb = MB(["M_Button", "M_Metal", "M_MetalDark", "M_PaintOrange"])
    R = panel.R
    o = panel.pt(u, v, 0.0)
    P = lambda x, y, z: o + R @ np.array([x, y, z])
    if kind == "push_square":
        add_box(mb, P(0, 0, 0.003), (0.04, 0.04, 0.006), R, "M_MetalDark")
        add_box(mb, P(0, 0, 0.012), (0.028, 0.028, 0.012), R, "M_Button", chamfer=0.003)
    elif kind == "push_round":
        add_cyl(mb, P(0, 0, 0), P(0, 0, 0.006), 0.022, 0.022, seg=12, mat="M_MetalDark")
        add_cyl(mb, P(0, 0, 0.006), P(0, 0, 0.02), 0.015, 0.0135, seg=12, mat="M_Button")
    elif kind == "toggle":
        add_cyl(mb, P(0, 0, 0), P(0, 0, 0.012), 0.016, 0.016, seg=8, mat="M_Metal")
        ang = rng.choice((-0.5, 0.5))
        d = np.array([math.sin(ang), 0, math.cos(ang)])
        add_cyl(mb, P(0, 0, 0.012), P(*(d * 0.04 + np.array([0, 0, 0.012]))), 0.005, 0.0045, seg=6, mat="M_Metal")
        add_sphere(mb, P(*(d * 0.043 + np.array([0, 0, 0.012]))), 0.008, seg=6, mat="M_MetalDark")
    elif kind == "rocker":
        add_box(mb, P(0, 0, 0.004), (0.036, 0.05, 0.008), R, "M_MetalDark")
        tilt = rot_axis(panel.ux, rng.choice((-0.25, 0.25)))
        add_box(mb, P(0, 0, 0.016), (0.028, 0.042, 0.012), tilt @ R, "M_Button", chamfer=0.003)
    elif kind == "lever":
        add_box(mb, P(0, 0, 0.005), (0.06, 0.05, 0.01), R, "M_MetalDark")
        add_cyl(mb, P(-0.012, 0, 0.012), P(0.012, 0, 0.012), 0.01, 0.01, seg=8, mat="M_Metal")
        ang = rng.uniform(-0.6, 0.6)
        d = np.array([0.0, math.sin(ang), math.cos(ang)])
        h = rng.uniform(0.11, 0.2)
        add_cyl(mb, P(0, 0, 0.012), P(*(d * h + np.array([0, 0, 0.012]))), 0.006, 0.0055, seg=6, mat="M_Metal")
        add_sphere(mb, P(*(d * (h + 0.012) + np.array([0, 0, 0.012]))), 0.014, seg=8, mat="M_PaintOrange")
    else:                                                       # selector knob
        add_cyl(mb, P(0, 0, 0), P(0, 0, 0.008), 0.03, 0.03, seg=12, mat="M_MetalDark")
        add_cyl(mb, P(0, 0, 0.008), P(0, 0, 0.026), 0.02, 0.018, seg=12, mat="M_Metal")
        a = rng.uniform(0, 6.28)
        add_box(mb, P(math.cos(a) * 0.012, math.sin(a) * 0.012, 0.027), (0.016, 0.004, 0.004), rot_axis(panel.n, a) @ R, "M_PaintOrange")
    return Part(name, mb, "Btn", meta={"type": kind})


def cap_part(name, panel, u, v):
    """Safety flip cover over a switch."""
    mb = MB(["M_PaintOrange", "M_MetalDark"])
    R = panel.R
    o = panel.pt(u, v, 0.0)
    add_box(mb, o + R @ np.array([0, 0.0, 0.004]), (0.05, 0.06, 0.008), R, "M_MetalDark")
    tilt = rot_axis(panel.ux, -0.9)
    add_box(mb, o + R @ np.array([0, 0.03, 0.03]), (0.046, 0.058, 0.004), tilt @ R, "M_PaintOrange", chamfer=0.0015)
    return Part(name, mb, "Cap")


def dial_part(name, panel, u, v, r, rng):
    mb = MB(["M_MetalDark", "M_Metal", "M_Lamp", "M_PaintOrange"])
    o = panel.pt(u, v, 0.0)
    R = panel.R
    P = lambda x, y, z: o + R @ np.array([x, y, z])
    add_cyl(mb, P(0, 0, 0), P(0, 0, 0.016), r * 1.2, r * 1.2, seg=20, mat="M_MetalDark")
    add_cyl(mb, P(0, 0, 0.016), P(0, 0, 0.018), r * 0.95, r * 0.95, seg=20, mat="M_Lamp")
    for k in range(10):
        a = math.radians(-130 + 260 * k / 9)
        add_box(mb, P(math.cos(a) * r * 0.8, math.sin(a) * r * 0.8, 0.019), (0.004, 0.012, 0.002), rot_axis(panel.n, a + math.pi / 2) @ R, "M_Metal")
    a = math.radians(rng.uniform(-110, 110))
    add_box(mb, P(math.cos(a) * r * 0.4, math.sin(a) * r * 0.4, 0.021), (r * 0.8, 0.004, 0.003), rot_axis(panel.n, a) @ R, "M_PaintOrange")
    add_cyl(mb, P(0, 0, 0.019), P(0, 0, 0.026), 0.008, 0.008, seg=8, mat="M_Metal")
    return Part(name, mb, "Dial")


def slider_part(name, panel, u, v, length, rng):
    mb = MB(["M_MetalDark", "M_Metal", "M_PaintOrange"])
    o = panel.pt(u, v, 0.0)
    R = panel.R
    P = lambda x, y, z: o + R @ np.array([x, y, z])
    add_box(mb, P(0, 0, 0.003), (0.02, length, 0.006), R, "M_MetalDark")
    add_box(mb, P(0, 0, 0.008), (0.006, length * 0.9, 0.004), R, "M_Metal")
    y = rng.uniform(-0.4, 0.4) * length
    add_box(mb, P(0, y, 0.014), (0.026, 0.02, 0.014), R, "M_PaintOrange", chamfer=0.002)
    return Part(name, mb, "Slider")


# ------------------------------------------------------------------------------------------------------------------ monitors, lamps
def monitor_part(name, panel, u, v, shape, w, h, depth, rng):
    """Monitor housing + a screen with its own 0..1 UV (slot M_Monitor). Shapes: flat, crt, strip, radar, curved."""
    mb = MB(["M_MonitorFrame", "M_Monitor", "M_Metal"])
    R = panel.R
    o = panel.pt(u, v, 0.0)
    P = lambda x, y, z: o + R @ np.array([x, y, z])
    if shape == "radar":
        r = w / 2.0
        add_cyl(mb, P(0, 0, 0), P(0, 0, depth), r * 1.18, r * 1.18, seg=24, mat="M_MonitorFrame")
        add_cyl(mb, P(0, 0, depth), P(0, 0, depth + 0.012), r * 1.18, r * 1.0, seg=24, mat="M_Metal", caps=(False, False))
        zc = depth + 0.0125
        c = mb.vert(P(0, 0, zc))
        seg = 32
        for k in range(seg):
            a0, a1 = 2 * math.pi * k / seg, 2 * math.pi * (k + 1) / seg
            p0, p1 = P(math.cos(a0) * r, math.sin(a0) * r, zc), P(math.cos(a1) * r, math.sin(a1) * r, zc)
            mb.tri(c, mb.vert(p0), mb.vert(p1), "M_Monitor", [(0.5, 0.5), (0.5 + 0.5 * math.cos(a0), 0.5 + 0.5 * math.sin(a0)), (0.5 + 0.5 * math.cos(a1), 0.5 + 0.5 * math.sin(a1))])
        return Part(name, mb, "Mon", meta={"shape": shape, "screen_m": [round(w, 3), round(w, 3)]}), P(0, 0, zc)
    body_d = depth
    add_box(mb, P(0, 0, body_d / 2.0), (w + 0.04, h + 0.04, body_d), R, "M_MonitorFrame", chamfer=0.006)
    zc = body_d + 0.002
    if shape in ("flat", "strip"):
        mb.quad(P(-w / 2, -h / 2, zc), P(w / 2, -h / 2, zc), P(w / 2, h / 2, zc), P(-w / 2, h / 2, zc), "M_Monitor", [(0, 0), (1, 0), (1, 1), (0, 1)])
    elif shape == "crt":                                               # bulged glass: 6 x 6 grid, centre pushed out
        nx = ny = 6
        bulge = 0.025
        grid = [[P(-w / 2 + w * i / nx, -h / 2 + h * j / ny, zc + bulge * (1 - ((2 * i / nx - 1) ** 2 + (2 * j / ny - 1) ** 2) / 2.0)) for i in range(nx + 1)] for j in range(ny + 1)]
        for j in range(ny):
            for i in range(nx):
                mb.quad(grid[j][i], grid[j][i + 1], grid[j + 1][i + 1], grid[j + 1][i], "M_Monitor", [(i / nx, j / ny), ((i + 1) / nx, j / ny), ((i + 1) / nx, (j + 1) / ny), (i / nx, (j + 1) / ny)])
    else:                                                              # curved wide: cylindrical patch
        nx, ny = 10, 2
        arc = 0.6
        grid = []
        for j in range(ny + 1):
            row = []
            for i in range(nx + 1):
                th = (i / nx - 0.5) * arc
                row.append(P(math.sin(th) * (w / arc), -h / 2 + h * j / ny, zc + (1 - math.cos(th)) * (w / arc) * -1.0 + 0.0))
            grid.append(row)
        for j in range(ny):
            for i in range(nx):
                mb.quad(grid[j][i], grid[j][i + 1], grid[j + 1][i + 1], grid[j + 1][i], "M_Monitor", [(i / nx, j / ny), ((i + 1) / nx, j / ny), ((i + 1) / nx, (j + 1) / ny), (i / nx, (j + 1) / ny)])
    return Part(name, mb, "Mon", meta={"shape": shape, "screen_m": [round(w, 3), round(h, 3)]}), P(0, 0, zc)


def lamp_part(name, panel, u, v, kind, rng):
    """Indicator lamp: a dome on a ring (slot M_Lamp for the lens). kind Warn / Ok only labels the class."""
    mb = MB(["M_Metal", "M_Lamp"])
    o = panel.pt(u, v, 0.0)
    R = panel.R
    add_cyl(mb, o, o + panel.n * 0.006, 0.014, 0.014, seg=10, mat="M_Metal")
    dome = MB(["M_Lamp"])
    add_sphere(dome, (0, 0, 0), 0.0105, seg=8, mat="M_Lamp", top_only=True)         # built around +Z, rotated onto the panel normal
    mb.merge(dome.transform(R=panel.R, t=o + panel.n * 0.006))
    return Part(name, mb, "Lamp", meta={"class": kind})


def beacon_part(name, base, axis, rng):
    mb = MB(["M_Metal", "M_Lamp", "M_PaintOrange"])
    base = np.asarray(base, float)
    axis = unit(axis)
    add_cyl(mb, base, base + axis * 0.03, 0.06, 0.055, seg=14, mat="M_Metal")
    add_cyl(mb, base + axis * 0.03, base + axis * 0.07, 0.046, 0.046, seg=14, mat="M_Lamp")
    top = base + axis * 0.07
    F = frame_from(axis)
    for k in range(10):
        a = 2 * math.pi * k / 10
        mb.tri(mb.vert(top + (F[:, 1] * math.cos(a) + F[:, 2] * math.sin(a)) * 0.046), mb.vert(top + (F[:, 1] * math.cos(a + 0.628) + F[:, 2] * math.sin(a + 0.628)) * 0.046),
               mb.vert(top + axis * 0.04), "M_Lamp")
    add_box(mb, base + axis * 0.05 + F[:, 1] * 0.0, (0.01, 0.07, 0.01), F, "M_PaintOrange")        # the rotating reflector bar
    return Part(name, mb, "AlarmBeacon")


def strobe_part(name, panel, u, v, w, h):
    mb = MB(["M_MetalDark", "M_Lamp"])
    R = panel.R
    o = panel.pt(u, v, 0.0)
    add_box(mb, o + panel.n * 0.006, (w + 0.02, h + 0.02, 0.012), R, "M_MetalDark", chamfer=0.002)
    mb.quad(panel.pt(u - w / 2, v - h / 2, 0.013), panel.pt(u + w / 2, v - h / 2, 0.013), panel.pt(u + w / 2, v + h / 2, 0.013), panel.pt(u - w / 2, v + h / 2, 0.013), "M_Lamp", [(0, 0), (1, 0), (1, 1), (0, 1)])
    return Part(name, mb, "StrobePanel")


# ------------------------------------------------------------------------------------------------------------------ glass, decals, structure
def glass_part(name, center, radius, th0, th1, z0, z1, nu=24, nv=6, axis_y=0.0):
    """Cylindrical glass patch around a vertical axis through (cx, cy): x = cx + R sin th, y = cy - R cos th. UV 0..1 over the patch (u = angle, v = height)."""
    mb = MB(["M_Glass"])
    cx, cy = center
    grid = []
    for j in range(nv + 1):
        z = z0 + (z1 - z0) * j / nv
        grid.append([np.array([cx + radius * math.sin(th0 + (th1 - th0) * i / nu), cy - radius * math.cos(th0 + (th1 - th0) * i / nu), z]) for i in range(nu + 1)])
    for j in range(nv):
        for i in range(nu):
            mb.quad(grid[j][i], grid[j][i + 1], grid[j + 1][i + 1], grid[j + 1][i], "M_Glass", [(i / nu, j / nv), ((i + 1) / nu, j / nv), ((i + 1) / nu, (j + 1) / nv), (i / nu, (j + 1) / nv)])
    return Part(name, mb, "Glass")


def flat_glass_part(name, p0, p1, p2, p3):
    mb = MB(["M_Glass"])
    mb.quad(p0, p1, p2, p3, "M_Glass", [(0, 0), (1, 0), (1, 1), (0, 1)])
    return Part(name, mb, "Glass")


def decal_part(name, panel, u, v, w, h, rot=0.0):
    mb = MB(["M_Decal_Scorch"])
    a = rot
    ca, sa = math.cos(a), math.sin(a)
    corners = [(-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)]
    pts = [panel.pt(u + x * ca - y * sa, v + x * sa + y * ca, 0.003) for x, y in corners]
    mb.quad(pts[0], pts[1], pts[2], pts[3], "M_Decal_Scorch", [(0, 0), (1, 0), (1, 1), (0, 1)])
    return Part(name, mb, "Scorch_Decal")


def beam_part(name, p0, p1, w, d, hint, mat="M_Frame", chamfer=0.004, kind="Frame"):
    mb = MB([mat])
    p0, p1 = np.asarray(p0, float), np.asarray(p1, float)
    F = frame_from(p1 - p0, hint)
    add_box(mb, (p0 + p1) / 2, (float(np.linalg.norm(p1 - p0)), w, d), F, mat, chamfer=chamfer)
    return Part(name, mb, kind)


def block_part(name, center, size, R=None, mat="M_Frame", chamfer=0.01, kind="Console"):
    mb = MB([mat])
    add_box(mb, center, size, R, mat, chamfer=chamfer)
    return Part(name, mb, kind)
