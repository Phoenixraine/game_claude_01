"""Props: cars, trees, lamps, guardrails. Placed by rules along roads; filtered against buildings and water."""
import math

from .geom import bbox, dist_to_poly_edges, point_in_poly, rot

CAR_VARIANTS = ["sedan", "van", "truck", "taxi", "hatchback", "bus"]
TREE_VARIANTS = ["plane", "palm", "birch", "pine"]


def _r(v, n=1):
    return round(v, n)


class PropPlacer:
    def __init__(self, terrain, rng, building_polys, road_polys=None):
        self.T = terrain
        self.rng = rng
        self.bpolys = [(bbox(p), p) for p in building_polys]
        self.props = []
        self.cell = {}
        self.counts = {}

    def _blocked(self, x, y, margin=2.0):
        for (x0, y0, x1, y1), poly in self.bpolys:
            if x0 - margin <= x <= x1 + margin and y0 - margin <= y <= y1 + margin:
                if point_in_poly((x, y), poly) or dist_to_poly_edges((x, y), poly)[0] < margin:
                    return True
        return False

    def _free(self, x, y, mind):
        gx, gy = int(x // 6), int(y // 6)
        for ix in (gx - 1, gx, gx + 1):
            for iy in (gy - 1, gy, gy + 1):
                for (px, py, pm) in self.cell.get((ix, iy), ()):
                    if (px - x) ** 2 + (py - y) ** 2 < max(mind, pm) ** 2:
                        return False
        return True

    def add(self, kind, x, y, yaw, variant, mind=3.0, z=None, extra=None):
        if not (-800 <= x <= 800 and -400 <= y <= 1200):
            return False
        zz = self.T.height(x, y) if z is None else z
        if zz < 0.3 or self._blocked(x, y) or not self._free(x, y, mind):
            return False
        self.counts[kind] = self.counts.get(kind, 0) + 1
        pid = "%s_%04d" % (kind, self.counts[kind])
        p = {"id": pid, "kind": kind, "pos": [_r(x), _r(y), _r(zz, 2)], "yaw_deg": _r(math.degrees(yaw)), "variant": variant}
        if extra:
            p.update(extra)
        self.props.append(p)
        gx, gy = int(x // 6), int(y // 6)
        self.cell.setdefault((gx, gy), []).append((x, y, mind))
        return True

    def along(self, pts, kind, spacing, lateral, jitter, variants, rng_chance=1.0, yaw_off=0.0, mind=3.0, both_sides=True):
        n_added = 0
        rng = self.rng
        for i in range(len(pts) - 1):
            ax, ay = pts[i]
            bx, by = pts[i + 1]
            ln = math.hypot(bx - ax, by - ay)
            if ln < 1e-6:
                continue
            ux, uy = (bx - ax) / ln, (by - ay) / ln
            vx, vy = -uy, ux
            s = rng.uniform(0, spacing)
            while s < ln:
                if rng.chance(rng_chance):
                    for side in ((-1, 1) if both_sides else (1,)):
                        off = side * lateral + rng.uniform(-jitter, jitter)
                        x = ax + ux * s + vx * off
                        y = ay + uy * s + vy * off
                        yaw = math.atan2(uy, ux) + yaw_off + (math.pi if side < 0 and kind == "car" else 0.0)
                        if self.add(kind, x, y, yaw, rng.choice(variants), mind):
                            n_added += 1
                s += spacing * rng.uniform(0.7, 1.3)
        return n_added


def make_props(layout, terrain, rng, building_polys, buildings):
    P = PropPlacer(terrain, rng.fork("props"), building_polys)
    rr = P.rng
    for road in layout.roads:
        pts = [tuple(p) for p in road["points"]]
        w = road["width"]
        kind = road["kind"]
        # parked / driving cars near both kerbs
        P.along(pts, "car", 24.0 if kind != "promenade" else 60.0, w / 2.0 - 7.0, 2.5, CAR_VARIANTS, 0.85, mind=7.0)
        # a second, inner lane of moving traffic on wide roads
        if w >= 50:
            P.along(pts, "car", 44.0, w / 2.0 - 20.0, 2.0, CAR_VARIANTS, 0.7, mind=7.0)
        # lamp posts on both kerbs
        P.along(pts, "lamp", 38.0, w / 2.0 + 1.5, 0.5, ["single", "double"], 1.0, mind=4.0)
        # street trees
        if kind in ("avenue", "promenade"):
            P.along(pts, "tree", 22.0, w / 2.0 + 5.0, 1.0, TREE_VARIANTS, 0.95, mind=5.0)
            if kind == "avenue":
                P.along(pts, "tree", 26.0, 0.0, 0.8, TREE_VARIANTS, 0.9, mind=5.0, both_sides=False)
        elif kind == "street":
            P.along(pts, "tree", 34.0, w / 2.0 + 5.0, 1.0, TREE_VARIANTS, 0.6, mind=5.0)
    # plaza: ring of trees and benches
    plaza = next(b for b in layout.blocks if b["kind"] == "plaza")
    xs = [p[0] for p in plaza["polygon"]]
    ys = [p[1] for p in plaza["polygon"]]
    cx, cy = sum(xs) / 4.0, sum(ys) / 4.0
    for k in range(36):
        a = 2 * math.pi * k / 36
        P.add("tree", cx + math.cos(a) * 95.0, cy + math.sin(a) * 52.0, a, rr.choice(TREE_VARIANTS), 5.0)
    for k in range(10):
        a = 2 * math.pi * k / 10
        P.add("bench", cx + math.cos(a) * 60.0, cy + math.sin(a) * 33.0, a + math.pi / 2, "bench_a", 3.0)
    # empty reserved block parts: a few trees (park-like) around the tower
    tower = next(b for b in buildings if b.get("hero_kind") == "glass_tower")
    tp = [tuple(p) for p in tower["footprint"]]
    tx = sum(p[0] for p in tp) / 4.0
    ty = sum(p[1] for p in tp) / 4.0
    for k in range(24):
        a = 2 * math.pi * k / 24
        P.add("tree", tx + math.cos(a) * 52.0, ty + math.sin(a) * 52.0, a, rr.choice(TREE_VARIANTS), 5.0)
    # scattered trees in lot yards
    for blk in layout.blocks:
        if blk["kind"] != "block":
            continue
        poly = [tuple(p) for p in blk["polygon"]]
        for _ in range(7):
            u, v = rr.random(), rr.random()
            c = layout.bilinear(poly, u, v)
            P.add("tree", c[0], c[1], rr.uniform(0, 6.28), rr.choice(TREE_VARIANTS), 6.0)
    return P.props
