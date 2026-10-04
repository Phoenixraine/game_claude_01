"""Tiny JSON-schema subset validator (stdlib only): type, enum, required, properties, additionalProperties, items, minItems, maxItems, minimum, maximum, $ref (#/$defs/..), oneOf, const, pattern."""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TYPES = {"object": dict, "array": list, "string": str, "boolean": bool, "null": type(None)}


def _is(v, t):
    if t == "number":
        return isinstance(v, (int, float)) and not isinstance(v, bool)
    if t == "integer":
        return isinstance(v, int) and not isinstance(v, bool)
    return isinstance(v, TYPES[t])


def validate(inst, schema, root=None, path="$"):
    """Returns a list of error strings (empty = valid)."""
    root = root or schema
    errs = []
    if "$ref" in schema:
        node = root
        for part in schema["$ref"].lstrip("#/").split("/"):
            node = node[part]
        return validate(inst, node, root, path)
    if "oneOf" in schema:
        results = [validate(inst, s, root, path) for s in schema["oneOf"]]
        if sum(1 for r in results if not r) != 1:
            errs.append("%s: does not match exactly one of oneOf" % path)
        return errs
    t = schema.get("type")
    if t:
        ts = t if isinstance(t, list) else [t]
        if not any(_is(inst, x) for x in ts):
            return ["%s: expected %s, got %s" % (path, t, type(inst).__name__)]
    if "const" in schema and inst != schema["const"]:
        errs.append("%s: expected %r" % (path, schema["const"]))
    if "enum" in schema and inst not in schema["enum"]:
        errs.append("%s: %r not in enum" % (path, inst))
    if "pattern" in schema and isinstance(inst, str) and not re.search(schema["pattern"], inst):
        errs.append("%s: %r does not match %s" % (path, inst, schema["pattern"]))
    if isinstance(inst, (int, float)) and not isinstance(inst, bool):
        if "minimum" in schema and inst < schema["minimum"]:
            errs.append("%s: %r < minimum %r" % (path, inst, schema["minimum"]))
        if "maximum" in schema and inst > schema["maximum"]:
            errs.append("%s: %r > maximum %r" % (path, inst, schema["maximum"]))
        if inst != inst or inst in (float("inf"), float("-inf")):
            errs.append("%s: not finite" % path)
    if isinstance(inst, dict):
        for k in schema.get("required", []):
            if k not in inst:
                errs.append("%s: missing '%s'" % (path, k))
        props = schema.get("properties", {})
        ap = schema.get("additionalProperties", True)
        for k, v in inst.items():
            if k in props:
                errs += validate(v, props[k], root, "%s.%s" % (path, k))
            elif ap is False:
                errs.append("%s: unexpected '%s'" % (path, k))
            elif isinstance(ap, dict):
                errs += validate(v, ap, root, "%s.%s" % (path, k))
    if isinstance(inst, list):
        if "minItems" in schema and len(inst) < schema["minItems"]:
            errs.append("%s: fewer than %d items" % (path, schema["minItems"]))
        if "maxItems" in schema and len(inst) > schema["maxItems"]:
            errs.append("%s: more than %d items" % (path, schema["maxItems"]))
        if "items" in schema:
            for i, v in enumerate(inst):
                errs += validate(v, schema["items"], root, "%s[%d]" % (path, i))
    return errs


TABLES = ["identifiers", "shake_profiles", "cockpit_effects", "mech_chunks", "building_destruction", "warnings", "global_tuning", "coverage"]


def validate_table(name):
    with open(os.path.join(HERE, name + ".json"), encoding="utf-8") as f:
        inst = json.load(f)
    with open(os.path.join(HERE, "schema", name + ".schema.json"), encoding="utf-8") as f:
        sch = json.load(f)
    return validate(inst, sch)


if __name__ == "__main__":
    bad = 0
    for n in TABLES:
        e = validate_table(n)
        print("%-22s %s" % (n, "OK" if not e else "%d errors" % len(e)))
        for x in e[:10]:
            print("   ", x)
        bad += bool(e)
    sys.exit(1 if bad else 0)
