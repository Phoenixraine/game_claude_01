"""A small JSON Schema (draft-07 subset) validator, standard library only.

Supports: type (single or list), enum, const, properties, required, additionalProperties (bool), items,
minItems, maxItems, minimum, maximum, pattern, $ref ("#/definitions/..."). Enough for worldgen/schema.json.
"""
import re


def _type_ok(value, t):
    if t == "object":
        return isinstance(value, dict)
    if t == "array":
        return isinstance(value, list)
    if t == "string":
        return isinstance(value, str)
    if t == "boolean":
        return isinstance(value, bool)
    if t == "null":
        return value is None
    if t == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if t == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    raise ValueError("unsupported type " + t)


def validate(instance, schema, root=None, path="$", errors=None, limit=50):
    """Returns a list of error strings (empty = valid)."""
    if errors is None:
        errors = []
    if root is None:
        root = schema
    if len(errors) >= limit:
        return errors
    if "$ref" in schema:
        ref = schema["$ref"]
        assert ref.startswith("#/"), ref
        node = root
        for part in ref[2:].split("/"):
            node = node[part]
        return validate(instance, node, root, path, errors, limit)
    if "const" in schema and instance != schema["const"]:
        errors.append("%s: expected const %r, got %r" % (path, schema["const"], instance))
        return errors
    if "enum" in schema and instance not in schema["enum"]:
        errors.append("%s: %r not in enum %r" % (path, instance, schema["enum"]))
        return errors
    if "type" in schema:
        ts = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
        if not any(_type_ok(instance, t) for t in ts):
            errors.append("%s: expected %s, got %s" % (path, "/".join(ts), type(instance).__name__))
            return errors
    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        if "minimum" in schema and instance < schema["minimum"]:
            errors.append("%s: %r < minimum %r" % (path, instance, schema["minimum"]))
        if "maximum" in schema and instance > schema["maximum"]:
            errors.append("%s: %r > maximum %r" % (path, instance, schema["maximum"]))
    if isinstance(instance, str) and "pattern" in schema and not re.search(schema["pattern"], instance):
        errors.append("%s: %r does not match %r" % (path, instance, schema["pattern"]))
    if isinstance(instance, list):
        if "minItems" in schema and len(instance) < schema["minItems"]:
            errors.append("%s: %d items < minItems %d" % (path, len(instance), schema["minItems"]))
        if "maxItems" in schema and len(instance) > schema["maxItems"]:
            errors.append("%s: %d items > maxItems %d" % (path, len(instance), schema["maxItems"]))
        if "items" in schema:
            for i, item in enumerate(instance):
                validate(item, schema["items"], root, "%s[%d]" % (path, i), errors, limit)
                if len(errors) >= limit:
                    break
    if isinstance(instance, dict):
        props = schema.get("properties", {})
        for r in schema.get("required", []):
            if r not in instance:
                errors.append("%s: missing required property %r" % (path, r))
        for k, v in instance.items():
            if k in props:
                validate(v, props[k], root, "%s.%s" % (path, k), errors, limit)
            elif schema.get("additionalProperties", True) is False:
                errors.append("%s: unexpected property %r" % (path, k))
    return errors
