#!/usr/bin/env python3
"""Writes schema.json (JSON Schema draft-07) – the machine-readable contract for district.json."""
import json
import os

N = {"type": "number"}
INT = {"type": "integer"}
STR = {"type": "string"}
ID = {"type": "string", "pattern": "^[a-z0-9_]+$"}
P2 = {"type": "array", "items": N, "minItems": 2, "maxItems": 2}
P3 = {"type": "array", "items": N, "minItems": 3, "maxItems": 3}
POLY = {"type": "array", "items": {"$ref": "#/definitions/point2"}, "minItems": 3}
LINE = {"type": "array", "items": {"$ref": "#/definitions/point2"}, "minItems": 2}


def obj(props, required=None, additional=False):
    return {"type": "object", "properties": props, "required": required if required is not None else list(props), "additionalProperties": additional}


defs = {
    "point2": P2, "point3": P3, "polygon": POLY, "polyline": LINE, "id": ID,
    "column": obj({"id": {"$ref": "#/definitions/id"}, "pos": {"$ref": "#/definitions/point3"}, "height": {"type": "number", "minimum": 0},
                   "strength": {"type": "number", "minimum": 0}, "tier": INT, "role": {"enum": ["regular", "weak"]},
                   "holds": {"type": "array", "items": INT, "minItems": 1}},
                  ["id", "pos", "height", "strength", "tier", "role"]),
    "floor": obj({"id": {"$ref": "#/definitions/id"}, "z": N, "supports": {"type": "array", "items": {"$ref": "#/definitions/id"}, "minItems": 3},
                  "mass": {"type": "number", "minimum": 0}, "tier": INT}),
    "tier": obj({"index": INT, "z": N, "height": {"type": "number", "minimum": 0}, "mass": {"type": "number", "minimum": 0}, "com": P2}),
    "weak_line": obj({"id": {"$ref": "#/definitions/id"}, "columns": {"type": "array", "items": {"$ref": "#/definitions/id"}, "minItems": 2},
                      "tier": INT, "collapse_dir": P2, "hint": STR}),
    "fracture_stage": obj({"stage": {"type": "integer", "minimum": 1, "maximum": 3}, "floors": {"type": "array", "items": {"$ref": "#/definitions/id"}},
                           "sections": {"type": "array", "items": INT}}),
}
defs["structure"] = obj({"stacked": {"type": "boolean"},
                         "columns": {"type": "array", "items": {"$ref": "#/definitions/column"}, "minItems": 3},
                         "floors": {"type": "array", "items": {"$ref": "#/definitions/floor"}, "minItems": 1},
                         "tiers": {"type": "array", "items": {"$ref": "#/definitions/tier"}, "minItems": 1},
                         "weak_lines": {"type": "array", "items": {"$ref": "#/definitions/weak_line"}, "minItems": 1},
                         "fracture_stages": {"type": "array", "items": {"$ref": "#/definitions/fracture_stage"}, "minItems": 3, "maxItems": 3}})
defs["road"] = obj({"id": {"$ref": "#/definitions/id"}, "kind": {"enum": ["promenade", "avenue", "street", "alley"]}, "name": STR,
                    "width": {"type": "number", "minimum": 40, "maximum": 90}, "points": {"$ref": "#/definitions/polyline"}, "dead_end": {"type": "boolean"}})
defs["block"] = obj({"id": {"$ref": "#/definitions/id"}, "kind": {"enum": ["block", "site", "plaza"]},
                     "district": {"enum": ["downtown", "residential", "industrial", "mixed", "civic"]}, "col": INT, "row": INT,
                     "polygon": {"$ref": "#/definitions/polygon"}, "name": STR, "sub_block": {"type": "boolean"}}, ["id", "kind", "district", "col", "row", "polygon"])
defs["building"] = obj({
    "id": {"$ref": "#/definitions/id"}, "type": {"enum": ["generic", "hero"]},
    "hero_kind": {"enum": ["glass_tower", "stadium", "residential_complex", "overpass", "port_crane", "power_station"]},
    "name": STR, "block_id": {"type": ["string", "null"]},
    "district": {"enum": ["downtown", "residential", "industrial", "mixed", "civic"]},
    "building_type": {"enum": ["office", "residential", "industrial", "parking", "stadium", "overpass", "crane"]},
    "facade_style": STR, "footprint": {"$ref": "#/definitions/polygon"},
    "height": {"type": "number", "minimum": 8, "maximum": 220}, "floors": {"type": "integer", "minimum": 1},
    "base_z": N, "yaw_deg": N, "deck_z": N, "length": N, "width": N, "hazard": STR,
    "parts": {"type": "array", "items": {"type": "object"}},
    "structure": {"$ref": "#/definitions/structure"}},
    ["id", "type", "block_id", "district", "building_type", "facade_style", "footprint", "height", "floors", "base_z", "yaw_deg"])
defs["prop"] = obj({"id": {"$ref": "#/definitions/id"}, "kind": {"enum": ["car", "tree", "lamp", "bench"]}, "pos": {"$ref": "#/definitions/point3"},
                    "yaw_deg": N, "variant": STR}, ["id", "kind", "pos", "yaw_deg", "variant"])
defs["poi"] = obj({"id": {"$ref": "#/definitions/id"},
                   "kind": {"enum": ["spawn_player", "spawn_enemy", "spawn_duel_a", "spawn_duel_b", "camera"]}, "name": STR,
                   "pos": {"$ref": "#/definitions/point3"}, "yaw_deg": N, "look_at": {"$ref": "#/definitions/point3"}, "fov_deg": N},
                  ["id", "kind", "name", "pos"])
defs["hazard"] = obj({"id": {"$ref": "#/definitions/id"}, "kind": {"enum": ["electrical", "flood", "metro_collapse"]},
                      "polygon": {"type": "array", "items": {"$ref": "#/definitions/point2"}, "minItems": 2}, "effect": STR, "source": STR},
                     ["id", "kind", "polygon", "effect"])

terrain = obj({"heightmap": STR, "format": {"const": "r16_little_endian"}, "resolution": {"const": 1009}, "row_order": {"const": "y_ascending"},
               "extent": obj({"x_min": N, "x_max": N, "y_min": N, "y_max": N}), "cell_size_m": N,
               "height_encoding": obj({"zero_value": INT, "units_per_meter": N}), "min_z": N, "max_z": N, "sea_level_z": N, "unreal_landscape_hint": STR})
bounds = obj({"units": STR, "axes": STR, "playable": obj({"x_min": N, "x_max": N, "y_min": N, "y_max": N}),
              "terrain": obj({"x_min": N, "x_max": N, "y_min": N, "y_max": N})})
water = obj({"level_z": N, "sea_floor_z": N, "shoreline": {"$ref": "#/definitions/polyline"}, "flood_zones": {"type": "array", "items": {"$ref": "#/definitions/id"}}})
port = obj({"quay": {"$ref": "#/definitions/polygon"}, "block_id": {"$ref": "#/definitions/id"},
            "containers": {"type": "array", "items": obj({"id": {"$ref": "#/definitions/id"}, "pos": P2, "yaw_deg": N, "levels": {"type": "integer", "minimum": 1, "maximum": 6},
                                                         "variant": INT})},
            "cranes": {"type": "array", "items": {"$ref": "#/definitions/id"}}})
substation = obj({"id": {"$ref": "#/definitions/id"}, "yard": {"$ref": "#/definitions/polygon"}, "power_station_id": {"$ref": "#/definitions/id"},
                  "transformers": {"type": "array", "items": obj({"pos": P2})}})
metro = obj({"id": {"$ref": "#/definitions/id"}, "width": N, "floor_z": N, "ceiling_thickness": N, "points": {"$ref": "#/definitions/polyline"},
             "weak_segments": {"type": "array", "minItems": 1, "items": obj({"id": {"$ref": "#/definitions/id"}, "from": P2, "to": P2, "ceiling_thickness": N,
                                                                           "normal_thickness": N, "hint": STR})},
             "stations": {"type": "array", "items": obj({"id": {"$ref": "#/definitions/id"}, "entrance": P2, "platform_center": P2})}})
infra = obj({"port": port, "substation": substation, "metro": metro, "overpass_id": {"$ref": "#/definitions/id"},
             "guardrails": {"type": "array", "items": obj({"id": {"$ref": "#/definitions/id"}, "points": {"type": "array", "items": P3, "minItems": 2}, "height": N})}})

schema = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "IMPACT VECTOR district.json",
    "description": "Contract between worldgen/ (generator) and the Unreal project. Units: metres; x right, y from the sea toward the city, z up. schema_version 1.",
    "type": "object",
    "properties": {
        "schema_version": {"const": 1}, "seed": INT, "bounds": bounds, "terrain": terrain, "water": water,
        "roads": {"type": "array", "items": {"$ref": "#/definitions/road"}, "minItems": 1},
        "blocks": {"type": "array", "items": {"$ref": "#/definitions/block"}, "minItems": 1},
        "buildings": {"type": "array", "items": {"$ref": "#/definitions/building"}, "minItems": 6},
        "infrastructure": infra,
        "props": {"type": "array", "items": {"$ref": "#/definitions/prop"}},
        "pois": {"type": "array", "items": {"$ref": "#/definitions/poi"}, "minItems": 5},
        "hazards": {"type": "array", "items": {"$ref": "#/definitions/hazard"}, "minItems": 1},
    },
    "required": ["schema_version", "seed", "bounds", "terrain", "water", "roads", "blocks", "buildings", "infrastructure", "props", "pois", "hazards"],
    "additionalProperties": False,
    "definitions": defs,
}

# ---------------------------------------------------------------------------------------------------------------------------
# schema_version 2 (Tokyo style, TASK-015): a superset of v1 in structure; new optional fields and wider enums. schema.json (v1) is left untouched.
# ---------------------------------------------------------------------------------------------------------------------------
def make_v2():
    import copy
    d = copy.deepcopy(defs)
    d["road"]["properties"]["kind"] = {"enum": ["promenade", "avenue", "street", "alley", "embankment"]}
    d["road"]["properties"]["width"] = {"type": "number", "minimum": 24, "maximum": 90}
    d["building"]["properties"]["hero_kind"] = {"enum": ["glass_tower", "tower_lattice", "twin_tower_hall", "brick_station", "sphere_building", "temple_gate", "scramble_crossing",
                                                          "port_crane", "expressway", "suspension_bridge", "stadium", "residential_complex", "overpass", "power_station"]}
    d["building"]["properties"]["building_type"] = {"enum": ["office", "residential", "industrial", "parking", "stadium", "overpass", "crane", "apartment_tower", "office_tower",
                                                              "low_shop", "temple", "station", "landmark"]}
    d["building"]["properties"]["height"] = {"type": "number", "minimum": 8, "maximum": 340}
    d["prop"]["properties"]["kind"] = {"enum": ["car", "tree", "lamp", "bench", "vending", "lantern", "utility_pole", "sign", "traffic_light", "bus_stop", "cone", "bicycle",
                                                "scooter", "sakura"]}
    d["prop"]["properties"].update({"size": P2, "emissive": {"type": "boolean"}, "building_id": STR})
    d["poi"]["properties"]["kind"] = {"enum": ["spawn_player", "spawn_enemy", "spawn_duel_a", "spawn_duel_b", "duel_point", "camera"]}
    d["hazard"]["properties"]["kind"] = {"enum": ["electrical", "flood", "metro_collapse", "expressway_collapse", "canal_flood"]}
    d["light"] = obj({"id": {"$ref": "#/definitions/id"}, "kind": {"enum": ["street", "neon_sign", "window_block", "billboard"]}, "pos": {"$ref": "#/definitions/point3"},
                      "color": {"type": "array", "items": {"type": "integer", "minimum": 0, "maximum": 255}, "minItems": 3, "maxItems": 3}, "intensity_hint": {"type": "number", "minimum": 0}})
    d["wire"] = obj({"id": {"$ref": "#/definitions/id"}, "kind": STR, "from": {"$ref": "#/definitions/id"}, "to": {"$ref": "#/definitions/id"},
                     "points": {"type": "array", "items": P3, "minItems": 2}})
    canal = obj({"id": {"$ref": "#/definitions/id"}, "centre": {"$ref": "#/definitions/polyline"}, "south_bank": {"$ref": "#/definitions/polyline"},
                 "north_bank": {"$ref": "#/definitions/polyline"}, "depth": N, "width_min": N, "width_max": N})
    bridge = obj({"id": {"$ref": "#/definitions/id"}, "road_id": {"$ref": "#/definitions/id"}, "name": STR, "width": N, "deck_z": N, "from": P2, "to": P2, "length": N})
    infra2 = obj({"canal": canal, "bridges": {"type": "array", "items": bridge, "minItems": 2}, "expressway_id": {"$ref": "#/definitions/id"},
                  "suspension_bridge_id": {"$ref": "#/definitions/id"},
                  "port": obj({k: v for k, v in port["properties"].items() if k != "block_id"}),
                  "guardrails": {"type": "array", "items": obj({"id": {"$ref": "#/definitions/id"}, "points": {"type": "array", "items": P3, "minItems": 2}, "height": N})},
                  "wires": {"type": "array", "items": {"$ref": "#/definitions/wire"}}})
    s2 = copy.deepcopy(schema)
    s2["description"] = ("Contract between worldgen/ (generator) and the Unreal project. Units: metres; x right, y from the sea toward the city, z up. "
                         "schema_version 2 = Tokyo style (TASK-015).")
    s2["properties"]["schema_version"] = {"const": 2}
    s2["properties"]["style"] = {"enum": ["tokyo"]}
    s2["properties"]["infrastructure"] = infra2
    s2["properties"]["lights"] = {"type": "array", "items": {"$ref": "#/definitions/light"}, "minItems": 600}
    s2["properties"]["buildings"]["minItems"] = 100
    s2["required"] = s2["required"] + ["style", "lights"]
    s2["definitions"] = d
    return s2


def make_v3():
    """schema_version 3 (cyberpunk layer, TASK-019): a superset of v2."""
    import copy
    s3 = copy.deepcopy(make_v2())
    d = s3["definitions"]
    s3["description"] = ("Contract between worldgen/ (generator) and the Unreal project. Units: metres; x right, y from the sea toward the city, z up. "
                         "schema_version 3 = cyberpunk layer (TASK-019): arena config, glass towers, shop rows, mega signs, 1500+ lights, destruction, fog maps.")
    d["road"]["properties"]["kind"] = {"enum": ["promenade", "avenue", "street", "alley", "embankment", "pedestrian"]}
    d["road"]["properties"]["width"] = {"type": "number", "minimum": 8, "maximum": 90}
    b = d["building"]["properties"]
    b["building_type"] = {"enum": b["building_type"]["enum"] + ["glass_tower", "shopfront_row"]}
    b["hero_kind"] = b["hero_kind"]
    b["facade"] = {"type": "object"}
    b["destruction"] = obj({"material": {"enum": ["glass", "concrete", "mixed"]}, "fracture_pattern": STR,
                            "debris_mix": obj({"chunks": N, "gravel": N, "glass_shards": N, "dust": N}),
                            "dust_color": {"type": "array", "items": {"type": "integer", "minimum": 0, "maximum": 255}, "minItems": 3, "maxItems": 3}})
    d["prop"]["properties"]["kind"] = {"enum": d["prop"]["properties"]["kind"]["enum"] + ["torii_neon", "banner_flag", "steam_vent", "puddle", "water_tank", "rooftop_antenna"]}
    d["prop"]["properties"].update({"width_m": N, "height_m": N})
    d["light"] = obj({
        "id": {"$ref": "#/definitions/id"},
        "kind": {"enum": ["street", "neon_sign", "neon_tube", "window_block", "billboard", "beacon", "under_tower", "plaza"]},
        "type": {"enum": ["point", "rect", "spot"]}, "pos": {"$ref": "#/definitions/point3"},
        "color": {"type": "array", "items": {"type": "integer", "minimum": 0, "maximum": 255}, "minItems": 3, "maxItems": 3},
        "intensity_hint": {"type": "number", "minimum": 0}, "radius": {"type": "number", "minimum": 0}, "flicker": {"type": "number", "minimum": 0, "maximum": 1},
        "flicker_hz": N, "shadow": {"type": "boolean"}, "priority": {"type": "integer", "minimum": 1, "maximum": 5},
        "hue": {"enum": ["cyan", "magenta", "amber", "red", "tungsten"]}, "block_id": {"type": ["string", "null"]}, "size": P2, "dir": P3},
        ["id", "kind", "type", "pos", "color", "intensity_hint", "radius", "flicker", "shadow", "priority", "hue"])
    d["mega_sign"] = obj({
        "id": {"$ref": "#/definitions/id"}, "host": {"$ref": "#/definitions/id"}, "block_id": STR,
        "style": {"enum": ["vertical_banner", "billboard_screen", "neon_tube_kanji", "holo_ad", "logo_sphere"]}, "size_m": P2, "pos": {"$ref": "#/definitions/point3"},
        "yaw_deg": N, "normal": P2, "offset_m": N, "palette": {"type": "array", "items": {"type": "array", "items": INT, "minItems": 3, "maxItems": 3}, "minItems": 1},
        "palette_names": {"type": "array", "items": STR}, "emissive_intensity": N,
        "animation": obj({"kind": {"enum": ["flicker", "scroll", "pulse", "cycle"]}, "speed": N, "phase": N}),
        "glyph_set": STR, "text_glyphs": {"type": "array", "items": STR, "minItems": 1}, "glyph_layout": STR, "monster": {"type": "boolean"}})
    d["crowd"] = obj({"id": {"$ref": "#/definitions/id"}, "pos": {"$ref": "#/definitions/point3"}, "radius_m": N, "density_per_100m2": N, "speed_mps": N, "dir": P2})
    d["wire"] = obj({"id": {"$ref": "#/definitions/id"}, "kind": STR, "from": STR, "to": STR, "points": {"type": "array", "items": P3, "minItems": 2}})
    plaza = obj({"id": STR, "center": P2, "size": N, "polygon": {"$ref": "#/definitions/polygon"}})
    s3["properties"]["schema_version"] = {"const": 3}
    s3["properties"]["style"] = {"enum": ["cyber"]}
    s3["properties"]["arena"] = obj({"name": {"enum": ["takeshita", "shibuya_scramble", "nakamise"]}, "plaza": plaza, "free_zone_m": N,
                                     "street": {"type": ["object", "null"]}})
    s3["properties"]["lights"] = {"type": "array", "items": {"$ref": "#/definitions/light"}, "minItems": 1500}
    s3["properties"]["mega_signs"] = {"type": "array", "items": {"$ref": "#/definitions/mega_sign"}, "minItems": 80}
    s3["properties"]["crowd_spawners"] = {"type": "array", "items": {"$ref": "#/definitions/crowd"}, "minItems": 1}
    s3["properties"]["light_report"] = {"type": "object"}
    s3["properties"]["fog_map"] = {"type": "object"}
    s3["properties"]["resources"] = {"type": "object"}
    infra = s3["properties"]["infrastructure"]
    infra["properties"]["wires"] = {"type": "array", "items": {"$ref": "#/definitions/wire"}}
    s3["required"] = [r for r in s3["required"] if r != "style"] + ["style", "arena", "mega_signs", "crowd_spawners", "fog_map", "light_report"]
    s3["required"] = sorted(set(s3["required"]), key=s3["required"].index)
    return s3


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(here, "schema.json"), "w", encoding="utf-8") as f:
        json.dump(schema, f, indent=2, ensure_ascii=False)
        f.write("\n")
    with open(os.path.join(here, "schema_v2.json"), "w", encoding="utf-8") as f:
        json.dump(make_v2(), f, indent=2, ensure_ascii=False)
        f.write("\n")
    with open(os.path.join(here, "schema_v3.json"), "w", encoding="utf-8") as f:
        json.dump(make_v3(), f, indent=2, ensure_ascii=False)
        f.write("\n")
    print("schema.json (v1), schema_v2.json and schema_v3.json written")
