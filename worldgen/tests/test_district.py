import math
import os
import sys
import tempfile
import unittest

from tests.common import ROOT, district, schema  # noqa: F401  (sets sys.path)

import generate
from iv_worldgen import structure as S, terrain as Tm
from iv_worldgen.geom import angle_between, bbox, dist_point_polyline, dist_to_poly_edges, point_in_poly, polys_intersect
from iv_worldgen.minischema import validate

HERO_KINDS = {"glass_tower", "stadium", "residential_complex", "overpass", "port_crane", "power_station"}


def all_ids(doc):
    ids = []
    for key in ("roads", "blocks", "buildings", "props", "pois", "hazards"):
        ids += [x["id"] for x in doc[key]]
    for b in doc["buildings"]:
        st = b.get("structure")
        if st:
            ids += [c["id"] for c in st["columns"]] + [f["id"] for f in st["floors"]] + [w["id"] for w in st["weak_lines"]]
    infra = doc["infrastructure"]
    ids += [c["id"] for c in infra["port"]["containers"]] + [infra["substation"]["id"], infra["metro"]["id"]]
    ids += [s["id"] for s in infra["metro"]["weak_segments"]] + [s["id"] for s in infra["metro"]["stations"]] + [g["id"] for g in infra["guardrails"]]
    return ids


class Determinism(unittest.TestCase):
    def test_same_seed_same_hash_and_different_seed_differs(self):
        doc1, t1 = generate.build(3)
        doc2, t2 = generate.build(3)
        self.assertEqual(generate.digest(doc1, t1), generate.digest(doc2, t2))
        doc3, t3 = generate.build(4)
        self.assertNotEqual(generate.digest(doc1, t1), generate.digest(doc3, t3))

    def test_cli_writes_identical_files_twice(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            generate.main(["--seed", "5", "--out", a, "--no-preview"])
            generate.main(["--seed", "5", "--out", b, "--no-preview"])
            for name in ("district.json", "heightmap.r16", "district.sha256"):
                with open(os.path.join(a, name), "rb") as fa, open(os.path.join(b, name), "rb") as fb:
                    self.assertEqual(fa.read(), fb.read(), name)


class Schema(unittest.TestCase):
    def test_document_matches_json_schema(self):
        doc, _ = district()
        self.assertEqual(validate(doc, schema()), [])

    def test_validator_rejects_broken_documents(self):
        doc, _ = district()
        bad = dict(doc)
        del bad["roads"]
        self.assertTrue(validate(bad, schema()))
        bad = dict(doc, schema_version=2)
        self.assertTrue(validate(bad, schema()))
        bad = dict(doc, buildings=[dict(doc["buildings"][0], height=900.0)] + doc["buildings"][1:])
        self.assertTrue(validate(bad, schema()))

    def test_agrees_with_jsonschema_package_when_installed(self):
        try:
            import jsonschema
        except ImportError:
            self.skipTest("jsonschema not installed")
        doc, _ = district()
        jsonschema.validate(doc, schema())

    def test_ids_are_unique(self):
        doc, _ = district()
        ids = all_ids(doc)
        self.assertEqual(len(ids), len(set(ids)))


class Layout(unittest.TestCase):
    def test_exactly_six_hero_buildings_of_the_required_kinds(self):
        doc, _ = district()
        heroes = [b for b in doc["buildings"] if b["type"] == "hero"]
        self.assertEqual(len(heroes), 6)
        self.assertEqual({b["hero_kind"] for b in heroes}, HERO_KINDS)
        by = {b["hero_kind"]: b for b in heroes}
        self.assertEqual(by["glass_tower"]["height"], 220.0)
        self.assertGreaterEqual(by["overpass"]["length"], 400.0)
        for b in heroes:
            self.assertIn("structure", b, b["id"])

    def test_generic_buildings_follow_the_spec(self):
        doc, _ = district()
        gen = [b for b in doc["buildings"] if b["type"] == "generic"]
        self.assertGreaterEqual(len(gen), 50)
        for b in gen:
            self.assertTrue(30.0 <= b["height"] <= 220.0, b["id"])
            self.assertEqual(b["floors"] * S.FLOOR_H, b["height"], b["id"])
            self.assertIn(b["building_type"], ("office", "residential", "industrial", "parking"))
        self.assertGreaterEqual(sum(1 for b in gen if "structure" in b), math.ceil(0.25 * len(gen)))

    def test_footprints_do_not_overlap_and_stay_on_land(self):
        doc, terrain = district()
        polys = [(b["id"], [tuple(p) for p in b["footprint"]]) for b in doc["buildings"]]
        for i in range(len(polys)):
            for j in range(i + 1, len(polys)):
                self.assertFalse(polys_intersect(polys[i][1], polys[j][1]), "%s overlaps %s" % (polys[i][0], polys[j][0]))
        for b in doc["buildings"]:
            for p in b["footprint"]:
                self.assertTrue(-800 <= p[0] <= 800 and 0 <= p[1] <= 1200, b["id"])
            self.assertGreater(b["base_z"], 0.3, b["id"])

    def test_buildings_stay_off_the_streets(self):
        doc, _ = district()
        for b in doc["buildings"]:
            if b.get("hero_kind") in ("overpass", "port_crane"):
                continue
            for p in b["footprint"]:
                for r in doc["roads"]:
                    d = dist_point_polyline(tuple(p), [tuple(q) for q in r["points"]])
                    self.assertGreaterEqual(d, r["width"] / 2.0 - 0.5, "%s too close to %s" % (b["id"], r["id"]))

    def test_street_widths_blocks_plaza_alley_avenues(self):
        doc, _ = district()
        for r in doc["roads"]:
            self.assertTrue(40.0 <= r["width"] <= 90.0, r["id"])
        self.assertGreaterEqual(sum(1 for r in doc["roads"] if r["kind"] == "avenue"), 2)
        self.assertEqual(sum(1 for b in doc["blocks"] if b["kind"] == "plaza"), 1)
        alleys = [r for r in doc["roads"] if r["kind"] == "alley"]
        self.assertEqual(len(alleys), 1)
        self.assertTrue(alleys[0]["dead_end"])
        for b in doc["blocks"]:
            if b["kind"] != "block" or b.get("sub_block"):
                continue
            x0, y0, x1, y1 = bbox([tuple(p) for p in b["polygon"]])
            self.assertTrue(120.0 <= min(x1 - x0, y1 - y0) and max(x1 - x0, y1 - y0) <= 251.0, "%s %.0fx%.0f" % (b["id"], x1 - x0, y1 - y0))

    def test_props_pois_hazards_infrastructure(self):
        doc, _ = district()
        kinds = {}
        for p in doc["props"]:
            kinds[p["kind"]] = kinds.get(p["kind"], 0) + 1
        self.assertGreaterEqual(kinds["car"], 600)
        self.assertGreaterEqual(len(doc["props"]), 1500)
        for k in ("tree", "lamp"):
            self.assertGreater(kinds[k], 100)
        poi_kinds = [p["kind"] for p in doc["pois"]]
        for k in ("spawn_player", "spawn_enemy", "spawn_duel_a", "spawn_duel_b"):
            self.assertEqual(poi_kinds.count(k), 1, k)
        self.assertGreaterEqual(poi_kinds.count("camera"), 3)
        self.assertEqual({h["kind"] for h in doc["hazards"]}, {"electrical", "flood", "metro_collapse"})
        infra = doc["infrastructure"]
        self.assertGreater(len(infra["port"]["containers"]), 50)
        self.assertGreaterEqual(len(infra["metro"]["weak_segments"]), 1)
        self.assertEqual(infra["overpass_id"], "hero_overpass")

    def test_props_are_not_inside_buildings_or_water(self):
        doc, terrain = district()
        polys = [[tuple(p) for p in b["footprint"]] for b in doc["buildings"]]
        for p in doc["props"][:: max(1, len(doc["props"]) // 600)]:
            self.assertFalse(any(point_in_poly((p["pos"][0], p["pos"][1]), poly) for poly in polys), p["id"])
            self.assertGreater(p["pos"][2], 0.0, p["id"])


class Terrain(unittest.TestCase):
    def test_heightmap_file_and_encoding(self):
        doc, terrain = district()
        data = terrain.to_r16()
        self.assertEqual(len(data), 1009 * 1009 * 2)
        meta = doc["terrain"]
        vals = [data[i] | (data[i + 1] << 8) for i in range(0, len(data), 2 * 997)]
        zs = [(v - meta["height_encoding"]["zero_value"]) / meta["height_encoding"]["units_per_meter"] for v in vals]
        self.assertGreaterEqual(min(zs), meta["min_z"] - 0.02)
        self.assertLessEqual(max(zs), meta["max_z"] + 0.02)
        self.assertTrue(-27.0 <= meta["min_z"] <= -23.0)

    def test_gentle_descent_from_the_shore_to_minus_25(self):
        doc, terrain = district()
        for x in (-600.0, 0.0, 600.0):
            coast = terrain.coast_y(x)
            self.assertTrue(abs(terrain.height(x, coast)) < 1.0)
            prev = terrain.height(x, coast)
            for k in range(1, 40):
                y = coast - k * 8.0
                z = terrain.height(x, y)
                self.assertLessEqual(z, prev + 0.9)            # keeps going down (seabed noise < 1 m)
                self.assertGreater(prev - z, -0.9)
                prev = z
            self.assertLessEqual(terrain.height(x, coast - 250.0), -22.0)
            self.assertGreaterEqual(terrain.height(x, coast - 250.0), -27.0)
            # steepest 8 m step stays gentle (< 14 degrees)
            steps = [abs(terrain.height(x, coast - k * 8.0) - terrain.height(x, coast - (k + 1) * 8.0)) for k in range(30)]
            self.assertLess(max(steps) / 8.0, math.tan(math.radians(14)))

    def test_spawn_player_is_in_the_water_near_the_shore(self):
        doc, terrain = district()
        sp = next(p for p in doc["pois"] if p["kind"] == "spawn_player")
        self.assertTrue(-24.0 <= sp["pos"][2] <= -6.0, sp["pos"])
        self.assertLess(terrain.height(sp["pos"][0], sp["pos"][1]), 0.0)
        shore = terrain.coast_y(sp["pos"][0])
        self.assertTrue(40.0 <= shore - sp["pos"][1] <= 160.0)
        en = next(p for p in doc["pois"] if p["kind"] == "spawn_enemy")
        self.assertGreater(en["pos"][2], 0.5)


class Walkability(unittest.TestCase):
    CELL = 5.0
    HALF_WIDTH = 17.5                    # a 35 m wide corridor

    def test_path_of_35_m_from_player_spawn_to_enemy_spawn(self):
        doc, terrain = district()
        x0, y0, x1, y1 = -800.0, -120.0, 800.0, 1200.0
        nx, ny = int((x1 - x0) / self.CELL), int((y1 - y0) / self.CELL)
        blocked = bytearray(nx * ny)
        r = self.HALF_WIDTH
        for b in doc["buildings"]:
            if b.get("hero_kind") == "overpass":
                continue                  # elevated deck: a mech steps through it
            poly = [tuple(p) for p in b["footprint"]]
            bx0, by0, bx1, by1 = bbox(poly)
            for j in range(max(0, int((by0 - r - y0) / self.CELL)), min(ny, int((by1 + r - y0) / self.CELL) + 1)):
                for i in range(max(0, int((bx0 - r - x0) / self.CELL)), min(nx, int((bx1 + r - x0) / self.CELL) + 1)):
                    p = (x0 + (i + 0.5) * self.CELL, y0 + (j + 0.5) * self.CELL)
                    if point_in_poly(p, poly) or dist_to_poly_edges(p, poly)[0] < r:
                        blocked[j * nx + i] = 1

        def cell(p):
            return (int((p[0] - x0) / self.CELL), int((p[1] - y0) / self.CELL))

        start = cell(next(p for p in doc["pois"] if p["kind"] == "spawn_player")["pos"])
        goal = cell(next(p for p in doc["pois"] if p["kind"] == "spawn_enemy")["pos"])
        self.assertFalse(blocked[start[1] * nx + start[0]])
        self.assertFalse(blocked[goal[1] * nx + goal[0]])
        seen = {start}
        stack = [start]
        while stack:
            i, j = stack.pop()
            if (i, j) == goal:
                break
            for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                a, b2 = i + di, j + dj
                if 0 <= a < nx and 0 <= b2 < ny and (a, b2) not in seen and not blocked[b2 * nx + a]:
                    seen.add((a, b2))
                    stack.append((a, b2))
        self.assertIn(goal, seen, "no 35 m corridor from spawn_player to spawn_enemy")


class Statics(unittest.TestCase):
    def structures(self):
        doc, _ = district()
        return [(b["id"], b["structure"], b["type"]) for b in doc["buildings"] if "structure" in b]

    def test_weak_lines_collapse_in_the_stated_direction(self):
        count = 0
        for bid, st, _ in self.structures():
            for w in st["weak_lines"]:
                res = S.simulate(st, w["columns"])
                self.assertTrue(res["collapsed_tiers"], "%s %s did not collapse" % (bid, w["id"]))
                self.assertLessEqual(angle_between(res["direction"], w["collapse_dir"]), 25.0, "%s %s" % (bid, w["id"]))
                self.assertGreater(res["collapsed_mass_fraction"], 0.1, bid)
                self.assertLess(res["collapsed_mass_fraction"], 1.0, bid)
                count += 1
        self.assertGreaterEqual(count, 30)

    def test_removing_any_single_column_never_brings_the_whole_building_down(self):
        for bid, st, _ in self.structures():
            for c in st["columns"]:
                res = S.simulate(st, [c["id"]])
                self.assertLess(res["collapsed_mass_fraction"], 0.5, "%s %s" % (bid, c["id"]))
                if st.get("stacked", True):
                    self.assertNotIn(0, res["collapsed_tiers"], "%s: the reinforced ground tier must hold (%s)" % (bid, c["id"]))

    def test_graph_consistency(self):
        for bid, st, _ in self.structures():
            col_ids = {c["id"] for c in st["columns"]}
            self.assertEqual(len(col_ids), len(st["columns"]), bid)
            floor_ids = set()
            for f in st["floors"]:
                floor_ids.add(f["id"])
                for s in f["supports"]:
                    self.assertIn(s, col_ids, bid)
            for w in st["weak_lines"]:
                for c in w["columns"]:
                    self.assertIn(c, col_ids)
                self.assertAlmostEqual(math.hypot(*w["collapse_dir"]), 1.0, places=2)
            stages = st["fracture_stages"]
            self.assertEqual([s["stage"] for s in stages], [1, 2, 3])
            seen = set()
            for s in stages:
                self.assertTrue(s["floors"], "%s stage %d is empty" % (bid, s["stage"]))
                for f in s["floors"]:
                    self.assertIn(f, floor_ids)
                    self.assertNotIn(f, seen)
                    seen.add(f)
            tier_idx = {t["index"] for t in st["tiers"]}
            for c in st["columns"]:
                self.assertIn(c["tier"], tier_idx)
                self.assertGreater(c["strength"], 0)

    def test_ground_tier_is_reinforced(self):
        for bid, st, kind in self.structures():
            if not st.get("stacked", True):
                continue
            ground = [c for c in st["columns"] if c["tier"] == 0]
            upper = [c for c in st["columns"] if c["tier"] == 1 and c["role"] == "regular"]
            total = sum(t["mass"] for t in st["tiers"])
            self.assertGreater(len(ground), 0)
            nominal0 = total / len(ground)
            self.assertGreaterEqual(min(c["strength"] for c in ground) / nominal0, S.GROUND_FACTOR - 0.05, bid)

    def test_overpass_loses_only_a_few_spans(self):
        doc, _ = district()
        ov = next(b for b in doc["buildings"] if b.get("hero_kind") == "overpass")["structure"]
        self.assertFalse(ov["stacked"])
        res = S.simulate(ov, ov["weak_lines"][0]["columns"])
        self.assertEqual(len(res["collapsed_tiers"]), 2)
        self.assertLess(res["collapsed_mass_fraction"], 0.25)


class Previews(unittest.TestCase):
    def test_png_previews_are_valid(self):
        import struct
        with tempfile.TemporaryDirectory() as d:
            generate.main(["--seed", "1", "--out", d])
            for name, size in (("preview_topdown.png", (1600, 1320)), ("preview_skyline.png", (1600, 430))):
                with open(os.path.join(d, name), "rb") as f:
                    data = f.read()
                self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n")
                w, h = struct.unpack(">II", data[16:24])
                self.assertEqual((w, h), size)
                self.assertGreater(len(data), 5000)


if __name__ == "__main__":
    unittest.main()
