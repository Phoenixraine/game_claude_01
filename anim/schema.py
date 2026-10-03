"""Tiny JSON-Schema subset validator (type, required, properties, items, minItems, maxItems, enum, minimum, maximum, additionalProperties)."""


def validate(obj, schema, path="$"):
    errs = []
    t = schema.get("type")
    py = {"object": dict, "array": list, "string": str, "number": (int, float), "integer": int, "boolean": bool}
    if t and not (isinstance(obj, py[t]) and not (t in ("number", "integer") and isinstance(obj, bool))):
        return ["%s: expected %s, got %s" % (path, t, type(obj).__name__)]
    if "enum" in schema and obj not in schema["enum"]:
        errs.append("%s: %r not in %s" % (path, obj, schema["enum"]))
    if t in ("number", "integer"):
        if "minimum" in schema and obj < schema["minimum"]:
            errs.append("%s: %s < minimum %s" % (path, obj, schema["minimum"]))
        if "maximum" in schema and obj > schema["maximum"]:
            errs.append("%s: %s > maximum %s" % (path, obj, schema["maximum"]))
    if t == "object":
        for k in schema.get("required", []):
            if k not in obj:
                errs.append("%s: missing %s" % (path, k))
        props = schema.get("properties", {})
        for k, v in obj.items():
            if k in props:
                errs += validate(v, props[k], "%s.%s" % (path, k))
            elif schema.get("additionalProperties") is False:
                errs.append("%s: unexpected key %s" % (path, k))
            elif isinstance(schema.get("additionalProperties"), dict):
                errs += validate(v, schema["additionalProperties"], "%s.%s" % (path, k))
    if t == "array":
        if "minItems" in schema and len(obj) < schema["minItems"]:
            errs.append("%s: fewer than %d items" % (path, schema["minItems"]))
        if "maxItems" in schema and len(obj) > schema["maxItems"]:
            errs.append("%s: more than %d items" % (path, schema["maxItems"]))
        if "items" in schema:
            for i, v in enumerate(obj[:200]):
                errs += validate(v, schema["items"], "%s[%d]" % (path, i))
    return errs


VEC3 = {"type": "array", "minItems": 3, "maxItems": 3, "items": {"type": "number"}}

POSES_SCHEMA = {
    "type": "object", "required": ["version", "convention", "bones", "limits_deg", "poses", "transitions"],
    "properties": {
        "version": {"type": "integer"}, "convention": {"type": "string"},
        "bones": {"type": "array", "items": {"type": "string"}},
        "limits_deg": {"type": "object", "additionalProperties": {"type": "object"}},
        "poses": {"type": "object", "additionalProperties": {
            "type": "object", "required": ["name", "group", "joints", "root_pos", "com", "feet"],
            "properties": {"name": {"type": "string"}, "group": {"type": "string"}, "joints": {"type": "object", "additionalProperties": VEC3},
                           "root_pos": VEC3, "com": VEC3,
                           "feet": {"type": "object", "required": ["l", "r"], "additionalProperties": {
                               "type": "object", "required": ["ankle", "heel", "toe", "ground"],
                               "properties": {"ankle": VEC3, "heel": VEC3, "toe": VEC3, "ground": {"type": "boolean"}}}}}}},
        "transitions": {"type": "object", "additionalProperties": {"type": "array", "items": {"type": "string"}}},
    },
}

LOCO_SCHEMA = {
    "type": "object", "required": ["version", "fps", "bone_order", "gaits", "clips"],
    "properties": {
        "version": {"type": "integer"}, "fps": {"type": "integer", "minimum": 1}, "bone_order": {"type": "array", "items": {"type": "string"}},
        "gaits": {"type": "object", "additionalProperties": {"type": "object", "required": ["step_length_m", "step_period_s", "speed_mps", "pelvis_height_m"]}},
        "clips": {"type": "array", "items": {"type": "object", "required": ["name", "fps", "gait", "duration_s", "frames", "plants"],
                  "properties": {"frames": {"type": "array", "minItems": 2, "items": {
                      "type": "object", "required": ["t", "root", "j", "contact", "ankle_l", "ankle_r"],
                      "properties": {"t": {"type": "number"}, "root": VEC3, "j": {"type": "array", "items": {"type": "number"}},
                                     "contact": {"type": "array", "items": {"type": "boolean"}, "minItems": 2, "maxItems": 2},
                                     "ankle_l": VEC3, "ankle_r": VEC3}}}}}},
    },
}

CURVES_SCHEMA = {
    "type": "object", "required": ["version", "easings", "swing_timing", "spring", "shake"],
    "properties": {"version": {"type": "integer"}, "easings": {"type": "object", "additionalProperties": {"type": "array", "items": {"type": "number"}}},
                   "swing_timing": {"type": "object"}, "spring": {"type": "object"}, "shake": {"type": "object"}},
}
