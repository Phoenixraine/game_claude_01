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


# ===================================================================================================================== SHELL v4
# Recreates the concept image: a wide raked windshield between two inward-leaning A-pillars, a heavy overhead gantry with hanging cables,
# a low desk with a big radar screen in the middle, tilted side consoles with screens, and two massive hydraulic control arms.
# Everything is dark graphite; orange / cyan appear only as small lamps and screens.
# Placement helper: scr(px, py, depth) maps a pixel of the 1672x941 concept image (90 deg horizontal FOV) to a point at a given depth.
TH = 1.0355
TV = TH * 9.0 / 16.0


def scr(px, py, d):
    return Vector((d, -((px - 836.0) / 836.0 * TH) * d, -((py - 470.5) / 470.5 * TV) * d))


def facing(o, yaw=0.0, pitch=0.0):
    """Frame at o whose normal points to the pilot's eye (optionally turned): u = pilot's right, v = up."""
    o = Vector(o)
    n = (-o).normalized()
    n = Matrix.Rotation(math.radians(yaw), 3, "Z") @ n
    n = Matrix.Rotation(math.radians(pitch), 3, "Y") @ n
    return Frame(o, Vector((0, -1, 0)), n)


def screen(f, w, h, mid, bez=0.028, depth=0.05, lamp=None):
    """A bezelled display on frame f (origin = screen centre). Registers it as a game monitor."""
    f.box(S, 0, 0, -depth, w + 2 * bez, h + 2 * bez, depth, cls=0, bevel=0.006)
    f.box(S, 0, 0, 0.0, w + 2 * bez - 0.012, h + 2 * bez - 0.012, 0.006, cls=1, bevel=0.003)
    f.box(S, 0, 0, 0.004, w, h, 0.004, cls=6)
    add_monitor(mid, f, 0, 0, w, h, t=0.0085, label=mid)
    # bolts in the bezel corners and a small status lamp under it
    for sx in (-1, 1):
        for sy in (-1, 1):
            f.cyl(S, sx * (w / 2 + bez * 0.5), sy * (h / 2 + bez * 0.5), 0.004, 0.012, 0.0045, cls=10, seg=6)
    if lamp is not None:
        f.box(S, w / 2 - 0.02, -h / 2 - bez * 0.55, 0.004, 0.018, 0.008, 0.006, cls=lamp)


def housing(f, w, h, depth, cls=0):
    """The shell behind a tilted panel: tapers back to the desk."""
    f.box(S, 0, 0, -depth, w * 0.92, h * 0.92, depth, cls=cls, bevel=0.01)
    f.box(S, 0, 0, -depth - 0.04, w * 0.7, h * 0.7, 0.04, cls=1, bevel=0.01)


rr = random.Random(11)
S = B("SM_Cockpit_Shell")
G = B("SM_Cockpit_Glass")

# ---------------------------------------------------------------------------------------------- floor and drive platform (darker than v3)
S.cyl((0, 0, FLOOR - 0.14), (0, 0, FLOOR), 1.1, cls=0, seg=56)
S.cyl((0, 0, FLOOR - 0.02), (0, 0, FLOOR + 0.02), 1.15, cls=1, seg=56)
ring(S, (0, 0), 1.06, FLOOR + 0.025, 0.008, n=64, cls=5)
ring(S, (0, 0), 0.62, FLOOR + 0.02, 0.006, n=48, cls=4)
for k in range(24):
    a = 2 * math.pi * k / 24
    S.box((0.85 * math.cos(a), 0.85 * math.sin(a), FLOOR + 0.012), (0.5, 0.06, 0.012), rot=(0, 0, a), cls=0)
for sy in (-1, 1):
    S.box((0.04, sy * 0.15, FLOOR + 0.014), (0.36, 0.15, 0.014), cls=0, bevel=0.004)
    S.box((0.04, sy * 0.15, FLOOR + 0.022), (0.30, 0.11, 0.004), cls=4)
    for k in range(4):
        S.box((-0.12 + 0.08 * k, sy * 0.15, FLOOR + 0.026), (0.012, 0.09, 0.004), cls=0)
S.cyl((0, 0, FLOOR - 0.55), (0, 0, FLOOR - 0.16), 2.4, cls=0, seg=56)
for k in range(30):
    a = 2 * math.pi * k / 30
    S.box((1.45 * math.cos(a), 1.45 * math.sin(a), FLOOR - 0.15), (0.7, 0.05, 0.02), rot=(0, 0, a), cls=1 if k % 3 else 0)
for k in range(8):
    a = 2 * math.pi * k / 8 + 0.2
    ring(S, (0, 0), 1.3 + 0.06 * k, FLOOR - 0.12, 0.014 + 0.003 * (k % 3), n=40, cls=0 if k % 2 else 3, a0=a, a1=a + 0.9)
for k in range(36):
    a = 2 * math.pi * k / 36
    S.box((1.17 * math.cos(a), 1.17 * math.sin(a), FLOOR + 0.004), (0.12, 0.05, 0.008), rot=(0, 0, a), cls=8 if k % 4 == 0 else 0)

# ---------------------------------------------------------------------------------------------- the A-pillars (lean in at the bottom, like the concept)
PIL = {}
for sd in (1, -1):          # +1 = left (y > 0)
    pt_top = scr(836 - sd * 790, -130, 0.95)
    pt_bot = scr(836 - sd * 500, 760, 1.5)
    PIL[sd] = (pt_top, pt_bot)
    ax = (pt_bot - pt_top).normalized()
    L = (pt_bot - pt_top).length
    # slim main beam, a thin glass-side fin and an outer fin: dark graphite, like the concept
    beam(S, pt_top - ax * 0.12, pt_bot + ax * 0.12, 0.065, 0.17, (-1, 0, 0), cls=0, bevel=0.01)
    beam(S, pt_top + Vector((0.0, -sd * 0.04, 0.0)), pt_bot + Vector((0.0, -sd * 0.04, 0.0)), 0.018, 0.2, (-1, 0, 0), cls=1, bevel=0.004)
    beam(S, pt_top + Vector((-0.02, sd * 0.05, 0.0)), pt_bot + Vector((-0.02, sd * 0.05, 0.0)), 0.03, 0.12, (-1, 0, 0), cls=0, bevel=0.005)
    # armour plating on the cabin-facing side: many small plates with bolts
    n_in = Vector((-1, 0, 0.0)) + Vector((0, -sd * 0.05, 0.08))
    pf = Frame((pt_top + pt_bot) / 2 + Vector((-0.085, 0, 0)), ax, n_in)
    for k in range(9):
        v = (k - 4.0) * L / 9.4
        pf.box(S, v, 0.0, 0.0, L / 10.0, 0.07, 0.016, cls=1 if k % 3 == 1 else 0, bevel=0.004)
        for sy in (-1, 1):
            pf.cyl(S, v, sy * 0.03, 0.016, 0.022, 0.0045, cls=10, seg=6)
        if k % 3 == 0:
            pf.box(S, v + L * 0.03, 0.0, 0.016, 0.03, 0.045, 0.01, cls=0, bevel=0.002)
    # tiny amber status lamps (the only colour on the pillar)
    pf.box(S, -L * 0.30, 0.0, 0.018, 0.035, 0.012, 0.006, cls=5)
    pf.box(S, L * 0.2, 0.0, 0.018, 0.02, 0.012, 0.006, cls=5)
    # hydraulic strut and bundled cables clipped to the outside of the pillar
    b0 = pt_top + Vector((-0.04, sd * 0.1, -0.05))
    b1 = pt_bot + Vector((-0.04, sd * 0.11, 0.05))
    S.cyl(b0, b1, 0.028, cls=0, seg=12)
    S.cyl(b0 + (b1 - b0) * 0.1, b0 + (b1 - b0) * 0.5, 0.04, cls=10, seg=12)
    for q in (0.12, 0.3, 0.5, 0.7, 0.9):
        c = b0 + (b1 - b0) * q
        S.cyl(c - ax * 0.018, c + ax * 0.018, 0.05, cls=1, seg=12)
    for off in (0.07, 0.1):
        S.cyl(b0 + Vector((-0.02, sd * off, 0)), b1 + Vector((-0.02, sd * off, 0)), 0.012, cls=3, seg=8)

# ---------------------------------------------------------------------------------------------- header, windshield and sill
hdrL, hdrR = PIL[1][0], PIL[-1][0]
beam(S, hdrL, hdrR, 0.12, 0.22, (0, 0, 1), cls=0, bevel=0.012)
beam(S, hdrL + Vector((-0.1, 0, 0.1)), hdrR + Vector((-0.1, 0, 0.1)), 0.07, 0.14, (0, 0, 1), cls=1, bevel=0.01)
sillL, sillR = PIL[1][1], PIL[-1][1]
beam(S, sillL + Vector((0.0, 0, -0.07)), sillR + Vector((0.0, 0, -0.07)), 0.1, 0.16, (0, 0, 1), cls=0, bevel=0.01)
# orange lamps in the header (little accents like the concept) and warning chevrons
for sx in (-0.55, -0.25, 0.25, 0.55):
    S.box(Vector((hdrL.x - 0.13, sx, hdrL.z - 0.07)), (0.012, 0.03, 0.01), cls=5)
S.box(Vector((hdrL.x - 0.13, 0.0, hdrL.z - 0.08)), (0.012, 0.2, 0.008), cls=8)

# the glass: one big raked pane between the pillars and a thinner lower pane over the desk
def glass_quad(pts):
    vs = [G.bm.verts.new(p) for p in pts]
    for v in vs:
        v[G.cl] = 6
    face = G.bm.faces.new(vs)
    c = sum(pts, Vector()) / len(pts)
    if face.normal.dot(-c) < 0:
        face.normal_flip()


def glass_grid(c00, c10, c11, c01, nu=6, nv=4):
    """Subdivided so the crack shader / vertex-encoded coordinates are accurate."""
    c00, c10, c11, c01 = map(Vector, (c00, c10, c11, c01))
    for i in range(nu):
        for j in range(nv):
            def P(a, b):
                return (c00 * (1 - a) + c10 * a) * (1 - b) + (c01 * (1 - a) + c11 * a) * b
            glass_quad([P(i / nu, j / nv), P((i + 1) / nu, j / nv), P((i + 1) / nu, (j + 1) / nv), P(i / nu, (j + 1) / nv)])


inL = Vector((0.0, -0.085, 0.0))
glass_grid(sillL + inL * -1 + Vector((0.02, 0, 0.06)) - Vector((0, 0, 0)), sillR + Vector((0.02, 0.085, 0.06)), hdrR + Vector((0.02, 0.085, -0.17)), hdrL + Vector((0.02, -0.085, -0.17)), 8, 5)
# side windows: from the pillar outwards to the side posts
for sd in (1, -1):
    top_in = PIL[sd][0] + Vector((0.0, sd * 0.11, -0.07))
    bot_in = PIL[sd][1] + Vector((0.0, sd * 0.11, 0.07))
    top_out = Vector((0.12, sd * 1.32, 0.55))
    bot_out = Vector((0.55, sd * 1.5, -0.28))
    if sd == 1:
        glass_grid(bot_in, bot_out, top_out, top_in, 4, 4)
    else:
        glass_grid(bot_out, bot_in, top_in, top_out, 4, 4)
    beam(S, top_out, bot_out, 0.14, 0.3, (-1, 0, 0), cls=0, bevel=0.01)
    beam(S, top_in, top_out, 0.07, 0.2, (0, 0, 1), cls=1, bevel=0.006)
    beam(S, bot_in, bot_out, 0.09, 0.2, (0, 0, 1), cls=0, bevel=0.006)

# ---------------------------------------------------------------------------------------------- the overhead gantry (top 10 % of the picture)
ceil_z = 0.8
S.box((0.35, 0.0, ceil_z + 0.1), (1.7, 3.4, 0.2), cls=0, bevel=0.01)             # ceiling slab
S.cyl((-0.2, 0, ceil_z + 0.08), (-0.2, 0, ceil_z + 0.2), 1.9, cls=0, seg=48)
for sd in (1, -1):
    # large housings above each pillar top, with fins and a lamp
    c = Vector((0.68, sd * 0.78, ceil_z - 0.05))
    S.box(c, (0.46, 0.42, 0.22), cls=0, bevel=0.015)
    S.box(c + Vector((-0.05, 0, -0.12)), (0.34, 0.32, 0.05), cls=1, bevel=0.008)
    for k in range(5):
        S.box(c + Vector((0.2, -0.15 + 0.075 * k, 0.0)), (0.06, 0.03, 0.2), cls=1)
    S.cyl(c + Vector((-0.22, 0, 0.0)), c + Vector((-0.22, 0, -0.13)), 0.07, cls=10, seg=14)
    S.box(c + Vector((-0.24, sd * 0.12, -0.1)), (0.02, 0.05, 0.02), cls=5)
    # a spherical-joint hub and big hydraulic cylinders running to the pillar top
    hubp = Vector((0.62, sd * 0.42, ceil_z - 0.12))
    S.sphere(hubp, 0.1, cls=1, seg=14)
    S.cyl(hubp, PIL[sd][0] + Vector((-0.02, sd * 0.1, 0.1)), 0.05, cls=10, seg=12)
    S.cyl(hubp + Vector((0, 0, 0.0)), Vector((0.2, sd * 0.9, ceil_z - 0.03)), 0.075, cls=0, seg=14)
# ceiling clutter: junction boxes, clamps, relays and U-shaped cable loops (the busy roof of the concept)
rc = random.Random(31)
for k in range(46):
    cx = rc.uniform(0.15, 1.0)
    cy = rc.uniform(-1.45, 1.45)
    if abs(cy) < 0.5 and cx > 0.3 and rc.random() < 0.6:
        continue
    sz = (rc.uniform(0.05, 0.2), rc.uniform(0.05, 0.22), rc.uniform(0.03, 0.12))
    S.box(Vector((cx, cy, ceil_z - 0.02 - sz[2] / 2)), sz, cls=rc.choice((0, 0, 1)), bevel=0.008)
    if rc.random() < 0.35:
        S.box(Vector((cx + sz[0] / 2, cy, ceil_z - 0.04 - sz[2] * 0.5)), (0.012, 0.03, 0.012), cls=5 if rc.random() < 0.7 else 9)
    if rc.random() < 0.3:
        S.cyl(Vector((cx, cy, ceil_z)), Vector((cx, cy, ceil_z - 0.1 - sz[2])), 0.02, cls=10, seg=8)
for sd in (1, -1):
    for k in range(7):
        x0 = 0.25 + 0.1 * k
        y0 = sd * (0.45 + 0.17 * k)
        pts = [Vector((x0, y0, ceil_z - 0.03)), Vector((x0 + 0.02, y0 + sd * 0.03, ceil_z - 0.2 - 0.03 * (k % 3))), Vector((x0 + 0.03, y0 + sd * 0.12, ceil_z - 0.26 - 0.04 * (k % 2))), Vector((x0 + 0.02, y0 + sd * 0.22, ceil_z - 0.18)), Vector((x0, y0 + sd * 0.26, ceil_z - 0.03))]
        S.pipe(pts, rc.choice((0.012, 0.016, 0.02)), cls=3, collars=False)
# centre overhead strip with switches (reachable by looking up)
oc = Vector((0.5, 0, ceil_z - 0.14))
of = Frame(oc, (0, -1, 0), Vector((-0.15, 0, -1)))
of.box(S, 0, 0, -0.03, 0.9, 0.34, 0.05, cls=0, bevel=0.01)
r4 = random.Random(77)
button_grid(S, of, -0.36, 0.05, 8, 3, 0.05, r4, palette=(0, 0, 0, 5, 9, 0))
for i in range(2):
    toggle_bank(S, of, -0.22 + i * 0.44, -0.11, 4, r4, pitch=0.04)
of.box(S, 0.0, 0.1, 0.0, 0.5, 0.075, 0.016, cls=0, bevel=0.004)
of.box(S, 0.0, 0.1, 0.016, 0.46, 0.065, 0.004, cls=6)
add_monitor("overhead", of, 0.0, 0.1, 0.46, 0.065, t=0.021, label="overhead")
# rear hydraulic hub
hub = Vector((-0.55, 0, ceil_z))
S.cyl(hub - Vector((0, 0, 0.25)), hub + Vector((0, 0, 0.12)), 0.26, cls=0, seg=30)
for k in range(6):
    aa = 2 * math.pi * k / 6
    S.cyl(hub + Vector((0.26 * math.cos(aa), 0.26 * math.sin(aa), -0.1)), hub + Vector((0.26 * math.cos(aa), 0.26 * math.sin(aa), 0.1)), 0.028, cls=10, seg=8)

# ---------------------------------------------------------------------------------------------- the dash: a steep raked face (like the concept) with the radar cluster
DASH_P = Vector((1.28, 0.0, -0.46))                 # top edge
DASH_N = Vector((-0.74, 0.0, 0.67)).normalized()    # faces the pilot, leaning up
DASH_T = Vector((DASH_N.z, 0.0, -DASH_N.x)).normalized()   # up the slope


def on_dash(px, py, extra=0.0):
    """Point of the dash plane under screen pixel (px, py) + its facing frame."""
    r0 = scr(px, py, 1.0)
    t = (DASH_P - Vector((0, 0, 0))).dot(DASH_N) / r0.dot(DASH_N)
    return r0 * t


dash_o = on_dash(836, 835)
df = Frame(dash_o, (0, -1, 0), DASH_N)
df.box(S, 0, -0.16, -0.42, 1.7, 0.62, 0.4, cls=0, bevel=0.015)                      # the dash body
df.box(S, 0, 0.15, 0.0, 1.62, 0.04, 0.03, cls=1, bevel=0.004)                      # top lip
S.box((1.18, 0, -1.2), (0.5, 1.7, 0.9), cls=0, bevel=0.01)                         # below the dash down to the floor
cfg = [("radar_C", 836, 835, 0.42, 0.28, 0.0), ("aux_L", 640, 835, 0.18, 0.135, -10.0), ("aux_R", 1032, 835, 0.18, 0.135, 10.0),
       ("side_c1", 545, 862, 0.12, 0.09, -18.0), ("side_c2", 1127, 862, 0.12, 0.09, 18.0)]
for mid, px, py, w, h, yaw in cfg:
    o = on_dash(px, py)
    f = Frame(o, (0, -1, 0), (Matrix.Rotation(math.radians(yaw), 3, "Z") @ DASH_N))
    f.box(S, 0, 0, -0.05, w + 0.09, h + 0.09, 0.05, cls=1, bevel=0.006)
    screen(f, w, h, mid, lamp=5 if mid != "radar_C" else 4)
    r5 = random.Random(len(mid) * 13 + px)
    for i in range(int(w / 0.04)):
        if r5.random() < 0.7:
            button(S, f, -w / 2 + 0.02 + i * 0.04, -h / 2 - 0.075, 0.016, cls=r5.choice((0, 0, 0, 5, 9, 7)), h=0.01)
    if w > 0.3:
        for sx in (-1, 1):
            knob(S, f, sx * (w / 2 + 0.07), -0.04, 0.018, r5)
            dial(S, f, sx * (w / 2 + 0.07), 0.07, 0.032, r5)
        led_bar(S, f, -0.12, h / 2 + 0.07, 12, r5, pitch=0.02, cls_on=5)
for sd in (1, -1):
    for k in range(3):
        fk = Frame(on_dash(836 - sd * (360 + 60 * k), 860), (0, -1, 0), DASH_N)
        round_button(S, fk, 0, 0, 0.02, cls=7 if k == 1 else 5)
    ft = Frame(on_dash(836 - sd * 255, 880), (0, -1, 0), DASH_N)
    toggle_bank(S, ft, 0, 0, 4, random.Random(5 + sd), pitch=0.045)

# ---------------------------------------------------------------------------------------------- side consoles: big tilted screens, lower rows (left = map, right = own mech)
for sd in (1, -1):
    mid = "main_R" if sd == 1 else "main_L"
    f = facing(scr(836 - sd * 700, 560, 0.95), yaw=-sd * 30.0, pitch=0)
    housing(f, 0.30, 0.225, 0.2)
    screen(f, 0.30, 0.225, mid, lamp=5)
    r6 = random.Random(40 + sd)
    button_grid(S, f, -0.12, -0.2, 6, 2, 0.045, r6, palette=(0, 0, 0, 5, 9))
    led_bar(S, f, -0.12, 0.17, 12, r6, pitch=0.02, cls_on=4 if sd == 1 else 11)
    f2 = facing(scr(836 - sd * 745, 745, 0.9), yaw=-sd * 38.0)
    housing(f2, 0.16, 0.12, 0.15)
    screen(f2, 0.16, 0.12, "side_%d" % (sd + 2), lamp=7)
    button_grid(S, f2, -0.07, -0.14, 4, 2, 0.04, r6, palette=(0, 5, 0, 9))
    # column of switch panels below and a console base
    S.box(scr(836 - sd * 780, 880, 0.9), (0.4, 0.3, 0.5), cls=0, bevel=0.01)
    fp = facing(scr(836 - sd * 760, 820, 0.8), yaw=-sd * 40.0)
    toggle_bank(S, fp, 0, 0, 4, r6, pitch=0.042)
    guarded_switch(S, fp, 0.1, -0.07, r6)

# ---------------------------------------------------------------------------------------------- side walls and the rear (modules, vents, racks)
def wall_pt(a, z, off=0.0):
    rad = rho(a, 0.0) - off
    return Vector((CEN.x + rad * math.cos(a), rad * math.sin(a), z))


WALL_A0, WALL_A1 = 72.0, 288.0
NW = 18
console_frames = {}
for k in range(NW):
    a0 = math.radians(WALL_A0 + (WALL_A1 - WALL_A0) * k / NW)
    a1 = math.radians(WALL_A0 + (WALL_A1 - WALL_A0) * (k + 1) / NW)
    am = (a0 + a1) / 2
    p = wall_pt(am, 0.0, 0.0)
    d = Vector((math.cos(am), math.sin(am), 0))
    tng = Vector((-math.sin(am), math.cos(am), 0))
    f = Frame(Vector((p.x, p.y, 0)), -tng, -d)
    console_frames[k] = f
    w = (rho(am, 0.0)) * (a1 - a0) + 0.01
    r3 = random.Random(300 + k)
    f.box(S, 0, 0.0, -0.1, w, 2.6, 0.1, cls=0)
    f.box(S, 0, 0.0, 0.0, w - 0.03, 2.56, 0.012, cls=1 if k % 2 else 0)
    f.box(S, w / 2, 0.0, 0.0, 0.07, 2.6, 0.1, cls=0, bevel=0.01)
    vs = 1.0 if f.uy.z >= 0 else -1.0
    for mi, (zz, hh) in enumerate(((-1.15, 0.85), (-0.35, 0.8), (0.28, 0.45))):
        vv = vs * zz
        typ = r3.choice(("rack", "switches", "vent", "monitor", "greeble", "pipes", "panel"))
        plate_with_bolts(S, f, 0, vv, w - 0.08, hh - 0.08, cls=r3.choice((0, 1, 1)), th=0.02, rr=r3)
        if typ == "rack" and hh > 0.6:
            for i in range(3):
                f.box(S, 0, vv + vs * (-0.24 + i * 0.22), 0.02, w - 0.14, 0.15, 0.03, cls=0, bevel=0.004)
                led_bar(S, f, -0.1, vv + vs * (-0.24 + i * 0.22), 8, r3, pitch=0.02, cls_on=r3.choice((11, 5, 9)))
        elif typ == "switches" and hh > 0.6:
            button_grid(S, f, -0.12, vv - 0.2 * vs, 5, 5, 0.05, r3, palette=(0, 0, 5, 9))
        elif typ == "vent":
            vent(S, f, 0, vv, w - 0.18, hh - 0.2, 9)
        elif typ == "monitor" and hh > 0.6 and 112 < math.degrees(am) < 248:
            f.box(S, 0, vv, 0.02, w - 0.14, hh * 0.5, 0.02, cls=0, bevel=0.004)
            f.box(S, 0, vv, 0.04, w - 0.18, hh * 0.45, 0.004, cls=6)
            add_monitor("wall_%d_%d" % (k, mi), f, 0, vv, w - 0.18, hh * 0.45, t=0.045, label="wall")
        elif typ == "greeble":
            greeble_patch(S, f, 0, vv, w - 0.12, hh - 0.14, 22, r3, palette=(0, 1, 0, 0, 8))
        else:
            for i in range(3):
                f.cyl(S, -0.1 + 0.1 * i, vv, 0.02, 0.02, 0.0, cls=0)
            hazard_strip(S, f, 0, vv + 0.18 * vs, w - 0.14, 0.04, t=0.02)

# hatch in the rear wall
ha = math.radians(180.0)
hp = wall_pt(ha, -0.6, 0.05)
S.cyl(hp, hp + Vector((0.05, 0, 0)), 0.62, cls=0, seg=36)
S.cyl(hp + Vector((0.04, 0, 0)), hp + Vector((0.09, 0, 0)), 0.55, cls=1, seg=36)
for k in range(20):
    aa = 2 * math.pi * k / 20
    S.cyl(hp + Vector((0.09, 0.5 * math.cos(aa), 0.5 * math.sin(aa))), hp + Vector((0.115, 0.5 * math.cos(aa), 0.5 * math.sin(aa))), 0.016, cls=10, seg=6)
for k in range(24):
    aa = 2 * math.pi * k / 24
    S.box((hp.x + 0.1, hp.y + 0.45 * math.cos(aa), hp.z + 0.45 * math.sin(aa)), (0.012, 0.09, 0.03), rot=(aa, 0, 0), cls=8 if k % 2 else 0)
S.cyl(hp + Vector((0.1, 0, 0)), hp + Vector((0.2, 0, 0)), 0.05, cls=10, seg=12)
for k in range(3):
    aa = 2 * math.pi * k / 3 + 0.4
    S.cyl(hp + Vector((0.2, 0, 0)), hp + Vector((0.2, 0.26 * math.cos(aa), 0.26 * math.sin(aa))), 0.015, cls=10, seg=8)
S.box((hp.x + 0.1, hp.y + 0.62, hp.z + 0.1), (0.04, 0.08, 0.2), cls=7)
add_lamp("hatch_strobe", (hp.x + 0.25, hp.y, hp.z + 0.7), [1.0, 0.1, 0.05], 3.0, 1.3, "strobe")

# ---------------------------------------------------------------------------------------------- back column and waist ring
col = Vector((-0.62, 0, 0))
S.cyl((col.x, 0, FLOOR - 0.1), (col.x, 0, ceil_z), 0.13, cls=1, seg=24)
for z in np.linspace(FLOOR + 0.2, 0.5, 7):
    S.cyl((col.x, 0, z - 0.03), (col.x, 0, z + 0.03), 0.16, cls=0, seg=24)
for sy in (-1, 1):
    S.cyl((col.x + 0.06, sy * 0.1, FLOOR + 0.1), (col.x + 0.06, sy * 0.1, 0.4), 0.03, cls=10, seg=10)
WR = 0.43
ring(S, (0, 0), WR, -0.80, 0.032, n=48, cls=1)
ring(S, (0, 0), WR + 0.04, -0.80, 0.018, n=48, cls=0)
for a_deg in (60, 180, 300):
    aa = math.radians(a_deg)
    S.box((WR * math.cos(aa), WR * math.sin(aa), -0.80), (0.12, 0.09, 0.1), rot=(0, 0, aa), cls=1, bevel=0.01)
for sy in (-1, 1):
    beam(S, (col.x + 0.1, sy * 0.1, -0.8), (-WR * 0.92, sy * 0.22, -0.8), 0.07, 0.05, (0, 0, 1), cls=1, bevel=0.005)

# ---------------------------------------------------------------------------------------------- arm mounts (the animated exo-arms come out of these)
for sd in (1, -1):
    mnt = Vector((-0.2, sd * 0.5, -0.24))
    S.box(mnt + Vector((-0.1, sd * 0.1, -0.1)), (0.5, 0.34, 0.5), cls=0, bevel=0.02)
    S.sphere(mnt, 0.13, cls=1, seg=16)
    S.cyl(mnt + Vector((0, sd * 0.05, 0.05)), mnt + Vector((-0.35, sd * 0.2, 0.35)), 0.05, cls=10, seg=12)
    S.cyl(mnt + Vector((0, 0, 0)), mnt + Vector((-0.1, sd * 0.4, -0.5)), 0.06, cls=0, seg=12)
    for k in range(4):
        S.box(mnt + Vector((-0.1 + 0.07 * k, sd * 0.12, 0.17)), (0.04, 0.08, 0.02), cls=5 if k == 1 else 0)

# ---------------------------------------------------------------------------------------------- big hydraulic control arms in the lower corners (from the concept)
for sd in (1, -1):
    base = Vector((0.15, sd * 0.78, -0.72))
    knee = Vector((0.62, sd * 0.66, -0.50))
    tip = Vector((0.98, sd * 0.52, -0.40))
    S.sphere(base, 0.19, cls=0, seg=18)
    S.cyl(base, knee, 0.15, 0.13, cls=0, seg=18)
    S.sphere(knee, 0.15, cls=0, seg=18)
    S.cyl(knee, tip, 0.12, 0.10, cls=0, seg=18)
    S.sphere(tip, 0.11, cls=0, seg=16)
    # ribbed collars, piston rods and a cable harness running along the arm
    for q in (0.25, 0.5, 0.75):
        c = base + (knee - base) * q
        S.cyl(c - Vector((0.02, 0, 0)), c + Vector((0.02, 0, 0)), 0.17, cls=0, seg=18)
        c2 = knee + (tip - knee) * q
        S.cyl(c2 - Vector((0.02, 0, 0)), c2 + Vector((0.02, 0, 0)), 0.135, cls=0, seg=18)
    S.cyl(base + Vector((0.0, -sd * 0.16, 0.12)), knee + Vector((0.0, -sd * 0.14, 0.1)), 0.04, cls=10, seg=10)
    S.cyl(knee + Vector((0.0, -sd * 0.14, 0.1)), tip + Vector((0.0, -sd * 0.1, 0.1)), 0.032, cls=10, seg=10)
    for k in range(3):
        S.pipe([base + Vector((0.02 * k, sd * 0.13, 0.1)), (base + knee) / 2 + Vector((0.0, sd * 0.15, 0.17 + 0.02 * k)), knee + Vector((0.02, sd * 0.1, 0.15))], 0.012, cls=3, collars=False)
    # armour plates and amber caps
    for q, w_ in ((0.35, 0.2), (0.7, 0.16)):
        c = base + (knee - base) * q + Vector((0, 0, 0.13))
        S.box(c, (0.2, w_, 0.04), cls=0, bevel=0.008)
    S.cyl(tip + Vector((0.08, 0, 0.0)), tip + Vector((0.13, 0, 0.0)), 0.075, cls=5, seg=14)
    S.cyl(base + Vector((0.0, sd * 0.1, 0.17)), base + Vector((0.0, sd * 0.1, 0.2)), 0.04, cls=5, seg=10)

# ---------------------------------------------------------------------------------------------- pipes (dynamic tubes that can burst and vent steam)
rp = random.Random(5)
for sd in (1, -1):
    # from the ceiling hubs down along the outside of the pillars and into the desk sides
    for rep in range(3):
        top = PIL[sd][0] + Vector((-0.06 - 0.04 * rep, sd * (0.2 + 0.07 * rep), 0.14))
        bot = PIL[sd][1] + Vector((-0.1, sd * (0.22 + 0.06 * rep), 0.0))
        mid1 = top + (bot - top) * 0.35 + Vector((0.0, sd * 0.05, 0.0))
        mid2 = top + (bot - top) * 0.72 + Vector((-0.02, sd * 0.04, 0.0))
        add_pipe([top + Vector((0.1, -sd * 0.15, 0.2)), top, mid1, mid2, bot, bot + Vector((0.05, 0, -0.3))], (0.03, 0.022, 0.016)[rep], cls=(0, 1, 0)[rep], steam=0.6 if rep == 0 else 0.0)
    # from the side posts along the ceiling
    for rep in range(3):
        p0 = Vector((0.1, sd * (1.3 + 0.05 * rep), -0.6))
        p1 = Vector((0.0, sd * (1.5 + 0.03 * rep), -0.1 + 0.08 * rep))
        p2 = Vector((0.15, sd * (1.35 + 0.04 * rep), 0.38 + 0.04 * rep))
        p3 = Vector((0.45, sd * (0.9 + 0.1 * rep), ceil_z - 0.08))
        p4 = Vector((0.7, sd * (0.5 + 0.1 * rep), ceil_z - 0.12))
        add_pipe([p0, p1, p2, p3, p4], 0.026 + 0.008 * (rep % 2), cls=(0, 1, 0)[rep], steam=0.5 if rep == 1 else 0.0)
# wall runs
for k, a_deg in enumerate(range(112, 250, 12)):
    a = math.radians(a_deg)
    off = 0.1 + rp.uniform(0, 0.08)
    add_pipe([wall_pt(a, FLOOR + 0.12, off), wall_pt(a + rp.uniform(-0.08, 0.08), -0.5, off + 0.04), wall_pt(a + rp.uniform(-0.1, 0.1), 0.2, off + 0.06), wall_pt(a, ceil_z - 0.05, off)],
             rp.choice((0.018, 0.024, 0.03)), cls=rp.choice((0, 1)), steam=rp.choice((0, 0, 0.4)))
# ceiling collectors
for k in range(6):
    a = 2 * math.pi * k / 6 + 0.2
    pts = [Vector((-0.2 + 0.25 * math.cos(a), 0.25 * math.sin(a), ceil_z - 0.02)), Vector((-0.2 + 0.8 * math.cos(a + 0.2), 0.8 * math.sin(a + 0.2), ceil_z - 0.04)), Vector((-0.2 + 1.3 * math.cos(a + 0.1), 1.3 * math.sin(a + 0.1), ceil_z - 0.1))]
    add_pipe(pts, 0.026 if k % 2 else 0.036, cls=k % 2, steam=rp.choice((0, 0.5)))
for p in LAY["pipes"]:
    if p["steam"] > 0:
        pts = p["pts"]
        add_socket("steam", pts[len(pts) // 2], (0, 0, 1), p["id"])

# ---------------------------------------------------------------------------------------------- hanging cables (from the overhead; they sway and snap)
rw = random.Random(9)
cols = ["black", "black", "black", "grey", "black", "black"]
slots = [(0.45, -0.95), (0.55, -0.55), (0.5, -0.2), (0.45, 0.2), (0.6, 0.55), (0.5, 0.95), (0.8, -0.7), (0.78, 0.7), (0.3, -1.25), (0.3, 1.25), (0.9, 0.0), (0.65, -0.35), (0.7, 0.35)]
for k, (ax_, ay_) in enumerate(slots):
    add_wire((ax_, ay_, ceil_z - 0.08), (rw.uniform(-0.15, 0.15), rw.uniform(-0.1, 0.1), -1.0), rw.uniform(0.28, 0.6), rw.choice((0.011, 0.014, 0.018)), rw.choice(cols), "hang")
    S.cyl(Vector((ax_, ay_, ceil_z - 0.02)), Vector((ax_, ay_, ceil_z - 0.1)), 0.03, cls=10, seg=8)

# ---------------------------------------------------------------------------------------------- lamps (low-key: mostly dark, small accents)
add_lamp("dash_cyan", (0.45, 0.0, -0.1), [0.2, 0.7, 1.0], 1.6, 1.8)
add_lamp("left_amber", (0.55, 0.9, -0.35), [1.0, 0.5, 0.14], 1.0, 1.6)
add_lamp("right_amber", (0.55, -0.9, -0.35), [1.0, 0.5, 0.14], 1.0, 1.6)
add_lamp("ceiling_cool", (0.2, 0.0, 0.45), [0.6, 0.75, 1.0], 1.0, 2.4)
add_lamp("alarm_front_l", (0.8, 0.8, 0.5), [1.0, 0.04, 0.02], 3.0, 2.4, "beacon")
add_lamp("alarm_front_r", (0.8, -0.8, 0.5), [1.0, 0.04, 0.02], 3.0, 2.4, "beacon")
add_lamp("alarm_rear", (-1.2, 0.0, 0.5), [1.0, 0.04, 0.02], 2.5, 2.4, "beacon")
for sy in (-1, 1):
    S.cyl((0.8, sy * 0.8, ceil_z + 0.02), (0.8, sy * 0.8, ceil_z - 0.08), 0.06, cls=0, seg=14)
    S.cyl((0.8, sy * 0.8, ceil_z - 0.08), (0.8, sy * 0.8, ceil_z - 0.15), 0.045, cls=7, seg=14)
S.cyl((-1.2, 0, ceil_z + 0.02), (-1.2, 0, ceil_z - 0.08), 0.06, cls=0, seg=14)
S.cyl((-1.2, 0, ceil_z - 0.08), (-1.2, 0, ceil_z - 0.15), 0.045, cls=7, seg=14)
for sgn in (-1, 1):
    add_socket("fire", (0.9, sgn * 0.8, -0.38), (0, 0, 1), "fire_front_%d" % sgn)
    add_socket("fire", (-0.3, sgn * 1.45, -0.9), (0, 0, 1), "fire_side_%d" % sgn)
    add_socket("fire", (0.3, sgn * 0.8, 0.5), (0, 0, -1), "fire_ceiling_%d" % sgn)
for k in range(10):
    add_socket("spark", (rw.uniform(0.2, 1.0), rw.uniform(-1.1, 1.1), ceil_z - 0.1), (0, 0, -1), "ceiling_spark_%d" % k)
for k in range(8):
    add_socket("spark", (rw.uniform(0.9, 1.2), rw.uniform(-0.8, 0.8), -0.45), (0, 0, 1), "console_%d" % k)

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
    sc.render.engine = "CYCLES"; sc.cycles.samples = 10; sc.cycles.use_denoising = False; sc.cycles.device = "CPU"
    sc.render.resolution_x, sc.render.resolution_y = 1672, 941
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
    for nm, src, loc, rot in (() if "--norig" in argv else (("UpL", up, (0.25, 0.30, -0.45), (0, math.radians(15), math.radians(-14))), ("FoL", fo, (0.78, 0.22, -0.40), (0, math.radians(8), math.radians(-8))), ("GlL", gl, (1.30, 0.12, -0.36), (0, 0, 0)))):
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
        if SHOTS is not None and name.replace('prev_', '') not in SHOTS:
            return
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
    if SHOTS is None or "outer" in SHOTS:
        sc.render.filepath = os.path.join(OUT, "prev_outer.png"); bpy.ops.render.render(write_still=True)
    # debug: top-down (ceiling clipped away) and side orthographic
    cd.type = "ORTHO"; cd.ortho_scale = 5.0; cd.clip_start = 0.01
    cam.location = (0, 0, 3.0); cam.rotation_euler = (0, 0, math.radians(-90)); cd.clip_start = 1.85
    if SHOTS is None or "top" in SHOTS:
        sc.render.filepath = os.path.join(OUT, "prev_top.png"); bpy.ops.render.render(write_still=True)
    cd.clip_start = 0.01
    cam.location = (0, 4.0, -0.2); cam.rotation_euler = (math.radians(90), 0, math.radians(180))
    if SHOTS is None or "side" in SHOTS:
        sc.render.filepath = os.path.join(OUT, "prev_side.png"); bpy.ops.render.render(write_still=True)
    print("PREVIEW DONE")
