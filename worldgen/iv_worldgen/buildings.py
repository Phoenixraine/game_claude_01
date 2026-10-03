"""Generic buildings (lots inside blocks) and the six hero buildings with structure graphs."""
import math

from . import structure as S
from .geom import (area, bbox, centroid, dist_point_polyline, nearest_on_segment, norm, point_in_poly, polys_intersect, rect_poly, rot)

FACADES = {
    "office": ["glass_curtain", "concrete_grid", "metal_panel"],
    "residential": ["brick", "plaster_balcony", "concrete_prefab"],
    "industrial": ["corrugated_metal", "brick_industrial"],
    "parking": ["open_deck", "concrete_ribbed"],
}


def _r(v, n=2):
    return round(v, n)


def _poly_json(poly):
    return [[_r(p[0], 1), _r(p[1], 1)] for p in poly]


class BuildingGen:
    def __init__(self, layout, terrain, rng):
        self.L = layout
        self.T = terrain
        self.rng = rng
        self.buildings = []
        self.reserved = {}      # block id -> hero kind
        self._n = 0

    # --- helpers ----------------------------------------------------------------------------------
    def _block(self, col, row):
        for b in self.L.blocks:
            if b["col"] == col and b["row"] == row and b["kind"] in ("block", "site"):
                return b
        raise KeyError((col, row))

    def _nearest_road_dir(self, p):
        best = (1e18, None)
        for road in self.L.roads:
            pts = road["points"]
            for i in range(len(pts) - 1):
                q = nearest_on_segment(p, pts[i], pts[i + 1])
                d = math.hypot(q[0] - p[0], q[1] - p[1])
                if d < best[0]:
                    best = (d, q)
        q = best[1]
        return norm((q[0] - p[0], q[1] - p[1]))

    def _frame_toward(self, center, yaw, w, d):
        """Pick the structure frame (a multiple of 90 deg from the footprint yaw) whose +v faces the nearest road."""
        n = self._nearest_road_dir(center)
        best = None
        for k in range(4):
            psi = yaw + k * math.pi / 2
            v = (-math.sin(psi), math.cos(psi))
            dot = v[0] * n[0] + v[1] * n[1]
            if best is None or dot > best[0]:
                best = (dot, psi, k)
        _, psi, k = best
        hu, hv = (w / 2.0, d / 2.0) if k % 2 == 0 else (d / 2.0, w / 2.0)
        return psi, hu, hv

    def _road_clearance(self, poly):
        """Smallest margin (m) between the footprint corners and any street edge."""
        worst = 1e18
        for road in self.L.roads:
            line = road["points"]
            for p in poly:
                d = dist_point_polyline(p, line) - road["width"] / 2.0
                if d < worst:
                    worst = d
        return worst

    def _next_id(self, prefix="bld"):
        self._n += 1
        return "%s_%03d" % (prefix, self._n)

    def _ground(self, poly):
        c = centroid(poly)
        return self.T.height(c[0], c[1])

    # --- heroes -----------------------------------------------------------------------------------
    def _block_center(self, block):
        poly, w, h, yaw = self.L.block_frame(block)
        return self.L.bilinear(poly, 0.5, 0.5), w, h, yaw

    def _add(self, b):
        self.buildings.append(b)
        return b

    def hero_glass_tower(self):
        blk = self._block(3, 1)
        c, w, h, yaw = self._block_center(blk)
        fp = rect_poly(c[0], c[1], 62.0, 62.0, yaw)
        floors = 55
        psi, hu, hv = self._frame_toward(c, yaw, 62.0, 62.0)
        st, _ = S.build_rect_structure("glass_tower", c, psi, hu, hv, self._ground(fp), floors, self.rng,
                                       weak_tiers=[(3, 0.0), (2, math.pi / 2)], floor_area=62.0 * 62.0)
        self.reserved[blk["id"]] = "glass_tower"
        return self._add({"id": "hero_glass_tower", "type": "hero", "hero_kind": "glass_tower", "name": "Meridian Glass Tower", "block_id": blk["id"],
                          "district": "downtown", "building_type": "office", "facade_style": "glass_curtain", "footprint": _poly_json(fp),
                          "height": floors * S.FLOOR_H, "floors": floors, "base_z": _r(self._ground(fp)), "yaw_deg": _r(math.degrees(yaw)),
                          "structure": st})

    def hero_stadium(self):
        blk = self._block(1, 1)
        c, w, h, yaw = self._block_center(blk)
        a, b = 102.0, 60.0
        n = 40
        fp = [(c[0] + rot((math.cos(2 * math.pi * k / n) * a, math.sin(2 * math.pi * k / n) * b), yaw)[0],
               c[1] + rot((math.cos(2 * math.pi * k / n) * a, math.sin(2 * math.pi * k / n) * b), yaw)[1]) for k in range(n)]
        floors = 12
        psi, hu, hv = self._frame_toward(c, yaw, 2 * a, 2 * b)
        st, _ = S.build_rect_structure("stadium", c, psi, hu, hv, self._ground(fp), floors, self.rng, ring=True,
                                       weak_tiers=[(1, 0.0)], floor_area=math.pi * a * b * 0.6)
        self.reserved[blk["id"]] = "stadium"
        return self._add({"id": "hero_stadium", "type": "hero", "hero_kind": "stadium", "name": "Harbour Arena", "block_id": blk["id"],
                          "district": "residential", "building_type": "stadium", "facade_style": "concrete_ribbed", "footprint": _poly_json(fp),
                          "height": floors * S.FLOOR_H, "floors": floors, "base_z": _r(self._ground(fp)), "yaw_deg": _r(math.degrees(yaw)),
                          "structure": st})

    def hero_residential(self):
        blk = self._block(4, 3)
        c0, w, h, yaw = self._block_center(blk)
        c = c0
        nroad = self._nearest_road_dir(c)
        # U shape: base toward the nearest road (the collapse side), courtyard opens away from it
        psi, hu, hv = self._frame_toward(c, yaw, 120.0, 140.0)
        ow, od, wing = 2 * hu, 2 * hv, 34.0

        def local_poly():
            return [(-hu, -hv), (hu, -hv), (hu, hv), (-hu, hv)]

        # U in the structure frame: base is the +v strip, wings run toward -v
        pts = [(-hu, hv), (-hu, -hv), (-hu + wing, -hv), (-hu + wing, hv - wing), (hu - wing, hv - wing), (hu - wing, -hv), (hu, -hv), (hu, hv)]
        fp = [(c[0] + rot(p, psi)[0], c[1] + rot(p, psi)[1]) for p in pts]
        com = centroid(fp)
        floors = 18
        inside = lambda p: point_in_poly(p, fp)
        st, _ = S.build_rect_structure("residential_complex", c, psi, hu, hv, self._ground(fp), floors, self.rng, inside=inside,
                                       weak_tiers=[(2, 0.0)], com=com, floor_area=abs(area(fp)), n_tiers=4)
        self.reserved[blk["id"]] = "residential_complex"
        return self._add({"id": "hero_residential_complex", "type": "hero", "hero_kind": "residential_complex", "name": "Courtyard Residences",
                          "block_id": blk["id"], "district": "downtown", "building_type": "residential", "facade_style": "plaster_balcony",
                          "footprint": _poly_json(fp), "height": floors * S.FLOOR_H, "floors": floors, "base_z": _r(self._ground(fp)),
                          "yaw_deg": _r(math.degrees(psi)), "structure": st})

    def hero_power_station(self):
        blk = self._block(5, 1)
        c, w, h, yaw = self._block_center(blk)
        c = (c[0] - 40.0, c[1])
        fp = rect_poly(c[0], c[1], 130.0, 85.0, yaw)
        floors = 10
        psi, hu, hv = self._frame_toward(c, yaw, 130.0, 85.0)
        st, _ = S.build_rect_structure("power_station", c, psi, hu, hv, self._ground(fp), floors, self.rng,
                                       weak_tiers=[(2, 0.0)], floor_area=130.0 * 85.0 * 0.8, n_tiers=4)
        chimneys = []
        for k, dx in enumerate((-30.0, 30.0)):
            p = rot((dx, hv - 15.0), psi)
            chimneys.append({"kind": "chimney", "pos": [_r(c[0] + p[0], 1), _r(c[1] + p[1], 1)], "radius": 6.0, "height": 120.0})
        self.reserved[blk["id"]] = "power_station"
        return self._add({"id": "hero_power_station", "type": "hero", "hero_kind": "power_station", "name": "Eastside Power Station",
                          "block_id": blk["id"], "district": "industrial", "building_type": "industrial", "facade_style": "corrugated_metal",
                          "footprint": _poly_json(fp), "height": floors * S.FLOOR_H, "floors": floors, "base_z": _r(self._ground(fp)),
                          "yaw_deg": _r(math.degrees(yaw)), "parts": chimneys, "hazard": "electrical", "structure": st})

    def hero_port_crane(self):
        blk = self._block(5, 0)
        poly, w, h, yaw = self.L.block_frame(blk)
        x = (poly[0][0] + poly[1][0]) / 2.0 - 60.0
        y = self.T.coast_y(x) + 28.0
        fp = rect_poly(x, y, 40.0, 24.0, 0.0)
        # frame: +v points to the sea (-Y) -> yaw = pi
        psi = math.pi
        floors = 17           # 68 m of legs and machinery house
        st, _ = S.build_rect_structure("port_crane", (x, y), psi, 20.0, 12.0, self._ground(fp), floors, self.rng,
                                       weak_tiers=[(1, 0.0)], floor_area=40.0 * 24.0 * 0.5)
        return self._add({"id": "hero_port_crane", "type": "hero", "hero_kind": "port_crane", "name": "Quay Gantry Crane", "block_id": blk["id"],
                          "district": "industrial", "building_type": "crane", "facade_style": "corrugated_metal", "footprint": _poly_json(fp),
                          "height": 95.0, "floors": floors, "base_z": _r(self._ground(fp)), "yaw_deg": 180.0,
                          "parts": [{"kind": "boom", "from": [_r(x, 1), _r(y, 1)], "to": [_r(x, 1), _r(y - 85.0, 1)], "height": 70.0}],
                          "structure": st})

    def hero_overpass(self):
        xc = [v for v in self.L.vlines if v[2] == "avenue"][1][0]
        p0 = self.L.warp(xc, 600.0)
        q1 = self.L.warp(xc, 1030.0)
        d = norm((q1[0] - p0[0], q1[1] - p0[1]))
        length = 405.0                                          # pitch §17: a 400 m overpass
        p1 = (p0[0] + d[0] * length, p0[1] + d[1] * length)
        width = 26.0
        yaw = math.atan2(p1[1] - p0[1], p1[0] - p0[0])
        fp = rect_poly((p0[0] + p1[0]) / 2.0, (p0[1] + p1[1]) / 2.0, length, width, yaw)
        base = self._ground(fp)
        st, _ = S.build_span_structure("overpass", p0, p1, base, base + 14.0, width, 11, 3)
        return self._add({"id": "hero_overpass", "type": "hero", "hero_kind": "overpass", "name": "Avenue Overpass", "block_id": None,
                          "district": "downtown", "building_type": "overpass", "facade_style": "concrete_ribbed", "footprint": _poly_json(fp),
                          "height": 16.0, "floors": 1, "base_z": _r(base), "deck_z": _r(base + 14.0), "length": _r(length, 1), "width": width,
                          "yaw_deg": _r(math.degrees(yaw)), "structure": st})

    # --- generic buildings ------------------------------------------------------------------------
    def _generic_for_block(self, blk):
        rng = self.rng
        poly, w, h, yaw = self.L.block_frame(blk)
        district = blk["district"]
        nu = 1 if w < 118 else (2 if w < 200 else 3)
        nv = 1 if h < 150 else 2
        if blk["kind"] == "site":
            nu, nv = (3, 1) if w > 250 else (2, 1)
            if h > 170:
                nv = 2
        for i in range(nu):
            for j in range(nv):
                u0, u1 = i / nu, (i + 1) / nu
                v0, v1 = j / nv, (j + 1) / nv
                su = rng.uniform(5.0, 8.0)
                sv = rng.uniform(5.0, 8.0)
                bw = (u1 - u0) * w - 2 * su
                bd = (v1 - v0) * h - 2 * sv
                if bw < 22 or bd < 22:
                    continue
                if rng.chance(0.18):                        # sometimes a smaller building leaves a yard
                    bw *= rng.uniform(0.65, 0.85)
                    bd *= rng.uniform(0.65, 0.85)
                c = self.L.bilinear(poly, (u0 + u1) / 2.0, (v0 + v1) / 2.0)
                fp = rect_poly(c[0], c[1], bw, bd, yaw)
                for _ in range(4):                          # the warped block edge can be a few metres off the street polyline
                    if self._road_clearance(fp) >= 3.0:
                        break
                    bw *= 0.92
                    bd *= 0.92
                    fp = rect_poly(c[0], c[1], bw, bd, yaw)
                if self._road_clearance(fp) < 3.0 or bw < 22 or bd < 22:
                    continue
                self._make_generic(blk, district, c, bw, bd, yaw, fp)

    def _height_for(self, district, c, btype):
        rng = self.rng
        core = (-20.0, 780.0)
        dist = math.hypot(c[0] - core[0], c[1] - core[1])
        falloff = max(0.35, 1.0 - dist / 1100.0)
        if district == "downtown":
            h = rng.uniform(70.0, 190.0)
        elif district == "industrial":
            h = rng.uniform(30.0, 56.0)
        elif district == "residential":
            h = rng.uniform(32.0, 92.0)
        else:
            h = rng.uniform(36.0, 120.0)
        if btype == "parking":
            h = rng.uniform(30.0, 42.0)
        return max(30.0, min(200.0, h * (0.55 + 0.45 * falloff)))

    def _make_generic(self, blk, district, c, bw, bd, yaw, fp):
        rng = self.rng
        if district == "industrial":
            btype = rng.weighted([("industrial", 8), ("parking", 2)])
        elif district == "downtown":
            btype = rng.weighted([("office", 7), ("residential", 2), ("parking", 1)])
        elif district == "residential":
            btype = rng.weighted([("residential", 8.5), ("office", 1), ("parking", 0.5)])
        else:
            btype = rng.weighted([("office", 4), ("residential", 5), ("parking", 1)])
        floors = max(7, int(round(self._height_for(district, c, btype) / S.FLOOR_H)))
        height = floors * S.FLOOR_H
        if height > 200.0:
            floors = 50
            height = 200.0
        bid = self._next_id()
        b = {"id": bid, "type": "generic", "block_id": blk["id"], "district": district, "building_type": btype,
             "facade_style": rng.choice(FACADES[btype]), "footprint": _poly_json(fp), "height": height, "floors": floors,
             "base_z": _r(self._ground(fp)), "yaw_deg": _r(math.degrees(yaw))}
        b["_structure_spec"] = (c, yaw, bw, bd, fp)
        self._add(b)

    def attach_structures(self):
        """Structure graphs for every third generic building (>= 25 % requirement) – deterministic by order."""
        gen = [b for b in self.buildings if b["type"] == "generic"]
        for k, b in enumerate(gen):
            spec = b.pop("_structure_spec", None)
            if spec is None or k % 3 != 0:
                continue
            c, yaw, bw, bd, fp = spec
            psi, hu, hv = self._frame_toward(c, yaw, bw, bd)
            st, _ = S.build_rect_structure("s_" + b["id"], c, psi, hu, hv, b["base_z"], b["floors"], self.rng,
                                           floor_area=bw * bd)
            b["structure"] = st
        for b in gen:
            b.pop("_structure_spec", None)

    # --- driver -----------------------------------------------------------------------------------
    def generate(self):
        self.hero_glass_tower()
        self.hero_stadium()
        self.hero_residential()
        self.hero_power_station()
        self.hero_port_crane()
        self.hero_overpass()
        for blk in self.L.blocks:
            if blk["kind"] == "plaza" or blk["id"] in self.reserved:
                continue
            if blk["kind"] == "site" and blk["col"] == 5 and blk["row"] == 0:
                continue                                    # port yard: containers instead of buildings
            self._generic_for_block(blk)
        self.attach_structures()
        # stable ids: heroes first, generic by creation order; renumber generic sequentially
        n = 0
        for b in self.buildings:
            if b["type"] == "generic":
                n += 1
                b["id"] = "bld_%03d" % n
        return self.buildings
