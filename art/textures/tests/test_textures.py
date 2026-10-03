"""Texture acceptance tests. They build everything at 1/8 resolution (a few seconds) into a temp dir and check the physics of the
maps: seamless tiles, unit normals, ORM ranges, decal borders, flipbooks, LUTs, masks, trim regions, determinism."""
import hashlib
import json
import math
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))

from lib import maps, materials, noise  # noqa: E402

TMP = None
MAN = None

MATERIAL_NAMES = ["graphite_armor_worn", "ceramic_gray_panels", "dark_metal_scratched", "basalt_armor_worn", "hydraulic_steel", "rubber_black",
                  "concrete_weathered", "concrete_cracked", "asphalt_wet", "asphalt_cracked", "sidewalk_tiles", "brick_facade", "glass_curtain_wall",
                  "rusty_steel_plate", "corrugated_metal", "container_painted_worn", "water_foam_mask", "gravel_rubble"]
VFX_NAMES = ["smoke_dark", "smoke_light", "collapse_dust", "coolant_steam", "sparks", "water_splash_impact", "water_splash_wide", "fire_smoke",
             "electric_arc", "glass_shards", "missile_explosion", "rain_drops", "wave_ring", "projectile_trail"]


def setUpModule():
    global TMP, MAN
    TMP = tempfile.TemporaryDirectory()
    subprocess.run([sys.executable, str(HERE / "build_all.py"), "--scale", "8", "--out", TMP.name, "--no-previews"], check=True, capture_output=True)
    with open(os.path.join(TMP.name, "manifest.json")) as f:
        MAN = json.load(f)


def tearDownModule():
    TMP.cleanup()


def P(rel):
    return os.path.join(TMP.name, rel[len("out/"):] if rel.startswith("out/") else rel)


def load(rel):
    return maps.load_png(P(rel))


class TestManifest(unittest.TestCase):
    def test_all_materials_present_with_four_maps(self):
        names = [m["name"] for m in MAN["materials"]]
        self.assertEqual(names, MATERIAL_NAMES)
        for m in MAN["materials"]:
            self.assertEqual(sorted(m["files"]), ["BaseColor", "Height", "Normal", "ORM"])
            for k, v in m["files"].items():
                self.assertTrue(os.path.exists(P(v["file"])), v["file"])
                self.assertEqual(v["colorspace"], "sRGB" if k == "BaseColor" else "Linear")
            n = m["size"]
            self.assertEqual(n & (n - 1), 0, "size must be a power of two")

    def test_full_resolution_manifest_is_committed_and_matches(self):
        with open(HERE / "manifest.json") as f:
            full = json.load(f)
        self.assertEqual([m["name"] for m in full["materials"]], MATERIAL_NAMES)
        self.assertEqual(full["sizes"]["material"], 2048)
        self.assertEqual(full["sizes"]["trim"], 4096)
        self.assertEqual([v["name"] for v in full["vfx"]], VFX_NAMES)
        self.assertEqual(len(full["decals"]), len(MAN["decals"]))
        self.assertTrue((HERE / "previews" / "vfx.png").exists())

    def test_decal_set_has_the_required_families(self):
        names = [d["name"] for d in MAN["decals"]]
        for prefix, count in (("scratch_", 4), ("dent_", 4), ("burn_", 4), ("fluid_", 4), ("salt_streak_", 4), ("hazard_stripes_", 3), ("panel_seam_", 3),
                              ("vent_grille_", 3), ("plate_blank_", 3)):
            self.assertEqual(sum(n.startswith(prefix) for n in names), count, prefix)
        self.assertGreaterEqual(sum(n.startswith("mark_") for n in names), 6)


class TestMaterials(unittest.TestCase):
    def test_tiles_are_seamless(self):
        for m in MAN["materials"]:
            for k, v in m["files"].items():
                a = load(v["file"])
                a = a if a.ndim == 3 else a[..., None]
                for axis in (0, 1):
                    seam = float(np.abs(np.take(a, 0, axis) - np.take(a, -1, axis)).mean())
                    # the wrap-around pair must be no worse than the WORST interior neighbour pair (features such as mortar lines
                    # centred on the tile edge legitimately have large steps there, in the interior as well)
                    steps = np.abs(np.diff(a, axis=axis)).mean(axis=tuple(i for i in range(a.ndim) if i != axis))
                    worst = float(steps.max())
                    self.assertLessEqual(seam, worst * 1.25 + 0.004, "%s %s axis %d: seam %.4f vs worst interior step %.4f" % (m["name"], k, axis, seam, worst))

    def test_normals_are_unit_length_and_face_up(self):
        for m in MAN["materials"]:
            c = load(m["files"]["Normal"]["file"]) * 2 - 1
            ln = np.linalg.norm(c, axis=-1)
            self.assertAlmostEqual(float(ln.mean()), 1.0, delta=0.02, msg=m["name"])
            self.assertLess(float(np.abs(ln - 1).max()), 0.06, m["name"])
            self.assertGreater(float(c[..., 2].min()), 0.0, m["name"])

    def test_normal_convention_is_opengl_y_plus(self):
        n = 64
        y, x = np.meshgrid(np.arange(n), np.arange(n), indexing="ij")
        h = np.exp(-(((x - 32) ** 2 + (y - 32) ** 2) / 120.0)).astype(np.float32)       # a bump
        nrm = maps.normal_from_height(h, 5.0)
        self.assertGreater(nrm[32, 40, 0], 0.05)       # right flank leans +X
        self.assertLess(nrm[32, 24, 0], -0.05)         # left flank leans -X
        self.assertGreater(nrm[24, 32, 1], 0.05)       # flank toward the image top leans +Y (up) - OpenGL convention
        self.assertLess(nrm[40, 32, 1], -0.05)
        self.assertAlmostEqual(float(nrm[32, 32, 2]), 1.0, places=2)

    def test_orm_ranges_and_variation(self):
        for m in MAN["materials"]:
            orm = load(m["files"]["ORM"]["file"])
            self.assertGreaterEqual(float(orm.min()), 0.0)
            self.assertLessEqual(float(orm.max()), 1.0)
            self.assertGreater(float(orm[..., 1].std()), 0.004, "%s: roughness is constant" % m["name"])
            self.assertTrue(float(orm[..., 1].min()) >= 0.02, "roughness must not hit 0")
        glass = load(next(m for m in MAN["materials"] if m["name"] == "glass_curtain_wall")["files"]["ORM"]["file"])
        self.assertLess(float(np.percentile(glass[..., 1], 50)), 0.2, "glass pane is smooth")
        rub = load(next(m for m in MAN["materials"] if m["name"] == "rubber_black")["files"]["ORM"]["file"])
        self.assertGreater(float(rub[..., 1].mean()), 0.7)
        self.assertLess(float(rub[..., 2].mean()), 0.05)
        steel = load(next(m for m in MAN["materials"] if m["name"] == "hydraulic_steel")["files"]["ORM"]["file"])
        self.assertGreater(float(steel[..., 2].mean()), 0.8)

    def test_base_color_brightness_is_sane(self):
        for m in MAN["materials"]:
            c = load(m["files"]["BaseColor"]["file"])
            mean = float(c.mean())
            self.assertGreater(float(c.std()), 0.004, "%s is flat" % m["name"])
            if m["name"] == "water_foam_mask":
                continue
            self.assertTrue(0.015 < mean < 0.75, "%s mean albedo %.3f" % (m["name"], mean))
        dark = {n: float(load(next(m for m in MAN["materials"] if m["name"] == n)["files"]["BaseColor"]["file"]).mean()) for n in ("graphite_armor_worn", "basalt_armor_worn", "ceramic_gray_panels")}
        self.assertLess(dark["basalt_armor_worn"], dark["graphite_armor_worn"] + 0.01, "the enemy basalt is darker than graphite")
        self.assertGreater(dark["ceramic_gray_panels"], dark["graphite_armor_worn"] * 3)

    def test_enemy_basalt_has_dark_red_marks(self):
        c = load(next(m for m in MAN["materials"] if m["name"] == "basalt_armor_worn")["files"]["BaseColor"]["file"])
        red = (c[..., 0] > c[..., 1] * 2.0) & (c[..., 0] > 0.2)
        self.assertGreater(float(red.mean()), 0.0005)

    def test_height_maps_are_not_constant(self):
        for m in MAN["materials"]:
            h = load(m["files"]["Height"]["file"])
            self.assertGreater(float(h.std()), 0.003, m["name"])
            self.assertTrue(0.0 <= float(h.min()) and float(h.max()) <= 1.0)


class TestDecals(unittest.TestCase):
    def test_alpha_is_zero_on_the_border_and_decal_is_not_empty(self):
        for d in MAN["decals"]:
            a = load(d["files"]["RGBA"]["file"])
            self.assertEqual(a.shape[-1], 4, d["name"])
            al = a[..., 3]
            for edge in (al[0], al[-1], al[:, 0], al[:, -1]):
                self.assertEqual(float(edge.max()), 0.0, d["name"])
            self.assertGreater(float(al.max()), 0.3, d["name"] + " is nearly empty")
            self.assertLess(float(al.mean()), 0.9, d["name"] + " fills the whole canvas")

    def test_normal_decals_carry_unit_normals_where_visible(self):
        for d in MAN["decals"]:
            if d["kind"] != "normal":
                continue
            a = load(d["files"]["RGBA"]["file"])
            vis = a[..., 3] > 0.5
            n = a[..., :3][vis] * 2 - 1
            self.assertGreater(len(n), 10, d["name"])
            self.assertAlmostEqual(float(np.linalg.norm(n, axis=-1).mean()), 1.0, delta=0.03, msg=d["name"])

    def test_marks_have_no_text_like_complexity(self):
        # marks are bold single shapes: few connected components (text would have many)
        from scipy import ndimage
        for d in MAN["decals"]:
            if d["name"].startswith("mark_"):
                al = load(d["files"]["RGBA"]["file"])[..., 3] > 0.3
                _, n = ndimage.label(al)
                self.assertLessEqual(n, 7, d["name"])


class TestVfx(unittest.TestCase):
    def test_atlases_have_64_distinct_frames_and_premultiplied_alpha(self):
        for v in MAN["vfx"]:
            a = load(v["file"])
            f = v["frame"]
            self.assertEqual(a.shape, (8 * f, 8 * f, 4), v["name"])
            self.assertEqual(v["frames"], 64)
            frames = [a[(i // 8) * f:(i // 8 + 1) * f, (i % 8) * f:(i % 8 + 1) * f] for i in range(64)]
            live = [fr for fr in frames if fr[..., 3].mean() > 1e-4]
            keys = {hashlib.md5(fr.tobytes()).hexdigest() for fr in live}
            self.assertGreaterEqual(len(live), 32, "%s: effect is visible for too few frames" % v["name"])
            self.assertEqual(len(keys), len(live), "%s: visible frames repeat" % v["name"])
            diff = np.mean([np.abs(frames[i] - frames[i + 1]).mean() for i in range(63)])
            self.assertGreater(float(diff), 2e-4, "%s barely animates" % v["name"])
            alpha = a[..., 3]
            self.assertGreater(float(alpha.max()), 0.3, v["name"])
            self.assertLessEqual(float((a[..., :3] - alpha[..., None]).max()), 0.02, "%s is not premultiplied (rgb > alpha)" % v["name"])
            self.assertTrue(v["premultiplied"])

    def test_animation_is_not_a_rotated_copy(self):
        # frame-to-frame structure changes (correlation between first active frame and a later one is far from 1)
        for name in ("smoke_dark", "water_splash_impact", "collapse_dust"):
            v = next(v for v in MAN["vfx"] if v["name"] == name)
            a = load(v["file"])
            f = v["frame"]
            fr = lambda i: a[(i // 8) * f:(i // 8 + 1) * f, (i % 8) * f:(i % 8 + 1) * f, 3].ravel()
            c = np.corrcoef(fr(12), fr(44))[0, 1]
            self.assertLess(c, 0.97, name)

    def test_effects_fade_out_unless_looping(self):
        for v in MAN["vfx"]:
            a = load(v["file"])
            f = v["frame"]
            last = a[7 * f:8 * f, 7 * f:8 * f, 3]
            peak = max(a[(i // 8) * f:(i // 8 + 1) * f, (i % 8) * f:(i % 8 + 1) * f, 3].mean() for i in range(64))
            if not v["loop"]:
                self.assertLess(float(last.mean()), 0.5 * peak + 0.005, v["name"] + " does not fade out")


class TestLutsMasksTrim(unittest.TestCase):
    def test_luts(self):
        heat = load(next(l for l in MAN["luts"] if l["name"] == "heat_lut")["file"])
        self.assertEqual(heat.shape, (1, 256, 4))
        self.assertGreater(heat[0, -1, :3].min(), 0.95)        # hottest = white
        self.assertLess(heat[0, 0, 0], 0.1)                    # coldest = deep blue
        self.assertGreater(heat[0, 0, 2], heat[0, 0, 0])
        dmg = load(next(l for l in MAN["luts"] if l["name"] == "damage_color_lut")["file"])
        self.assertEqual(dmg.shape, (2, 256, 4))
        steps = [np.array(s["rgb"]) for s in next(l for l in MAN["luts"] if l["name"] == "damage_color_lut")["steps"]]
        self.assertEqual(len(steps), 5)
        for i, c in enumerate(steps):
            px = dmg[0, int((i + 0.5) / 5 * 256), :3]
            self.assertTrue(np.allclose(px, c, atol=0.01), "band %d" % i)
        self.assertGreater(steps[0][2], steps[0][0])           # neutral is white-blue
        self.assertGreater(steps[1][0], 0.9)                   # yellow
        self.assertLess(steps[4].max(), 0.05)                  # lost = black
        self.assertGreater(steps[3][0], 0.9)
        self.assertLess(steps[3][1], 0.2)                      # critical = red

    def test_masks(self):
        self.assertEqual(len(MAN["masks"]), 12)
        for kind in ("Dent", "Crack", "Burn"):
            vs = [load(m["file"]) for m in MAN["masks"] if m["kind"] == kind]
            self.assertEqual(len(vs), 4)
            for a in vs:
                self.assertGreaterEqual(float(a.min()), 0.0)
                self.assertLessEqual(float(a.max()), 1.0)
                self.assertGreater(float(a.std()), 0.02)
            for i in range(4):
                for j in range(i + 1, 4):
                    self.assertGreater(float(np.abs(vs[i] - vs[j]).mean()), 0.005)
        z = MAN["mask_zone_variants"]
        self.assertEqual(sorted(z), ["ArmL", "ArmR", "Head", "LegL", "LegR", "Reactor", "ShoulderL", "ShoulderR", "Torso"])
        self.assertEqual(len({tuple(sorted(v.items())) for v in z.values()}), 9, "every zone gets a different mask combination")

    def test_trim_sheet_regions_tile_the_sheet(self):
        t = MAN["trim_sheet"]
        regs = t["regions"]
        self.assertEqual(len(regs), 16)
        ys = sorted((r["pixels"][1], r["pixels"][3]) for r in regs)
        self.assertEqual(ys[0][0], 0)
        self.assertEqual(ys[-1][1], t["size"])
        for (a0, a1), (b0, b1) in zip(ys, ys[1:]):
            self.assertEqual(a1, b0, "gap or overlap between strips")
        for r in regs:
            u0, v0, u1, v1 = r["uv_top_left"]
            self.assertTrue(0 <= u0 < u1 <= 1 and 0 <= v0 < v1 <= 1)
            b0, b1 = r["uv_bottom_left"][1], r["uv_bottom_left"][3]
            self.assertAlmostEqual(b0, 1 - v1, places=5)
        names = {r["name"] for r in regs}
        for n in ("panel_line_wide", "bevel_hard", "rivets_large", "slots_vent", "cable_channel", "screw_heads", "hazard_stripe"):
            self.assertIn(n, names)
        a = load(t["files"]["BaseColor"]["file"])
        self.assertLessEqual(float(np.abs(a[:, 0] - a[:, -1]).mean()), max(float(np.abs(a[:, 0] - a[:, 1]).mean()) * 1.8, 0.004), "trim strips tile along U")
        self.assertTrue(os.path.exists(os.path.join(TMP.name, "trim_sheet", "trim_sheet.json")))


class TestDeterminism(unittest.TestCase):
    def test_materials_rebuild_identically(self):
        for fn in (materials.graphite_armor_worn, materials.brick_facade, materials.water_foam_mask):
            a = materials.build_material(fn, 128)
            b = materials.build_material(fn, 128)
            self.assertTrue(np.array_equal(a.base, b.base) and np.array_equal(a.normal, b.normal) and np.array_equal(a.orm, b.orm))

    def test_png_bytes_are_reproducible(self):
        with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
            for d in (d1, d2):
                subprocess.run([sys.executable, str(HERE / "build_all.py"), "--scale", "16", "--only", "decal", "--out", d, "--no-previews"], check=True, capture_output=True)
            for p in sorted(Path(d1, "decals").glob("*.png"))[:6]:
                self.assertEqual(p.read_bytes(), Path(d2, "decals", p.name).read_bytes(), p.name)

    def test_noise_is_periodic(self):
        rng = noise.rng_for("p")
        for img in (noise.fbm(128, rng, 2, 1, 30), noise.worley(128, rng, 8)[0], noise.lines(128, rng, 30)):
            self.assertLessEqual(np.abs(img[:, 0] - img[:, -1]).mean(), max(np.abs(img[:, 0] - img[:, 1]).mean() * 1.8, 0.01))


if __name__ == "__main__":
    unittest.main()
