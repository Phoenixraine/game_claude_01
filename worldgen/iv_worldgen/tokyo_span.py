"""Elevated roads and bridges along a polyline (TASK-015): the span model of v1 (`structure.build_span_structure`) generalised from one straight
segment to a polyline. Spans are independent tiers; every pier carries three columns (v = -0.5w, -0.15w, +0.5w) and holds the two neighbouring spans;
the weak line is the +v edge column of three consecutive piers (the deck between them tips sideways)."""
import math

from . import structure as S


def sample_polyline(pts, spacing):
    """Points (x, y, ux, uy) every `spacing` metres of arc length, both ends included."""
    seg = []
    total = 0.0
    for i in range(len(pts) - 1):
        l = math.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1])
        seg.append((total, l))
        total += l
    n = max(2, int(round(total / spacing)))
    out = []
    for k in range(n + 1):
        s = total * k / n
        for i, (s0, l) in enumerate(seg):
            if s <= s0 + l + 1e-9 or i == len(seg) - 1:
                t = (s - s0) / l if l > 0 else 0.0
                x = pts[i][0] + (pts[i + 1][0] - pts[i][0]) * t
                y = pts[i][1] + (pts[i + 1][1] - pts[i][1]) * t
                ux, uy = (pts[i + 1][0] - pts[i][0]) / l, (pts[i + 1][1] - pts[i][1]) / l
                out.append((x, y, ux, uy))
                break
    # smooth the tangent a little so the piers of a bend are not twisted
    return out, total


def deck_polygon(samples, width):
    left, right = [], []
    for x, y, ux, uy in samples:
        vx, vy = -uy, ux
        left.append((x + vx * width / 2.0, y + vy * width / 2.0))
        right.append((x - vx * width / 2.0, y - vy * width / 2.0))
    return left + right[::-1]


def build_polyline_span_structure(prefix, samples, base_fn, deck_z, width, weak_pier):
    """samples: output of sample_polyline (n piers). base_fn(x, y) -> ground z at the pier. Returns (structure, builder)."""
    b = S.Builder(prefix, stacked=False)
    n_piers = len(samples)
    n_spans = n_piers - 1
    pier_ids = []
    span_len = []
    for k in range(n_spans):
        span_len.append(math.hypot(samples[k + 1][0] - samples[k][0], samples[k + 1][1] - samples[k][1]))
    for k, (x, y, ux, uy) in enumerate(samples):
        vx, vy = -uy, ux
        ids = []
        holds = [t for t in (k - 1, k) if 0 <= t < n_spans]
        ref_mass = max(span_len[t] for t in holds) * width * 0.9 * 2.2
        for vv in (-0.5 * width, -0.15 * width, 0.5 * width):
            px, py = x + vx * vv, y + vy * vv
            base = base_fn(px, py)
            cid = b.add_col((px, py, base), deck_z - base, holds[0], 1.8 * ref_mass / 6.0, "weak" if (vv > 0 and weak_pier <= k <= weak_pier + 2) else "regular")
            b.columns[-1]["holds"] = holds
            ids.append(cid)
        pier_ids.append(ids)
    for k in range(n_spans):
        mid = ((samples[k][0] + samples[k + 1][0]) / 2.0, (samples[k][1] + samples[k + 1][1]) / 2.0)
        mass = span_len[k] * width * 0.9 * 2.2
        b.tiers.append({"index": k, "z": round(deck_z, 2), "height": 1.5, "mass": round(mass, 2), "com": [round(mid[0], 2), round(mid[1], 2)]})
        b.add_floor(deck_z, k, mass, pier_ids[k] + pier_ids[k + 1])
    wcols = [c["id"] for c in b.columns if c["role"] == "weak"]
    mx, my = samples[weak_pier + 1][2], samples[weak_pier + 1][3]
    vx, vy = -my, mx
    b.weak_lines.append({"id": prefix + "_w1", "columns": wcols, "tier": weak_pier, "collapse_dir": [round(vx, 4), round(vy, 4)],
                         "hint": "edge columns of piers %d-%d; the deck between them tips sideways" % (weak_pier, weak_pier + 2)})
    order = [weak_pier, weak_pier + 1, weak_pier - 1, weak_pier + 2, weak_pier - 2, weak_pier + 3]
    order = [t for t in order if 0 <= t < n_spans]
    rest = [t for t in range(n_spans) if t not in order]
    chunks = [order[:2], order[2:4], order[4:] + rest]
    return b.finish(chunks), b
