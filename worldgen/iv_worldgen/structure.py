"""Structural graph of a building (columns / floors / weak lines / fracture stages) and the simplified
statics model that validates it (pitch §17 "Обрушение здания", §18 "Разрушаемость").

Model. A structure is a stack of tiers (an overpass: a row of independent spans). Every tier rests on its
own columns. A tier is *stable* when
  (a) at least three non-collinear columns survive,
  (b) the centre of mass (COM) lies inside the convex hull of the surviving columns with a margin, and
  (c) no column is overloaded: the load of the stack above is shared equally between survivors and must
      not exceed the column's `strength` (capacity in tonnes).
When the lowest failing tier gives way, that tier and everything above it falls (stacked structures). The fall
direction is from the nearest point of the support hull towards the COM. The ground tier is reinforced, so no
single column removal can bring a whole building down.
The same numbers are in district.json, so the Unreal side can run the same check at runtime.
"""
import math

from .geom import centroid, convex_hull, dist_to_poly_edges, norm, point_in_poly, rot, area

FLOOR_H = 4.0              # metres per storey
MASS_PER_M2 = 0.9          # tonnes per m2 of slab (incl. contents)
HULL_MARGIN = 0.75         # COM must be at least this far inside the hull to stand (metres)
UPPER_FACTOR = 1.8         # capacity of an ordinary column = factor * (tier load / columns)
GROUND_FACTOR = 3.0        # reinforced lower floors (pitch §17)
WEAK_FACTOR = 2.4          # transfer columns of a weak line carry more


def _hull_margin(com, cols):
    """Signed distance of the COM inside the hull of `cols` (negative = outside, -1e9 = degenerate)."""
    pts = [(c["pos"][0], c["pos"][1]) for c in cols]
    hull = convex_hull(pts)
    if len(hull) < 3 or abs(area(hull)) < 1.0:
        return -1e9, hull
    d, _ = dist_to_poly_edges(com, hull)
    return (d if point_in_poly(com, hull) else -d), hull


def simulate(structure, removed):
    """Returns {collapsed_tiers, collapsed_mass_fraction, direction} for the removed column ids."""
    removed = set(removed)
    tiers = structure["tiers"]
    cols_by_tier = {}
    for c in structure["columns"]:
        for ti in c.get("holds", [c["tier"]]):     # overpass piers hold two spans
            cols_by_tier.setdefault(ti, []).append(c)
    stacked = structure.get("stacked", True)
    total_mass = sum(t["mass"] for t in tiers)
    failing = None
    direction = None
    for t in tiers:
        i = t["index"]
        alive = [c for c in cols_by_tier.get(i, []) if c["id"] not in removed]
        all_cols = cols_by_tier.get(i, [])
        above = sum(u["mass"] for u in tiers if u["index"] >= i) if stacked else t["mass"]
        com = tuple(t["com"])
        fail = False
        dirv = None
        if len(alive) < 3:
            fail = True
        else:
            margin, hull = _hull_margin(com, alive)
            if margin < HULL_MARGIN:
                fail = True
                if margin <= -1e8:
                    cx = sum(c["pos"][0] for c in alive) / len(alive)
                    cy = sum(c["pos"][1] for c in alive) / len(alive)
                    dirv = norm((com[0] - cx, com[1] - cy))
                else:
                    _, q = dist_to_poly_edges(com, hull)
                    dirv = norm((com[0] - q[0], com[1] - q[1]))
            else:
                load = above / len(alive)
                if any(c["strength"] < load for c in alive):
                    fail = True
        if fail:
            if dirv is None or dirv == (0.0, 0.0):
                rem = [c for c in all_cols if c["id"] in removed]
                if rem and alive:
                    ax = sum(c["pos"][0] for c in alive) / len(alive)
                    ay = sum(c["pos"][1] for c in alive) / len(alive)
                    rx = sum(c["pos"][0] for c in rem) / len(rem)
                    ry = sum(c["pos"][1] for c in rem) / len(rem)
                    dirv = norm((rx - ax, ry - ay))
                else:
                    dirv = (0.0, 0.0)
            if stacked:
                failing = i
                direction = dirv
                break
            # independent spans: accumulate
            failing = (failing or []) + [i]
            direction = (direction or (0.0, 0.0))
            direction = (direction[0] + dirv[0] * t["mass"], direction[1] + dirv[1] * t["mass"])
    if failing is None:
        return {"collapsed_tiers": [], "collapsed_mass_fraction": 0.0, "direction": None}
    if stacked:
        collapsed = [t["index"] for t in tiers if t["index"] >= failing]
    else:
        collapsed = failing
        direction = norm(direction)
    mass = sum(t["mass"] for t in tiers if t["index"] in collapsed)
    return {"collapsed_tiers": collapsed, "collapsed_mass_fraction": mass / total_mass, "direction": direction}


class Builder:
    """Accumulates columns / floors / tiers with stable ids."""

    def __init__(self, prefix, stacked=True):
        self.prefix = prefix
        self.columns = []
        self.floors = []
        self.tiers = []
        self.weak_lines = []
        self.stacked = stacked
        self._nc = 0
        self._nf = 0

    def add_col(self, pos, height, tier, strength, role="regular"):
        self._nc += 1
        cid = "%s_c%03d" % (self.prefix, self._nc)
        self.columns.append({"id": cid, "pos": [round(pos[0], 2), round(pos[1], 2), round(pos[2], 2)], "height": round(height, 2),
                             "strength": round(strength, 2), "tier": tier, "role": role})
        return cid

    def add_floor(self, z, tier, mass, supports):
        self._nf += 1
        fid = "%s_f%02d" % (self.prefix, self._nf)
        self.floors.append({"id": fid, "z": round(z, 2), "supports": list(supports), "mass": round(mass, 2), "tier": tier})
        return fid

    def finish(self, fracture_tiers):
        st = {"stacked": self.stacked, "columns": self.columns, "floors": self.floors, "tiers": self.tiers,
              "weak_lines": self.weak_lines}
        st["fracture_stages"] = self._stages(fracture_tiers)
        return st

    def _stages(self, fracture_tiers):
        """Three stages of progressive detachment, each a list of floor ids (stage 1 first)."""
        by_tier = {}
        for f in self.floors:
            by_tier.setdefault(f["tier"], []).append(f["id"])
        out = []
        if fracture_tiers and isinstance(fracture_tiers[0], list):
            seen = set()
            for k, c in enumerate(fracture_tiers):
                fl = [f for t in c for f in by_tier.get(t, []) if f not in seen]
                seen.update(fl)
                out.append({"stage": k + 1, "floors": fl, "sections": list(c)})
            return out
        tiers = list(fracture_tiers)
        if len(tiers) >= 3:
            chunks = [tiers[:1], tiers[1:-1], tiers[-1:]]
            seen = set()
            for k, c in enumerate(chunks):
                fl = [f for t in c for f in by_tier.get(t, []) if f not in seen]
                seen.update(fl)
                out.append({"stage": k + 1, "floors": fl, "sections": list(c)})
            return out
        # fewer than three tiers: split the floors (weak tier first, then upwards) into three parts
        ordered = [f for t in tiers for f in by_tier.get(t, [])]
        n = len(ordered)
        cuts = [0, max(1, n // 3), max(2, (2 * n) // 3), n]
        for k in range(3):
            out.append({"stage": k + 1, "floors": ordered[cuts[k]:cuts[k + 1]], "sections": tiers})
        return out


def tier_split(floors, n_tiers):
    """Floors per tier, ground tier at least 2 floors."""
    base = max(2, floors // n_tiers)
    out = [base] * n_tiers
    out[-1] = max(1, floors - base * (n_tiers - 1))
    return out


def build_rect_structure(prefix, center, frame_yaw, half_u, half_v, base_z, floors, rng, weak_tiers=None, inside=None, ring=False,
                         com=None, floor_area=None, n_tiers=None):
    """Tiered structure for a footprint that is (roughly) a rectangle of half extents (half_u, half_v) in a frame
    rotated by frame_yaw. +v of the frame is the collapse direction of the (first) weak line.

    weak_tiers: list of (tier_index, frame_yaw_offset) – extra weak lines may point to other sides.
    inside(u, v): optional predicate (local metres) used to drop columns that fall outside a non-rectangular footprint.
    ring: place regular columns on an ellipse instead of a grid (stadium).
    """
    if n_tiers is None:
        n_tiers = max(3, min(5, floors // 5 if floors >= 15 else 3))
    split = tier_split(floors, n_tiers)
    if weak_tiers is None:
        weak_tiers = [(n_tiers - 2, 0.0)]
    b = Builder(prefix)
    cx, cy = center
    a_u, a_v = half_u, half_v
    if floor_area is None:
        floor_area = 4.0 * a_u * a_v
    if com is None:
        com = center
    # tier masses
    z = base_z
    tier_defs = []
    for i, nf in enumerate(split):
        tier_defs.append({"index": i, "z0": z, "floors": nf, "height": nf * FLOOR_H, "mass": nf * floor_area * MASS_PER_M2})
        z += nf * FLOOR_H
    total = [sum(t["mass"] for t in tier_defs if t["index"] >= i) for i in range(n_tiers)]

    def world(u, v, yaw_off=0.0):
        p = rot((u, v), frame_yaw + yaw_off)
        return (cx + p[0], cy + p[1])

    nx = 5 if a_u >= 14 else 4
    ny = 4 if a_v >= 14 else 3
    weak_info = {}
    for ti, yoff in weak_tiers:
        weak_info[ti] = yoff

    for t in tier_defs:
        i = t["index"]
        h = t["height"]
        ids = []
        factor = GROUND_FACTOR if i == 0 else UPPER_FACTOR
        if i in weak_info:
            yoff = weak_info[i]
            # in the weak tier's own frame +v is the weak side; swap half extents when it is turned by 90 deg
            turned = abs((yoff / (math.pi / 2)) % 2 - 1) < 1e-6
            hu, hv = (a_v, a_u) if turned else (a_u, a_v)
            n_total = 0
            cols = []
            if ring:
                n_ring = 24
                ring_pts = []
                for k in range(n_ring):
                    th = 2 * math.pi * k / n_ring
                    ring_pts.append((math.cos(th) * (hu - 2.5), math.sin(th) * (hv - 2.5)))
                A = [p for p in ring_pts if p[1] <= -0.2 * hv]
                W = sorted([p for p in ring_pts if p[1] > 0.0], key=lambda p: -p[1])[:4]
                cols = [("A", p) for p in A] + [("W", p) for p in W]
            else:
                a_rows = [-hv + 2.5, -0.2 * hv]
                us = [(-hu + 2.5) + k * (2 * hu - 5.0) / (nx - 1) for k in range(nx)]
                for vv in a_rows:
                    for uu in us:
                        cols.append(("A", (uu, vv)))
                wn = 4
                for k in range(wn):
                    cols.append(("W", ((-hu + 2.5) + k * (2 * hu - 5.0) / (wn - 1), hv - 2.5)))
            if inside is not None:
                kept = []
                for role, (uu, vv) in cols:
                    wp = world(uu, vv, yoff)
                    if inside(wp):
                        kept.append((role, (uu, vv)))
                cols = kept
            n_total = len(cols)
            nominal = total[i] / max(1, n_total)
            for role, (uu, vv) in cols:
                wp = world(uu, vv, yoff)
                cap = (WEAK_FACTOR if role == "W" else UPPER_FACTOR) * nominal
                ids.append((b.add_col((wp[0], wp[1], t["z0"]), h, i, cap, "weak" if role == "W" else "regular"), role))
        else:
            if ring:
                n_ring = 28 if i == 0 else 20
                pts = [(math.cos(2 * math.pi * k / n_ring) * (a_u - 2.5), math.sin(2 * math.pi * k / n_ring) * (a_v - 2.5)) for k in range(n_ring)]
            else:
                pts = []
                for m in range(ny):
                    for k in range(nx):
                        pts.append(((-a_u + 2.5) + k * (2 * a_u - 5.0) / (nx - 1), (-a_v + 2.5) + m * (2 * a_v - 5.0) / (ny - 1)))
            if inside is not None:
                pts = [p for p in pts if inside(world(p[0], p[1]))]
            nominal = total[i] / max(1, len(pts))
            for uu, vv in pts:
                wp = world(uu, vv)
                ids.append((b.add_col((wp[0], wp[1], t["z0"]), h, i, factor * nominal), "regular"))
        support_ids = [cid for cid, _ in ids]
        for k in range(t["floors"]):
            mass = floor_area * MASS_PER_M2
            b.add_floor(t["z0"] + (k + 1) * FLOOR_H, i, mass, support_ids)
        b.tiers.append({"index": i, "z": round(t["z0"], 2), "height": round(h, 2), "mass": round(t["mass"], 2),
                        "com": [round(com[0], 2), round(com[1], 2)]})
    # weak lines
    for n, (ti, yoff) in enumerate(weak_tiers):
        wcols = [c["id"] for c in b.columns if c["tier"] == ti and c["role"] == "weak"]
        v = rot((0.0, 1.0), frame_yaw + yoff)
        b.weak_lines.append({"id": "%s_w%d" % (prefix, n + 1), "columns": wcols, "tier": ti,
                             "collapse_dir": [round(v[0], 4), round(v[1], 4)],
                             "hint": "transfer columns of tier %d; losing them tips tiers %d..%d toward (%.2f, %.2f)" % (ti, ti, n_tiers - 1, v[0], v[1])})
    for n, (ti, _) in enumerate(weak_tiers):
        wl = b.weak_lines[n]
        if not (1 <= ti <= n_tiers - 1) or len(wl["columns"]) < 2:
            raise ValueError("%s: weak line %d needs a tier in 1..%d with >= 2 weak columns (tier %d, %d columns)" % (prefix, n + 1, n_tiers - 1, ti, len(wl["columns"])))
    first_weak = min(ti for ti, _ in weak_tiers)
    return b.finish(list(range(first_weak, n_tiers))), b


def build_span_structure(prefix, p0, p1, base_z, deck_z, width, n_piers, weak_pier):
    """Elevated road (overpass). Spans are independent tiers; each pier has three columns (v = -0.5w, -0.15w, +0.5w)
    and holds the two neighbouring spans. The weak line is the +v edge column of three consecutive piers
    starting at `weak_pier`: the two spans between them lose their +v support and tip sideways (+v)."""
    b = Builder(prefix, stacked=False)
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    length = math.hypot(dx, dy)
    ux, uy = dx / length, dy / length
    vx, vy = -uy, ux
    span = length / (n_piers - 1)
    n_spans = n_piers - 1
    span_mass = span * width * 0.9 * 2.2
    pier_ids = []
    for k in range(n_piers):
        ids = []
        for vv in (-0.5 * width, -0.15 * width, 0.5 * width):
            x = p0[0] + ux * k * span + vx * vv
            y = p0[1] + uy * k * span + vy * vv
            holds = [t for t in (k - 1, k) if 0 <= t < n_spans]
            cid = b.add_col((x, y, base_z), deck_z - base_z, holds[0], 1.8 * span_mass / 6.0,
                            "weak" if (vv > 0 and weak_pier <= k <= weak_pier + 2) else "regular")
            b.columns[-1]["holds"] = holds
            ids.append(cid)
        pier_ids.append(ids)
    for k in range(n_spans):
        mid = (p0[0] + ux * (k + 0.5) * span, p0[1] + uy * (k + 0.5) * span)
        b.tiers.append({"index": k, "z": round(deck_z, 2), "height": 1.5, "mass": round(span_mass, 2), "com": [round(mid[0], 2), round(mid[1], 2)]})
        b.add_floor(deck_z, k, span_mass, pier_ids[k] + pier_ids[k + 1])
    wcols = [c["id"] for c in b.columns if c["role"] == "weak"]
    b.weak_lines.append({"id": prefix + "_w1", "columns": wcols, "tier": weak_pier,
                         "collapse_dir": [round(vx, 4), round(vy, 4)],
                         "hint": "edge columns of piers %d-%d; the deck between them tips sideways onto the street" % (weak_pier, weak_pier + 2)})
    order = [weak_pier, weak_pier + 1, weak_pier - 1, weak_pier + 2, weak_pier - 2, weak_pier + 3]
    order = [t for t in order if 0 <= t < n_spans]
    rest = [t for t in range(n_spans) if t not in order]
    chunks = [order[:2], order[2:4], order[4:] + rest]
    return b.finish(chunks), b
