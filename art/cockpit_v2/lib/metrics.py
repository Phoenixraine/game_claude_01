"""Pure-python metrics and JSON documents of the model (no bpy): used by build_cockpit_v2.py and by the tests."""
import collections

from . import damage

MAX_PART_TRIS = 3000
MAX_TOTAL_TRIS = 400000


def kind_counts(model):
    c = collections.Counter(p.kind for p in model.parts)
    c.update("Empty:" + e.kind for e in model.empties)
    return dict(sorted(c.items()))


def triangles(model, include_hidden=True):
    per = {p.name: p.mb.tris() for p in model.parts}
    total = sum(n for p, n in zip(model.parts, per.values()) if include_hidden or p.visible)
    return per, total


def parts_doc(model):
    rows = []
    for p in model.parts:
        bb = p.mb.bbox()
        rows.append({"name": p.name, "class": p.kind, "tris": p.mb.tris(), "default_visible": bool(p.visible), "bbox": [[round(float(x), 3) for x in b] for b in bb] if bb is not None else None,
                     "materials": list(p.mb.mats), "meta": p.meta})
    emp = [{"name": e.name, "class": e.kind, "pos": [round(float(x), 4) for x in e.pos], "dir": [round(float(x), 4) for x in e.dir], "meta": e.meta} for e in model.empties]
    return {"version": 1, "units": "metres, pilot eye at (0,0,0), view along -Y, Z up", "parts": rows, "empties": emp}


def metrics_doc(model, glass_pct=None):
    per, total = triangles(model)
    cc = kind_counts(model)
    return {
        "triangles_total": total, "triangles_visible_intact": triangles(model, False)[1], "triangles_max_part": max(per.values()), "limits": {"part": MAX_PART_TRIS, "total": MAX_TOTAL_TRIS},
        "counts": cc, "glass_share_percent": glass_pct, "glass_share_required": 70.0,
    }


def spec_doc(model, seed=7):
    return damage.make_spec(damage.pools_from_model(model), seed)
