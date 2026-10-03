"""Secondary detail: hydraulic pairs, hose runs with clamps, bolt rings around joints, handrails/ladder, camera pods, radiator fins, toe claws.
Everything here is mechanical detail that makes the big shapes read as an engineered machine (and brings the triangle count into the 250-450 k band)."""
import math

from mathutils import Vector

from . import forms, hs, kit
from .forms import Sec, Tube
from .kit import vt
from .z_legs import L3
from .z_torso import ly


def bolt_ring(part, centre, axis, radius, count, r=0.3, h=0.26, mat="M_DarkMetal"):
    c, n = Vector(centre), Vector(axis).normalized()
    up = Vector((0, 0, 1)) if abs(n.z) < 0.9 else Vector((1, 0, 0))
    a = n.cross(up).normalized()
    b = n.cross(a)
    for k in range(count):
        ang = 2 * math.pi * k / count
        d = a * math.cos(ang) + b * math.sin(ang)
        kit.bolt(part, c + d * radius, d if abs(n.dot(d)) < 0.5 else n, r, h, 6, mat)


def clamp(part, p, axis, r, w=0.8, mat="M_DarkMetal"):
    """A hose clamp: a ring band with a bolt on it, around a hose of radius r running along `axis` through p."""
    kit.ring(part, p, axis, r * 1.55, r * 1.05, w, 20, mat)
    a = Vector(axis).normalized()
    up = Vector((0, 0, 1)) if abs(a.z) < 0.9 else Vector((1, 0, 0))
    d = a.cross(up).normalized()
    kit.bolt(part, Vector(p) + d * r * 1.55, d, r * 0.45, r * 0.5, 6, mat)


def hose_with_clamps(zone, bone, pts, r=0.5, nclamps=2):
    o = hs.cable_curve(zone, bone, pts, r)
    return o


def build_extra(P):
    for s in (1, -1):
        side = "l" if s > 0 else "r"
        ZL = "Leg" + side.upper()
        ZA = "Arm" + side.upper()
        ZS = "Shoulder" + side.upper()
        lx, ax, sx = s * P["leg_x"], s * P["arm_x"], s * P["shoulder_x"]
        H = (lx, P["hip_y"], P["hip_z"])
        K = (lx, P["knee_y"], P["knee_z"])
        A = (lx, P["ankle_y"], P["ankle_z"])
        # ---------------- legs: front hip hydraulics, knee shock absorbers, ankle pistons, bolt rings, hoses
        ip = hs.inner(ZL, "thigh_" + side, "M_DarkMetal")
        rp = hs.inner(ZL, "thigh_" + side, "M_Hydraulic")
        kit.piston(ip, rp, (H[0] + s * 4.8, H[1] - 5.2, H[2] + 1.0), (H[0] + s * 6.4, H[1] - 8.2, H[2] - 8.0), 0.95, 0.55, 3)
        kit.piston(ip, rp, (K[0] + s * 5.2, K[1] + 2.5, K[2] + 7.0), (K[0] + s * 5.6, K[1] + 4.0, K[2] - 3.0), 0.8, 0.5, 2)
        bolt_ring(ip, (H[0] + s * 6.8, H[1], H[2]), (s, 0, 0), 5.4, 14, 0.34, 0.3)
        bolt_ring(ip, (K[0] + s * 5.6, K[1], K[2]), (s, 0, 0), 3.5, 10, 0.3, 0.26)
        ip.commit()
        rp.commit()
        sp = hs.inner(ZL, "shin_" + side, "M_DarkMetal")
        sr = hs.inner(ZL, "shin_" + side, "M_Hydraulic")
        for dx in (-1, 1):
            kit.piston(sp, sr, (A[0] + dx * 5.4, A[1] + 3.2, A[2] + 8.5), (A[0] + dx * 5.6, A[1] + 1.2, A[2] + 1.2), 0.8, 0.5, 2)
        bolt_ring(sp, (A[0] + s * 5.1, A[1], A[2]), (s, 0, 0), 2.7, 9, 0.28, 0.24)
        sp.commit()
        sr.commit()
        hs.cable_curve(ZL, "shin_" + side, [(K[0] + s * 2.0, K[1] + 5.4, K[2] - 1.0), (K[0] + s * 3.0, K[1] + 7.6, K[2] - 6.0), (A[0] + s * 2.4, A[1] + 7.8, A[2] + 8.0), (A[0] + s * 2.0, A[1] + 5.0, A[2] + 2.0)], 0.5)
        hs.cable_curve(ZL, "thigh_" + side, [(H[0] - s * 2.2, H[1] + 7.0, H[2] - 1.0), (H[0] - s * 3.0, H[1] + 10.0, H[2] - 9.0), (K[0] - s * 2.5, K[1] + 10.2, K[2] + 6.0), (K[0] - s * 2.4, K[1] + 7.0, K[2] + 1.0)], 0.5)
        # toe claws (removable armour pieces) + heel spur
        for k, dx in enumerate((-3.6, 0.0, 3.6)):
            cl = hs.armor(ZL, "foot_" + side, "M_DarkMetal")
            cl.box((2.6, 3.4, 1.6), (lx + dx, -14.6, 1.3), bevel=0.35, taper=(0.6, 0.5), mat="M_DarkMetal")
            cl.commit()
        # ---------------- arms: elbow shocks, wrist rings, hoses, forearm bolt rings
        ap = hs.inner(ZA, "forearm_" + side, "M_DarkMetal")
        ar = hs.inner(ZA, "forearm_" + side, "M_Hydraulic")
        E = (ax, -4.6, P["elbow_z"])
        W = (ax + s * 0.5, -7.0, P["wrist_z"])
        kit.piston(ap, ar, (E[0] + s * 4.2, E[1] + 2.0, E[2] + 3.0), (E[0] + s * 4.8, E[1] - 1.0, E[2] - 5.0), 0.7, 0.5, 2)
        bolt_ring(ap, (E[0] + s * 4.8, E[1], E[2]), (s, 0, 0), 2.6, 9, 0.26, 0.22)
        bolt_ring(ap, (W[0], W[1], W[2] + 0.4), (0, 0, 1), 4.3, 12, 0.26, 0.22)
        ap.commit()
        ar.commit()
        hs.cable_curve(ZA, "forearm_" + side, [(E[0] - s * 3.2, E[1] + 4.2, E[2] - 2.0), (E[0] - s * 4.0, E[1] + 5.2, E[2] - 8.0), (W[0] - s * 3.0, W[1] + 4.6, W[2] + 1.0)], 0.4)
        # ---------------- shoulder: camera pod, band rings on the stack, hydraulics to the chest
        sh = hs.armor(ZS, "shoulder_" + side, "M_CeramicGray")
        forms.add_ellipsoid(sh, (sx + s * 7.6, -5.2, 70.6), (1.7, 1.7, 1.2), lat=6, lon=12, mat="M_DarkMetal")
        sh.cyl(0.75, 1.0, (sx + s * 7.6, -6.9, 70.6), "y", 10, mat="M_Glass_Sensor")
        for k in range(3):
            kit.ring(sh, (s * 13.0, 6.2, 71.0 + 3.2 * k), (0, 0, 1), 2.2, 1.7, 0.45, 18, "M_DarkMetal")
        sh.commit()
        shp = hs.inner(ZS, "shoulder_" + side, "M_DarkMetal")
        shr = hs.inner(ZS, "shoulder_" + side, "M_Hydraulic")
        kit.piston(shp, shr, (s * 8.0, -3.0, 61.5), (s * 12.0, -7.0, 67.8), 0.9, 0.55, 3)
        kit.piston(shp, shr, (s * 8.2, 3.0, 61.5), (s * 12.4, 7.0, 67.0), 0.9, 0.55, 3)
        bolt_ring(shp, (s * 12.6, 0.2, 59.0), (0, 0, -1), 5.4, 14, 0.32, 0.26)
        shp.commit()
        shr.commit()
    # ---------------- torso: handrails and a side ladder (removable plates), radiators and exhaust pipes at the back, hatch hinges
    ch = chest_surf(P)
    for s in (1, -1):
        h = hs.armor("Torso", "torso", "M_DarkMetal")
        for k in range(8):
            z = 49.5 + k * 2.1
            y = ly(P, z) + 0.0
            h.box((0.5, 0.5, 0.7), (s * 9.6, y + 3.2, z), mat="M_DarkMetal")
            h.cyl(0.28, 3.6, (s * 9.6, y + 2.5, z), "y", 8, mat="M_Hydraulic")
        h.commit()
    rad = hs.armor("Reactor", "reactor", "M_CeramicGray")
    for k in range(7):
        rad.box((10.4 - 0.8 * abs(k - 3), 0.5, 1.2), (0, P["reactor_y"] + 5.9, P["reactor_z"] + 5.5 - 1.8 * k), bevel=0.12, mat="M_CeramicGray")
    for sx_ in (-1, 1):
        rad.cyl(0.9, 9.0, (sx_ * 7.4, P["reactor_y"] + 3.0, P["reactor_z"] - 0.5), "z", 12, mat="M_DarkMetal")
        for k in range(4):
            kit.ring(rad, (sx_ * 7.4, P["reactor_y"] + 3.0, P["reactor_z"] - 4.0 + 2.4 * k), (0, 0, 1), 1.3, 0.9, 0.4, 14, "M_DarkMetal")
    rad.commit()
    hh = hs.inner("Torso", "torso", "M_DarkMetal")
    for sx_ in (-1, 1):
        hh.box((0.9, 1.4, 2.4), (sx_ * 3.9, ly(P, 63) + 9.4, 63.0), bevel=0.15, mat="M_DarkMetal")
        hh.cyl(0.35, 2.2, (sx_ * 3.9, ly(P, 63) + 9.6, 63.0), "z", 8, mat="M_Hydraulic")
    hh.commit()


def chest_surf(P):
    from .z_torso import chest_surface
    return chest_surface(P)
