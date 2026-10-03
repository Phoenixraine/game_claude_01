"""Audio acceptance tests: run `python -m unittest discover audio/tests` (or pytest) from the repo root.

They check the files on disk against the manifest and the physical limits from TASK-005 (no clipping, seamless loops,
durations, level, determinism). Missing files (e.g. the >5 MB music loop, which is not committed) are built on demand.
"""
import json
import subprocess
import sys
import unittest
from pathlib import Path

import numpy as np

AUDIO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AUDIO))

from build_all import load  # noqa: E402
from gen import dsp, render  # noqa: E402

OUT = AUDIO / "out"
REQUIRED = """
mech_step_heavy_01 mech_step_heavy_02 mech_step_heavy_03 mech_step_heavy_04 mech_step_water_01 mech_step_water_02
mech_step_rubble_01 mech_step_rubble_02 mech_servo_arm_windup mech_servo_arm_strike mech_hydraulic_release
mech_stabilizer_whine mech_power_shift mech_weapon_charge_loop mech_weapon_charge_peak mech_weapon_fire
mech_joint_creak_01 mech_joint_creak_02 mech_joint_creak_03 mech_armor_plate_tear mech_limb_sever
hit_metal_contact_light hit_metal_contact_heavy hit_lowfreq_thump_light hit_lowfreq_thump_heavy hit_deform_01
hit_deform_02 hit_deform_03 hit_cockpit_rumble_light hit_cockpit_rumble_heavy hit_compensator_kick
hit_debris_delay_01 hit_debris_delay_02 hit_debris_delay_03 parry_clang intercept_clash block_impact clinch_grind_loop
cockpit_reactor_loop cockpit_breath_loop cockpit_harness_creak cockpit_switch_01 cockpit_switch_02 cockpit_switch_03
cockpit_switch_04 cockpit_alarm_warning cockpit_alarm_critical cockpit_coolant_leak_loop cockpit_spark_01
cockpit_spark_02 cockpit_spark_03 cockpit_spark_04 cockpit_panel_burst cockpit_sensor_fail_static cockpit_sensor_boot
cockpit_hud_lock cockpit_hud_unlock env_building_collapse_start env_building_collapse_mid env_building_collapse_end
env_glass_shatter_big env_concrete_crumble env_car_crush env_wave_big env_water_loop_sea env_rain_loop
env_wind_loop_city env_siren_distant_loop env_substation_arc env_missile_incoming env_missile_explosion
env_distant_boom_01 env_distant_boom_02 env_distant_boom_03 ui_move ui_confirm ui_back ui_deny ui_hangar_ambience_loop
mus_contact_theme_loop mus_tension_pulse_loop mus_commit_hit
""".split()


def setUpModule():
    reg = load()
    missing = [i for i in reg if not (OUT / (i + ".wav")).exists()]
    if missing or not (AUDIO / "manifest.json").exists():
        for i in missing:
            subprocess.run([sys.executable, str(AUDIO / "build_all.py"), "--only", i, "--jobs", "1", "--no-spectrograms"], check=True)
        subprocess.run([sys.executable, str(AUDIO / "build_all.py"), "--only", "__none__", "--no-spectrograms"], check=True)


def _manifest():
    return json.loads((AUDIO / "manifest.json").read_text(encoding="utf-8"))


class TestManifest(unittest.TestCase):
    def test_required_ids_present_and_nothing_unlisted(self):
        ids = [s["id"] for s in _manifest()["sounds"]]
        self.assertEqual(len(ids), len(set(ids)), "duplicate ids")
        self.assertEqual(sorted(set(REQUIRED) - set(ids)), [], "required sounds missing from the manifest")
        files = sorted(p.stem for p in OUT.glob("*.wav"))
        self.assertEqual(files, sorted(ids), "WAV files on disk and manifest entries differ")
        self.assertEqual(sorted(ids), sorted(load().keys()), "registry and manifest differ (rebuild?)")

    def test_fields_and_buses(self):
        for s in _manifest()["sounds"]:
            for k in ("id", "file", "duration_s", "loop", "bus", "volume_db", "attenuation_radius_m", "variation_group"):
                self.assertIn(k, s)
            self.assertIn(s["bus"], ("sfx_ext", "sfx_cockpit", "ambient", "ui", "music"), s["id"])
            self.assertTrue(np.isfinite(s["volume_db"]), s["id"])
            self.assertEqual(s["file"], "out/%s.wav" % s["id"])
            if s["bus"] == "sfx_ext":
                self.assertGreater(s["attenuation_radius_m"], 0, s["id"] + ": 3D sounds need an attenuation radius")
                self.assertEqual(s["channels"], 1, s["id"] + ": 3D sources must be mono")
            if s["bus"] in ("sfx_cockpit", "music") or s["id"].endswith("_loop") and s["bus"] == "ambient":
                self.assertEqual(s["channels"], 2, s["id"] + ": interior/ambient/music are stereo")

    def test_variation_groups(self):
        groups = {}
        for s in _manifest()["sounds"]:
            groups.setdefault(s["variation_group"], []).append(s["id"])
        self.assertEqual(len(groups["mech_step_heavy"]), 4)
        self.assertEqual(len(groups["cockpit_spark"]), 4)
        self.assertEqual(len(groups["env_distant_boom"]), 3)

    def test_total_size(self):
        total = sum(p.stat().st_size for p in OUT.glob("*.wav"))
        self.assertLessEqual(total, 120 * 1024 * 1024)

    def test_spectrogram_per_group(self):
        groups = {s["variation_group"] for s in _manifest()["sounds"]}
        have = {p.stem for p in (OUT / "spectrograms").glob("*.png")}
        if not have:
            self.skipTest("spectrograms not built (matplotlib missing?)")
        self.assertEqual(sorted(groups - have), [])


class TestFiles(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reg = load()
        cls.items = []
        for s in _manifest()["sounds"]:
            x, sr = render.read_wav(OUT / (s["id"] + ".wav"))
            cls.items.append((s, x, sr))

    def test_format_and_duration(self):
        for s, x, sr in self.items:
            snd = self.reg[s["id"]]
            self.assertEqual(sr, 48000, s["id"])
            self.assertEqual(x.ndim, s["channels"], s["id"])
            dur = len(x) / sr
            self.assertAlmostEqual(dur, s["duration_s"], places=2, msg=s["id"])
            lo, hi = snd.dur_range
            self.assertGreaterEqual(dur, lo - 1e-3, "%s too short: %.2f s" % (s["id"], dur))
            self.assertLessEqual(dur, hi + 1e-3, "%s too long: %.2f s" % (s["id"], dur))
            if s["loop"]:
                self.assertTrue(8.0 <= dur <= 60.0, s["id"])

    def test_no_clipping_finite_and_not_silent(self):
        for s, x, _ in self.items:
            self.assertTrue(np.isfinite(x).all(), s["id"])
            peak = np.max(np.abs(x))
            self.assertLess(peak, 0.95, "%s peaks at %.1f dBFS" % (s["id"], render.db(peak)))
            self.assertEqual(int(np.sum(np.abs(x) >= 32767 / 32768.0)), 0, s["id"] + ": full-scale samples")
            self.assertGreater(render.db(render.rms(x)), -45.0, s["id"] + " is nearly silent")

    def test_no_dc_offset(self):
        for s, x, _ in self.items:
            self.assertLess(np.max(np.abs(np.mean(x, axis=0))), 0.01, s["id"])

    def test_one_shots_start_and_end_at_silence(self):
        for s, x, _ in self.items:
            if s["loop"]:
                continue
            m = np.abs(x if x.ndim == 1 else x.max(axis=1))
            self.assertLess(m[0], 0.02, s["id"] + ": click at start")
            self.assertLess(m[-1], 0.002, s["id"] + ": click at end")

    def test_loops_are_seamless(self):
        """The jump across the loop point must be no bigger than the natural sample-to-sample movement of the signal."""
        for s, x, _ in self.items:
            if not s["loop"]:
                continue
            cols = [x] if x.ndim == 1 else [x[:, 0], x[:, 1]]
            for c in cols:
                seam = abs(c[0] - c[-1])
                p99 = np.percentile(np.abs(np.diff(c)), 99.5)
                self.assertLessEqual(seam, max(0.01, 3.0 * p99), "%s: seam jump %.4f vs p99.5 step %.4f" % (s["id"], seam, p99))

    def test_loop_seam_energy_is_continuous(self):
        """Short-time RMS 50 ms before vs after the loop point must agree (no level dip from a bad cross-fade)."""
        w = dsp.n(0.05)
        for s, x, _ in self.items:
            if not s["loop"]:
                continue
            m = x if x.ndim == 1 else x.mean(axis=1)
            a, b = render.rms(m[-w:]), render.rms(m[:w])
            ref = render.rms(m)
            self.assertLess(abs(a - b), 0.6 * ref + 1e-4, "%s: level jump at the seam" % s["id"])

    def test_loop_levels_matched(self):
        for s, x, _ in self.items:
            if s["loop"]:
                target = -18.0 if s["bus"] == "music" else -20.0
                self.assertAlmostEqual(render.db(render.rms(x)), target, delta=0.6, msg=s["id"])

    def test_mass_sounds_live_in_the_lows(self):
        """§24: size and mass = 25-90 Hz and long tails. Check the footsteps/thumps carry real energy there."""
        from scipy import signal
        for sid in ("mech_step_heavy_01", "mech_step_heavy_02", "hit_lowfreq_thump_heavy", "env_distant_boom_01", "mech_limb_sever"):
            x = next(x for s, x, _ in self.items if s["id"] == sid)
            m = x if x.ndim == 1 else x.mean(axis=1)
            f, p = signal.welch(m, 48000, nperseg=8192)
            share = p[(f >= 25) & (f <= 120)].sum() / p.sum()
            self.assertGreater(share, 0.25, "%s: only %.0f%% of the energy in 25-120 Hz" % (sid, share * 100))

    def test_variants_differ(self):
        by = {}
        for s, x, _ in self.items:
            by.setdefault(s["variation_group"], []).append(x)
        for g, xs in by.items():
            for i in range(len(xs)):
                for j in range(i + 1, len(xs)):
                    L = min(len(xs[i]), len(xs[j]))
                    a, b = xs[i][:L], xs[j][:L]
                    self.assertFalse(np.array_equal(a, b), g + ": identical variants")


class TestDeterminism(unittest.TestCase):
    def test_rebuild_is_bit_identical(self):
        reg = load()
        for sid in ("ui_confirm", "cockpit_spark_02", "hit_metal_contact_light", "mech_servo_arm_strike"):
            x = render.render(reg[sid])
            on_disk, _ = render.read_wav(OUT / (sid + ".wav"))
            self.assertTrue(np.array_equal(render.to_int16(x), np.round(on_disk * 32768).astype("<i2")), sid)

    def test_rng_is_per_id(self):
        a = dsp.rng_for("a").random(4)
        self.assertTrue(np.array_equal(a, dsp.rng_for("a").random(4)))
        self.assertFalse(np.array_equal(a, dsp.rng_for("b").random(4)))


class TestDsp(unittest.TestCase):
    def test_make_loop_is_continuous(self):
        rng = dsp.rng_for("loop-test")
        y = dsp.make_loop(lambda N: dsp.sine(220.0, N) + 0.2 * dsp.lp(dsp.white(rng, N), 2000, 2), 2.0, 0.3)
        self.assertEqual(len(y), dsp.n(2.0))
        self.assertLess(abs(y[0] - y[-1]), 0.15)

    def test_filters_do_what_they_say(self):
        rng = dsp.rng_for("filter-test")
        x = dsp.white(rng, 48000)
        lo = dsp.lp(x, 500, 4)
        spec = np.abs(np.fft.rfft(lo)) ** 2
        f = np.fft.rfftfreq(len(lo), 1 / 48000)
        self.assertLess(spec[f > 2000].sum() / spec.sum(), 1e-4)


if __name__ == "__main__":
    unittest.main()
