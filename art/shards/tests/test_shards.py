"""Pure-numpy tests (no bpy needed). Run from the repo root: python3 -m unittest discover -s art/shards/tests"""
import hashlib
import json
import math
import os
import sys
import unittest

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from lib import builders, checks, fracture, geom   # noqa: E402

_LIB = None
_MAN = None


def lib():
    global _LIB, _MAN
    if _LIB is None:
        _LIB = builders.build_library()
        _MAN = checks.manifest(_LIB)
    return _LIB


def man():
    lib()
    return _MAN


class Library(unittest.TestCase):
    def test_self_check_clean(self):
        self.assertEqual(checks.check_library(lib()), [])

    def test_name_contract(self):
        names = {a.name for a in lib()}
        for cls in ("S", "M", "L", "XL"):
            for i in range(10):
                self.assertIn("Shard_Concrete_%s_%02d" % (cls, i), names)
        for prefix, n in (("Slab_Concrete", 8), ("Column_Broken", 8), ("Rebar_Bundle", 6), ("Rebar_Single", 10), ("Glass_Shard", 18), ("Window_Frame_Broken", 6), ("Pebble", 30),
                          ("Gravel_Cluster", 8), ("Steel_Plate_Bent", 8), ("Girder_Twisted", 6), ("Pipe_Broken", 6), ("Cable_Dangling", 6), ("AC_Unit_Broken", 4), ("Sign_Torn", 5)):
            for i in range(n):
                self.assertIn("%s_%02d" % (prefix, i), names, prefix)
        for cls in ("S", "M", "L"):
            self.assertEqual(sum(1 for n in names if n.startswith("Panel_Facade_Torn_%s_" % cls)), 3)

    def test_budgets(self):
        total = sum(a.mesh.tris() for a in lib())
        self.assertLessEqual(total, 300000)
        self.assertTrue(all(a.mesh.tris() <= 1500 for a in lib()))

    def test_concrete_shards_are_watertight(self):
        for a in lib():
            if a.category != "Shard_Concrete":
                continue
            edges = {}
            for t in a.mesh.t:
                for i in range(3):
                    e = tuple(sorted((int(t[i]), int(t[(i + 1) % 3]))))
                    edges[e] = edges.get(e, 0) + 1
            self.assertTrue(all(c == 2 for c in edges.values()), a.name)
            self.assertGreater(a.mesh.signed_volume(), 0, a.name + " is inside-out")

    def test_materials_and_old_face(self):
        for a in lib():
            self.assertTrue(set(a.mesh.mats) <= set(builders.MATS))
            if a.category == "Shard_Concrete":
                used = {a.mesh.mats[i] for i in set(a.mesh.m.tolist())}
                self.assertEqual(used, {"M_Concrete_Old", "M_Fracture"}, a.name)
                old_tris = int((a.mesh.m == a.mesh.mats.index("M_Concrete_Old")).sum())
                self.assertLess(old_tris, a.mesh.tris() * 0.6)

    def test_uv_islands_do_not_overlap(self):
        for a in lib():
            self.assertEqual(checks.uv_problems(a.mesh), [], a.name)

    def test_pivot_is_centre_of_mass(self):
        for a in lib():
            if a.category in ("Shard_Concrete", "Pebble"):
                vol, cen = a.mesh.volume_centroid()
                self.assertLess(np.linalg.norm(cen), 1e-6, a.name)

    def test_ucx_for_large_shards_is_convex_and_encloses(self):
        for a in lib():
            if a.category == "Shard_Concrete" and a.size_class in ("L", "XL"):
                self.assertIsNotNone(a.ucx)
                for f in a.ucx.faces:
                    n = f.normal()
                    d = float(n @ f.v[0])
                    self.assertLessEqual(float((a.ucx.verts() @ n).max()), d + 1e-6)
                lo, hi = a.mesh.bbox()
                ulo, uhi = a.ucx.verts().min(axis=0), a.ucx.verts().max(axis=0)
                self.assertTrue(np.all(ulo < lo + 0.35 * (hi - lo)) and np.all(uhi > hi - 0.35 * (hi - lo)))

    def test_deterministic(self):
        a = checks.manifest(builders.build_library())
        self.assertEqual(json.dumps(a, sort_keys=True), json.dumps(man(), sort_keys=True))

    def test_manifest_fields(self):
        for e in man()["assets"]:
            for k in ("name", "category", "size_class", "group", "triangles", "bbox_min", "bbox_max", "radius", "mass_kg_hint", "ucx", "pca_axes", "pca_extents"):
                self.assertIn(k, e)
            self.assertGreater(e["radius"], 0)
            self.assertGreater(e["mass_kg_hint"], 0)
            self.assertTrue(all(math.isfinite(x) for x in e["size"]))
        self.assertEqual(sum(e["triangles"] for e in man()["assets"]), man()["triangles_total"])

    def test_committed_manifest_matches(self):
        p = os.path.join(ROOT, "shards_manifest.json")
        if not os.path.exists(p):
            self.skipTest("manifest not generated yet")
        with open(p, encoding="utf-8") as f:
            self.assertEqual(json.load(f), json.loads(json.dumps(man())), "run build_shards.py")


class Fracture(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.P = fracture.make_patterns(man())

    def test_twenty_patterns_all_kinds(self):
        self.assertEqual(len(self.P["patterns"]), 20)
        self.assertEqual({p["kind"] for p in self.P["patterns"]}, {"voronoi", "radial_impact", "layered", "diagonal"})
        self.assertEqual(len({p["name"] for p in self.P["patterns"]}), 20)

    def test_cells_partition_the_cube(self):
        for p in self.P["patterns"]:
            self.assertAlmostEqual(p["volume_sum"], 1.0, places=3, msg=p["name"])
            self.assertAlmostEqual(sum(f["volume"] for f in p["pieces"]), 1.0, places=3, msg=p["name"])
            self.assertGreaterEqual(p["fragments"], 8)

    def test_cells_are_convex_and_inside_the_cube(self):
        for p in self.P["patterns"]:
            for c in p["cells"]:
                V = np.array(c["verts"])
                self.assertTrue(np.all(np.abs(V) <= 0.5 + 1e-4), p["name"])
                for poly in c["polys"]:
                    pts = V[poly["v"]]
                    n = sum(np.cross(pts[i] - pts[0], pts[i + 1] - pts[0]) for i in range(1, len(pts) - 1))      # Newell-style: robust for sliver corners
                    n = n / np.linalg.norm(n)
                    self.assertLessEqual(float(((V - pts[0]) @ n).max()), 1e-4, p["name"])

    def test_fragments_reference_the_library(self):
        names = {e["name"]: e for e in man()["assets"]}
        for p in self.P["patterns"]:
            for f in p["pieces"]:
                self.assertIn(f["lib"], names)
                self.assertTrue(names[f["lib"]]["category"] == "Shard_Concrete")
                q = np.array(f["quat"])
                self.assertAlmostEqual(float(np.linalg.norm(q)), 1.0, places=4)
                R = fracture.quat_to_mat(f["quat"])
                self.assertLess(np.abs(R @ R.T - np.eye(3)).max(), 1e-4)
                self.assertAlmostEqual(float(np.linalg.det(R)), 1.0, places=4)
                self.assertTrue(all(0.0 < s < 50 and math.isfinite(s) for s in f["scale"]))
                self.assertTrue(all(abs(x) <= 0.5 + 1e-4 for x in f["pos"]))

    def test_scaled_shard_fits_its_cell(self):
        names = {e["name"]: e for e in man()["assets"]}
        for p in self.P["patterns"][:6]:
            for f in p["pieces"]:
                e = np.array(names[f["lib"]]["pca_extents"]) * np.array(f["scale"])
                self.assertLess(np.abs(e - np.array(f["extents"])).max(), 1e-3)

    def test_radial_pattern_has_small_pieces_near_the_impact(self):
        for p in self.P["patterns"]:
            if p["kind"] != "radial_impact":
                continue
            near = [f for f in p["pieces"] if abs(f["pos"][1] + 0.5) < 0.2]
            far = [f for f in p["pieces"] if f["pos"][1] > 0.0]
            self.assertTrue(near)
            self.assertLess(np.mean([f["volume"] for f in near]), np.mean([f["volume"] for f in far]) * 1.2 if far else 1.0)

    def test_deterministic(self):
        Q = fracture.make_patterns(man())
        self.assertEqual(hashlib.sha1(json.dumps(Q, sort_keys=True).encode()).hexdigest(), hashlib.sha1(json.dumps(self.P, sort_keys=True).encode()).hexdigest())

    def test_committed_patterns_match(self):
        p = os.path.join(ROOT, "fracture_patterns.json")
        if not os.path.exists(p):
            self.skipTest("patterns not generated yet")
        with open(p, encoding="utf-8") as f:
            self.assertEqual(json.load(f), json.loads(json.dumps(self.P)))


class Geometry(unittest.TestCase):
    def test_clip_keeps_volume_additive(self):
        s = geom.box_solid((1, 1, 1))
        n = geom.unit([1, 0.3, 0.1])
        a = geom.clip_solid(s, n, 0.1)
        b = geom.clip_solid(s, -n, -0.1)
        self.assertAlmostEqual(a.volume() + b.volume(), 1.0, places=6)

    def test_ear_clip_concave(self):
        P = [(-1, -1), (1, -1), (1, -.8), (.1, -.8), (.1, .8), (1, .8), (1, 1), (-1, 1), (-1, .8), (-.1, .8), (-.1, -.8), (-1, -.8)]
        tris = geom.ear_clip(P)
        self.assertEqual(len(tris), len(P) - 2)
        area = 0.0
        for a, b, c in tris:
            area += 0.5 * ((P[b][0] - P[a][0]) * (P[c][1] - P[a][1]) - (P[b][1] - P[a][1]) * (P[c][0] - P[a][0]))
        self.assertAlmostEqual(area, 2 * 0.2 * 2 + 0.2 * 1.6, places=6)       # two flanges + web of the I section, every triangle wound CCW


    def test_noise_deterministic_bounded(self):
        vals = [geom.vnoise((i * 0.37, i * 0.11, 0.5), 3) for i in range(200)]
        self.assertTrue(all(-1.0 <= v <= 1.0 for v in vals))
        self.assertEqual(vals, [geom.vnoise((i * 0.37, i * 0.11, 0.5), 3) for i in range(200)])


if __name__ == "__main__":
    unittest.main()
