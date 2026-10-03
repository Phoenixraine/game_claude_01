"""Acceptance tests for the animation library: python -m unittest discover -s anim/tests (from the repo root)."""
import hashlib
import json
import math
import os
import sys
import unittest

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from anim import clips, curves, damage, export, locomotion, poses, rig, schema  # noqa: E402

SLIDE_LIMIT_MPS = 0.25          # a planted sole may creep by less than this (walk speed is 4-9 m/s)
POSES = poses.all_poses()
LIB = {p.name: p for p in POSES}
LOCO = locomotion.all_clips()


def _upper(p):
    return [b for b in rig.BONES if b != "root" and not b.startswith(("thigh", "shin", "foot"))]


class TestRig(unittest.TestCase):
    def test_bones_match_the_mech_contract(self):
        self.assertEqual(set(rig.BONES), set(["root", "pelvis", "torso", "head", "reactor"] + [
            "%s_%s" % (n, s) for s in "lr" for n in ("shoulder", "upperarm", "forearm", "hand", "thigh", "shin", "foot")]))
        self.assertEqual(rig.PARENT["reactor"], "torso")

    def test_limits_follow_the_spec_dof(self):
        L = rig.LIMITS
        self.assertEqual(L["forearm_l"]["x"], (-140, 0))     # elbow: 1 DoF, 0..140
        self.assertEqual(L["forearm_l"]["y"], (0, 0))
        self.assertEqual(L["shin_r"]["x"], (0, 120))         # knee: 1 DoF, 0..120
        self.assertEqual(L["shin_r"]["z"], (0, 0))
        self.assertEqual(L["head"]["y"], (0, 0))              # head: 2 DoF
        self.assertEqual(L["foot_l"]["z"], (0, 0))            # ankle: 2 DoF
        self.assertEqual(L["hand_l"]["z"], (0, 0))            # wrist: 2 DoF

    def test_euler_roundtrip(self):
        rng = np.random.default_rng(3)
        for _ in range(100):
            e = [rng.uniform(-80, 80), rng.uniform(-80, 80), rng.uniform(-170, 170)]
            e2 = rig.mat_to_euler(rig.euler_to_mat(e))
            self.assertTrue(np.allclose(rig.euler_to_mat(e2), rig.euler_to_mat(e), atol=1e-9))

    def test_fk_rest_is_identity(self):
        F = rig.fk({})
        for b in rig.BONES:
            self.assertTrue(np.allclose(F[b][:3, 3], rig.REST[b]))
        self.assertTrue(rig.foot_contacts(F)["l"]["ground"])

    def test_fk_knee_bends_the_heel_backwards(self):
        F = rig.fk({"shin_l": [60, 0, 0]})
        self.assertGreater(F["foot_l"][1, 3], rig.REST["foot_l"][1] + 10)

    def test_clamp_reports_hits(self):
        c, hits = rig.clamp_pose({"forearm_l": [30, 5, 0]})
        self.assertEqual(c["forearm_l"], [0, 0, 0])
        self.assertEqual(len(hits), 2)


class TestIK(unittest.TestCase):
    def test_leg_ik_reaches_random_reachable_targets(self):
        rng = np.random.default_rng(1)
        for _ in range(100):
            a = {"thigh_l": [rng.uniform(-45, 15), rng.uniform(-25, 5), rng.uniform(-10, 10)], "shin_l": [rng.uniform(5, 100), 0, 0]}
            F = rig.fk(a, (0, 0, rng.uniform(-8, 1)))
            sol = rig.solve_limb("leg", "l", F["pelvis"], F["foot_l"][:3, 3], foot_yaw=a["thigh_l"][2])
            self.assertTrue(sol["reachable"], sol["clamped"])
            self.assertLess(sol["error_m"], 1e-6)
            self.assertEqual(rig.limit_violations(sol["angles"]), [])

    def test_arm_ik_reaches_and_respects_elbow_limit(self):
        a = {"upperarm_r": [-70, 20, -10], "forearm_r": [-60, 0, 0]}
        F = rig.fk(a)
        sol = rig.solve_limb("arm", "r", F["shoulder_r"], F["hand_r"][:3, 3], foot_yaw=-10)
        self.assertTrue(sol["reachable"])
        self.assertLess(sol["error_m"], 1e-6)
        self.assertTrue(-140 <= sol["angles"]["forearm_r"][0] <= 0)

    def test_unreachable_target_is_reported_honestly(self):
        F = rig.fk({})
        far = F["foot_l"][:3, 3] + np.array([0, -60.0, 0])
        sol = rig.solve_limb("leg", "l", F["pelvis"], far)
        self.assertFalse(sol["reachable"])
        self.assertGreater(sol["error_m"], 5.0)
        self.assertEqual(rig.limit_violations(sol["angles"]), [], "even a failed solve must stay inside the limits")

    def test_target_inside_the_minimum_reach_is_unreachable(self):
        F = rig.fk({})
        near = F["thigh_l"][:3, 3] + np.array([0, 0, -1.0])      # ankle almost at the hip: needs a knee angle beyond 120
        sol = rig.solve_limb("leg", "l", F["pelvis"], near)
        self.assertFalse(sol["reachable"])


class TestPoses(unittest.TestCase):
    def test_required_poses_exist(self):
        names = set(LIB)
        self.assertIn("guard_neutral", names)
        for sector in ("up", "right", "left", "down"):
            for arm in ("r", "l"):
                for ph in ("windup", "commit", "strike_end", "recovery"):
                    self.assertIn("swing_%s_%s_%s" % (sector, arm, ph), names)
            self.assertIn("block_" + sector, names)
        for k in ("piston", "hook", "shove", "palm"):
            self.assertIn("quick_%s_r_strike" % k, names)
            self.assertIn("quick_%s_l_windup" % k, names)
        for n in ("hard_stance", "dodge_left_plant", "dodge_right_plant", "dodge_back_plant", "grab_reach", "ram_hit", "weapon_charge_hold",
                  "kneel", "knockdown_fall", "knockdown_down"):
            self.assertIn(n, names)
        self.assertGreaterEqual(len(names), 70)

    def test_joint_limits_hold_in_every_pose(self):
        for p in POSES:
            self.assertEqual(rig.limit_violations(p.final), [], p.name)

    def test_every_leg_ik_in_poses_succeeds(self):
        for p in POSES:
            for s, sol in p.leg_solutions.items():
                self.assertTrue(sol["reachable"], "%s %s %s" % (p.name, s, sol["clamped"]))

    def test_pose_records_have_com_and_feet(self):
        for p in POSES:
            r = p.record()
            self.assertEqual(len(r["com"]), 3)
            for s in "lr":
                self.assertEqual(len(r["feet"][s]["ankle"]), 3)
                self.assertIn("ground", r["feet"][s])
            self.assertTrue(np.isfinite(r["com"]).all())

    def test_static_poses_keep_the_com_over_the_feet(self):
        for n in ("guard_neutral", "hard_stance", "block_up", "block_down", "block_right", "block_left", "grab_reach", "weapon_charge_hold"):
            r = LIB[n].record()
            pts = np.array([r["feet"][s][k][:2] for s in "lr" for k in ("heel", "toe")])
            lo, hi = pts.min(0) - 3.0, pts.max(0) + 3.0
            self.assertTrue(np.all(np.array(r["com"][:2]) >= lo) and np.all(np.array(r["com"][:2]) <= hi), "%s com %s outside feet box" % (n, r["com"]))
            self.assertTrue(r["feet"]["l"]["ground"] and r["feet"]["r"]["ground"], n)

    def test_swings_start_by_moving_the_pelvis_and_torso(self):
        # pitch §11: the intent must be visible at once - the windup differs from guard in pelvis/torso, not only in the arm
        g = LIB["guard_neutral"].final
        for n in ("swing_up_r_windup", "swing_right_r_windup", "swing_down_r_windup"):
            w = LIB[n].final
            moved = abs(w["torso"][2] - g["torso"][2]) + abs(w["torso"][0] - g["torso"][0]) + abs(w["pelvis"][2] - g["pelvis"][2]) + abs(w["pelvis"][0] - g["pelvis"][0])
            self.assertGreater(moved, 12.0, n)

    def test_left_arm_swings_mirror_the_right_arm(self):
        for sector, other in (("up", "up"), ("down", "down"), ("right", "left"), ("left", "right")):
            for ph in ("windup", "commit", "strike_end", "recovery"):
                a = LIB["swing_%s_r_%s" % (sector, ph)].final
                b = LIB["swing_%s_l_%s" % (other, ph)].final
                for bone in ("upperarm", "forearm", "hand"):
                    ea, eb = a[bone + "_r"], b[bone + "_l"]
                    self.assertAlmostEqual(ea[0], eb[0], places=3)
                    self.assertAlmostEqual(ea[1], -eb[1], places=3)
                    self.assertAlmostEqual(ea[2], -eb[2], places=3)

    def test_recovery_is_compatible_with_the_transition_table(self):
        names = list(LIB)
        table = poses.transitions(names)
        for n in names:
            if n.startswith("swing_") and n.endswith("_recovery"):
                self.assertIn(n, table)
                self.assertGreaterEqual(len(table[n]), 6, n)
                a = LIB[n].final
                for nxt in table[n]:
                    self.assertIn(nxt, LIB, "%s -> %s: unknown pose" % (n, nxt))
                    b = LIB[nxt].final
                    d = np.mean([np.abs(np.array(a.get(x, [0, 0, 0])) - np.array(b.get(x, [0, 0, 0]))).max() for x in _upper(None)])
                    self.assertLess(d, 55.0, "%s -> %s: poses too far apart (%.0f deg mean)" % (n, nxt, d))
        self.assertIn("guard_neutral", table["swing_up_r_recovery"])
        for k, v in table.items():
            self.assertNotIn(k, v)

    def test_mirror_is_an_involution(self):
        j = LIB["swing_right_r_windup"].final
        mm = poses.mirror_angles(poses.mirror_angles(j))
        for b in j:
            self.assertEqual([round(x, 9) for x in mm[b]], [round(x, 9) for x in j[b]])


class TestLocomotion(unittest.TestCase):
    def test_gait_table_matches_the_82_m_machine(self):
        t = locomotion.table()
        for n in ("walk_slow", "walk", "walk_fast"):
            self.assertTrue(18.0 <= t[n]["step_length_m"] <= 26.0, n)
            self.assertTrue(3.0 <= t[n]["step_period_s"] <= 4.5, n)
        self.assertLess(t["walk"]["speed_kmh"], 35)      # not a human run
        self.assertGreater(t["run"]["speed_mps"], t["walk_fast"]["speed_mps"])

    def test_no_foot_sliding_in_any_clip(self):
        for c in LOCO:
            self.assertLess(locomotion.foot_slide(c), SLIDE_LIMIT_MPS, "%s slides %.2f m/s" % (c.name, locomotion.foot_slide(c)))

    def test_ik_reaches_the_feet_in_every_frame(self):
        for c in LOCO:
            self.assertLess(max(f["ik_error_m"] for f in c.frames), 1e-3, c.name)

    def test_joint_limits_hold_in_every_frame(self):
        for c in LOCO:
            for f in c.frames[::3]:
                self.assertEqual(rig.limit_violations(f["joints"]), [], "%s t=%s" % (c.name, f["t"]))

    def test_the_planted_leg_is_never_fully_straight(self):
        for c in LOCO:
            if c.gait not in locomotion.GAITS:
                continue
            for f in c.frames[::5]:
                for s in "lr":
                    if f["contact"][s]:
                        self.assertGreater(f["joints"]["shin_" + s][0], 3.0, "%s %s" % (c.name, f["t"]))

    def test_phases_are_in_order_and_the_swing_foot_lifts(self):
        c = locomotion.walk_cycle("walk", 2)
        first = c.frames[: int(locomotion.GAITS["walk"]["T"] * c.fps)]
        zs = [f["ankle"]["r"][2] for f in first]       # right foot swings first
        self.assertAlmostEqual(zs[0], rig.GROUND_ANKLE_Z, places=2)
        self.assertGreater(max(zs) - rig.GROUND_ANKLE_Z, locomotion.GAITS["walk"]["clearance"] * 0.9)
        self.assertAlmostEqual(zs[-1], rig.GROUND_ANKLE_Z, places=2)
        self.assertTrue(first[0]["contact"]["l"] and first[0]["contact"]["r"], "starts in double support (weight shift)")
        lifted = [i for i, f in enumerate(first) if not f["contact"]["r"]]
        self.assertGreater(lifted[0] / len(first), locomotion.PHASE["shift"] - 0.02)

    def test_weight_shift_precedes_the_lift(self):
        c = locomotion.walk_cycle("walk", 2)
        n = int(locomotion.GAITS["walk"]["T"] * c.fps)
        x0 = c.frames[0]["root_pos"][0]
        shift_end = c.frames[int(locomotion.PHASE["shift"] * n)]["root_pos"][0]
        self.assertGreater(abs(shift_end - x0), 1.5, "pelvis moves sideways over the stance foot before the foot lifts")

    def test_walk_covers_the_expected_distance(self):
        c = locomotion.walk_cycle("walk", 2)
        d = float(np.hypot(*(np.array(c.frames[-1]["root_pos"][:2]) - np.array(c.frames[0]["root_pos"][:2]))))
        self.assertAlmostEqual(d, 2 * locomotion.GAITS["walk"]["L"], delta=locomotion.GAITS["walk"]["sway"] + 1.0)

    def test_turn_in_place_rotates_the_heading(self):
        c = locomotion.turn_in_place("left")
        self.assertAlmostEqual(c.frames[-1]["joints"]["root"][2] - c.frames[0]["joints"]["root"][2], 5 * 16.0, delta=3.0)

    def test_stop_ends_with_the_feet_together(self):
        c = locomotion.walk_stop("walk")
        a, b = c.frames[-1]["ankle"]["l"], c.frames[-1]["ankle"]["r"]
        self.assertLess(abs(a[1] - b[1]), locomotion.GAITS["walk"]["L"] * 0.35)


class TestCurves(unittest.TestCase):
    def test_heavy_easing_starts_fast_and_ends_slowly(self):
        h = 1e-4
        d0 = (curves.ease_heavy(h) - curves.ease_heavy(0)) / h
        d1 = (curves.ease_heavy(1) - curves.ease_heavy(1 - h)) / h
        self.assertGreater(d0, 2.0)
        self.assertLess(d1, 0.01)
        v = [curves.ease_heavy(i / 100) for i in range(101)]
        self.assertTrue(all(b >= a for a, b in zip(v, v[1:])))
        self.assertGreater(curves.ease_heavy(0.2), 0.4)
        self.assertEqual(curves.ease_heavy(1.0), 1.0)

    def test_per_joint_timing_lets_the_torso_lead_and_the_hand_trail(self):
        a = {"torso": [0, 0, 0], "hand_r": [0, 0, 0]}
        b = {"torso": [0, 0, 40], "hand_r": [-40, 0, 0]}
        mid = curves.blend_poses(a, b, 0.2, curves.SWING_TIMING, "smoothstep")
        self.assertGreater(abs(mid["torso"][2]) / 40.0, abs(mid["hand_r"][0]) / 40.0 + 0.1)
        end = curves.blend_poses(a, b, 1.0, curves.SWING_TIMING, "heavy")
        self.assertAlmostEqual(end["hand_r"][0], -40.0, places=6)

    def test_spring_overshoots_a_little_and_settles(self):
        tr = np.zeros((300, 3))
        tr[20:] = 1.0
        r = curves.secondary_motion(tr, 1 / 60.0, 1.2, 0.45)
        self.assertGreater(r[:, 0].max(), 1.0)
        self.assertLess(r[:, 0].max(), 1.4)
        self.assertAlmostEqual(r[-1, 0], 1.0, delta=0.02)

    def test_step_shake_peaks_on_the_heel_strike_and_decays(self):
        a = [abs(curves.step_shake(p / 100.0)[0]) for p in range(100)]
        self.assertEqual(int(np.argmax(a)) // 12, 0)
        self.assertLess(max(a[50:]), 0.25 * max(a))
        self.assertGreater(abs(curves.step_shake(0.0, 2.0)[0]), abs(curves.step_shake(0.0, 1.0)[0]))


class TestDamage(unittest.TestCase):
    def test_destroyed_arm_hangs_limp_and_severed_hides_the_hand(self):
        base = LIB["swing_up_r_commit"].record()
        d = damage.apply_damage(base, {"ArmR": "Destroyed"})
        self.assertGreater(d["joints"]["upperarm_r"][0], -10)         # arm no longer raised
        s = damage.apply_damage(base, {"ArmR": "Severed"})
        self.assertIn("hand_r", s["damage"]["hidden_bones"])
        self.assertEqual(damage.apply_damage(base, {"ArmL": "Intact"})["joints"], base["joints"])

    def test_critical_elbow_is_jammed_regardless_of_the_pose(self):
        for n in ("guard_neutral", "swing_up_r_windup", "block_up"):
            d = damage.apply_damage(LIB[n].record(), {"ArmL": "Critical"})
            self.assertEqual(d["joints"]["forearm_l"], [-38.0, 0.0, 0.0])
            self.assertIn("forearm_l", d["damage"]["jammed"])

    def test_damaged_shoulder_limits_the_raise(self):
        d = damage.apply_damage(LIB["swing_up_r_windup"].record(), {"ShoulderR": "Critical"})
        self.assertGreater(d["joints"]["upperarm_r"][0], -90)
        self.assertEqual(rig.limit_violations(d["joints"]), [])

    def test_damage_modifiers_keep_joints_inside_limits(self):
        for p in POSES[::7]:
            for st in damage.STATES:
                d = damage.apply_damage(p.record(), {z: st for z in damage.ZONES})
                self.assertEqual(rig.limit_violations(d["joints"]), [], "%s %s" % (p.name, st))

    def test_leg_damage_makes_the_gait_visibly_asymmetric(self):
        sym = damage.asymmetry(locomotion.walk_cycle("walk", 6))
        self.assertAlmostEqual(sym[0], 1.0, places=3)
        self.assertAlmostEqual(sym[1], 1.0, places=3)
        for st, need in (("Damaged", 0.08), ("Critical", 0.15)):
            for side in ("LegL", "LegR"):
                c = damage.limp_walk({side: st}, "walk", 6)
                lr, tr = damage.asymmetry(c)
                self.assertGreater(1.0 - lr, need, "%s %s step length ratio %.2f" % (side, st, lr))
                self.assertGreater(1.0 - tr, need, "%s %s swing time ratio %.2f" % (side, st, tr))
                self.assertLess(locomotion.foot_slide(c), SLIDE_LIMIT_MPS)
                self.assertLess(max(f["ik_error_m"] for f in c.frames), 1e-3)

    def test_destroyed_leg_blocks_locomotion(self):
        d = damage.apply_damage(LIB["guard_neutral"].record(), {"LegR": "Severed"})
        self.assertTrue(d["damage"]["locomotion_blocked"])

    def test_every_zone_and_state_of_task_001_is_known(self):
        self.assertEqual(damage.ZONES, ["Head", "Torso", "Reactor", "ShoulderL", "ShoulderR", "ArmL", "ArmR", "LegL", "LegR"])
        self.assertEqual(damage.STATES, ["Intact", "Dented", "Exposed", "Damaged", "Critical", "Destroyed", "Severed"])
        sev = [damage.severity(s) for s in damage.STATES]
        self.assertEqual(sev, sorted(sev))


class TestExport(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pj, cls.lj, cls.cj, cls.pclips, cls.walk = export.build_all(os.path.join(ROOT, "anim", "out", "_test"), verbose=False)

    def test_json_matches_the_schemas(self):
        self.assertEqual(schema.validate(self.pj, schema.POSES_SCHEMA), [])
        self.assertEqual(schema.validate(self.lj, schema.LOCO_SCHEMA), [])
        self.assertEqual(schema.validate(self.cj, schema.CURVES_SCHEMA), [])

    def test_schema_validator_catches_errors(self):
        bad = json.loads(json.dumps(self.pj))
        bad["poses"]["guard_neutral"]["com"] = [1, 2]
        self.assertTrue(schema.validate(bad, schema.POSES_SCHEMA))
        del bad["transitions"]
        self.assertTrue(any("missing transitions" in e for e in schema.validate(bad, schema.POSES_SCHEMA)))

    def test_exported_angles_respect_the_limits(self):
        for name, p in self.pj["poses"].items():
            self.assertEqual(rig.limit_violations(p["joints"], tol=1e-2), [], name)
        for c in self.lj["clips"]:
            for fr in c["frames"][::4]:
                j = {b: fr["j"][3 * i:3 * i + 3] for i, b in enumerate(self.lj["bone_order"])}
                self.assertEqual(rig.limit_violations(j, tol=1e-2), [], "%s %s" % (c["name"], fr["t"]))

    def test_deterministic(self):
        a, _, _, _, _ = export.build_all(os.path.join(ROOT, "anim", "out", "_test2"), verbose=False)
        h1 = hashlib.sha256(json.dumps(self.pj, sort_keys=True).encode()).hexdigest()
        h2 = hashlib.sha256(json.dumps(a, sort_keys=True).encode()).hexdigest()
        self.assertEqual(h1, h2)
        for rel in ("locomotion.json", "curves.json", "bvh/walk.bvh", "bvh/swing_up_right.bvh"):
            with open(os.path.join(ROOT, "anim", "out", "_test", rel), "rb") as f1, open(os.path.join(ROOT, "anim", "out", "_test2", rel), "rb") as f2:
                self.assertEqual(f1.read(), f2.read(), rel)

    def test_bvh_files_are_well_formed(self):
        d = os.path.join(ROOT, "anim", "out", "_test", "bvh")
        names = sorted(os.listdir(d))
        self.assertEqual(sorted(n[:-4] for n in names), ["block_up", "dodge_left", "fall_back", "quick_piston_right", "swing_up_right", "walk"])
        for n in names:
            with open(os.path.join(d, n)) as f:
                joints, frames, ft, chans, rows = export.parse_bvh(f.read())
            self.assertEqual(len(joints), 19)
            self.assertEqual(joints[0], "root")
            self.assertEqual(len(rows), frames)
            self.assertAlmostEqual(ft, 1 / 30.0, places=5)
            self.assertEqual(len(rows[0]), 6 + 3 * 18)
            self.assertEqual(sum(chans), 6 + 3 * 18)
            self.assertTrue(np.isfinite(np.array(rows)).all())

    def test_pose_clips_start_and_end_in_guard(self):
        g = LIB["guard_neutral"].final
        for c in self.pclips:
            if c["name"] == "fall_back":
                continue
            last = c["frames"][-1]["joints"]
            for b in ("torso", "upperarm_r", "forearm_l", "shin_l"):
                for x, y in zip(last[b], g[b]):
                    self.assertAlmostEqual(x, y, delta=0.5, msg="%s %s" % (c["name"], b))

    def test_pose_clips_keep_the_feet_planted_during_a_swing(self):
        c = next(c for c in self.pclips if c["name"] == "swing_up_right")
        pos = []
        for fr in c["frames"]:
            F = rig.fk(fr["joints"], fr["root_pos"])
            fc = rig.foot_contacts(F)
            pos.append((np.array(fc["l"]["ankle"][:2]), np.array(fc["r"]["ankle"][:2])))
        drift = max(float(np.linalg.norm(p[0] - pos[0][0])) for p in pos)
        self.assertLess(drift, 6.0)     # the front foot steps in a few metres, it does not skate across the arena

    def test_the_swing_clip_follows_the_core_timings(self):
        c = next(c for c in self.pclips if c["name"] == "swing_up_right")
        spec = clips.KEYS["swing_up_right"]
        dur = {n: d for n, d in spec}
        # pitch §5.2 / Tuning.h: strike travel 330 ms, recovery 600 ms, windup between 300 ms and 1 s of charge
        self.assertAlmostEqual(dur["swing_up_r_strike_end"], 0.33, places=2)
        self.assertAlmostEqual(dur["swing_up_r_recovery"], 0.6, places=2)
        self.assertTrue(0.3 <= dur["swing_up_r_windup"] <= 1.0)
        self.assertGreater(c["frames"][-1]["t"], 2.5)
        # the heavy swing is the fastest thing in the clip; the windup/recovery stay slow (hand speed in m/s)
        prev, speeds = None, []
        for fr in c["frames"]:
            h = rig.fk(fr["joints"], fr["root_pos"])["hand_r"][:3, 3]
            if prev is not None:
                speeds.append(float(np.linalg.norm(h - prev)) * c["fps"])
            prev = h
        n_w = int(round(dur["swing_up_r_windup"] * c["fps"]))
        self.assertLess(max(speeds[:n_w - 1]), 0.25 * max(speeds), "the windup is much slower than the strike")


if __name__ == "__main__":
    unittest.main()
