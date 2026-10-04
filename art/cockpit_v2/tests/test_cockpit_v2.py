"""Metrics and contract tests of cockpit v2. Pure python (no bpy) except the optional glass-share check, which reads out/cockpit_metrics.json written by build_cockpit_v2.py.
Run: python3 -m unittest discover -s art/cockpit_v2/tests -v"""
import json
import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
sys.path.insert(0, ROOT)

from lib import cracks, damage, layout, metrics  # noqa: E402

MODEL = layout.build_model(20261004)
OUT = os.path.join(ROOT, "out")


def names(kind):
    return [p.name for p in MODEL.parts if p.kind == kind]


def enames(kind):
    return [e.name for e in MODEL.empties if e.kind == kind]


class Counts(unittest.TestCase):
    def test_pipes(self):
        self.assertGreaterEqual(len(names("Pipe")), 40)

    def test_pipe_radii_variety(self):
        r = {round(p.meta["radius"], 3) for p in MODEL.parts if p.kind == "Pipe"}
        self.assertGreaterEqual(len(r), 5)
        self.assertLessEqual(len(r), 16)

    def test_steam_ports(self):
        self.assertGreaterEqual(len(enames("SteamPort")), 12)

    def test_burst_variants_replace_pipes(self):
        pipes = set(names("Pipe"))
        for p in MODEL.parts:
            if p.kind == "Pipe_Burst":
                self.assertIn(p.meta["replaces"], pipes)
                self.assertFalse(p.visible)
        self.assertGreaterEqual(len(enames("LeakPoint")), 8)

    def test_wires(self):
        self.assertGreaterEqual(len(names("Wire")), 60)
        self.assertGreaterEqual(len(enames("WireAnchor")), 60)

    def test_snapped_wires(self):
        wires = set(names("Wire"))
        sn = [p for p in MODEL.parts if p.kind == "Wire_Snapped"]
        self.assertGreaterEqual(len(sn), 12)
        for p in sn:
            self.assertIn(p.meta["replaces"], wires)
        self.assertGreaterEqual(len(enames("SparkPort")), len(sn))

    def test_buttons(self):
        btn = [p for p in MODEL.parts if p.kind == "Btn"]
        self.assertGreaterEqual(len(btn), 80)
        self.assertGreaterEqual(len({p.meta["type"] for p in btn}), 6)

    def test_dials_sliders_caps(self):
        for k in ("Dial", "Slider", "Cap"):
            self.assertGreater(len(names(k)), 0, k)

    def test_monitors(self):
        mons = [p for p in MODEL.parts if p.kind == "Mon"]
        self.assertGreaterEqual(len(mons), 12)
        self.assertGreaterEqual(len({p.meta["shape"] for p in mons}), 4)
        self.assertGreaterEqual(len(enames("MonitorAnchor")), len(mons))
        for p in mons:
            self.assertIn("M_Monitor", p.mb.mats)

    def test_monitor_uv_range(self):
        for p in MODEL.parts:
            if p.kind != "Mon":
                continue
            uvs = [uv for tri_uv, m in zip(p.mb.UV, p.mb.M) if p.mb.mats[m] == "M_Monitor" for uv in tri_uv if uv is not None]
            self.assertTrue(uvs, p.name)
            lo = min(min(u) for u in map(tuple, [(a, b) for a, b in uvs]))
            hi = max(max(u) for u in map(tuple, [(a, b) for a, b in uvs]))
            self.assertGreaterEqual(lo, -1e-6, p.name)
            self.assertLessEqual(hi, 1.0 + 1e-6, p.name)

    def test_lamps(self):
        lamps = names("Lamp")
        self.assertGreaterEqual(len(lamps), 40)
        self.assertTrue(any(n.startswith("Lamp_Warn_") for n in lamps))
        self.assertTrue(any(n.startswith("Lamp_Ok_") for n in lamps))
        for p in MODEL.parts:
            if p.kind == "Lamp":
                self.assertIn("M_Lamp", p.mb.mats)

    def test_beacons_strobes(self):
        self.assertEqual(len(names("AlarmBeacon")), 4)
        self.assertEqual(len(enames("AlarmBeaconAxis")), 4)
        self.assertEqual(len(names("StrobePanel")), 4)

    def test_fire_and_decals(self):
        self.assertEqual(len(enames("Fire_Socket")), 8)
        self.assertEqual(len(names("Scorch_Decal")), 6)

    def test_glass(self):
        g = names("Glass")
        self.assertIn("Glass_Front", g)
        self.assertTrue(all(n.startswith("Glass_") for n in g))

    def test_unique_names(self):
        allnames = [p.name for p in MODEL.parts] + [e.name for e in MODEL.empties]
        self.assertEqual(len(allnames), len(set(allnames)))

    def test_name_pattern(self):
        pat = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
        for p in MODEL.parts:
            self.assertRegex(p.name, pat)


class Budgets(unittest.TestCase):
    def test_triangles(self):
        per, total = metrics.triangles(MODEL)
        self.assertLessEqual(max(per.values()), metrics.MAX_PART_TRIS, max(per, key=per.get))
        self.assertLessEqual(total, metrics.MAX_TOTAL_TRIS)

    def test_deterministic(self):
        a = layout.build_model(20261004)
        self.assertEqual([(p.name, p.mb.tris()) for p in a.parts], [(p.name, p.mb.tris()) for p in MODEL.parts])
        self.assertEqual(json.dumps(metrics.parts_doc(a), sort_keys=True), json.dumps(metrics.parts_doc(MODEL), sort_keys=True))

    def test_geometry_finite_and_in_cabin(self):
        import numpy as np
        for p in MODEL.parts:
            P, T, M, UV = p.mb.arrays()
            self.assertTrue(np.isfinite(P).all(), p.name)
            self.assertLess(np.abs(P).max(), 6.0, p.name)
            if len(T):
                self.assertLess(T.max(), len(P), p.name)

    def test_no_negative_volume(self):
        import numpy as np
        for p in MODEL.parts:
            if p.kind not in ("Console", "Btn", "Dial", "Slider", "Cap", "Frame", "Pipe", "Wire"):  # closed solids only (domes, screens, decals are open shells)
                continue
            P, T, M, UV = p.mb.arrays()
            if not len(T):
                continue
            v = np.einsum("ij,ij->i", P[T[:, 0]], np.cross(P[T[:, 1]], P[T[:, 2]])).sum() / 6.0
            self.assertGreater(v, -1e-6, p.name)

    def test_pilot_clearance(self):
        """Nothing solid inside a 0.35 m sphere around the eye (the near plane is 2 cm)."""
        import numpy as np
        for p in MODEL.parts:
            P = p.mb.arrays()[0]
            if len(P):
                self.assertGreater(np.linalg.norm(P, axis=1).min(), 0.35, p.name)


class DamageSpec(unittest.TestCase):
    SPEC = metrics.spec_doc(MODEL)

    def test_levels_cumulative(self):
        prev = {}
        for sev in damage.SEVERITIES:
            lv = self.SPEC["levels"][sev]
            for k, v in lv.items():
                if isinstance(v, list) and k not in ("Mon_dead", "Mon_glitch"):
                    self.assertTrue(set(prev.get(k, [])) <= set(v), (sev, k))
            # a glitching monitor may go dead at the next level: the union of both groups only grows
            self.assertTrue(set(prev.get("Mon_dead", [])) | set(prev.get("Mon_glitch", [])) <= set(lv.get("Mon_dead", [])) | set(lv.get("Mon_glitch", [])), sev)
            self.assertTrue(set(prev.get("Mon_dead", [])) <= set(lv.get("Mon_dead", [])), sev)
            prev = lv

    def test_names_exist(self):
        existing = {p.name for p in MODEL.parts} | {e.name for e in MODEL.empties} | {"Glass_Crack_Mask_%02d" % k for k in range(4)}
        for sev, lv in self.SPEC["levels"].items():
            for k, v in lv.items():
                if isinstance(v, list):
                    for n in v:
                        self.assertIn(n, existing, (sev, k))

    def test_s4_is_heaviest(self):
        s = self.SPEC["levels"]
        self.assertEqual(s["S0"].get("Pipe_Burst", []), [])
        self.assertGreaterEqual(len(s["S4"]["Pipe_Burst"]), 5)
        self.assertGreaterEqual(len(s["S4"]["Wire_Snapped"]), 6)
        self.assertGreaterEqual(len(s["S4"]["Fire_Socket"]), 2)
        self.assertEqual(len(s["S4"]["AlarmBeacon"]), 4)
        self.assertTrue(s["S4"]["power_flicker"])
        peaks = [s[k]["red_light_peak"] for k in damage.SEVERITIES]
        self.assertEqual(peaks, sorted(peaks))
        self.assertEqual(peaks[-1], 1.0)

    def test_dead_and_glitch_disjoint(self):
        for lv in self.SPEC["levels"].values():
            self.assertFalse(set(lv.get("Mon_dead", [])) & set(lv.get("Mon_glitch", [])))

    def test_shake_limits_match_task022(self):
        self.assertEqual(self.SPEC["shake"]["limits"], {"max_pos_cm": 12.0, "max_rot_deg": 4.0, "reduce_motion_mult": 0.25})

    def test_deterministic(self):
        self.assertEqual(json.dumps(self.SPEC, sort_keys=True), json.dumps(metrics.spec_doc(MODEL), sort_keys=True))


class Masks(unittest.TestCase):
    def test_masks(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            res = cracks.write_masks(d)
            self.assertEqual(len(res), 4)
            for p, n in res:
                self.assertLess(n, 1_000_000)
                with open(p, "rb") as f:
                    head = f.read(24)
                self.assertEqual(head[:8], b"\x89PNG\r\n\x1a\n")
                self.assertEqual(int.from_bytes(head[16:20], "big"), 1024)
                self.assertEqual(int.from_bytes(head[20:24], "big"), 1024)

    def test_masks_deterministic(self):
        import tempfile
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            cracks.write_masks(a)
            cracks.write_masks(b)
            for k in range(4):
                n = "Glass_Crack_Mask_%02d.png" % k
                self.assertEqual(open(os.path.join(a, n), "rb").read(), open(os.path.join(b, n), "rb").read())


@unittest.skipUnless(os.path.exists(os.path.join(OUT, "cockpit_metrics.json")), "run build_cockpit_v2.py first")
class BuiltOutputs(unittest.TestCase):
    def test_glass_share(self):
        m = json.load(open(os.path.join(OUT, "cockpit_metrics.json")))
        self.assertGreaterEqual(m["glass_share_percent"], 70.0)

    def test_metrics_match_model(self):
        m = json.load(open(os.path.join(OUT, "cockpit_metrics.json")))
        self.assertEqual(m["triangles_total"], metrics.triangles(MODEL)[1])
        self.assertEqual(m["counts"], metrics.kind_counts(MODEL))

    def test_parts_json_matches(self):
        d = json.load(open(os.path.join(OUT, "cockpit_parts.json")))
        self.assertEqual([r["name"] for r in d["parts"]], [p.name for p in MODEL.parts])

    def test_spec_file_matches(self):
        d = json.load(open(os.path.join(OUT, "cockpit_damage_spec.json")))
        self.assertEqual(d, json.loads(json.dumps(metrics.spec_doc(MODEL))))

    def test_export_size(self):
        total = sum(os.path.getsize(os.path.join(OUT, f)) for f in os.listdir(OUT))
        self.assertLess(total, 25 * 1024 * 1024)


if __name__ == "__main__":
    unittest.main()
