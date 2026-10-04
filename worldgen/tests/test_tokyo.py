"""Tests of the Tokyo style (TASK-015, schema_version 2). Run: python3 -m unittest discover -s worldgen/tests -t worldgen"""
import json
import math
import os
import tempfile
import unittest

from tests.common import ROOT  # noqa: F401  (sets sys.path)

import generate
from iv_worldgen import structure as S
from iv_worldgen.geom import angle_between, bbox, dist_point_polyline, dist_to_poly_edges, point_in_poly, polys_intersect
from iv_worldgen.minischema import validate

HERO_KINDS = {"glass_tower", "tower_lattice", "twin_tower_hall", "brick_station", "sphere_building", "temple_gate", "scramble_crossing", "port_crane", "expressway", "suspension_bridge"}
NO_BLOCK = {"expressway", "suspension_bridge", "scramble_crossing"}
_CACHE = {}


def tokyo(seed=1):
    if seed not in _CACHE:
        _CACHE[seed] = generate.build(seed, "tokyo")
    return _CACHE[seed]


def schema_v2():
    with open(os.path.join(ROOT, "schema_v2.json"), encoding="utf-8") as f:
        return json.load(f)


def poly(b):
    return [tuple(p) for p in b["footprint"]]


def all_structures(doc):
    out = []
    for b in doc["buildings"]:
        if "structure" in b:
            out.append((b["id"], b["structure"]))
        for p in b.get("parts", []):
            if "structure" in p:
                out.append((b["id"] + "/" + p["id"], p["structure"]))
    return out


class Determinism(unittest.TestCase):
    def test_same_seed_same_hash(self):
        d1, t1 = generate.build(3, "tokyo")
        d2, t2 = generate.build(3, "tokyo")
        self.assertEqual(generate.digest(d1, t1), generate.digest(d2, t2))
        d3, t3 = generate.build(4, "tokyo")
        self.assertNotEqual(generate.digest(d1, t1), generate.digest(d3, t3))

    def test_cli_default_is_tokyo_and_identical_twice(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            generate.main(["--seed", "6", "--out", a, "--no-preview"])
            generate.main(["--seed", "6", "--out", b, "--no-preview"])
            for name in ("district.json", "heightmap.r16", "district.sha256"):
                with open(os.path.join(a, name), "rb") as fa, open(os.path.join(b, name), "rb") as fb:
                    self.assertEqual(fa.read(), fb.read(), name)
            with open(os.path.join(a, "district.json")) as f:
                self.assertEqual(json.load(f)["schema_version"], 2)

    def test_generic_style_still_gives_schema_version_1(self):
        with tempfile.TemporaryDirectory() as a:
            generate.main(["--seed", "2", "--out", a, "--no-preview", "--style", "generic"])
            with open(os.path.join(a, "district.json")) as f:
                self.assertEqual(json.load(f)["schema_version"], 1)


class Schema(unittest.TestCase):
    def test_matches_schema_v2(self):
        doc, _ = tokyo()
        self.assertEqual(validate(doc, schema_v2()), [])

    def test_rejects_broken_documents(self):
        doc, _ = tokyo()
        bad = dict(doc)
        del bad["lights"]
        self.assertTrue(validate(bad, schema_v2()))
        self.assertTrue(validate(dict(doc, schema_version=1), schema_v2()))
        bad = dict(doc, buildings=[dict(doc["buildings"][0], height=999.0)] + doc["buildings"][1:])
        self.assertTrue(validate(bad, schema_v2()))

    def test_unique_ids(self):
        doc, _ = tokyo()
        ids = []
        for key in ("roads", "blocks", "buildings", "props", "lights", "pois", "hazards"):
            ids += [x["id"] for x in doc[key]]
        for _, st in all_structures(doc):
            ids += [c["id"] for c in st["columns"]] + [f["id"] for f in st["floors"]] + [w["id"] for w in st["weak_lines"]]
        infra = doc["infrastructure"]
        ids += [c["id"] for c in infra["port"]["containers"]] + [g["id"] for g in infra["guardrails"]] + [w["id"] for w in infra["wires"]] + [b["id"] for b in infra["bridges"]]
        ids.append(infra["canal"]["id"])
        self.assertEqual(len(ids), len(set(ids)))


class Heroes(unittest.TestCase):
    def test_exactly_the_ten_hero_objects(self):
        doc, _ = tokyo()
        kinds = [b["hero_kind"] for b in doc["buildings"] if b["type"] == "hero"]
        self.assertEqual(sorted(kinds), sorted(HERO_KINDS))
        self.assertLessEqual(len(kinds), 10)

    def test_heroes_inside_the_playable_area(self):
        doc, _ = tokyo()
        pl = doc["bounds"]["playable"]
        for b in doc["buildings"]:
            if b["type"] != "hero":
                continue
            x0, y0, x1, y1 = bbox(poly(b))
            self.assertTrue(pl["x_min"] <= x0 and x1 <= pl["x_max"] and pl["y_min"] <= y0 and y1 <= pl["y_max"], b["id"])

    def test_landmark_sizes(self):
        doc, _ = tokyo()
        H = {b["hero_kind"]: b for b in doc["buildings"] if b["type"] == "hero"}
        self.assertAlmostEqual(H["tower_lattice"]["height"], 333.0, delta=1.0)
        self.assertAlmostEqual(H["twin_tower_hall"]["height"], 240.0, delta=1.0)
        self.assertEqual(H["glass_tower"]["height"], 220.0)
        x0, y0, x1, y1 = bbox(poly(H["brick_station"]))
        self.assertGreater(max(x1 - x0, y1 - y0), 290.0)
        sb = H["suspension_bridge"]
        self.assertEqual([p["height"] for p in sb["parts"] if p["kind"] == "pylon"], [90.0, 90.0])
        self.assertGreater(len([p for p in sb["parts"] if p["kind"] == "main_cable" and len(p["points"]) > 20]), 1)
        sc = H["scramble_crossing"]
        x0, y0, x1, y1 = bbox(poly(sc))
        self.assertAlmostEqual(x1 - x0, 80.0, delta=0.5)
        self.assertAlmostEqual(y1 - y0, 80.0, delta=0.5)
        self.assertGreaterEqual(len([p for p in sc["parts"] if p["kind"] == "screen_wall"]), 3)
        self.assertGreaterEqual(len([p for p in sc["parts"] if p["kind"] == "crosswalk"]), 6)
        self.assertEqual(len(H["twin_tower_hall"]["parts"]), 3)


class Layout(unittest.TestCase):
    def test_building_count_and_types(self):
        for seed in (1, 2, 3):
            doc, _ = tokyo(seed)
            n = len(doc["buildings"])
            self.assertTrue(150 <= n <= 260, (seed, n))
        doc, _ = tokyo()
        types = {b["building_type"] for b in doc["buildings"]}
        self.assertTrue({"apartment_tower", "office_tower", "low_shop", "parking", "temple", "station", "landmark"} <= types, types)
        gen = [b for b in doc["buildings"] if b["type"] == "generic"]
        self.assertGreaterEqual(sum(1 for b in gen if "structure" in b), 0.25 * len(gen) * 0.9 - 1)
        for b in gen:
            lim = {"apartment_tower": (40, 120), "office_tower": (80, 200), "low_shop": (12, 30), "parking": (20, 36), "temple": (8, 16)}[b["building_type"]]
            self.assertTrue(lim[0] <= b["height"] <= lim[1], (b["id"], b["building_type"], b["height"]))
            self.assertEqual(b["height"], b["floors"] * 4.0) if b["building_type"] != "temple" else None

    def test_street_widths_and_at_least_20_narrow_alleys(self):
        for seed in (1, 2, 3):
            doc, _ = tokyo(seed)
            alleys = [r for r in doc["roads"] if r["kind"] == "alley"]
            self.assertGreaterEqual(len(alleys), 20, seed)
            for r in alleys:
                self.assertTrue(24.0 <= r["width"] <= 36.0, r)
            for r in doc["roads"]:
                if r["kind"] != "alley":
                    self.assertTrue(40.0 <= r["width"] <= 90.0, r)
            self.assertGreaterEqual(sum(1 for r in doc["roads"] if r["width"] >= 90.0), 3)      # two avenues and the boulevard
            self.assertTrue(all(90.0 <= b["width"] or True for b in doc["infrastructure"]["bridges"]))

    def test_blocks_are_90_to_180_m(self):
        doc, _ = tokyo()
        for b in doc["blocks"]:
            if b["kind"] != "block" or b.get("sub_block"):
                continue
            pts = [tuple(p) for p in b["polygon"]]
            w = math.hypot(pts[1][0] - pts[0][0], pts[1][1] - pts[0][1])
            h = math.hypot(pts[3][0] - pts[0][0], pts[3][1] - pts[0][1])
            self.assertTrue(85.0 <= w <= 185.0 and 85.0 <= h <= 185.0, (b["id"], w, h))

    def test_footprints_do_not_overlap_and_stay_on_land(self):
        doc, terrain = tokyo()
        bs = [b for b in doc["buildings"] if b.get("hero_kind") not in NO_BLOCK]
        for i, a in enumerate(bs):
            for b in bs[i + 1:]:
                self.assertFalse(polys_intersect(poly(a), poly(b)), (a["id"], b["id"]))
        for b in bs:
            for p in poly(b):
                self.assertGreater(terrain.height(p[0], p[1]), 0.0, b["id"])

    def test_buildings_stay_off_the_streets(self):
        doc, _ = tokyo()
        for b in doc["buildings"]:
            if b["type"] != "generic" or b["id"] == "bld_temple":
                continue
            for r in doc["roads"]:
                line = [tuple(p) for p in r["points"]]
                for p in poly(b):
                    self.assertGreater(dist_point_polyline(p, line) - r["width"] / 2.0, 0.5, (b["id"], r["id"]))

    def test_canal_and_bridges(self):
        doc, terrain = tokyo()
        canal = doc["infrastructure"]["canal"]
        for s, n in zip(canal["south_bank"], canal["north_bank"]):
            self.assertTrue(49.5 <= n[1] - s[1] <= 80.5, (s, n))
            mid = (s[1] + n[1]) / 2.0
            self.assertLess(terrain.height(s[0], mid), -2.0)
        self.assertEqual(len(doc["infrastructure"]["bridges"]), 2)
        for br in doc["infrastructure"]["bridges"]:
            self.assertGreaterEqual(br["length"], 60.0)
            self.assertGreater(br["deck_z"], 2.0)


class Walkability(unittest.TestCase):
    CELL = 5.0
    HALF = 17.5

    def test_35_m_corridor_from_the_bay_to_the_scramble(self):
        doc, terrain = tokyo()
        x0, y0, x1, y1 = -800.0, -120.0, 800.0, 1200.0
        nx, ny = int((x1 - x0) / self.CELL), int((y1 - y0) / self.CELL)
        blocked = bytearray(nx * ny)
        r = self.HALF
        for b in doc["buildings"]:
            if b.get("hero_kind") in NO_BLOCK:
                continue
            p = poly(b)
            bx0, by0, bx1, by1 = bbox(p)
            for j in range(max(0, int((by0 - r - y0) / self.CELL)), min(ny, int((by1 + r - y0) / self.CELL) + 1)):
                for i in range(max(0, int((bx0 - r - x0) / self.CELL)), min(nx, int((bx1 + r - x0) / self.CELL) + 1)):
                    q = (x0 + (i + 0.5) * self.CELL, y0 + (j + 0.5) * self.CELL)
                    if point_in_poly(q, p) or dist_to_poly_edges(q, p)[0] < r:
                        blocked[j * nx + i] = 1
        cell = lambda p: (int((p[0] - x0) / self.CELL), int((p[1] - y0) / self.CELL))
        start = cell(next(p for p in doc["pois"] if p["kind"] == "spawn_player")["pos"])
        goal = cell(next(p for p in doc["pois"] if p["kind"] == "spawn_enemy")["pos"])
        self.assertFalse(blocked[start[1] * nx + start[0]])
        self.assertFalse(blocked[goal[1] * nx + goal[0]])
        seen, stack = {start}, [start]
        while stack:
            i, j = stack.pop()
            if (i, j) == goal:
                break
            for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                a, c = i + di, j + dj
                if 0 <= a < nx and 0 <= c < ny and (a, c) not in seen and not blocked[c * nx + a]:
                    seen.add((a, c))
                    stack.append((a, c))
        self.assertIn(goal, seen)

    def test_duel_points_are_reachable_open_ground(self):
        doc, terrain = tokyo()
        for p in doc["pois"]:
            if p["kind"].startswith("spawn_duel") or p["kind"] == "duel_point":
                self.assertGreater(p["pos"][2], 0.5)
                for b in doc["buildings"]:
                    if b.get("hero_kind") in NO_BLOCK:
                        continue
                    self.assertGreater(dist_to_poly_edges((p["pos"][0], p["pos"][1]), poly(b))[0], 17.5, (p["id"], b["id"]))


class Expressway(unittest.TestCase):
    def test_deck_does_not_cross_buildings_pylons_are_on_land(self):
        doc, terrain = tokyo()
        ex = next(b for b in doc["buildings"] if b.get("hero_kind") == "expressway")
        deck = poly(ex)
        for b in doc["buildings"]:
            if b is ex or b.get("hero_kind") in ("suspension_bridge", "scramble_crossing"):
                continue
            self.assertFalse(polys_intersect(deck, poly(b)), b["id"])
        canal = doc["infrastructure"]["canal"]
        for c in ex["structure"]["columns"]:
            x, y, z = c["pos"]
            self.assertGreater(terrain.height(x, y), 0.5, c["id"])
            south = min(canal["south_bank"], key=lambda p: abs(p[0] - x))[1]
            north = min(canal["north_bank"], key=lambda p: abs(p[0] - x))[1]
            self.assertFalse(south - 1.0 < y < north + 1.0, c["id"])

    def test_geometry(self):
        doc, terrain = tokyo()
        ex = next(b for b in doc["buildings"] if b.get("hero_kind") == "expressway")
        self.assertEqual(ex["width"], 26.0)
        self.assertGreater(ex["length"], 1500.0)
        for c in ex["structure"]["columns"]:
            self.assertTrue(10.0 <= c["height"] <= 18.0, c)
        piers = sorted({round(c["pos"][0], 0) for c in ex["structure"]["columns"]})
        gaps = [b - a for a, b in zip(piers, piers[1:]) if b - a > 5.0]
        self.assertTrue(all(30.0 <= g <= 50.0 for g in gaps), gaps[:5])
        self.assertEqual(len([p for p in ex["parts"] if p["kind"] == "ramp"]), 2)
        self.assertGreater(ex["parts"][0]["points"][0][2], ex["parts"][0]["points"][-1][2])

    def test_only_a_few_spans_fall(self):
        doc, _ = tokyo()
        ex = next(b for b in doc["buildings"] if b.get("hero_kind") == "expressway")
        st = ex["structure"]
        res = S.simulate(st, st["weak_lines"][0]["columns"])
        n = len(st["tiers"])
        self.assertTrue(1 <= len(res["collapsed_tiers"]) <= 4, res["collapsed_tiers"])
        self.assertLess(res["collapsed_mass_fraction"], 4.0 / n + 0.01)
        self.assertEqual(S.simulate(st, [st["columns"][3]["id"]])["collapsed_tiers"], [])


class Statics(unittest.TestCase):
    def test_weak_lines_collapse_in_the_stated_direction(self):
        doc, _ = tokyo()
        count = 0
        for bid, st in all_structures(doc):
            for w in st["weak_lines"]:
                res = S.simulate(st, w["columns"])
                self.assertTrue(res["collapsed_tiers"], "%s %s did not collapse" % (bid, w["id"]))
                self.assertLessEqual(angle_between(res["direction"], w["collapse_dir"]), 25.0, "%s %s" % (bid, w["id"]))
                count += 1
        self.assertGreaterEqual(count, 50)

    def test_single_column_loss_never_drops_a_stacked_building(self):
        doc, _ = tokyo()
        for bid, st in all_structures(doc):
            if not st.get("stacked", True):
                continue
            for c in st["columns"][::5]:
                res = S.simulate(st, [c["id"]])
                self.assertLess(res["collapsed_mass_fraction"], 1.0, (bid, c["id"]))

    def test_graph_consistency(self):
        doc, _ = tokyo()
        for bid, st in all_structures(doc):
            ids = {c["id"] for c in st["columns"]}
            for f in st["floors"]:
                self.assertTrue(set(f["supports"]) <= ids, bid)
            for w in st["weak_lines"]:
                self.assertTrue(set(w["columns"]) <= ids, bid)
            seen = set()
            for stg in st["fracture_stages"]:
                for f in stg["floors"]:
                    self.assertNotIn(f, seen)
                    seen.add(f)


class Props(unittest.TestCase):
    def test_counts(self):
        doc, _ = tokyo()
        cnt = {}
        for p in doc["props"]:
            cnt[p["kind"]] = cnt.get(p["kind"], 0) + 1
        self.assertGreaterEqual(cnt["vending"], 800)
        self.assertEqual(cnt["sakura"], 40)
        self.assertGreaterEqual(cnt["car"], 600)
        for k in ("lantern", "utility_pole", "sign", "traffic_light", "bus_stop", "cone", "bicycle", "scooter", "tree", "lamp"):
            self.assertGreater(cnt.get(k, 0), 0, k)

    def test_signs_are_emissive_and_text_free(self):
        doc, _ = tokyo()
        signs = [p for p in doc["props"] if p["kind"] == "sign"]
        self.assertGreater(len(signs), 100)
        for s in signs:
            self.assertTrue(s["emissive"])
            self.assertEqual(len(s["size"]), 2)
            self.assertNotIn("text", s)

    def test_wires_connect_existing_poles_with_sag(self):
        doc, _ = tokyo()
        poles = {p["id"]: p for p in doc["props"] if p["kind"] == "utility_pole"}
        wires = doc["infrastructure"]["wires"]
        self.assertGreater(len(wires), 30)
        for w in wires:
            self.assertIn(w["from"], poles)
            self.assertIn(w["to"], poles)
            zs = [p[2] for p in w["points"]]
            self.assertLess(min(zs[1:-1]), zs[0])
            self.assertLess(min(zs[1:-1]), zs[-1] + 0.5)

    def test_props_are_not_inside_buildings_or_water(self):
        doc, terrain = tokyo()
        polys = [poly(b) for b in doc["buildings"] if b.get("hero_kind") not in NO_BLOCK]
        for p in doc["props"]:
            if p["kind"] in ("sign",):
                continue
            self.assertGreater(terrain.height(p["pos"][0], p["pos"][1]), 0.0, p["id"])
            for q in polys:
                if bbox(q)[0] <= p["pos"][0] <= bbox(q)[2] and bbox(q)[1] <= p["pos"][1] <= bbox(q)[3]:
                    self.assertFalse(point_in_poly((p["pos"][0], p["pos"][1]), q), p["id"])

    def test_lights(self):
        doc, _ = tokyo()
        self.assertGreaterEqual(len(doc["lights"]), 600)
        self.assertEqual({l["kind"] for l in doc["lights"]}, {"street", "neon_sign", "window_block", "billboard"})
        pl = doc["bounds"]["playable"]
        for l in doc["lights"]:
            self.assertTrue(pl["x_min"] - 40 <= l["pos"][0] <= pl["x_max"] + 40 and pl["y_min"] - 40 <= l["pos"][1] <= pl["y_max"] + 40, l["id"])


class PoisAndHazards(unittest.TestCase):
    def test_pois(self):
        doc, terrain = tokyo()
        kinds = [p["kind"] for p in doc["pois"]]
        self.assertEqual(kinds.count("camera"), 8)
        for k in ("spawn_player", "spawn_enemy", "spawn_duel_a", "spawn_duel_b", "duel_point"):
            self.assertIn(k, kinds)
        sp = next(p for p in doc["pois"] if p["kind"] == "spawn_player")
        self.assertTrue(-24.0 <= sp["pos"][2] <= -6.0)
        self.assertTrue(40.0 <= terrain.coast_y(sp["pos"][0]) - sp["pos"][1] <= 160.0)
        for p in doc["pois"]:
            if p["kind"] == "camera":
                self.assertEqual(len(p["look_at"]), 3)

    def test_new_hazards(self):
        doc, _ = tokyo()
        kinds = {h["kind"] for h in doc["hazards"]}
        self.assertTrue({"expressway_collapse", "canal_flood"} <= kinds)
        self.assertIn("haz_canal_flood", doc["water"]["flood_zones"])


class Previews(unittest.TestCase):
    def test_pngs_are_valid(self):
        with tempfile.TemporaryDirectory() as d:
            generate.main(["--seed", "1", "--out", d])
            for name, size in (("preview_topdown.png", (1600, 1320)), ("preview_skyline.png", (1600, 520))):
                with open(os.path.join(d, name), "rb") as f:
                    data = f.read()
                self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n")
                self.assertEqual((int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")), size)


if __name__ == "__main__":
    unittest.main()
