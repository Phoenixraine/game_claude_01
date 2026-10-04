"""Buildings of the cyberpunk layer (TASK-019): the 10 heroes of TASK-015, glass towers with curtain-wall parameters round the battle plaza,
shopfront rows along the pedestrian street, destruction data for every building. Free of buildings: the battle plaza."""
import math

from . import structure as S
from .buildings import _poly_json, _r
from .cyber_data import PALETTE, TOWER_PRESETS, destruction_for
from .geom import centroid, point_in_poly, polys_intersect, rect_poly
from .tokyo_buildings import FACADES, TokyoBuildingGen

FACADES = dict(FACADES, glass_tower=["glass_curtain"], shopfront_row=["shopfront_neon"])
HERO_DESTRUCTION_KEY = {"glass_tower": "glass_tower", "tower_lattice": "landmark", "twin_tower_hall": "office_tower", "brick_station": "station", "sphere_building": "landmark",
                        "temple_gate": "temple", "port_crane": "crane", "expressway": "overpass", "suspension_bridge": "overpass"}
R_FRAME = 235.0                      # towers frame the plaza within this distance of its centre


def _rgb_jitter(c, rng, d=10):
    return [max(0, min(255, int(v + rng.uniform(-d, d)))) for v in c]


class CyberBuildingGen(TokyoBuildingGen):
    def __init__(self, layout, terrain, rng):
        super().__init__(layout, terrain, rng)
        self.plaza_poly = [tuple(p) for p in layout.plaza["polygon"]]
        self.plaza_c = tuple(layout.plaza["center"])
        self.preset_order = []
        self.glass_count = 0
        self.shop_rows = []

    # ---- glass towers --------------------------------------------------------------------------------------------------------
    def _next_preset(self):
        if not self.preset_order:
            self.preset_order = list(range(len(TOWER_PRESETS)))
            self.rng.shuffle(self.preset_order)
        return TOWER_PRESETS[self.preset_order.pop()]

    def _facade_glass(self, preset, floors, bw, bd, c):
        r = self.rng
        lo, hi = preset["mullion_spacing_m"]
        refl = preset["reflectivity"]
        setbacks = []
        for sb in preset["setbacks"]:
            e = {"from_floor": max(1, int(floors * sb["at"])), "inset_m": sb["inset_m"]}
            if "side" in sb:
                e["side"] = sb["side"]
            setbacks.append(e)
        lights = []
        for k in range(preset["rooftop_lights"]):
            ang = 2 * math.pi * k / preset["rooftop_lights"]
            lights.append({"pos": [_r(math.cos(ang) * bw * 0.38, 1), _r(math.sin(ang) * bd * 0.38, 1)], "color": list(PALETTE["red"] if k % 3 == 0 else PALETTE["amber"] if k % 3 == 1 else PALETTE["cyan"]),
                           "kind": "beacon" if k % 2 == 0 else "steady", "blink_hz": _r(r.uniform(0.4, 1.1), 2)})
        return {"preset": preset["id"], "mullion_spacing_m": _r(r.uniform(lo, hi), 2), "floor_height_m": S.FLOOR_H, "tint": _rgb_jitter(preset["tint"], r, 8),
                "reflectivity": _r(r.uniform(refl[0], refl[1]), 2), "crown": preset["crown"], "setbacks": setbacks,
                "curtain_wall": {"panel_w": preset["panel_w"], "panel_h": S.FLOOR_H, "spandrel_ratio": preset["spandrel_ratio"]},
                "emissive_floors": {"pattern": preset["emissive"]["pattern"], "density": preset["emissive"]["density"], "color_seed": r.next_u32() & 0xFFFF},
                "rooftop_lights": lights}

    def _make_glass(self, blk, district, c, bw, bd, yaw, fp, core):
        r = self.rng
        preset = self._next_preset()
        lo, hi = preset["height_range"]
        h = lo + (hi - lo) * min(1.0, r.random() ** 0.8 * (0.6 + 0.5 * core))
        floors = max(int(math.ceil(120.0 / S.FLOOR_H)), min(int(hi // S.FLOOR_H), int(round(h / S.FLOOR_H))))
        b = {"id": self._next_id(), "type": "generic", "block_id": blk["id"], "district": district, "building_type": "glass_tower", "facade_style": "glass_curtain",
             "footprint": _poly_json(fp), "height": floors * S.FLOOR_H, "floors": floors, "base_z": _r(self._ground(fp)), "yaw_deg": _r(math.degrees(yaw)),
             "facade": self._facade_glass(preset, floors, bw, bd, c)}
        b["_structure_spec"] = (c, yaw, bw, bd, fp)
        self.glass_count += 1
        self._add(b)

    # ---- generic lots with the plaza kept free ---------------------------------------------------------------------------------
    def _generic_for_block(self, blk):
        if self.L.strip and blk["col"] == self.L.strip_col and blk["row"] == 0:
            self._shop_lots(blk)
            return
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
                dp = math.hypot(c[0] - self.plaza_c[0], c[1] - self.plaza_c[1])
                glass = (dp <= R_FRAME and min(bw, bd) >= 24.0 and rng.chance(0.82)) or (district == "downtown" and core > 0.35 and min(bw, bd) >= 30.0 and rng.chance(0.12))
                if glass:
                    bw, bd = min(bw, 52.0), min(bd, 52.0)
                    btype = "glass_tower"
                else:
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
                if self._in_plaza(fp):
                    continue
                if btype == "glass_tower":
                    if min(bw, bd) < 22.0:
                        continue
                    self._make_glass(blk, district, c, bw, bd, yaw, fp, core)
                    prev_tall = True
                    continue
                height = self._height(btype, core)
                floors = int(round(height / S.FLOOR_H))
                prev_tall = height >= 60.0
                b = {"id": self._next_id(), "type": "generic", "block_id": blk["id"], "district": district, "building_type": btype, "facade_style": rng.choice(FACADES[btype]),
                     "footprint": _poly_json(fp), "height": height, "floors": floors, "base_z": _r(self._ground(fp)), "yaw_deg": _r(math.degrees(yaw))}
                b["_structure_spec"] = (c, yaw, bw, bd, fp)
                self._add(b)

    def _in_plaza(self, fp):
        return polys_intersect(fp, self.plaza_poly) or point_in_poly(fp[0], self.plaza_poly) or point_in_poly(self.plaza_c, fp)

    # ---- the shop rows of the pedestrian street ------------------------------------------------------------------------------------
    def _shop_lots(self, blk):
        rng = self.rng
        poly, w, h, yaw = self.L.block_frame(blk)
        xs = (self.L.strip["x0"] + self.L.strip["x1"]) / 2.0
        cx = centroid(poly)[0]
        street_on_plus = cx < xs                        # the pedestrian street lies on the +x side of this block
        n = max(1, int(h / rng.uniform(9.5, 13.5)))
        for j in range(n):
            v0, v1 = j / n, (j + 1) / n
            front = (v1 - v0) * h - 1.4
            depth = rng.uniform(20.0, 32.0)
            if front < 7.0 or depth > w - 4.0:
                continue
            u = (w - depth / 2.0 - 0.8) / w if street_on_plus else (depth / 2.0 + 0.8) / w
            c = self.L.bilinear(poly, u, (v0 + v1) / 2.0)
            fp = rect_poly(c[0], c[1], depth, front, yaw)
            if self._road_clearance(fp) < 0.4 or self._in_plaza(fp):
                continue
            floors = rng.weighted([(3, 2.0), (4, 3.0), (5, 3.0), (6, 2.0)])
            b = {"id": self._next_id(), "type": "generic", "block_id": blk["id"], "district": "mixed", "building_type": "shopfront_row", "facade_style": "shopfront_neon",
                 "footprint": _poly_json(fp), "height": floors * S.FLOOR_H, "floors": floors, "base_z": _r(self._ground(fp)), "yaw_deg": _r(math.degrees(yaw)),
                 "facade": {"floors": floors, "bay_width_m": _r(front, 2), "street_side": "east" if street_on_plus else "west",
                            "signage_strip": {"height_m": _r(rng.uniform(0.9, 1.6), 2), "emissive": True},
                            "awning": rng.chance(0.55), "shutter": rng.chance(0.25), "shopfront_glass_ratio": _r(rng.uniform(0.55, 0.85), 2),
                            "vertical_signs": rng.randint(1, 3), "crowd_spawn": True}}
            b["_structure_spec"] = (c, yaw, depth, front, fp)
            self._add(b)
            # a taller building behind the shop (the rest of the block): apartments / low offices
            rem = w - depth - 3.0
            if rem >= 17.0 and rng.chance(0.55):
                bu = (w - depth - 0.8 - rem / 2.0 - 0.8) / w if street_on_plus else (depth + 0.8 + rem / 2.0 + 0.8) / w
                c2 = self.L.bilinear(poly, bu, (v0 + v1) / 2.0)
                fp2 = rect_poly(c2[0], c2[1], rem - 2.0, front, yaw)
                if self._road_clearance(fp2) >= 2.5 and not self._in_plaza(fp2):
                    fl2 = rng.randint(8, 18)
                    self._add({"id": self._next_id(), "type": "generic", "block_id": blk["id"], "district": "mixed", "building_type": "apartment_tower", "facade_style": "balcony_grid",
                               "footprint": _poly_json(fp2), "height": fl2 * S.FLOOR_H, "floors": fl2, "base_z": _r(self._ground(fp2)), "yaw_deg": _r(math.degrees(yaw)),
                               "_structure_spec": (c2, yaw, rem - 2.0, front, fp2)})

    # ---- structures: every glass tower has a graph ------------------------------------------------------------------------------------
    def attach_structures(self):
        gen = [b for b in self.buildings if b["type"] == "generic" and b["id"] != "tmp_temple"]
        k = 0
        for b in gen:
            spec = b.pop("_structure_spec", None)
            if spec is None or b["floors"] < 5:
                continue
            k += 1
            if b["building_type"] != "glass_tower" and k % 3 != 1:
                continue
            c, yaw, bw, bd, fp = spec
            psi, hu, hv = self._frame_toward(c, yaw, bw, bd)
            b["structure"] = S.build_rect_structure("s_" + b["id"], c, psi, hu, hv, b["base_z"], b["floors"], self.rng, floor_area=bw * bd)[0]
        for b in self.buildings:
            b.pop("_structure_spec", None)

    # ---- driver ------------------------------------------------------------------------------------------------------------------------
    def generate(self):
        bs = super().generate()
        for b in bs:
            if b["type"] == "hero":
                key = HERO_DESTRUCTION_KEY.get(b["hero_kind"])
                if key is None:
                    continue
            else:
                key = b["building_type"]
            b["destruction"] = destruction_for(key, self.rng.fork(b["id"]))
        return bs
