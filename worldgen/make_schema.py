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

if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(here, "schema.json"), "w", encoding="utf-8") as f:
        json.dump(schema, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print("schema.json written")
