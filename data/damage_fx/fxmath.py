"""Damage-FX math (TASK-022): core event -> severity -> shake curves, cockpit effect commands, flying chunks, building destruction, warnings.

Pure Python 3 (standard library only), deterministic: every plan takes a `seed` and uses its own `random.Random`. The JSON tables next to this file
are the data; the functions here are the reference implementation the Unreal side ports (or replaces by loading the same tables).

    from fxmath import severity_for_event, shake_for_event, plan_cockpit_effects, plan_chunks, plan_building_break, warnings_for_event, plan_for_event
"""
import json
import math
import os
import random

HERE = os.path.dirname(os.path.abspath(__file__))
_cache = {}


def table(name):
    if name not in _cache:
        with open(os.path.join(HERE, name + ".json"), encoding="utf-8") as f:
            _cache[name] = json.load(f)
    return _cache[name]


LAYERS = ["Armor", "Mechanism", "System"]
ZONE_STATES = ["Intact", "Dented", "Exposed", "Damaged", "Critical", "Destroyed", "Severed"]
SWING = ["Up", "Left", "Right", "Down"]

DEFAULT_KNOBS = None


def knobs(over=None):
    k = dict(table("global_tuning")["knobs"])
    if over:
        k.update(over)
    return k


def _rng(seed, salt=""):
    return random.Random("%s|%s" % (seed, salt))


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


def _norm(v):
    n = math.sqrt(sum(c * c for c in v))
    return [c / n for c in v] if n > 1e-9 else [0.0, 0.0, 0.0]


# ------------------------------------------------------------------------------------------------------------------ severity
def severity_score(damage, layer="Armor", zone="Torso", blocked=False, parried=False, state_after="Intact", stability_damage=0.0, external_source=None):
    """Weighted strength of a hit as felt in the cockpit. 1.0 = an unblocked heavy strike (17.5) that only scratched the armour of a 'neutral' zone."""
    S = table("shake_profiles")["severity"]
    base = float(damage) / S["reference_damage"]
    s = base * S["layer_mult"][layer] * S["zone_weight"][zone]
    if parried:
        s *= S["parried_mult"]
    elif blocked:
        s *= S["blocked_mult"]
    if external_source is not None:
        s *= S["external_source_mult"].get(str(external_source), 1.0)
    s += S["state_bump"][state_after]
    s += min(S["stability_term"]["cap"], max(0.0, stability_damage) * S["stability_term"]["per_point"])
    return s


def severity_level(score):
    t = table("shake_profiles")["severity"]["thresholds"]
    lvl = 0
    for i, th in enumerate(t):
        if score > th:
            lvl = i + 1
    return lvl


def decode_event(event):
    """Normalises a raw core event dict {type, zone, a, b, c, value, value2} (or the same with named fields) into the fields the tables use."""
    e = dict(event)
    t = e.get("type")
    out = {"type": t, "zone": e.get("zone", "Torso"), "layer": "Armor", "state_after": "Intact", "blocked": False, "parried": False, "swing": None,
           "damage": float(e.get("value", 0.0)), "stability_damage": float(e.get("value2", 0.0)), "external_source": None, "system": e.get("system"), "status": e.get("status")}
    if t == "HitEvent":
        out["layer"] = LAYERS[int(e.get("a", 0))] if isinstance(e.get("a", 0), int) else e.get("a", "Armor")
        out["state_after"] = ZONE_STATES[int(e.get("b", 0))] if isinstance(e.get("b", 0), int) else e.get("b", "Intact")
        c = int(e.get("c", 0))
        out["swing"] = SWING[c & 3]
        out["blocked"] = bool(c & 4)
        out["parried"] = bool(c & 8)
    elif t == "ExternalHit":
        out["external_source"] = int(e.get("a", 0))
    elif t == "ArmorPlateLost":
        out["layer"] = "Armor"
    elif t == "ZoneState":
        out["state_after"] = ZONE_STATES[int(e.get("a", 0))]
    elif t == "LimbSevered":
        out["state_after"] = "Severed"
        out["layer"] = "System"
    elif t == "ReactorBreach":
        out["zone"] = "Reactor"
        out["layer"] = "System"
        out["state_after"] = "Damaged"
    elif t in ("UltimateFinisher", "UltimateSever"):
        out["layer"] = "System"
        out["state_after"] = "Destroyed"
    elif t == "BoardingBlast":
        out["layer"] = "Mechanism"
    return out


def severity_for_event(event):
    d = decode_event(event)
    if d["type"] == "BoardingSwatImpact":
        return 4, 9.0
    if d["type"] == "BoardingBlast":
        d["damage"] = d["damage"] or 30.0
    s = severity_score(d["damage"], d["layer"], d["zone"], d["blocked"], d["parried"], d["state_after"], d["stability_damage"], d["external_source"])
    return severity_level(s), s


# ------------------------------------------------------------------------------------------------------------------ shake
def _value_noise(rng_state, n, freq, rate):
    """Smooth noise, `n` samples at `rate` Hz with ~`freq` random knots per second (cosine interpolation)."""
    knots = int(freq * n / rate) + 3
    pts = [rng_state.uniform(-1.0, 1.0) for _ in range(knots)]
    out = []
    for i in range(n):
        x = i / rate * freq
        k = int(x)
        f = x - k
        f = (1 - math.cos(f * math.pi)) / 2
        out.append(pts[k] * (1 - f) + pts[k + 1] * f)
    return out


def _wave(comp, rate, rng):
    dur = comp["duration_s"]
    n = max(2, int(math.ceil(dur * rate)) + 1)
    out = []
    shape = comp["shape"]
    noise = _value_noise(rng, n, comp["freq_hz"], rate) if shape == "noise" else None
    ph = rng.uniform(0, 2 * math.pi) if shape == "damped_sine" else 0.0
    for i in range(n):
        t = i / rate
        u = t / dur
        env = math.exp(-comp["decay"] * t)
        if comp["attack_s"] > 0:
            env *= min(1.0, t / comp["attack_s"])
        taper = 1.0 if u < 0.7 else 0.5 * (1 + math.cos(math.pi * (u - 0.7) / 0.3))   # exactly zero at the end
        if shape == "damped_sine":
            v = math.sin(2 * math.pi * comp["freq_hz"] * t + ph) * env
        elif shape == "impulse":
            v = math.sin(math.pi * min(1.0, u)) ** 2
            taper = 1.0
        else:
            v = noise[i] * env
        out.append(v * taper)
    return out


def shake_direction(profile, zone, swing):
    S = table("shake_profiles")
    name = profile.get("direction", "none")
    if name == "impact":
        d = list(S["zone_direction"][zone])
        if swing:
            sd = S["swing_direction"][swing]
            d = [d[i] + sd[i] for i in range(3)]
        return _norm(d)
    return _norm(S["named_direction"][name]) if name in S["named_direction"] else [0.0, 0.0, 0.0]


def _soft_limit(vec, cap):
    m = math.sqrt(sum(c * c for c in vec))
    if m <= 1e-9:
        return vec
    s = cap * math.tanh(m / cap) / m
    return [c * s for c in vec]


def shake_for_event(event_type, damage=0.0, zone="Torso", layer="Armor", blocked=False, *, state_after="Intact", direction=None, stability_damage=0.0, seed=0,
                    reduce_motion=False, severity=None, external_source=None, knob_overrides=None):
    """Curves for one core event. Returns {t, pos_cm[[x,y,z]], rot_deg[[pitch,yaw,roll]], chroma, duration_s, severity, mult}; axes of pos: right, up, forward.
    Position and rotation are NOT yet limited against other shakes: use mix_shakes() for the final camera."""
    T = table("shake_profiles")
    profile = T["events"][event_type]
    K = knobs(knob_overrides)
    if severity is None:
        score = severity_score(damage, layer, zone, blocked, False, state_after, stability_damage, external_source)
        severity = severity_level(score)
    mult = T["severity_mult"][severity] if profile["scale"] == "severity" else profile.get("mult", 1.0)
    mult *= K["shake"]
    if reduce_motion or K["shake_reduce_motion"]:
        mult *= T["limits"]["reduce_motion_mult"]
    rate = T["limits"]["sample_hz"]
    rng = _rng(seed, event_type)
    d = shake_direction(profile, zone, direction)
    random_dir = d == [0.0, 0.0, 0.0]
    comps = [_wave(c, rate, rng) for c in profile["components"]]
    n = max(len(c) for c in comps)
    pos = [[0.0, 0.0, 0.0] for _ in range(n)]
    rot = [[0.0, 0.0, 0.0] for _ in range(n)]
    chroma = [0.0] * n
    for c, w in zip(profile["components"], comps):
        axes_noise = [_wave({**c, "shape": "noise", "freq_hz": min(c["freq_hz"], 3.4)}, rate, rng) for _ in range(3)] if random_dir else None
        for i, v in enumerate(w):
            if random_dir:
                dx, dy, dz = (axes_noise[0][i], axes_noise[1][i], axes_noise[2][i])
            else:
                dx, dy, dz = d[0] * v, d[1] * v, d[2] * v
            a = c["amp_cm"] * mult
            ax = c["axes"]
            pos[i][0] += a * dx * ax[0]
            pos[i][1] += a * dy * ax[1]
            pos[i][2] += a * dz * ax[2]
            b = c["amp_deg"] * mult
            rot[i][0] += b * (-0.5 * dz + 0.5 * dy)      # pitch: a push forward tips the view down
            rot[i][1] += b * 0.5 * dx
            rot[i][2] += b * 0.6 * dx
            chroma[i] += c["chroma"] * abs(v) * min(2.0, mult)
    lim = T["limits"]
    pos = [_soft_limit(p, lim["max_pos_cm"]) for p in pos]
    rot = [_soft_limit(r, lim["max_rot_deg"]) for r in rot]
    return {"t": [i / rate for i in range(n)], "pos_cm": pos, "rot_deg": rot, "chroma": [min(1.0, c) for c in chroma], "duration_s": (n - 1) / rate, "severity": severity, "mult": mult}


def mix_shakes(shakes, offsets=None):
    """Sum several shakes (each starting at offsets[i] seconds) and limit the SUM: <= 12 cm and <= 4 deg at every sample."""
    T = table("shake_profiles")["limits"]
    rate = T["sample_hz"]
    offsets = offsets or [0.0] * len(shakes)
    n = max(int(round(o * rate)) + len(s["t"]) for s, o in zip(shakes, offsets))
    pos = [[0.0, 0.0, 0.0] for _ in range(n)]
    rot = [[0.0, 0.0, 0.0] for _ in range(n)]
    chroma = [0.0] * n
    for s, o in zip(shakes, offsets):
        k0 = int(round(o * rate))
        for i in range(len(s["t"])):
            for a in range(3):
                pos[k0 + i][a] += s["pos_cm"][i][a]
                rot[k0 + i][a] += s["rot_deg"][i][a]
            chroma[k0 + i] += s["chroma"][i]
    pos = [_soft_limit(p, T["max_pos_cm"]) for p in pos]
    rot = [_soft_limit(r, T["max_rot_deg"]) for r in rot]
    return {"t": [i / rate for i in range(n)], "pos_cm": pos, "rot_deg": rot, "chroma": [min(1.0, c) for c in chroma], "duration_s": (n - 1) / rate}


def shake_for_core_event(event, seed=0, reduce_motion=False):
    """Convenience: raw core event dict -> shake (None when the event type has no shake profile)."""
    d = decode_event(event)
    if d["type"] not in table("shake_profiles")["events"]:
        return None
    lvl, _ = severity_for_event(event)
    return shake_for_event(d["type"], d["damage"], d["zone"], d["layer"], d["blocked"], state_after=d["state_after"], direction=d["swing"], stability_damage=d["stability_damage"],
                           seed=seed, reduce_motion=reduce_motion, severity=lvl, external_source=d["external_source"])


# ------------------------------------------------------------------------------------------------------------------ cockpit
def new_cockpit_state():
    return {"burst": [], "snapped": [], "dead_mon": [], "fires": {}, "cracks": [], "scorch": [], "beacons": [], "time": 0.0}


DESTRUCTIVE = {"burst": "burst", "snap": "snapped", "dead": "dead_mon", "ignite": "fires", "crack": "cracks", "show": "scorch"}


def _pick_ids(cls, count, rng, taken):
    n = table("identifiers")["cockpit"].get(cls, 1)
    pool = [i for i in range(n) if i not in taken]
    rng.shuffle(pool)
    return pool[:count]


def _inst(cls, i):
    return "%s_%02d" % (cls, i) if cls in table("identifiers")["cockpit"] else cls


def plan_cockpit_effects(severity, seed, state=None, knob_overrides=None):
    """Deterministic list of cockpit commands {t, target, action, duration_s, params} for one hit of severity 0..4.
    `state` (see new_cockpit_state) remembers what is already broken: destroyed things are not destroyed twice. Returns (commands, new_state)."""
    C = table("cockpit_effects")
    K = knobs(knob_overrides)
    sev = "S%d" % severity
    rng = _rng(seed, "cockpit%d" % severity)
    st = json.loads(json.dumps(state)) if state else new_cockpit_state()
    t0 = st.get("time", 0.0)
    cmds = []
    for e in C["severity"][sev]:
        if rng.random() > e["probability"]:
            continue
        lo, hi = e["count"]
        cnt = rng.randint(lo, hi)
        mult = K["cockpit_fire"] if e["action"] == "ignite" else K["cockpit_effects_count"]
        cnt = int(round(cnt * mult))
        if e["action"] == "ignite":
            cnt = min(cnt, C["fire"]["max_simultaneous"] - len(st["fires"]))
        cls = e["target"]
        key = DESTRUCTIVE.get(e["action"])
        taken = set(st[key].keys() if key == "fires" and isinstance(st[key], dict) else st[key]) if key else set()
        taken = {int(x) for x in taken}
        ids = _pick_ids(cls, cnt, rng, taken) if cls in table("identifiers")["cockpit"] else [None] * cnt
        for i in ids:
            t = t0 + rng.uniform(*e["delay_s"])
            dur = rng.uniform(*e["duration_s"])
            target = _inst(cls, i) if i is not None else cls
            cmds.append({"t": round(t, 3), "target": target, "action": e["action"], "duration_s": round(dur, 3), "params": dict(e["params"])})
            if key:
                if key == "fires":
                    st["fires"][str(i)] = round(t, 3)
                else:
                    st[key].append(i)
            if e["action"] == "burst":
                cmds.append({"t": round(t, 3), "target": _inst("LeakPoint", i), "action": "leak", "duration_s": round(dur, 3), "params": {"system": e["params"].get("system", "ps_steam_jet")}})
                cmds.append({"t": round(t, 3), "target": _inst("SteamPort", i), "action": "steam", "duration_s": round(dur, 3), "params": {"system": e["params"].get("system", "ps_steam_jet")}})
            if e["action"] == "snap":
                cmds.append({"t": round(t, 3), "target": _inst("SparkPort", i), "action": "sparks", "duration_s": round(min(dur, 5.0), 3), "params": {"system": "ps_sparks_wire"}})
    siren, voice = C["siren"][sev], C["voice"][sev]
    if siren:
        cmds.append({"t": round(t0 + 0.2, 3), "target": "Audio", "action": "play", "duration_s": siren["duration_s"] * K["siren_volume"], "params": {"id": siren["sound"], "volume": K["siren_volume"]}})
    if voice:
        cmds.append({"t": round(t0 + voice["delay_s"], 3), "target": "Audio", "action": "voice", "duration_s": 2.0, "params": {"id": voice["id"]}})
    rl = C["red_light"][sev]
    if rl["peak"] > 0:
        cmds.append({"t": round(t0, 3), "target": "Camera_Rig", "action": "red_light", "duration_s": rl["fade_s"], "params": {"severity": sev, "peak": rl["peak"] * K["red_light"]}})
    cmds.sort(key=lambda c: (c["t"], c["target"], c["action"]))
    return cmds, st


def red_light_curve(severity, seed=0, dt=1.0 / 30.0, knob_overrides=None):
    """Intensity (0..1) of the red cockpit light after a hit: a pulsing wave that fades out. [(t, value)]."""
    rl = table("cockpit_effects")["red_light"]["S%d" % severity]
    K = knobs(knob_overrides)
    if rl["peak"] <= 0:
        return [(0.0, 0.0)]
    n = int(rl["fade_s"] / dt) + 1
    out = []
    for i in range(n):
        t = i * dt
        fade = 1.0 - t / rl["fade_s"]
        pulse = 0.5 * (1 + math.sin(2 * math.pi * t / rl["period_s"] - math.pi / 2))
        v = (rl["base"] + (rl["peak"] - rl["base"]) * pulse) * max(0.0, fade) ** 0.7
        out.append((round(t, 4), min(1.0, v * K["red_light"])))
    return out


def plan_fire_spread(state, seed, horizon_s, last_severity=3, knob_overrides=None):
    """Fire in the cockpit: every burning socket may ignite a neighbour (graph of Fire_Socket), burns for burn_s, and is put out by the extinguisher
    after extinguish_after_s unless the last hit was at least `extinguish_below`. Returns commands + new state."""
    C = table("cockpit_effects")["fire"]
    G = table("identifiers")["fire_graph"]["edges"]
    K = knobs(knob_overrides)
    rng = _rng(seed, "fire")
    st = json.loads(json.dumps(state))
    adj = {}
    for a, b in G:
        adj.setdefault(a, []).append(b)
        adj.setdefault(b, []).append(a)
    cmds = []
    ends = {}
    for sid, t_ign in st["fires"].items():
        ends[int(sid)] = {"start": t_ign, "end": t_ign + rng.uniform(*C["burn_s"]), "ext": t_ign + rng.uniform(*C["extinguish_after_s"])}
    ext_ok = last_severity < int(C["extinguish_below"][1:])
    t = st.get("time", 0.0)
    step = 1.0
    now = t
    while now < t + horizon_s:
        for sid in sorted(ends):
            e = ends[sid]
            if e.get("dead") or now < e["start"]:
                continue
            end = min(e["end"], e["ext"]) if ext_ok else e["end"]
            if now >= end:
                e["dead"] = True
                cmds.append({"t": round(now, 3), "target": _inst("Fire_Socket", sid), "action": "extinguish", "duration_s": 1.0, "params": {"sound": "fx_extinguisher" if ext_ok else "fx_fire_loop"}})
                continue
            if sum(1 for x in ends.values() if not x.get("dead")) >= C["max_simultaneous"]:
                continue
            for nb in sorted(adj.get(sid, [])):
                if nb in ends or sum(1 for x in ends.values() if not x.get("dead")) >= C["max_simultaneous"]:
                    continue
                if rng.random() < C["spread_per_s"] * step * K["cockpit_fire"]:
                    ends[nb] = {"start": now, "end": now + rng.uniform(*C["burn_s"]), "ext": now + rng.uniform(*C["extinguish_after_s"])}
                    cmds.append({"t": round(now, 3), "target": _inst("Fire_Socket", nb), "action": "ignite", "duration_s": round(ends[nb]["end"] - now, 3), "params": {"system": "ps_fire_small", "spread_from": sid}})
                    st["fires"][str(nb)] = round(now, 3)
        now += step
    for sid, e in ends.items():
        if e.get("dead"):
            st["fires"].pop(str(sid), None)
    st["time"] = t + horizon_s
    cmds.sort(key=lambda c: (c["t"], c["target"], c["action"]))
    return cmds, st


# ------------------------------------------------------------------------------------------------------------------ mech chunks
ZONE_ANCHOR = {"Head": (0.0, -4.0, 75.0), "Torso": (0.0, -9.0, 58.0), "Reactor": (0.0, 12.0, 57.0), "ShoulderL": (15.0, 0.0, 66.0), "ShoulderR": (-15.0, 0.0, 66.0),
               "ArmL": (19.0, -6.0, 44.0), "ArmR": (-19.0, -6.0, 44.0), "LegL": (9.5, -2.0, 24.0), "LegR": (-9.5, -2.0, 24.0)}
ZONE_NORMAL = {"Head": (0.0, -1.0, 0.1), "Torso": (0.0, -1.0, 0.0), "Reactor": (0.0, 1.0, 0.0), "ShoulderL": (0.8, -0.5, 0.3), "ShoulderR": (-0.8, -0.5, 0.3),
               "ArmL": (0.8, -0.6, 0.0), "ArmR": (-0.8, -0.6, 0.0), "LegL": (0.7, -0.7, 0.0), "LegR": (-0.7, -0.7, 0.0)}


def flight_range(v, z0, g, drag):
    """Horizontal range of a projectile with linear drag, by a short numeric integration (2 ms)."""
    x, y, z = 0.0, 0.0, z0
    vx, vy, vz = math.hypot(v[0], v[1]), 0.0, v[2]
    t = 0.0
    dt = 0.002
    while z > 0.0 and t < 30.0:
        vx -= drag * vx * dt
        vz -= (g + drag * vz) * dt
        x += vx * dt
        z += vz * dt
        t += dt
    return x


def plan_chunks(event, seed, knob_overrides=None):
    """Flying pieces for one core event. event = {type, zone, a (layer for HitEvent), plate_index?, normal?, hit_point?, severity?}. Returns a list of chunk dicts."""
    M = table("mech_chunks")
    K = knobs(knob_overrides)
    d = decode_event(event)
    rule = M["event_rules"].get(d["type"])
    if rule is None:
        return []
    sev = event.get("severity")
    if sev is None:
        sev = severity_for_event(event)[0]
    zone = rule.get("zone", d["zone"])
    if "min_severity" in rule and sev < int(rule["min_severity"][1:]):
        return []
    layers = rule.get("layers") or [d["layer"]]
    if "min_layer" in rule and LAYERS.index(d["layer"]) < LAYERS.index(rule["min_layer"]):
        return []
    if "layers" not in rule:
        layers = [d["layer"]]
    rng = _rng(seed, "chunks|%s|%s" % (d["type"], zone))
    anchor = list(event.get("hit_point") or ZONE_ANCHOR[zone])
    normal = _norm(event.get("normal") or ZONE_NORMAL[zone])
    B = M["ballistics"]
    out = []
    serial = 0
    rows = []
    for lay in layers:
        rows += M["zones"][zone][lay]
    if rule.get("extra") == "limb_part":
        rows.append(M["limb_part"])
    for row in rows:
        lo, hi = row["count"]
        cnt = rng.randint(lo, hi)
        cnt = int(round(cnt * rule["count_mult"] * K["chunks_count"] * (0.6 + 0.2 * sev)))
        for _ in range(cnt):
            if row["type"] == "armor_plate_burning" and rng.random() > 0.6 + 0.1 * sev:
                continue
            speed = rng.uniform(*row["speed_mps"]) * rule.get("scale", 1.0) * B["speed_scale_by_severity"][sev] * K["chunks_speed"]
            spread = math.radians(B["spread_deg"])
            # outward direction with a random cone and an upward bias
            ang = rng.uniform(0, 2 * math.pi)
            r = math.tan(rng.uniform(0, spread))
            perp1 = _norm([-normal[1], normal[0], 0.0]) if abs(normal[2]) < 0.9 else [1.0, 0.0, 0.0]
            perp2 = _norm([normal[1] * perp1[2] - normal[2] * perp1[1], normal[2] * perp1[0] - normal[0] * perp1[2], normal[0] * perp1[1] - normal[1] * perp1[0]])
            dirv = _norm([normal[i] + r * (math.cos(ang) * perp1[i] + math.sin(ang) * perp2[i]) for i in range(3)])
            v = [dirv[0] * speed, dirv[1] * speed, dirv[2] * speed + B["min_up_mps"] + rng.uniform(0, 0.4) * speed]
            pos = [anchor[i] + normal[i] * B["spawn_offset_m"] + rng.uniform(-1.5, 1.5) for i in range(3)]
            pos[2] = max(0.5, pos[2])
            z0 = pos[2]
            limit = B["max_range_m"] * 0.98          # margin for the integrator step difference
            while flight_range(v, z0, B["gravity"], B["drag_per_s"]) > limit and v[0] ** 2 + v[1] ** 2 > 1e-6:
                v = [v[0] * 0.92, v[1] * 0.92, v[2]]
            burning = rng.random() < row["fire_prob"]
            out.append({
                "id": "%s_%s_%02d" % (d["type"], zone, serial), "type": row["type"], "mesh_hint": row["mesh_hint"], "zone": zone,
                "pos": [round(c, 3) for c in pos], "vel": [round(c, 3) for c in v],
                "spin_rad_s": round(rng.uniform(*row["spin_rad_s"]) * (1 if rng.random() < 0.5 else -1), 3),
                "mass_kg": round(rng.uniform(*row["mass_kg"]), 2), "life_s": round(rng.uniform(*row["life_s"]), 2),
                "fire": {"on": burning, "duration_s": round(rng.uniform(*row["fire_s"]), 2) if burning else 0.0, "system": "ps_debris_trail_fire" if burning else None},
                "smoke_s": round(rng.uniform(*row["smoke_s"]), 2) if (burning or row["smoke_s"][1] > 0 and rng.random() < 0.5) else 0.0,
                "ground_sparks": row["ground_sparks"],
            })
            serial += 1
    return out


def simulate_chunk(chunk, colliders=(), dt=1.0 / 120.0, gravity=None, drag=None):
    """Integrates one chunk. colliders = [{"x","y","r","h"}] vertical cylinders (mechs). Stops at the ground or at the first collider.
    Returns {"points": [[x,y,z]...], "range_m", "hit": index of the collider or None, "t_land"}."""
    B = table("mech_chunks")["ballistics"]
    g = B["gravity"] if gravity is None else gravity
    k = B["drag_per_s"] if drag is None else drag
    p = list(chunk["pos"])
    v = list(chunk["vel"])
    pts = [list(p)]
    t = 0.0
    start = list(p)
    hit = None
    while t < 40.0:
        v[0] -= k * v[0] * dt
        v[1] -= k * v[1] * dt
        v[2] -= (g + k * v[2]) * dt
        q = [p[i] + v[i] * dt for i in range(3)]
        for ci, c in enumerate(colliders):
            inside_new = math.hypot(q[0] - c["x"], q[1] - c["y"]) < c["r"] and 0.0 <= q[2] <= c["h"]
            inside_old = math.hypot(p[0] - c["x"], p[1] - c["y"]) < c["r"] and 0.0 <= p[2] <= c["h"]
            if inside_new and not inside_old:
                hit = ci
                break
        if hit is not None:
            pts.append(list(p))
            break
        p = q
        t += dt
        if int(t / dt) % 6 == 0:
            pts.append(list(p))
        if p[2] <= 0.0:
            p[2] = 0.0
            pts.append(list(p))
            break
    return {"points": pts, "range_m": math.hypot(p[0] - start[0], p[1] - start[1]), "hit": hit, "t_land": t}


# ------------------------------------------------------------------------------------------------------------------ buildings
def plan_building_break(kind, energy, normal, building_params, seed, knob_overrides=None):
    """Destruction plan of a building. kind = sword_hit | mech_crash | thrown_debris | plasma | rockets; energy in kJ; normal = outward normal of the hit face;
    building_params = {height_m, width_m, depth_m, floors, material, glass_ratio}. The counts are scaled by the energy / material and then CLAMPED to the CPU budget."""
    B = table("building_destruction")
    K = knobs(knob_overrides)
    sc = B["scenarios"][kind]
    p = dict({"height_m": 60.0, "width_m": 30.0, "depth_m": 25.0, "floors": 15, "material": "concrete", "glass_ratio": 0.2}, **building_params)
    rng = _rng(seed, "building|%s" % kind)
    e = _clamp(float(energy) / sc["energy_ref_kj"], 0.05, 6.0)
    scale = _clamp(e ** 0.8, 0.35, 2.2) * K["building_shards"]
    nrm = _norm(normal)
    mat = B["material_scale"].get(p["material"], {})
    spawns = []
    for st in sc["stages"]:
        for s in st["spawns"]:
            cls = s["class"]
            cnt = s["count"] * scale * mat.get(cls, 1.0)
            if cls == "Slab_Concrete":
                cnt *= _clamp(p["floors"] / 6.0, 0.5, 3.0)
            if cls == "Glass_Shard":
                cnt *= 0.4 + 2.4 * p["glass_ratio"]
            cnt = int(round(cnt))
            if cnt <= 0 and s["count"] > 0 and B["classes"][cls] == "large" and e > 0.3:
                cnt = 1
            if cnt <= 0:
                continue
            spawns.append({"stage": st["name"], "t_s": round(s["t_s"] + rng.uniform(0.0, 0.05), 3), "class": cls, "budget": B["classes"][cls], "count": cnt,
                           "speed_mps": [round(x * _clamp(e ** 0.4, 0.6, 1.4), 2) for x in s["speed_mps"]], "cone_deg": s["cone_deg"], "normal": [round(c, 4) for c in nrm],
                           "mass_kg": s["mass_kg"], "life_s": s["life_s"]})
    totals = {"large": sum(s["count"] for s in spawns if s["budget"] == "large"), "small": sum(s["count"] for s in spawns if s["budget"] == "small")}
    for kind_b, cap in (("large", B["budgets"]["large_shards"]), ("small", B["budgets"]["small_shards"])):
        if totals[kind_b] > cap:
            f = cap / totals[kind_b]
            for s in spawns:
                if s["budget"] == kind_b:
                    s["count"] = max(1, int(s["count"] * f))
            totals[kind_b] = sum(s["count"] for s in spawns if s["budget"] == kind_b)
            while totals[kind_b] > cap:     # the max(1, ...) floor can overshoot: trim the biggest spawn
                big = max((s for s in spawns if s["budget"] == kind_b), key=lambda s: s["count"])
                big["count"] -= 1
                totals[kind_b] -= 1
    sm = B["smoke_puffs"]
    n_puffs = int(_clamp(sm["base"] + sm["per_energy_unit"] * e, 0, sm["max"]) * K["building_dust"])
    n_puffs = min(n_puffs, sm["max"])
    puffs = []
    for i in range(n_puffs):
        puffs.append({"t_s": round(rng.uniform(0.0, 3.0), 3), "offset_m": [round(rng.uniform(-p["width_m"] / 2, p["width_m"] / 2), 2), round(rng.uniform(-p["depth_m"] / 2, p["depth_m"] / 2), 2),
                      round(rng.uniform(0, p["height_m"] * 0.7), 2)], "size_m": round(rng.uniform(6.0, 18.0) * (0.7 + 0.3 * e), 2), "life_s": round(rng.uniform(*sm["lifetime_s"]), 2),
                      "system": "ps_dust_puff"})
    dust = B["dust"][p["material"]]
    vol = 3000.0 * e * (p["height_m"] / 60.0)
    plan = {"kind": kind, "energy_norm": round(e, 4), "material": p["material"], "spawns": sorted(spawns, key=lambda s: (s["t_s"], s["class"])), "smoke_puffs": puffs,
            "dust": {"color": dust["color"], "density": [[t, round(v * K["building_dust"], 4)] for t, v in dust["density"]], "peak_volume_m3": round(vol * K["building_dust"], 1), "system": "ps_dust_cloud"},
            "sounds": [{"t_s": 0.0, "id": B["sounds"]["contact"]}, {"t_s": 0.15, "id": B["sounds"]["facade_crush"]}, {"t_s": 0.7, "id": B["sounds"]["floor_collapse"]},
                       {"t_s": 1.0, "id": B["sounds"]["debris_rain"]}, {"t_s": 0.5, "id": B["sounds"]["dust_cloud"]}] + ([{"t_s": 0.2, "id": B["sounds"]["glass_rain"]}] if p["glass_ratio"] > 0.3 or p["material"] == "glass_curtain" else []),
            "totals": {"large_shards": totals["large"], "small_shards": totals["small"], "smoke_puffs": len(puffs)}, "cpu_particle_tick_hz": B["budgets"]["cpu_particle_tick_hz"]}
    return plan


# ------------------------------------------------------------------------------------------------------------------ warnings
def warnings_for_event(event):
    """Ids of the warnings an event raises (the table `warnings.json`). Events: raw core event dict, plus optional 'system' / 'status' names."""
    W = table("warnings")["warnings"]
    d = decode_event(event)
    sev = severity_for_event(event)[0] if d["type"] in ("HitEvent", "ExternalHit") else 0
    out = []
    for w in W:
        tr = w["trigger"]
        if tr["event"] != d["type"]:
            continue
        if "min_severity" in tr and sev < int(tr["min_severity"][1:]):
            continue
        if "zones" in tr and d["zone"] not in tr["zones"]:
            continue
        if "system" in tr and d.get("system") != tr["system"]:
            continue
        if "status" in tr and d.get("status") != tr["status"]:
            continue
        out.append(w["id"])
    return out


def active_warning(ids):
    """The single warning that owns the siren / voice: the highest priority (lowest number); ties go to the table order."""
    W = {w["id"]: (w["priority"], i) for i, w in enumerate(table("warnings")["warnings"])}
    return min(ids, key=lambda i: W[i]) if ids else None


def plan_for_event(event, seed=0, state=None):
    """Everything the game does for one core event: severity, shake, cockpit commands, chunks, warnings (what docs/ux/damage_fx.md describes)."""
    lvl, score = severity_for_event(event)
    sh = shake_for_core_event(event, seed)
    cockpit = []
    st = state
    if event["type"] in table("coverage")["cockpit_by_severity"] and lvl > 0:
        cockpit, st = plan_cockpit_effects(lvl, seed, state)
    return {"severity": lvl, "score": score, "shake": sh, "cockpit": cockpit, "chunks": plan_chunks(event, seed), "warnings": warnings_for_event(event), "state": st}
