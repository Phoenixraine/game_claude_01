"""Preview renders: top-down map with legend and a skyline seen from the sea."""
import math

from .raster import Canvas
from .terrain import X0, X1, Y0, Y1

SEA_TOP = (62, 128, 176)
SEA_DEEP = (14, 44, 92)
SAND = (205, 192, 150)
LAND = (150, 168, 120)
ASPHALT = (74, 76, 82)
BLOCK = (176, 172, 160)
PLAZA = (214, 204, 176)
HERO_COLORS = {"glass_tower": (60, 200, 230), "stadium": (240, 190, 60), "residential_complex": (235, 120, 90),
               "overpass": (200, 90, 220), "port_crane": (250, 150, 40), "power_station": (230, 60, 60)}


def _lerp(a, b, t):
    t = max(0.0, min(1.0, t))
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def render_topdown(doc, terrain, path_png_fn):
    ymin, ymax = -120.0, 1200.0
    W = int(X1 - X0)
    H = int(ymax - ymin)
    cv = Canvas(W, H)

    def P(x, y):
        return (x - X0, ymax - y)

    # terrain colours
    for py in range(H):
        y = ymax - py - 0.5
        row = cv.buf
        base = py * W * 3
        for px in range(W):
            x = X0 + px + 0.5
            z = terrain.height(x, y)
            if z < 0:
                c = _lerp(SEA_TOP, SEA_DEEP, -z / 25.0)
            elif z < 1.2:
                c = SAND
            else:
                t = min(1.0, (z - 1.2) / 8.0)
                c = _lerp(LAND, (120, 140, 96), t)
                s = 0.94 + 0.06 * ((px + py) % 3 == 0)
                c = tuple(int(v * s) for v in c)
            i = base + px * 3
            row[i] = c[0]
            row[i + 1] = c[1]
            row[i + 2] = c[2]
    # blocks
    for b in doc["blocks"]:
        pts = [P(*p) for p in b["polygon"]]
        cv.polygon(pts, PLAZA if b["kind"] == "plaza" else BLOCK)
    # roads
    for r in doc["roads"]:
        col = (96, 98, 104) if r["kind"] == "promenade" else ASPHALT
        pts = [P(*p) for p in r["points"]]
        for i in range(len(pts) - 1):
            cv.thick_line(pts[i], pts[i + 1], r["width"] / 2.0, col)
        for i in range(len(pts) - 1):                                   # centre line
            cv.line(pts[i], pts[i + 1], (150, 150, 120), 1)
    # metro line
    metro = doc["infrastructure"]["metro"]
    mp = [P(*p) for p in metro["points"]]
    for i in range(0, len(mp) - 1):
        if i % 2 == 0:
            cv.line(mp[i], mp[i + 1], (150, 60, 190), 3)
    for seg in metro["weak_segments"]:
        cv.line(P(*seg["from"]), P(*seg["to"]), (255, 80, 220), 5)
    # port
    port = doc["infrastructure"]["port"]
    cv.polygon([P(*p) for p in port["quay"]], (128, 128, 132))
    for c in port["containers"]:
        x, y = P(*c["pos"])
        col = [(200, 70, 60), (60, 110, 190), (230, 170, 50), (70, 150, 90), (160, 160, 170), (150, 90, 60)][c["variant"] % 6]
        cv.rect(int(x) - 6, int(y) - 1, int(x) + 5, int(y) + 1, col)
    sub = doc["infrastructure"]["substation"]
    cv.polygon([P(*p) for p in sub["yard"]], (170, 170, 176))
    for t in sub["transformers"]:
        x, y = P(*t["pos"])
        cv.disc(x, y, 2, (60, 60, 70))
    # hazards
    for h in doc["hazards"]:
        pts = [P(*p) for p in h["polygon"]]
        if h["kind"] == "flood":
            cv.polygon(pts, (60, 120, 230), 0.35)
            cv.outline(pts, (40, 90, 220), 1)
        elif h["kind"] == "electrical":
            cv.polygon(pts, (240, 220, 60), 0.18)
            cv.outline(pts, (240, 200, 0), 2)
    # buildings
    for b in doc["buildings"]:
        pts = [P(*p) for p in b["footprint"]]
        if b["type"] == "hero":
            col = HERO_COLORS[b["hero_kind"]]
            cv.polygon(pts, col)
            cv.outline(pts, (20, 20, 20), 2)
        else:
            t = min(1.0, (b["height"] - 30.0) / 170.0)
            col = _lerp((214, 190, 150), (88, 96, 128), t)
            cv.polygon(pts, col)
            cv.outline(pts, (60, 60, 60), 1)
    for b in doc["buildings"]:
        if b["type"] == "hero":
            for part in b.get("parts", []):
                if part["kind"] == "chimney":
                    x, y = P(*part["pos"])
                    cv.disc(x, y, 6, (40, 40, 40))
                if part["kind"] == "boom":
                    cv.line(P(*part["from"]), P(*part["to"]), (30, 30, 30), 3)
    # props
    for pr in doc["props"]:
        x, y = P(pr["pos"][0], pr["pos"][1])
        if pr["kind"] == "tree":
            cv.disc(x, y, 2, (28, 110, 44))
        elif pr["kind"] == "car":
            cv.rect(int(x) - 1, int(y) - 1, int(x) + 1, int(y) + 1, (235, 235, 235))
        elif pr["kind"] == "lamp":
            cv.px(int(x), int(y), (255, 240, 120))
    # POIs
    for poi in doc["pois"]:
        x, y = P(poi["pos"][0], poi["pos"][1])
        if poi["kind"] == "spawn_player":
            cv.disc(x, y, 9, (30, 220, 60))
            cv.outline([(x - 11, y - 11), (x + 11, y - 11), (x + 11, y + 11), (x - 11, y + 11)], (0, 80, 0), 2)
        elif poi["kind"] == "spawn_enemy":
            cv.disc(x, y, 9, (230, 40, 40))
        elif poi["kind"].startswith("spawn_duel"):
            cv.disc(x, y, 7, (255, 230, 40))
        elif poi["kind"] == "camera":
            cv.polygon([(x, y - 8), (x + 7, y + 6), (x - 7, y + 6)], (255, 255, 255))
            cv.outline([(x, y - 8), (x + 7, y + 6), (x - 7, y + 6)], (0, 0, 0), 1)
    # hero labels
    for b in doc["buildings"]:
        if b["type"] == "hero":
            pts = [P(*p) for p in b["footprint"]]
            cx = sum(p[0] for p in pts) / len(pts)
            cy = min(p[1] for p in pts) - 12
            lab = b["name"].upper()
            tw = Canvas.text_width(lab, 2)
            cv.rect(int(cx - tw / 2) - 3, int(cy) - 3, int(cx + tw / 2) + 3, int(cy) + 17, (0, 0, 0))
            cv.text(int(cx - tw / 2), int(cy), lab, (255, 255, 255), 2)
    # scale bar, north (sea side) note
    cv.rect(20, H - 40, 20 + 200, H - 36, (255, 255, 255))
    cv.text(20, H - 30, "200 M", (255, 255, 255), 2)
    cv.text(W - 330, 14, "SEA IS AT THE BOTTOM", (255, 255, 255), 2)
    # legend
    lx, ly = 16, 16
    items = [("HERO BUILDING (6, NAMED ON MAP)", (60, 200, 230)), ("SPAWN PLAYER (WATER)", (30, 220, 60)), ("SPAWN ENEMY (PLAZA)", (230, 40, 40)), ("DUEL A / B", (255, 230, 40)), ("CAMERA", (255, 255, 255)),
             ("FLOOD ZONE", (60, 120, 230)), ("ELECTRIC HAZARD", (240, 200, 0)), ("METRO / WEAK ROOF", (150, 60, 190)), ("ROAD", ASPHALT),
             ("BLOCK", BLOCK), ("GENERIC BUILDING (TALLER = DARKER)", (88, 96, 128)), ("TREE", (28, 110, 44)), ("CAR", (235, 235, 235))]
    box_w = 12 + max(Canvas.text_width(t, 1) for t, _ in items) * 2 // 1 + 40
    cv.rect(lx - 6, ly - 6, lx + 420, ly + 12 + len(items) * 20 + 10 + 30, (20, 22, 28))
    cv.text(lx, ly, "IMPACT VECTOR DISTRICT  SEED %d  1.6 X 1.2 KM" % doc["seed"], (255, 255, 255), 2)
    y = ly + 26
    for label, col in items:
        cv.rect(lx, y, lx + 14, y + 12, col)
        cv.text(lx + 22, y + 2, label, (230, 230, 230), 2)
        y += 20
    return cv


def render_skyline(doc, terrain):
    W, H = 1600, 430
    zmin, zmax = -30.0, 250.0
    sc = (H - 30) / (zmax - zmin)
    cv = Canvas(W, H)

    def PX(x):
        return int(x - X0)

    def PZ(z):
        return int(H - 14 - (z - zmin) * sc)

    # sky
    for y in range(H):
        t = y / H
        c = _lerp((120, 160, 205), (225, 215, 200), t)
        cv.hline(0, W - 1, y, c)
    # distant haze layers
    bs = sorted(doc["buildings"], key=lambda b: -sum(p[1] for p in b["footprint"]) / len(b["footprint"]))
    for b in bs:
        xs = [p[0] for p in b["footprint"]]
        ys = [p[1] for p in b["footprint"]]
        depth = (sum(ys) / len(ys) - 250.0) / 950.0
        base = b["base_z"]
        top = base + b["height"]
        haze = max(0.0, min(1.0, depth))
        if b["type"] == "hero":
            col = HERO_COLORS[b["hero_kind"]]
        else:
            col = _lerp((92, 100, 126), (150, 162, 190), haze * 0.9 if b["type"] == "generic" else 0.0)
        x0, x1 = PX(min(xs)), PX(max(xs))
        if b["hero_kind" ] == "overpass" if b["type"] == "hero" else False:
            cv.rect(x0, PZ(b["deck_z"] + 1.5), x1, PZ(b["deck_z"] - 1.0), col)
            for c in b["structure"]["columns"]:
                cx = PX(c["pos"][0])
                cv.rect(cx - 1, PZ(b["deck_z"]), cx + 1, PZ(b["base_z"]), (100, 90, 110))
            continue
        if b["type"] == "hero" and b["hero_kind"] == "port_crane":
            cx0 = PX(min(xs))
            cv.rect(cx0, PZ(70.0), PX(max(xs)), PZ(b["base_z"]), col)
            cv.rect(cx0 - 20, PZ(78.0), PX(max(xs)) + 20, PZ(70.0), col)
            cv.line((cx0 - 55, PZ(74.0)), (PX(max(xs)) + 20, PZ(74.0)), (30, 30, 30), 4)
            continue
        if b["type"] == "hero" and b["hero_kind"] == "stadium":
            cv.polygon([(x0, PZ(base)), (x0 + 12, PZ(top)), (x1 - 12, PZ(top)), (x1, PZ(base))], col)
            continue
        cv.rect(x0, PZ(top), x1, PZ(base), col)
        if b["type"] == "hero":
            cv.outline([(x0, PZ(top)), (x1, PZ(top)), (x1, PZ(base)), (x0, PZ(base))], (20, 20, 20), 1)
        for part in b.get("parts", []):
            if part["kind"] == "chimney":
                px = PX(part["pos"][0])
                cv.rect(px - 3, PZ(base + part["height"]), px + 3, PZ(base), (60, 60, 64))
    # sea in front
    for y in range(PZ(0.0), H):
        t = (y - PZ(0.0)) / max(1, H - PZ(0.0))
        cv.hline(0, W - 1, y, _lerp((70, 130, 178), (12, 40, 86), t))
    cv.hline(0, W - 1, PZ(0.0), (230, 240, 250))
    # labels
    heroes = sorted([b for b in doc["buildings"] if b["type"] == "hero"], key=lambda b: sum(p[0] for p in b["footprint"]) / len(b["footprint"]))
    for k, b in enumerate(heroes):
        if True:
            xs = [p[0] for p in b["footprint"]]
            cx = PX((min(xs) + max(xs)) / 2.0)
            top = b["base_z"] + (b["height"] if b["hero_kind"] != "port_crane" else 78.0)
            lab = ("%s  %dM" % (b["name"].upper(), int(top - b["base_z"]) if b["hero_kind"] != "overpass" else int(b["length"])))
            tw = Canvas.text_width(lab, 2)
            ty = max(4 + 20 * (k % 3), PZ(top) - 24 - 4) if b["hero_kind"] == "glass_tower" else 40 + 120 * ((k % 3)) + 20 * (k // 3)
            if b["hero_kind"] != "glass_tower":
                cv.line((cx, ty + 17), (cx, max(ty + 20, PZ(top))), (20, 20, 30), 1)
            cv.rect(max(0, cx - tw // 2 - 3), ty - 3, min(W - 1, cx + tw // 2 + 3), ty + 17, (0, 0, 0))
            cv.text(max(2, cx - tw // 2), ty, lab, (255, 255, 255), 2)
    cv.text(10, 8, "SKYLINE FROM THE SEA (LOOKING +Y)  SEED %d" % doc["seed"], (20, 20, 30), 2)
    cv.text(10, H - 12, "WATER LEVEL 0 M   SEA FLOOR -25 M   SCALE 1 PX = 1 M (X)", (240, 240, 245), 1)
    return cv
