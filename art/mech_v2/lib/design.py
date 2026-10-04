"""BASTION-01 v2 design: skeleton + zone builders. Proportions follow docs/art/DESIGN_BIBLE.md (1 "head" = 10.8 m of the 82 m height):
foot 0.35 shin, shin = thigh 1.7 heads' worth, torso 2.4, arm (shoulder -> fist) 3.6, shoulder span ~0.5 of the height."""
import math

from mathutils import Vector

from . import forms, hs
from .forms import Sec, Tube


def skeleton(P):
    """bone -> (head, tail, parent). Heads are the real rotation points of the joints (same bone names as the v1 contract)."""
    L = P
    b = {}
    b["root"] = ((0, 0, 0), (0, 0, 4), None)
    b["pelvis"] = ((0, 0, L["hip_z"] + 2), (0, 0, L["hip_z"] + 8), "root")
    b["torso"] = ((0, 0, L["waist_z"]), (0, 0, L["shoulder_z"] + 2), "pelvis")
    b["head"] = ((0, L["head_y"], L["neck_z"]), (0, L["head_y"], L["head_top"]), "torso")
    b["reactor"] = ((0, L["reactor_y"], L["reactor_z"]), (0, L["reactor_y"], L["reactor_z"] + 8), "torso")
    for side, s in (("l", 1), ("r", -1)):
        sx = s * L["shoulder_x"]
        b["shoulder_" + side] = ((sx * 0.9, 0, L["shoulder_z"]), (sx, 0, L["shoulder_z"]), "torso")
        b["upperarm_" + side] = ((sx, 0, L["shoulder_z"] - 2), (s * L["arm_x"], -2, L["elbow_z"]), "shoulder_" + side)
        b["forearm_" + side] = ((s * L["arm_x"], -2, L["elbow_z"]), (s * L["arm_x"], -4, L["wrist_z"]), "upperarm_" + side)
        b["hand_" + side] = ((s * L["arm_x"], -4, L["wrist_z"]), (s * L["arm_x"], -4, L["wrist_z"] - 8), "forearm_" + side)
        b["thigh_" + side] = ((s * L["leg_x"], 0, L["hip_z"]), (s * L["leg_x"], -2, L["knee_z"]), "pelvis")
        b["shin_" + side] = ((s * L["leg_x"], -2, L["knee_z"]), (s * L["leg_x"], 1, L["ankle_z"]), "thigh_" + side)
        b["foot_" + side] = ((s * L["leg_x"], 1, L["ankle_z"]), (s * L["leg_x"], -9, 1.5), "shin_" + side)
    return b


def _mirror_x(secs):
    return secs


def blockout(P):
    """Plain proportion study: one lofted solid per bone. Used for the silhouette renders before any detail is added."""
    hs.reset()
    z = P
    # pelvis + waist
    p = hs.body("pelvis", "Torso", "M_Graphite")
    forms.add_tube(p, Tube([Sec((0, 0, 35.0), 7.0, 6.4, 2.6), Sec((0, 0, 38.5), 10.0, 8.2, 3.0), Sec((0, 0, 42), 9.6, 7.8, 3.0),
                            Sec((0, 0, 46.5), 7.4, 6.4, 2.6)], 28))
    p.commit()
    # barrel chest: V-taper, forward-bulging breastplate
    t = hs.body("torso", "Torso", "M_CeramicGray")
    forms.add_tube(t, Tube([Sec((0, 0, 46), 7.4, 6.4, 2.6), Sec((0, 0, 49), 7.6, 6.6, 2.6), Sec((0, -0.8, 53), 10.6, 9.4, 3.0, flat_front=0.2),
                            Sec((0, -1.6, 58), 13.0, 11.8, 3.3, flat_front=0.35), Sec((0, -1.2, 62), 13.6, 11.4, 3.3, flat_front=0.3),
                            Sec((0, -0.4, 66), 11.4, 9.4, 3.0), Sec((0, -1.5, 69.5), 7.0, 6.4, 2.4)], 32))
    t.commit()
    # reactor back-pack
    r = hs.body("reactor", "Reactor", "M_DarkMetal")
    forms.add_tube(r, Tube([Sec((0, 9, 50), 5.0, 2.4, 2.6), Sec((0, 10.5, 54), 8.0, 4.6, 2.8), Sec((0, 11, 59), 8.4, 5.0, 2.8),
                            Sec((0, 10, 64), 6.5, 3.6, 2.6)], 24))
    r.commit()
    # head: small helmet sunk between the shoulders
    h = hs.body("head", "Head", "M_Graphite")
    hy = z["head_y"] - 0.5
    forms.add_tube(h, Tube([Sec((0, hy, 69), 3.8, 4.0, 2.4), Sec((0, hy, 71), 4.8, 5.4, 2.8), Sec((0, hy - 0.4, 74.5), 5.2, 6.0, 3.0, flat_front=0.4),
                            Sec((0, hy, 77.5), 4.4, 5.0, 2.8), Sec((0, hy + 0.3, 79.5), 2.6, 3.2, 2.4)], 24))
    h.commit()
    for s, side in ((1, "l"), (-1, "r")):
        # shoulder: angular super-ellipsoid pauldron
        sh = hs.body("shoulder_" + side, "Shoulder" + side.upper(), "M_CeramicGray")
        forms.add_tube(sh, Tube([Sec((s * 17.0, 0.5, 58.0), 5.2, 6.8, 3.4), Sec((s * 16.2, 0.3, 60.5), 8.0, 9.0, 3.8), Sec((s * 15.2, 0.2, 66.0), 8.8, 9.6, 4.0),
                                 Sec((s * 14.0, 0.0, 71.0), 7.8, 8.8, 3.8), Sec((s * 12.8, -0.2, 74.0), 5.2, 6.4, 3.2), Sec((s * 12.4, -0.2, 74.8), 3.0, 4.0, 2.8)], 28))
        sh.commit()
        # upper arm
        ua = hs.body("upperarm_" + side, "Arm" + side.upper(), "M_Graphite")
        ax = s * z["shoulder_x"]
        forms.add_tube(ua, Tube([Sec((ax, 0, 62), 3.8, 4.2, 2.4), Sec((ax + s * 1.5, -0.5, 57), 4.2, 4.6, 2.4), Sec((s * z["arm_x"], -1.5, 51), 4.2, 4.6, 2.4)], 20))
        ua.commit()
        # forearm (massive, longer than the upper arm)
        fa = hs.body("forearm_" + side, "Arm" + side.upper(), "M_CeramicGray")
        ex = s * z["arm_x"]
        forms.add_tube(fa, Tube([Sec((ex, -2, z["elbow_z"] + 1), 5.0, 5.2, 2.4), Sec((ex, -2.5, z["elbow_z"] - 3), 6.4, 6.8, 2.8),
                                 Sec((ex, -3.2, z["elbow_z"] - 9), 6.2, 6.6, 2.8), Sec((ex, -3.8, z["wrist_z"] + 0.5), 5.2, 5.6, 2.6)], 24))
        fa.commit()
        hd = hs.body("hand_" + side, "Arm" + side.upper(), "M_Graphite")
        wz = z["wrist_z"]
        forms.add_tube(hd, Tube([Sec((ex, -4, wz + 0.5), 4.8, 5.2, 2.6), Sec((ex, -5, wz - 3), 6.0, 6.8, 3.2), Sec((ex, -5.5, wz - 7), 6.2, 7.2, 3.4),
                                 Sec((ex, -5, wz - 10.5), 4.8, 6.0, 3.0)], 24))
        hd.commit()
        # thigh: heavy at the hip, tapering into the knee
        lx = s * z["leg_x"]
        th = hs.body("thigh_" + side, "Leg" + side.upper(), "M_CeramicGray")
        forms.add_tube(th, Tube([Sec((lx, 0, z["hip_z"] + 2), 6.0, 6.8, 2.5), Sec((lx, -0.5, 36), 7.0, 8.0, 2.8), Sec((lx, -1.3, 30), 6.6, 7.6, 2.8),
                                 Sec((lx, -2, 24.5), 5.8, 6.6, 2.6), Sec((lx, -2, z["knee_z"]), 5.4, 6.2, 2.4)], 24))
        th.commit()
        # shin: boot with calf bulge to the back, tapering to the ankle
        sn = hs.body("shin_" + side, "Leg" + side.upper(), "M_Graphite")
        forms.add_tube(sn, Tube([Sec((lx, -2, z["knee_z"] + 0.5), 5.6, 6.4, 2.4), Sec((lx, -1.5, 19.5), 6.4, 7.8, 2.8, shift=(0, 0.8)),
                                 Sec((lx, 0, 13), 5.6, 7.0, 2.8, shift=(0, 0.6)), Sec((lx, 0.5, 8), 5.4, 6.4, 2.6), Sec((lx, 1, z["ankle_z"] + 1), 5.6, 6.4, 2.4)], 24))
        sn.commit()
        # ski foot (tube along -Y): wide and heavy
        ft = hs.body("foot_" + side, "Leg" + side.upper(), "M_DarkMetal")
        forms.add_tube(ft, Tube([Sec((lx, 6.0, 1.8), 4.6, 1.6, 2.4), Sec((lx, 2, 2.8), 6.6, 2.8, 2.8), Sec((lx, -4, 2.6), 7.0, 2.6, 3.0),
                                 Sec((lx, -9, 2.0), 6.4, 1.9, 3.0), Sec((lx, -13, 1.2), 4.4, 1.2, 2.6)], 24, ref=(1, 0, 0)))
        ft.commit()
    return hs.REG
