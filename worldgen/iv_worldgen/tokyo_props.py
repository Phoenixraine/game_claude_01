"""Props, wires and light points of the Tokyo style (TASK-015): vending machines (800+), lanterns, utility poles with sagging wires, emissive signs
(no text), traffic lights, bus stops, cones, bicycles, scooters, street trees and 40 sakura around the temple and the canal."""
import math

from .geom import bbox, centroid, dist_to_poly_edges, norm, point_in_poly
from .props import CAR_VARIANTS, TREE_VARIANTS, PropPlacer

SIGN_COLORS = ["pink", "cyan", "amber", "red", "green", "violet", "white"]
SIGN_RGB = {"pink": (255, 70, 170), "cyan": (60, 230, 255), "amber": (255, 180, 50), "red": (255, 60, 50), "green": (90, 255, 140), "violet": (160, 100, 255), "white": (255, 245, 230)}
VENDING = ["drink_a", "drink_b", "snack", "ticket", "capsule"]


def _r(v, n=1):
    return round(v, n)


class TokyoPropPlacer(PropPlacer):
    def add_free(self, kind, x, y, z, yaw, variant, extra=None):
        """Wall / pole mounted item: no collision test against buildings (it sits on the facade), still inside the arena."""
        if not (-800 <= x <= 800 and -400 <= y <= 1200):
            return False
        self.counts[kind] = self.counts.get(kind, 0) + 1
        p = {"id": "%s_%04d" % (kind, self.counts[kind]), "kind": kind, "pos": [_r(x), _r(y), _r(z, 2)], "yaw_deg": _r(math.degrees(yaw)), "variant": variant}
        if extra:
            p.update(extra)
        self.props.append(p)
        return True


def _polyline_runs(pts, spacing, rng):
    """Positions (x, y, ux, uy) every ~spacing metres of arc length."""
    out = []
    for i in range(len(pts) - 1):
        ax, ay = pts[i]
        bx, by = pts[i + 1]
        ln = math.hypot(bx - ax, by - ay)
        if ln < 1e-6:
            continue
        ux, uy = (bx - ax) / ln, (by - ay) / ln
        s = rng.uniform(0.0, spacing)
        while s < ln:
            out.append((ax + ux * s, ay + uy * s, ux, uy))
            s += spacing * rng.uniform(0.8, 1.2)
    return out


def make_props(layout, terrain, rng, building_polys, buildings, heroes, return_placer=False):
    P = TokyoPropPlacer(terrain, rng.fork("props"), building_polys)
    rr = P.rng
    roads = layout.roads
    alleys = [r for r in roads if r["kind"] == "alley"]
    main = [r for r in roads if r["kind"] != "alley"]
    # ---- cars, lamps, trees, benches (rules as in v1, lighter in the narrow streets) --------------------------------------
    for road in main:
        pts = [tuple(p) for p in road["points"]]
        w = road["width"]
        kind = road["kind"]
        P.along(pts, "car", 26.0 if kind != "promenade" else 70.0, w / 2.0 - 7.0, 2.5, CAR_VARIANTS, 0.85 if kind != "embankment" else 0.6, mind=7.0)
        if w >= 50:
            P.along(pts, "car", 46.0, w / 2.0 - 20.0, 2.0, CAR_VARIANTS, 0.7, mind=7.0)
        P.along(pts, "lamp", 34.0, w / 2.0 + 1.6, 0.4, ["single", "double"], 1.0, mind=4.0)
        if kind in ("avenue", "promenade", "embankment"):
            P.along(pts, "tree", 20.0, w / 2.0 + 5.0, 1.0, TREE_VARIANTS, 0.9, mind=5.0)
        elif kind == "street":
            P.along(pts, "tree", 36.0, w / 2.0 + 5.0, 1.0, TREE_VARIANTS, 0.55, mind=5.0)
        if kind == "promenade":
            P.along(pts, "bench", 60.0, w / 2.0 - 2.0, 0.5, ["bench_a"], 0.7, yaw_off=math.pi / 2, mind=4.0, both_sides=False)
    for road in alleys:
        pts = [tuple(p) for p in road["points"]]
        P.along(pts, "lamp", 30.0, road["width"] / 2.0 - 0.8, 0.3, ["single"], 1.0, mind=4.0, both_sides=False)
    # ---- vending machines: dense along alleys and kerbs, >= 800 --------------------------------------------------------
    target = 840
    passes = [(alleys, 7.5, 0.8, 0.6), (main, 22.0, 0.55, 1.0)]
    for rounds in range(5):
        for group, spacing, chance, off in passes:
            for road in group:
                pts = [tuple(p) for p in road["points"]]
                P.along(pts, "vending", spacing, road["width"] / 2.0 + (0.6 if road["kind"] == "alley" else 1.1) + off * 0.0, 0.2, VENDING, chance, mind=2.4)
        if P.counts.get("vending", 0) >= target:
            break
        passes = [(alleys, 6.0, 0.9, 0.0), (main, 16.0, 0.7, 0.0)]
    # ---- lanterns (red paper lanterns) in the alleys + temple precinct ---------------------------------------------------
    for road in alleys:
        pts = [tuple(p) for p in road["points"]]
        P.along(pts, "lantern", 11.0, road["width"] / 2.0 - 1.4, 0.3, ["red", "red", "white"], 0.8, mind=3.0)
    gate = next(h for h in heroes if h["hero_kind"] == "temple_gate")
    gc = centroid([tuple(p) for p in gate["footprint"]])
    for k in range(24):
        a = 2 * math.pi * k / 24
        P.add("lantern", gc[0] + math.cos(a) * 16.0, gc[1] + math.sin(a) * 16.0, a, "red", 2.0)
    # ---- utility poles with wires ---------------------------------------------------------------------------------------
    wires = []
    n_pole = [0]

    def add_pole(x, y):
        if P.add("utility_pole", x, y, 0.0, "wood_a", mind=5.0):
            return P.props[-1]
        return None

    for road in alleys + [r for r in main if r["kind"] == "street" and r["width"] <= 52.0][:6]:
        pts = [tuple(p) for p in road["points"]]
        side = 1 if rr.chance(0.5) else -1
        last = None
        for (x, y, ux, uy) in _polyline_runs(pts, 26.0, rr):
            off = side * (road["width"] / 2.0 - 0.9 if road["kind"] == "alley" else road["width"] / 2.0 + 1.8)
            pole = add_pole(x - uy * off, y + ux * off)
            if pole is None:
                last = None
                continue
            if last is not None:
                a, b = last["pos"], pole["pos"]
                for tier, (dz, sag) in enumerate(((8.6, 0.9), (7.7, 0.7), (6.9, 0.6))):
                    pts3 = []
                    for k in range(5):
                        f = k / 4.0
                        pts3.append([_r(a[0] + (b[0] - a[0]) * f, 2), _r(a[1] + (b[1] - a[1]) * f, 2), _r(a[2] + dz - sag * 4.0 * f * (1.0 - f), 2)])
                    wires.append({"id": "wire_%04d" % (len(wires) + 1), "kind": "power", "from": last["id"], "to": pole["id"], "points": pts3})
            last = pole
    # ---- emissive signs on the facades (no text) --------------------------------------------------------------------------
    for b in buildings:
        if b["type"] != "generic" or b["height"] < 10.0:
            continue
        p_sign = {"low_shop": 0.95, "apartment_tower": 0.7, "office_tower": 0.6, "parking": 0.3, "temple": 0.0}.get(b["building_type"], 0.3)
        if not rr.chance(p_sign):
            continue
        n_signs = rr.randint(1, 3) if b["building_type"] == "low_shop" else (rr.randint(1, 2) if b["building_type"] != "parking" else 1)
        for _sign in range(n_signs):
            _place_sign(P, rr, layout, b)
    props, wires = _finish_props(P, layout, terrain, rr, main, alleys, heroes, gc, wires)
    return (P, wires) if return_placer else (props, wires)


def _place_sign(P, rr, layout, b):
    if True:
        poly = [tuple(p) for p in b["footprint"]]
        c = centroid(poly)
        # facade edge facing the nearest street
        best = None
        for i in range(len(poly)):
            m = ((poly[i][0] + poly[(i + 1) % len(poly)][0]) / 2.0, (poly[i][1] + poly[(i + 1) % len(poly)][1]) / 2.0)
            d = min(_dist_road(layout, m, 0.0), 1e9)
            if best is None or d < best[0]:
                best = (d, i, m)
        _, i, m = best
        a, bq = poly[i], poly[(i + 1) % len(poly)]
        tx, ty = norm((bq[0] - a[0], bq[1] - a[1]))
        nx, ny = norm((m[0] - c[0], m[1] - c[1]))
        ln = math.hypot(bq[0] - a[0], bq[1] - a[1])
        w = min(ln * 0.8, rr.uniform(1.6, 4.5))
        h = rr.uniform(3.5, 9.0) if rr.chance(0.5) else rr.uniform(1.2, 2.2)
        zz = rr.uniform(3.0, max(3.5, min(b["height"] - h - 1.0, 24.0)))
        col = rr.choice(SIGN_COLORS)
        x = m[0] + nx * 0.5 + tx * rr.uniform(-0.2, 0.2) * ln
        y = m[1] + ny * 0.5 + ty * rr.uniform(-0.2, 0.2) * ln
        P.add_free("sign", x, y, zz, math.atan2(ny, nx), col, {"size": [_r(w, 2), _r(h, 2)], "emissive": True, "building_id": b["id"]})


def _finish_props(P, layout, terrain, rr, main, alleys, heroes, gc, wires):
    # ---- traffic lights, bus stops, cones ----------------------------------------------------------------------------------
    for (xc, w, kind, name) in layout.vlines:
        for (yc, hw, hk) in layout.hlines:
            cx, cy = layout.warp(xc, yc)
            for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                P.add("traffic_light", cx + sx * (w / 2.0 + 1.8), cy + sy * (hw / 2.0 + 1.8), math.atan2(-sy, -sx), "pole_3", 3.0)
    for road in main:
        if road["kind"] in ("avenue", "street") and road["width"] >= 44:
            pts = [tuple(p) for p in road["points"]]
            P.along(pts, "bus_stop", 170.0, road["width"] / 2.0 + 2.0, 0.5, ["shelter_a", "shelter_b"], 0.9, mind=12.0, both_sides=False)
    sc = layout.scramble_centre()
    for k in range(48):
        a = 2 * math.pi * k / 48
        P.add("cone", sc[0] + math.cos(a) * 49.0, sc[1] + math.sin(a) * 49.0, a, "orange", 2.0)
    # ---- bicycles and scooters -------------------------------------------------------------------------------------------------
    for road in alleys:
        pts = [tuple(p) for p in road["points"]]
        P.along(pts, "scooter", 17.0, road["width"] / 2.0 - 2.2, 0.4, ["scooter_a", "scooter_b"], 0.55, mind=2.2, both_sides=False)
        P.along(pts, "bicycle", 13.0, -(road["width"] / 2.0 - 2.4), 0.4, ["city_bike", "mama_chari"], 0.6, mind=1.8, both_sides=False)
    st = next(h for h in heroes if h["hero_kind"] == "twin_tower_hall") if False else None
    # ---- sakura: 20 round the temple, 20 along the canal banks -------------------------------------------------------------
    placed = 0
    for k in range(240):
        if placed >= 20:
            break
        a = 2 * math.pi * k / 240.0 * 7.0
        rad = 20.0 + 4.0 * (k % 7)
        if P.add("sakura", gc[0] + math.cos(a) * rad, gc[1] + math.sin(a) * rad, a, "blossom", 4.5):
            placed += 1
    placed = 0
    x = -780.0
    tries = 0
    while placed < 20 and tries < 400:
        yc = layout.canal_centre(x)
        w = layout.canal_width(x)
        side = 1 if tries % 2 == 0 else -1
        if P.add("sakura", x, yc + side * (w / 2.0 + 14.0), 0.0, "blossom", 5.0):
            placed += 1
        x += 53.0
        if x > 780.0:
            x = -770.0 + (tries % 5) * 9.0
        tries += 1
    # ---- extra street trees along the canal banks and the promenade -------------------------------------------------------------
    return P.props, wires


def _dist_road(layout, p, margin):
    from .geom import dist_point_polyline
    best = 1e18
    for r in layout.roads:
        d = dist_point_polyline(p, [tuple(q) for q in r["points"]]) - r["width"] / 2.0
        if d < best:
            best = d
    return best
