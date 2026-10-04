"""Generates the "Takeshita" arena district: district.json (schema v1 + `signs`, `lights`, `arena`) and a flat heightmap.

Layout (district metres: x right, y north; Unreal X = y*100, Y = x*100):
  * a wide plaza (the duel ground) with a scramble crossing at its south end,
  * Takeshita-dori: a narrow pedestrian street running north from the plaza, lined with low shopfronts and blade signs,
    a neon gate at its mouth,
  * glass towers (some with setbacks and crowns) and building-sized signs around the plaza,
  * dense blocks further out that fade into the fog.
Run: python make_arena.py [out_dir]   (default: Content/Data of the Unreal project)
"""
import json, math, os, random, struct, sys

OUT = sys.argv[1] if len(sys.argv) > 1 else r"F:\IVUnreal\Content\Data"
R = random.Random(20261004)

RES = 1009
X0, X1, Y0, Y1 = -800.0, 800.0, -400.0, 1200.0
PLAZA = (-120.0, 120.0, 215.0, 575.0)      # x0 x1 y0 y1 : kept free of buildings
STREET_X = 9.0                              # half width of Takeshita-dori
STREET_Y0, STREET_Y1 = 575.0, 1000.0
CROSS_Y = (150.0, 215.0)                   # scramble avenue (east-west)
PLAZA_C = (0.0, 395.0)

buildings, signs, lights, props, roads = [], [], [], [], []
_bid = [0]


def rect_footprint(cx, cy, w, d, yaw=0.0):
    c, s = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    pts = []
    for dx, dy in ((-w / 2, -d / 2), (w / 2, -d / 2), (w / 2, d / 2), (-w / 2, d / 2)):
        pts.append([round(cx + dx * c - dy * s, 2), round(cy + dx * s + dy * c, 2)])
    return pts


def add_building(cx, cy, w, d, h, style, yaw=0.0, tint=None, crown=None, kind="office", **extra):
    _bid[0] += 1
    b = {
        "id": "bld_%03d" % _bid[0], "type": "generic", "block_id": "blk", "district": "downtown", "building_type": kind,
        "facade_style": "glass_curtain" if style == "glass_tower" else ("shop" if style == "shop" else "concrete"),
        "footprint": rect_footprint(cx, cy, w, d, yaw), "height": round(h, 1), "floors": max(1, int(h / 4)), "base_z": 0.0,
        "yaw_deg": yaw, "style": style,
    }
    if tint is not None:
        b["tint"] = tint
    if crown:
        b["crown"] = crown
    b.update(extra)
    buildings.append(b)
    return b


def overlaps_free(cx, cy, w, d, margin=0.0):
    """True if the box touches a keep-free zone (plaza, street corridor, crossing)."""
    def hit(x0, x1, y0, y1):
        return not (cx + w / 2 < x0 - margin or cx - w / 2 > x1 + margin or cy + d / 2 < y0 - margin or cy - d / 2 > y1 + margin)
    if hit(*PLAZA):
        return True
    if hit(-STREET_X - 0.5, STREET_X + 0.5, STREET_Y0 - 5, STREET_Y1):
        return True
    if hit(X0, X1, CROSS_Y[0], CROSS_Y[1]):
        return True
    return False


NEON_PAL = [
    (1.0, 0.08, 0.55), (0.05, 0.85, 1.0), (1.0, 0.45, 0.05), (0.55, 0.15, 1.0), (0.1, 1.0, 0.45), (1.0, 0.1, 0.12), (1.0, 0.85, 0.2), (0.2, 0.45, 1.0),
]
GLASS_TINTS = [
    (0.10, 0.25, 0.36), (0.07, 0.20, 0.30), (0.20, 0.12, 0.34), (0.09, 0.30, 0.30), (0.24, 0.20, 0.10), (0.12, 0.14, 0.26), (0.06, 0.12, 0.2),
]


def pal(i=None):
    return NEON_PAL[R.randrange(len(NEON_PAL))] if i is None else NEON_PAL[i % len(NEON_PAL)]


def add_sign(pos, yaw, w, h, style, color, color2=None, anim=0, light=True, seed=None, depth=0.6):
    """pos = centre in metres (x, y, z); yaw_deg = direction of the sign face normal (district frame, 0 = +x, 90 = +y)."""
    s = {"pos": [round(pos[0], 2), round(pos[1], 2), round(pos[2], 2)], "yaw_deg": round(yaw, 1), "size": [round(w, 1), round(h, 1)],
         "style": style, "color": [round(c, 3) for c in color], "color2": [round(c, 3) for c in (color2 or pal())],
         "anim": anim, "seed": seed if seed is not None else R.randrange(10000), "depth": depth}
    signs.append(s)
    if light:
        nx, ny = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
        dist = max(6.0, min(w, h) * 0.45)
        lights.append({"pos": [round(pos[0] + nx * dist, 2), round(pos[1] + ny * dist, 2), round(pos[2], 2)], "color": s["color"],
                       "intensity": round(min(60.0, 4.0 + w * h / 40.0), 1), "radius": round(max(14.0, min(70.0, math.sqrt(w * h) * 1.5)), 1),
                       "flicker": 1 if anim == 1 else 0, "prio": round(w * h, 1)})
    return s


# ------------------------------------------------------------------ roads
def road(kind, width, pts, name):
    roads.append({"id": name, "kind": kind, "name": name, "width": width, "points": [[round(p[0], 1), round(p[1], 1)] for p in pts], "dead_end": False})


road("avenue", 52, [(X0, 182), (X1, 182)], "scramble_avenue")
road("promenade", 2 * STREET_X, [(0, STREET_Y0 - 30), (0, STREET_Y1)], "takeshita_dori")
road("street", 40, [(X0, 395), (-120, 395)], "west_street")
road("street", 40, [(120, 395), (X1, 395)], "east_street")
road("avenue", 60, [(-150, Y0), (-150, 1150)], "west_avenue")
road("avenue", 60, [(150, Y0), (150, 1150)], "east_avenue")
road("street", 30, [(-400, Y0), (-400, 1150)], "far_west_street")
road("street", 30, [(400, Y0), (400, 1150)], "far_east_street")
road("street", 30, [(X0, 700), (X1, 700)], "north_street")
road("street", 30, [(X0, 880), (X1, 880)], "north_street_2")
road("street", 30, [(X0, 40), (X1, 40)], "south_street")

# ------------------------------------------------------------------ towers around the plaza (the skyline the player looks at)
def crown_for(h, w):
    if h > 220:
        return R.choice(["spire", "spire", "stepped", "halo", "antenna_cluster"])
    if h > 140:
        return R.choice(["stepped", "slanted", "halo", "flat", "antenna_cluster"])
    return R.choice(["flat", "flat", "stepped", "antenna_cluster"])


def tower(cx, cy, w, d, h, face_yaw, glass=True):
    t = R.choice(GLASS_TINTS)
    cr = crown_for(h, w) if glass else R.choice(["flat", "antenna_cluster"])
    b = add_building(cx, cy, w, d, h, "glass_tower" if glass else "concrete", yaw=0.0, tint=list(t), crown=cr, kind="office",
                     setback=R.choice([0, 0, 1, 2]))
    return b


# ring of towers east/west of the plaza and behind the player (south) and behind the street
def place_tower_belt():
    # west and east walls of the plaza: continuous belt of big towers facing inward
    for side in (-1, 1):
        y = PLAZA[2] + 5
        while y < PLAZA[3] + 15:
            d = R.uniform(46, 78)
            w = R.uniform(48, 80)
            h = R.uniform(150, 330)
            cx = side * (PLAZA[1] + 14 + w / 2 + R.uniform(0, 6))
            cy = y + d / 2
            if not overlaps_free(cx, cy, w, d):
                b = tower(cx, cy, w, d, h, 180 if side > 0 else 0)
                # HUGE signs on the inner face: building-sized billboards and towering vertical banners, several per tower
                face = 180.0 if side > 0 else 0.0
                fx = cx - side * (w / 2 + 0.3)
                kinds = R.choice([("billboard", 0), ("banner", 1), ("billboard", 0)])
                z_prev = 0
                for k in range(R.choice([1, 2, 2, 3])):
                    if k == 0 and R.random() < 0.55:
                        sw = min(R.uniform(34, 62), d * 0.95)
                        sh = R.uniform(46, min(150, h * 0.7))
                        style = "billboard"
                    else:
                        sw = R.uniform(9, 16)
                        sh = R.uniform(60, min(190, h * 0.85))
                        style = "banner"
                    sz = R.uniform(sh / 2 + 12, max(sh / 2 + 14, h - sh / 2 - 6))
                    off = R.uniform(-d / 3, d / 3)
                    add_sign((fx - side * 0.2 * k, cy + off, sz), face, sw if style != "banner" else min(sw, 14), sh, style, pal(), anim=R.choice([0, 1, 2]), seed=R.randrange(10000))
                if R.random() < 0.7:
                    add_sign((fx, cy + R.uniform(-d / 3, d / 3), R.uniform(14, 40)), face, R.uniform(6, 18), R.uniform(10, 28), "banner", pal(), anim=1)
            y += d + R.uniform(2, 8)
    # south end: wall of towers beyond the scramble avenue, facing north
    x = -330.0
    while x < 330:
        w = R.uniform(52, 90)
        d = R.uniform(50, 80)
        h = R.uniform(170, 360)
        cx, cy = x + w / 2, CROSS_Y[0] - 10 - d / 2 - R.uniform(0, 4)
        if not overlaps_free(cx, cy, w, d) and abs(cx) > 14:
            tower(cx, cy, w, d, h, 90)
            if R.random() < 0.7:
                sw = R.uniform(14, 40)
                sh = R.uniform(40, 120)
                add_sign((cx + R.uniform(-w / 4, w / 4), cy + d / 2 + 0.3, R.uniform(sh / 2 + 15, h - sh / 2)), 90.0, sw if sw > 16 else 11, sh if sw <= 16 else R.uniform(20, 46),
                         "banner" if sw <= 16 else "billboard", pal(), anim=R.choice([0, 1, 2]))
        x += w + R.uniform(3, 10)
    # north: behind the street, towers on both sides of the corridor (the enemy's backdrop)
    for side in (-1, 1):
        y = STREET_Y0 + 40
        while y < 1150:
            d = R.uniform(46, 80)
            w = R.uniform(48, 84)
            h = R.uniform(120, 340)
            cx = side * (STREET_X + 34 + w / 2 + R.uniform(0, 14))
            cy = y + d / 2
            tower(cx, cy, w, d, h, 0 if side < 0 else 180)
            if R.random() < 0.8:
                sw = R.uniform(8, 30)
                sh = R.uniform(30, min(140, h * 0.7))
                add_sign((cx - side * (w / 2 + 0.3), cy, R.uniform(sh / 2 + 12, h - sh / 2)), 0.0 if side > 0 else 180.0, sw, sh, "banner" if sw < 14 else "billboard", pal(), anim=R.choice([0, 1, 2]))
            y += d + R.uniform(3, 10)


place_tower_belt()

# ------------------------------------------------------------------ Takeshita-dori shop rows
def shop_rows():
    for side in (-1, 1):
        y = STREET_Y0 + 4
        k = 0
        while y < STREET_Y1:
            w = R.uniform(8, 15)         # along y
            d = R.uniform(13, 20)        # depth along x
            h = R.choice([9, 12, 14, 17, 20, 24]) + R.uniform(0, 2)
            cx = side * (STREET_X + 0.6 + d / 2)
            cy = y + w / 2
            b = add_building(cx, cy, d, w, h, "shop", kind="commercial", tint=[R.uniform(0.05, 0.14), R.uniform(0.05, 0.12), R.uniform(0.07, 0.16)])
            # blade sign: protrudes into the street, faces along the street (normal +-y)
            if R.random() < 0.85:
                sx = side * (STREET_X - 0.4 - R.uniform(0.2, 1.0))
                sh = R.uniform(5, 11)
                sw = R.uniform(1.6, 2.6)
                add_sign((sx, cy + R.uniform(-w / 3, w / 3), R.uniform(5.5, h - 1.0 if h > 11 else 8)), 90.0 if R.random() < 0.5 else 270.0, sw, sh, "banner", pal(), anim=R.choice([0, 0, 1]),
                         light=(k % 3 == 0), depth=2.5)
            # facade sign (faces the street)
            if R.random() < 0.9:
                fw = min(w * 0.9, R.uniform(5, 12))
                add_sign((side * (STREET_X + 0.55), cy, R.uniform(h * 0.55, h - 1.5)), 180.0 if side > 0 else 0.0, fw, R.uniform(1.8, 3.2), "strip", pal(), anim=R.choice([0, 1, 2]), light=False)
            # shopfront glow at street level
            if k % 2 == 0:
                lights.append({"pos": [round(side * (STREET_X - 2.0), 2), round(cy, 2), 3.2], "color": [round(c, 3) for c in R.choice([(1.0, 0.75, 0.45), (1.0, 0.35, 0.65), (0.4, 0.9, 1.0), (1.0, 0.6, 0.2)])],
                               "intensity": 6.0, "radius": 16.0, "flicker": 0, "prio": 40.0})
            y += w + R.uniform(0.2, 1.5)
            k += 1
        # second row: mid-rise behind the shops
        y = STREET_Y0 + 8
        while y < STREET_Y1 + 40:
            w = R.uniform(18, 30)
            d = R.uniform(22, 34)
            h = R.uniform(34, 90)
            cx = side * (STREET_X + 22 + d / 2)
            cy = y + w / 2
            add_building(cx, cy, d, w, h, "glass_tower" if R.random() < 0.4 else "concrete", tint=list(R.choice(GLASS_TINTS)), crown=R.choice(["flat", "antenna_cluster"]), kind="office")
            y += w + R.uniform(1, 3)


shop_rows()

# gate arch at the mouth of the street: two posts + a lintel built from signs (neon arch), plus a huge sign above it
add_sign((0, STREET_Y0 - 1.0, 17.5), 270.0, 22.0, 3.2, "strip", (1.0, 0.1, 0.5), color2=(0.1, 0.9, 1.0), anim=2, light=True, depth=1.0)
add_sign((0, STREET_Y0 - 1.0, 17.5), 90.0, 22.0, 3.2, "strip", (1.0, 0.1, 0.5), color2=(0.1, 0.9, 1.0), anim=2, light=False, depth=1.0)
for sx in (-9.5, 9.5):
    add_sign((sx, STREET_Y0 - 1.0, 8.0), 270.0, 1.2, 16.0, "tube", (0.1, 0.9, 1.0), anim=0, light=True, depth=1.0)
    add_sign((sx, STREET_Y0 - 1.0, 8.0), 90.0, 1.2, 16.0, "tube", (0.1, 0.9, 1.0), anim=0, light=False, depth=1.0)
signs_gate = True

# ------------------------------------------------------------------ outer city: dense blocks fading into the fog
def outer_city():
    pitch = 84.0
    ix = int((X0) // pitch)
    xs = [X0 + 20 + i * pitch for i in range(int((X1 - X0) // pitch))]
    ys = [Y0 + 30 + j * pitch for j in range(int((Y1 - Y0) // pitch))]
    for cx0 in xs:
        for cy0 in ys:
            for sx in (0, 1):
                for sy in (0, 1):
                    w = R.uniform(24, 36)
                    d = R.uniform(24, 36)
                    cx = cx0 + 4 + sx * 38 + R.uniform(-3, 3)
                    cy = cy0 + 4 + sy * 38 + R.uniform(-3, 3)
                    if overlaps_free(cx, cy, w, d, margin=16.0):
                        continue
                    # skip anything over a road centre line
                    bad = False
                    for rd in roads:
                        p = rd["points"]
                        if abs(p[0][1] - p[1][1]) < 0.1 and abs(cy - p[0][1]) < rd["width"] / 2 + d / 2 + 2: bad = True
                        if abs(p[0][0] - p[1][0]) < 0.1 and abs(cx - p[0][0]) < rd["width"] / 2 + w / 2 + 2: bad = True
                    if bad:
                        continue
                    dist = math.hypot(cx - PLAZA_C[0], cy - PLAZA_C[1])
                    h = R.uniform(35, 120) * (1.0 + min(dist, 600) / 500.0) * (1.8 if R.random() < 0.12 else 1.0)
                    glass = R.random() < 0.45
                    b = add_building(cx, cy, w, d, h, "glass_tower" if glass else "concrete", tint=list(R.choice(GLASS_TINTS)), crown=crown_for(h, w) if glass else "flat")
                    if dist < 520 and R.random() < 0.35 and h > 50:
                        face = R.choice([0.0, 90.0, 180.0, 270.0])
                        nx, ny = math.cos(math.radians(face)), math.sin(math.radians(face))
                        half = (w if abs(nx) > 0.5 else d) / 2
                        sw = R.uniform(6, 14)
                        sh = R.uniform(18, min(70, h * 0.7))
                        add_sign((cx + nx * (half + 0.3), cy + ny * (half + 0.3), R.uniform(sh / 2 + 6, max(sh / 2 + 7, h - sh / 2))), face, sw, sh, "banner", pal(), anim=R.choice([0, 1, 2]), light=(dist < 380 and R.random() < 0.5))


outer_city()

# ------------------------------------------------------------------ props: a lived-in boulevard
def addp(kind, x, y, yaw=0.0, variant=None):
    p = {"id": "%s_%d" % (kind, len(props)), "kind": kind, "pos": [round(x, 2), round(y, 2), 0.0], "yaw_deg": round(yaw, 1)}
    if variant:
        p["variant"] = variant
    props.append(p)


def lamp_line(x0, y0, x1, y1, step):
    n = max(1, int(math.hypot(x1 - x0, y1 - y0) / step))
    for i in range(n + 1):
        t = i / n
        addp("lamp", x0 + (x1 - x0) * t, y0 + (y1 - y0) * t, 0 if x0 < 0 else 180)


CAR_KINDS = ["sedan", "taxi", "sedan", "van", "suv", "bus", "truck", "sedan", "taxi", "suv"]

# street lamps on both pavements of the plaza, bollards along the kerb, trees in planters
for sx in (-1, 1):
    lamp_line(sx * 111.0, 224, sx * 111.0, 566, 22)
    for k in range(0, 60):
        addp("bollard", sx * 108.8, 222 + k * 5.8, 0)
    for k in range(14):
        addp("tree", sx * R.uniform(114, 119), 232 + k * 24 + R.uniform(-4, 4))
for sx in (-24, 24):
    lamp_line(sx, STREET_Y0 + 5, sx, STREET_Y1, 30)

# traffic on the boulevard: six lanes each way; the middle stays fairly empty for the duel, the outer lanes carry stopped traffic
for lane in range(-9, 9):
    lx = lane * 12.0 + 6.0
    if abs(lx) < 4:
        continue
    y = 232.0 + R.uniform(0, 12)
    dens = 0.1 if abs(lx) < 30 else 0.55
    while y < 556:
        if R.random() < dens:
            addp("car", lx + R.uniform(-1.2, 1.2), y, 90 if lx > 0 else 270, R.choice(CAR_KINDS))
        y += R.uniform(9, 24)
# the crossing avenue: a traffic jam, bumper to bumper
for lane_y, yaw in ((158.0, 0), (170.0, 0), (194.0, 180), (206.0, 180)):
    x = -640.0
    while x < 640:
        if abs(x) > 12 or R.random() < 0.5:
            if R.random() < 0.62:
                addp("car", x, lane_y + R.uniform(-1, 1), yaw, R.choice(CAR_KINDS))
        x += R.uniform(8, 16)
# the old outer avenues
for i in range(120):
    ax = R.choice([-150.0, 150.0])
    x, y = ax + R.uniform(-24, 24), R.uniform(Y0 + 20, 1100)
    addp("car", x, y, R.choice([90, 270]), R.choice(CAR_KINDS))

# pedestrians (most under neon umbrellas) on the zebra crossings, the pavements and the pedestrian street
for zy in (221.0, 569.0):
    for i in range(34):
        addp("person", R.uniform(-104, 104), zy + R.uniform(-5, 5), R.uniform(0, 360))
for sx in (-1, 1):
    for i in range(55):
        addp("person", sx * R.uniform(110, 120), R.uniform(224, 566), R.uniform(0, 360))
for i in range(120):
    addp("person", R.uniform(-5.5, 5.5), R.uniform(STREET_Y0 + 5, STREET_Y1 - 5), R.uniform(0, 360))
for i in range(30):
    addp("person", R.uniform(-120, 120), R.uniform(152, 213), R.uniform(0, 360))

# pavement furniture
for sx in (-1, 1):
    face = 180 if sx > 0 else 0
    for y in (260.0, 340.0, 470.0, 540.0):
        addp("busstop", sx * 113.5, y + R.uniform(-8, 8), face)
    for k in range(7):
        addp("kiosk", sx * 117.0, 240 + k * 48 + R.uniform(-6, 6), face, None)
    for k in range(24):
        y = 225 + k * 14.2
        addp(R.choice(["vending", "hydrant", "bench", "trash", "sign", "vending", "trash"]), sx * R.uniform(111.5, 119.0), y + R.uniform(-3, 3), face)
    # zebra-crossing traffic lights
    for zy in (232.0, 558.0):
        addp("trafficlight", sx * 107.0, zy, 180 if sx > 0 else 0, str(R.randint(0, 2)))
# construction site in one corner of the plaza: barriers, cones, crates, a dumpster
cx0, cx1, cy0, cy1 = 56.0, 98.0, 500.0, 548.0
for t in range(int((cx1 - cx0) / 3.2) + 1):
    addp("barrier", cx0 + t * 3.2, cy0, 0)
    addp("barrier", cx0 + t * 3.2, cy1, 0)
for t in range(int((cy1 - cy0) / 3.2) + 1):
    addp("barrier", cx0, cy0 + t * 3.2, 90)
    addp("barrier", cx1, cy0 + t * 3.2, 90)
for i in range(26):
    addp("cone", R.uniform(cx0 - 6, cx1 + 6), R.uniform(cy0 - 6, cy1 + 6), 0)
for i in range(18):
    addp("crate", R.uniform(cx0 + 3, cx1 - 3), R.uniform(cy0 + 3, cy1 - 3), R.uniform(0, 360))
for i in range(3):
    addp("dumpster", R.uniform(cx0 + 5, cx1 - 5), R.uniform(cy0 + 4, cy1 - 4), R.uniform(0, 360))
# a second, smaller roadworks fence on the opposite side
for t in range(10):
    addp("barrier", -90.0 + t * 3.2, 262.0, 0)
for i in range(12):
    addp("cone", R.uniform(-92, -58), R.uniform(255, 268), 0)
# the pedestrian street: market stalls on both sides, crates and rubbish behind them
y = STREET_Y0 + 10
while y < STREET_Y1 - 6:
    for sx in (-1, 1):
        addp("stall", sx * 6.4, y + R.uniform(-1, 1), 0 if sx < 0 else 180)
        if R.random() < 0.5:
            addp("crate", sx * 8.2, y + R.uniform(-3, 3), R.uniform(0, 360))
    y += 7.5
for i in range(30):
    addp("trash", R.choice([-1, 1]) * R.uniform(7.6, 8.6), R.uniform(STREET_Y0, STREET_Y1), R.uniform(0, 360))
# dumpsters and rubbish at the foot of the buildings that line the plaza and the avenue
for i in range(40):
    addp(R.choice(["dumpster", "trash", "crate", "hydrant"]), R.choice([-1, 1]) * R.uniform(122, 130), R.uniform(222, 570), R.uniform(0, 360))
for i in range(40):
    addp(R.choice(["dumpster", "trash", "crate"]), R.uniform(-400, 400), R.choice([149.0, 216.0]) + R.uniform(-2, 2), R.uniform(0, 360))

# overhead cross-street lantern/wire lines along the street (rendered by the loader as emissive beads)
strings = []
y = STREET_Y0 + 14
while y < STREET_Y1:
    strings.append({"a": [-STREET_X + 0.5, round(y, 1), 11.5], "b": [STREET_X - 0.5, round(y, 1), 11.5], "sag": 1.0, "color": list(R.choice([(1.0, 0.3, 0.5), (1.0, 0.7, 0.2), (0.3, 0.9, 1.0)])), "beads": 12})
    y += R.uniform(14, 22)

# scattered fill lights on the plaza (sodium/teal street lamps) and over the crossing
for i in range(16):
    lights.append({"pos": [R.uniform(-100, 100), R.uniform(230, 550), 12.0], "color": list(R.choice([(1.0, 0.65, 0.35), (0.35, 0.8, 1.0), (1.0, 0.3, 0.7)])), "intensity": 12.0, "radius": 40.0, "flicker": 0, "prio": 90.0})

pois = [
    {"id": "spawn_player", "kind": "spawn_player", "name": "player", "pos": [0.0, 300.0, 0.0], "yaw_deg": 90.0},
    {"id": "spawn_enemy", "kind": "spawn_enemy", "name": "enemy", "pos": [0.0, 500.0, 0.0], "yaw_deg": 270.0},
    {"id": "spawn_duel_a", "kind": "spawn_duel_a", "name": "a", "pos": [0.0, 310.0, 0.0], "yaw_deg": 90.0},
    {"id": "spawn_duel_b", "kind": "spawn_duel_b", "name": "b", "pos": [0.0, 490.0, 0.0], "yaw_deg": 270.0},
]

doc = {
    "schema_version": 1, "seed": 20261004, "arena": "takeshita",
    "bounds": {"units": "meters", "axes": "x right, y north, z up", "playable": {"x_min": -800, "x_max": 800, "y_min": 0, "y_max": 1200}, "terrain": {"x_min": X0, "x_max": X1, "y_min": Y0, "y_max": Y1}},
    "terrain": {"heightmap": "heightmap.r16", "format": "r16_little_endian", "resolution": RES, "row_order": "y_ascending",
                "extent": {"x_min": X0, "x_max": X1, "y_min": Y0, "y_max": Y1}, "cell_size_m": (X1 - X0) / (RES - 1),
                "height_encoding": {"zero_value": 32768, "units_per_meter": 128.0}, "min_z": 0.0, "max_z": 0.0, "sea_level_z": -60.0},
    "water": {"level_z": -60.0, "sea_floor_z": -80.0, "shoreline": [], "flood_zones": []},
    "roads": roads, "blocks": [], "buildings": buildings, "infrastructure": {}, "props": props, "pois": pois, "hazards": [],
    "signs": signs, "lights": lights, "strings": strings,
}
os.makedirs(OUT, exist_ok=True)
with open(os.path.join(OUT, "district_arena.json"), "w", encoding="utf-8") as f:
    json.dump(doc, f, separators=(",", ":"))
with open(os.path.join(OUT, "heightmap_arena.r16"), "wb") as f:
    f.write(struct.pack("<H", 32768) * (RES * RES))
print("buildings", len(buildings), "signs", len(signs), "lights", len(lights), "props", len(props), "strings", len(strings))
