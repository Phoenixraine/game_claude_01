"""Step-cycle generator for an 82 m, >8000 t biped: weight shift -> lift -> swing -> plant, no foot sliding.

Gait table (pitch §11: not a human run; step 18-26 m, 3.0-4.5 s per step when walking). A *step* is the interval between two
consecutive heel strikes of opposite feet; one full cycle = two steps. The pelvis is lowered so the planted leg never has to be
fully straight (leg length hip->ankle = 37.2 m).
"""
import math

import numpy as np

from . import rig

FPS = 30
LEG_REACH = float(np.linalg.norm(rig.REST["shin_l"] - rig.REST["thigh_l"]) + np.linalg.norm(rig.REST["foot_l"] - rig.REST["shin_l"]))

# name -> (step length m, step period s, swing foot clearance m, pelvis sway m, bob m, arm swing deg, torso lean deg)
GAITS = {
    "walk_slow": dict(L=18.0, T=4.5, clearance=4.0, sway=3.5, bob=0.9, arm=10.0, lean=3.0),
    "walk": dict(L=22.0, T=3.8, clearance=5.0, sway=4.0, bob=1.1, arm=13.0, lean=4.0),
    "walk_fast": dict(L=26.0, T=3.0, clearance=6.0, sway=4.5, bob=1.3, arm=17.0, lean=6.0),
    "run": dict(L=28.0, T=2.6, clearance=7.0, sway=5.0, bob=1.6, arm=24.0, lean=10.0),   # heavy stomp: no flight phase
}
PHASE = dict(shift=0.22, lift=0.10, swing=0.48, plant=0.20)    # fractions of one step (sum 1.0)
U_LIFT = PHASE["shift"] + PHASE["lift"] * 0.5                  # the swing foot leaves the ground
U_PLANT = PHASE["shift"] + PHASE["lift"] + PHASE["swing"]      # ...and lands again


def table():
    """Length/frequency table for the docs and export: speed, cadence and the lowered pelvis height per gait."""
    out = {}
    for n, g in GAITS.items():
        out[n] = {"step_length_m": g["L"], "step_period_s": g["T"], "speed_mps": round(g["L"] / g["T"], 2),
                  "speed_kmh": round(g["L"] / g["T"] * 3.6, 1), "steps_per_min": round(60.0 / g["T"], 1),
                  "pelvis_height_m": round(pelvis_height(g["L"]), 2), "pelvis_drop_m": round(rig.REST["pelvis"][2] - pelvis_height(g["L"]), 2)}
    return out


def pelvis_height(L, margin=0.93):
    """Hip height such that the front foot (L/2 ahead) is within `margin` of the full leg length."""
    hip_to_ankle_h = math.sqrt(max(1.0, (LEG_REACH * margin) ** 2 - (L / 2.0) ** 2))
    return rig.GROUND_ANKLE_Z + hip_to_ankle_h + (rig.REST["thigh_l"][2] - rig.REST["pelvis"][2])


def _smooth(u):
    u = min(1.0, max(0.0, u))
    return u * u * (3 - 2 * u)


def _rotz(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s], [s, c]])


class Clip:
    """Result of a generator: per-frame dicts."""

    def __init__(self, name, fps, gait, frames, plants):
        self.name, self.fps, self.gait, self.frames, self.plants = name, fps, gait, frames, plants

    def to_json(self):
        return {"name": self.name, "fps": self.fps, "gait": self.gait, "duration_s": round(len(self.frames) / self.fps, 3),
                "frames": self.frames, "plants": self.plants}


def generate(name, gait, steps, first_swing="r", fps=FPS, start_pos=(0.0, 0.0), start_heading=0.0, init="stand"):
    """Generate a clip. `steps` = list of dicts {L: step length scale in m, turn: heading change in degrees over the step,
    T (optional): period}. The foot that swings in step k alternates, starting with `first_swing`."""
    g = GAITS[gait]
    hip_off = rig.REST["thigh_l"][0]
    ankle_z = rig.GROUND_ANKLE_Z
    pos = np.array(start_pos, dtype=float)
    psi = math.radians(start_heading)
    # initial planted feet: standing stance (rest offsets) under the pelvis
    side_sign = {"l": 1.0, "r": -1.0}
    plant = {s: pos + _rotz(psi) @ np.array([side_sign[s] * hip_off, 0.0]) for s in "lr"}
    plant_heading = {s: psi for s in "lr"}
    if init == "stride":   # start in mid-stride: stance foot L/2 ahead of the pelvis, the foot about to swing L/2 behind
        L0 = steps[0].get("L", g["L"])
        st0 = "l" if first_swing == "r" else "r"
        plant[st0] = pos + _rotz(psi) @ np.array([side_sign[st0] * hip_off, -L0 / 2.0])
        plant[first_swing] = pos + _rotz(psi) @ np.array([side_sign[first_swing] * hip_off, L0 / 2.0])
    # pelvis start = between the feet; world frame: forward is local -Y
    frames, plants = [], []
    t_global = 0.0
    swing = first_swing
    c0, psi0 = pos.copy(), psi
    for k, st in enumerate(steps):
        L = st.get("L", g["L"])
        T = st.get("T", g["T"])
        clear_mul = st.get("clear", 1.0)       # swing-foot clearance multiplier (a dragging leg lifts less)
        hike = st.get("roll", 0.0)             # pelvis roll in degrees (hip hike while the damaged leg swings)
        turn = math.radians(st.get("turn", 0.0))
        psi1 = psi0 + turn
        fwd0 = _rotz(psi0) @ np.array([0.0, -1.0])
        fwd1 = _rotz((psi0 + psi1) / 2) @ np.array([0.0, -1.0])
        c1 = c0 + fwd1 * L
        # the swinging foot lands L/2 ahead of the pelvis position at the end of the step (a pure turn lands it beside the other foot)
        land = c1 + _rotz(psi1) @ np.array([side_sign[swing] * hip_off, -L / 2.0 if L > 1e-6 else 0.0])
        stance = "l" if swing == "r" else "r"
        p_from = plant[swing].copy()
        n = max(2, int(round(T * fps)))
        drop_start = rig.REST["pelvis"][2] - pelvis_height(max(L, 4.0))
        for i in range(n):
            u = i / n
            e = u
            c = c0 + (c1 - c0) * e
            psi_t = psi0 + (psi1 - psi0) * _smooth(u)
            # pelvis height: lowest at double support, highest mid-stance
            z_p = pelvis_height(max(L, 4.0)) + g["bob"] * (0.5 - 0.5 * math.cos(2 * math.pi * u)) - g["bob"] * 0.5
            sway_dir = side_sign[stance]
            sway = sway_dir * g["sway"] * math.sin(math.pi * u) * (min(1.0, L / g["L"]) if L > 0 else 0.4)
            lateral = _rotz(psi_t) @ np.array([sway, 0.0])
            root_xy = c + lateral
            # swing foot trajectory
            if u < U_LIFT:
                w, h = 0.0, 0.0
            elif u < U_PLANT:
                w = (u - U_LIFT) / (U_PLANT - U_LIFT)
                h = g["clearance"] * clear_mul * math.sin(math.pi * w) ** 1.2 if L > 1e-6 or abs(turn) > 1e-6 else 0.0
            else:
                w, h = 1.0, 0.0
            we = _smooth(w) * 0.65 + w * 0.35
            sw_xy = p_from + (land - p_from) * we
            on_ground_swing = u < U_LIFT or u >= U_PLANT
            feet_xy = {stance: plant[stance], swing: sw_xy}
            feet_z = {stance: 0.0, swing: h}
            feet_psi = {stance: plant_heading[stance], swing: plant_heading[swing] + (psi1 - plant_heading[swing]) * _smooth(w)}
            frames.append(_solve_frame(t_global + u * T, root_xy, z_p, psi_t, turn, u, g, k, feet_xy, feet_z, feet_psi,
                                       {stance: True, swing: on_ground_swing}, swing, ankle_z, hike * math.sin(math.pi * u)))
        t_global += n / fps
        plants.append({"step": k, "foot": swing, "t": round(t_global, 3), "pos": [round(float(land[0]), 3), round(float(land[1]), 3)]})
        plant[swing] = land
        plant_heading[swing] = psi1
        c0, psi0 = c1, psi1
        swing = stance
    return Clip(name, fps, gait, frames, plants)


def _solve_frame(t, root_xy, z_p, psi, turn_per_step, u, g, k, feet_xy, feet_z, feet_psi, contact, swing, ankle_z, hike=0.0):
    root_z = z_p - rig.REST["pelvis"][2]
    root_pos = np.array([root_xy[0], root_xy[1], root_z])
    sgn_swing = 1.0 if swing == "l" else -1.0
    # upper body: counter-rotation of torso against the pelvis, arms opposite to the legs, small forward lean
    ph = math.sin(math.pi * u) * sgn_swing           # + while the left foot swings
    pel_yaw = 0.0 + 5.0 * (1 - 2 * u) * sgn_swing * 0.0
    pelvis = [0.0, hike, 5.0 * math.cos(math.pi * u) * sgn_swing]
    torso = [g["lean"], 0.0, -4.5 * math.cos(math.pi * u) * sgn_swing]
    head = [-g["lean"] * 0.6, 0.0, 3.0 * math.cos(math.pi * u) * sgn_swing]
    joints = {"root": [0.0, 0.0, math.degrees(psi)], "pelvis": pelvis, "torso": torso, "head": head}
    a = g["arm"]
    arm_l = -a * math.cos(math.pi * u) * sgn_swing * -1.0      # left arm moves with the right leg
    joints["upperarm_l"] = [-18 + a * math.cos(math.pi * u) * sgn_swing, -10.0, 4.0]
    joints["upperarm_r"] = [-18 - a * math.cos(math.pi * u) * sgn_swing, 10.0, -4.0]
    joints["forearm_l"] = [-45 - 0.5 * a * math.sin(math.pi * u), 0, 0]
    joints["forearm_r"] = [-45 - 0.5 * a * math.sin(math.pi * u), 0, 0]
    joints["hand_l"] = [-6, 0, 0]
    joints["hand_r"] = [-6, 0, 0]
    base = {b: e for b, e in joints.items()}
    F0 = rig.fk(base, root_pos)
    out = dict(joints)
    ik_err = 0.0
    for s in "lr":
        tgt = np.array([feet_xy[s][0], feet_xy[s][1], ankle_z + feet_z[s]])
        # thigh twist so the foot faces its own heading even when the pelvis is turned
        rel = math.degrees(feet_psi[s] - psi - math.radians(pelvis[2]))
        rel = max(-28.0, min(28.0, rel))
        # foot is world-flat but yawed to its heading
        sol = rig.solve_limb("leg", s, F0["pelvis"], tgt, foot_yaw=rel, hand_world_rot=rig.rz(math.degrees(feet_psi[s])))
        for b, e in sol["angles"].items():
            out[b] = [float(x) for x in e]
        ik_err = max(ik_err, sol["error_m"])
    F = rig.fk(out, root_pos)
    fc = rig.foot_contacts(F)
    return {
        "t": round(t, 4), "root_pos": [round(float(x), 4) for x in root_pos],
        "joints": {b: [round(float(x), 3) for x in out[b]] for b in rig.BONES if b in out},
        "contact": {s: bool(contact[s]) for s in "lr"},
        "ankle": {s: [round(float(x), 3) for x in fc[s]["ankle"]] for s in "lr"},
        "heel": {s: [round(float(x), 3) for x in fc[s]["heel"]] for s in "lr"},
        "toe": {s: [round(float(x), 3) for x in fc[s]["toe"]] for s in "lr"},
        "com": [round(float(x), 3) for x in rig.com(F)],
        "step": k, "step_phase": round(u, 4), "ik_error_m": round(ik_err, 5),
    }


# ----------------------------------------------------------------------------------------------- ready-made clips
def walk_cycle(gait="walk", steps=2):
    """Steady-state walk: `steps` steps starting from the stance pose (use steps=2 for one full cycle)."""
    g = GAITS[gait]
    return generate("%s_cycle" % gait, gait, [{"L": g["L"]} for _ in range(steps)], init="stride")


def walk_start(gait="walk"):
    g = GAITS[gait]
    return generate("%s_start" % gait, gait, [{"L": g["L"] * f, "T": g["T"] * (1.25 - 0.25 * f)} for f in (0.45, 0.8, 1.0)])


def walk_stop(gait="walk"):
    g = GAITS[gait]
    return generate("%s_stop" % gait, gait, [{"L": g["L"] * f, "T": g["T"] * (1.0 + (1 - f) * 0.35)} for f in (1.0, 0.6, 0.25)], init="stride")


def turn_in_place(direction="left", degrees_per_step=16.0, steps=5):
    sgn = 1.0 if direction == "left" else -1.0
    return generate("turn_%s" % direction, "walk", [{"L": 0.0, "T": 3.4, "turn": sgn * degrees_per_step} for _ in range(steps)], first_swing="r" if sgn > 0 else "l")


def all_clips():
    return [walk_cycle("walk_slow"), walk_cycle("walk"), walk_cycle("walk_fast"), walk_cycle("run"), walk_start("walk"), walk_stop("walk"),
            turn_in_place("left"), turn_in_place("right")]


def foot_slide(clip):
    """Largest horizontal speed (m/s) of any grounded sole point (heel/toe) over frames where that foot is flagged in contact,
    measured from the posed skeleton, not from the targets."""
    worst = 0.0
    dt = 1.0 / clip.fps
    for a, b in zip(clip.frames[:-1], clip.frames[1:]):
        for s in "lr":
            if a["contact"][s] and b["contact"][s]:
                for key in ("heel", "toe"):
                    d = np.linalg.norm(np.array(a[key][s][:2]) - np.array(b[key][s][:2])) / dt
                    worst = max(worst, d)
    return worst
