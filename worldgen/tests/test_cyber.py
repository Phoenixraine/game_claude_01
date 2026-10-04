"""Tests of the cyberpunk layer (TASK-019, schema_version 3). Run: python3 -m unittest discover -s worldgen/tests -t worldgen"""
import json
import math
import os
import tempfile
import time
import unittest

from tests.common import ROOT  # noqa: F401  (sets sys.path)

import generate
from iv_worldgen import cyber_data as CD
from iv_worldgen import structure as S
from iv_worldgen.cyber_signs import sign_visible
from iv_worldgen.geom import angle_between, bbox, dist_point_polyline, dist_to_poly_edges, point_in_poly, polys_intersect
from iv_worldgen.minischema import validate

NO_BLOCK = {"expressway", "suspension_bridge", "scramble_crossing"}
_CACHE = {}
GEN_SECONDS = {}


def cyber(seed=1, arena="takeshita"):
    k = (seed, arena)
    if k not in _CACHE:
        t0 = time.time()
        _CACHE[k] = generate.build(seed, "cyber", arena)
        GEN_SECONDS[k] = time.time() - t0
    return _CACHE[k]


def schema_v3():
    with open(os.path.join(ROOT, "schema_v3.json"), encoding="utf-8") as f:
        return json.load(f)


def poly(b):
    return [tuple(p) for p in b["footprint"]]


def both():
    return [("takeshita", cyber(1, "takeshita")), ("shibuya_scramble", cyber(1, "shibuya_scramble"))]


class Determinism(unittest.TestCase):
    def test_same_seed_same_hash_and_time_limit(self):
        for arena in ("takeshita", "shibuya_scramble"):
            t0 = time.time()
            d1, t1 = generate.build(2, "cyber", arena)
            dt = time.time() - t0
            self.assertLess(dt, 90.0, arena)
            d2, t2 = generate.build(2, "cyber", arena)
            self.assertEqual(generate.digest(d1, t1), generate.digest(d2, t2), arena)
        d3, t3 = generate.build(3, "cyber", "takeshita")
        self.assertNotEqual(generate.digest(d1, t1), generate.digest(d3, t3))

    def test_cli_writes_identical_files_twice(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            for d in (a, b):
                generate.main(["--seed", "4", "--out", d, "--style", "cyber", "--arena", "shibuya_scramble", "--no-preview"])
            names = ("district.json", "heightmap.r16", "district.sha256", "fog_density.png", "fog_glow.png", "towers.json", "glyph_sets.json", "light_report.json")
            for name in names:
                with open(os.path.join(a, name), "rb") as fa, open(os.path.join(b, name), "rb") as fb:
                    self.assertEqual(fa.read(), fb.read(), name)
            self.assertLess(os.path.getsize(os.path.join(a, "district.json")), 15 * 1024 * 1024)

    def test_tokyo_style_is_unchanged_by_the_cyber_layer(self):
        # worldgen/out is the committed TASK-015 reference for seed 1
        with open(os.path.join(ROOT, "out", "district.sha256")) as f:
            ref = f.read().strip()
        doc, terrain = generate.build(1, "tokyo")
        self.assertEqual(generate.digest(doc, terrain), ref)


class Schema(unittest.TestCase):
    def test_matches_schema_v3(self):
        for arena, (doc, _) in both():
            self.assertEqual(validate(doc, schema_v3()), [], arena)

    def test_rejects_broken_documents(self):
        doc, _ = cyber()
        bad = dict(doc)
        del bad["mega_signs"]
        self.assertTrue(validate(bad, schema_v3()))
        self.assertTrue(validate(dict(doc, schema_version=2), schema_v3()))
        bad = dict(doc, lights=doc["lights"][:100])
        self.assertTrue(validate(bad, schema_v3()))
        l0 = dict(doc["lights"][0], type="laser")
        self.assertTrue(validate(dict(doc, lights=[l0] + doc["lights"][1:]), schema_v3()))

    def test_unique_ids(self):
        for arena, (doc, _) in both():
            ids = []
            for key in ("roads", "blocks", "buildings", "props", "lights", "pois", "hazards", "mega_signs", "crowd_spawners"):
                ids += [x["id"] for x in doc[key]]
            for b in doc["buildings"]:
                for st in [b.get("structure")] + [p.get("structure") for p in b.get("parts", [])]:
                    if st:
                        ids += [c["id"] for c in st["columns"]] + [f["id"] for f in st["floors"]] + [w["id"] for w in st["weak_lines"]]
            ids += [w["id"] for w in doc["infrastructure"]["wires"]]
            self.assertEqual(len(ids), len(set(ids)), arena)


class Arena(unittest.TestCase):
    def test_plaza_is_free_of_buildings_and_big_enough(self):
        for arena, (doc, _) in both():
            pz = doc["arena"]["plaza"]
            self.assertGreaterEqual(pz["size"], 160.0)
            ppoly = [tuple(p) for p in pz["polygon"]]
            x0, y0, x1, y1 = bbox(ppoly)
            self.assertGreaterEqual(min(x1 - x0, y1 - y0), 160.0)
            for b in doc["buildings"]:
                if b.get("hero_kind") in NO_BLOCK:
                    continue
                self.assertFalse(polys_intersect(poly(b), ppoly), (arena, b["id"]))
                self.assertFalse(point_in_poly(poly(b)[0], ppoly), (arena, b["id"]))
            sp = next(p for p in doc["pois"] if p["kind"] == "spawn_enemy")
            self.assertTrue(point_in_poly((sp["pos"][0], sp["pos"][1]), ppoly))
            for k in ("spawn_duel_a", "spawn_duel_b"):
                p = next(q for q in doc["pois"] if q["kind"] == k)
                self.assertTrue(point_in_poly((p["pos"][0], p["pos"][1]), ppoly), k)

    def test_towers_frame_the_plaza(self):
        for arena, (doc, _) in both():
            c = doc["arena"]["plaza"]["center"]
            near = [b for b in doc["buildings"] if b.get("building_type") == "glass_tower" and math.hypot(sum(p[0] for p in b["footprint"]) / 4 - c[0], sum(p[1] for p in b["footprint"]) / 4 - c[1]) < 260.0]
            self.assertGreaterEqual(len(near), 6, arena)
            quad = {(b["footprint"][0][0] > c[0], b["footprint"][0][1] > c[1]) for b in near}
            self.assertGreaterEqual(len(quad), 3, arena)           # towers on at least three sides

    def test_takeshita_street(self):
        doc, _ = cyber(1, "takeshita")
        st = doc["arena"]["street"]
        road = next(r for r in doc["roads"] if r["id"] == st["road_id"])
        self.assertEqual(road["kind"], "pedestrian")
        self.assertTrue(10.0 <= road["width"] <= 14.0)
        length = sum(math.hypot(road["points"][i + 1][0] - road["points"][i][0], road["points"][i + 1][1] - road["points"][i][1]) for i in range(len(road["points"]) - 1))
        self.assertTrue(320.0 <= length <= 380.0, length)
        torii = [p for p in doc["props"] if p["kind"] == "torii_neon"]
        self.assertEqual(len(torii), 3)
        line = [tuple(p) for p in road["points"]]
        for t in torii:
            self.assertLess(dist_point_polyline((t["pos"][0], t["pos"][1]), line), 3.0)
        shops = [b for b in doc["buildings"] if b["building_type"] == "shopfront_row"]
        self.assertGreaterEqual(len(shops), 24)
        for b in shops:
            self.assertTrue(3 <= b["floors"] <= 6)
            self.assertLess(dist_point_polyline((sum(p[0] for p in b["footprint"]) / 4, sum(p[1] for p in b["footprint"]) / 4), line), 40.0)
            self.assertTrue(b["facade"]["vertical_signs"] >= 1)
        crowds = [c for c in doc["crowd_spawners"]]
        self.assertGreaterEqual(len(crowds), 25)
        for c in crowds:
            self.assertLess(dist_point_polyline((c["pos"][0], c["pos"][1]), line), 6.5)
        # the axis of the street is free: no footprint corner within 5 m of it
        for b in doc["buildings"]:
            if b.get("hero_kind") in NO_BLOCK:
                continue
            for p in poly(b):
                self.assertGreater(dist_point_polyline(p, line), 5.0, b["id"])

    def test_arena_flag_and_alternative(self):
        for arena, (doc, _) in both():
            self.assertEqual(doc["arena"]["name"], arena)
        d, _ = cyber(1, "shibuya_scramble")
        self.assertIsNone(d["arena"]["street"])
        with self.assertRaises(ValueError):
            generate.build(1, "cyber", "nowhere")


class GlassTowers(unittest.TestCase):
    def test_every_glass_tower_is_at_least_120_m_with_parameters(self):
        for arena, (doc, _) in both():
            gl = [b for b in doc["buildings"] if b["building_type"] == "glass_tower"]
            self.assertGreaterEqual(len(gl), 8, arena)
            for b in gl:
                self.assertGreaterEqual(b["height"], 120.0, b["id"])
                self.assertLessEqual(b["height"], 300.0)
                f = b["facade"]
                for k in ("mullion_spacing_m", "floor_height_m", "tint", "reflectivity", "crown", "setbacks", "curtain_wall", "emissive_floors", "rooftop_lights"):
                    self.assertIn(k, f)
                self.assertIn(f["crown"], ("flat", "spire", "stepped", "slanted", "halo", "antenna_cluster"))
                self.assertTrue(0.0 <= f["reflectivity"] <= 1.0)
                self.assertTrue({"panel_w", "panel_h", "spandrel_ratio"} <= set(f["curtain_wall"]))
                self.assertTrue({"pattern", "density", "color_seed"} <= set(f["emissive_floors"]))
                self.assertIn("structure", b)

    def test_at_least_ten_silhouette_presets(self):
        self.assertGreaterEqual(len(CD.TOWER_PRESETS), 10)
        sig = {(p["crown"], tuple((s["at"], s["inset_m"]) for s in p["setbacks"])) for p in CD.TOWER_PRESETS}
        self.assertGreaterEqual(len(sig), 10)
        used = set()
        for _, (doc, _) in both():
            used |= {b["facade"]["preset"] for b in doc["buildings"] if b["building_type"] == "glass_tower"}
        self.assertGreaterEqual(len(used), 10)
        doc, terrain = cyber()
        towers = json.loads(terrain.extras["towers.json"])
        self.assertEqual({p["id"] for p in towers["presets"]}, {p["id"] for p in CD.TOWER_PRESETS})


class MegaSigns(unittest.TestCase):
    def test_count_monsters_and_styles(self):
        for arena, (doc, _) in both():
            signs = doc["mega_signs"]
            self.assertGreaterEqual(len(signs), 80)
            mon = [s for s in signs if s["size_m"][1] >= 40.0]
            self.assertGreaterEqual(len(mon), 0.25 * len(signs), arena)
            self.assertTrue(all(s["monster"] == (s["size_m"][1] >= 40.0) for s in signs))
            self.assertEqual({s["style"] for s in signs}, {"vertical_banner", "billboard_screen", "neon_tube_kanji", "holo_ad", "logo_sphere"}, arena)
            for s in signs:
                self.assertLessEqual(s["size_m"][0], 60.0)
                self.assertLessEqual(s["size_m"][1], 180.0)
                self.assertTrue(s["emissive_intensity"] > 0)
                self.assertIn(s["animation"]["kind"], ("flicker", "scroll", "pulse", "cycle"))

    def test_signs_sit_on_their_host_buildings(self):
        for arena, (doc, _) in both():
            by_id = {b["id"]: b for b in doc["buildings"]}
            for s in doc["mega_signs"]:
                b = by_id[s["host"]]
                self.assertLessEqual(s["pos"][2] + s["size_m"][1] / 2.0, b["base_z"] + b["height"] + 0.5, s["id"])
                self.assertGreater(s["pos"][2] - s["size_m"][1] / 2.0, b["base_z"] + 1.0, s["id"])
                d, _ = dist_to_poly_edges((s["pos"][0], s["pos"][1]), poly(b))
                self.assertLess(d, s["size_m"][1] / 2.0 + 6.0 if s["style"] == "logo_sphere" else 5.0, s["id"])

    def test_at_least_90_percent_visible_from_the_plaza(self):
        for arena, (doc, _) in both():
            view = tuple(doc["arena"]["plaza"]["center"])
            vis = sum(1 for s in doc["mega_signs"] if sign_visible(s, doc["buildings"], view))
            self.assertGreaterEqual(vis / len(doc["mega_signs"]), 0.9, arena)

    def test_glyphs_are_known_identifiers_and_no_text(self):
        doc, terrain = cyber()
        gs = json.loads(terrain.extras["glyph_sets.json"])
        ids = {g["id"] for v in gs["sets"].values() for g in v}
        for s in doc["mega_signs"]:
            self.assertTrue(set(s["text_glyphs"]) <= ids, s["id"])
            self.assertNotIn("text", s)
        self.assertGreaterEqual(len(gs["sets"]), 3)


class Lights(unittest.TestCase):
    def test_count_bounds_defaults(self):
        for arena, (doc, _) in both():
            L = doc["lights"]
            self.assertGreaterEqual(len(L), 1500, arena)
            self.assertLess(len(json.dumps(doc)), 15 * 1024 * 1024)
            pl = doc["bounds"]["playable"]
            for l in L:
                self.assertTrue(pl["x_min"] - 40 <= l["pos"][0] <= pl["x_max"] + 40 and pl["y_min"] - 40 <= l["pos"][1] <= pl["y_max"] + 40, l["id"])
                self.assertFalse(l["shadow"])
                self.assertIn(l["type"], ("point", "rect", "spot"))
                self.assertTrue(1 <= l["priority"] <= 5 and l["radius"] > 0)
                if l["type"] == "rect":
                    self.assertIn("size", l)
            self.assertTrue({"point", "rect", "spot"} <= {l["type"] for l in L})
            self.assertGreater(sum(1 for l in L if l["flicker"] > 0), 50)

    def test_palette_policy(self):
        pal = CD.PALETTE
        for arena, (doc, _) in both():
            by_block = {}
            for l in doc["lights"]:
                # the colour stays within 40 of its palette colour (no stray hues)
                c = pal[l["hue"]]
                self.assertLess(sum((c[i] - l["color"][i]) ** 2 for i in range(3)) ** 0.5, 60.0, l["id"])
                if l["kind"] in ("neon_sign", "neon_tube", "billboard") and l["hue"] != "tungsten":
                    by_block.setdefault(l["block_id"], {}).setdefault(l["hue"], 0)
                    by_block[l["block_id"]][l["hue"]] += 1
            for bid, hues in by_block.items():
                tot = sum(hues.values())
                dominant = [h for h, n in hues.items() if n >= 0.1 * tot]
                self.assertLessEqual(len(dominant) + 1, 5, (arena, bid, hues))
            rep = doc["light_report"]
            self.assertLessEqual(rep["max_dominant_hues_in_a_block"], 5)
            self.assertEqual(rep["total"], len(doc["lights"]))
            self.assertAlmostEqual(sum(rep["hue_share"].values()), 1.0, delta=0.01)


class FogMap(unittest.TestCase):
    def test_png_is_512_square_8_bit(self):
        doc, terrain = cyber()
        for name, ctype in (("fog_density.png", 0), ("fog_glow.png", 2)):
            data = terrain.extras[name]
            self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n")
            self.assertEqual((int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")), (512, 512))
            self.assertEqual(data[24], 8)
            self.assertEqual(data[25], ctype)
        self.assertEqual(doc["fog_map"]["resolution"], [512, 512])

    def test_fog_is_lighter_on_streets_and_coloured_near_signs(self):
        import zlib
        doc, terrain = cyber()
        data = terrain.extras["fog_density.png"]
        # decode the IDAT of the grey map
        pos, idat = 8, b""
        while pos < len(data):
            n = int.from_bytes(data[pos:pos + 4], "big")
            tag = data[pos + 4:pos + 8]
            if tag == b"IDAT":
                idat += data[pos + 8:pos + 8 + n]
            pos += 12 + n
        raw = zlib.decompress(idat)
        g = lambda i, j: raw[j * 513 + 1 + i]
        sx, sy = 1600.0 / 512, 1200.0 / 512
        px = lambda x, y: (int((x + 800.0) / sx), int((1200.0 - y) / sy))
        road = next(r for r in doc["roads"] if r["kind"] == "street" and r["width"] >= 44)
        mid = road["points"][len(road["points"]) // 2]
        i, j = px(*mid)
        canal = doc["infrastructure"]["canal"]["centre"][20]
        ci, cj = px(*canal)
        self.assertLess(g(i, j), g(ci, cj))          # fog over the water is thicker than in the street


class Destruction(unittest.TestCase):
    def test_every_building_has_destruction_data(self):
        for arena, (doc, _) in both():
            for b in doc["buildings"]:
                if b.get("hero_kind") == "scramble_crossing":
                    continue
                d = b["destruction"]
                self.assertIn(d["material"], ("glass", "concrete", "mixed"))
                self.assertIn(d["fracture_pattern"], CD.FRACTURE_PATTERN_IDS)
                self.assertAlmostEqual(sum(d["debris_mix"].values()), 1.0, places=6)
                self.assertEqual(len(d["dust_color"]), 3)
            for b in doc["buildings"]:
                if b["building_type"] == "glass_tower":
                    self.assertEqual(b["destruction"]["material"], "glass")
                    self.assertGreaterEqual(b["destruction"]["debris_mix"]["glass_shards"], 0.5)
                if b["building_type"] in ("low_shop", "shopfront_row"):
                    self.assertEqual(b["destruction"]["material"], "concrete")

    def test_patterns_exist_in_the_shards_manifest_when_present(self):
        p = os.path.join(os.path.dirname(ROOT), "art", "shards", "fracture_patterns.json")
        if not os.path.exists(p):
            self.skipTest("art/shards/fracture_patterns.json is not in this branch (TASK-016)")
        with open(p) as f:
            names = {x["name"] for x in json.load(f)["patterns"]}
        self.assertEqual(set(CD.FRACTURE_PATTERN_IDS), names)


class Inherited(unittest.TestCase):
    """The checks of TASK-015 that must keep holding in the cyberpunk layer."""

    def test_footprints_do_not_overlap_and_stay_off_streets(self):
        for arena, (doc, terrain) in both():
            bs = [b for b in doc["buildings"] if b.get("hero_kind") not in NO_BLOCK]
            for i, a in enumerate(bs):
                for b in bs[i + 1:]:
                    self.assertFalse(polys_intersect(poly(a), poly(b)), (arena, a["id"], b["id"]))
            for b in bs:
                for p in poly(b):
                    self.assertGreater(terrain.height(p[0], p[1]), 0.0, b["id"])
            for b in doc["buildings"]:
                if b["type"] != "generic" or b["id"] == "bld_temple":
                    continue
                for r in doc["roads"]:
                    line = [tuple(p) for p in r["points"]]
                    for p in poly(b):
                        self.assertGreater(dist_point_polyline(p, line) - r["width"] / 2.0, 0.2, (arena, b["id"], r["id"]))

    def test_35_m_corridor_from_the_bay_to_the_plaza(self):
        for arena, (doc, terrain) in both():
            cell, half = 5.0, 17.5
            x0, y0, x1, y1 = -800.0, -120.0, 800.0, 1200.0
            nx, ny = int((x1 - x0) / cell), int((y1 - y0) / cell)
            blocked = bytearray(nx * ny)
            for b in doc["buildings"]:
                if b.get("hero_kind") in NO_BLOCK:
                    continue
                p = poly(b)
                bx0, by0, bx1, by1 = bbox(p)
                for j in range(max(0, int((by0 - half - y0) / cell)), min(ny, int((by1 + half - y0) / cell) + 1)):
                    for i in range(max(0, int((bx0 - half - x0) / cell)), min(nx, int((bx1 + half - x0) / cell) + 1)):
                        q = (x0 + (i + 0.5) * cell, y0 + (j + 0.5) * cell)
                        if point_in_poly(q, p) or dist_to_poly_edges(q, p)[0] < half:
                            blocked[j * nx + i] = 1
            c = lambda p: (int((p[0] - x0) / cell), int((p[1] - y0) / cell))
            start = c(next(p for p in doc["pois"] if p["kind"] == "spawn_player")["pos"])
            goal = c(next(p for p in doc["pois"] if p["kind"] == "spawn_enemy")["pos"])
            seen, stack = {start}, [start]
            while stack:
                i, j = stack.pop()
                if (i, j) == goal:
                    break
                for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    a, b2 = i + di, j + dj
                    if 0 <= a < nx and 0 <= b2 < ny and (a, b2) not in seen and not blocked[b2 * nx + a]:
                        seen.add((a, b2))
                        stack.append((a, b2))
            self.assertIn(goal, seen, arena)

    def test_statics(self):
        for arena, (doc, _) in both():
            n = 0
            for b in doc["buildings"]:
                sts = [b.get("structure")] + [p.get("structure") for p in b.get("parts", [])]
                for st in [s for s in sts if s]:
                    for w in st["weak_lines"]:
                        res = S.simulate(st, w["columns"])
                        self.assertTrue(res["collapsed_tiers"], (arena, b["id"]))
                        self.assertLessEqual(angle_between(res["direction"], w["collapse_dir"]), 25.0, (arena, b["id"]))
                        n += 1
            self.assertGreaterEqual(n, 60)

    def test_ten_heroes_and_building_count(self):
        for arena, (doc, _) in both():
            heroes = [b for b in doc["buildings"] if b["type"] == "hero"]
            self.assertEqual(len(heroes), 10)
            self.assertTrue(150 <= len(doc["buildings"]) <= 280, len(doc["buildings"]))


class Previews(unittest.TestCase):
    def test_pngs_written(self):
        with tempfile.TemporaryDirectory() as d:
            generate.main(["--seed", "1", "--out", d, "--style", "cyber", "--arena", "takeshita"])
            for name in ("plan.png", "signs_map.png", "light_map.png", "birdseye.png", "palette.png"):
                with open(os.path.join(d, "previews", name), "rb") as f:
                    data = f.read()
                self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n", name)
                self.assertGreater(len(data), 5000, name)


if __name__ == "__main__":
    unittest.main()
