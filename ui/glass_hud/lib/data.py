"""Source of truth for the JSON contracts: palette, states, layout (normalised 16:9 rects), event bindings."""

ZONES = ["Head", "Torso", "Reactor", "ShoulderL", "ShoulderR", "ArmL", "ArmR", "LegL", "LegR"]
LAYERS = ["Armor", "Mechanism", "System"]
ZONE_STATES = ["Intact", "Dented", "Exposed", "Damaged", "Critical", "Destroyed", "Severed"]
STATUSES = ["Blind", "StrikeLock", "Burn"]
WEAPONS = ["RailSpear", "SuppressionRockets", "PlasmaCannon"]
PRIORITIES = ["Arms", "Legs", "Guard", "Weapon"]

PALETTE = {
    "version": 1,
    "note": "Pitch s.21 colour code: neutral = intact, yellow = exposed armour, orange = damaged mechanism, red = critical, black (grey outline) = lost. Hex values match data/damage_fx/warnings.json.",
    "colors": {
        "cyan": "#7fe4ff", "white": "#e8fbff", "red": "#ff4a3d", "orange": "#ff9a2e", "amber": "#ffd24a", "pale_amber": "#f3e7a0",
        "neutral": "#bfeeff", "lost": "#7d8899", "ink": "#0b1220", "bg_dark": "#05080d", "bg_mid": "#25324a", "bg_light": "#c8d4de", "ok": "#7fe4ff",
    },
    "zone_state": {"Intact": "neutral", "Dented": "pale_amber", "Exposed": "amber", "Damaged": "orange", "Critical": "red", "Destroyed": "lost", "Severed": "lost"},
    "min_contrast": {"core_on_dark": 3.0, "halo_on_light": 3.0},
}

STATES = {
    "version": 1,
    "zone_state_style": {
        "Intact": {"color": "neutral", "dash": None, "width": 2.4, "blink_hz": 0.0, "fill_opacity": 0.06},
        "Dented": {"color": "pale_amber", "dash": None, "width": 2.5, "blink_hz": 0.0, "fill_opacity": 0.09},
        "Exposed": {"color": "amber", "dash": None, "width": 2.9, "blink_hz": 0.0, "fill_opacity": 0.15},
        "Damaged": {"color": "orange", "dash": "9 3", "width": 3.1, "blink_hz": 0.0, "fill_opacity": 0.18},
        "Critical": {"color": "red", "dash": None, "width": 3.6, "blink_hz": 2.5, "fill_opacity": 0.26},
        "Destroyed": {"color": "lost", "dash": "2 5", "width": 2.2, "blink_hz": 0.0, "fill_opacity": 0.0},
        "Severed": {"color": "lost", "dash": "2 5", "width": 2.2, "blink_hz": 0.0, "fill_opacity": 0.0, "slash": True},
    },
    "layer_arc": {"note": "A layer arc is drawn with the length = remaining fraction of that layer; the colour is that of the zone state; Destroyed/Severed zones show empty dotted arcs.", "sweep_deg": 70.0, "radius_step": 6.0},
    "gauges": {
        "armor": {"color": "neutral", "low": 0.35, "low_color": "orange", "critical": 0.15, "critical_color": "red", "segments": 24},
        "stability": {"color": "cyan", "low": 0.35, "low_color": "orange", "critical": 0.15, "critical_color": "red", "segments": 0},
        "heat": {"color": "cyan", "warm": 0.6, "warm_color": "orange", "hot": 0.85, "hot_color": "red", "segments": 0, "inverse": True},
        "energy": {"color": "amber", "low": 0.25, "low_color": "red", "segments": 12},
        "ultimate": {"color": "cyan", "ready_color": "white", "segments": 12, "ready_blink_hz": 2.0},
    },
    "alarm": {"red_edge_color": "red", "blink_hz": {"S2": 1.5, "S3": 2.0, "S4": 3.0}, "vignette_alpha": {"S0": 0.0, "S1": 0.0, "S2": 0.35, "S3": 0.6, "S4": 0.9}},
    "glass_fx": {"cracks_by_severity": {"S2": 1, "S3": 3, "S4": 5}, "soot_by_severity": {"S3": 1, "S4": 3}, "glitch_by_severity": {"S1": 0.1, "S2": 0.25, "S3": 0.5, "S4": 0.85}, "signal_loss_s": 0.6},
    "lockon": {"quality_colors": [[0.0, "red"], [0.4, "amber"], [0.75, "cyan"]], "stability_warn": 0.35},
}

# Layout in normalised 16:9 coordinates [x, y, w, h] of the 1920x1080 reference. anchor decides how the rect moves for other aspect ratios (see lib/scene.py).
ELEMENTS = [
    {"id": "body_player", "file": "svg/silhouette_body_player.svg", "anchor": "top_left", "rect": [0.020, 0.030, 0.135, 0.330], "persistent": True},
    {"id": "layers_player", "file": "svg/zone_layers_arcs.svg", "anchor": "top_left", "rect": [0.020, 0.030, 0.135, 0.330], "persistent": True, "overlay_of": "body_player"},
    {"id": "body_enemy", "file": "svg/silhouette_body_enemy.svg", "anchor": "top_right", "rect": [0.845, 0.030, 0.135, 0.330], "persistent": True},
    {"id": "layers_enemy", "file": "svg/zone_layers_arcs_enemy.svg", "anchor": "top_right", "rect": [0.845, 0.030, 0.135, 0.330], "persistent": True, "overlay_of": "body_enemy"},
    {"id": "enemy_status", "file": "svg/status_icons_row.svg", "anchor": "top_right", "rect": [0.845, 0.375, 0.135, 0.050], "persistent": False},
    {"id": "enemy_stability", "file": "svg/stability_bar_h.svg", "anchor": "top_right", "rect": [0.845, 0.435, 0.135, 0.028], "persistent": False},
    {"id": "compass", "file": "svg/compass_strip.svg", "anchor": "top_center", "rect": [0.350, 0.020, 0.300, 0.040], "persistent": True},
    {"id": "weapons", "file": "svg/weapon_icons_row.svg", "anchor": "bottom_left", "rect": [0.020, 0.745, 0.150, 0.055], "persistent": True},
    {"id": "gauge_armor", "file": "png/bar_armor.png", "anchor": "bottom_left", "rect": [0.020, 0.835, 0.060, 0.107], "persistent": True},
    {"id": "gauge_stability", "file": "png/bar_stability.png", "anchor": "bottom_left", "rect": [0.087, 0.835, 0.060, 0.107], "persistent": True},
    {"id": "gauge_heat", "file": "png/bar_heat.png", "anchor": "bottom_left", "rect": [0.154, 0.835, 0.060, 0.107], "persistent": True},
    {"id": "gauge_energy", "file": "png/bar_energy.png", "anchor": "bottom_left", "rect": [0.221, 0.835, 0.060, 0.107], "persistent": True},
    {"id": "arm_armor", "file": "svg/arm_armor_bars.svg", "anchor": "bottom_left", "rect": [0.020, 0.950, 0.261, 0.020], "persistent": True},
    {"id": "clock", "file": "svg/clock_digits.svg", "anchor": "bottom_right", "rect": [0.805, 0.700, 0.062, 0.035], "persistent": True},
    {"id": "distance", "file": "svg/distance_digits.svg", "anchor": "bottom_right", "rect": [0.875, 0.700, 0.105, 0.035], "persistent": True},
    {"id": "priority", "file": "svg/power_priority.svg", "anchor": "bottom_right", "rect": [0.805, 0.748, 0.062, 0.038], "persistent": True},
    {"id": "radar", "file": "svg/radar.svg", "anchor": "bottom_right", "rect": [0.875, 0.745, 0.105, 0.187], "persistent": True},
    {"id": "ultimate", "file": "png/ultimate_gauge.png", "anchor": "bottom_right", "rect": [0.805, 0.835, 0.062, 0.110], "persistent": True},
]
# Elements that live where the world is (projected by the game) or in the centre; they may occupy the free centre.
WORLD_ELEMENTS = [
    {"id": "lockon", "file": "svg/lockon_corners.svg", "note": "4 corner brackets around the target's screen rect; min 120 px, drawn over the enemy", "center_ok": True},
    {"id": "lockon_ring", "file": "png/lockon_ring_anim_strip.png", "note": "16-frame 4x4 strip (128 px cells), 24 fps loop while the lock is being acquired", "center_ok": True},
    {"id": "lockon_zone_hexes", "file": "svg/lockon_zone_hexes.svg", "note": "hex outline of the selected zone on the enemy (pitch s.21)", "center_ok": True},
    {"id": "strike_arc", "file": "svg/strike_arc.svg", "note": "the thin line the player draws for the strike; the only persistent central element", "center_ok": True},
    {"id": "crosshair", "file": "svg/crosshair.svg", "note": "tiny reticle, 24 px", "center_ok": True},
    {"id": "off_screen_arrow", "file": "svg/threat_arrows_up.svg", "note": "points at an off-screen target, clamped to the safe margin", "center_ok": False},
]
FULLSCREEN_LAYERS = [
    {"id": "alarm_frame", "file": "png/alarm_frame.png", "blend": "add"},
    {"id": "threat_arrows", "files": ["svg/threat_arrows_up.svg", "svg/threat_arrows_left.svg", "svg/threat_arrows_right.svg", "svg/threat_arrows_down.svg"], "placement": "edge midpoints, 2 % inset"},
    {"id": "crack_masks", "files": ["png/crack_mask_%02d.png" % i for i in range(8)], "blend": "mask"},
    {"id": "soot_masks", "files": ["png/soot_mask_%02d.png" % i for i in range(4)], "blend": "multiply"},
    {"id": "rain_drops", "files": ["png/rain_drops_atlas.png"], "blend": "normal"},
    {"id": "glitch_strips", "files": ["png/glitch_strip_%02d.png" % i for i in range(8)], "blend": "add"},
]
ASPECTS = {"16:9": 16 / 9, "21:9": 21 / 9, "16:10": 16 / 10}
FREE_CENTER = [0.20, 0.20, 0.60, 0.60]
MAX_PERSISTENT_COVERAGE = 0.25

# Event -> element -> behaviour (EventType names must exist in core/include/iv/Events.h: a test parses the header).
BINDINGS = [
    ("ZoneState", "layers_player / layers_enemy / body_*", "Recolour the zone (a = new ZoneState) with the style from states.json; Critical blinks; actor decides the player or the enemy silhouette."),
    ("HitEvent", "layers_*, alarm_frame, cracks", "Pulse the hit zone outline (0.25 s); layer reached (a) shortens that layer arc; severity b >= Exposed spawns the plate marks; S2+ adds a crack mask, S3+ soot."),
    ("ArmorPlateLost", "body_* (shard marks)", "Small shard ticks fly off the zone outline; the Armor arc loses 1/b of its length."),
    ("ReactorBreach", "body_player zone_Reactor, alarm_frame", "Reactor hex turns red and blinks 4 Hz for 8 s, red edge frame on."),
    ("SystemFailure", "weapons, gauge_*, priority, radar", "The matching widget shows a dead state (dotted outline, no fill); a = SystemId (Sensors -> radar + lock-on quality 0, Power -> gauge_energy, Cooling -> gauge_heat, Weapon -> weapons)."),
    ("LimbSevered", "body_* zone", "Zone drawn as Severed (dotted + slash); an arm hides its weapon-hand icon."),
    ("StaggerBegin", "gauge_stability, alarm_frame", "Stability ring flashes orange; short horizontal glitch strip."),
    ("StaggerEnd", "gauge_stability", "Flash stops."),
    ("Knockdown", "alarm_frame, glitch_strips", "Signal loss 0.6 s (glitch strip alpha 1), red edge frame pulse."),
    ("HeatWarning", "gauge_heat", "Ring turns orange then red above the hot threshold and blinks 2 Hz."),
    ("CoolantLeak", "gauge_heat, body_player", "Heat ring drips marks; the torso outline blinks amber."),
    ("Shutdown", "all persistent elements", "Everything dims to 25 % except alarm_frame and gauge_energy (power loss)."),
    ("EnergyShift", "priority", "The new priority pictogram lights, the old one fades (0.3 s)."),
    ("StatusApplied", "enemy_status, body_player corner", "Show the status icon (a = StatusKind: Blind, StrikeLock, Burn) with a duration ring (b ticks); actor chooses the player or the enemy side."),
    ("StatusEnded", "enemy_status", "Remove the status icon."),
    ("WeaponCharging", "weapons", "The weapon icon fills a ring."),
    ("WeaponFired", "weapons", "Icon flash, cooldown ring starts from full."),
    ("WeaponReady", "weapons", "Ring completes, icon pulses once (a = WeaponKind)."),
    ("WeaponEmpty", "weapons", "Icon turns red and dotted."),
    ("UltimateReady", "ultimate", "Ring full: white blink 2 Hz."),
    ("UltimateUsed", "ultimate", "Ring empties with a sweep."),
    ("WindupStarted", "threat_arrows, strike_arc", "Threat arrow in the attack direction (b = SwingSide) with a wide sector; narrows after the commit."),
    ("Committed", "threat_arrows", "The arrow turns solid red and the sector collapses into a line."),
    ("StrikeContact", "alarm_frame", "Single white-red flash of the edges at the contact moment."),
    ("ExternalHit", "alarm_frame, threat_arrows", "Arrow from the side of the source (a: 0 debris, 1 building, 2 fall)."),
    ("BurnTick", "status_icons_burn, soot_masks", "Burn icon pulses; soot grows by one step every 5 ticks."),
    ("BoardingSwatTelegraph", "threat_arrows, alarm_frame", "Corner arrow on the shoulder side (a), the edge frame fills during b ticks until impact."),
    ("HackProgress", "distance, lockon_ring", "Progress arc around the crosshair (value 0..1)."),
    ("MatchEnd", "all", "Fade everything out over 1 s (a = EndReason)."),
]
