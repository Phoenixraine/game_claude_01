"""blender -b -P build_cockpit_v3.py -- <out_dir> [--preview]

IMPACT VECTOR cockpit v3: a full conn-pod room instead of a desk.
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


# =============================================================================================================== SHELL
S = B("SM_Cockpit_Shell")
G = B("SM_Cockpit_Glass")
rr = random.Random(11)

# ---------------------------------------------------------------------------------------------- dome: glass panes + ribs
NU, NV = 12, 4
U = [math.radians(-112 + 224.0 * i / NU) for i in range(NU + 1)]
VR = [math.radians(x) for x in (-12, 12, 36, 58, 74)]
for i in range(NU):
    for j in range(NV):
        c = [dome_pt(U[i], VR[j]), dome_pt(U[i + 1], VR[j]), dome_pt(U[i + 1], VR[j + 1]), dome_pt(U[i], VR[j + 1])]
        ctr = sum(c, Vector()) / 4
        ins = [ctr + (p - ctr) * (1.0 - 0.042 / max((p - ctr).length, 0.06)) for p in c]
        vs = [G.bm.verts.new(p) for p in ins]
        for v in vs:
            v[G.cl] = 6
        face = G.bm.faces.new(vs)
        nrm = face.normal
        if nrm.dot(-ctr) < 0:
            face.normal_flip()

# meridian ribs
for i in range(NU + 1):
    heavy = (i % 3 == 1)
    for j in range(NV):
        p0, p1 = dome_pt(U[i], VR[j]), dome_pt(U[i], VR[j + 1])
        n = dome_n((p0 + p1) / 2)
        if heavy:
            beam(S, p0, p1, 0.085, 0.075, n, cls=0, bevel=0.008)
            beam(S, p0 - n * 0.040, p1 - n * 0.040, 0.022, 0.010, n, cls=2)             # orange inlay on the inner face
        else:
            beam(S, p0, p1, 0.036, 0.04, n, cls=0, bevel=0.004)
# hoops
for j in range(NV + 1):
    for i in range(NU):
        p0, p1 = dome_pt(U[i], VR[j]), dome_pt(U[i + 1], VR[j])
        n = dome_n((p0 + p1) / 2)
        if j == 0:
            beam(S, p0, p1, 0.13, 0.11, n, cls=0, bevel=0.01)
            beam(S, p0 - n * 0.056, p1 - n * 0.056, 0.03, 0.01, n, cls=5 if i % 2 == 0 else 9)
        elif j == NV:
            beam(S, p0, p1, 0.12, 0.10, n, cls=0, bevel=0.008)
        else:
            beam(S, p0, p1, 0.032, 0.036, n, cls=0, bevel=0.003)
# nodes (bolted plates at every rib/hoop junction)
for i in range(NU + 1):
    for j in range(NV + 1):
        p = dome_pt(U[i], VR[j])
        n = dome_n(p)
        S.cyl(p - n * 0.052, p + n * 0.03, 0.05 if (i % 3 == 1) else 0.034, cls=1, seg=10)
        S.cyl(p - n * 0.058, p - n * 0.052, 0.014, cls=10, seg=6)
        if i % 3 == 1 and j in (1, 3):
            S.cyl(p - n * 0.07, p - n * 0.052, 0.022, cls=5 if (i + j) % 2 else 9, seg=8)

# oculus: the ring at the top of the glass and the ceiling cone above it
for i in range(NU * 2):
    u0, u1 = math.radians(-112 + 224.0 * i / (NU * 2)), math.radians(-112 + 224.0 * (i + 1) / (NU * 2))
    p0, p1 = dome_pt(u0, VR[-1]), dome_pt(u1, VR[-1])
    top = Vector((CEN.x + 0.1, 0, 1.12))
    S.box((p0 + p1) / 2 * 0.5 + top * 0.5 + Vector((0, 0, 0.0)), (0.12, 0.2, 0.05), rot=(0, 0, 0), cls=0)
S.cyl(Vector((CEN.x + 0.05, 0, 1.08)), Vector((CEN.x + 0.05, 0, 1.2)), 1.05, cls=0, seg=40)

# ---------------------------------------------------------------------------------------------- floor and drive platform
S.cyl((0, 0, FLOOR - 0.14), (0, 0, FLOOR), 1.1, cls=0, seg=56)
S.cyl((0, 0, FLOOR - 0.02), (0, 0, FLOOR + 0.02), 1.15, cls=1, seg=56)
ring(S, (0, 0), 1.06, FLOOR + 0.025, 0.011, n=64, cls=5)
ring(S, (0, 0), 0.62, FLOOR + 0.02, 0.008, n=48, cls=4)
for k in range(24):                                   # tread plates
    a = 2 * math.pi * k / 24
    S.box((0.85 * math.cos(a), 0.85 * math.sin(a), FLOOR + 0.012), (0.5, 0.06, 0.012), rot=(0, 0, a), cls=0)
for sy in (-1, 1):                                    # foot pads
    S.box((0.04, sy * 0.15, FLOOR + 0.014), (0.36, 0.15, 0.014), cls=0, bevel=0.004)
    S.box((0.04, sy * 0.15, FLOOR + 0.022), (0.30, 0.11, 0.004), cls=4)
    for k in range(4):
        S.box((-0.12 + 0.08 * k, sy * 0.15, FLOOR + 0.026), (0.012, 0.09, 0.004), cls=0)
# lower floor, with under-floor pipes visible around the platform
S.cyl((0, 0, FLOOR - 0.55), (0, 0, FLOOR - 0.16), 2.2, cls=0, seg=56)
for k in range(30):
    a = 2 * math.pi * k / 30
    S.box((1.45 * math.cos(a), 1.45 * math.sin(a), FLOOR - 0.15), (0.7, 0.05, 0.02), rot=(0, 0, a), cls=1 if k % 3 else 0)
for k in range(8):
    a = 2 * math.pi * k / 8 + 0.2
    ring(S, (0, 0), 1.3 + 0.06 * k, FLOOR - 0.12, 0.014 + 0.003 * (k % 3), n=40, cls=0 if k % 2 else 3, a0=a, a1=a + 0.9)
for k in range(36):
    a = 2 * math.pi * k / 36
    S.box((1.17 * math.cos(a), 1.17 * math.sin(a), FLOOR + 0.004), (0.12, 0.05, 0.008), rot=(0, 0, a), cls=8 if k % 2 else 0)

# ---------------------------------------------------------------------------------------------- consoles around the dome
T = math.radians(32.0)
NSEG = 16
console_frames = {}
for k in range(NSEG):
    a = math.radians(-112.5 + 15.0 * k)            # azimuth from forward, + = left
    d = Vector((math.cos(a), math.sin(a), 0))
    tng = Vector((-math.sin(a), math.cos(a), 0))
    rs = rho(a, V0)
    rc = rs - 0.36
    zc = -0.88
    c = Vector((CEN.x, CEN.y, 0)) + d * rc
    c.z = zc
    n = -d * math.sin(T) + Vector((0, 0, math.cos(T)))
    f = Frame(c, -tng, n)                          # u to the pilot's right, v up-slope (away from the pilot)
    console_frames[k] = f
    w = 2 * rc * math.sin(math.radians(7.5)) + 0.004
    depth = 0.58
    # slab
    f.box(S, 0, 0, -0.06, w, depth, 0.06, cls=0, bevel=0.006)
    f.box(S, 0, 0, 0.0, w - 0.012, depth - 0.012, 0.012, cls=1)
    # side cheeks
    for sx in (-1, 1):
        f.box(S, sx * (w / 2 - 0.006), 0, -0.05, 0.012, depth + 0.02, 0.07, cls=0)
    # skirt down to the floor (outer) and the pilot-side kick panel
    po = f.pt(0, depth / 2, -0.06)
    ph = max(po.z - (FLOOR - 0.1), 0.1)
    S.box((po.x - d.x * 0.03, po.y - d.y * 0.03, po.z - ph / 2), (0.08, w, ph), rot=(0, 0, a), cls=0)
    pi_ = f.pt(0, -depth / 2, -0.06)
    ph2 = max(pi_.z - (FLOOR - 0.1), 0.1)
    S.box((pi_.x + d.x * 0.0, pi_.y + d.y * 0.0, pi_.z - ph2 / 2), (0.05, w, ph2), rot=(0, 0, a), cls=1 if k % 2 else 0)
    f.box(S, 0, -depth / 2 + 0.02, 0.0, w - 0.02, 0.05, 0.03, cls=3, bevel=0.012)             # padded lip
    # hazard + LED trim at the outer edge
    f.box(S, 0, depth / 2 - 0.012, 0.0, w - 0.03, 0.02, 0.005, cls=8)
    f.box(S, 0, depth / 2 - 0.04, 0.0, w * 0.7, 0.008, 0.004, cls=5 if k % 3 else 9)
    # bolts on the corners
    bolts(S, f, -w / 2 + 0.02, -depth / 2 + 0.07, 2, 2, w - 0.04, depth - 0.14)
    # ---- fill by type
    sym = abs(k - 7.5)               # 0.5 centre ... 7.5 outer
    r2 = random.Random(100 + k)
    if sym < 1.0:                    # two big centre monitors
        f.box(S, 0, 0.06, 0.0, w - 0.03, 0.30, 0.018, cls=0, bevel=0.004)
        f.box(S, 0, 0.06, 0.018, w - 0.07, 0.25, 0.004, cls=6)
        add_monitor("main_%s" % ("L" if k >= 8 else "R"), f, 0, 0.06, w - 0.07, 0.25, t=0.0225, label="main")
        button_grid(S, f, -w / 2 + 0.05, -0.16, 5, 2, 0.045, r2)
        led_bar(S, f, -0.1, 0.235, 12, r2, pitch=0.017)
    elif sym < 2.0:                  # radar/gauge cluster + secondary monitor
        f.box(S, 0, 0.08, 0.0, w - 0.05, 0.22, 0.016, cls=0, bevel=0.004)
        f.box(S, 0, 0.08, 0.016, w - 0.08, 0.18, 0.004, cls=6)
        add_monitor("aux_%s" % ("L" if k > 7 else "R"), f, 0, 0.08, w - 0.08, 0.18, t=0.021, label="aux")
        dial(S, f, -0.09, -0.14, 0.04, r2)
        dial(S, f, 0.0, -0.14, 0.04, r2, cls=5)
        dial(S, f, 0.09, -0.14, 0.04, r2)
        toggle_bank(S, f, 0, -0.045, 5, r2, pitch=0.05)
    elif sym < 3.0:
        button_grid(S, f, -w / 2 + 0.05, 0.14, 6, 4, 0.047, r2)
        slider(S, f, 0, -0.13, w * 0.7, r2)
        slider(S, f, 0, -0.18, w * 0.7, r2)
        knob(S, f, -0.1, -0.06, 0.02, r2)
        knob(S, f, 0.1, -0.06, 0.02, r2)
    elif sym < 4.0:
        toggle_bank(S, f, 0, 0.17, 5, r2, pitch=0.05)
        guarded_switch(S, f, -0.09, 0.0, r2)
        guarded_switch(S, f, 0.09, 0.0, r2)
        led_bar(S, f, -0.12, -0.12, 12, r2, pitch=0.02)
        led_bar(S, f, -0.12, -0.17, 12, r2, pitch=0.02, cls_on=5)
        dial(S, f, 0, -0.06, 0.035, r2)
    elif sym < 5.0:
        vent(S, f, 0, 0.12, w * 0.7, 0.22, 7)
        for sx in (-1, 1):
            round_button(S, f, sx * 0.1, -0.1, 0.02, rr=None, cls=7) if False else round_button(S, f, sx * 0.1, -0.1, 0.02, cls=7 if sx > 0 else 11)
        hazard_strip(S, f, 0, -0.18, w * 0.8, 0.04)
        led_bar(S, f, -0.1, 0.0, 10, r2, pitch=0.02)
    else:                            # outer consoles: lever + small monitor + clusters
        f.box(S, 0, 0.1, 0.0, w - 0.06, 0.2, 0.014, cls=0, bevel=0.004)
        f.box(S, 0, 0.1, 0.014, w - 0.09, 0.16, 0.004, cls=6)
        add_monitor("side_%d" % k, f, 0, 0.1, w - 0.09, 0.16, t=0.019, label="side")
        greeble_patch(S, f, 0, -0.12, w - 0.08, 0.2, 14, r2, hmax=0.03)
        if sym > 6.0:
            # big control lever on the outermost consoles
            p = f.pt(0.0, -0.1, 0.0)
            S.cyl(p, p + f.n * 0.05, 0.05, cls=0, seg=14)
            tip = p + f.n * 0.34 + f.ux * (0.08 if k % 2 else -0.08)
            S.cyl(p + f.n * 0.04, tip, 0.016, 0.012, cls=10, seg=10)
            S.cyl(tip - f.n * 0.0, tip + f.n * 0.0 + (tip - p).normalized() * 0.12, 0.028, 0.024, cls=3, seg=12)
            S.sphere(tip + (tip - p).normalized() * 0.13, 0.026, cls=3, seg=10)
    # the dome sill sits right above the outer edge
    sillp = f.pt(0, depth / 2, 0.02)
    # a small status lamp on every console edge
    add_socket("spark", f.pt(rr.uniform(-0.1, 0.1), rr.uniform(-0.1, 0.2), 0.01), tuple(f.n), "console_%d" % k)

# -- extra: two big dials flanking the main monitors (as in the concept art) and the central warning panel
fc = console_frames[7]
# ---------------------------------------------------------------------------------------------- walls: sides and rear
def wall_point(a, z, off=0.0):
    r = rho(a, 0.0) - off
    return Vector((CEN.x + r * math.cos(a), r * math.sin(a), z))


WALL_A0, WALL_A1 = 112.0, 248.0
NW = 12
for k in range(NW):
    a0 = math.radians(WALL_A0 + (WALL_A1 - WALL_A0) * k / NW)
    a1 = math.radians(WALL_A0 + (WALL_A1 - WALL_A0) * (k + 1) / NW)
    am = (a0 + a1) / 2
    p = wall_point(am, 0.0, 0.0)
    d = Vector((math.cos(am), math.sin(am), 0))
    tng = Vector((-math.sin(am), math.cos(am), 0))
    f = Frame(Vector((p.x, p.y, 0)) + Vector((0, 0, 0)), -tng, -d)       # normal points to the pilot; u to the pilot's right when looking at the wall
    w = (rho(am, 0.0)) * (a1 - a0) + 0.01
    r3 = random.Random(300 + k)
    # base wall
    f.box(S, 0, 0.0, -0.1, w, 2.9, 0.1, cls=0)
    f.box(S, 0, 0.0, 0.0, w - 0.03, 2.86, 0.012, cls=1 if k % 2 else 0)
    # vertical rib between panels
    f.box(S, w / 2, 0.0, 0.0, 0.07, 2.9, 0.1, cls=0, bevel=0.01)
    f.box(S, w / 2, 0.0, 0.1, 0.02, 2.9, 0.012, cls=2 if k % 3 == 0 else 1)
    # modules (v is vertical here: uy = n x ux ... use explicit z positions by mapping v -> z)
    zc = [(-1.2, 0.8), (-0.35, 0.8), (0.55, 0.85)]
    for mi, (zz, hh) in enumerate(zc):
        v = zz - 0.0 + 0.0
        # frame-local v along uy: figure out sign so that v increases with z
        uy_z = f.uy.z
        vs = 1.0 if uy_z >= 0 else -1.0
        vv = vs * zz
        typ = r3.choice(("rack", "switches", "vent", "monitor", "greeble", "pipes", "panel"))
        plate_with_bolts(S, f, 0, vv, w - 0.08, hh - 0.08, cls=r3.choice((0, 1, 1)), th=0.02, rr=r3)
        if typ == "rack":
            for i in range(4):
                f.box(S, 0, vv + vs * (-0.28 + i * 0.18), 0.02, w - 0.14, 0.14, 0.03, cls=0, bevel=0.004)
                led_bar(S, f, -0.1, vv + vs * (-0.28 + i * 0.18) + 0.0, 8, r3, pitch=0.02, cls_on=r3.choice((11, 5, 9)))
                round_button(S, f, 0.14, vv + vs * (-0.28 + i * 0.18), 0.015, cls=r3.choice((7, 11)))
        elif typ == "switches":
            button_grid(S, f, -0.12, vv - 0.2 * vs, 5, 6, 0.05, r3)
            toggle_bank(S, f, 0, vv + 0.3 * vs, 5, r3)
        elif typ == "vent":
            vent(S, f, 0, vv, w - 0.18, hh - 0.2, 10)
        elif typ == "monitor":
            f.box(S, 0, vv, 0.02, w - 0.14, hh * 0.55, 0.02, cls=0, bevel=0.004)
            f.box(S, 0, vv, 0.04, w - 0.18, hh * 0.5, 0.004, cls=6)
            add_monitor("wall_%d_%d" % (k, mi), f, 0, vv, w - 0.18, hh * 0.5, t=0.045, label="wall")
            button_grid(S, f, -0.12, vv - hh * 0.38 * vs, 5, 1, 0.05, r3)
        elif typ == "greeble":
            greeble_patch(S, f, 0, vv, w - 0.12, hh - 0.14, 26, r3)
        elif typ == "pipes":
            for i in range(3):
                f.cyl(S, -0.1 + 0.1 * i, vv, 0.02, 0.02, 0.0, cls=0)
            plate_with_bolts(S, f, 0, vv + 0.25 * vs, w - 0.16, 0.12, cls=2, th=0.03, rr=r3)
        else:
            hazard_strip(S, f, 0, vv + 0.3 * vs, w - 0.14, 0.05, t=0.02)
            dial(S, f, -0.1, vv, 0.05, r3)
            dial(S, f, 0.1, vv, 0.05, r3)
    # hazard band + trim at the floor and the ceiling line
    f.box(S, 0, 0.0, 0.0, w, 0.0, 0.0, cls=0) if False else None

# hatch in the rear wall (the way out for the boarding sequence)
ha = math.radians(180.0)
hp = wall_point(ha, -0.6, 0.05)
hf = Frame(hp, (0, -1, 0), (1, 0, 0))
S.cyl(hp + Vector((0.0, 0, 0)), hp + Vector((0.05, 0, 0)), 0.62, cls=0, seg=36)
S.cyl(hp + Vector((0.04, 0, 0)), hp + Vector((0.09, 0, 0)), 0.55, cls=1, seg=36)
for k in range(20):
    aa = 2 * math.pi * k / 20
    S.cyl(hp + Vector((0.09, 0.5 * math.cos(aa), 0.5 * math.sin(aa))), hp + Vector((0.115, 0.5 * math.cos(aa), 0.5 * math.sin(aa))), 0.016, cls=10, seg=6)
ring(S, (hp.x + 0.1, hp.y), 0.0, hp.z, 0.0, n=1) if False else None
for k in range(24):
    aa = 2 * math.pi * k / 24
    S.box((hp.x + 0.1, hp.y + 0.45 * math.cos(aa), hp.z + 0.45 * math.sin(aa)), (0.012, 0.09, 0.03), rot=(aa, 0, 0), cls=8 if k % 2 else 0)
S.cyl(hp + Vector((0.1, 0, 0)), hp + Vector((0.2, 0, 0)), 0.05, cls=10, seg=12)          # wheel hub
for k in range(3):
    aa = 2 * math.pi * k / 3 + 0.4
    S.cyl(hp + Vector((0.2, 0, 0)), hp + Vector((0.2, 0.26 * math.cos(aa), 0.26 * math.sin(aa))), 0.015, cls=10, seg=8)
S.box((hp.x + 0.1, hp.y + 0.62, hp.z + 0.1), (0.04, 0.08, 0.2), cls=7)
add_lamp("hatch_strobe", (hp.x + 0.25, hp.y, hp.z + 0.7), [1.0, 0.1, 0.05], 3.0, 1.3, "strobe")

# ---------------------------------------------------------------------------------------------- ceiling and overhead
S.cyl((CEN.x + 0.05, 0, 1.1), (CEN.x + 0.05, 0, 1.22), 1.9, cls=0, seg=48)
for k in range(10):
    a = 2 * math.pi * k / 10
    S.box((CEN.x + 0.05 + 1.2 * math.cos(a), 1.2 * math.sin(a), 1.09), (0.5, 0.07, 0.03), rot=(0, 0, a), cls=1)
ring(S, (CEN.x + 0.05, 0), 1.25, 1.075, 0.03, n=48, cls=0)
ring(S, (CEN.x + 0.05, 0), 0.8, 1.07, 0.02, n=40, cls=5)
# overhead console (reachable by looking up): a tilted panel over the dome apex
oc = Vector((0.45, 0, 0.92))
of = Frame(oc, (0, -1, 0), Vector((-0.5, 0, -0.85)))
of.box(S, 0, 0, -0.04, 1.3, 0.5, 0.05, cls=0, bevel=0.01)
of.box(S, 0, 0, 0.0, 1.26, 0.46, 0.01, cls=1)
r4 = random.Random(77)
button_grid(S, of, -0.58, 0.05, 11, 4, 0.05, r4)
for i in range(3):
    toggle_bank(S, of, -0.45 + i * 0.45, -0.17, 5, r4, pitch=0.045)
of.box(S, 0.25, 0.14, 0.0, 0.5, 0.14, 0.016, cls=0, bevel=0.004)
of.box(S, 0.25, 0.14, 0.016, 0.46, 0.11, 0.004, cls=6)
add_monitor("overhead", of, 0.25, 0.14, 0.46, 0.11, t=0.021, label="overhead")
# central hydraulic hub behind the pilot
hub = Vector((-0.55, 0, 1.0))
S.cyl(hub - Vector((0, 0, 0.25)), hub + Vector((0, 0, 0.12)), 0.26, cls=0, seg=30)
for k in range(6):
    aa = 2 * math.pi * k / 6
    S.cyl(hub + Vector((0.26 * math.cos(aa), 0.26 * math.sin(aa), -0.1)), hub + Vector((0.26 * math.cos(aa), 0.26 * math.sin(aa), 0.1)), 0.028, cls=10, seg=8)
for sy in (-1, 1):
    S.cyl(hub + Vector((-0.1, sy * 0.2, -0.2)), Vector((-0.62, sy * 0.38, -0.8)), 0.04, cls=10, seg=10)
    S.cyl(hub + Vector((-0.1, sy * 0.2, -0.2)), Vector((-0.4, sy * 0.28, -0.5)), 0.065, cls=0, seg=12)

# ---------------------------------------------------------------------------------------------- back column and waist ring (the rig that holds the pilot)
col = Vector((-0.62, 0, 0))
S.cyl((col.x, 0, FLOOR - 0.1), (col.x, 0, 1.1), 0.13, cls=1, seg=24)
for z in np.linspace(FLOOR + 0.2, 1.0, 7):
    S.cyl((col.x, 0, z - 0.03), (col.x, 0, z + 0.03), 0.16, cls=2 if int(z * 10) % 2 else 0, seg=24)
for sy in (-1, 1):
    S.cyl((col.x + 0.06, sy * 0.1, FLOOR + 0.1), (col.x + 0.06, sy * 0.1, 0.4), 0.03, cls=10, seg=10)
    S.cyl((col.x + 0.06, sy * 0.1, -0.3), (col.x + 0.06, sy * 0.1, 0.9), 0.05, cls=0, seg=12)
WR = 0.43
ring(S, (0, 0), WR, -0.80, 0.032, n=48, cls=1)
ring(S, (0, 0), WR + 0.04, -0.80, 0.018, n=48, cls=0)
for a_deg in (60, 180, 300):                    # clamps with orange pads
    aa = math.radians(a_deg)
    S.box((WR * math.cos(aa), WR * math.sin(aa), -0.80), (0.12, 0.09, 0.1), rot=(0, 0, aa), cls=2, bevel=0.01)
for sy in (-1, 1):                              # links from the column to the ring
    beam(S, (col.x + 0.1, sy * 0.1, -0.8), (-WR * 0.92, sy * 0.22, -0.8), 0.07, 0.05, (0, 0, 1), cls=1, bevel=0.005)
    beam(S, (col.x + 0.1, sy * 0.1, -0.55), (-WR * 0.9, sy * 0.23, -0.77), 0.04, 0.035, (0, 0, 1), cls=10)

# ---------------------------------------------------------------------------------------------- pipes (dynamic: built as tubes in the game)
rp = random.Random(5)
for k, a_deg in enumerate(range(112, 250, 9)):
    a = math.radians(a_deg)
    for rep in range(2):
        off = 0.1 + 0.07 * rep + rp.uniform(0, 0.03)
        p0 = wall_point(a, FLOOR + 0.12, off)
        p1 = wall_point(a + rp.uniform(-0.08, 0.08), -0.5, off + rp.uniform(0, 0.08))
        p2 = wall_point(a + rp.uniform(-0.1, 0.1), 0.45, off + rp.uniform(0, 0.1))
        p3 = wall_point(a + rp.uniform(-0.12, 0.12), 1.04, off + rp.uniform(0.0, 0.15))
        add_pipe([p0, p1, p2, p3], rp.choice((0.018, 0.024, 0.032, 0.04)), cls=rp.choice((0, 1, 10)), steam=rp.choice((0, 0, 0.4, 1.0)))
# pipes framing the window: from the side consoles up along the dome ribs
for sgn in (1, -1):
    for rep in range(4):
        ang = math.radians(sgn * (74 + 7 * rep))
        pts = []
        for t_, vv in enumerate((-0.2, 0.0, 0.3, 0.55, 0.72)):
            uu = ang + sgn * math.radians(1.5 * t_)
            p = dome_pt(uu, vv)
            nn = dome_n(p)
            pts.append(p - nn * (0.07 + 0.04 * rep))
        add_pipe(pts, 0.022 + 0.008 * (rep % 2), cls=rp.choice((0, 1, 10)), steam=rp.choice((0.6, 1.0)))
# thick bundle in the upper corners (like the concept art)
for sgn in (1, -1):
    for rep in range(3):
        pts = [Vector((0.4, sgn * 1.55, -0.6)), Vector((0.55, sgn * 1.45, -0.1 + 0.05 * rep)), Vector((0.5, sgn * 1.2, 0.5 + 0.04 * rep)), Vector((0.3, sgn * 0.75, 0.95)), Vector((0.1, sgn * 0.3, 1.04))]
        add_pipe(pts, 0.036 - 0.006 * rep, cls=(0, 1, 10)[rep], steam=0.8 if rep == 1 else 0.0)
# ceiling collectors
for k in range(8):
    a = 2 * math.pi * k / 8 + 0.2
    pts = [Vector((CEN.x + 0.05 + 0.25 * math.cos(a), 0.25 * math.sin(a), 1.06)), Vector((CEN.x + 0.05 + 0.7 * math.cos(a + 0.2), 0.7 * math.sin(a + 0.2), 1.0)), Vector((CEN.x + 0.05 + 1.2 * math.cos(a + 0.1), 1.2 * math.sin(a + 0.1), 0.9)), Vector((CEN.x + 0.05 + 1.5 * math.cos(a), 1.5 * math.sin(a), 0.55))]
    add_pipe(pts, 0.026 if k % 2 else 0.036, cls=k % 3 if k % 3 != 2 else 10, steam=rp.choice((0, 0.5)))
# flanges / joint collars along the dome-side pipes become steam sockets
for p in LAY["pipes"]:
    if p["steam"] > 0:
        pts = p["pts"]
        mid = pts[len(pts) // 2]
        add_socket("steam", mid, (0, 0, 1), p["id"])

# ---------------------------------------------------------------------------------------------- dangling and standing wires
rw = random.Random(9)
cols = ["black", "black", "orange", "red", "blue", "grey"]
for k in range(54):
    if k < 34:
        a = rw.uniform(-2.6, 2.6) if rw.random() < 0.65 else rw.uniform(2.8, 3.5)
        rad = rw.uniform(0.2, 1.4)
        anchor = (CEN.x + 0.05 + rad * math.cos(a), rad * math.sin(a), 1.05)
        add_wire(anchor, (rw.uniform(-0.2, 0.2), rw.uniform(-0.2, 0.2), -1.0), rw.uniform(0.35, 1.0), rw.choice((0.006, 0.008, 0.011, 0.015)), rw.choice(cols), "hang")
    else:
        kk = rw.randrange(NSEG)
        f = console_frames[kk]
        p = f.pt(rw.uniform(-0.1, 0.1), rw.uniform(0.15, 0.25), 0.0)
        dd = (f.n * 1.0 + f.uy * 0.4 + f.ux * rw.uniform(-0.5, 0.5)).normalized()
        add_wire(p, tuple(dd), rw.uniform(0.25, 0.6), rw.choice((0.006, 0.009)), rw.choice(cols), "stick")

# ---------------------------------------------------------------------------------------------- lamps and effect sockets
add_lamp("dash_cyan", (0.55, 0.0, -0.75), [0.15, 0.85, 1.0], 2.2, 2.2)
add_lamp("left_amber", (0.5, 1.1, -0.7), [1.0, 0.42, 0.1], 1.6, 2.0)
add_lamp("right_amber", (0.5, -1.1, -0.7), [1.0, 0.42, 0.1], 1.6, 2.0)
add_lamp("ceiling_white", (0.2, 0.0, 0.95), [0.75, 0.85, 1.0], 1.4, 3.0)
add_lamp("alarm_front_l", (0.9, 0.9, 0.95), [1.0, 0.04, 0.02], 3.0, 2.4, "beacon")
add_lamp("alarm_front_r", (0.9, -0.9, 0.95), [1.0, 0.04, 0.02], 3.0, 2.4, "beacon")
add_lamp("alarm_rear", (-1.2, 0.0, 0.9), [1.0, 0.04, 0.02], 2.5, 2.4, "beacon")
for sy in (-1, 1):
    S.cyl((0.9, sy * 0.9, 1.07), (0.9, sy * 0.9, 0.97), 0.07, cls=0, seg=14)
    S.cyl((0.9, sy * 0.9, 0.97), (0.9, sy * 0.9, 0.9), 0.055, cls=7, seg=14)
S.cyl((-1.2, 0, 1.07), (-1.2, 0, 0.97), 0.07, cls=0, seg=14)
S.cyl((-1.2, 0, 0.97), (-1.2, 0, 0.9), 0.055, cls=7, seg=14)
# fire sockets in the front corners and on the consoles
for sgn in (-1, 1):
    add_socket("fire", (0.7, sgn * 1.1, -0.85), (0, 0, 1), "fire_front_%d" % sgn)
    add_socket("fire", (-0.3, sgn * 1.45, -0.9), (0, 0, 1), "fire_side_%d" % sgn)
    add_socket("fire", (0.2, sgn * 0.8, 0.9), (0, 0, -1), "fire_ceiling_%d" % sgn)
for k in range(10):
    add_socket("spark", (rw.uniform(0.0, 0.9), rw.uniform(-1.3, 1.3), 1.03), (0, 0, -1), "ceiling_spark_%d" % k)

shell = S.finish()
glass = G.finish()

# =============================================================================================================== PILOT BODY
HIP_Z = -0.82
LAY["body"] = {"hip_l": [0.0, 0.115, HIP_Z], "hip_r": [0.0, -0.115, HIP_Z], "thigh": 0.38, "shin": 0.36, "pelvis": [0.0, 0.0, HIP_Z], "torso_pivot": [0.0, 0.0, HIP_Z], "waist_ring": [0.0, 0.0, -0.80]}


def body_part(name, builder):
    bb = B(name)
    builder(bb)
    return bb.finish()


def build_boot(b):
    # pivot at the ankle; foot points +X
    b.box((0.06, 0, -0.045), (0.30, 0.115, 0.075), cls=12, bevel=0.015)
    b.box((0.09, 0, -0.06), (0.30, 0.125, 0.04), cls=3, bevel=0.01)                  # sole
    b.box((0.11, 0, 0.0), (0.18, 0.10, 0.07), cls=13, bevel=0.012)                    # toe cap armour
    b.box((-0.02, 0, 0.0), (0.12, 0.11, 0.1), cls=13, bevel=0.012)
    b.box((0.06, 0, 0.026), (0.12, 0.07, 0.02), cls=2, bevel=0.004)
    b.cyl((-0.02, -0.055, 0.02), (-0.02, 0.055, 0.02), 0.03, cls=0, seg=10)           # ankle joint
    for k in range(3):
        b.box((0.0 + 0.05 * k, 0, 0.03), (0.02, 0.095, 0.012), cls=9 if k == 1 else 0)


def build_shin(b):
    # pivot at the knee, runs down -Z, length 0.36
    L = 0.36
    b.cyl((0, 0, 0), (0, 0, -L), 0.058, 0.044, cls=12, seg=16)
    b.box((0.04, 0, -0.14), (0.045, 0.1, 0.24), cls=13, bevel=0.01)                   # front shin guard
    b.box((0.052, 0, -0.14), (0.01, 0.06, 0.2), cls=2)
    b.cyl((0.0, -0.06, -0.06), (0.0, 0.06, -0.06), 0.032, cls=0, seg=10)
    for z in (-0.06, -0.22, -0.3):
        b.cyl((0, 0, z - 0.012), (0, 0, z + 0.012), 0.066 - 0.001 * abs(z) * 10, cls=0, seg=14)
    b.box((0.0, 0.06, -0.2), (0.05, 0.016, 0.18), cls=5)
    b.pipe([(0.0, -0.05, -0.04), (-0.06, -0.06, -0.18), (-0.04, -0.045, -0.33)], 0.008, cls=3, collars=False)


def build_thigh(b):
    L = 0.38
    b.cyl((0, 0, 0), (0, 0, -L), 0.075, 0.06, cls=12, seg=16)
    b.box((0.05, 0, -0.17), (0.05, 0.12, 0.28), cls=13, bevel=0.012)
    b.box((0.062, 0, -0.17), (0.01, 0.07, 0.2), cls=2)
    b.sphere((0.045, 0, -L + 0.03), 0.055, cls=13, seg=10)                              # knee cap
    b.cyl((0.0, -0.075, 0.0), (0.0, 0.075, 0.0), 0.04, cls=0, seg=12)                  # hip joint
    b.box((0.0, 0.075, -0.2), (0.04, 0.016, 0.26), cls=9)
    for z in (-0.05, -0.17, -0.3):
        b.cyl((0, 0, z - 0.01), (0, 0, z + 0.01), 0.083, cls=0, seg=14)
    b.pipe([(-0.04, 0.05, 0.0), (-0.08, 0.06, -0.16), (-0.05, 0.05, -0.34)], 0.011, cls=3, collars=False)


def build_pelvis(b):
    b.box((0, 0, 0.02), (0.26, 0.34, 0.14), cls=12, bevel=0.02)
    b.box((0.02, 0, 0.02), (0.22, 0.3, 0.1), cls=13, bevel=0.02)                       # front hip armour
    b.box((0.13, 0, -0.01), (0.06, 0.12, 0.1), cls=2, bevel=0.012)                     # cod plate
    b.box((0, 0, 0.1), (0.3, 0.38, 0.045), cls=0, bevel=0.01)                          # belt
    for sy in (-1, 1):
        b.box((0.08, sy * 0.19, 0.09), (0.08, 0.05, 0.07), cls=13, bevel=0.008)       # belt pouches
        b.box((0.0, sy * 0.175, 0.0), (0.12, 0.05, 0.14), cls=13, bevel=0.012)         # side hip plates
        b.box((0.07, sy * 0.19, 0.09), (0.02, 0.04, 0.012), cls=5)
    for k in range(6):
        b.box((0.145, -0.1 + 0.04 * k, 0.1), (0.012, 0.022, 0.03), cls=5 if k % 2 else 9)


def build_torso(b):
    # pivot at the hip centre; chest top at about +0.62 (the neck is at +0.7)
    b.box((0.0, 0, 0.12), (0.22, 0.28, 0.2), cls=12, bevel=0.03)                       # abdomen
    for z in (0.05, 0.11, 0.17, 0.23):
        b.box((0.02, 0, z), (0.2, 0.3, 0.035), cls=13 if z > 0.1 else 0, bevel=0.01)   # ab plates
    b.box((0.0, 0, 0.42), (0.27, 0.42, 0.33), cls=12, bevel=0.04)                      # chest
    b.box((0.065, 0, 0.44), (0.2, 0.38, 0.28), cls=13, bevel=0.04)                     # chest armour
    b.box((0.17, 0, 0.45), (0.03, 0.12, 0.12), cls=0, bevel=0.01)                      # core housing
    b.cyl((0.19, 0, 0.45), (0.205, 0, 0.45), 0.044, cls=14, seg=6)                     # glowing core (hex)
    for sy in (-1, 1):
        b.box((0.075, sy * 0.1, 0.46), (0.05, 0.1, 0.22), cls=2, bevel=0.01)           # orange pecs plates
        b.box((0.0, sy * 0.24, 0.54), (0.17, 0.12, 0.1), cls=13, bevel=0.03)           # shoulder pads
        b.cyl((0.0, sy * 0.21, 0.51), (0.0, sy * 0.3, 0.51), 0.045, cls=0, seg=12)     # shoulder joints
        b.box((0.0, sy * 0.24, 0.585), (0.15, 0.08, 0.016), cls=2)
        b.box((-0.05, sy * 0.1, 0.5), (0.04, 0.05, 0.3), cls=3)                         # harness straps (back)
    b.box((0.1, 0, 0.62), (0.07, 0.34, 0.06), cls=13, bevel=0.01)                      # collar
    b.box((0.0, 0, 0.64), (0.08, 0.1, 0.07), cls=12)                                    # neck
    for k in range(5):
        b.box((0.16, -0.08 + 0.04 * k, 0.33), (0.012, 0.022, 0.016), cls=9 if k == 2 else 5)
    # cables from the chest port
    b.pipe([(0.18, 0.1, 0.34), (0.25, 0.14, 0.2), (0.22, 0.2, 0.0)], 0.014, cls=3, collars=False)
    b.pipe([(0.18, -0.1, 0.34), (0.25, -0.14, 0.2), (0.22, -0.2, 0.0)], 0.014, cls=3, collars=False)
    # backpack unit
    b.box((-0.17, 0, 0.42), (0.14, 0.3, 0.34), cls=0, bevel=0.02)
    b.box((-0.25, 0, 0.42), (0.04, 0.22, 0.26), cls=1, bevel=0.01)
    for sy in (-1, 1):
        b.cyl((-0.22, sy * 0.08, 0.6), (-0.3, sy * 0.1, 0.8), 0.022, cls=3, seg=8)


boots = body_part("SM_Body_Boot", build_boot)
shins = body_part("SM_Body_Shin", build_shin)
thighs = body_part("SM_Body_Thigh", build_thigh)
pelvis = body_part("SM_Body_Pelvis", build_pelvis)
torso = body_part("SM_Body_Torso", build_torso)

# =============================================================================================================== ARMS (the drive-suit sleeves on the rig; same contract as v1)
def rig_upper():
    R = B("SM_Rig_Upper")
    L = 0.55
    R.cyl((0, 0, 0), (L, 0, 0), 0.085, 0.075, cls=12, seg=20)
    R.sphere((0, 0, 0), 0.105, cls=0, seg=16)
    for t in (0.18, 0.5, 0.82):
        R.cyl((L * t - 0.02, 0, 0), (L * t + 0.02, 0, 0), 0.098, cls=1, seg=20)
    R.box((L * 0.5, 0, 0.1), (0.4, 0.15, 0.06), cls=13, bevel=0.015)
    R.box((L * 0.5, 0, 0.135), (0.3, 0.1, 0.012), cls=2)
    R.cyl((0.05, 0.0, 0.12), (L - 0.05, 0.0, 0.07), 0.028, cls=10, seg=12)
    R.box((L * 0.55, 0, -0.1), (0.3, 0.14, 0.06), cls=2, bevel=0.012)
    for k in range(5):
        R.box((0.1 + k * 0.085, 0.09, 0.0), (0.04, 0.02, 0.05), cls=5 if k == 2 else 0, bevel=0.003)
    R.pipe([(0.02, -0.09, 0.05), (L * 0.5, -0.12, 0.06), (L - 0.03, -0.09, 0.03)], 0.018, cls=3, collars=False)
    return R.finish()


def rig_fore():
    R = B("SM_Rig_Fore")
    L = 0.55
    R.sphere((0, 0, 0), 0.095, cls=0, seg=16)
    R.cyl((0, 0, 0), (L, 0, 0), 0.078, 0.062, cls=12, seg=20)
    for t in (0.22, 0.55, 0.85):
        R.cyl((L * t - 0.02, 0, 0), (L * t + 0.02, 0, 0), 0.088 - 0.012 * t, cls=1, seg=20)
    R.box((L * 0.55, 0, 0.075), (0.38, 0.16, 0.05), cls=13, bevel=0.012)
    R.box((L * 0.55, 0, 0.1), (0.3, 0.1, 0.01), cls=2)
    R.cyl((0.04, -0.05, -0.11), (L - 0.04, -0.03, -0.075), 0.022, cls=10, seg=10)
    for k in range(4):
        R.box((0.18 + k * 0.09, 0.075, 0.0), (0.03, 0.02, 0.04), cls=9 if k % 2 == 0 else 0, bevel=0.003)
    R.box((L * 0.4, 0.0, -0.085), (0.22, 0.12, 0.04), cls=0, bevel=0.01)
    return R.finish()


def rig_glove():
    R = B("SM_Rig_Glove")
    R.sphere((0, 0, 0), 0.08, cls=0, seg=14)
    R.cyl((0, 0, 0), (0.12, 0, 0), 0.07, 0.065, cls=1, seg=18)
    R.cyl((0.04, 0, 0), (0.09, 0, 0), 0.085, cls=2, seg=18)
    R.box((0.24, 0, 0), (0.16, 0.15, 0.1), cls=3, bevel=0.03)
    R.box((0.24, 0, 0.055), (0.15, 0.14, 0.03), cls=13, bevel=0.01)
    for k, yy in enumerate((-0.054, -0.018, 0.018, 0.054)):
        R.box((0.37, yy, 0.012), (0.1, 0.032, 0.05), rot=(0, math.radians(-20), 0), cls=3, bevel=0.012)
        R.box((0.43, yy, -0.024), (0.07, 0.03, 0.044), rot=(0, math.radians(-70), 0), cls=3, bevel=0.01)
    R.box((0.26, 0.095, -0.015), (0.1, 0.04, 0.05), rot=(0, 0, math.radians(30)), cls=3, bevel=0.012)
    R.cyl((0.38, -0.12, -0.03), (0.38, 0.12, -0.03), 0.018, cls=10, seg=12)
    R.box((0.22, 0, -0.115), (0.34, 0.26, 0.04), cls=13, bevel=0.015)
    R.box((0.22, 0.13, 0.0), (0.34, 0.04, 0.2), cls=13, bevel=0.015)
    R.box((0.22, -0.13, 0.0), (0.34, 0.04, 0.2), cls=13, bevel=0.015)
    R.box((0.05, 0, 0.1), (0.06, 0.3, 0.05), cls=1, bevel=0.012)
    R.box((0.22, 0.152, 0.0), (0.3, 0.008, 0.03), cls=2)
    R.box((0.22, -0.152, 0.0), (0.3, 0.008, 0.03), cls=2)
    for sy in (-1, 1):
        R.box((0.30, sy * 0.15, 0.03), (0.07, 0.012, 0.025), cls=5 if sy > 0 else 7, bevel=0.002)
    return R.finish()


up, fo, gl = rig_upper(), rig_fore(), rig_glove()

# =============================================================================================================== export
objs = {"SM_Cockpit_Shell": shell, "SM_Cockpit_Glass": glass, "SM_Body_Boot": boots, "SM_Body_Shin": shins, "SM_Body_Thigh": thighs, "SM_Body_Pelvis": pelvis,
        "SM_Body_Torso": torso, "SM_Rig_Upper": up, "SM_Rig_Fore": fo, "SM_Rig_Glove": gl}
for name, ob in objs.items():
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    path = os.path.join(OUT, name + ".fbx")
    bpy.ops.export_scene.fbx(filepath=path, use_selection=True, apply_scale_options="FBX_SCALE_UNITS", global_scale=1.0,
                             axis_forward="-Y", axis_up="Z", object_types={"MESH"}, mesh_smooth_type="EDGE", bake_space_transform=False, path_mode="AUTO")
    print("EXPORTED", path, len(ob.data.polygons), "faces")
with open(os.path.join(OUT, "cockpit_layout.json"), "w") as fh:
    json.dump(LAY, fh, separators=(",", ":"))
print("LAYOUT pipes %d wires %d monitors %d lamps %d sockets %d" % (len(LAY["pipes"]), len(LAY["wires"]), len(LAY["monitors"]), len(LAY["lamps"]), len(LAY["sockets"])))

if PREVIEW:
    sc = bpy.context.scene
    sc.view_settings.view_transform = "Standard"
    sc.render.engine = "BLENDER_EEVEE_NEXT"
    sc.render.resolution_x, sc.render.resolution_y = 1600, 900
    world = bpy.data.worlds.new("W"); sc.world = world; world.use_nodes = True
    world.node_tree.nodes["Background"].inputs[0].default_value = (0.5, 0.58, 0.8, 1)
    cols_ = {0: (0.09, 0.09, 0.105), 1: (0.28, 0.3, 0.34), 2: (0.7, 0.24, 0.02), 3: (0.015, 0.015, 0.02), 4: (0.0, 0.7, 1.0), 5: (1.0, 0.45, 0.05), 6: (0.0, 0.02, 0.03), 7: (1.0, 0.05, 0.03),
             8: (0.8, 0.6, 0.0), 9: (0.9, 0.95, 1.0), 10: (0.5, 0.5, 0.52), 11: (0.1, 1.0, 0.2), 12: (0.05, 0.06, 0.08), 13: (0.1, 0.11, 0.13), 14: (0.0, 0.9, 1.0)}
    emissive = {4, 5, 7, 9, 11, 14}
    for ob in objs.values():
        me = ob.data
        cls = np.empty(len(me.vertices)); me.attributes["cls"].data.foreach_get("value", cls)
        ca = me.color_attributes.new("PC", "FLOAT_COLOR", "POINT")
        arr = np.array([list(cols_[int(round(c))]) + [1.0] for c in cls], np.float32)
        ca.data.foreach_set("color", arr.ravel())
        em = me.color_attributes.new("EM", "FLOAT_COLOR", "POINT")
        arr2 = np.array([(list(cols_[int(round(c))]) if int(round(c)) in emissive else [0, 0, 0]) + [1.0] for c in cls], np.float32)
        em.data.foreach_set("color", arr2.ravel())
        m = bpy.data.materials.new("P"); m.use_nodes = True
        nt = m.node_tree; bsdf = nt.nodes["Principled BSDF"]
        vc = nt.nodes.new("ShaderNodeVertexColor"); vc.layer_name = "PC"
        ve = nt.nodes.new("ShaderNodeVertexColor"); ve.layer_name = "EM"
        nt.links.new(vc.outputs[0], bsdf.inputs["Base Color"]); bsdf.inputs["Metallic"].default_value = 0.55; bsdf.inputs["Roughness"].default_value = 0.42
        nt.links.new(ve.outputs[0], bsdf.inputs["Emission Color"]); bsdf.inputs["Emission Strength"].default_value = 2.0
        me.materials.clear(); me.materials.append(m)
    gm = bpy.data.materials.new("GL"); gm.use_nodes = True
    gb = gm.node_tree.nodes["Principled BSDF"]; gb.inputs["Base Color"].default_value = (0.3, 0.5, 0.7, 1); gb.inputs["Alpha"].default_value = 0.08
    glass.data.materials.clear(); glass.data.materials.append(gm)
    # body in a standing pose
    def put(src, loc, rot=(0, 0, 0), scale=(1, 1, 1), name="X"):
        ob = src.copy(); ob.data = src.data; ob.name = name
        bpy.context.scene.collection.objects.link(ob)
        ob.location = loc; ob.rotation_euler = rot; ob.scale = scale
    put(pelvis, (0, 0, HIP_Z), name="pel")
    put(torso, (0, 0, HIP_Z), name="tor")
    for sy, nm in ((1, "L"), (-1, "R")):
        put(thighs, (0, sy * 0.115, HIP_Z), scale=(1, sy, 1), name="th" + nm)
        put(shins, (0.0, sy * 0.115, HIP_Z - 0.38), scale=(1, sy, 1), name="sh" + nm)
        put(boots, (0.0, sy * 0.115, HIP_Z - 0.38 - 0.36), scale=(1, sy, 1), name="bt" + nm)
    for nm, src, loc, rot in (("UpL", up, (0.25, 0.30, -0.45), (0, math.radians(15), math.radians(-14))), ("FoL", fo, (0.78, 0.22, -0.40), (0, math.radians(8), math.radians(-8))), ("GlL", gl, (1.30, 0.12, -0.36), (0, 0, 0))):
        put(src, loc, rot, name=nm)
        put(src, (loc[0], -loc[1], loc[2]), (rot[0], rot[1], -rot[2]), (1, -1, 1), nm + "R")
    for o in (up, fo, gl, glass, boots, shins, thighs, pelvis, torso):
        o.hide_render = True
    # monitors lit cyan
    mm = bpy.data.materials.new("MON"); mm.use_nodes = True
    mb = mm.node_tree.nodes["Principled BSDF"]; mb.inputs["Base Color"].default_value = (0, 0.05, 0.08, 1); mb.inputs["Emission Color"].default_value = (0.0, 0.6, 1.0, 1); mb.inputs["Emission Strength"].default_value = 1.5
    for mon in LAY["monitors"]:
        bm_ = bmesh.new()
        c = Vector(mon["c"]); r_ = Vector(mon["right"]); u_ = Vector(mon["up"])
        hw, hh = mon["w"] / 2, mon["h"] / 2
        vs = [bm_.verts.new(c + r_ * sx * hw + u_ * sy * hh + Vector(mon["n"]) * 0.002) for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
        bm_.faces.new(vs)
        me = bpy.data.meshes.new("mon"); bm_.to_mesh(me); bm_.free()
        mo = bpy.data.objects.new("mon", me); sc.collection.objects.link(mo); me.materials.append(mm)
    # lights
    for loc, e, c in (((-1.0, 0.8, 0.5), 150.0, (1.0, 0.9, 0.8)), ((-1.0, -0.8, 0.5), 150.0, (0.8, 0.9, 1.0)), ((0.2, 0.0, 0.9), 120.0, (0.6, 0.8, 1.0)), ((0.6, 1.0, -0.6), 60.0, (1.0, 0.55, 0.25)), ((0.6, -1.0, -0.6), 60.0, (0.4, 0.7, 1.0)), ((-0.6, 0.0, 0.4), 50.0, (1.0, 0.9, 0.8)), ((0.3, 0.0, -0.9), 30.0, (0.2, 0.8, 1.0))):
        bpy.ops.object.light_add(type="POINT", location=loc); L = bpy.context.object; L.data.energy = e; L.data.color = c
    cd = bpy.data.cameras.new("C"); cd.lens = 17.4; cd.sensor_width = 36
    cam = bpy.data.objects.new("C", cd); sc.collection.objects.link(cam); sc.camera = cam
    cam.location = (0, 0, 0)

    def shot(name, pitch_deg, yaw_deg, lens=17.4):
        cd.lens = lens
        cam.rotation_euler = Euler((math.radians(90 + pitch_deg), 0, math.radians(-90 + yaw_deg)), "XYZ")
        sc.render.filepath = os.path.join(OUT, name + ".png"); bpy.ops.render.render(write_still=True)
    shot("prev_front", 0, 0)
    shot("prev_down", -62, 0)
    shot("prev_left", -8, 85)
    shot("prev_up", 55, 0)
    shot("prev_back", -10, 180)
    cam.location = (-1.9, 2.2, 0.8); cam.rotation_euler = Vector((1.8, -1.6, -0.5)).to_track_quat("-Z", "Y").to_euler(); cd.lens = 22
    for o in (shell,):
        pass
    sc.render.filepath = os.path.join(OUT, "prev_outer.png"); bpy.ops.render.render(write_still=True)
    # debug: top-down (ceiling clipped away) and side orthographic
    cd.type = "ORTHO"; cd.ortho_scale = 5.0; cd.clip_start = 0.01
    cam.location = (0, 0, 3.0); cam.rotation_euler = (0, 0, math.radians(-90)); cd.clip_start = 1.85
    sc.render.filepath = os.path.join(OUT, "prev_top.png"); bpy.ops.render.render(write_still=True)
    cd.clip_start = 0.01
    cam.location = (0, 4.0, -0.2); cam.rotation_euler = (math.radians(90), 0, math.radians(180))
    sc.render.filepath = os.path.join(OUT, "prev_side.png"); bpy.ops.render.render(write_still=True)
    print("PREVIEW DONE")
