"""blender -b -P build_cockpit_v3.py -- <out_dir> [--preview]

IMPACT VECTOR cockpit v4 (concept-art rebuild): a full conn-pod room instead of a desk.
  * a flattened half-dome of faceted glass panes in front (SM_Cockpit_Glass) held by a rib cage,
  * a ring of consoles under the dome (monitors, buttons, dials, toggles, sliders, levers), side and rear walls with racks,
    the rear hatch, a ceiling with the overhead console and hydraulic hub, the drive platform with a waist ring,
  * the pilot's own body in a drive suit (boots, shins, thighs, pelvis, torso) as separate parts with joint pivots,
  * cockpit_layout.json: pipes (polylines, the game builds them as tubes so they can burst), dangling wires, monitor quads,
    lamps and effect sockets (steam / sparks / fire).
Blender axes: +X forward, +Y left, +Z up, the pilot's EYE is the origin, metres. The game maps Blender -> Unreal as (x, -y, z) * 100.
Material classes are stored in UV1.y (see kit.py / M_Cockpit).
"""
import bpy, bmesh, sys, math, random, os, json
import numpy as np
from mathutils import Vector, Matrix, Euler

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "..", "common"))
from bmb import B as _B
from kit import *

argv = sys.argv[sys.argv.index("--") + 1:]
OUT = argv[0]
PREVIEW = "--preview" in argv
SHOTS = [a.split("=")[1] for a in argv if a.startswith("--shots=")]
SHOTS = SHOTS[0].split(",") if SHOTS else None
os.makedirs(OUT, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)


class B(_B):
    def __init__(self, name):
        super().__init__(name, "M_Cockpit")


def beam(b, p0, p1, w, d, hint, cls=0, bevel=0.0):
    p0, p1 = Vector(p0), Vector(p1)
    e = p1 - p0
    L = e.length
    if L < 1e-5:
        return
    x = e.normalized()
    h = Vector(hint)
    z = (h - x * h.dot(x))
    if z.length < 1e-4:
        z = Vector((0, 0, 1)) if abs(x.z) < 0.9 else Vector((1, 0, 0))
    z.normalize()
    y = z.cross(x)
    M = Matrix((x, y, z)).transposed()
    return b.box((p0 + p1) / 2, (L, w, d), rot=tuple(M.to_euler()), cls=cls, bevel=bevel)


LAY = {"pipes": [], "wires": [], "monitors": [], "lamps": [], "sockets": [], "body": {}}
FLOOR = -1.62
A_, B_, H_ = 1.75, 1.95, 1.5                      # dome ellipsoid radii (forward, lateral, vertical)
CEN = Vector((0.05, 0.0, -0.35))
V0 = math.radians(-12.0)


def dome_pt(u, v):
    return Vector((CEN.x + A_ * math.cos(v) * math.cos(u), B_ * math.cos(v) * math.sin(u), CEN.z + H_ * math.sin(v)))


def dome_n(p):
    return Vector(((p.x - CEN.x) / A_ ** 2, p.y / B_ ** 2, (p.z - CEN.z) / H_ ** 2)).normalized()


def rho(a, v=V0):
    ax, by = A_ * math.cos(v), B_ * math.cos(v)
    return 1.0 / math.sqrt((math.cos(a) / ax) ** 2 + (math.sin(a) / by) ** 2)


def add_monitor(mid, f, u, v, w, h, t=0.012, label=""):
    c = f.pt(u, v, t)
    LAY["monitors"].append({"id": mid, "c": [c.x, c.y, c.z], "right": list(f.ux), "up": list(f.uy), "n": list(f.n), "w": w, "h": h, "label": label})


def add_socket(kind, p, d=(0, 0, 1), tag=""):
    LAY["sockets"].append({"kind": kind, "p": [p[0], p[1], p[2]], "d": [d[0], d[1], d[2]], "tag": tag})


def add_pipe(pts, r, cls=0, steam=0.0, breakable=True, name=""):
    LAY["pipes"].append({"id": name or "pipe_%d" % len(LAY["pipes"]), "pts": [[p[0], p[1], p[2]] for p in pts], "r": r, "cls": cls, "steam": steam, "breakable": breakable})


def add_wire(anchor, d, length, r, color, kind="hang"):
    LAY["wires"].append({"id": "wire_%d" % len(LAY["wires"]), "a": [anchor[0], anchor[1], anchor[2]], "d": [d[0], d[1], d[2]], "len": length, "r": r, "color": color, "kind": kind})


def add_lamp(name, p, color, intensity, radius, kind="steady"):
    LAY["lamps"].append({"id": name, "p": [p[0], p[1], p[2]], "color": color, "i": intensity, "radius": radius, "kind": kind})

