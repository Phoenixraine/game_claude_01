"""Head: a small armoured sensor helmet sunk between the shoulders: continuous visor slit, brow/cheek/jaw plates, crest, antennas, vents."""
import math

from mathutils import Vector

from . import forms, hs, kit
from .forms import Sec
from .kit import vt, plate


def build_head(P):
    Z = "Head"
    a = "head"
    hy = P["head_y"]
    hd = vt([Sec((0, hy, 68.6), 3.8, 4.0, 2.4), Sec((0, hy, 70.4), 4.8, 5.2, 3.0), Sec((0, hy - 0.4, 73.2), 5.4, 6.0, 3.4, flat_front=0.4), Sec((0, hy - 0.2, 76.4), 5.0, 5.6, 3.3),
             Sec((0, hy + 0.2, 78.6), 3.6, 4.2, 3.0), Sec((0, hy + 0.5, 79.6), 2.0, 2.6, 2.6)], 30)
    body = hs.body(a, Z, "M_Graphite")
    forms.add_tube(body, hd)
    # one continuous visor slit across the face (glass) with a darker frame
    vs = vt([Sec((0, hy - 0.9, 73.9), 5.1, 5.4, 3.6, flat_front=0.5), Sec((0, hy - 0.9, 74.5), 5.1, 5.4, 3.6, flat_front=0.5)], 30)
    kit.patch(body, vs, (0.0, 1.0), (205, 335), 0.15, 0.3, (1, 1, 1, 1), 1, 10, 0.0, 0.0, "M_Glass_Sensor", cham_w=0.5)
    body.commit()
    jt = hs.joint(a, Z, "M_DarkMetal")
    forms.add_ellipsoid(jt, (0, hy + 0.2, 68.6), (3.6, 3.6, 2.2), lat=6, lon=14, mat="M_DarkMetal")
    jt.commit()
    # brow visor hood, crown, crest, cheek and jaw guards, rear plate
    plate(Z, a, hd, (0.56, 0.62 + 0.0), (205, 335), 0.7, 1.7, "wedge", "M_CeramicGray", (1, 1.6, 1, 1), 2, 10, taper=0.0, crown=0.4, seed=121, bolts=0)
    plate(Z, a, hd, (0.62, 0.96), (200, 340), 0.4, 1.3, "wedge", "M_CeramicGray", (1, 1.4, 1, 1), 4, 8, taper=0.35, crown=0.6, seed=122, bolts=6, accent=((0.15, 0.5), (0.4, 0.6)))
    plate(Z, a, hd, (0.2, 0.46), (222, 318), 0.4, 1.2, "wedge", "M_CeramicGray", (1.4, 1, 1, 1), 3, 6, taper=0.5, crown=0.4, seed=123, bolts=4)
    plate(Z, a, hd, (0.3, 0.84), (-46, 38), 0.4, 1.1, "stepped", "M_CeramicGray", (1, 1, 1, 1), 4, 5, taper=0.25, crown=0.5, seed=124, bolts=4, panel=dict(inset=0.22, mat="M_Graphite", th=0.3))
    plate(Z, a, hd, (0.3, 0.84), (142, 226), 0.4, 1.1, "stepped", "M_CeramicGray", (1, 1, 1, 1), 4, 5, taper=0.25, crown=0.5, seed=125, bolts=4, panel=dict(inset=0.22, mat="M_Graphite", th=0.3))
    plate(Z, a, hd, (0.2, 0.9), (56, 124), 0.4, 1.1, "vent", "M_CeramicGray", (1, 1, 1, 1), 4, 5, crown=0.4, seed=126, vent=3, bolts=4)
    plate(Z, a, hd, (0.7, 0.98), (82, 98), 1.2, 1.2, "wedge", "M_DarkMetal", (1, 1, 1, 1), 4, 1, seed=127)
    for sx, top in ((-1, 81.2), (1, 82.0)):     # two antennas: base sleeve + whip (the tip of the right one is the 82 m top of the mech)
        an = hs.armor(Z, a, "M_DarkMetal")
        an.cyl(0.34, 2.2, (sx * 3.8, hy + 2.8, 79.4), "z", 8, mat="M_DarkMetal")
        an.cyl(0.18, top - 80.4, (sx * 3.8, hy + 2.8, 80.4 + (top - 80.4) / 2), "z", 6, mat="M_Hydraulic")
        an.commit()
    ie = hs.inner(Z, a, "M_Emissive_Status")
    ie.box((7.4, 0.3, 0.35), (0, hy - 6.6, 73.0), bevel=0.05, mat="M_Emissive_Status")
    ie.commit()
