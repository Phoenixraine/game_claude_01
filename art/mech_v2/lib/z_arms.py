"""Shoulders (pauldron slabs + vertical stacks), arms (hydraulic upper arm, elbow fork, massive forearm with amplifier cylinder), fists."""
import math

from mathutils import Matrix, Vector

from . import forms, hs, kit
from .forms import Sec
from .kit import vt, plate
from .z_legs import L3
from .z_torso import ly


def build_shoulder(P, s):
    side = "l" if s > 0 else "r"
    Z = "Shoulder" + side.upper()
    a = "shoulder_" + side
    A_ = (lambda x: x) if s > 0 else (lambda x: (180.0 - x) % 360.0)
    V = lambda p, q: (A_(p), A_(q))
    cx = s * 15.4
    zc = P["shoulder_z"]
    sh = vt([Sec((s * 15.2, 0.5, 58.0), 3.8, 5.0, 3.8), Sec((s * 14.8, 0.3, 60.0), 5.8, 6.4, 4.4), Sec((s * 14.0, 0.2, 65.0), 6.4, 7.0, 4.6),
             Sec((s * 13.0, 0.0, 70.0), 6.2, 6.8, 4.6), Sec((s * 12.4, -0.2, 72.6), 5.4, 6.0, 4.2), Sec((s * 12.0, -0.2, 73.6), 3.6, 4.4, 3.6), Sec((s * 11.8, -0.2, 74.0), 2.6, 3.4, 3.0)], 30)
    body = hs.body(a, Z, "M_Graphite")
    forms.add_tube(body, sh)
    body.commit()
    jt = hs.joint(a, Z, "M_DarkMetal")
    forms.add_ellipsoid(jt, (s * 12.6, 0.2, zc - 3.0), (4.4, 4.6, 4.4), lat=8, lon=16, mat="M_DarkMetal")
    kit.ring(jt, (s * 12.6, 0.2, zc - 6.2), (0, 0, 1), 5.4, 4.0, 0.9, 28, "M_Hydraulic")
    jt.commit()
    # layered pauldron: outer slab lames + cap + front/back covers
    plate(Z, a, sh, (0.5, 0.97), V(-62, 62), 1.1, 1.8, "stepped", "M_CeramicGray", (1.2, 1.6, 1, 1), 5, 8, taper=0.0, crown=0.9, seed=81, bolts=8,
          panel=dict(inset=0.14, mat="M_Graphite", th=0.5), accent=((0.1, 0.5), (0.1, 0.55)))
    plate(Z, a, sh, (0.2, 0.52), V(-60, 60), 1.4, 1.6, "stepped", "M_CeramicGray", (1, 1, 1, 1), 4, 8, taper=0.0, crown=0.9, seed=82, bolts=8, accent=((0.55, 0.95), (0.2, 0.6)),
          panel=dict(inset=0.16, mat="M_Graphite", th=0.4))
    plate(Z, a, sh, (0.04, 0.24), V(-70, 70), 1.7, 1.4, "wedge", "M_CeramicGray", (1, 1.4, 1, 1), 3, 8, taper=0.1, crown=0.5, seed=83, bolts=6)
    plate(Z, a, sh, (0.3, 0.95), V(240, 305), 1.0, 1.6, "stepped", "M_CeramicGray", (1, 1, 1, 1), 5, 5, taper=0.25, crown=0.8, seed=84, bolts=6,
          panel=dict(inset=0.2, mat="M_Graphite", th=0.4))
    plate(Z, a, sh, (0.3, 0.95), V(55, 120), 1.0, 1.6, "ribbed", "M_CeramicGray", (1, 1, 1, 1), 5, 6, taper=0.25, crown=0.8, seed=85, bolts=6, ribs=3)
    plate(Z, a, sh, (0.3, 0.9), V(150, 215), 1.0, 1.4, "shell", "M_CeramicGray", (1, 1, 1, 1), 4, 5, taper=0.2, crown=0.5, seed=86, bolts=4)
    plate(Z, a, sh, (0.9, 1.0), V(0, 360), 1.0, 0.8, "shell", "M_DarkMetal", (1, 1, 1, 1), 1, 18, seed=87)
    # exhaust/antenna stack behind the pauldron + a narrow white work lamp
    st = hs.armor(Z, a, "M_CeramicGray")
    st.box((3.6, 3.2, 11.0), (s * 13.0, 6.2, 74.5), bevel=0.5, taper=(0.82, 0.82), mat="M_CeramicGray")
    st.box((2.2, 1.0, 8.0), (s * 13.0, 4.4, 74.5), bevel=0.2, mat="M_DarkMetal")
    st.cyl(1.0, 1.4, (s * 13.0, 6.2, 80.2), "z", 10, mat="M_DarkMetal")
    st.commit()
    lamp = hs.inner(Z, a, "M_Emissive_Status")
    lamp.box((1.2, 0.5, 4.0), (s * 9.0, -7.9, 70.6), bevel=0.1, mat="M_Emissive_Status")
    lamp.commit()


def build_arm(P, s):
    side = "l" if s > 0 else "r"
    Z = "Arm" + side.upper()
    A_ = (lambda x: x) if s > 0 else (lambda x: (180.0 - x) % 360.0)
    V = lambda p, q: (A_(p), A_(q))
    sx, ax = s * P["shoulder_x"], s * P["arm_x"]
    S0 = (sx, ly(P, 62) - 0.6, 62.0)
    E = (ax, -4.6, P["elbow_z"])
    W = (ax + s * 0.5, -7.0, P["wrist_z"])
    # ---- upper arm
    ua = vt([Sec(L3(S0, E, 0.0), 3.4, 3.8, 2.4), Sec(L3(S0, E, 0.5), 3.8, 4.2, 2.5), Sec(L3(S0, E, 1.0), 3.5, 3.9, 2.4)], 24)
    b = hs.body("upperarm_" + side, Z, "M_Graphite")
    forms.add_tube(b, ua)
    b.commit()
    a = "upperarm_" + side
    plate(Z, a, ua, (0.12, 0.62), V(240, 300), 0.7, 1.0, "stepped", "M_CeramicGray", (1, 1, 1, 1), 4, 5, taper=0.2, crown=0.5, seed=91, bolts=4, panel=dict(inset=0.2, mat="M_Graphite", th=0.3))
    plate(Z, a, ua, (0.12, 0.7), V(-40, 40), 0.7, 1.0, "ribbed", "M_CeramicGray", (1, 1, 1, 1), 4, 4, taper=0.1, crown=0.4, seed=92, bolts=4, ribs=3)
    plate(Z, a, ua, (0.15, 0.7), V(140, 220), 0.7, 0.9, "shell", "M_CeramicGray", (1, 1, 1, 1), 4, 4, crown=0.3, seed=93, bolts=4)
    plate(Z, a, ua, (0.7, 0.98), V(200, 340), 0.8, 1.1, "wedge", "M_CeramicGray", (1.4, 1, 1, 1), 3, 6, taper=0.3, crown=0.4, seed=94, bolts=4)
    ip = hs.inner(Z, a, "M_DarkMetal")
    rp = hs.inner(Z, a, "M_Hydraulic")
    for dx in (-1.6, 1.6):
        kit.piston(ip, rp, (S0[0] + dx, S0[1] + 4.2, S0[2] - 1.0), (E[0] + dx, E[1] + 4.0, E[2] + 3.0), 0.8, 0.55, 2)
    ip.commit()
    rp.commit()
    hs.cable_curve(Z, a, [(S0[0] - s * 2, S0[1] - 4.5, S0[2] + 1), L3(S0, E, 0.5), (E[0] - s * 1.0, E[1] - 4.8, E[2] + 1.0)], 0.4)
    uj = hs.joint("upperarm_" + side, Z, "M_DarkMetal")
    forms.add_ellipsoid(uj, (S0[0], S0[1], S0[2] + 1.0), (4.2, 4.2, 4.2), lat=8, lon=16, mat="M_DarkMetal")
    kit.ring(uj, (S0[0], S0[1], S0[2] - 1.6), (0, 0, 1), 4.6, 3.2, 0.8, 24, "M_Hydraulic")
    uj.commit()
    # ---- elbow fork
    ej = hs.joint("forearm_" + side, Z, "M_DarkMetal")
    forms.add_ellipsoid(ej, E, (4.0, 4.0, 4.0), lat=8, lon=16, mat="M_DarkMetal")
    for d in (-1, 1):
        kit.ring(ej, (E[0] + d * 4.4, E[1], E[2]), (1, 0, 0), 3.2, 2.0, 0.8, 22, "M_Hydraulic")
    ej.commit()
    # ---- forearm: the arm is a fist-weapon: bigger than the upper arm, with an amplifier cylinder on top
    fa = vt([Sec(L3(E, W, 0.0), 4.0, 4.3, 2.5), Sec(L3(E, W, 0.18), 5.0, 5.5, 2.9), Sec(L3(E, W, 0.5), 5.1, 5.7, 3.0), Sec(L3(E, W, 0.85), 4.5, 5.0, 2.8),
            Sec(L3(E, W, 1.0), 4.1, 4.6, 2.6)], 30)
    b = hs.body("forearm_" + side, Z, "M_Graphite")
    forms.add_tube(b, fa)
    b.commit()
    a = "forearm_" + side
    plate(Z, a, fa, (0.1, 0.95), V(-50, 52), 1.2, 1.6, "stepped", "M_CeramicGray", (1, 1, 1, 1), 6, 7, taper=-0.15, crown=0.9, seed=101, bolts=8,
          panel=dict(inset=0.14, mat="M_Graphite", th=0.45), accent=((0.5, 0.9), (0.15, 0.5)))
    plate(Z, a, fa, (0.12, 0.9), V(228, 312), 1.1, 1.5, "stepped", "M_CeramicGray", (1, 1, 1, 1), 6, 7, taper=-0.1, crown=0.7, seed=102, bolts=8,
          panel=dict(inset=0.16, mat="M_Graphite", th=0.4))
    plate(Z, a, fa, (0.1, 0.9), V(134, 226), 1.1, 1.5, "ribbed", "M_CeramicGray", (1, 1, 1, 1), 6, 7, taper=-0.1, crown=0.7, seed=103, bolts=6, ribs=4)
    plate(Z, a, fa, (0.15, 0.85), V(56, 124), 1.0, 1.4, "vent", "M_CeramicGray", (1, 1, 1, 1), 5, 5, crown=0.5, seed=104, vent=4, bolts=4)
    plate(Z, a, fa, (0.0, 0.14), V(0, 360), 1.4, 1.0, "shell", "M_DarkMetal", (1, 1, 1, 1), 1, 20, seed=105)
    plate(Z, a, fa, (0.86, 1.0), V(0, 360), 1.2, 1.1, "shell", "M_Graphite", (1, 1, 1, 1), 1, 20, seed=106)
    ip = hs.inner(Z, a, "M_DarkMetal")
    rp = hs.inner(Z, a, "M_Hydraulic")
    kit.piston(ip, rp, (ax, E[1] - 4.6, E[2] - 1.0), (W[0], W[1] - 4.2, W[2] + 2.0), 1.35, 0.6, 3)
    ip.commit()
    rp.commit()
    # ---- fist
    build_fist(P, s, W, side, Z)


def build_fist(P, s, W, side, Z):
    wx, wy, wz = W
    a = "hand_" + side
    A_ = (lambda x: x) if s > 0 else (lambda x: (180.0 - x) % 360.0)
    V = lambda p, q: (A_(p), A_(q))
    hd = vt([Sec((wx, wy, wz - 10.0), 4.0, 5.0, 3.2), Sec((wx, wy - 0.4, wz - 8.0), 4.8, 5.8, 3.4), Sec((wx, wy - 0.4, wz - 4.0), 4.5, 5.4, 3.2), Sec((wx, wy, wz + 0.5), 3.8, 4.4, 2.6)], 28)
    body = hs.body(a, Z, "M_Graphite")
    forms.add_tube(body, hd)
    # curled fingers (large segments): proximal goes down, middle goes inward, distal tucks up
    for k in range(4):
        y = wy - 4.6 + k * 2.9
        r = 1.45 if k in (1, 2) else 1.3
        xo = wx + s * 3.8
        xi = wx - s * 2.8
        p = [(xo, y, wz - 3.2), (xo + s * 0.5, y, wz - 8.2), (xi, y, wz - 9.4), (xi - s * 0.4, y, wz - 6.2)]
        for i in range(3):
            forms.add_capsule(body, p[i], p[i + 1], r, r * 0.95, 10, 3.0, "M_Graphite")
        for q in p[1:3]:
            forms.add_ellipsoid(body, q, (r * 1.2, r * 1.2, r * 1.2), lat=5, lon=10, mat="M_DarkMetal")
    th = [(wx - s * 3.4, wy - 6.2, wz - 3.8), (wx + s * 0.8, wy - 7.0, wz - 6.2), (wx + s * 4.6, wy - 6.6, wz - 7.6)]
    forms.add_capsule(body, th[0], th[1], 1.9, 1.7, 10, 3.0, "M_Graphite")
    forms.add_capsule(body, th[1], th[2], 1.7, 1.5, 10, 3.0, "M_Graphite")
    body.commit()
    wj = hs.joint(a, Z, "M_DarkMetal")
    forms.add_ellipsoid(wj, (wx, wy, wz + 0.2), (3.6, 3.6, 3.0), lat=6, lon=14, mat="M_DarkMetal")
    wj.commit()
    plate(Z, a, hd, (0.3, 0.9), V(-44, 44), 0.7, 1.3, "stepped", "M_CeramicGray", (1, 1, 1, 1), 4, 5, taper=0.1, crown=0.6, seed=111, bolts=6, panel=dict(inset=0.2, mat="M_Graphite", th=0.35))
    plate(Z, a, hd, (0.3, 0.9), V(236, 304), 0.7, 1.2, "shell", "M_CeramicGray", (1, 1, 1, 1), 4, 5, taper=0.1, crown=0.5, seed=112, bolts=4)
    plate(Z, a, hd, (0.3, 0.9), V(120, 224), 0.7, 1.1, "ribbed", "M_CeramicGray", (1, 1, 1, 1), 4, 5, taper=0.1, crown=0.4, seed=113, ribs=3, bolts=4)
    plate(Z, a, hd, (0.5, 0.96), V(56, 124), 0.7, 1.1, "shell", "M_CeramicGray", (1, 1, 1, 1), 3, 4, crown=0.3, seed=114)
    # knuckle plates over the finger row
    for k in range(4):
        y = wy - 4.6 + k * 2.9
        kp = hs.armor(Z, a, "M_CeramicGray")
        kp.box((1.5, 2.5, 2.6), (wx + s * 5.2, y, wz - 5.8), bevel=0.35, mat="M_CeramicGray")
        kp.commit()


def build_all_arms(P):
    for s in (1, -1):
        build_shoulder(P, s)
        build_arm(P, s)
