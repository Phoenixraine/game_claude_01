"""Pose library of BASTION-01: guard, 8 swings x 4 phases, quick strikes, blocks, hard stance, dodges, grab, ram, weapon charge,
kneel, knockdown. Each pose = joint angles (deg, local frame, see rig.py) + root offset + centre of mass + foot contacts.
Legs are solved by IK from foot targets so the feet are really where the pose says (planted or lifted)."""
import numpy as np

from . import rig

SIDES = ("l", "r")
LEG_KEYS = ("thigh", "shin", "foot")


def mirror_angles(joints):
    out = {}
    for b, e in joints.items():
        out[rig.mirror_name(b)] = [e[0], -e[1], -e[2]]
    return out


def default_ankle(side):
    k = 1 if side == "l" else -1
    return np.array([k * 11.5, 2.0, rig.GROUND_ANKLE_Z])


class Pose:
    """Mutable builder; `finish()` runs the leg IK and fills derived data."""

    def __init__(self, name, group, desc=""):
        self.name, self.group, self.desc = name, group, desc
        self.joints = {}
        self.root = np.zeros(3)
        self.foot = {"l": np.zeros(4), "r": np.zeros(4)}   # dx, dy, dz, yaw relative to the default planted ankle
        self.foot_abs = {}
        self.leg_direct = {}                                  # bones whose angles are given, not solved
        self.ground = False
        self.meta = {}

    def set(self, **bones):
        for k, v in bones.items():
            self.joints[k] = list(v)
        return self

    def arm(self, side, ur=None, fr=None, hd=None, sh=None):
        if ur is not None:
            self.joints["upperarm_" + side] = list(ur)
        if fr is not None:
            self.joints["forearm_" + side] = list(fr)
        if hd is not None:
            self.joints["hand_" + side] = list(hd)
        if sh is not None:
            self.joints["shoulder_" + side] = list(sh)
        return self

    def stance(self, root=None, fl=None, fr=None):
        if root is not None:
            self.root = np.array(root, dtype=float)
        if fl is not None:
            self.foot["l"] = np.array(fl, dtype=float)
        if fr is not None:
            self.foot["r"] = np.array(fr, dtype=float)
        return self

    def legs_direct(self, side, thigh, shin, foot=(0, 0, 0)):
        self.leg_direct[side] = {"thigh_" + side: list(thigh), "shin_" + side: list(shin), "foot_" + side: list(foot)}
        return self

    def finish(self):
        base = {b: e for b, e in self.joints.items() if not b.startswith(LEG_KEYS)}
        F0 = rig.fk(base, self.root)
        out = dict(self.joints)
        solved = {}
        for s in SIDES:
            if s in self.leg_direct:
                out.update(self.leg_direct[s])
                continue
            tgt = default_ankle(s) + self.foot[s][:3]
            tgt[:2] += 0.0
            sol = rig.solve_limb("leg", s, F0["pelvis"], tgt, foot_yaw=self.foot[s][3])
            solved[s] = sol
            for b, e in sol["angles"].items():
                out[b] = [float(x) for x in e]
        if self.ground:
            F = rig.fk(out, self.root)
            low = min(rig.segment_endpoints(F)[b][i][2] - rig.THICK[b] / 2 for b in rig.segment_endpoints(F) for i in (0, 1))
            self.root = self.root + np.array([0, 0, -low])
        F = rig.fk(out, self.root)
        self.final = out
        self.F = F
        self.leg_solutions = solved
        return self

    def record(self):
        F = self.F
        fc = rig.foot_contacts(F)
        c = rig.com(F)
        return {
            "name": self.name, "group": self.group, "desc": self.desc,
            "joints": {b: [round(float(x), 3) for x in self.final.get(b, [0, 0, 0])] for b in rig.BONES if b != "root"},
            "root_pos": [round(float(x), 3) for x in self.root],
            "root_rot": [round(float(x), 3) for x in self.final.get("root", [0, 0, 0])],
            "com": [round(float(x), 3) for x in c],
            "feet": {s: {"ankle": [round(float(x), 3) for x in fc[s]["ankle"]], "heel": [round(float(x), 3) for x in fc[s]["heel"]],
                         "toe": [round(float(x), 3) for x in fc[s]["toe"]], "ground": fc[s]["ground"]} for s in SIDES},
            "ik": {s: {"reachable": bool(v["reachable"]), "error_m": round(float(v["error_m"]), 4)} for s, v in self.leg_solutions.items()},
            **self.meta,
        }


def _guard_arms(p, k=1.0):
    p.arm("l", ur=(-38, -16 * k, 8), fr=(-112, 0, 0), hd=(-8, 0, 0))
    p.arm("r", ur=(-38, 16 * k, -8), fr=(-112, 0, 0), hd=(-8, 0, 0))


def guard_neutral():
    p = Pose("guard_neutral", "stance", "Default guard: knees bent, forearms up in front of the chest, weight centred.")
    p.stance(root=(0, 0, -3.0), fl=(1.0, -1.5, 0, 0), fr=(-1.0, -1.5, 0, 0))
    p.set(torso=(4, 0, 0), head=(-4, 0, 0), pelvis=(0, 0, 0))
    _guard_arms(p)
    return p


# ------------------------------------------------------------------------------------------------ swings (right arm)
# phase -> dict of joint angles for the RIGHT arm and the body. Left arm / mirrored sectors are obtained by mirror().
SWING_R = {
    "up": {   # overhead hammer blow
        "windup": dict(ur=(-165, 5, 0), fr=(-12, 0, 0), hd=(-10, 0, 0), torso=(-13, 0, -14), pelvis=(-4, 0, -6), head=(2, 0, 0), root=(0, 1.5, -1.5)),
        "commit": dict(ur=(-118, 8, 0), fr=(-35, 0, 0), hd=(-15, 0, 0), torso=(6, 0, -4), pelvis=(0, 0, -2), head=(0, 0, 0), root=(0, -1.5, -3.5)),
        "strike_end": dict(ur=(-52, 6, 0), fr=(-22, 0, 0), hd=(-5, 0, 0), torso=(19, 0, 8), pelvis=(6, 0, 4), head=(-8, 0, 0), root=(0, -4.5, -6.0)),
        "recovery": dict(ur=(-36, 12, -6), fr=(-70, 0, 0), hd=(-8, 0, 0), torso=(10, 0, 3), pelvis=(3, 0, 1), head=(-5, 0, 0), root=(0, -2.5, -4.0)),
    },
    "right": {  # outside hook from the right
        "windup": dict(ur=(-30, 82, -25), fr=(-88, 0, 0), hd=(0, 0, 0), torso=(5, 0, -36), pelvis=(0, 0, -12), head=(-3, 0, 14), root=(-1.5, 0.5, -3.5)),
        "commit": dict(ur=(-62, 50, -10), fr=(-55, 0, 0), hd=(0, 0, 0), torso=(6, 0, -6), pelvis=(0, 0, -2), head=(-3, 0, 4), root=(0.5, -1.5, -4.0)),
        "strike_end": dict(ur=(-84, -6, 15), fr=(-22, 0, 0), hd=(0, 0, 0), torso=(6, 0, 36), pelvis=(0, 0, 14), head=(-3, 0, -12), root=(2.5, -3.0, -4.5)),
        "recovery": dict(ur=(-48, 8, 6), fr=(-75, 0, 0), hd=(-8, 0, 0), torso=(5, 0, 14), pelvis=(0, 0, 5), head=(-3, 0, -5), root=(1.0, -1.5, -3.5)),
    },
    "left": {   # cross / backhand arriving from the left
        "windup": dict(ur=(-55, -22, 20), fr=(-95, 0, 0), hd=(0, 10, 0), torso=(5, 0, 32), pelvis=(0, 0, 12), head=(-3, 0, -12), root=(1.5, 0.5, -3.5)),
        "commit": dict(ur=(-70, 4, 5), fr=(-55, 0, 0), hd=(0, 0, 0), torso=(6, 0, 6), pelvis=(0, 0, 2), head=(-3, 0, -4), root=(-0.5, -1.5, -4.0)),
        "strike_end": dict(ur=(-75, 62, -25), fr=(-18, 0, 0), hd=(0, 0, 0), torso=(7, 0, -38), pelvis=(0, 0, -14), head=(-3, 0, 14), root=(-2.5, -3.0, -4.5)),
        "recovery": dict(ur=(-45, 22, -8), fr=(-75, 0, 0), hd=(-8, 0, 0), torso=(5, 0, -14), pelvis=(0, 0, -5), head=(-3, 0, 5), root=(-1.0, -1.5, -3.5)),
    },
    "down": {   # uppercut from below
        "windup": dict(ur=(28, 10, 0), fr=(-25, 0, 0), hd=(10, 0, 0), torso=(12, 0, -12), pelvis=(6, 0, -5), head=(-8, 0, 0), root=(0, 1.0, -9.0)),
        "commit": dict(ur=(-50, 8, 0), fr=(-80, 0, 0), hd=(-5, 0, 0), torso=(4, 0, -2), pelvis=(0, 0, 0), head=(-4, 0, 0), root=(0, -2.0, -5.0)),
        "strike_end": dict(ur=(-112, 8, 0), fr=(-48, 0, 0), hd=(-10, 0, 0), torso=(-7, 0, 8), pelvis=(-4, 0, 4), head=(0, 0, 0), root=(0, -3.5, -1.0)),
        "recovery": dict(ur=(-55, 10, -4), fr=(-75, 0, 0), hd=(-8, 0, 0), torso=(2, 0, 3), pelvis=(0, 0, 1), head=(-3, 0, 0), root=(0, -1.5, -3.0)),
    },
}
SWING_FEET = {   # per phase: foot offsets (dx, dy, dz, yaw): the front foot steps in on the commit
    "windup": ((1.0, 0.0, 0, 0), (-1.0, 0.0, 0, 0)),
    "commit": ((1.0, -1.0, 0, 0), (-1.0, -1.0, 0, 0)),
    "strike_end": ((1.5, -3.0, 0, 4), (-1.5, -1.0, 0, 0)),
    "recovery": ((1.0, -1.5, 0, 0), (-1.0, -1.5, 0, 0)),
}
PHASES = ("windup", "commit", "strike_end", "recovery")
SECTORS = ("up", "right", "left", "down")


def _apply_swing(p, spec, arm_side, mirrored):
    tmp = Pose("tmp", "tmp")
    tmp.arm("r", ur=spec["ur"], fr=spec["fr"], hd=spec["hd"])
    tmp.set(torso=spec["torso"], pelvis=spec["pelvis"], head=spec["head"])
    j = dict(tmp.joints)
    root = np.array(spec["root"], dtype=float)
    if mirrored:
        j = mirror_angles(j)
        root[0] = -root[0]
    p.joints.update(j)
    p.root = root


def swing(sector, arm, phase):
    """Heavy swing pose. `sector` = where the attack arrives from (up/right/left/down), `arm` = 'r' or 'l'."""
    mirrored = arm == "l"
    base_sector = {"right": "left", "left": "right"}.get(sector, sector) if mirrored else sector
    p = Pose("swing_%s_%s_%s" % (sector, arm, phase), "swing",
             "Heavy %s swing (%s arm), phase %s." % (sector, {"r": "right", "l": "left"}[arm], phase))
    p.meta = {"sector": sector, "arm": arm, "phase": phase}
    _apply_swing(p, SWING_R[base_sector][phase], arm, mirrored)
    # the idle arm stays in guard, slightly pulled in
    idle = "l" if arm == "r" else "r"
    p.arm(idle, ur=(-26, -20 if idle == "l" else 20, 6 if idle == "l" else -6), fr=(-95, 0, 0), hd=(-8, 0, 0))
    fl, fr = SWING_FEET[phase]
    if mirrored:     # the stepping foot is the one on the attacking side's opposite? keep the same foot forward for the arm
        fl, fr = (-fr[0], fr[1], fr[2], -fr[3]) if False else (fr[0] * -1, fr[1], fr[2], -fr[3]), (fl[0] * -1, fl[1], fl[2], -fl[3])
    p.stance(fl=fl, fr=fr)
    return p


# ---------------------------------------------------------------------------------------------------- quick strikes
QUICK_R = {
    "piston": {   # straight punch
        "windup": dict(ur=(-16, 8, 0), fr=(-120, 0, 0), hd=(0, 0, 0), torso=(5, 0, -8), pelvis=(0, 0, -3)),
        "strike": dict(ur=(-84, 4, 0), fr=(-4, 0, 0), hd=(0, 0, 0), torso=(9, 0, 12), pelvis=(2, 0, 5)),
    },
    "hook": {     # short side hook
        "windup": dict(ur=(-30, 60, -10), fr=(-100, 0, 0), hd=(0, 0, 0), torso=(5, 0, -16), pelvis=(0, 0, -6)),
        "strike": dict(ur=(-62, 18, 6), fr=(-65, 0, 0), hd=(0, 0, 0), torso=(7, 0, 16), pelvis=(0, 0, 6)),
    },
    "shove": {    # forearm shove
        "windup": dict(ur=(-25, 12, 0), fr=(-125, 0, 0), hd=(-20, 0, 0), torso=(3, 0, -6), pelvis=(0, 0, -2)),
        "strike": dict(ur=(-60, 8, 0), fr=(-72, 0, 0), hd=(-30, 0, 0), torso=(12, 0, 8), pelvis=(3, 0, 3)),
    },
    "palm": {     # open-palm strike, hand turned out
        "windup": dict(ur=(-30, 12, -10), fr=(-110, 0, 0), hd=(-30, 20, 0), torso=(4, 0, -10), pelvis=(0, 0, -4)),
        "strike": dict(ur=(-78, 6, 12), fr=(-12, 0, 0), hd=(-40, 25, 0), torso=(8, 0, 12), pelvis=(2, 0, 4)),
    },
}
QUICK_ROOT = {"windup": (0, 0.5, -3.0), "strike": (0, -2.0, -3.5)}


def quick(kind, arm, phase):
    mirrored = arm == "l"
    spec = QUICK_R[kind][phase]
    p = Pose("quick_%s_%s_%s" % (kind, arm, phase), "quick", "Quick %s strike (%s arm), %s." % (kind, {"r": "right", "l": "left"}[arm], phase))
    p.meta = {"kind": kind, "arm": arm, "phase": phase}
    tmp = Pose("t", "t")
    tmp.arm("r", ur=spec["ur"], fr=spec["fr"], hd=spec["hd"])
    tmp.set(torso=spec["torso"], pelvis=spec["pelvis"], head=(-4, 0, -spec["torso"][2] * 0.5))
    j = dict(tmp.joints)
    root = np.array(QUICK_ROOT[phase], dtype=float)
    if mirrored:
        j = mirror_angles(j)
        root[0] = -root[0]
    p.joints.update(j)
    p.root = root
    idle = "l" if arm == "r" else "r"
    p.arm(idle, ur=(-24, -18 if idle == "l" else 18, 6 if idle == "l" else -6), fr=(-90, 0, 0), hd=(-8, 0, 0))
    p.stance(fl=(1.0, -1.5 - (1.0 if phase == "strike" else 0), 0, 0), fr=(-1.0, -1.5 - (1.0 if phase == "strike" else 0), 0, 0))
    return p


# ------------------------------------------------------------------------------------------------------------ blocks
def block(sector):
    p = Pose("block_" + sector, "block", "Block against a swing arriving from the %s sector." % sector)
    p.meta = {"sector": sector}
    p.stance(root=(0, 0.5, -4.5), fl=(1.5, -1.0, 0, 0), fr=(-1.5, -1.0, 0, 0))
    p.set(torso=(6, 0, 0), head=(-4, 0, 0), pelvis=(0, 0, 0))
    if sector == "up":      # both forearms raised and crossed above the head
        p.arm("l", ur=(-120, -4, -22), fr=(-70, 0, 0), hd=(0, 0, 0))
        p.arm("r", ur=(-120, 4, 22), fr=(-70, 0, 0), hd=(0, 0, 0))
        p.set(torso=(2, 0, 0))
    elif sector == "down":  # forearms dropped in front of the belly/legs
        p.arm("l", ur=(-18, -10, 0), fr=(-55, 0, 0), hd=(25, 0, 0))
        p.arm("r", ur=(-18, 10, 0), fr=(-55, 0, 0), hd=(25, 0, 0))
        p.set(torso=(12, 0, 0), head=(-8, 0, 0))
        p.root = np.array([0, 0.5, -7.5])
    elif sector == "right":  # right forearm out to the side, torso turned into the blow
        p.arm("r", ur=(-35, 62, -30), fr=(-85, 0, 0), hd=(0, 0, 0))
        p.arm("l", ur=(-30, -18, 6), fr=(-95, 0, 0), hd=(0, 0, 0))
        p.set(torso=(5, 0, -18), pelvis=(0, 0, -6), head=(-4, 0, 10))
    else:
        p.arm("l", ur=(-35, -62, 30), fr=(-85, 0, 0), hd=(0, 0, 0))
        p.arm("r", ur=(-30, 18, -6), fr=(-95, 0, 0), hd=(0, 0, 0))
        p.set(torso=(5, 0, 18), pelvis=(0, 0, 6), head=(-4, 0, -10))
    return p


def hard_stance():
    p = Pose("hard_stance", "stance", "Reinforced stance: wide, low, elbows tucked; the mech braces rather than moves.")
    p.stance(root=(0, 1.0, -9.0), fl=(5.5, -2.0, 0, 6), fr=(-5.5, -2.0, 0, -6))
    p.set(torso=(10, 0, 0), head=(-8, 0, 0), pelvis=(2, 0, 0))
    p.arm("l", ur=(-8, -8, 8), fr=(-100, 0, 0), hd=(-5, 0, 0))
    p.arm("r", ur=(-8, 8, -8), fr=(-100, 0, 0), hd=(-5, 0, 0))
    return p


# ----------------------------------------------------------------------------------------------------------- dodges
def dodge(direction, phase):
    """One heavy step. phases: shift (weight moves onto the support leg, pelvis turns), lift (foot leaves the ground), plant."""
    p = Pose("dodge_%s_%s" % (direction, phase), "dodge", "Heavy dodge step %s, phase %s." % (direction, phase))
    p.meta = {"direction": direction, "phase": phase}
    p.set(torso=(5, 0, 0), head=(-4, 0, 0))
    _guard_arms(p)
    sgn = {"left": 1, "right": -1, "back": 0}[direction]
    step_side = "l" if direction == "left" else "r" if direction == "right" else "r"
    sup = "r" if step_side == "l" else "l"
    if direction == "back":
        shift = {"shift": (0, 1.5, -4.0), "lift": (0, 4.0, -5.0), "plant": (0, 12.0, -4.0)}[phase]
        p.root = np.array(shift)
        zl = {"shift": 0, "lift": 3.5, "plant": 0}[phase]
        p.stance(fl=(0.5, 0.0, 0, 0), fr=(-0.5, {"shift": 0, "lift": 6, "plant": 24}[phase] , zl, 0))
        p.set(torso=(-2 if phase != "shift" else 5, 0, 0), pelvis=(-4, 0, 0))
    else:
        s = 1 if direction == "left" else -1
        root_x = {"shift": -s * 4.5, "lift": -s * 3.0, "plant": s * 7.0}[phase]
        p.root = np.array([root_x, 0.5, -4.5])
        foot_dx = {"shift": 0.0, "lift": s * 7.0, "plant": s * 17.0}[phase]
        foot_dz = {"shift": 0.0, "lift": 3.5, "plant": 0.0}[phase]
        off = (foot_dx + (1.0 if step_side == "l" else -1.0), -1.0, foot_dz, 0)
        sup_off = (-s * 0.0 + (1.0 if sup == "l" else -1.0) + (0.0), -1.0, 0, 0)
        if step_side == "l":
            p.stance(fl=off, fr=sup_off)
        else:
            p.stance(fl=sup_off, fr=off)
        p.set(pelvis=(0, 0, s * (6 if phase != "plant" else -6)), torso=(5, 0, -s * (6 if phase != "plant" else -6)))
    return p


# --------------------------------------------------------------------------------------------------- grab / ram / weapon
def grab(phase):
    p = Pose("grab_" + phase, "grab", "Both arms forward to seize the opponent (%s)." % phase)
    p.meta = {"phase": phase}
    p.stance(root=(0, -1.0, -5.0), fl=(1.5, -3.0, 0, 0), fr=(-1.5, -3.0, 0, 0))
    p.set(torso=(10, 0, 0), head=(-8, 0, 0), pelvis=(3, 0, 0))
    if phase == "reach":
        p.arm("l", ur=(-88, -22, 10), fr=(-6, 0, 0), hd=(-10, 14, 0))
        p.arm("r", ur=(-88, 22, -10), fr=(-6, 0, 0), hd=(-10, -14, 0))
    else:
        p.arm("l", ur=(-80, -4, 10), fr=(-48, 0, 0), hd=(-20, 22, 0))
        p.arm("r", ur=(-80, 4, -10), fr=(-48, 0, 0), hd=(-20, -22, 0))
    return p


def ram(phase):
    p = Pose("ram_" + phase, "ram", "Shoulder ram (%s)." % phase)
    p.meta = {"phase": phase}
    if phase == "windup":
        p.stance(root=(0, 4.0, -8.0), fl=(2.0, 5.0, 0, 0), fr=(-2.0, 2.0, 0, 0))
        p.set(torso=(-6, 0, 12), pelvis=(-3, 0, 8), head=(0, 0, -6))
        p.arm("l", ur=(18, -10, 0), fr=(-30, 0, 0), hd=(0, 0, 0))
        p.arm("r", ur=(-60, 20, -10), fr=(-90, 0, 0), hd=(0, 0, 0))
    else:
        p.stance(root=(0, -9.0, -9.0), fl=(2.0, -12.0, 0, 0), fr=(-2.0, -2.0, 0, 0))
        p.set(torso=(20, 0, -16), pelvis=(6, 0, -8), head=(-12, 0, 8))
        p.arm("l", ur=(-45, -8, 0), fr=(-100, 0, 0), hd=(0, 0, 0))
        p.arm("r", ur=(-70, 24, -10), fr=(-90, 0, 0), hd=(0, 0, 0))
    return p


def weapon_charge(phase):
    p = Pose("weapon_charge_" + phase, "weapon", "Shoulder weapon deployed, legs locked wide (%s)." % phase)
    p.meta = {"phase": phase}
    p.stance(root=(0, 1.0, -7.5), fl=(4.5, 0.0, 0, 8), fr=(-4.5, 0.0, 0, -8))
    p.set(torso=(-3, 0, 14), pelvis=(0, 0, 4), head=(-2, 0, -12))
    # left shoulder opened outwards/up to expose the emitter, right arm braces the left
    p.arm("l", ur=(-62, -52, 0), fr=(-28, 0, 0), hd=(-18, 0, 0), sh=(0, 0, 8))
    p.arm("r", ur=(-40, 30, -12), fr=(-96, 0, 0), hd=(-12, 0, 0))
    if phase == "peak":
        p.arm("l", ur=(-72, -64, 0), fr=(-22, 0, 0), hd=(-22, 0, 0), sh=(0, 0, 10))
        p.set(torso=(-6, 0, 18), head=(0, 0, -16))
        p.root = np.array([0, 1.5, -8.5])
    return p


# --------------------------------------------------------------------------------------------------------- kneel / fall
def kneel():
    p = Pose("kneel", "down", "Down on the left knee, right foot forward, torso upright, arms bracing.")
    p.stance(root=(0, -2.0, -19.5), fr=(-2.0, -22.0, 0, 0))
    p.legs_direct("l", thigh=(4, -4, 0), shin=(112, 0, 0), foot=(-30, 0, 0))
    p.set(torso=(8, 0, 0), head=(-8, 0, 0), pelvis=(0, 0, 0))
    p.arm("l", ur=(-30, -22, 0), fr=(-60, 0, 0), hd=(0, 0, 0))
    p.arm("r", ur=(-50, 16, -4), fr=(-40, 0, 0), hd=(0, 0, 0))
    return p


def knockdown(phase):
    p = Pose("knockdown_" + phase, "down", "Knocked over backwards (%s)." % phase)
    p.meta = {"phase": phase}
    if phase == "fall":
        p.joints["root"] = [-38, 0, 0]
        p.stance(root=(0, 0, 0))
        p.legs_direct("l", thigh=(-8, -6, 0), shin=(22, 0, 0), foot=(10, 0, 0))
        p.legs_direct("r", thigh=(-6, 6, 0), shin=(20, 0, 0), foot=(10, 0, 0))
        p.set(torso=(-12, 0, 0), head=(18, 0, 0), pelvis=(-5, 0, 0))
        p.arm("l", ur=(40, -35, 0), fr=(-15, 0, 0), hd=(0, 0, 0))
        p.arm("r", ur=(32, 35, 0), fr=(-25, 0, 0), hd=(0, 0, 0))
    else:
        p.joints["root"] = [-90, 0, 0]
        p.ground = True
        p.legs_direct("l", thigh=(-5, -10, 0), shin=(15, 0, 0), foot=(0, 0, 0))
        p.legs_direct("r", thigh=(-8, 12, 0), shin=(30, 0, 0), foot=(0, 0, 0))
        p.set(torso=(0, 0, 0), head=(10, 0, 8), pelvis=(0, 0, 0))
        p.arm("l", ur=(30, -40, 0), fr=(-10, 0, 0), hd=(0, 0, 0))
        p.arm("r", ur=(20, 55, 0), fr=(-35, 0, 0), hd=(0, 0, 0))
    return p


def all_poses():
    """Ordered list of finished Pose objects."""
    out = [guard_neutral()]
    for sector in SECTORS:
        for arm in ("r", "l"):
            for ph in PHASES:
                out.append(swing(sector, arm, ph))
    for kind in QUICK_R:
        for arm in ("r", "l"):
            for ph in ("windup", "strike"):
                out.append(quick(kind, arm, ph))
    for sector in SECTORS:
        out.append(block(sector))
    out.append(hard_stance())
    for d in ("left", "right", "back"):
        for ph in ("shift", "lift", "plant"):
            out.append(dodge(d, ph))
    out += [grab("reach"), grab("clamp"), ram("windup"), ram("hit"), weapon_charge("hold"), weapon_charge("peak"), kneel(),
            knockdown("fall"), knockdown("down")]
    for p in out:
        p.finish()
    return out


def build_all():
    return {p.name: p.record() for p in all_poses()}


# -------------------------------------------------------------------------------------------- transition table
def transitions(names):
    """Which poses may follow which (pitch §5.4 pose economy): a recovery leads to guard, a block, hard stance, a dodge start or
    the windup of the OTHER arm; quick strikes return to guard or chain into the other arm's quick windup."""
    names = set(names)
    table = {}
    for n in sorted(names):
        if not n.startswith("swing_") or not n.endswith("_recovery"):
            continue
        arm = n.split("_")[2]
        other = "l" if arm == "r" else "r"
        nxt = ["guard_neutral", "hard_stance"] + ["block_" + s for s in SECTORS] + ["dodge_left_shift", "dodge_right_shift", "dodge_back_shift"]
        nxt += ["swing_%s_%s_windup" % (s, other) for s in SECTORS]
        nxt += ["quick_%s_%s_windup" % (k, other) for k in QUICK_R]
        table[n] = [x for x in nxt if x in names]
    for n in sorted(names):
        if n.startswith("quick_") and n.endswith("_strike"):
            arm = n.split("_")[2]
            other = "l" if arm == "r" else "r"
            nxt = ["guard_neutral"] + ["quick_%s_%s_windup" % (k, other) for k in QUICK_R] + ["block_" + s for s in SECTORS]
            table[n] = [x for x in nxt if x in names]
    for ph in ("knockdown_down",):
        if ph in names:
            table[ph] = ["kneel"]
    if "kneel" in names:
        table["kneel"] = ["guard_neutral"]
    return table
