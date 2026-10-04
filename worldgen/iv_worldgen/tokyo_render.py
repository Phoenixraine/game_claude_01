"""Previews of the Tokyo style: top-down plan with legend and a skyline seen from the bay with the landmarks named (software rasteriser, no PIL)."""
import math

from .raster import Canvas
from .render import ASPHALT, BLOCK, LAND, SAND, SEA_DEEP, SEA_TOP, _lerp
from .terrain import X0, X1

HERO_COLORS = {"glass_tower": (60, 200, 230), "tower_lattice": (235, 70, 60), "twin_tower_hall": (170, 120, 230), "brick_station": (170, 70, 50),
               "sphere_building": (250, 200, 80), "temple_gate": (255, 90, 40), "scramble_crossing": (255, 255, 255), "port_crane": (250, 150, 40),
               "expressway": (150, 90, 200), "suspension_bridge": (235, 235, 245)}
TYPE_COLORS = {"glass_tower": (70, 190, 225), "shopfront_row": (235, 120, 170), "apartment_tower": (222, 178, 130), "office_tower": (110, 130, 170), "low_shop": (205, 190, 150), "parking": (150, 150, 158), "temple": (200, 70, 50),
               "station": (170, 70, 50), "landmark": (200, 200, 200)}
ROAD_COLORS = {"promenade": (110, 112, 118), "embankment": (92, 92, 104), "avenue": (82, 84, 92), "street": ASPHALT, "alley": (118, 116, 112)}


def render_topdown(doc, terrain, title=None, overlay=None, legend_extra=None):
    ymin, ymax = -120.0, 1200.0
    W, H = int(X1 - X0), int(ymax - ymin)
    cv = Canvas(W, H)

    def P(x, y):
        return (x - X0, ymax - y)

    for py in range(H):
        y = ymax - py - 0.5
        base = py * W * 3
        buf = cv.buf
        for px in range(W):
            z = terrain.height(X0 + px + 0.5, y)
            if z < 0:
                c = _lerp(SEA_TOP, SEA_DEEP, -z / 25.0)
            elif z < 1.2:
                c = SAND
            else:
                c = _lerp(LAND, (120, 140, 96), min(1.0, (z - 1.2) / 8.0))
            i = base + px * 3
            buf[i], buf[i + 1], buf[i + 2] = c
    for b in doc["blocks"]:
        cv.polygon([P(*p) for p in b["polygon"]], BLOCK)
    for r in sorted(doc["roads"], key=lambda r: -r["width"]):
        col = ROAD_COLORS.get(r["kind"], ASPHALT)
        pts = [P(*p) for p in r["points"]]
        for i in range(len(pts) - 1):
            cv.thick_line(pts[i], pts[i + 1], r["width"] / 2.0, col)
    for br in doc["infrastructure"]["bridges"]:
        a, b = P(*br["from"]), P(*br["to"])
        cv.thick_line(a, b, br["width"] / 2.0, (190, 190, 196))
    # expressway deck, ramps
    ex = next(b for b in doc["buildings"] if b.get("hero_kind") == "expressway")
    cv.polygon([P(*p) for p in ex["footprint"]], (130, 80, 170), 0.55)
    for part in ex["parts"]:
        if part["kind"] == "ramp":
            pts = [P(p[0], p[1]) for p in part["points"]]
            for i in range(len(pts) - 1):
                cv.thick_line(pts[i], pts[i + 1], 6.0, (170, 110, 210))
    for h in doc["hazards"]:
        pts = [P(*p) for p in h["polygon"]]
        if h["kind"] == "expressway_collapse":
            cv.polygon(pts, (255, 80, 80), 0.28)
            cv.outline(pts, (255, 60, 60), 2)
        elif h["kind"] == "canal_flood":
            cv.outline(pts, (60, 140, 255), 1)
    for c in doc["infrastructure"]["port"]["containers"]:
        x, y = P(*c["pos"])
        cv.rect(int(x) - 6, int(y) - 3, int(x) + 5, int(y) + 3, [(200, 70, 60), (60, 110, 190), (230, 170, 50), (70, 150, 90), (160, 160, 170), (150, 90, 60)][c["variant"] % 6])
    cv.polygon([P(*p) for p in doc["infrastructure"]["port"]["quay"]], (128, 128, 132), 0.5)
    for b in doc["buildings"]:
        if b["type"] == "hero":
            continue
        t = min(1.0, b["height"] / 200.0)
        col = _lerp(TYPE_COLORS[b["building_type"]], (40, 44, 70), t * 0.55)
        pts = [P(*p) for p in b["footprint"]]
        cv.polygon(pts, col)
        cv.outline(pts, (50, 50, 55), 1)
    for b in doc["buildings"]:
        if b["type"] != "hero" or b["hero_kind"] in ("expressway", "suspension_bridge"):
            continue
        pts = [P(*p) for p in b["footprint"]]
        cv.polygon(pts, HERO_COLORS[b["hero_kind"]], 0.85 if b["hero_kind"] == "scramble_crossing" else 1.0)
        cv.outline(pts, (20, 20, 20), 2)
        if b["hero_kind"] == "scramble_crossing":
            for part in b["parts"]:
                if part["kind"] == "crosswalk":
                    cv.line(P(*part["from"]), P(*part["to"]), (20, 20, 20), 2)
        for part in b.get("parts", []):
            if part["kind"] == "boom":
                cv.line(P(*part["from"]), P(*part["to"]), (30, 30, 30), 3)
            if part["kind"] == "body":
                cv.outline([P(*p) for p in part["footprint"]], (60, 20, 100), 2)
    br = next(b for b in doc["buildings"] if b.get("hero_kind") == "suspension_bridge")
    cv.polygon([P(*p) for p in br["footprint"]], (235, 235, 245))
    cv.outline([P(*p) for p in br["footprint"]], (30, 30, 40), 1)
    for part in br["parts"]:
        if part["kind"] == "pylon":
            x, y = P(*part["pos"])
            cv.rect(int(x) - 6, int(y) - 12, int(x) + 6, int(y) + 12, (240, 60, 50))
    for pr in doc["props"]:
        x, y = P(pr["pos"][0], pr["pos"][1])
        k = pr["kind"]
        if k == "tree":
            cv.px(int(x), int(y), (28, 110, 44))
        elif k == "sakura":
            cv.disc(x, y, 2, (255, 150, 190))
        elif k == "vending":
            cv.px(int(x), int(y), (60, 240, 255))
        elif k == "lantern":
            cv.px(int(x), int(y), (255, 50, 40))
        elif k == "car":
            cv.px(int(x), int(y), (235, 235, 235))
        elif k == "sign":
            cv.px(int(x), int(y), (255, 70, 200))
        elif k == "utility_pole":
            cv.px(int(x), int(y), (120, 80, 40))
    for poi in doc["pois"]:
        x, y = P(poi["pos"][0], poi["pos"][1])
        k = poi["kind"]
        if k == "spawn_player":
            cv.disc(x, y, 9, (30, 220, 60))
        elif k == "spawn_enemy":
            cv.disc(x, y, 9, (230, 40, 40))
        elif k.startswith("spawn_duel") or k == "duel_point":
            cv.disc(x, y, 7, (255, 230, 40))
        elif k == "camera":
            tri = [(x, y - 8), (x + 7, y + 6), (x - 7, y + 6)]
            cv.polygon(tri, (255, 255, 255))
            cv.outline(tri, (0, 0, 0), 1)
    if overlay:
        overlay(cv, P)
    for b in doc["buildings"]:
        if b["type"] != "hero":
            continue
        pts = [P(*p) for p in b["footprint"]]
        cx = sum(p[0] for p in pts) / len(pts)
        cy = min(p[1] for p in pts) - 14
        if b["hero_kind"] == "glass_tower":
            cy = max(p[1] for p in pts) + 4
        if b["hero_kind"] == "expressway":
            cx, cy = P(300.0, [q for q in b["footprint"]][0][1] if False else 395.0)
            cy -= 40
        lab = b["name"].upper()
        tw = Canvas.text_width(lab, 2)
        cv.rect(int(cx - tw / 2) - 3, int(cy) - 3, int(cx + tw / 2) + 3, int(cy) + 17, (0, 0, 0))
        cv.text(int(cx - tw / 2), int(cy), lab, (255, 255, 255), 2)
    cv.rect(W - 230, H - 40, W - 30, H - 36, (255, 255, 255))
    cv.text(W - 230, H - 30, "200 M", (255, 255, 255), 2)
    items = [("HERO OBJECT (10, NAMED)", (255, 255, 255)), ("APARTMENT TOWER", TYPE_COLORS["apartment_tower"]), ("OFFICE TOWER", TYPE_COLORS["office_tower"]),
             ("LOW SHOP", TYPE_COLORS["low_shop"]), ("PARKING", TYPE_COLORS["parking"]), ("TEMPLE", TYPE_COLORS["temple"]), ("EXPRESSWAY + RAMPS", (130, 80, 170)),
             ("COLLAPSE ZONE", (255, 80, 80)), ("CANAL 50-80 M + 2 BRIDGES", (60, 140, 255)), ("SPAWN PLAYER (BAY)", (30, 220, 60)), ("SPAWN ENEMY (SCRAMBLE)", (230, 40, 40)),
             ("DUEL POINTS", (255, 230, 40)), ("CAMERA", (255, 255, 255)), ("ALLEY 24-36 M", ROAD_COLORS["alley"]), ("STREET 44-90 M", ASPHALT), ("VENDING MACHINE", (60, 240, 255)),
             ("LANTERN", (255, 50, 40)), ("SAKURA (40)", (255, 150, 190)), ("SIGN (NO TEXT)", (255, 70, 200)), ("CAR", (235, 235, 235))] + list(legend_extra or [])
    lx, ly = 16, H - 36 - (len(items) + 1) // 2 * 20 - 30
    cv.rect(lx - 6, ly - 6, lx + 700, H - 8, (20, 22, 28))
    cv.text(lx, ly, title or ("TOKYO DISTRICT  SEED %d  1.6 X 1.2 KM  (SEA AT THE BOTTOM)" % doc["seed"]), (255, 255, 255), 2)
    half = (len(items) + 1) // 2
    for k, (label, col) in enumerate(items):
        x = lx + (k // half) * 350
        y = ly + 26 + (k % half) * 20
        cv.rect(x, y, x + 14, y + 12, col)
        cv.text(x + 22, y + 2, label, (230, 230, 230), 2)
    return cv


def render_skyline(doc, terrain):
    W, H = 1600, 520
    zmin, zmax = -30.0, 345.0
    sc = (H - 40) / (zmax - zmin)
    cv = Canvas(W, H)

    def PX(x):
        return int(x - X0)

    def PZ(z):
        return int(H - 14 - (z - zmin) * sc)

    for y in range(H):
        cv.hline(0, W - 1, y, _lerp((120, 160, 205), (225, 215, 200), y / H))
    items = sorted(doc["buildings"], key=lambda b: -sum(p[1] for p in b["footprint"]) / len(b["footprint"]))
    for b in items:
        xs = [p[0] for p in b["footprint"]]
        ys = [p[1] for p in b["footprint"]]
        depth = max(0.0, min(1.0, (sum(ys) / len(ys) - 250.0) / 950.0))
        x0, x1 = PX(min(xs)), PX(max(xs))
        base = b["base_z"]
        k = b.get("hero_kind")
        if k == "expressway":
            for c in b["structure"]["columns"]:
                cx = PX(c["pos"][0])
                cv.rect(cx - 1, PZ(b["deck_z"]), cx + 1, PZ(base), (100, 80, 120))
            cv.rect(x0, PZ(b["deck_z"] + 1.5), x1, PZ(b["deck_z"] - 1.0), HERO_COLORS[k])
            continue
        if k == "suspension_bridge":
            cv.rect(x0, PZ(b["deck_z"] + 1.0), x1, PZ(b["deck_z"] - 1.0), HERO_COLORS[k])
            for part in b["parts"]:
                if part["kind"] == "pylon":
                    px = PX(part["pos"][0])
                    cv.rect(px - 3, PZ(part["top_z"]), px + 3, PZ(-20.0), (240, 60, 50))
                if part["kind"] == "main_cable" and part["points"][0][1] < b["footprint"][0][1] + 40:
                    pts = [(PX(p[0]), PZ(p[2])) for p in part["points"]]
                    for i in range(len(pts) - 1):
                        cv.line(pts[i], pts[i + 1], (245, 245, 250), 2)
            continue
        if k == "tower_lattice":
            cx = (x0 + x1) // 2
            for z in range(0, 333, 6):
                half = 32 * (1 - z / 333.0) ** 1.2 + 2
                band = (235, 70, 60) if (z // 30) % 2 == 0 else (245, 245, 245)
                cv.rect(int(cx - half), PZ(z + 6), int(cx + half), PZ(z), band)
            continue
        if k == "sphere_building":
            cx = (x0 + x1) // 2
            for p in b["parts"]:
                if p["kind"] == "sphere":
                    cv.disc(cx, PZ(p["center"][2]), p["radius"] * sc, (250, 200, 80))
            cv.rect(x0 + 10, PZ(8.8), x1 - 10, PZ(base), (200, 200, 205))
            continue
        if k == "port_crane":
            cv.rect(x0, PZ(70.0), x1, PZ(base), HERO_COLORS[k])
            cv.rect(x0 - 8, PZ(78.0), x1 + 8, PZ(70.0), HERO_COLORS[k])
            continue
        if k == "scramble_crossing":
            continue
        if k == "twin_tower_hall":
            for p in b["parts"]:
                if p["kind"] == "body":
                    bx = [q[0] for q in p["footprint"]]
                    cv.rect(PX(min(bx)), PZ(base + p["height"]), PX(max(bx)), PZ(base), HERO_COLORS[k])
            cv.rect(x0, PZ(base + 12.0), x1, PZ(base), HERO_COLORS[k])
            continue
        col = HERO_COLORS[k] if k else _lerp(TYPE_COLORS[b["building_type"]], (120, 130, 160), 0.45 + 0.4 * depth)
        top = base + b["height"]
        cv.rect(x0, PZ(top), x1, PZ(base), col)
        if k:
            cv.outline([(x0, PZ(top)), (x1, PZ(top)), (x1, PZ(base)), (x0, PZ(base))], (20, 20, 20), 1)
    for y in range(PZ(0.0), H):
        cv.hline(0, W - 1, y, _lerp((70, 130, 178), (12, 40, 86), (y - PZ(0.0)) / max(1, H - PZ(0.0))))
    cv.hline(0, W - 1, PZ(0.0), (230, 240, 250))
    heroes = sorted([b for b in doc["buildings"] if b["type"] == "hero" and b["hero_kind"] != "scramble_crossing"], key=lambda b: sum(p[0] for p in b["footprint"]) / len(b["footprint"]))
    used = []
    for n, b in enumerate(heroes):
        xs = [p[0] for p in b["footprint"]]
        cx = PX((min(xs) + max(xs)) / 2.0)
        if b["hero_kind"] == "expressway":
            cx = PX(-640.0)
        top = {"tower_lattice": 333.0, "suspension_bridge": 90.0, "expressway": b.get("deck_z", 0.0), "sphere_building": 58.0, "port_crane": 95.0}.get(b["hero_kind"], b["base_z"] + b["height"])
        lab = "%s %dM" % (b["name"].upper(), int(top if b["hero_kind"] in ("tower_lattice", "suspension_bridge") else b["height"] if b["hero_kind"] != "expressway" else b["length"]))
        tw = Canvas.text_width(lab, 2)
        lx0 = max(2, min(W - tw - 6, cx - tw // 2))
        row = 0
        while any(not (lx0 + tw + 8 < a or lx0 - 8 > b) for (r_, a, b) in used if r_ == row):
            row += 1
        used.append((row, lx0, lx0 + tw))
        ty = 28 + 24 * row
        cv.line((cx, ty + 17), (cx, max(ty + 20, PZ(top))), (20, 20, 30), 1)
        cv.rect(lx0 - 3, ty - 3, lx0 + tw + 3, ty + 17, (0, 0, 0))
        cv.text(lx0, ty, lab, (255, 255, 255), 2)
    cv.text(10, 6, "TOKYO SKYLINE FROM THE BAY (LOOKING +Y)  SEED %d" % doc["seed"], (20, 20, 30), 2)
    cv.text(10, H - 12, "WATER LEVEL 0 M   SEA FLOOR -25 M   1 PX = 1 M (X)   SCRAMBLE CROSSING = GROUND-LEVEL 80 X 80 M (NOT SHOWN)", (240, 240, 245), 1)
    return cv
