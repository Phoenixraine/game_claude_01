"""cockpit_damage_spec.json: which named objects react at each severity S0..S4 (cumulative). Counts follow data/damage_fx/cockpit_effects.json (TASK-022); if that
file is present next to this repository the ranges are read from it, otherwise the same numbers embedded below are used. Pure Python (no bpy)."""
import json
import os
import random

HERE = os.path.dirname(os.path.abspath(__file__))
REF = os.path.join(HERE, "..", "..", "..", "data", "damage_fx", "cockpit_effects.json")

# (min, max) per effect and severity as in TASK-022; the spec takes the upper end rounded down so that S4 is the heaviest example
DEFAULT_COUNTS = {
    "steam_puff": {"S0": (0, 1), "S1": (1, 2)},
    "warn_on": {"S1": (1, 1), "S2": (3, 5), "S3": (6, 10), "S4": (12, 20)},
    "mon_glitch": {"S1": (1, 1), "S2": (1, 2), "S3": (1, 2)},
    "burst": {"S2": (1, 1), "S3": (2, 4), "S4": (5, 8)},
    "snap": {"S2": (1, 2), "S3": (3, 5), "S4": (6, 10)},
    "beacon": {"S2": (1, 1), "S3": (2, 3), "S4": (4, 4)},
    "crack": {"S2": (1, 1), "S3": (1, 2), "S4": (2, 3)},
    "fire": {"S3": (1, 1), "S4": (2, 3)},
    "scorch": {"S3": (1, 1), "S4": (2, 3)},
    "mon_dead": {"S3": (1, 2), "S4": (4, 6)},
    "strobe": {"S3": (1, 2), "S4": (3, 4)},
    "ok_off": {"S4": (8, 14)},
}
RED_LIGHT = {"S0": 0.0, "S1": 0.18, "S2": 0.4, "S3": 0.7, "S4": 1.0}
SHAKE_MULT = {"S0": 0.12, "S1": 0.4, "S2": 1.0, "S3": 1.7, "S4": 2.6}
SIREN = {"S0": None, "S1": None, "S2": "fx_alarm_beep", "S3": "fx_siren", "S4": "fx_siren"}
VOICE = {"S0": None, "S1": None, "S2": "vo_hull_damage", "S3": "vo_hull_damage", "S4": "vo_hull_critical"}
SEVERITIES = ["S0", "S1", "S2", "S3", "S4"]

ACTION_OF = {"Pipe_Burst": "burst", "Wire_Snapped": "snap", "Lamp_Warn": "warn_on", "Lamp_Ok": "ok_off", "AlarmBeacon": "beacon", "Glass_Crack_Mask": "crack", "Fire_Socket": "fire",
             "Scorch_Decal": "scorch", "StrobePanel": "strobe", "SteamPort": "steam_puff"}


def reference_counts():
    """Counts from data/damage_fx/cockpit_effects.json when it exists, else the embedded table. Returns (counts, source)."""
    if not os.path.exists(REF):
        return DEFAULT_COUNTS, "embedded (data/damage_fx/cockpit_effects.json not found)"
    with open(REF, encoding="utf-8") as f:
        c = json.load(f)
    table = {}
    names = {("SteamPort", "puff"): "steam_puff", ("Lamp_Warn", "on"): "warn_on", ("Mon", "glitch"): "mon_glitch", ("Pipe_Burst", "burst"): "burst", ("Wire_Snapped", "snap"): "snap",
             ("AlarmBeacon", "spin"): "beacon", ("Glass_Crack_Mask", "crack"): "crack", ("Fire_Socket", "ignite"): "fire", ("Scorch_Decal", "show"): "scorch", ("Mon", "dead"): "mon_dead",
             ("StrobePanel", "strobe"): "strobe", ("Lamp_Ok", "off"): "ok_off"}
    for sev, rows in c["severity"].items():
        for r in rows:
            k = names.get((r["target"], r["action"]))
            if k:
                table.setdefault(k, {})[sev] = tuple(r["count"])
    return table, "data/damage_fx/cockpit_effects.json"


def make_spec(names, seed=7):
    """names: dict of pools {class: [object names]}. Returns the cumulative spec. Pools are shuffled once, so every level is a prefix (superset of the previous)."""
    rng = random.Random(seed)
    counts, source = reference_counts()
    pools = {}
    for cls, lst in names.items():
        p = list(lst)
        rng.shuffle(p)
        pools[cls] = p
    spec = {"version": 1, "seed": seed, "source_of_counts": source, "red_light_peak": RED_LIGHT, "shake": {"profile": "HitEvent (data/damage_fx/shake_profiles.json)", "severity_mult": SHAKE_MULT,
            "limits": {"max_pos_cm": 12.0, "max_rot_deg": 4.0, "reduce_motion_mult": 0.25}}, "levels": {}}
    prev = {}
    for sev in SEVERITIES:
        lv = {}
        for cls, action in ACTION_OF.items():
            rng_ = counts.get(action, {}).get(sev)
            n = rng_[1] if rng_ else prev.get(cls, 0)
            n = max(n, prev.get(cls, 0))
            n = min(n, len(pools.get(cls, [])))
            prev[cls] = n
            if n:
                lv[cls] = pools[cls][:n]
        # monitors: dead and glitch are disjoint pools drawn from the same shuffled list (dead first, glitch after it)
        mons = pools.get("Mon", [])
        nd = min(len(mons), max(counts.get("mon_dead", {}).get(sev, (0, 0))[1], prev.get("mon_dead", 0)))
        prev["mon_dead"] = nd
        ng = min(len(mons) - nd, max(counts.get("mon_glitch", {}).get(sev, (0, 0))[1], prev.get("mon_glitch", 0)))
        prev["mon_glitch"] = ng
        if nd:
            lv["Mon_dead"] = mons[:nd]
        if ng:
            lv["Mon_glitch"] = mons[nd:nd + ng]
        lv["red_light_peak"] = RED_LIGHT[sev]
        lv["siren"] = SIREN[sev]
        lv["voice"] = VOICE[sev]
        lv["power_flicker"] = sev == "S4"
        lv["shake_mult"] = SHAKE_MULT[sev]
        spec["levels"][sev] = lv
    return spec


def pools_from_model(model):
    names = {"Pipe_Burst": [], "Wire_Snapped": [], "Lamp_Warn": [], "Lamp_Ok": [], "AlarmBeacon": [], "StrobePanel": [], "Scorch_Decal": [], "Mon": [], "Glass_Crack_Mask": []}
    for p in model.parts:
        if p.kind in names:
            names[p.kind].append(p.name)
        elif p.kind == "Lamp":
            names["Lamp_Warn" if p.name.startswith("Lamp_Warn") else "Lamp_Ok"].append(p.name)
    names["Glass_Crack_Mask"] = ["Glass_Crack_Mask_%02d" % k for k in range(4)]
    names["Fire_Socket"] = [e.name for e in model.empties if e.kind == "Fire_Socket"]
    names["SteamPort"] = [e.name for e in model.empties if e.kind == "SteamPort"]
    return names
