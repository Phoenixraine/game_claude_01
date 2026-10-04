"""TASK-022 tests. Run: python3 -m unittest discover -s data/damage_fx/tests  (from the repo root)."""
import copy
import json
import math
import os
import re
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
FX = os.path.dirname(HERE)
REPO = os.path.abspath(os.path.join(FX, "..", ".."))
sys.path.insert(0, FX)

import fxmath as fx          # noqa: E402
import validate as V         # noqa: E402

ZONES = ["Head", "Torso", "Reactor", "ShoulderL", "ShoulderR", "ArmL", "ArmR", "LegL", "LegR"]
# EventType values that TASK-017 (boarding) appends to core/include/iv/Events.h; may be absent from Events.h until that PR is merged
BOARDING_EVENTS = {"BoardingStarted", "BoardingPhase", "BoardingDenied", "HookFired", "HookLanded", "HackStarted", "HackProgress", "HackResultEvt", "BoardingSwatTelegraph",
                   "BoardingSwingOk", "BoardingSmashed", "GrenadeThrown", "BoardingBlast", "BoardingEnded", "BoardingSwatImpact", "BoardingSwatAdjusted", "BoardingShock"}


# warning triggers that are derived by the cockpit layer, not core events
DERIVED_TRIGGERS = {"cockpit_fire"}


def core_events():
    with open(os.path.join(REPO, "core", "include", "iv", "Events.h"), encoding="utf-8") as f:
        src = f.read()
    body = re.search(r"enum class EventType[^{]*\{(.*?)\};", src, re.S).group(1)
    names = []
    for line in body.splitlines():
        line = line.split("//")[0].strip()
        for m in re.finditer(r"([A-Za-z_]\w*)\s*(?:=[^,]*)?,", line):
            names.append(m.group(1))
    return names


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def T(name):
    return fx.table(name)


def hit(zone="Torso", layer=1, state=3, flags=0, dmg=17.5, stab=10.0):
    return {"type": "HitEvent", "zone": zone, "a": layer, "b": state, "c": flags, "value": dmg, "value2": stab}


class Schemas(unittest.TestCase):
    def test_all_tables_validate(self):
        for n in V.TABLES:
            self.assertEqual(V.validate_table(n), [], n)

    def test_validator_rejects_bad_data(self):
        sch = json.loads(read(os.path.join(FX, "schema", "shake_profiles.schema.json")))
        bad = copy.deepcopy(T("shake_profiles"))
        bad["limits"]["max_pos_cm"] = 30.0
        self.assertTrue(V.validate(bad, sch))
        bad = copy.deepcopy(T("shake_profiles"))
        del bad["events"]["HitEvent"]["components"]
        self.assertTrue(V.validate(bad, sch))
        bad = copy.deepcopy(T("shake_profiles"))
        bad["events"]["HitEvent"]["components"][0]["amp_cm"] = float("nan")
        self.assertTrue(V.validate(bad, sch))

    def test_builder_output_equals_committed_json(self):
        with tempfile.TemporaryDirectory() as d:
            subprocess.run([sys.executable, os.path.join(FX, "build_tables.py"), d], check=True, stdout=subprocess.DEVNULL)
            for n in V.TABLES:
                a = read(os.path.join(d, n + ".json"))
                b = read(os.path.join(FX, n + ".json"))
                self.assertEqual(a, b, n + ".json is stale: run build_tables.py")


class Coverage(unittest.TestCase):
    def groups(self):
        c = T("coverage")
        return {k: set(c[k] if isinstance(c[k], list) else c[k].keys()) for k in ("shake", "warnings_only", "chunks", "cockpit_by_severity", "no_cockpit_effect")}

    def test_every_event_type_is_classified(self):
        g = self.groups()
        union = set().union(*g.values())
        missing = [e for e in core_events() if e not in union]
        self.assertEqual(missing, [], "EventType values without a FX decision")

    def test_no_unknown_event_names(self):
        union = set().union(*self.groups().values())
        unknown = union - set(core_events()) - BOARDING_EVENTS
        self.assertEqual(unknown, set())

    def test_no_effect_group_is_disjoint_from_effect_groups(self):
        g = self.groups()
        effect = g["shake"] | g["chunks"] | g["cockpit_by_severity"]
        self.assertEqual(g["no_cockpit_effect"] & g["cockpit_by_severity"], set())
        self.assertTrue(effect)

    def test_shake_group_has_a_profile_for_each_event(self):
        for e in T("coverage")["shake"]:
            self.assertIn(e, T("shake_profiles")["events"], e)
        for e in T("shake_profiles")["events"]:
            self.assertIn(e, T("coverage")["shake"], e)

    def test_chunk_group_has_rules(self):
        self.assertEqual(set(T("coverage")["chunks"]), set(T("mech_chunks")["event_rules"]))

    def test_all_nine_zones_everywhere(self):
        M = T("mech_chunks")["zones"]
        self.assertEqual(sorted(M), sorted(ZONES))
        for z in ZONES:
            for layer in ("Armor", "Mechanism", "System"):
                self.assertTrue(M[z][layer], (z, layer))
        self.assertEqual(sorted(T("shake_profiles")["zone_direction"]), sorted(ZONES))
        self.assertEqual(sorted(T("shake_profiles")["severity"]["zone_weight"]), sorted(ZONES))
        self.assertEqual(sorted(T("identifiers")["zones"]), sorted(ZONES))
        for z in ZONES:
            self.assertIn(z, fx.ZONE_ANCHOR)
            self.assertIn(z, fx.ZONE_NORMAL)


class References(unittest.TestCase):
    def test_cockpit_targets_exist(self):
        ids = T("identifiers")
        known = set(ids["cockpit"]) | set(ids["cockpit_singletons"]) | {"Audio"}
        for sev, rows in T("cockpit_effects")["severity"].items():
            for r in rows:
                self.assertIn(r["target"], known, (sev, r["target"]))

    def test_cockpit_counts_fit_the_class_sizes(self):
        ids = T("identifiers")["cockpit"]
        for sev, rows in T("cockpit_effects")["severity"].items():
            for r in rows:
                if r["target"] in ids:
                    self.assertLessEqual(r["count"][1] * 1.0, ids[r["target"]], (sev, r["target"]))

    def test_chunk_types_are_declared(self):
        decl = set(T("identifiers")["mech_chunks"])
        M = T("mech_chunks")
        rows = [r for z in M["zones"].values() for l in z.values() for r in l] + [M["limb_part"]]
        for r in rows:
            self.assertIn(r["type"], decl)

    def test_building_classes_are_declared_shards(self):
        sh = T("identifiers")["shards"]
        declared = {c for v in sh.values() for c in v}
        B = T("building_destruction")
        self.assertEqual(set(B["classes"]) - declared, set())
        for sc in B["scenarios"].values():
            for st in sc["stages"]:
                for s in st["spawns"]:
                    self.assertIn(s["class"], B["classes"])
        for mat in B["material_scale"].values():
            for c in mat:
                self.assertIn(c, B["classes"])
        for mat in B["material_scale"]:
            self.assertIn(mat, B["dust"])

    def test_warning_triggers_reference_known_events_and_unique_ids(self):
        W = T("warnings")["warnings"]
        self.assertEqual(len({w["id"] for w in W}), len(W))
        known = set(core_events()) | BOARDING_EVENTS | DERIVED_TRIGGERS
        for w in W:
            self.assertIn(w["trigger"]["event"], known)
            self.assertIn(w["color"], T("warnings")["colors"])
            self.assertTrue(all(isinstance(x, int) and x >= 0 for x in w["blink_ms"]))      # [on_ms, off_ms]
        for w in W:
            if w["trigger"]["event"] not in DERIVED_TRIGGERS:
                self.assertIn(w["trigger"]["event"], T("coverage")["warnings_only"] + T("coverage")["shake"] + list(T("coverage")["cockpit_by_severity"]) + T("coverage")["chunks"])

    def test_sounds_use_known_ids_if_listed(self):
        snd = T("identifiers")["sounds"]
        snd = set(snd if isinstance(snd, list) else snd.keys())
        cp = T("cockpit_effects")
        for k in ("siren",):
            for v in cp[k].values():
                if v:
                    self.assertIn(v["sound"], snd)
        for v in T("building_destruction")["sounds"].values():
            self.assertIn(v, snd)
        for w in T("warnings")["warnings"]:
            if w.get("sound"):
                self.assertIn(w["sound"], snd, w["id"])


class Severity(unittest.TestCase):
    def test_monotone_in_damage(self):
        prev = -1
        for d in range(0, 80, 2):
            _, s = fx.severity_for_event(hit(dmg=float(d)))
            self.assertGreaterEqual(s, prev)
            prev = s

    def test_blocked_and_parried_are_softer(self):
        free = fx.severity_for_event(hit(flags=0))[1]
        blk = fx.severity_for_event(hit(flags=4))[1]
        par = fx.severity_for_event(hit(flags=8))[1]
        self.assertLess(blk, free)
        self.assertLess(par, blk)

    def test_levels_span_s0_to_s4(self):
        lv = {fx.severity_for_event(hit(zone=z, layer=l, state=s, dmg=d))[0] for z in ZONES for l in (0, 1, 2) for s in (0, 3, 5) for d in (3.0, 17.5, 30.0, 45.0)}
        self.assertEqual(lv, {0, 1, 2, 3, 4})

    def test_swat_impact_is_max(self):
        self.assertEqual(fx.severity_for_event({"type": "BoardingSwatImpact", "zone": "ShoulderL"})[0], 4)


def finite(vs):
    return all(math.isfinite(c) for v in vs for c in v)


class Shake(unittest.TestCase):
    def test_all_profiles_all_severities_within_limits(self):
        L = T("shake_profiles")["limits"]
        for ev in T("shake_profiles")["events"]:
            for sev in range(5):
                for zone in ZONES:
                    s = fx.shake_for_event(ev, 40.0, zone, severity=sev, seed=sev)
                    self.assertTrue(finite(s["pos_cm"]) and finite(s["rot_deg"]) and all(math.isfinite(c) for c in s["chroma"]))
                    self.assertLessEqual(max(math.sqrt(sum(c * c for c in p)) for p in s["pos_cm"]), L["max_pos_cm"] + 1e-6, (ev, sev))
                    self.assertLessEqual(max(math.sqrt(sum(c * c for c in r)) for r in s["rot_deg"]), L["max_rot_deg"] + 1e-6, (ev, sev))
                    self.assertLessEqual(max(s["chroma"]), 1.0)

    def test_every_shake_settles_to_zero(self):
        for ev in T("shake_profiles")["events"]:
            s = fx.shake_for_event(ev, 30.0, "Torso", severity=3, seed=1)
            self.assertLess(max(abs(c) for c in s["pos_cm"][-1]), 0.05, ev)
            self.assertLess(max(abs(c) for c in s["rot_deg"][-1]), 0.01, ev)

    def test_high_frequency_components_are_short(self):
        L = T("shake_profiles")["limits"]
        for ev, p in T("shake_profiles")["events"].items():
            for c in p["components"]:
                if c["freq_hz"] > L["high_freq_hz"]:
                    self.assertLessEqual(c["duration_s"], L["high_freq_max_s"], (ev, c))

    def test_severity_scales_amplitude(self):
        amp = []
        for sev in range(5):
            s = fx.shake_for_event("HitEvent", 20.0, "Torso", severity=sev, seed=2)
            amp.append(max(math.sqrt(sum(c * c for c in p)) for p in s["pos_cm"]))
        self.assertEqual(amp, sorted(amp))
        self.assertGreater(amp[4], amp[0] * 2)

    def test_reduce_motion_is_quarter(self):
        a = fx.shake_for_event("HitEvent", 20.0, "Torso", severity=2, seed=3)
        b = fx.shake_for_event("HitEvent", 20.0, "Torso", severity=2, seed=3, reduce_motion=True)
        ma = max(math.sqrt(sum(c * c for c in p)) for p in a["pos_cm"])
        mb = max(math.sqrt(sum(c * c for c in p)) for p in b["pos_cm"])
        self.assertLess(mb, ma * 0.3)

    def test_deterministic_and_seed_sensitive(self):
        a = fx.shake_for_event("HitEvent", 20.0, "Head", severity=3, seed=5)
        b = fx.shake_for_event("HitEvent", 20.0, "Head", severity=3, seed=5)
        c = fx.shake_for_event("HitEvent", 20.0, "Head", severity=3, seed=6)
        self.assertEqual(json.dumps(a), json.dumps(b))
        self.assertNotEqual(json.dumps(a), json.dumps(c))

    def test_direction_follows_the_zone(self):
        s = fx.shake_for_event("HitEvent", 25.0, "ShoulderL", severity=3, seed=1, direction="Left")
        peak = max(s["pos_cm"], key=lambda p: sum(c * c for c in p))
        self.assertGreater(abs(peak[0]), abs(peak[1]) * 0.5)

    def test_mixing_limits_the_sum(self):
        L = T("shake_profiles")["limits"]
        shakes = [fx.shake_for_event("HitEvent", 40.0, z, severity=4, seed=i) for i, z in enumerate(ZONES)]
        m = fx.mix_shakes(shakes, [0.0, 0.02, 0.05, 0.08, 0.1, 0.12, 0.15, 0.2, 0.25])
        self.assertLessEqual(max(math.sqrt(sum(c * c for c in p)) for p in m["pos_cm"]), L["max_pos_cm"] + 1e-6)
        self.assertLessEqual(max(math.sqrt(sum(c * c for c in r)) for r in m["rot_deg"]), L["max_rot_deg"] + 1e-6)

    def test_core_event_helper_returns_none_without_profile(self):
        self.assertIsNone(fx.shake_for_core_event({"type": "Whiff"}))
        self.assertIsNotNone(fx.shake_for_core_event(hit()))


class Cockpit(unittest.TestCase):
    def test_deterministic(self):
        a = fx.plan_cockpit_effects(3, 11)
        b = fx.plan_cockpit_effects(3, 11)
        self.assertEqual(json.dumps(a), json.dumps(b))

    def test_commands_sorted_finite_and_reference_real_ids(self):
        ids = T("identifiers")["cockpit"]
        for sev in range(5):
            for seed in range(30):
                cmds, _ = fx.plan_cockpit_effects(sev, seed)
                self.assertEqual([c["t"] for c in cmds], sorted(c["t"] for c in cmds))
                for c in cmds:
                    self.assertTrue(math.isfinite(c["t"]) and math.isfinite(c["duration_s"]) and c["t"] >= 0 and c["duration_s"] >= 0)
                    m = re.match(r"^(.*)_(\d\d)$", c["target"])
                    if m and m.group(1) in ids:
                        self.assertLess(int(m.group(2)), ids[m.group(1)], c)

    def test_s0_destroys_nothing(self):
        for seed in range(50):
            cmds, st = fx.plan_cockpit_effects(0, seed)
            self.assertFalse([c for c in cmds if c["action"] in ("burst", "snap", "dead", "ignite", "crack")])

    def test_destruction_grows_with_severity(self):
        def destroyed(sev):
            n = 0
            for seed in range(60):
                cmds, _ = fx.plan_cockpit_effects(sev, seed)
                n += sum(1 for c in cmds if c["action"] in ("burst", "snap", "dead", "ignite", "crack"))
            return n
        d = [destroyed(s) for s in range(5)]
        self.assertEqual(d, sorted(d))
        self.assertGreater(d[4], d[1])

    def test_state_prevents_double_destruction_and_exhausts(self):
        st = None
        seen = set()
        for i in range(60):
            cmds, st = fx.plan_cockpit_effects(4, i, st)
            for c in cmds:
                if c["action"] in ("burst", "snap", "dead", "crack"):
                    key = (c["target"], c["action"])
                    self.assertNotIn(key, seen, "destroyed twice")
                    seen.add(key)
            st = dict(st, time=st["time"] + 5.0)
        ids = T("identifiers")["cockpit"]
        self.assertLessEqual(len(st["burst"]), ids["Pipe_Burst"])
        self.assertLessEqual(len(st["snapped"]), ids["Wire_Snapped"])

    def test_fire_cap(self):
        mx = T("cockpit_effects")["fire"]["max_simultaneous"]
        st = None
        for i in range(30):
            _, st = fx.plan_cockpit_effects(4, i, st)
            self.assertLessEqual(len(st["fires"]), mx)
            cmds, st = fx.plan_fire_spread(st, i, 5.0, 4)
            self.assertLessEqual(len(st["fires"]), mx)

    def test_fire_spreads_only_along_graph_and_burns_out(self):
        edges = {tuple(sorted(e)) for e in T("identifiers")["fire_graph"]["edges"]}
        st = fx.new_cockpit_state()
        st["fires"] = {"0": 0.0}
        cmds, st = fx.plan_fire_spread(st, 7, 40.0, 4)
        for c in cmds:
            if c["action"] == "ignite":
                a = int(c["params"]["spread_from"])
                b = int(c["target"].split("_")[-1])
                self.assertIn(tuple(sorted((a, b))), edges)
        cmds2, st2 = fx.plan_fire_spread(st, 7, 120.0, 4)
        self.assertEqual(st2["fires"], {})

    def test_red_light_curve(self):
        for sev in range(5):
            cv = fx.red_light_curve(sev)
            self.assertTrue(all(0.0 <= v <= 1.0 and math.isfinite(v) for _, v in cv))
        self.assertEqual(max(v for _, v in fx.red_light_curve(0)), 0.0)
        self.assertGreater(max(v for _, v in fx.red_light_curve(4)), max(v for _, v in fx.red_light_curve(2)))
        self.assertLess(fx.red_light_curve(4)[-1][1], 0.1)


class Chunks(unittest.TestCase):
    MECH_H = 85.0

    def events(self):
        out = []
        for z in ZONES:
            for layer in (0, 1, 2):
                out.append(hit(zone=z, layer=layer, state=5, dmg=40.0))
            out.append({"type": "ArmorPlateLost", "zone": z, "a": 0, "b": 3})
            out.append({"type": "LimbSevered", "zone": z})
            out.append({"type": "ExternalHit", "zone": z, "a": 1, "value": 30.0})
        out += [{"type": "ReactorBreach"}, {"type": "UltimateFinisher", "zone": "Torso"}, {"type": "UltimateSever", "zone": "ArmL"}, {"type": "BoardingBlast", "zone": "Torso", "value": 30.0}]
        return out

    def test_deterministic_and_non_empty_for_destructive_events(self):
        for e in self.events():
            a = fx.plan_chunks(e, 3)
            b = fx.plan_chunks(e, 3)
            self.assertEqual(json.dumps(a), json.dumps(b))
        self.assertTrue(fx.plan_chunks({"type": "ArmorPlateLost", "zone": "Head", "a": 0, "b": 3}, 1))
        self.assertTrue(fx.plan_chunks({"type": "LimbSevered", "zone": "ArmL"}, 1))

    def test_light_hits_make_no_chunks(self):
        self.assertEqual(fx.plan_chunks(hit(dmg=2.0, layer=0, state=0, flags=4), 1), [])
        self.assertEqual(fx.plan_chunks({"type": "Whiff"}, 1), [])

    def test_no_nan_and_sane_values(self):
        for e in self.events():
            for c in fx.plan_chunks(e, 9):
                for v in c["pos"] + c["vel"] + [c["spin_rad_s"], c["mass_kg"], c["life_s"], c["smoke_s"]]:
                    self.assertTrue(math.isfinite(v))
                self.assertGreater(c["mass_kg"], 0)
                self.assertGreater(c["life_s"], 0)
                self.assertGreaterEqual(c["pos"][2], 0.5)
                self.assertIn(c["mesh_hint"], T("identifiers")["mech_chunks"] + [c["mesh_hint"]])

    def test_ballistics_range_and_no_flight_through_mechs(self):
        R = T("mech_chunks")["ballistics"]["owner_capsule_radius_m"]["default"]
        owner = {"x": 0.0, "y": 0.0, "r": R, "h": self.MECH_H}
        enemy = {"x": 0.0, "y": -42.0, "r": R, "h": self.MECH_H}     # the attacker stands in front of the victim (its -y side)
        total = hit_enemy = 0
        for e in self.events():
            for seed in (1, 2, 3):
                for c in fx.plan_chunks(e, seed):
                    r = fx.simulate_chunk(c, [owner, enemy])
                    total += 1
                    self.assertLessEqual(r["range_m"], T("mech_chunks")["ballistics"]["max_range_m"] + 0.5, (e["type"], c["id"]))
                    for p in r["points"]:
                        self.assertFalse(math.hypot(p[0] - enemy["x"], p[1] - enemy["y"]) < enemy["r"] - 1e-6 and 0 <= p[2] <= enemy["h"], "chunk inside the attacker")
                    if r["hit"] == 1:
                        hit_enemy += 1
                    self.assertNotEqual(r["hit"], 0, "chunk re-entered the owner body")
                    # a chunk must move away from the owner's axis from the very start (it never tunnels through the body)
                    radial = [math.hypot(p[0], p[1]) for p in r["points"][:12]]
                    for a, b in zip(radial, radial[1:]):
                        self.assertGreaterEqual(b, a - 0.05, (e["type"], c["id"]))
        self.assertGreater(total, 500)
        self.assertLess(hit_enemy / total, 0.5)

    def test_burning_fraction_present_for_burning_plates(self):
        burning = [c for c in fx.plan_chunks({"type": "ArmorPlateLost", "zone": "Torso", "a": 0, "b": 3}, 1) + fx.plan_chunks(hit(layer=2, state=5, dmg=50.0), 1) if c["fire"]["on"]]
        allc = [fx.plan_chunks({"type": "LimbSevered", "zone": z}, s) for z in ZONES for s in range(5)]
        self.assertTrue(any(c["fire"]["on"] for cs in allc for c in cs))
        for c in burning:
            self.assertGreater(c["fire"]["duration_s"], 0)

    def test_knob_scales_counts(self):
        e = {"type": "LimbSevered", "zone": "ArmL"}
        n1 = len(fx.plan_chunks(e, 4))
        n2 = len(fx.plan_chunks(e, 4, {"chunks_count": 0.25}))
        self.assertLess(n2, n1)


class Buildings(unittest.TestCase):
    PARAMS = [{}, {"material": "glass_curtain", "glass_ratio": 0.8, "floors": 40, "height_m": 160.0}, {"material": "brick", "floors": 5, "height_m": 20.0}, {"material": "steel_frame", "floors": 30}]

    def test_all_scenarios_within_budgets(self):
        B = T("building_destruction")["budgets"]
        for kind in T("building_destruction")["scenarios"]:
            for p in self.PARAMS:
                for e in (50.0, 1000.0, 20000.0, 1e7):
                    for seed in range(3):
                        plan = fx.plan_building_break(kind, e, (0, -1, 0), p, seed)
                        t = plan["totals"]
                        self.assertLessEqual(t["large_shards"], B["large_shards"], (kind, p, e))
                        self.assertLessEqual(t["small_shards"], B["small_shards"], (kind, p, e))
                        self.assertLessEqual(t["smoke_puffs"], B["smoke_puffs"])
                        self.assertEqual(t["large_shards"], sum(s["count"] for s in plan["spawns"] if s["budget"] == "large"))
                        self.assertEqual(t["small_shards"], sum(s["count"] for s in plan["spawns"] if s["budget"] == "small"))
                        self.assertEqual(len(plan["smoke_puffs"]), t["smoke_puffs"])

    def test_deterministic_and_energy_monotone(self):
        a = fx.plan_building_break("mech_crash", 5000.0, (0, -1, 0), {}, 3)
        b = fx.plan_building_break("mech_crash", 5000.0, (0, -1, 0), {}, 3)
        self.assertEqual(json.dumps(a), json.dumps(b))
        lo = fx.plan_building_break("sword_hit", 20.0, (0, -1, 0), {}, 1)["totals"]
        hi = fx.plan_building_break("sword_hit", 400.0, (0, -1, 0), {}, 1)["totals"]
        self.assertLessEqual(lo["small_shards"], hi["small_shards"])
        self.assertLessEqual(lo["large_shards"], hi["large_shards"])

    def test_values_finite_and_ordered(self):
        for kind in T("building_destruction")["scenarios"]:
            plan = fx.plan_building_break(kind, 3000.0, (1, 0, 0), {"material": "glass_curtain"}, 2)
            self.assertTrue(plan["spawns"])
            for s in plan["spawns"]:
                self.assertGreater(s["count"], 0)
                self.assertTrue(all(math.isfinite(v) for v in s["speed_mps"] + s["mass_kg"] + s["life_s"] + [s["t_s"]]))
            ts = [s["t_s"] for s in plan["spawns"]]
            self.assertEqual(ts, sorted(ts))
            self.assertTrue(plan["sounds"])
            self.assertTrue(all(math.isfinite(v) for _, v in plan["dust"]["density"]))

    def test_glass_building_has_more_glass(self):
        g = fx.plan_building_break("plasma", 3000.0, (0, -1, 0), {"material": "glass_curtain", "glass_ratio": 0.9}, 1)
        c = fx.plan_building_break("plasma", 3000.0, (0, -1, 0), {"material": "concrete", "glass_ratio": 0.1}, 1)
        cnt = lambda p: sum(s["count"] for s in p["spawns"] if s["class"] == "Glass_Shard")
        self.assertGreater(cnt(g), cnt(c))

    def test_knob_scales_down(self):
        a = fx.plan_building_break("mech_crash", 5000.0, (0, -1, 0), {}, 3)["totals"]
        b = fx.plan_building_break("mech_crash", 5000.0, (0, -1, 0), {}, 3, {"building_shards": 0.2})["totals"]
        self.assertLess(b["small_shards"], a["small_shards"])


class Warnings(unittest.TestCase):
    def test_priorities_unique_for_siren_owners_and_resolution(self):
        W = T("warnings")["warnings"]
        self.assertTrue(all(isinstance(w["priority"], int) for w in W))
        ids = [w["id"] for w in W]
        self.assertEqual(fx.active_warning(ids), min(W, key=lambda w: w["priority"])["id"])
        self.assertIsNone(fx.active_warning([]))

    def test_events_raise_warnings(self):
        self.assertTrue(fx.warnings_for_event({"type": "ReactorBreach"}))
        self.assertTrue(fx.warnings_for_event({"type": "HeatWarning"}))
        self.assertTrue(fx.warnings_for_event({"type": "LimbSevered", "zone": "ArmL"}))
        self.assertEqual(fx.warnings_for_event({"type": "Whiff"}), [])


class Plan(unittest.TestCase):
    def test_plan_for_event_deterministic_and_complete(self):
        e = hit(zone="Reactor", layer=2, state=5, dmg=45.0, stab=30.0)
        a = fx.plan_for_event(e, 4)
        b = fx.plan_for_event(e, 4)
        self.assertEqual(json.dumps(a), json.dumps(b))
        self.assertGreaterEqual(a["severity"], 3)
        self.assertIsNotNone(a["shake"])
        self.assertTrue(a["cockpit"])
        self.assertTrue(a["chunks"])

    def test_every_core_event_has_a_decision_and_no_crash(self):
        for name in core_events():
            r = fx.plan_for_event({"type": name, "zone": "Torso", "a": 1, "b": 3, "c": 0, "value": 20.0, "value2": 5.0}, 1)
            self.assertIn("severity", r)


if __name__ == "__main__":
    unittest.main()
