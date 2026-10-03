"""Torso: barrel chest with reactor window, abdomen lames, back hatch, waist bellows joint, pelvis with hip skirts, back reactor pack."""
import math

from mathutils import Vector

from . import forms, hs, kit
from .forms import Sec
from .kit import vt, plate


def ly(P, z, base=0.0):
    """Forward lean: y offset (negative = towards -Y) of the upper body at height z."""
    return base - max(0.0, z - P["waist_z"]) * P["lean"]


def chest_surface(P):
    f = lambda z, rx, ry, p, ff=0.0, sh=(0, 0): Sec((0, ly(P, z), z), rx, ry, p, flat_front=ff, shift=sh)
    return vt([f(45.5, 6.4, 5.6, 2.6), f(48, 6.8, 6.0, 2.6), f(51, 7.8, 6.8, 3.2, 0.15), f(54, 9.8, 8.0, 3.6, 0.3), f(58, 10.8, 8.4, 3.8, 0.35),
              f(63, 11.0, 8.4, 3.8, 0.35), f(66, 9.4, 7.4, 3.4), f(68.5, 7.0, 6.0, 2.8), f(70.2, 4.8, 4.8, 2.4)], 36)


def pelvis_surface(P):
    f = lambda z, rx, ry, p: Sec((0, 0.3, z), rx, ry, p)
    return vt([f(34.6, 6.0, 5.4, 2.6), f(37, 8.0, 6.6, 2.9), f(40, 8.4, 7.0, 3.0), f(43.5, 7.8, 6.4, 2.9), f(46.5, 6.6, 5.8, 2.6)], 32)


def build_torso(P):
    Z = "Torso"
    ch = chest_surface(P)
    body = hs.body("torso", Z, "M_Graphite")
    forms.add_tube(body, ch)
    body.commit()
    # waist joint: bellows (rubber rings) + steel collars
    wj = hs.joint("torso", Z, "M_DarkMetal")
    zc = P["waist_z"]
    for k in range(5):
        kit.ring(wj, (0, ly(P, zc + 0.6 * k - 1.2) + 0.3, zc + 0.6 * k - 1.2), (0, 0, 1), 7.6 - 0.25 * abs(k - 2), 5.6, 0.5, 32, "M_Rubber" if k % 2 else "M_DarkMetal")
    wj.commit()
    F, B = kit.FRONT, kit.BACK
    a = "torso"
    # --- breastplate set around the reactor window (window = gap u .44-.64)
    plate(Z, a, ch, (0.64, 0.92), (232, 308), 1.4, 1.6, "stepped", "M_CeramicGray", (1.2, 1, 1.5, 1.5), 6, 8, taper=0.0, crown=0.6, seed=31, bolts=8,
          panel=dict(inset=0.14, mat="M_Graphite", th=0.5), accent=((0.1, 0.35), (0.05, 0.3)))
    plate(Z, a, ch, (0.16, 0.44), (240, 300), 1.3, 1.6, "wedge", "M_CeramicGray", (1, 1.4, 1, 1), 5, 7, taper=0.35, crown=0.5, seed=32, bolts=6)
    plate(Z, a, ch, (0.38, 0.84), (194, 246), 1.2, 1.7, "stepped", "M_CeramicGray", (1, 1, 1, 1.6), 6, 6, taper=0.1, crown=0.5, seed=33, bolts=8,
          panel=dict(inset=0.17, mat="M_Graphite", th=0.5), accent=((0.2, 0.55), (0.12, 0.4)))
    plate(Z, a, ch, (0.38, 0.84), (294, 346), 1.2, 1.7, "stepped", "M_CeramicGray", (1, 1, 1.6, 1), 6, 6, taper=0.1, crown=0.5, seed=34, bolts=8,
          panel=dict(inset=0.17, mat="M_Graphite", th=0.5), accent=((0.55, 0.9), (0.55, 0.9)))
    plate(Z, a, ch, (0.46, 0.64), (196, 234), 1.0, 1.2, "shell", "M_CeramicGray", (1, 1, 1, 1), 3, 4, taper=0.2, crown=0.3, seed=35, bolts=4)
    plate(Z, a, ch, (0.46, 0.64), (306, 344), 1.0, 1.2, "shell", "M_CeramicGray", (1, 1, 1, 1), 3, 4, taper=0.2, crown=0.3, seed=36, bolts=4)
    # abdomen lames (overlapping, front + sides)
    for k, (u0, u1) in enumerate(((0.02, 0.13), (0.12, 0.24), (0.23, 0.36))):
        plate(Z, a, ch, (u0, u1), (205, 335), 0.9 + 0.35 * k, 1.0, "shell", "M_CeramicGray" if k != 1 else "M_Graphite", (1, 1, 1, 1), 2, 10, crown=0.3, seed=40 + k, bolts=6)
    # side plates (ribbed) and shoulder-line yoke
    plate(Z, a, ch, (0.26, 0.86), (-46, 36), 1.1, 1.5, "ribbed", "M_CeramicGray", (1, 1, 1, 1), 6, 6, taper=0.2, crown=0.5, seed=44, bolts=6, ribs=3)
    plate(Z, a, ch, (0.26, 0.86), (144, 226), 1.1, 1.5, "ribbed", "M_CeramicGray", (1, 1, 1, 1), 6, 6, taper=0.2, crown=0.5, seed=45, bolts=6, ribs=3)
    plate(Z, a, ch, (0.92, 1.0), (180, 360), 1.2, 1.2, "shell", "M_DarkMetal", (1, 1, 1, 1), 1, 14, seed=46)       # collar
    plate(Z, a, ch, (0.84, 0.98), (180, 360), 0.2, 1.0, "vent", "M_CeramicGray", (1, 1, 1, 1), 2, 12, seed=47, vent=3)
    # --- back: upper back armour, spine ridge, hatch
    plate(Z, a, ch, (0.36, 0.9), (50, 130), 1.2, 1.6, "stepped", "M_CeramicGray", (1, 1, 1, 1), 6, 8, taper=0.1, crown=0.5, seed=48, bolts=8,
          panel=dict(inset=0.16, mat="M_Graphite", th=0.5))
    plate(Z, a, ch, (0.1, 0.34), (58, 122), 1.0, 1.2, "vent", "M_CeramicGray", (1, 1, 1, 1), 4, 6, taper=0.1, crown=0.5, seed=49, vent=5, bolts=4)
    plate(Z, a, ch, (0.4, 0.9), (88, 92), 2.2, 1.0, "wedge", "M_DarkMetal", (1, 1, 1, 1), 5, 1, seed=50)       # spine ridge
    plate(Z, a, ch, (0.42, 0.74), (74, 106), 2.0, 0.9, "stepped", "M_AccentOrange", (1, 1, 1, 1), 3, 4, seed=51,
          panel=dict(inset=0.22, mat="M_DarkMetal", th=0.5))                                                       # cockpit hatch frame
    # --- chest window: housing ring, emissive disc, iris petals
    zc = 57.0
    yf = ch.point((zc - 45.5) / (70.2 - 45.5), math.radians(270)).y
    cen = Vector((0, yf - 1.2, zc))
    ring = hs.inner(Z, a, "M_DarkMetal")
    kit.ring(ring, cen + Vector((0, -0.2, 0)), (0, 1, 0), 5.8, 4.1, 1.4, 40, "M_DarkMetal")
    kit.ring(ring, cen + Vector((0, 0.3, 0)), (0, 1, 0), 4.2, 3.5, 1.4, 40, "M_Hydraulic")
    ring.commit()
    core = hs.inner(Z, a, "M_Emissive_Status")
    forms.add_ellipsoid(core, cen + Vector((0, 0.9, 0)), (3.7, 1.4, 3.7), rot=(90, 0, 0), lat=6, lon=24, z_cut=(-1, 1), mat="M_Emissive_Status")
    core.commit()
    for k in range(8):
        ang = 2 * math.pi * k / 8 + math.pi / 8
        pet = hs.armor(Z, a, "M_CeramicGray")
        c = Vector((0, 0, 0))
        r0, r1 = 4.2, 6.3
        for dz, dh in ((0.0, 0.5), (0.0, 0.0)):
            pass
        # a small wedge petal in the plane of the window (normal -Y), built from a tapered box
        pet.box((1.9, 0.9, r1 - r0), (0, 0, (r0 + r1) / 2), taper=(1.5, 1.0), bevel=0.12, mat="M_CeramicGray")
        pet.transform((0, 0, 0), (0, 0, 0))
        import bmesh
        from mathutils import Matrix
        M = Matrix.Translation(cen + Vector((0, -0.9, 0))) @ Matrix.Rotation(math.pi / 2, 4, "X") @ Matrix.Rotation(ang, 4, "Y")
        bmesh.ops.transform(pet.bm, matrix=M, verts=list(pet.bm.verts))
        pet.commit()
    # hoses at the waist sides (over the abdomen lames, between chest and pelvis)
    for s in (1, -1):
        hs.cable_curve(Z, a, [(s * 7.6, ly(P, 52) - 3.6, 52.5), (s * 9.4, ly(P, 49) - 1.0, 49.5), (s * 8.8, 0.6, 46.2), (s * 8.4, 0.8, 42.8)], 0.55)


def build_pelvis(P):
    Z = "Torso"
    a = "pelvis"
    pv = pelvis_surface(P)
    body = hs.body("pelvis", Z, "M_Graphite")
    forms.add_tube(body, pv)
    body.commit()
    plate(Z, a, pv, (0.36, 0.78), (240, 300), 1.2, 1.5, "wedge", "M_CeramicGray", (1, 1.6, 1, 1), 4, 6, taper=0.5, crown=0.9, seed=61, bolts=6)         # codpiece
    plate(Z, a, pv, (0.5, 0.96), (205, 238), 1.0, 1.3, "stepped", "M_CeramicGray", (1, 1, 1, 1), 4, 4, taper=0.1, crown=0.6, seed=62, bolts=4,
          panel=dict(inset=0.2, mat="M_Graphite", th=0.4))
    plate(Z, a, pv, (0.5, 0.96), (302, 335), 1.0, 1.3, "stepped", "M_CeramicGray", (1, 1, 1, 1), 4, 4, taper=0.1, crown=0.6, seed=63, bolts=4,
          panel=dict(inset=0.2, mat="M_Graphite", th=0.4))
    plate(Z, a, pv, (0.2, 0.9), (-48, 40), 1.2, 1.5, "ribbed", "M_CeramicGray", (1, 1, 1, 1), 5, 6, taper=0.15, crown=0.5, seed=64, bolts=6, ribs=3)
    plate(Z, a, pv, (0.2, 0.9), (140, 228), 1.2, 1.5, "ribbed", "M_CeramicGray", (1, 1, 1, 1), 5, 6, taper=0.15, crown=0.5, seed=65, bolts=6, ribs=3)
    plate(Z, a, pv, (0.2, 0.92), (56, 124), 1.1, 1.5, "stepped", "M_CeramicGray", (1, 1, 1, 1), 5, 6, taper=0.1, crown=0.8, seed=66, bolts=6,
          panel=dict(inset=0.2, mat="M_Graphite", th=0.4))
    plate(Z, a, pv, (0.0, 0.2), (0, 360), 1.3, 1.1, "shell", "M_DarkMetal", (1, 1, 1, 1), 1, 24, seed=67)
    # fauld lames hanging over the thighs
    for s in (1, -1):
        for k in range(2):
            plate(Z, a, pv, (0.0 + 0.0 * k, 0.26), (-70 + 20, 70 - 20) if s > 0 else (110 + 20, 250 - 20), 1.3 + 0.5 * k, 1.0, "shell", "M_CeramicGray", (1, 1, 1, 1), 2, 5, crown=0.3, seed=68 + k, bolts=4)
    for s in (1, -1):
        ip = hs.inner(Z, a, "M_Hydraulic")
        forms.add_ellipsoid(ip, (s * 10.0, 0.3, 40.0), (3.0, 3.0, 3.0), lat=6, lon=12)
        ip.commit()


def build_reactor(P):
    Z = "Reactor"
    a = "reactor"
    cy, cz = P["reactor_y"], P["reactor_z"]
    rs = vt([Sec((0, cy - 2.0, 50.0), 5.0, 2.6, 2.8), Sec((0, cy - 1.0, 53.5), 7.8, 4.6, 3.2), Sec((0, cy, 58.0), 8.4, 5.2, 3.2), Sec((0, cy - 0.6, 63.0), 7.2, 4.4, 3.0),
            Sec((0, cy - 1.5, 66.0), 4.0, 3.0, 2.6)], 28)
    body = hs.body("reactor", Z, "M_DarkMetal")
    forms.add_tube(body, rs)
    body.commit()
    # cover plates (removable) around the core slot
    plate(Z, a, rs, (0.1, 0.45), (52, 128), 0.8, 1.2, "vent", "M_CeramicGray", (1, 1, 1, 1), 4, 6, crown=0.7, seed=71, vent=4, bolts=6)
    plate(Z, a, rs, (0.62, 0.95), (52, 128), 0.8, 1.2, "stepped", "M_CeramicGray", (1, 1, 1, 1), 4, 6, crown=0.7, seed=72, bolts=6, panel=dict(inset=0.2, mat="M_Graphite", th=0.4))
    plate(Z, a, rs, (0.1, 0.9), (0, 44), 0.8, 1.2, "ribbed", "M_CeramicGray", (1, 1, 1, 1), 5, 4, taper=0.1, crown=0.6, seed=73, ribs=4, bolts=4)
    plate(Z, a, rs, (0.1, 0.9), (136, 180), 0.8, 1.2, "ribbed", "M_CeramicGray", (1, 1, 1, 1), 5, 4, taper=0.1, crown=0.6, seed=74, ribs=4, bolts=4)
    plate(Z, a, rs, (0.0, 0.1), (0, 360), 0.8, 1.0, "shell", "M_Graphite", (1, 1, 1, 1), 1, 20, seed=75)
    # glowing core slot + cooling fins + exhaust stacks
    cs = hs.inner(Z, a, "M_Emissive_Status")
    cs.box((2.2, 0.9, 6.4), (0, cy + 5.5, cz + 0.5), bevel=0.2, mat="M_Emissive_Status")
    cs.commit()
    fn = hs.inner(Z, a, "M_Hydraulic")
    for k in range(6):
        fn.box((9.6 - 0.5 * abs(k - 2.5), 0.5, 0.8), (0, cy + 5.4, cz - 4.3 + k * 1.7), bevel=0.1, mat="M_Hydraulic")
    fn.commit()
    for s in (1, -1):
        ex = hs.armor(Z, a, "M_CeramicGray")
        ex.box((2.6, 2.6, 9.0), (s * 6.0, cy + 1.0, cz + 11.0), bevel=0.4, taper=(0.8, 0.8), mat="M_CeramicGray")
        ex.cyl(1.4, 1.0, (s * 6.0, cy + 1.0, cz + 15.8), "z", 12, mat="M_DarkMetal")
        ex.commit()
