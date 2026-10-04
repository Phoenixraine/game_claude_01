"""Extra props of the cyberpunk layer (TASK-019): neon torii arches, banner flags, steam vents, puddle masks, roof water tanks and antennas, garland wires,
and the crowd spawners of the pedestrian street / the scramble."""
import math

from .geom import centroid, norm
from .tokyo_props import TokyoPropPlacer


def _r(v, n=1):
    return round(v, n)


def make_extras(layout, terrain, rng, buildings, props_by_placer, wires, arena):
    """`props_by_placer` is the TokyoPropPlacer that already holds the TASK-015 props (so ids and the spacing grid continue). Returns (spawners)."""
    P = props_by_placer
    rr = rng.fork("cyber_props")
    spawners = []
    plaza_c = layout.plaza["center"]
    if arena == "takeshita":
        st = layout.strip
        road = layout.road_by_id(st["road"])
        line = [tuple(p) for p in road["points"]]
        # three neon torii arches over the first 45 m of the street (entrance from the station side)
        for k, s in enumerate((12.0, 30.0, 48.0)):
            x, y, ux, uy = _at(line, s)
            P.add_free("torii_neon", x, y, terrain.height(x, y), math.atan2(uy, ux), "arch_pipe_%d" % (k + 1), {"width_m": 13.0, "height_m": 8.5 - k * 0.6})
        # banner flags every ~14 m on both sides, steam vents behind the shop rows
        total = _length(line)
        s = 20.0
        n = 0
        while s < total - 15.0:
            x, y, ux, uy = _at(line, s)
            for side in (-1, 1):
                P.add_free("banner_flag", x - uy * side * 5.2, y + ux * side * 5.2, terrain.height(x, y) + 4.5, math.atan2(uy, ux) + side * math.pi / 2, "flag_%d" % rr.randint(1, 6),
                           {"size": [1.0, 4.0], "emissive": False})
            s += 14.0 * rr.uniform(0.85, 1.15)
            n += 1
        # crowd along the street, denser at the entrance and towards the plaza
        s = 8.0
        k = 0
        while s < total - 6.0:
            x, y, ux, uy = _at(line, s)
            f = s / total
            dens = 3.0 + 5.0 * (1.0 - abs(f - 0.5) * 1.2) + rr.uniform(-0.8, 0.8)
            spawners.append({"id": "crowd_%03d" % (len(spawners) + 1), "pos": [_r(x + rr.uniform(-2.0, 2.0)), _r(y), _r(terrain.height(x, y), 2)], "radius_m": 5.5,
                             "density_per_100m2": _r(max(1.5, dens), 1), "speed_mps": _r(rr.uniform(0.7, 1.5), 2), "dir": [round(ux * (1 if k % 2 == 0 else -1), 3), round(uy * (1 if k % 2 == 0 else -1), 3)]})
            s += 9.0
            k += 1
        # garland (string lights) wires across the street between the shop facades
        s = 26.0
        while s < total - 20.0:
            x, y, ux, uy = _at(line, s)
            a = (x - uy * 6.2, y + ux * 6.2)
            b = (x + uy * 6.2, y - ux * 6.2)
            z0 = terrain.height(x, y) + 8.8
            pts = []
            for q in range(7):
                f = q / 6.0
                pts.append([_r(a[0] + (b[0] - a[0]) * f, 2), _r(a[1] + (b[1] - a[1]) * f, 2), _r(z0 - 1.1 * 4.0 * f * (1.0 - f), 2)])
            wires.append({"id": "wire_g%03d" % (len(wires) + 1), "kind": "garland", "from": "street", "to": "street", "points": pts})
            s += 18.0
    else:
        # scramble: three neon arches over the boulevard approach, flags on the crossing edge, crowd at the four corners and along the sidewalks
        yb = layout.hlines[1][0]
        for k, dx in enumerate((-110.0, -140.0, -170.0)):
            x, y = plaza_c[0] + dx, plaza_c[1]
            P.add_free("torii_neon", x, y, terrain.height(x, y), 0.0, "arch_pipe_%d" % (k + 1), {"width_m": 92.0, "height_m": 9.0})
        for k in range(24):
            a = 2 * math.pi * k / 24
            x, y = plaza_c[0] + math.cos(a) * 46.0, plaza_c[1] + math.sin(a) * 46.0
            P.add_free("banner_flag", x, y, terrain.height(x, y) + 4.5, a, "flag_%d" % rr.randint(1, 6), {"size": [1.0, 4.0], "emissive": False})
        for k in range(36):
            a = 2 * math.pi * k / 36
            rad = 30.0 + 40.0 * rr.random()
            x, y = plaza_c[0] + math.cos(a) * rad, plaza_c[1] + math.sin(a) * rad
            spawners.append({"id": "crowd_%03d" % (len(spawners) + 1), "pos": [_r(x), _r(y), _r(terrain.height(x, y), 2)], "radius_m": 7.0, "density_per_100m2": _r(rr.uniform(3.0, 9.0), 1),
                             "speed_mps": _r(rr.uniform(0.9, 1.6), 2), "dir": [round(-math.sin(a), 3), round(math.cos(a), 3)]})
    # steam vents along the alleys (nearly every alley has one or two, plus the street sides)
    for road in layout.roads:
        if road["kind"] != "alley":
            continue
        pts = [tuple(p) for p in road["points"]]
        total = _length(pts)
        for s in (total * 0.3, total * 0.7):
            if rr.chance(0.7):
                x, y, ux, uy = _at(pts, s)
                side = 1 if rr.chance(0.5) else -1
                P.add("steam_vent", x - uy * side * (road["width"] / 2.0 - 1.2), y + ux * side * (road["width"] / 2.0 - 1.2), 0.0, "vent_%s" % rr.choice("abc"), 3.0)
    # puddle masks on the streets (reflection masks for the wet asphalt)
    for road in layout.roads:
        if road["kind"] in ("embankment", "promenade"):
            continue
        pts = [tuple(p) for p in road["points"]]
        total = _length(pts)
        cnt = int(total / (60.0 if road["kind"] != "alley" else 40.0))
        for _ in range(cnt):
            x, y, ux, uy = _at(pts, rr.uniform(0.0, total))
            off = rr.uniform(-road["width"] / 2.0 + 1.5, road["width"] / 2.0 - 1.5)
            P.add_free("puddle", x - uy * off, y + ux * off, terrain.height(x, y) + 0.02, rr.uniform(0.0, 6.28), "puddle_%d" % rr.randint(1, 4), {"size": [_r(rr.uniform(2.0, 9.0)), _r(rr.uniform(1.5, 5.0))]})
    # roof clutter
    for b in buildings:
        if b["type"] != "generic" or b["building_type"] in ("temple", "parking"):
            continue
        if b["height"] > 130.0 or not rr.chance(0.6 if b["building_type"] in ("low_shop", "shopfront_row", "apartment_tower") else 0.3):
            continue
        c = centroid([tuple(p) for p in b["footprint"]])
        z = b["base_z"] + b["height"]
        for _ in range(rr.randint(1, 3)):
            kind = "water_tank" if rr.chance(0.45) else "rooftop_antenna"
            P.add_free(kind, c[0] + rr.uniform(-5.0, 5.0), c[1] + rr.uniform(-5.0, 5.0), z, rr.uniform(0.0, 6.28), "roof_%s" % rr.choice("abc"),
                       {"size": [_r(rr.uniform(1.5, 3.5)), _r(rr.uniform(2.0, 9.0))], "building_id": b["id"]})
    return spawners


def _length(line):
    return sum(math.hypot(line[i + 1][0] - line[i][0], line[i + 1][1] - line[i][1]) for i in range(len(line) - 1))


def _at(line, s):
    """Point at arc length s along a polyline with its unit tangent."""
    acc = 0.0
    for i in range(len(line) - 1):
        l = math.hypot(line[i + 1][0] - line[i][0], line[i + 1][1] - line[i][1])
        if acc + l >= s or i == len(line) - 2:
            t = max(0.0, min(1.0, (s - acc) / l)) if l > 0 else 0.0
            ux, uy = (line[i + 1][0] - line[i][0]) / l, (line[i + 1][1] - line[i][1]) / l
            return (line[i][0] + (line[i + 1][0] - line[i][0]) * t, line[i][1] + (line[i + 1][1] - line[i][1]) * t, ux, uy)
        acc += l
    return (line[-1][0], line[-1][1], 1.0, 0.0)
