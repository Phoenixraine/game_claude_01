"""Infrastructure: port (quay, containers, crane), substation, metro tunnel, hazards."""
import math

from .geom import point_in_poly, rect_poly, rot, centroid


def _r(v, n=1):
    return round(v, n)


def make_port(layout, terrain, rng, buildings):
    blk = next(b for b in layout.blocks if b["col"] == 5 and b["row"] == 0 and b["kind"] == "site")
    poly, w, h, yaw = layout.block_frame(blk)
    quay = []
    x0, x1 = poly[0][0], poly[1][0]
    n = 8
    top = []
    for i in range(n + 1):
        x = x0 + (x1 - x0) * i / n
        top.append((x, terrain.coast_y(x) + 6.0))
    quay = [(p[0], p[1]) for p in top] + [(p[0], p[1] + 26.0) for p in reversed(top)]
    crane = next(b for b in buildings if b.get("hero_kind") == "port_crane")
    crane_poly = [tuple(p) for p in crane["footprint"]]
    cx, cy = centroid(crane_poly)
    containers = []
    # stacks in a yard, aligned to the block frame
    u_count, v_count = 17, 5
    k = 0
    for i in range(u_count):
        for j in range(v_count):
            u = 0.34 + 0.62 * i / (u_count - 1)
            v = 0.30 + 0.62 * j / (v_count - 1)
            c = layout.bilinear(poly, u, v)
            if abs(c[0] - cx) < 34.0 and abs(c[1] - cy) < 30.0:
                continue
            if rng.chance(0.12):
                continue
            k += 1
            containers.append({"id": "cnt_%03d" % k, "pos": [_r(c[0]), _r(c[1])], "yaw_deg": _r(math.degrees(yaw)), "levels": rng.randint(1, 4),
                               "variant": rng.randint(0, 5)})
    return {"quay": [[_r(p[0]), _r(p[1])] for p in quay], "block_id": blk["id"], "containers": containers,
            "cranes": [crane["id"]]}


def make_substation(buildings):
    ps = next(b for b in buildings if b.get("hero_kind") == "power_station")
    poly = [tuple(p) for p in ps["footprint"]]
    c = centroid(poly)
    yaw = math.radians(ps["yaw_deg"])
    yard = rect_poly(c[0] + 95.0 * math.cos(yaw), c[1] + 95.0 * math.sin(yaw), 52.0, 46.0, yaw)
    return {"id": "substation_01", "yard": [[_r(p[0]), _r(p[1])] for p in yard], "power_station_id": ps["id"],
            "transformers": [{"pos": [_r(c[0] + (95.0 + dx) * math.cos(yaw) - dy * math.sin(yaw)), _r(c[1] + (95.0 + dx) * math.sin(yaw) + dy * math.cos(yaw))]}
                             for dx in (-14.0, 0.0, 14.0) for dy in (-10.0, 10.0)]}


def make_metro(layout, terrain):
    """One line under the street west of the central avenue; ceilings are thin under the cross streets."""
    street = [v for v in layout.vlines if v[2] == "street"][1]
    xc = street[0]
    pts = []
    y = terrain.coast_y(xc) + 120.0
    while y <= 1180.0:
        w = layout.warp(xc, y)
        pts.append((w[0], w[1]))
        y += 70.0
    weak = []
    for k, yc in enumerate((520.0, 720.0, 945.0)):
        a = layout.warp(xc, yc - 32.0)
        b = layout.warp(xc, yc + 32.0)
        weak.append({"id": "metro_weak_%d" % (k + 1), "from": [_r(a[0]), _r(a[1])], "to": [_r(b[0]), _r(b[1])], "ceiling_thickness": 0.9,
                     "normal_thickness": 3.0, "hint": "thin roof under the cross street: a heavy step collapses it into the tunnel"})
    stations = []
    for k, yc in enumerate((600.0, 830.0)):
        c = layout.warp(xc, yc)
        stations.append({"id": "metro_station_%d" % (k + 1), "entrance": [_r(c[0] + 30.0), _r(c[1])], "platform_center": [_r(c[0]), _r(c[1])]})
    return {"id": "metro_line_1", "width": 16.0, "floor_z": -14.0, "ceiling_thickness": 3.0, "points": [[_r(p[0]), _r(p[1])] for p in pts],
            "weak_segments": weak, "stations": stations}


def make_hazards(layout, terrain, buildings, substation, metro):
    hazards = []
    ps = next(b for b in buildings if b.get("hero_kind") == "power_station")
    c = centroid([tuple(p) for p in ps["footprint"]])
    ring = [[_r(c[0] + math.cos(2 * math.pi * k / 24) * 125.0), _r(c[1] + math.sin(2 * math.pi * k / 24) * 125.0)] for k in range(24)]
    hazards.append({"id": "haz_electrical_01", "kind": "electrical", "polygon": ring, "source": ps["id"],
                    "effect": "arcing near broken lines; electrical damage to a mech standing in the zone; lights out when the station falls"})
    for i, (cx, cy, r, depth) in enumerate(terrain.basins):
        rr = r * 0.75
        hazards.append({"id": "haz_flood_%02d" % (i + 1), "kind": "flood", "polygon": [[_r(cx + math.cos(2 * math.pi * k / 20) * rr), _r(cy + math.sin(2 * math.pi * k / 20) * rr)] for k in range(20)],
                        "effect": "low ground: water rises with a tidal surge; slows movement, cools the reactor"})
    for seg in metro["weak_segments"]:
        hazards.append({"id": "haz_" + seg["id"], "kind": "metro_collapse", "polygon": [seg["from"], seg["to"]], "effect": seg["hint"]})
    return hazards
