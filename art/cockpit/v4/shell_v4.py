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
add_lamp("dash_cyan", (0.85, 0.0, -0.45), [0.2, 0.7, 1.0], 1.6, 1.8)
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
