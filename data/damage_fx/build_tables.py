#!/usr/bin/env python3
"""Source of truth of the damage-FX tables (TASK-022). Writes the JSON files next to this script; a test checks that the committed JSON equals
what this script produces.   python3 data/damage_fx/build_tables.py"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))

ZONES = ["Head", "Torso", "Reactor", "ShoulderL", "ShoulderR", "ArmL", "ArmR", "LegL", "LegR"]
LAYERS = ["Armor", "Mechanism", "System"]
ZONE_STATES = ["Intact", "Dented", "Exposed", "Damaged", "Critical", "Destroyed", "Severed"]
SEVERITIES = ["S0", "S1", "S2", "S3", "S4"]

# ---------------------------------------------------------------------------------------------------------------- identifiers
# Every id a table may refer to. Counts of the cockpit classes are the MINIMA that TASK-020 (art/cockpit_v2) must provide.
IDENTIFIERS = {
    "version": 1,
    "note": "Registry of ids used by the damage-FX tables. cockpit.* = scene object / empty classes of TASK-020 (name = <class>_<NN>, two digits); shards.* = TASK-016; sounds / voices / icons = proposals for audio/ and ui/glass_hud (TASK-021): they must adopt these ids or tell us the new ones.",
    "zones": ZONES,
    "layers": LAYERS,
    "zone_states": ZONE_STATES,
    "severities": SEVERITIES,
    "cockpit": {
        "Pipe_Burst": 12, "SteamPort": 12, "LeakPoint": 12, "Wire_Snapped": 24, "SparkPort": 24, "Mon": 12, "Lamp_Warn": 20, "Lamp_Ok": 20,
        "AlarmBeacon": 4, "StrobePanel": 4, "Fire_Socket": 8, "Scorch_Decal": 6, "Glass_Crack_Mask": 4, "Btn": 80, "Dial": 12,
    },
    "cockpit_singletons": ["Glass_Front", "Cockpit_Root", "Camera_Rig"],
    "fire_graph": {   # which Fire_Socket can ignite which (undirected edges; indices of Fire_Socket_NN)
        "edges": [[0, 1], [1, 2], [2, 3], [3, 4], [4, 5], [5, 6], [6, 7], [7, 0], [1, 6], [2, 5]]
    },
    "shards": {
        "concrete": ["Shard_Concrete_S", "Shard_Concrete_M", "Shard_Concrete_L", "Shard_Concrete_XL"],
        "big": ["Slab_Concrete", "Column_Broken", "Panel_Facade_Torn", "Girder_Twisted", "Steel_Plate_Bent", "AC_Unit_Broken", "Sign_Torn"],
        "small": ["Glass_Shard", "Gravel_Cluster", "Pebble", "Rebar_Single", "Rebar_Bundle", "Pipe_Broken", "Cable_Dangling", "Window_Frame_Broken"],
    },
    "mech_chunks": ["armor_plate", "armor_plate_burning", "piston", "hose", "cable_bundle", "limb_part", "reactor_fragment", "sensor_housing", "debris_small"],
    "sounds": [
        "fx_cockpit_hit_light", "fx_cockpit_hit_heavy", "fx_cockpit_hit_crit", "fx_pipe_burst", "fx_steam_jet", "fx_wire_spark", "fx_fire_loop", "fx_extinguisher",
        "fx_monitor_glitch", "fx_monitor_dead", "fx_glass_crack", "fx_glass_shatter", "fx_power_flicker", "fx_siren", "fx_alarm_beep", "fx_servo_whine",
        "fx_chunk_tumble", "fx_chunk_ground", "fx_building_crack", "fx_building_collapse", "fx_debris_rain", "fx_dust_whoosh", "fx_glass_rain", "fx_blast_far",
    ],
    "voices": [
        "vo_hull_damage", "vo_hull_critical", "vo_reactor_breach", "vo_arm_lost", "vo_leg_lost", "vo_overheat", "vo_coolant_leak", "vo_power_loss",
        "vo_sensors_failed", "vo_hook_alert", "vo_ultimate_ready", "vo_weapon_ready", "vo_target_lost",
    ],
    "icons": [
        "icon_hull", "icon_reactor", "icon_arm", "icon_leg", "icon_head", "icon_heat", "icon_coolant", "icon_power", "icon_sensors", "icon_fire", "icon_hook",
        "icon_ultimate", "icon_weapon_rail", "icon_weapon_rockets", "icon_weapon_plasma", "icon_status_blind", "icon_status_strikelock", "icon_status_burn",
    ],
    "particle_systems": [
        "ps_steam_puff", "ps_steam_jet", "ps_sparks_wire", "ps_sparks_ground", "ps_fire_small", "ps_fire_big", "ps_smoke_dark", "ps_smoke_light", "ps_dust_ceiling",
        "ps_coolant_spray", "ps_dust_cloud", "ps_dust_puff", "ps_debris_trail_fire", "ps_glass_sparkle",
    ],
    "building_materials": ["concrete", "glass_curtain", "brick", "steel_frame"],
}

COCKPIT_COUNTS = IDENTIFIERS["cockpit"]

# ---------------------------------------------------------------------------------------------------------------- shake
# Components: shape damped_sine | impulse | noise. Components above 3.5 Hz last at most 0.3 s (motion sickness), slower ones carry the long part.
def comp(shape, freq, pos_cm, rot_deg, dur, decay=6.0, attack=0.0, chroma=0.0, axes=(1, 1, 1)):
    return {"shape": shape, "freq_hz": freq, "amp_cm": pos_cm, "amp_deg": rot_deg, "duration_s": dur, "decay": decay, "attack_s": attack, "chroma": chroma, "axes": list(axes)}

SEV_MULT = [0.12, 0.40, 1.0, 1.7, 2.6]    # S0..S4
SHAKE = {
    "limits": {"max_pos_cm": 12.0, "max_rot_deg": 4.0, "high_freq_hz": 3.5, "high_freq_max_s": 0.3, "reduce_motion_mult": 0.25, "sample_hz": 120},
    "severity_mult": SEV_MULT,
    "events": {
        "HitEvent": {"direction": "impact", "scale": "severity", "components": [comp("damped_sine", 10.0, 2.4, 0.7, 0.28, 16.0, chroma=0.5), comp("damped_sine", 2.2, 1.2, 0.5, 0.9, 4.5), comp("noise", 3.0, 0.5, 0.2, 0.7, 5.0)]},
        "ExternalHit": {"direction": "impact", "scale": "severity", "components": [comp("damped_sine", 8.0, 3.0, 0.9, 0.3, 14.0, chroma=0.6), comp("damped_sine", 1.8, 2.0, 0.8, 1.1, 3.8)]},
        "Blocked": {"direction": "impact", "scale": "fixed", "mult": 0.45, "components": [comp("damped_sine", 12.0, 1.4, 0.4, 0.22, 18.0), comp("damped_sine", 2.5, 0.6, 0.3, 0.5, 6.0)]},
        "ParrySuccess": {"direction": "impact", "scale": "fixed", "mult": 0.3, "components": [comp("impulse", 6.0, 0.9, 0.25, 0.14, 0.0)]},
        "InterceptSuccess": {"direction": "impact", "scale": "fixed", "mult": 0.5, "components": [comp("damped_sine", 11.0, 1.6, 0.5, 0.2, 18.0)]},
        "BladesClash": {"direction": "forward", "scale": "fixed", "mult": 0.7, "components": [comp("damped_sine", 14.0, 1.8, 0.4, 0.2, 20.0, chroma=0.3), comp("damped_sine", 2.8, 0.8, 0.3, 0.6, 6.0)]},
        "Evaded": {"direction": "lateral", "scale": "fixed", "mult": 0.2, "components": [comp("damped_sine", 2.0, 0.5, 0.3, 0.5, 5.0)]},
        "Dodge": {"direction": "lateral", "scale": "fixed", "mult": 0.6, "components": [comp("damped_sine", 1.6, 2.2, 1.4, 0.8, 3.5), comp("impulse", 6.0, 0.8, 0.2, 0.12, 0.0)]},
        "StaggerBegin": {"direction": "back", "scale": "fixed", "mult": 1.0, "components": [comp("damped_sine", 1.4, 3.2, 1.8, 1.0, 3.0), comp("damped_sine", 9.0, 1.6, 0.6, 0.25, 15.0)]},
        "StaggerEnd": {"direction": "forward", "scale": "fixed", "mult": 0.25, "components": [comp("damped_sine", 2.0, 0.8, 0.4, 0.5, 5.0)]},
        "Knockdown": {"direction": "down", "scale": "fixed", "mult": 1.8, "components": [comp("damped_sine", 1.2, 5.0, 2.6, 1.6, 2.4), comp("damped_sine", 8.0, 2.8, 1.0, 0.3, 12.0, chroma=0.8), comp("noise", 3.2, 1.2, 0.6, 1.2, 2.0)]},
        "GotUp": {"direction": "up", "scale": "fixed", "mult": 0.5, "components": [comp("damped_sine", 1.5, 1.8, 0.9, 0.9, 3.5)]},
        "Clinch": {"direction": "forward", "scale": "fixed", "mult": 1.1, "components": [comp("damped_sine", 6.0, 2.4, 0.8, 0.3, 10.0), comp("noise", 3.4, 1.4, 0.5, 1.5, 1.2)]},
        "WallSlam": {"direction": "impact", "scale": "fixed", "mult": 1.7, "components": [comp("damped_sine", 9.0, 4.0, 1.4, 0.3, 11.0, chroma=0.9), comp("damped_sine", 1.6, 3.0, 1.2, 1.2, 3.0)]},
        "GrabHit": {"direction": "forward", "scale": "fixed", "mult": 1.0, "components": [comp("damped_sine", 8.0, 2.2, 0.7, 0.3, 12.0), comp("damped_sine", 2.0, 1.2, 0.6, 0.8, 4.0)]},
        "HeatWarning": {"direction": "none", "scale": "fixed", "mult": 0.25, "components": [comp("noise", 3.4, 0.4, 0.15, 2.0, 0.6)]},
        "CoolantLeak": {"direction": "none", "scale": "fixed", "mult": 0.4, "components": [comp("noise", 3.2, 0.6, 0.2, 2.5, 0.5)]},
        "Shutdown": {"direction": "down", "scale": "fixed", "mult": 1.2, "components": [comp("damped_sine", 1.3, 3.0, 1.6, 1.5, 2.6)]},
        "ArmorPlateLost": {"direction": "impact", "scale": "fixed", "mult": 0.8, "components": [comp("damped_sine", 12.0, 1.8, 0.5, 0.2, 20.0, chroma=0.4)]},
        "LimbSevered": {"direction": "impact", "scale": "fixed", "mult": 2.2, "components": [comp("damped_sine", 9.0, 3.6, 1.2, 0.3, 11.0, chroma=1.0), comp("damped_sine", 1.4, 3.4, 1.8, 1.6, 2.4), comp("noise", 3.0, 1.0, 0.5, 1.4, 1.6)]},
        "ReactorBreach": {"direction": "forward", "scale": "fixed", "mult": 2.0, "components": [comp("damped_sine", 8.0, 3.2, 1.2, 0.3, 10.0, chroma=1.0), comp("noise", 3.4, 2.0, 0.9, 2.5, 1.0)]},
        "SystemFailure": {"direction": "none", "scale": "fixed", "mult": 1.0, "components": [comp("damped_sine", 9.0, 1.8, 0.6, 0.25, 14.0, chroma=0.6), comp("noise", 3.0, 0.9, 0.4, 1.2, 2.0)]},
        "WeaponCharging": {"direction": "none", "scale": "fixed", "mult": 0.3, "components": [comp("noise", 3.3, 0.5, 0.2, 1.5, 0.4, attack=0.6)]},
        "WeaponFired": {"direction": "back", "scale": "fixed", "mult": 1.3, "components": [comp("damped_sine", 7.0, 3.0, 0.9, 0.3, 10.0, chroma=0.7), comp("damped_sine", 1.8, 1.6, 0.7, 0.9, 4.0)]},
        "UltimateUsed": {"direction": "forward", "scale": "fixed", "mult": 1.6, "components": [comp("damped_sine", 6.0, 2.8, 1.0, 0.3, 9.0, chroma=0.8), comp("noise", 3.0, 1.6, 0.8, 2.0, 1.4)]},
        "UltimateFinisher": {"direction": "down", "scale": "fixed", "mult": 2.2, "components": [comp("damped_sine", 1.2, 5.0, 2.6, 2.0, 2.0)]},
        "UltimateSever": {"direction": "impact", "scale": "fixed", "mult": 2.0, "components": [comp("damped_sine", 8.0, 3.4, 1.2, 0.3, 10.0, chroma=0.9), comp("damped_sine", 1.4, 2.8, 1.4, 1.4, 2.6)]},
        "BurnTick": {"direction": "none", "scale": "fixed", "mult": 0.15, "components": [comp("impulse", 5.0, 0.3, 0.1, 0.1, 0.0)]},
        "StatusApplied": {"direction": "none", "scale": "fixed", "mult": 0.5, "components": [comp("damped_sine", 9.0, 1.0, 0.4, 0.2, 16.0, chroma=0.4)]},
        "MatchEnd": {"direction": "down", "scale": "fixed", "mult": 1.5, "components": [comp("damped_sine", 1.2, 4.0, 2.0, 2.5, 1.8)]},
        # ---- boarding (TASK-017; only present in Events.h after that PR is merged)
        "HookFired": {"direction": "forward", "scale": "fixed", "mult": 0.5, "components": [comp("damped_sine", 7.0, 1.2, 0.4, 0.25, 12.0)]},
        "HookLanded": {"direction": "forward", "scale": "fixed", "mult": 0.8, "components": [comp("damped_sine", 6.0, 1.8, 0.6, 0.3, 9.0)]},
        "BoardingSwatImpact": {"direction": "impact", "scale": "fixed", "mult": 2.6, "components": [comp("damped_sine", 8.0, 4.4, 1.6, 0.3, 9.0, chroma=1.0), comp("damped_sine", 1.4, 3.8, 2.0, 1.6, 2.4)]},
        "BoardingBlast": {"direction": "back", "scale": "fixed", "mult": 1.4, "components": [comp("damped_sine", 5.0, 2.4, 0.9, 0.3, 7.0), comp("damped_sine", 1.6, 2.2, 1.0, 1.4, 3.0)]},
        "BoardingShock": {"direction": "impact", "scale": "fixed", "mult": 0.9, "components": [comp("damped_sine", 9.0, 2.0, 0.7, 0.25, 14.0)]},
    },
    # direction of the push in the camera frame (right, up, forward): where the cockpit is thrown by a hit on this zone
    "zone_direction": {
        "Head": [0.0, 0.3, -0.9], "Torso": [0.0, 0.0, -1.0], "Reactor": [0.0, 0.1, 1.0], "ShoulderL": [0.9, -0.2, -0.3], "ShoulderR": [-0.9, -0.2, -0.3],
        "ArmL": [0.7, -0.4, -0.2], "ArmR": [-0.7, -0.4, -0.2], "LegL": [0.5, -0.8, 0.0], "LegR": [-0.5, -0.8, 0.0],
    },
    "swing_direction": {"Up": [0.0, -0.8, 0.0], "Left": [0.8, 0.0, 0.0], "Right": [-0.8, 0.0, 0.0], "Down": [0.0, 0.8, 0.0]},
    "named_direction": {"none": [0.0, 0.0, 0.0], "forward": [0.0, 0.0, 1.0], "back": [0.0, 0.0, -1.0], "down": [0.0, -1.0, 0.0], "up": [0.0, 1.0, 0.0], "lateral": [1.0, 0.0, 0.0]},
}

# ---------------------------------------------------------------------------------------------------------------- severity
SEVERITY = {
    "reference_damage": 17.5,        # kHeavyDamage: an unblocked heavy hit on armour = 1.0
    "layer_mult": {"Armor": 1.0, "Mechanism": 1.35, "System": 1.8},
    "zone_weight": {"Head": 1.25, "Torso": 1.2, "Reactor": 1.5, "ShoulderL": 1.0, "ShoulderR": 1.0, "ArmL": 0.8, "ArmR": 0.8, "LegL": 0.7, "LegR": 0.7},
    "blocked_mult": 0.45,
    "parried_mult": 0.1,
    "state_bump": {"Intact": 0.0, "Dented": 0.0, "Exposed": 0.1, "Damaged": 0.4, "Critical": 0.8, "Destroyed": 1.2, "Severed": 1.5},
    "stability_term": {"per_point": 0.005, "cap": 0.3},
    "thresholds": [0.35, 0.9, 1.6, 2.6],   # S0 < t0 <= S1 < t1 <= S2 < t2 <= S3 < t3 <= S4
    "external_source_mult": {"0": 1.0, "1": 1.5, "2": 1.3, "3": 1.4},   # ExternalHit.a: debris, crash, fall, grenade
}

# ---------------------------------------------------------------------------------------------------------------- cockpit
def eff(target, action, count, delay, dur, prob=1.0, **params):
    return {"target": target, "action": action, "count": list(count), "delay_s": list(delay), "duration_s": list(dur), "probability": prob, "params": params}

COCKPIT = {
    "version": 1,
    "red_light": {   # intensity keyframes: pulse period (s), peak, base, fade-out (s) by severity
        "S0": {"period_s": 0.0, "peak": 0.0, "base": 0.0, "fade_s": 0.0},
        "S1": {"period_s": 1.4, "peak": 0.18, "base": 0.0, "fade_s": 1.5},
        "S2": {"period_s": 1.1, "peak": 0.40, "base": 0.08, "fade_s": 3.0},
        "S3": {"period_s": 0.8, "peak": 0.70, "base": 0.18, "fade_s": 6.0},
        "S4": {"period_s": 0.6, "peak": 1.00, "base": 0.35, "fade_s": 10.0},
    },
    "siren": {"S0": None, "S1": None, "S2": {"sound": "fx_alarm_beep", "duration_s": 2.0}, "S3": {"sound": "fx_siren", "duration_s": 6.0}, "S4": {"sound": "fx_siren", "duration_s": 12.0}},
    "voice": {"S0": None, "S1": None, "S2": {"id": "vo_hull_damage", "delay_s": 0.6}, "S3": {"id": "vo_hull_damage", "delay_s": 0.4}, "S4": {"id": "vo_hull_critical", "delay_s": 0.3}},
    "fire": {"spread_per_s": 0.12, "burn_s": [12.0, 25.0], "extinguish_after_s": [6.0, 9.0], "extinguish_below": "S3", "max_simultaneous": 4},
    "severity": {
        "S0": [
            eff("Lamp_Warn", "flicker", [0, 1], [0.0, 0.2], [0.2, 0.4], 0.5),
            eff("SteamPort", "puff", [0, 1], [0.0, 0.3], [0.4, 0.8], 0.3, system="ps_steam_puff"),
        ],
        "S1": [
            eff("SteamPort", "puff", [1, 2], [0.0, 0.4], [0.6, 1.2], 1.0, system="ps_steam_puff"),
            eff("Lamp_Warn", "on", [1, 1], [0.0, 0.3], [2.0, 4.0], 0.8, color="amber"),
            eff("Mon", "glitch", [1, 1], [0.0, 0.3], [0.2, 0.5], 0.7),
            eff("Cockpit_Root", "dust_fall", [1, 1], [0.0, 0.2], [0.8, 1.6], 0.6, system="ps_dust_ceiling"),
        ],
        "S2": [
            eff("Pipe_Burst", "burst", [1, 1], [0.0, 0.3], [6.0, 10.0], 1.0, system="ps_steam_jet", leak="LeakPoint", sound="fx_pipe_burst"),
            eff("Wire_Snapped", "snap", [1, 2], [0.0, 0.5], [3.0, 6.0], 1.0, system="ps_sparks_wire", spark="SparkPort", sound="fx_wire_spark"),
            eff("Lamp_Warn", "on", [3, 5], [0.0, 0.5], [4.0, 8.0], 1.0, color="red"),
            eff("AlarmBeacon", "spin", [1, 1], [0.1, 0.4], [4.0, 6.0], 1.0),
            eff("Mon", "glitch", [1, 2], [0.0, 0.4], [1.0, 2.0], 1.0, sound="fx_monitor_glitch"),
            eff("Glass_Crack_Mask", "crack", [1, 1], [0.0, 0.1], [20.0, 40.0], 0.4, strength=0.35, sound="fx_glass_crack"),
        ],
        "S3": [
            eff("Pipe_Burst", "burst", [2, 4], [0.0, 0.8], [8.0, 14.0], 1.0, system="ps_steam_jet", leak="LeakPoint", sound="fx_pipe_burst"),
            eff("Wire_Snapped", "snap", [3, 5], [0.0, 0.8], [4.0, 8.0], 1.0, system="ps_sparks_wire", spark="SparkPort", sound="fx_wire_spark"),
            eff("Fire_Socket", "ignite", [1, 1], [0.4, 1.2], [12.0, 25.0], 0.9, system="ps_fire_small", sound="fx_fire_loop"),
            eff("Scorch_Decal", "show", [1, 1], [0.6, 1.4], [60.0, 120.0], 0.9),
            eff("Mon", "dead", [1, 2], [0.0, 0.6], [6.0, 12.0], 1.0, sound="fx_monitor_dead"),
            eff("Mon", "glitch", [1, 2], [0.0, 0.6], [1.5, 3.0], 1.0),
            eff("Lamp_Warn", "on", [6, 10], [0.0, 0.8], [8.0, 14.0], 1.0, color="red"),
            eff("AlarmBeacon", "spin", [2, 3], [0.0, 0.5], [6.0, 10.0], 1.0),
            eff("StrobePanel", "strobe", [1, 2], [0.2, 0.8], [1.5, 3.0], 1.0),
            eff("Glass_Crack_Mask", "crack", [1, 2], [0.0, 0.3], [40.0, 90.0], 0.9, strength=0.7, sound="fx_glass_crack"),
            eff("Cockpit_Root", "dust_fall", [1, 1], [0.0, 0.2], [1.5, 3.0], 1.0, system="ps_dust_ceiling"),
        ],
        "S4": [
            eff("Pipe_Burst", "burst", [5, 8], [0.0, 1.0], [10.0, 18.0], 1.0, system="ps_steam_jet", leak="LeakPoint", sound="fx_pipe_burst"),
            eff("Wire_Snapped", "snap", [6, 10], [0.0, 1.0], [5.0, 10.0], 1.0, system="ps_sparks_wire", spark="SparkPort", sound="fx_wire_spark"),
            eff("Fire_Socket", "ignite", [2, 3], [0.3, 1.5], [15.0, 30.0], 1.0, system="ps_fire_big", sound="fx_fire_loop"),
            eff("Scorch_Decal", "show", [2, 3], [0.5, 1.6], [90.0, 180.0], 1.0),
            eff("Mon", "dead", [4, 6], [0.0, 0.8], [10.0, 20.0], 1.0, sound="fx_monitor_dead"),
            eff("Lamp_Warn", "on", [12, 20], [0.0, 1.0], [10.0, 20.0], 1.0, color="red"),
            eff("Lamp_Ok", "off", [8, 14], [0.0, 0.8], [10.0, 20.0], 1.0),
            eff("AlarmBeacon", "spin", [4, 4], [0.0, 0.4], [10.0, 16.0], 1.0),
            eff("StrobePanel", "strobe", [3, 4], [0.1, 0.6], [3.0, 5.0], 1.0),
            eff("Glass_Crack_Mask", "crack", [2, 3], [0.0, 0.4], [60.0, 120.0], 1.0, strength=1.0, sound="fx_glass_shatter"),
            eff("Camera_Rig", "power_flicker", [1, 1], [0.0, 0.3], [0.5, 0.9], 1.0, sound="fx_power_flicker"),
            eff("Cockpit_Root", "dust_fall", [1, 1], [0.0, 0.2], [2.5, 4.5], 1.0, system="ps_dust_ceiling"),
            eff("Cockpit_Root", "smoke", [1, 1], [0.8, 2.0], [10.0, 25.0], 1.0, system="ps_smoke_dark"),
        ],
    },
}

# ---------------------------------------------------------------------------------------------------------------- mech chunks
def chunk(type_, count, mass, speed, spin, life, fire=0.0, fire_s=(0, 0), smoke_s=(0, 0), sparks=0, mesh="Armor_Plate"):
    return {"type": type_, "mesh_hint": mesh, "count": list(count), "mass_kg": list(mass), "speed_mps": list(speed), "spin_rad_s": list(spin), "life_s": list(life),
            "fire_prob": fire, "fire_s": list(fire_s), "smoke_s": list(smoke_s), "ground_sparks": sparks}

ZONE_SIZE = {"Head": 0.5, "Torso": 1.4, "Reactor": 1.0, "ShoulderL": 1.0, "ShoulderR": 1.0, "ArmL": 0.9, "ArmR": 0.9, "LegL": 1.1, "LegR": 1.1}

def zone_chunks(zone):
    k = ZONE_SIZE[zone]
    n = lambda a, b: [max(1, int(round(a * k))), max(1, int(round(b * k)))]
    d = {
        "Armor": [chunk("armor_plate", n(1, 2), [200 * k, 900 * k], [14, 34], [1.0, 6.0], [5, 9], 0.25, [4, 9], [3, 7], 6, "Armor_Plate"),
                  chunk("armor_plate_burning", [0, 1], [150 * k, 500 * k], [10, 26], [2.0, 8.0], [6, 11], 1.0, [6, 12], [6, 12], 10, "Armor_Plate_Burning"),
                  chunk("debris_small", n(3, 6), [5, 40], [10, 40], [3.0, 12.0], [3, 6], 0.1, [2, 4], [1, 3], 2, "Shard_Steel_Small")],
        "Mechanism": [chunk("piston", [1, 2], [80, 260], [12, 28], [1.5, 6.0], [5, 9], 0.2, [4, 8], [3, 6], 5, "Piston_Rod"),
                      chunk("hose", n(1, 3), [10, 60], [8, 22], [2.0, 9.0], [4, 8], 0.4, [3, 7], [3, 7], 3, "Hose_Cut"),
                      chunk("armor_plate", [0, 1], [200 * k, 700 * k], [14, 30], [1.0, 5.0], [5, 9], 0.3, [4, 9], [3, 7], 6, "Armor_Plate")],
        "System": [chunk("cable_bundle", n(2, 4), [20, 90], [8, 20], [2.0, 8.0], [4, 8], 0.6, [3, 8], [3, 8], 4, "Cable_Bundle"),
                   chunk("sensor_housing" if zone == "Head" else "reactor_fragment" if zone == "Reactor" else "piston", [1, 2], [60, 300], [10, 26], [1.0, 6.0], [5, 10], 0.7, [5, 12], [5, 12], 8,
                         "Sensor_Housing" if zone == "Head" else "Reactor_Fragment" if zone == "Reactor" else "Piston_Rod"),
                   chunk("armor_plate_burning", [1, 2], [150 * k, 600 * k], [12, 28], [2.0, 8.0], [6, 12], 1.0, [8, 16], [8, 16], 10, "Armor_Plate_Burning")],
    }
    return d

MECH_CHUNKS = {
    "version": 1,
    "units": "SI: metres, kilograms, seconds; velocities are along the impact normal + spread; the mech is 82 m tall",
    "ballistics": {"gravity": 9.81, "drag_per_s": 0.04, "max_range_m": 120.0, "spawn_offset_m": 0.8, "min_up_mps": 6.0, "spread_deg": 38.0, "owner_capsule_radius_m": {"default": 12.0}, "speed_scale_by_severity": [0.6, 0.8, 1.0, 1.15, 1.3]},
    "event_rules": {
        "ArmorPlateLost": {"layers": ["Armor"], "scale": 1.0, "count_mult": 1.0},
        "HitEvent": {"min_layer": "Mechanism", "min_severity": "S2", "count_mult": 0.7},
        "LimbSevered": {"layers": ["Armor", "Mechanism", "System"], "scale": 1.4, "count_mult": 1.0, "extra": "limb_part"},
        "ReactorBreach": {"layers": ["System"], "scale": 1.3, "count_mult": 1.0, "zone": "Reactor"},
        "UltimateFinisher": {"layers": ["Armor", "Mechanism", "System"], "scale": 1.6, "count_mult": 2.0},
        "UltimateSever": {"layers": ["Armor", "Mechanism", "System"], "scale": 1.5, "count_mult": 1.5, "extra": "limb_part"},
        "ExternalHit": {"min_layer": "Mechanism", "min_severity": "S2", "count_mult": 0.8},
        "BoardingBlast": {"layers": ["Armor", "Mechanism"], "scale": 1.2, "count_mult": 1.2},
    },
    "limb_part": chunk("limb_part", [2, 3], [800, 4000], [10, 30], [0.5, 3.0], [8, 14], 0.8, [10, 20], [10, 20], 14, "Limb_Part"),
    "zones": {z: zone_chunks(z) for z in ZONES},
}

# ---------------------------------------------------------------------------------------------------------------- buildings
def spawn(t, cls, count, speed, cone, mass, life, **kw):
    d = {"t_s": t, "class": cls, "count": count, "speed_mps": list(speed), "cone_deg": cone, "mass_kg": list(mass), "life_s": list(life)}
    d.update(kw)
    return d

BUILDINGS = {
    "version": 1,
    "budgets": {"large_shards": 400, "small_shards": 6000, "smoke_puffs": 80, "cpu_particle_tick_hz": 30},
    "classes": {   # budget class of every shard family
        "Shard_Concrete_S": "small", "Shard_Concrete_M": "small", "Shard_Concrete_L": "large", "Shard_Concrete_XL": "large", "Slab_Concrete": "large", "Column_Broken": "large",
        "Panel_Facade_Torn": "large", "Girder_Twisted": "large", "Steel_Plate_Bent": "large", "AC_Unit_Broken": "large", "Sign_Torn": "large",
        "Glass_Shard": "small", "Gravel_Cluster": "small", "Pebble": "small", "Rebar_Single": "small", "Rebar_Bundle": "small", "Pipe_Broken": "small",
        "Cable_Dangling": "small", "Window_Frame_Broken": "small",
    },
    "dust": {   # colour by material (linear sRGB) and density curve: seconds -> relative volume
        "concrete": {"color": [0.55, 0.54, 0.50], "density": [[0, 0.0], [0.4, 0.5], [1.5, 1.0], [6.0, 0.7], [14.0, 0.25], [24.0, 0.0]]},
        "glass_curtain": {"color": [0.62, 0.70, 0.74], "density": [[0, 0.0], [0.3, 0.4], [1.2, 0.8], [5.0, 0.5], [11.0, 0.15], [18.0, 0.0]]},
        "brick": {"color": [0.55, 0.38, 0.32], "density": [[0, 0.0], [0.4, 0.5], [1.6, 1.0], [6.0, 0.7], [14.0, 0.25], [24.0, 0.0]]},
        "steel_frame": {"color": [0.30, 0.30, 0.32], "density": [[0, 0.0], [0.5, 0.4], [2.0, 0.9], [7.0, 0.6], [16.0, 0.2], [26.0, 0.0]]},
    },
    "scenarios": {
        "sword_hit": {"energy_ref_kj": 800.0, "stages": [
            {"name": "contact", "t0": 0.0, "t1": 0.1, "spawns": [spawn(0.0, "Shard_Concrete_M", 14, [8, 24], 70, [8, 60], [3, 6]), spawn(0.0, "Glass_Shard", 120, [6, 22], 85, [0.02, 0.2], [2, 5])]},
            {"name": "facade_crush", "t0": 0.1, "t1": 0.7, "spawns": [spawn(0.15, "Shard_Concrete_L", 6, [6, 16], 60, [120, 600], [4, 8]), spawn(0.2, "Pebble", 360, [5, 24], 80, [0.3, 3.0], [3, 7]), spawn(0.3, "Panel_Facade_Torn", 2, [4, 12], 50, [200, 900], [5, 9])]},
            {"name": "floor_collapse", "t0": 0.5, "t1": 2.5, "spawns": [spawn(0.8, "Slab_Concrete", 2, [1, 6], 40, [600, 3000], [6, 12])]},
            {"name": "dust_cloud", "t0": 0.4, "t1": 24.0, "spawns": []}]},
        "mech_crash": {"energy_ref_kj": 6000.0, "stages": [
            {"name": "contact", "t0": 0.0, "t1": 0.15, "spawns": [spawn(0.0, "Shard_Concrete_M", 30, [10, 30], 80, [8, 60], [3, 6]), spawn(0.0, "Glass_Shard", 320, [8, 30], 90, [0.02, 0.2], [2, 5])]},
            {"name": "facade_crush", "t0": 0.15, "t1": 1.0, "spawns": [spawn(0.2, "Shard_Concrete_L", 12, [8, 20], 70, [120, 600], [4, 9]), spawn(0.3, "Shard_Concrete_XL", 3, [4, 12], 50, [900, 4000], [6, 12]),
                                                                       spawn(0.25, "Pebble", 1200, [6, 28], 85, [0.3, 3.0], [3, 8]), spawn(0.4, "Panel_Facade_Torn", 5, [4, 14], 55, [200, 900], [5, 10]), spawn(0.4, "Rebar_Single", 60, [4, 16], 70, [3, 20], [4, 8])]},
            {"name": "floor_collapse", "t0": 0.6, "t1": 4.0, "spawns": [spawn(0.9, "Slab_Concrete", 6, [1, 8], 45, [600, 3000], [8, 14]), spawn(1.3, "Column_Broken", 2, [1, 5], 35, [1500, 6000], [8, 14]),
                                                                       spawn(1.5, "Gravel_Cluster", 80, [2, 12], 70, [5, 40], [5, 10])]},
            {"name": "dust_cloud", "t0": 0.5, "t1": 26.0, "spawns": []}]},
        "thrown_debris": {"energy_ref_kj": 1200.0, "stages": [
            {"name": "contact", "t0": 0.0, "t1": 0.1, "spawns": [spawn(0.0, "Shard_Concrete_M", 18, [8, 26], 75, [8, 60], [3, 6]), spawn(0.0, "Glass_Shard", 160, [6, 24], 85, [0.02, 0.2], [2, 5])]},
            {"name": "facade_crush", "t0": 0.1, "t1": 0.8, "spawns": [spawn(0.2, "Shard_Concrete_L", 7, [6, 16], 60, [120, 600], [4, 8]), spawn(0.25, "Pebble", 520, [5, 26], 80, [0.3, 3.0], [3, 7])]},
            {"name": "floor_collapse", "t0": 0.6, "t1": 2.8, "spawns": [spawn(0.9, "Slab_Concrete", 3, [1, 6], 40, [600, 3000], [6, 12])]},
            {"name": "dust_cloud", "t0": 0.4, "t1": 22.0, "spawns": []}]},
        "plasma": {"energy_ref_kj": 2500.0, "stages": [
            {"name": "contact", "t0": 0.0, "t1": 0.1, "spawns": [spawn(0.0, "Shard_Concrete_S", 40, [10, 34], 90, [1, 8], [2, 5]), spawn(0.0, "Glass_Shard", 260, [8, 30], 95, [0.02, 0.2], [2, 5])]},
            {"name": "facade_crush", "t0": 0.1, "t1": 0.9, "spawns": [spawn(0.2, "Shard_Concrete_L", 8, [6, 18], 65, [120, 600], [4, 8]), spawn(0.2, "Pebble", 700, [6, 30], 90, [0.3, 3.0], [3, 7]), spawn(0.3, "Cable_Dangling", 6, [2, 8], 60, [2, 12], [4, 8])]},
            {"name": "floor_collapse", "t0": 0.7, "t1": 3.0, "spawns": [spawn(1.0, "Slab_Concrete", 3, [1, 6], 40, [600, 3000], [6, 12])]},
            {"name": "dust_cloud", "t0": 0.4, "t1": 24.0, "spawns": []}]},
        "rockets": {"energy_ref_kj": 500.0, "stages": [
            {"name": "contact", "t0": 0.0, "t1": 0.08, "spawns": [spawn(0.0, "Shard_Concrete_S", 24, [10, 30], 90, [1, 8], [2, 5]), spawn(0.0, "Glass_Shard", 200, [8, 28], 95, [0.02, 0.2], [2, 5])]},
            {"name": "facade_crush", "t0": 0.08, "t1": 0.6, "spawns": [spawn(0.12, "Shard_Concrete_M", 14, [8, 22], 70, [8, 60], [3, 7]), spawn(0.15, "Pebble", 300, [6, 24], 85, [0.3, 3.0], [3, 7])]},
            {"name": "floor_collapse", "t0": 0.5, "t1": 1.8, "spawns": []},
            {"name": "dust_cloud", "t0": 0.3, "t1": 18.0, "spawns": []}]},
    },
    "smoke_puffs": {"base": 20, "per_energy_unit": 40, "max": 80, "lifetime_s": [6.0, 22.0]},
    "sounds": {"contact": "fx_building_crack", "facade_crush": "fx_building_collapse", "floor_collapse": "fx_building_collapse", "dust_cloud": "fx_dust_whoosh", "debris_rain": "fx_debris_rain", "glass_rain": "fx_glass_rain"},
    "material_scale": {"concrete": {"Glass_Shard": 0.15}, "glass_curtain": {"Glass_Shard": 3.0, "Shard_Concrete_L": 0.3, "Pebble": 0.6}, "brick": {"Pebble": 1.4}, "steel_frame": {"Girder_Twisted": 1.0, "Steel_Plate_Bent": 1.0}},
}

# ---------------------------------------------------------------------------------------------------------------- warnings
def warn(id_, trigger, priority, color, blink, sound, icon, voice=None, hold_s=3.0, **kw):
    d = {"id": id_, "trigger": trigger, "priority": priority, "color": color, "blink_ms": blink, "sound": sound, "hud_icon": icon, "voice": voice, "hold_s": hold_s}
    d.update(kw)
    return d

WARNINGS = {
    "version": 1,
    "colors": {"red": "#ff4a3d", "orange": "#ff9a2e", "amber": "#ffd24a", "cyan": "#7fe4ff", "white": "#e8fbff"},
    "priority_note": "1 = highest. Only the highest priority warning owns the siren and the voice; lower ones keep their lamp / HUD icon.",
    "warnings": [
        warn("reactor_breach", {"event": "ReactorBreach"}, 1, "red", [200, 200], "fx_siren", "icon_reactor", "vo_reactor_breach", 8.0, red_edge=True),
        warn("hull_critical", {"event": "HitEvent", "min_severity": "S4"}, 1, "red", [250, 250], "fx_siren", "icon_hull", "vo_hull_critical", 6.0, red_edge=True),
        warn("power_loss", {"event": "Shutdown"}, 1, "red", [400, 400], "fx_power_flicker", "icon_power", "vo_power_loss", 10.0, red_edge=True),
        warn("arm_lost", {"event": "LimbSevered", "zones": ["ArmL", "ArmR"]}, 2, "red", [300, 300], "fx_alarm_beep", "icon_arm", "vo_arm_lost", 5.0),
        warn("leg_lost", {"event": "LimbSevered", "zones": ["LegL", "LegR"]}, 2, "red", [300, 300], "fx_alarm_beep", "icon_leg", "vo_leg_lost", 5.0),
        warn("sensors_failed", {"event": "SystemFailure", "system": "Sensors"}, 2, "orange", [500, 300], "fx_monitor_glitch", "icon_sensors", "vo_sensors_failed", 5.0),
        warn("system_failure", {"event": "SystemFailure"}, 3, "orange", [500, 500], "fx_alarm_beep", "icon_hull", None, 4.0),
        warn("overheat", {"event": "HeatWarning"}, 3, "orange", [600, 400], "fx_alarm_beep", "icon_heat", "vo_overheat", 6.0),
        warn("coolant_leak", {"event": "CoolantLeak"}, 3, "orange", [700, 300], "fx_steam_jet", "icon_coolant", "vo_coolant_leak", 6.0),
        warn("fire_in_cockpit", {"event": "cockpit_fire"}, 3, "red", [350, 350], "fx_fire_loop", "icon_fire", None, 4.0),
        warn("burning", {"event": "StatusApplied", "status": "Burn"}, 4, "orange", [500, 500], "fx_alarm_beep", "icon_status_burn", None, 3.0),
        warn("blinded", {"event": "StatusApplied", "status": "Blind"}, 4, "cyan", [800, 400], "fx_monitor_glitch", "icon_status_blind", None, 3.0),
        warn("strike_lock", {"event": "StatusApplied", "status": "StrikeLock"}, 4, "amber", [600, 600], "fx_alarm_beep", "icon_status_strikelock", None, 3.0),
        warn("hook_alert", {"event": "BoardingSwatTelegraph"}, 1, "red", [150, 150], "fx_siren", "icon_hook", "vo_hook_alert", 3.0, red_edge=True, note="TASK-017: the enemy hand is swinging at the pilot"),
        warn("ultimate_ready", {"event": "UltimateReady"}, 5, "cyan", [900, 300], None, "icon_ultimate", "vo_ultimate_ready", 4.0),
        warn("weapon_ready", {"event": "WeaponReady"}, 5, "white", [300, 0], None, "icon_weapon_rail", "vo_weapon_ready", 1.5),
    ],
}

# ---------------------------------------------------------------------------------------------------------------- coverage / global
GLOBAL = {
    "version": 1,
    "note": "The 'juiciness knobs'. Everything multiplies the table values at run time; 1.0 = as authored.",
    "knobs": {"shake": 1.0, "shake_reduce_motion": False, "cockpit_fire": 1.0, "cockpit_effects_count": 1.0, "chunks_count": 1.0, "chunks_speed": 1.0, "building_shards": 1.0,
              "building_dust": 1.0, "red_light": 1.0, "siren_volume": 1.0},
    "ranges": {"shake": [0.0, 2.0], "cockpit_fire": [0.0, 2.0], "cockpit_effects_count": [0.25, 2.0], "chunks_count": [0.25, 2.0], "chunks_speed": [0.5, 1.5], "building_shards": [0.25, 1.5],
               "building_dust": [0.25, 2.0], "red_light": [0.0, 1.5], "siren_volume": [0.0, 1.0]},
}

# every EventType of core/include/iv/Events.h is listed in exactly one group (a test compares the list with the header)
COVERAGE = {
    "version": 1,
    "shake": [k for k in SHAKE["events"]],
    "warnings_only": ["UltimateReady", "WeaponReady", "BoardingSwatTelegraph", "HeatWarning", "CoolantLeak", "StatusApplied", "SystemFailure", "Shutdown", "LimbSevered", "ReactorBreach"],
    "chunks": list(MECH_CHUNKS["event_rules"].keys()),
    "cockpit_by_severity": ["HitEvent", "ExternalHit", "ReactorBreach", "SystemFailure", "LimbSevered", "UltimateFinisher", "UltimateSever", "BoardingSwatImpact", "BoardingBlast"],
    "no_cockpit_effect": ["WindupStarted", "Committed", "CancelCheap", "EmergencyBrake", "Feint", "Interrupted", "StrikeContact", "Hit", "Whiff", "ZoneState", "EnergyFlow", "EnergyShift",
                          "ReverseChain", "ReverseFailed", "ClinchResolved", "HardStanceOn", "HardStanceOff", "WeaponInterrupted", "PoseReturn", "UltimateReady", "CinematicBegin",
                          "CinematicEnd", "WeaponReady", "WeaponEmpty", "StatusEnded", "BoardingStarted", "BoardingPhase", "BoardingDenied", "HackStarted", "HackProgress",
                          "HackResultEvt", "BoardingSwingOk", "BoardingSmashed", "GrenadeThrown", "BoardingEnded", "BoardingSwatAdjusted"],
    "note": "HitEvent carries the effect of 'Hit' / 'Blocked' (the core emits both); StrikeContact / ZoneState / Hit are bookkeeping events with no effect of their own.",
}


OUT_DIR = HERE


def dump(name, obj):
    with open(os.path.join(OUT_DIR, name), "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=1, ensure_ascii=False, sort_keys=False)
        f.write("\n")


def main(out_dir=None):
    global OUT_DIR
    OUT_DIR = out_dir or HERE
    dump("identifiers.json", IDENTIFIERS)
    dump("shake_profiles.json", {"version": 1, **SHAKE, "severity": SEVERITY})
    dump("cockpit_effects.json", COCKPIT)
    dump("mech_chunks.json", MECH_CHUNKS)
    dump("building_destruction.json", BUILDINGS)
    dump("warnings.json", WARNINGS)
    dump("global_tuning.json", GLOBAL)
    dump("coverage.json", COVERAGE)
    print("wrote 8 tables into", OUT_DIR)


if __name__ == "__main__":
    import sys
    main(sys.argv[1] if len(sys.argv) > 1 else None)
