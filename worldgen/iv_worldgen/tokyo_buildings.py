"""Buildings of the Tokyo style (TASK-015): ten hero objects with structure graphs where applicable and 150-260 generic lots
(apartment towers, office towers, low shops, parking, a temple). Inherits the helpers of the v1 generator."""
import math

from . import structure as S
from . import tokyo_span as SP
from .buildings import BuildingGen, _poly_json, _r
from .geom import area, centroid, dist_point_polyline, norm, point_in_poly, rect_poly, rot
from .tokyo_layout import DECK_Z, EXPRESSWAY_W, PLAZA_BOULEVARD

FACADES = {
    "apartment_tower": ["balcony_grid", "plaster_balcony", "tile_panel"],
    "office_tower": ["glass_curtain", "concrete_grid", "metal_panel"],
    "low_shop": ["signage_strip", "shutter_front", "brick"],
    "parking": ["open_deck", "concrete_ribbed"],
    "temple": ["wood_red"],
}
PIER_Z = 2.8                      # reclaimed pier / quay level


def circle_poly(cx, cy, r, n=24):
    return [(cx + math.cos(2 * math.pi * k / n) * r, cy + math.sin(2 * math.pi * k / n) * r) for k in range(n)]


class TokyoBuildingGen(BuildingGen):
    def __init__(self, layout, terrain, rng):
        super().__init__(layout, terrain, rng)
        self.sc_centre = layout.scramble_centre()
        self.quay = None
        self.ramps = []

    # ---- hero helpers ------------------------------------------------------------------------------------------------
    def _hero(self, kind, name, building_type, facade, fp, height, floors, base_z, yaw, block_id=None, district="downtown", **extra):
        b = {"id": "hero_" + kind, "type": "hero", "hero_kind": kind, "name": name, "block_id": block_id, "district": district, "building_type": building_type,
             "facade_style": facade, "footprint": _poly_json(fp), "height": _r(height), "floors": floors, "base_z": _r(base_z), "yaw_deg": _r(math.degrees(yaw))}
        b.update(extra)
        return self._add(b)

    def hero_glass_tower(self):
        blk = self.L.sites["glass_tower_site"]
        c, w, h, yaw = self._block_center(blk)
        side = min(62.0, w - 26.0, h - 26.0)
        fp = rect_poly(c[0], c[1], side, side, yaw)
        floors = 55
        psi, hu, hv = self._frame_toward(c, yaw, side, side)
        st, _ = S.build_rect_structure("glass_tower", c, psi, hu, hv, self._ground(fp), floors, self.rng, weak_tiers=[(3, 0.0), (2, math.pi / 2)], floor_area=side * side)
        self.reserved[blk["id"]] = "glass_tower"
        return self._hero("glass_tower", "Meridian Glass Tower", "office_tower", "glass_curtain", fp, floors * S.FLOOR_H, floors, self._ground(fp), yaw, blk["id"], structure=st)

    def hero_tower_lattice(self):
        blk = self.L.sites["tower_lattice_site"]
        c, w, h, yaw = self._block_center(blk)
        side = min(64.0, w - 24.0, h - 24.0)
        fp = rect_poly(c[0], c[1], side, side, yaw)
        floors = 83                                           # 333 m
        psi, hu, hv = self._frame_toward(c, yaw, side, side)
        st, _ = S.build_rect_structure("tower_lattice", c, psi, hu, hv, self._ground(fp), floors, self.rng, weak_tiers=[(3, 0.0)], floor_area=side * side * 0.12)
        self.reserved[blk["id"]] = "tower_lattice"
        parts = [{"kind": "observation_deck", "z": 150.0, "radius": 17.0}, {"kind": "observation_deck", "z": 250.0, "radius": 10.0},
                 {"kind": "mast", "from_z": 280.0, "to_z": 333.0, "radius": 2.5}, {"kind": "paint", "scheme": "red_white_bands"}]
        return self._hero("tower_lattice", "Crimson Lattice Tower", "landmark", "lattice_red_white", fp, 333.0, floors, self._ground(fp), yaw, blk["id"], structure=st, parts=parts)

    def hero_twin_tower_hall(self):
        blk = self.L.sites["twin_hall_site"]
        c, w, h, yaw = self._block_center(blk)
        pw, pd = min(w - 18.0, 124.0), min(h - 18.0, 84.0)
        fp = rect_poly(c[0], c[1], pw, pd, yaw)
        ca = (c[0] + rot((-pw / 4.0, 0.0), yaw)[0], c[1] + rot((-pw / 4.0, 0.0), yaw)[1])
        cb = (c[0] + rot((pw / 4.0, 0.0), yaw)[0], c[1] + rot((pw / 4.0, 0.0), yaw)[1])
        bs = min(36.0, pd - 14.0)
        floors = 60
        g = self._ground(fp)
        psi, hu, hv = self._frame_toward(ca, yaw, bs, bs)
        sta, _ = S.build_rect_structure("twin_a", ca, psi, hu, hv, g, floors, self.rng, weak_tiers=[(3, 0.0)], floor_area=bs * bs)
        psi2, hu2, hv2 = self._frame_toward(cb, yaw, bs, bs)
        stb, _ = S.build_rect_structure("twin_b", cb, psi2, hu2, hv2, g, floors, self.rng, weak_tiers=[(3, 0.0)], floor_area=bs * bs)
        parts = [{"kind": "podium", "height": 12.0},
                 {"kind": "body", "id": "twin_a", "footprint": _poly_json(rect_poly(ca[0], ca[1], bs, bs, yaw)), "height": 240.0, "structure": sta},
                 {"kind": "body", "id": "twin_b", "footprint": _poly_json(rect_poly(cb[0], cb[1], bs, bs, yaw)), "height": 240.0, "structure": stb}]
        self.reserved[blk["id"]] = "twin_hall"
        return self._hero("twin_tower_hall", "Twin Tower City Hall", "landmark", "concrete_grid", fp, 240.0, floors, g, yaw, blk["id"], district="civic", parts=parts)

    def hero_brick_station(self):
        blk = next(b for b in self.L.blocks if b["col"] == 6 and b["row"] == 1)
        c, w, h, yaw = self._block_center(blk)
        length = 300.0
        fp = rect_poly(c[0], c[1], length, 40.0, yaw)
        floors = 5
        psi, hu, hv = self._frame_toward(c, yaw, length, 40.0)
        st, _ = S.build_rect_structure("brick_station", c, psi, hu, hv, self._ground(fp), floors, self.rng, weak_tiers=[(1, 0.0)], floor_area=length * 40.0 * 0.7, n_tiers=3)
        parts = []
        for k, dx in enumerate((-120.0, 0.0, 120.0)):
            p = rot((dx, 0.0), yaw)
            parts.append({"kind": "dome", "pos": [_r(c[0] + p[0], 1), _r(c[1] + p[1], 1)], "radius": 11.0 if dx == 0 else 8.0, "height": 38.0 if dx == 0 else 30.0})
        self.reserved[blk["id"]] = "brick_station"
        return self._hero("brick_station", "Red Brick Terminal", "station", "brick_red", fp, 38.0, floors, self._ground(fp), yaw, blk["id"], district="civic", structure=st, parts=parts)

    def hero_sphere_building(self):
        x = -330.0
        t = self.T
        yc = t.coast_y(x) - 40.0
        r = 24.0
        podium = circle_poly(x, yc, 30.0, 24)
        floors = 15
        st, _ = S.build_rect_structure("sphere_building", (x, yc), 0.0, r, r, PIER_Z, floors, self.rng, ring=True, weak_tiers=[(1, 0.0)], floor_area=math.pi * r * r * 0.5, n_tiers=3)
        parts = [{"kind": "sphere", "center": [_r(x, 1), _r(yc, 1), PIER_Z + 6.0 + r], "radius": r}, {"kind": "podium", "height": 6.0}, {"kind": "antenna", "height": 14.0}]
        return self._hero("sphere_building", "Harbour Sphere", "landmark", "sphere_metal", podium, 6.0 + 2 * r, floors, PIER_Z, 0.0, None, district="civic", structure=st, parts=parts)

    def hero_port_crane(self):
        x = 200.0
        t = self.T
        y = t.coast_y(x) - 18.0
        fp = rect_poly(x, y, 40.0, 24.0, 0.0)
        floors = 17
        st, _ = S.build_rect_structure("port_crane", (x, y), math.pi, 20.0, 12.0, PIER_Z, floors, self.rng, weak_tiers=[(1, 0.0)], floor_area=40.0 * 24.0 * 0.5)
        quay = [(x - 70.0, y - 26.0), (x + 70.0, y - 26.0), (x + 70.0, y + 26.0), (x - 70.0, y + 26.0)]
        self.quay = quay
        return self._hero("port_crane", "Quay Gantry Crane", "crane", "corrugated_metal", fp, 95.0, floors, PIER_Z, math.pi, None, district="industrial", structure=st,
                          parts=[{"kind": "boom", "from": [_r(x, 1), _r(y, 1)], "to": [_r(x, 1), _r(y - 85.0, 1)], "height": 70.0}])

    def hero_temple(self):
        blk = self.L.sites["temple_site"]
        c, w, h, yaw = self._block_center(blk)
        nd = self._nearest_road_dir(c)
        # the temple stands in the middle, the gate between it and the nearest street
        tfp = rect_poly(c[0] - nd[0] * 8.0, c[1] - nd[1] * 8.0, 34.0, 26.0, yaw)
        gate_c = (c[0] + nd[0] * (min(w, h) / 2.0 - 16.0), c[1] + nd[1] * (min(w, h) / 2.0 - 16.0))
        gyaw = math.atan2(nd[1], nd[0]) + math.pi / 2.0
        gfp = rect_poly(gate_c[0], gate_c[1], 13.0, 5.5, gyaw)
        self.reserved[blk["id"]] = "temple"
        self.buildings.append({"id": "tmp_temple", "type": "generic", "block_id": blk["id"], "district": "residential", "building_type": "temple", "facade_style": "wood_red",
                               "footprint": _poly_json(tfp), "height": 14.0, "floors": 3, "base_z": _r(self._ground(tfp)), "yaw_deg": _r(math.degrees(yaw))})
        return self._hero("temple_gate", "Thunder Gate", "landmark", "wood_red", gfp, 12.0, 3, self._ground(gfp), gyaw, blk["id"], district="residential",
                          parts=[{"kind": "pillar", "count": 4, "height": 10.0}, {"kind": "lantern", "radius": 1.6, "height": 4.0}, {"kind": "paint", "scheme": "vermilion"}])

    def hero_expressway(self):
        t = self.T
        emb = list(self.L.embankment_pts)
        emb[0] = (-788.0, emb[0][1] + (emb[1][1] - emb[0][1]) * 12.0 / 80.0)          # keep the whole deck inside the arena
        emb[-1] = (788.0, emb[-1][1] - (emb[-1][1] - emb[-2][1]) * 12.0 / 80.0)
        samples, total = SP.sample_polyline(emb, 40.0)
        gz = sum(t.height(s[0], s[1]) for s in samples) / len(samples)
        deck_z = gz + DECK_Z
        n = len(samples)
        wp = max(1, n // 2 - 3)
        st, _ = SP.build_polyline_span_structure("expressway", samples, lambda x, y: t.height(x, y), deck_z, EXPRESSWAY_W, wp)
        fp = SP.deck_polygon(samples, EXPRESSWAY_W)
        # two ramps down the first and the last vertical street (a descending ribbon along the street)
        ramps = []
        for k, (xc, w, kind, name) in enumerate((self.L.vlines[0], self.L.vlines[-1])):
            y0 = self.L.road_by_id(self.L.embankment)["points"]
            ex = min(y0, key=lambda p: abs(p[0] - xc))
            pts = []
            for i in range(8):
                yy = ex[1] + 24.0 + i * 18.0
                pts.append([_r(xc + (6.0 if k == 0 else -6.0), 1), _r(yy, 1), _r(deck_z - (deck_z - t.height(xc, yy)) * i / 7.0, 2)])
            ramps.append({"kind": "ramp", "width": 12.0, "points": pts})
        self.ramps = ramps
        parts = ramps + [{"kind": "pylons", "style": "T", "spacing": 40.0, "count": n}, {"kind": "carriageways", "count": 2, "width_each": 12.0, "median": 2.0}]
        return self._hero("expressway", "Shuto Expressway", "overpass", "concrete_ribbed", fp, DECK_Z + 2.0, 1, gz, math.atan2(samples[n // 2][3], samples[n // 2][2]), None,
                          deck_z=_r(deck_z), length=_r(total, 1), width=EXPRESSWAY_W, structure=st, parts=parts)

    def hero_suspension_bridge(self):
        t = self.T
        x0, x1, y = 330.0, 790.0, 105.0
        samples, total = SP.sample_polyline([(x0, y), (x1, y)], 57.5)
        n = len(samples)
        width = 22.0
        deck_z = 40.0
        wp = 2
        st, _ = SP.build_polyline_span_structure("suspension_bridge", samples, lambda px, py: t.height(px, py), deck_z, width, wp)
        fp = SP.deck_polygon(samples, width)
        px = [samples[2][0], samples[n - 3][0]]
        parts = []
        for xx in px:
            parts.append({"kind": "pylon", "pos": [_r(xx, 1), y], "height": 90.0, "top_z": 90.0, "width": 14.0})
        for side in (-1, 1):
            pts = []
            a, b = px
            for k in range(25):
                f = k / 24.0
                xx = x0 + (x1 - x0) * f
                # anchor - tower tops - catenary sag between the towers
                if xx <= a:
                    zz = 12.0 + (90.0 - 12.0) * (xx - x0) / max(1e-6, a - x0)
                elif xx >= b:
                    zz = 90.0 - (90.0 - 12.0) * (xx - b) / max(1e-6, x1 - b)
                else:
                    u = (xx - a) / (b - a)
                    zz = 90.0 - 64.0 * 4.0 * u * (1.0 - u)
                pts.append([_r(xx, 1), _r(y + side * (width / 2.0 + 1.5), 1), _r(zz, 1)])
            parts.append({"kind": "main_cable", "points": pts})
        parts.append({"kind": "hangers", "spacing": 12.0})
        return self._hero("suspension_bridge", "Harbour Suspension Bridge", "overpass", "steel_white", fp, 90.0, 1, t.height(samples[n // 2][0], y), 0.0, None, deck_z=deck_z,
                          length=_r(total, 1), width=width, structure=st, parts=parts)

    def hero_scramble_crossing(self):
        c = self.sc_centre
        fp = rect_poly(c[0], c[1], 80.0, 80.0, 0.0)
        # diagonal crosswalks + the four edge crosswalks
        hw = 40.0
        cw = []
        for (a, b) in (((-hw, -hw), (hw, hw)), ((-hw, hw), (hw, -hw)), ((-hw, -hw), (hw, -hw)), ((hw, -hw), (hw, hw)), ((hw, hw), (-hw, hw)), ((-hw, hw), (-hw, -hw))):
            cw.append({"kind": "crosswalk", "from": [_r(c[0] + a[0], 1), _r(c[1] + a[1], 1)], "to": [_r(c[0] + b[0], 1), _r(c[1] + b[1], 1)], "width": 6.0})
        # screen walls on the four corner buildings (video-wall polygons, no text)
        screens = []
        for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
            corner = (c[0] + sx * hw, c[1] + sy * hw)
            best = None
            for b in self.buildings:
                if b["type"] != "generic" or b["height"] < 40.0:
                    continue
                cc = centroid([tuple(p) for p in b["footprint"]])
                d = math.hypot(cc[0] - corner[0], cc[1] - corner[1])
                if cc[0] * 0 + (cc[0] - c[0]) * sx < 0 or (cc[1] - c[1]) * sy < 0:
                    continue
                if best is None or d < best[0]:
                    best = (d, b)
            if best is None:
                continue
            b = best[1]
            poly = [tuple(p) for p in b["footprint"]]
            edge = min(range(len(poly)), key=lambda i: math.hypot((poly[i][0] + poly[(i + 1) % len(poly)][0]) / 2.0 - c[0], (poly[i][1] + poly[(i + 1) % len(poly)][1]) / 2.0 - c[1]))
            a, bb = poly[edge], poly[(edge + 1) % len(poly)]
            top = min(b["height"] - 4.0, 46.0)
            screens.append({"kind": "screen_wall", "building_id": b["id"], "a": [_r(a[0], 1), _r(a[1], 1)], "b": [_r(bb[0], 1), _r(bb[1], 1)], "z0": 10.0, "z1": _r(top, 1),
                            "style": "video_wall", "emissive": True})
        return self._hero("scramble_crossing", "Scramble Crossing", "landmark", "video_walls", fp, 10.0, 1, self._ground(fp), 0.0, None, parts=cw + screens)

    # ---- generic lots --------------------------------------------------------------------------------------------------
    def _lot_type(self, district, core, prev_tall):
        rng = self.rng
        if district == "downtown":
            items = [("office_tower", 3.4), ("apartment_tower", 2.8), ("low_shop", 2.2), ("parking", 0.8)]
        elif district == "residential":
            items = [("apartment_tower", 5.0), ("low_shop", 3.0), ("office_tower", 1.0), ("parking", 1.0)]
        elif district == "civic":
            items = [("low_shop", 4.0), ("office_tower", 3.0), ("parking", 2.0), ("apartment_tower", 1.0)]
        else:
            items = [("apartment_tower", 3.5), ("office_tower", 2.0), ("low_shop", 3.5), ("parking", 1.0)]
        if prev_tall:                                         # checkerboard: a tall neighbour makes a low building likely
            items = [(k, (w * 2.4 if k in ("low_shop", "parking") else w * 0.7)) for k, w in items]
        return rng.weighted(items)

    HEIGHTS = {"apartment_tower": (40.0, 120.0), "office_tower": (80.0, 200.0), "low_shop": (12.0, 30.0), "parking": (20.0, 36.0)}

    def _height(self, btype, core):
        """Height in the range of the type (taller towards the scramble); returned already snapped to whole storeys inside the range."""
        rng = self.rng
        lo, hi = self.HEIGHTS[btype]
        if btype in ("apartment_tower", "office_tower"):
            h = lo + (hi - lo) * min(1.0, rng.random() ** 1.3 * (0.55 + 0.45 * core) * 1.25)
        else:
            h = rng.uniform(lo, hi)
        fl = max(int(math.ceil(lo / S.FLOOR_H)), min(int(hi // S.FLOOR_H), int(round(h / S.FLOOR_H))))
        return fl * S.FLOOR_H

    def _generic_for_block(self, blk):
        rng = self.rng
        poly, w, h, yaw = self.L.block_frame(blk)
        district = blk["district"]
        nu = max(1, int(round(w / rng.uniform(34.0, 48.0))))
        nv = max(1, int(round(h / rng.uniform(38.0, 54.0))))
        prev_tall = False
        for j in range(nv):
            for i in range(nu):
                u0, u1 = i / nu, (i + 1) / nu
                v0, v1 = j / nv, (j + 1) / nv
                su, sv = rng.uniform(3.5, 5.5), rng.uniform(3.5, 5.5)
                bw = (u1 - u0) * w - 2 * su
                bd = (v1 - v0) * h - 2 * sv
                if bw < 15.0 or bd < 15.0:
                    continue
                c = self.L.bilinear(poly, (u0 + u1) / 2.0, (v0 + v1) / 2.0)
                core = max(0.0, 1.0 - math.hypot(c[0] - self.sc_centre[0], c[1] - self.sc_centre[1]) / 900.0)
                btype = self._lot_type(district, core, prev_tall)
                if btype == "apartment_tower":
                    bw, bd = min(bw, rng.uniform(18.0, 28.0)), min(bd, rng.uniform(20.0, 34.0))
                elif btype == "office_tower":
                    bw, bd = min(bw, 44.0), min(bd, 48.0)
                elif rng.chance(0.18):
                    bw *= rng.uniform(0.7, 0.9)
                if bw < 15.0 or bd < 15.0:
                    continue
                fp = rect_poly(c[0], c[1], bw, bd, yaw)
                for _ in range(5):
                    if self._road_clearance(fp) >= 3.0:
                        break
                    bw *= 0.93
                    bd *= 0.93
                    fp = rect_poly(c[0], c[1], bw, bd, yaw)
                if self._road_clearance(fp) < 3.0 or bw < 14.0 or bd < 14.0:
                    continue
                height = self._height(btype, core)
                floors = int(round(height / S.FLOOR_H))
                prev_tall = height >= 60.0
                b = {"id": self._next_id(), "type": "generic", "block_id": blk["id"], "district": district, "building_type": btype, "facade_style": rng.choice(FACADES[btype]),
                     "footprint": _poly_json(fp), "height": height, "floors": floors, "base_z": _r(self._ground(fp)), "yaw_deg": _r(math.degrees(yaw))}
                b["_structure_spec"] = (c, yaw, bw, bd, fp)
                self._add(b)

    def attach_structures(self):
        gen = [b for b in self.buildings if b["type"] == "generic" and b["id"] != "tmp_temple"]
        k = 0
        for b in gen:
            spec = b.pop("_structure_spec", None)
            if spec is None or b["floors"] < 5:
                continue
            k += 1
            if k % 3 != 1:
                continue
            c, yaw, bw, bd, fp = spec
            psi, hu, hv = self._frame_toward(c, yaw, bw, bd)
            st, _ = S.build_rect_structure("s_" + b["id"], c, psi, hu, hv, b["base_z"], b["floors"], self.rng, floor_area=bw * bd)
            b["structure"] = st
        for b in self.buildings:
            b.pop("_structure_spec", None)

    # ---- driver --------------------------------------------------------------------------------------------------------
    def generate(self):
        self.hero_glass_tower()
        self.hero_tower_lattice()
        self.hero_twin_tower_hall()
        self.hero_brick_station()
        self.hero_temple()
        for blk in self.L.blocks:
            if blk["kind"] == "plaza" or blk["id"] in self.reserved:
                continue
            if blk["kind"] == "site" and blk["col"] == 6:
                self._generic_for_site(blk)
                continue
            self._generic_for_block(blk)
        self.attach_structures()
        self.hero_scramble_crossing()
        self.hero_sphere_building()
        self.hero_port_crane()
        self.hero_expressway()
        self.hero_suspension_bridge()
        n = 0
        for b in self.buildings:
            if b["id"] == "tmp_temple":
                b["id"] = "bld_temple"
            elif b["type"] == "generic":
                n += 1
                b["id"] = "bld_%03d" % n
        # screen walls reference the final ids
        return self.buildings

    def _generic_for_site(self, blk):
        """The 320 m station column: the terminal (hero) takes the row-1 block; the other three blocks get low shops / offices around the rail yard."""
        self._generic_for_block(blk)
