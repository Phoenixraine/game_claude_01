"""Legs: thigh (hip ball joint, hydraulic bundle), knee fork, shin/boot with exposed pistons, ski foot with treads."""
import math

from mathutils import Vector

from . import forms, hs, kit
from .forms import Sec
from .kit import vt, plate


def L3(a, b, t):
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t)


def pts_on(surf, pairs, h):
    return [surf.point(u, math.radians(v)) + surf.normal(u, math.radians(v)) * h for u, v in pairs]


def build_leg(P, s):
    side = "l" if s > 0 else "r"
    Z = "Leg" + side.upper()
    lx = s * P["leg_x"]
    H = (lx, P["hip_y"], P["hip_z"])
    K = (lx, P["knee_y"], P["knee_z"])
    A = (lx, P["ankle_y"], P["ankle_z"])
    A_ = (lambda a: a) if s > 0 else (lambda a: (180.0 - a) % 360.0)

    def V(a, b):
        return (A_(a), A_(b))

    # ------------------------------------------------------------- thigh core (graphite) + armour
    ths = vt([Sec(L3(H, K, 0.0), 4.9, 5.6, 2.6), Sec(L3(H, K, 0.2), 5.5, 6.3, 2.8), Sec(L3(H, K, 0.55), 5.2, 6.0, 2.8), Sec(L3(H, K, 0.9), 4.4, 5.0, 2.6),
              Sec(L3(H, K, 1.0), 4.0, 4.4, 2.4)], 32)
    body = hs.body("thigh_" + side, Z, "M_Graphite")
    forms.add_tube(body, ths)
    # upper-leg bundle: knee-side sleeve rings
    for t in (0.35, 0.5, 0.65):
        c = L3(H, K, t)
        kit.ring(body, (c[0], c[1] + 0.2, c[2]), (0.0, K[1] - H[1], K[2] - H[2]), 6.1 - 0.8 * abs(t - 0.5), 5.2, 0.55, 32, "M_DarkMetal")
    body.commit()
    jt = hs.joint("thigh_" + side, Z, "M_DarkMetal")
    forms.add_ellipsoid(jt, H, (6.4, 6.4, 6.4), lat=10, lon=20, mat="M_DarkMetal")
    kit.ring(jt, (H[0] + s * 0.0, H[1], H[2]), (1, 0, 0), 7.0, 5.0, 1.2, 28, "M_Hydraulic")
    jt.commit()

    ob = ths
    plate(Z, "thigh_" + side, ob, (0.14, 0.80), V(238, 302), 0.9, 1.2, "stepped", "M_CeramicGray", (1, 1, 1, 1.3), 5, 7, taper=0.12, crown=0.7, bolts=6, seed=1,
          panel=dict(inset=0.2, mat="M_Graphite", th=0.4))
    plate(Z, "thigh_" + side, ob, (0.12, 0.86), V(-38, 36), 0.9, 1.1, "ribbed", "M_CeramicGray", (1, 1, 1, 1), 6, 6, taper=0.18, crown=0.5, bolts=4, seed=2, ribs=3)
    plate(Z, "thigh_" + side, ob, (0.24, 0.76), V(146, 214), 0.8, 0.9, "vent", "M_CeramicGray", (1, 1, 1, 1), 4, 5, crown=0.3, seed=3, vent=4, bolts=4)
    plate(Z, "thigh_" + side, ob, (0.18, 0.74), V(56, 124), 0.8, 1.0, "stepped", "M_CeramicGray", (1, 1, 1, 1), 4, 5, taper=0.2, crown=0.4, seed=4, bolts=4,
          panel=dict(inset=0.22, mat="M_Graphite", th=0.35))
    plate(Z, "thigh_" + side, ob, (0.0, 0.2), V(190, 350), 1.3, 1.3, "wedge", "M_CeramicGray", (0.4, 1.8, 1, 1), 3, 10, taper=0.1, crown=0.5, seed=5, bolts=6,
          accent=((0.35, 0.8), (0.08, 0.3)))
    plate(Z, "thigh_" + side, ob, (0.78, 0.97), V(232, 308), 1.1, 1.3, "wedge", "M_CeramicGray", (1.8, 0.6, 1, 1), 3, 6, taper=0.4, crown=0.7, seed=6, bolts=4)
    plate(Z, "thigh_" + side, ob, (0.26, 0.7), V(306, 338), 1.1, 0.9, "shell", "M_CeramicGray", (1, 1, 1, 1), 4, 3, taper=-0.1, crown=0.3, seed=7, bolts=4)
    plate(Z, "thigh_" + side, ob, (0.3, 0.68), V(202, 236), 1.1, 0.8, "shell", "M_AccentOrange", (1, 1, 1, 1), 3, 3, crown=0.2, seed=8)

    # --- hydraulics behind the thigh (Inner)
    ip = hs.inner(Z, "thigh_" + side, "M_DarkMetal")
    rp = hs.inner(Z, "thigh_" + side, "M_Hydraulic")
    for k, dx in enumerate((-2.2, 2.2)):
        a = (H[0] + dx, H[1] + 8.8, H[2] - 3.0)
        b = (K[0] + dx * 0.8, K[1] + 8.4, K[2] + 3.0)
        kit.piston(ip, rp, a, b, 1.15, 0.6, 3)
    ip.commit()
    rp.commit()
    ic = hs.inner(Z, "thigh_" + side, "M_DarkMetal")
    for k in range(2):
        a = Vector(L3(H, K, 0.1)) + Vector((s * (k * 2 - 1) * 4.0, -3.5, 0))
        b = Vector(L3(H, K, 0.85)) + Vector((s * (k * 2 - 1) * 3.5, -3.0, 0))
        forms.add_capsule(ic, a, b, 0.7, 0.7, 10, 2.0)
    ic.commit()
    for k, dx in enumerate((-1.0, 1.0)):
        hs.cable_curve(Z, "thigh_" + side, [(H[0] + dx * 3, H[1] + 2, H[2] - 3), L3(H, K, 0.3), L3(H, K, 0.55), (K[0] + dx * 2, K[1] + 4.5, K[2] + 4)], 0.45)
        # displace the cable behind the thigh
    # ------------------------------------------------------------- knee fork + shin
    kj = hs.joint("shin_" + side, Z, "M_DarkMetal")
    forms.add_ellipsoid(kj, K, (4.6, 4.8, 4.8), lat=10, lon=20, mat="M_DarkMetal")
    for sx in (-1, 1):
        kit.ring(kj, (K[0] + sx * 5.0, K[1], K[2]), (1, 0, 0), 3.8, 2.4, 0.9, 24, "M_Hydraulic")
    kj.commit()
    shs = vt([Sec(L3(K, A, 0.0), 4.3, 4.9, 2.4), Sec(L3(K, A, 0.12), 4.9, 5.9, 2.7), Sec(L3(K, A, 0.4), 4.8, 6.4, 2.8, shift=(0, 0.8)),
              Sec(L3(K, A, 0.7), 4.4, 5.6, 2.7, shift=(0, 0.5)), Sec(L3(K, A, 0.92), 4.4, 5.3, 2.6), Sec(L3(K, A, 1.0), 4.1, 4.8, 2.4)], 32)
    sb = hs.body("shin_" + side, Z, "M_Graphite")
    forms.add_tube(sb, shs)
    sb.commit()
    plate(Z, "shin_" + side, shs, (0.62, 0.96), V(236, 304), 0.9, 1.3, "stepped", "M_CeramicGray", (1.2, 1, 1, 1), 5, 7, taper=0.3, crown=0.8, seed=11, bolts=6,
          panel=dict(inset=0.2, mat="M_Graphite", th=0.4))
    plate(Z, "shin_" + side, shs, (0.04, 0.38), V(232, 308), 0.9, 1.4, "stepped", "M_CeramicGray", (1, 1.2, 1, 1), 5, 7, taper=-0.2, crown=0.8, seed=12, bolts=8,
          panel=dict(inset=0.18, mat="M_Graphite", th=0.4), accent=((0.6, 0.9), (0.2, 0.5)))
    plate(Z, "shin_" + side, shs, (0.06, 0.9), V(-42, 40), 0.9, 1.3, "ribbed", "M_CeramicGray", (1, 1, 1, 1), 7, 6, taper=-0.1, crown=0.6, seed=13, bolts=8, ribs=4)
    plate(Z, "shin_" + side, shs, (0.1, 0.86), V(140, 222), 0.9, 1.1, "vent", "M_CeramicGray", (1, 1, 1, 1), 6, 6, crown=0.4, seed=14, vent=5, bolts=4)
    plate(Z, "shin_" + side, shs, (0.16, 0.9), V(52, 128), 0.9, 1.5, "stepped", "M_CeramicGray", (1, 1, 1, 1), 6, 6, crown=1.0, seed=15, bolts=6,
          panel=dict(inset=0.2, mat="M_Graphite", th=0.4))
    plate(Z, "shin_" + side, shs, (0.0, 0.1), V(0, 360), 1.2, 1.1, "shell", "M_DarkMetal", (1, 1, 1, 1), 1, 24, crown=0.0, seed=16, bolts=0)
    plate(Z, "shin_" + side, shs, (0.44, 0.52), V(240, 300), 1.8, 1.0, "shell", "M_AccentOrange", (1, 1, 1, 1), 2, 6, crown=0.4, seed=17, bolts=4)
    plate(Z, "shin_" + side, shs, (0.4, 0.62), V(-60, -20), 1.3, 0.9, "wedge", "M_CeramicGray", (1, 1, 1, 1), 3, 3, taper=0.3, crown=0.3, seed=18)
    # exposed pistons on the shin front (Inner)
    ip = hs.inner(Z, "shin_" + side, "M_DarkMetal")
    rp = hs.inner(Z, "shin_" + side, "M_Hydraulic")
    for k, dx in enumerate((-2.6, 0.0, 2.6)):
        a = Vector(L3(K, A, 0.62)) + Vector((dx, -4.9 - (0.8 if k == 1 else 0), 0))
        b = Vector(L3(K, A, 0.18)) + Vector((dx, -4.9 - (0.8 if k == 1 else 0), 0))
        kit.piston(ip, rp, a, b, 1.05 + (0.15 if k == 1 else 0), 0.55, 2)
    ip.commit()
    rp.commit()
    # ------------------------------------------------------------- ankle + ski foot
    aj = hs.joint("foot_" + side, Z, "M_DarkMetal")
    forms.add_ellipsoid(aj, A, (4.1, 3.8, 3.8), lat=8, lon=16, mat="M_DarkMetal")
    kit.ring(aj, (A[0] + s * 4.9, A[1], A[2]), (1, 0, 0), 3.6, 2.0, 0.8, 20, "M_Hydraulic")
    kit.ring(aj, (A[0] - s * 4.9, A[1], A[2]), (1, 0, 0), 3.6, 2.0, 0.8, 20, "M_Hydraulic")
    aj.commit()
    fy = lambda y: y
    fts = Sec
    foot = kit.Tube([Sec((lx, 6.6, 1.7), 4.4, 1.6, 2.4), Sec((lx, 3.0, 2.6), 5.8, 2.6, 2.8), Sec((lx, -3.0, 2.6), 6.2, 2.6, 3.0),
                     Sec((lx, -8.5, 2.1), 5.8, 2.0, 3.0), Sec((lx, -13.5, 1.2), 4.0, 1.2, 2.6)], 28, ref=(1, 0, 0))
    fb = hs.body("foot_" + side, Z, "M_DarkMetal")
    forms.add_tube(fb, foot)
    fb.commit()
    fa = "foot_" + side
    # u: 0 = heel (+Y), 1 = toe (-Y); v: 90 = top, 270 = underside, 0/180 = sides
    plate(Z, fa, foot, (0.52, 0.94), V(40, 140), 0.3, 1.1, "stepped", "M_CeramicGray", (1, 1.6, 1, 1), 5, 6, taper=0.3, crown=0.6, seed=21, bolts=6,
          panel=dict(inset=0.2, mat="M_Graphite", th=0.35))
    plate(Z, fa, foot, (0.18, 0.52), V(50, 130), 0.3, 1.2, "shell", "M_CeramicGray", (1, 1, 1, 1), 4, 6, crown=0.8, seed=22, bolts=4)
    plate(Z, fa, foot, (0.0, 0.22), V(20, 160), 0.3, 1.3, "wedge", "M_CeramicGray", (1.6, 1, 1, 1), 3, 7, taper=0.3, crown=0.5, seed=23, bolts=4)
    plate(Z, fa, foot, (0.14, 0.9), V(-30, 28), 0.3, 1.0, "ribbed", "M_CeramicGray", (1, 1, 1, 1), 6, 4, taper=0.2, crown=0.4, seed=24, ribs=3, bolts=4)
    plate(Z, fa, foot, (0.14, 0.9), V(152, 210), 0.3, 1.0, "shell", "M_CeramicGray", (1, 1, 1, 1), 6, 4, taper=0.2, crown=0.4, seed=25, bolts=4)
    plate(Z, fa, foot, (0.9, 1.0), V(30, 150), 0.3, 1.0, "wedge", "M_AccentOrange", (1, 1, 0.5, 0.5), 2, 6, taper=0.4, seed=26)
    ti = hs.inner(Z, fa, "M_Rubber")
    for k in range(5):
        y = 5.0 - k * 4.2
        ti.box((12.4 - abs(k - 2) * 0.8, 1.6, 1.0), (lx, y, 0.5), bevel=0.2, mat="M_Rubber")
    ti.commit()
