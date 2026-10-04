"""Glass HUD tests: contracts, identifiers, layout (no overlaps, free centre, three aspect ratios), contrast, event names vs core/include/iv/Events.h, file sizes, determinism.
Run from the repository root: python3 -m unittest discover -s ui/glass_hud/tests -v"""
import hashlib
import itertools
import json
import os
import re
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
REPO = os.path.normpath(os.path.join(ROOT, "..", ".."))
sys.path.insert(0, ROOT)

from lib import data, masks, presets, scene, shapes  # noqa: E402
from lib.svgkit import contrast  # noqa: E402

PAL = data.PALETTE["colors"]
ASPECT_SIZES = {"16:9": (1920, 1080), "21:9": (2520, 1080), "16:10": (1728, 1080)}


def load(name):
    with open(os.path.join(ROOT, name), encoding="utf-8") as f:
        return json.load(f)


def overlap(a, b):
    return not (a[0] + a[2] <= b[0] + 1e-6 or b[0] + b[2] <= a[0] + 1e-6 or a[1] + a[3] <= b[1] + 1e-6 or b[1] + b[3] <= a[1] + 1e-6)


class Identifiers(unittest.TestCase):
    def test_zone_ids_in_silhouettes(self):
        for side in ("player", "enemy"):
            svg = shapes.silhouette(side)
            for z in data.ZONES:
                self.assertIn('id="zone_%s"' % z, svg)
        self.assertEqual(len(data.ZONES), 9)

    def test_zone_names_match_core(self):
        src = open(os.path.join(REPO, "core/include/iv/Types.h"), encoding="utf-8").read()
        m = re.search(r"enum class Zone : uint8_t \{([^}]*)\}", src)
        core = [t.strip() for t in m.group(1).split(",") if t.strip() and t.strip() != "Count"]
        self.assertEqual(core, data.ZONES)
        m = re.search(r"enum class ZoneState : uint8_t \{([^}]*)\}", src)
        self.assertEqual([t.strip() for t in m.group(1).split(",")], data.ZONE_STATES)

    def test_layer_arcs_cover_zone_layer(self):
        for side in ("player", "enemy"):
            svg = shapes.layer_arcs(side)
            for z in data.ZONES:
                for l in data.LAYERS:
                    self.assertIn('id="arc_%s_%s"' % (z, l), svg)

    def test_every_state_has_a_style(self):
        st = data.STATES["zone_state_style"]
        self.assertEqual(sorted(st), sorted(data.ZONE_STATES))
        for s in data.ZONE_STATES:
            self.assertIn(st[s]["color"], PAL)

    def test_states_distinguishable_without_colour(self):
        """Colour-blind safety: every state differs from its neighbour by dash, width or blink, not by colour alone."""
        st = data.STATES["zone_state_style"]
        sig = {s: (st[s]["dash"], st[s]["width"], st[s]["blink_hz"], st[s].get("slash", False)) for s in data.ZONE_STATES}
        self.assertEqual(len(set(sig.values())), len(sig))


class Contracts(unittest.TestCase):
    def test_json_files_exist_and_parse(self):
        for f in ("palette.json", "states.json", "layout.json", "schema.json", "assets_manifest.json"):
            self.assertIsInstance(load(f), dict)

    def test_committed_json_equals_generator(self):
        from build_hud import layout_doc, schema_doc
        self.assertEqual(load("layout.json"), json.loads(json.dumps(layout_doc())))
        self.assertEqual(load("schema.json"), json.loads(json.dumps(schema_doc())))
        self.assertEqual(load("palette.json"), json.loads(json.dumps(data.PALETTE)))
        self.assertEqual(load("states.json"), json.loads(json.dumps(data.STATES)))

    def test_layout_follows_schema(self):
        lay, sch = load("layout.json"), load("schema.json")
        for k in sch["required"]:
            self.assertIn(k, lay)
        item = sch["properties"]["elements"]["items"]
        for el in lay["elements"]:
            for k in item["required"]:
                self.assertIn(k, el)
            self.assertIn(el["anchor"], item["properties"]["anchor"]["enum"])
            self.assertEqual(len(el["rect"]), 4)
            self.assertTrue(all(0 <= v <= 1 for v in el["rect"]))
            self.assertLessEqual(el["rect"][0] + el["rect"][2], 1.0 + 1e-9)
            self.assertLessEqual(el["rect"][1] + el["rect"][3], 1.0 + 1e-9)

    def test_referenced_files_exist(self):
        lay = load("layout.json")
        files = [e["file"] for e in lay["elements"]] + [e["file"] for e in lay["world_elements"]]
        for l in lay["fullscreen_layers"]:
            files += l.get("files", []) + ([l["file"]] if "file" in l else [])
        for f in files:
            self.assertTrue(os.path.exists(os.path.join(ROOT, f)), f)

    def test_required_deliverables(self):
        names = ["silhouette_body_player.svg", "silhouette_body_enemy.svg", "zone_layers_arcs.svg", "lockon_corners.svg", "lockon_ring_anim_strip.png", "ultimate_gauge.svg",
                 "alarm_frame.png"] + ["bar_%s.png" % k for k in ("armor", "stability", "heat", "energy")] + ["weapon_icons_%s.svg" % k for k in ("rockets", "rail", "plasma")] + \
                ["status_icons_%s.svg" % k for k in ("blind", "strikelock", "burn")] + ["threat_arrows_%s.svg" % d for d in ("up", "left", "right", "down")] + \
                ["glitch_strip_%02d.png" % i for i in range(8)] + ["crack_mask_%02d.png" % i for i in range(8)] + ["soot_mask_%02d.png" % i for i in range(4)] + ["rain_drops_atlas.png"]
        have = set(os.listdir(os.path.join(ROOT, "svg"))) | set(os.listdir(os.path.join(ROOT, "png")))
        for n in names:
            self.assertIn(n, have)
        self.assertEqual(len([n for n in have if n.startswith("crack_mask_")]), 8)

    def test_event_names_exist_in_core(self):
        src = open(os.path.join(REPO, "core/include/iv/Events.h"), encoding="utf-8").read()
        body = re.search(r"enum class EventType : uint8_t \{(.*?)\n\};", src, re.S).group(1)
        core = set(re.findall(r"^\s+([A-Za-z0-9]+),", body, re.M))
        for ev, _, _ in data.BINDINGS:
            self.assertIn(ev, core, ev)

    def test_bindings_cover_core_ui_events(self):
        have = {e for e, _, _ in data.BINDINGS}
        for must in ("ZoneState", "HitEvent", "ArmorPlateLost", "ReactorBreach", "SystemFailure", "LimbSevered", "StatusApplied", "WeaponReady", "UltimateReady", "EnergyShift", "HeatWarning", "MatchEnd"):
            self.assertIn(must, have)

    def test_no_text_elements(self):
        for sub in ("svg",):
            for f in os.listdir(os.path.join(ROOT, sub)):
                self.assertNotIn("<text", open(os.path.join(ROOT, sub, f), encoding="utf-8").read(), f)


class Layout(unittest.TestCase):
    def test_no_overlaps_all_aspects(self):
        for name, (W, H) in ASPECT_SIZES.items():
            R = scene.all_rects(W, H)
            for (ia, a), (ib, b) in itertools.combinations(R.items(), 2):
                el = {e["id"]: e for e in data.ELEMENTS}
                if el[ia].get("overlay_of") == ib or el[ib].get("overlay_of") == ia:
                    continue
                self.assertFalse(overlap(a, b), "%s: %s overlaps %s" % (name, ia, ib))

    def test_inside_screen_and_safe_margin(self):
        for name, (W, H) in ASPECT_SIZES.items():
            for i, r in scene.all_rects(W, H).items():
                self.assertGreaterEqual(r[0], 0.0, (name, i))
                self.assertGreaterEqual(r[1], 0.0, (name, i))
                self.assertLessEqual(r[0] + r[2], W + 1e-6, (name, i))
                self.assertLessEqual(r[1] + r[3], H + 1e-6, (name, i))

    def test_free_centre(self):
        """The central 60 % x 60 % of the frame holds no persistent element (lock-on, strike arc and crosshair are world / central elements by design)."""
        for name, (W, H) in ASPECT_SIZES.items():
            fc = scene.free_center_px(W, H)
            for i, r in scene.all_rects(W, H, True).items():
                self.assertFalse(overlap(fc, r), "%s: %s enters the free centre" % (name, i))

    def test_coverage_budget(self):
        for name, (W, H) in ASPECT_SIZES.items():
            area = sum(r[2] * r[3] for i, r in scene.all_rects(W, H, True).items() if not any(e["id"] == i and e.get("overlay_of") for e in data.ELEMENTS))
            self.assertLess(area / (W * H), data.MAX_PERSISTENT_COVERAGE, name)

    def test_threat_arrows_clear_of_hud_and_centre(self):
        for name, (W, H) in ASPECT_SIZES.items():
            R = scene.all_rects(W, H, True)
            for d in ("up", "down", "left", "right"):
                t = scene.threat_rect(d, W, H)
                for i, r in R.items():
                    self.assertFalse(overlap(t, r), "%s: arrow %s hits %s" % (name, d, i))
                self.assertGreaterEqual(t[0], 0)
                self.assertLessEqual(t[0] + t[2], W)

    def test_corners_hold_what_the_task_asks(self):
        ids = {e["id"]: e["anchor"] for e in data.ELEMENTS}
        self.assertEqual(ids["body_player"], "top_left")
        self.assertEqual(ids["body_enemy"], "top_right")
        self.assertEqual(ids["gauge_armor"], "bottom_left")
        self.assertEqual(ids["radar"], "bottom_right")
        self.assertEqual(ids["ultimate"], "bottom_right")

    def test_circular_widgets_are_square_in_pixels(self):
        for el in data.ELEMENTS:
            if el["id"].startswith("gauge_") or el["id"] in ("radar", "ultimate"):
                x, y, w, h = scene.element_rect_px(el, 1920, 1080)
                self.assertAlmostEqual(w / h, 1.0, delta=0.03, msg=el["id"])


class Contrast(unittest.TestCase):
    def test_core_colours_on_dark(self):
        need = data.PALETTE["min_contrast"]["core_on_dark"]
        for name, col in PAL.items():
            if name in ("ink", "bg_dark", "bg_mid", "bg_light"):
                continue
            self.assertGreaterEqual(contrast(col, PAL["bg_dark"]), need, name)

    def test_halo_on_light(self):
        self.assertGreaterEqual(contrast(PAL["ink"], PAL["bg_light"]), data.PALETTE["min_contrast"]["halo_on_light"])

    def test_zone_state_colours_on_mid_background(self):
        """Thin lines over a mid-grey city: every state colour still reaches 2:1 with the dark halo helping on top."""
        for s, c in data.PALETTE["zone_state"].items():
            self.assertGreaterEqual(contrast(PAL[c], PAL["bg_mid"]), 2.0, s)

    def test_state_colours_distinct(self):
        cols = [data.PALETTE["zone_state"][s] for s in ("Intact", "Exposed", "Damaged", "Critical", "Destroyed")]
        self.assertEqual(len(set(cols)), 5)


class Render(unittest.TestCase):
    def test_presets_render_and_differ(self):
        sizes = {}
        for name, fn in presets.PRESETS.items():
            svg = scene.hud_svg(fn(), 960, 540)
            self.assertTrue(svg.startswith("<svg"))
            sizes[name] = len(svg)
        self.assertEqual(len(set(sizes.values())), len(sizes))

    def test_aspect_markup_renders(self):
        for name, (W, H) in ASPECT_SIZES.items():
            rgba = scene.svg_to_rgba(scene.hud_svg(presets.critical(), W // 3, H // 3), W // 3, H // 3)
            self.assertEqual(rgba.shape, (H // 3, W // 3, 4))
            self.assertGreater(rgba[..., 3].max(), 0.5)

    def test_hud_does_not_paint_the_free_centre(self):
        """Rendered alpha of the vector HUD without lock-on / strike line is empty in the free centre except the 24 px crosshair."""
        st = presets.fight_ok()
        W, H = 960, 540
        rgba = scene.svg_to_rgba(scene.hud_svg(st, W, H), W, H)
        fx, fy, fw, fh = scene.free_center_px(W, H)
        cx, cy = W / 2, H / 2
        sub = rgba[int(fy):int(fy + fh), int(fx):int(fx + fw), 3].copy()
        sub[int(cy - fy - 14):int(cy - fy + 14), int(cx - fx - 14):int(cx - fx + 14)] = 0   # the crosshair
        self.assertLess(float((sub > 0.05).mean()), 0.001)

    def test_frame_composes(self):
        frame = scene.compose_frame(presets.critical(), 640, 360)
        self.assertEqual(frame.shape, (360, 640, 3))

    def test_critical_blinks(self):
        a = scene.hud_svg(dict(presets.critical(), blink=True), 640, 360)
        b = scene.hud_svg(dict(presets.critical(), blink=False), 640, 360)
        self.assertNotEqual(a, b)


class Masks(unittest.TestCase):
    def test_gauge_mask_progress_is_monotonic(self):
        m = masks.gauge_mask("stability")
        self.assertEqual(m.shape, (256, 256, 4))
        ring = m[..., 3] > 200
        self.assertGreater(ring.sum(), 500)
        # sample along the ring centre line: R grows with the angle from the start (lower left) clockwise
        import math
        vals = []
        for deg in range(0, 270, 10):
            a = math.radians(135 + deg)
            x, y = int(128 + 98 * math.cos(a)), int(128 + 98 * math.sin(a))
            vals.append(int(m[y, x, 0]))
        self.assertEqual(vals, sorted(vals))
        self.assertGreater(vals[-1], 200)
        self.assertLess(vals[0], 20)

    def test_masks_deterministic(self):
        self.assertEqual(hashlib.sha256(masks.crack_mask(5).tobytes()).hexdigest(), hashlib.sha256(masks.crack_mask(5).tobytes()).hexdigest())
        self.assertNotEqual(masks.crack_mask(5).tobytes(), masks.crack_mask(6).tobytes())

    def test_crack_masks_look_like_cracks(self):
        for i in range(8):
            from PIL import Image
            im = Image.open(os.path.join(ROOT, "png/crack_mask_%02d.png" % i))
            self.assertEqual(im.size, (1024, 1024))
            import numpy as np
            a = np.asarray(im)
            frac = float((a > 128).mean())
            self.assertGreater(frac, 0.002, i)
            self.assertLess(frac, 0.15, i)

    def test_alarm_frame_centre_transparent(self):
        a = masks.alarm_frame()
        h, w = a.shape[:2]
        self.assertLess(int(a[h // 2, w // 2, 3]), 3)
        self.assertGreater(int(a[0, w // 2, 3]), 150)


class Files(unittest.TestCase):
    def test_sizes(self):
        for sub in ("svg", "png", "previews"):
            for f in os.listdir(os.path.join(ROOT, sub)):
                self.assertLess(os.path.getsize(os.path.join(ROOT, sub, f)), 5 * 1024 * 1024, f)

    def test_total_size_budget(self):
        total = sum(os.path.getsize(os.path.join(ROOT, sub, f)) for sub in ("svg", "png", "previews") for f in os.listdir(os.path.join(ROOT, sub)))
        self.assertLess(total, 12 * 1024 * 1024)

    def test_png_dimensions(self):
        from PIL import Image
        self.assertEqual(Image.open(os.path.join(ROOT, "png/lockon_ring_anim_strip.png")).size, (512, 512))
        self.assertEqual(Image.open(os.path.join(ROOT, "png/rain_drops_atlas.png")).size, (1024, 1024))
        self.assertEqual(Image.open(os.path.join(ROOT, "png/bar_armor.png")).size, (256, 256))
        for f in os.listdir(os.path.join(ROOT, "png")):
            if f.endswith(".png"):
                w, h = Image.open(os.path.join(ROOT, "png", f)).size
                self.assertLessEqual(max(w, h), 2048, f)

    def test_manifest_matches_files(self):
        man = load("assets_manifest.json")
        for row in man["files"]:
            p = os.path.join(ROOT, row["path"])
            self.assertTrue(os.path.exists(p), row["path"])
            self.assertEqual(os.path.getsize(p), row["bytes"], row["path"])
            self.assertEqual(hashlib.sha256(open(p, "rb").read()).hexdigest()[:16], row["sha256"], row["path"])


class Determinism(unittest.TestCase):
    def test_svgs_reproduce(self):
        import build_hud
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "svg"))
            build_hud.build_svgs(d)
            for f in os.listdir(os.path.join(d, "svg")):
                self.assertEqual(open(os.path.join(d, "svg", f), "rb").read(), open(os.path.join(ROOT, "svg", f), "rb").read(), f)


if __name__ == "__main__":
    unittest.main()
