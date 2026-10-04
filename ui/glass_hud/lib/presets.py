"""Four preview states (what the game would feed the HUD): fight ok, medium damage, critical, enemy lock-on."""
from . import data

ZONES = data.ZONES


def _zones(**kw):
    z = {k: "Intact" for k in ZONES}
    z.update(kw)
    return z


def base():
    return {
        "player": {"zones": _zones(), "layers": {}}, "enemy": {"zones": _zones(), "layers": {}},
        "armor": 0.92, "arm_armor": [0.95, 0.90], "stability": 0.86, "heat": 0.22, "energy": 0.74, "priority": "Arms",
        "weapons": {"rail": {"ring": 1.0}, "rockets": {"ring": 0.7}, "plasma": {"ring": 0.3}},
        "ultimate": {"value": 0.45, "ready": False}, "radar": {"enemy_angle": 12, "dist": 0.55, "sweep": 70, "dead": False},
        "heading": 18.0, "distance_m": 24, "clock_s": 94, "enemy_status": {"stability": 0.8, "icons": []},
        "blink": True, "threats": [], "glass": {}, "enemy_pos_px": (960, 820, 520),
    }


def fight_ok():
    s = base()
    s["glass"] = {"drops": 14}
    s["lock"] = None
    return s


def medium():
    s = base()
    s["player"] = {"zones": _zones(ArmR="Exposed", ShoulderR="Dented", LegL="Damaged", Torso="Dented"),
                   "layers": {"ArmR": [0.0, 0.8, 1.0], "ShoulderR": [0.55, 1.0, 1.0], "LegL": [0.0, 0.45, 1.0], "Torso": [0.7, 1.0, 1.0]}}
    s["enemy"] = {"zones": _zones(ArmL="Dented", Head="Dented"), "layers": {"ArmL": [0.6, 1, 1], "Head": [0.5, 1, 1]}}
    s.update(armor=0.58, arm_armor=[0.9, 0.35], stability=0.52, heat=0.64, energy=0.48, priority="Guard", ultimate={"value": 0.7, "ready": False})
    s["enemy_status"] = {"stability": 0.55, "icons": ["strikelock"]}
    s["threats"] = ["right"]
    s["glass"] = {"drops": 24, "cracks": [1], "glitch": 0.12, "alarm": 0.25}
    s["warnings"] = [{"pos": [0.50, 0.78], "color": "amber"}]
    s["warnings"] = [{"pos": [0.80, 0.30], "color": "amber"}]
    return s


def critical():
    s = base()
    s["player"] = {"zones": _zones(Head="Damaged", Torso="Critical", Reactor="Critical", ShoulderR="Destroyed", ArmR="Severed", ArmL="Exposed", LegL="Critical", LegR="Damaged"),
                   "layers": {"Head": [0, 0.5, 1], "Torso": [0, 0.2, 0.6], "Reactor": [0, 0.1, 0.4], "ArmL": [0, 0.9, 1], "LegL": [0, 0.15, 0.5], "LegR": [0, 0.5, 1]}}
    s["enemy"] = {"zones": _zones(ArmL="Damaged", Torso="Exposed"), "layers": {"ArmL": [0, 0.5, 1], "Torso": [0, 0.9, 1]}}
    s.update(armor=0.12, arm_armor=[0.4, 0.0], stability=0.14, heat=0.93, energy=0.18, priority="Legs", ultimate={"value": 1.0, "ready": True}, distance_m=9, clock_s=171)
    s["weapons"] = {"rail": {"ring": 0.3, "empty": True}, "rockets": {"ring": 0.9}, "plasma": {"ring": 1.0, "dead": True}}
    s["radar"] = {"enemy_angle": -35, "dist": 0.2, "sweep": 250, "dead": True}
    s["threats"] = ["left", "up"]
    s["enemy_status"] = {"stability": 0.3, "icons": ["burn"]}
    s["glass"] = {"drops": 30, "cracks": [0, 2, 5, 7], "soot": [0, 1], "glitch": 0.7, "alarm": 1.0}
    s["warnings"] = [{"pos": [0.04, 0.46], "color": "red"}, {"pos": [0.04, 0.54], "color": "red"}]
    s["blink"] = True
    return s


def lock_on():
    s = base()
    s["enemy"] = {"zones": _zones(Torso="Exposed", ArmR="Dented"), "layers": {"Torso": [0.3, 1, 1], "ArmR": [0.6, 1, 1]}}
    s["lock"] = {"rect": [0.405, 0.185, 0.19, 0.62], "quality": 0.9, "hex": (0.50, 0.37, 0.7), "hex_hot": True}
    s["strike"] = {"points": [(0.36, 0.74), (0.42, 0.56), (0.50, 0.46), (0.58, 0.44), (0.66, 0.52), (0.70, 0.60)], "committed": False}
    s["enemy_status"] = {"stability": 0.38, "icons": ["blind"]}
    s["threats"] = []
    s["glass"] = {"drops": 10}
    return s


PRESETS = {"fight_ok": fight_ok, "medium_damage": medium, "critical_alarm": critical, "lock_on": lock_on}
