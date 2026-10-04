"""Static data of the cyberpunk layer (TASK-019): glass tower presets (`towers.json`), pseudo-Japanese glyph sets (`glyph_sets.json`, invented, no real
brands or readable words), neon palette, destruction rules (fracture pattern ids of TASK-016)."""
from .rng import Rng

# ---- neon palette: cyan / magenta / amber / red + warm tungsten (at most these five hues per block) --------------------------------
PALETTE = {"cyan": (60, 230, 255), "magenta": (255, 70, 200), "amber": (255, 180, 50), "red": (255, 60, 50), "tungsten": (255, 200, 130)}
NEON_NAMES = ["cyan", "magenta", "amber", "red"]          # tungsten is reserved for lamps and windows

# ---- glass tower presets: 12 silhouettes ---------------------------------------------------------------------------------------------------
TOWER_PRESETS = [
    {"id": "tower_00", "name": "slab_mirror", "crown": "flat", "setbacks": [], "tint": [90, 150, 190], "reflectivity": [0.70, 0.85], "mullion_spacing_m": [1.4, 1.8], "panel_w": 1.5,
     "spandrel_ratio": 0.16, "emissive": {"pattern": "random", "density": 0.35}, "rooftop_lights": 4, "aspect": [1.0, 1.4], "height_range": [120, 220]},
    {"id": "tower_01", "name": "ziggurat", "crown": "stepped", "setbacks": [{"at": 0.45, "inset_m": 4.0}, {"at": 0.70, "inset_m": 4.0}, {"at": 0.88, "inset_m": 3.0}], "tint": [120, 170, 190],
     "reflectivity": [0.60, 0.80], "mullion_spacing_m": [1.5, 2.0], "panel_w": 1.8, "spandrel_ratio": 0.2, "emissive": {"pattern": "bands", "density": 0.5}, "rooftop_lights": 6, "aspect": [1.0, 1.2],
     "height_range": [140, 260]},
    {"id": "tower_02", "name": "slant_roof", "crown": "slanted", "setbacks": [], "tint": [70, 130, 170], "reflectivity": [0.75, 0.9], "mullion_spacing_m": [1.2, 1.6], "panel_w": 1.4,
     "spandrel_ratio": 0.14, "emissive": {"pattern": "columns", "density": 0.3}, "rooftop_lights": 3, "aspect": [1.0, 1.6], "height_range": [130, 240]},
    {"id": "tower_03", "name": "needle", "crown": "spire", "setbacks": [{"at": 0.80, "inset_m": 5.0}], "tint": [110, 140, 200], "reflectivity": [0.7, 0.9], "mullion_spacing_m": [1.0, 1.4], "panel_w": 1.2,
     "spandrel_ratio": 0.12, "emissive": {"pattern": "top_heavy", "density": 0.55}, "rooftop_lights": 8, "aspect": [1.0, 1.1], "height_range": [180, 300]},
    {"id": "tower_04", "name": "halo_ring", "crown": "halo", "setbacks": [{"at": 0.92, "inset_m": 2.0}], "tint": [60, 110, 150], "reflectivity": [0.8, 0.95], "mullion_spacing_m": [1.4, 1.9],
     "panel_w": 1.6, "spandrel_ratio": 0.15, "emissive": {"pattern": "checker", "density": 0.3}, "rooftop_lights": 12, "aspect": [1.0, 1.3], "height_range": [150, 260]},
    {"id": "tower_05", "name": "antenna_cluster", "crown": "antenna_cluster", "setbacks": [], "tint": [100, 125, 150], "reflectivity": [0.55, 0.75], "mullion_spacing_m": [1.6, 2.2], "panel_w": 2.0,
     "spandrel_ratio": 0.22, "emissive": {"pattern": "random", "density": 0.45}, "rooftop_lights": 9, "aspect": [1.0, 1.5], "height_range": [120, 200]},
    {"id": "tower_06", "name": "notched_corner", "crown": "flat", "setbacks": [{"at": 0.62, "inset_m": 9.0, "side": "corner"}], "tint": [85, 160, 175], "reflectivity": [0.65, 0.85],
     "mullion_spacing_m": [1.3, 1.7], "panel_w": 1.5, "spandrel_ratio": 0.17, "emissive": {"pattern": "bands", "density": 0.4}, "rooftop_lights": 5, "aspect": [1.0, 1.3], "height_range": [140, 250]},
    {"id": "tower_07", "name": "tapered", "crown": "stepped", "setbacks": [{"at": 0.25, "inset_m": 2.0}, {"at": 0.45, "inset_m": 2.0}, {"at": 0.65, "inset_m": 2.0}, {"at": 0.85, "inset_m": 2.0}],
     "tint": [130, 150, 185], "reflectivity": [0.6, 0.8], "mullion_spacing_m": [1.5, 2.0], "panel_w": 1.7, "spandrel_ratio": 0.18, "emissive": {"pattern": "top_heavy", "density": 0.4},
     "rooftop_lights": 4, "aspect": [1.0, 1.2], "height_range": [160, 280]},
    {"id": "tower_08", "name": "gold_curtain", "crown": "flat", "setbacks": [], "tint": [190, 160, 100], "reflectivity": [0.6, 0.8], "mullion_spacing_m": [1.8, 2.4], "panel_w": 1.8,
     "spandrel_ratio": 0.3, "emissive": {"pattern": "columns", "density": 0.5}, "rooftop_lights": 4, "aspect": [1.0, 1.5], "height_range": [120, 210]},
    {"id": "tower_09", "name": "mono_black", "crown": "halo", "setbacks": [], "tint": [30, 40, 55], "reflectivity": [0.9, 0.98], "mullion_spacing_m": [1.0, 1.3], "panel_w": 1.1,
     "spandrel_ratio": 0.1, "emissive": {"pattern": "bands", "density": 0.25}, "rooftop_lights": 10, "aspect": [1.0, 1.2], "height_range": [170, 300]},
    {"id": "tower_10", "name": "pagoda_crown", "crown": "stepped", "setbacks": [{"at": 0.84, "inset_m": 4.0}, {"at": 0.91, "inset_m": 4.0}, {"at": 0.96, "inset_m": 3.0}], "tint": [140, 90, 120],
     "reflectivity": [0.6, 0.8], "mullion_spacing_m": [1.4, 1.9], "panel_w": 1.6, "spandrel_ratio": 0.2, "emissive": {"pattern": "random", "density": 0.5}, "rooftop_lights": 7, "aspect": [1.0, 1.3],
     "height_range": [130, 230]},
    {"id": "tower_11", "name": "sail", "crown": "slanted", "setbacks": [{"at": 0.5, "inset_m": 3.0, "side": "back"}], "tint": [95, 170, 200], "reflectivity": [0.7, 0.9], "mullion_spacing_m": [1.2, 1.6],
     "panel_w": 1.4, "spandrel_ratio": 0.15, "emissive": {"pattern": "checker", "density": 0.35}, "rooftop_lights": 6, "aspect": [1.2, 1.8], "height_range": [150, 270]},
]

FRACTURE_PATTERN_IDS = ["voronoi_08", "voronoi_12", "voronoi_16", "voronoi_24", "voronoi_32_relaxed", "voronoi_40_raw", "radial_center", "radial_offset", "radial_low", "radial_wide",
                        "layers_3", "layers_4", "layers_5", "layers_6_fine", "diagonal_20_shear", "diagonal_35", "diagonal_50", "diagonal_60_fine", "columns_vertical", "beams_horizontal"]

# material, patterns (one is picked per building), debris mix (chunks, gravel, glass_shards, dust; sums to 1), dust colour
DESTRUCTION = {
    "glass_tower": ("glass", ["voronoi_32_relaxed", "radial_wide", "layers_6_fine", "diagonal_60_fine"], (0.10, 0.05, 0.65, 0.20), (190, 205, 215)),
    "office_tower": ("mixed", ["layers_5", "layers_4", "voronoi_24"], (0.30, 0.15, 0.30, 0.25), (165, 165, 170)),
    "apartment_tower": ("concrete", ["voronoi_24", "layers_4", "columns_vertical"], (0.45, 0.25, 0.10, 0.20), (150, 145, 138)),
    "low_shop": ("concrete", ["voronoi_12", "radial_offset", "beams_horizontal"], (0.35, 0.30, 0.05, 0.30), (160, 150, 135)),
    "shopfront_row": ("concrete", ["voronoi_12", "voronoi_16", "radial_center"], (0.35, 0.30, 0.05, 0.30), (160, 150, 135)),
    "parking": ("concrete", ["layers_3", "layers_4"], (0.50, 0.25, 0.02, 0.23), (140, 140, 142)),
    "temple": ("mixed", ["voronoi_08", "radial_center"], (0.45, 0.20, 0.0, 0.35), (170, 140, 110)),
    "station": ("concrete", ["layers_3", "diagonal_35"], (0.45, 0.25, 0.05, 0.25), (150, 120, 110)),
    "landmark": ("mixed", ["diagonal_50", "layers_5", "radial_wide"], (0.35, 0.20, 0.15, 0.30), (170, 170, 175)),
    "crane": ("mixed", ["diagonal_35", "beams_horizontal"], (0.60, 0.10, 0.0, 0.30), (120, 120, 125)),
    "overpass": ("concrete", ["layers_3", "beams_horizontal"], (0.55, 0.25, 0.0, 0.20), (130, 130, 132)),
}


def destruction_for(btype, rng):
    mat, pats, mix, dust = DESTRUCTION.get(btype, DESTRUCTION["landmark"])
    return {"material": mat, "fracture_pattern": pats[rng.below(len(pats))],
            "debris_mix": {"chunks": mix[0], "gravel": mix[1], "glass_shards": mix[2], "dust": mix[3]}, "dust_color": list(dust)}


# ---- invented glyph sets (identifiers only; the renderer maps them to hand-drawn stroke shapes, they spell nothing) ----------------------------
def make_glyph_sets():
    r = Rng(20261004)
    sets = {}
    for name, count, strokes in (("kana_like", 48, (2, 4)), ("kanji_like", 64, (5, 14)), ("pictograms", 40, (1, 6)), ("digits_like", 10, (2, 5))):
        glyphs = []
        for k in range(count):
            glyphs.append({"id": "g_%s_%02d" % (name.split("_")[0], k), "strokes": r.randint(strokes[0], strokes[1]), "width_units": r.choice([1.0, 1.0, 1.0, 1.2, 0.8]),
                           "seed": r.next_u32() & 0xFFFF})
        sets[name] = glyphs
    pict_names = ["bowl", "cherry", "sword", "heart", "star", "moon", "fish", "cat", "bolt", "drop", "leaf", "gem", "cup", "key", "eye", "gear", "wave", "flame", "cloud", "arrow",
                  "gate", "lantern", "fan", "crane_bird", "koi", "mask", "drum", "dango", "sun", "snow", "clover", "note", "crown", "skull", "bell", "ring", "dice", "cube", "orb", "spiral"]
    for g, nm in zip(sets["pictograms"], pict_names):
        g["pictogram"] = nm
    return {"version": 1, "note": "Invented pseudo-Japanese glyph identifiers and pictograms. They are not real characters, words or brands: the material draws a stroke shape from `seed`.",
            "sets": sets}
