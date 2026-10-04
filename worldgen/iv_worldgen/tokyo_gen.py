"""Assembles district.json (schema_version 2) for the Tokyo style: terrain with canal and piers, layout, heroes, props, lights, POIs, hazards."""
import math

from . import tokyo_buildings as TB
from . import tokyo_layout as TL
from . import tokyo_props as TP
from .geom import centroid
from .rng import Rng
from . import terrain as Tm

SCHEMA_VERSION_V2 = 2
NO_BLOCK_HEROES = {"expressway", "suspension_bridge", "scramble_crossing"}   # elevated / painted: footprints do not block props or the 35 m corridor


def _r(v, n=2):
    return round(v, n)


def _pois(layout, terrain, buildings):
    pois = []
    x = 60.0
    yp = terrain.coast_y(x) - 95.0
    pois.append({"id": "spawn_player", "kind": "spawn_player", "name": "Player spawn (rising from the bay)", "pos": [_r(x, 1), _r(yp, 1), _r(terrain.height(x, yp))], "yaw_deg": 90.0})
    sc = layout.scramble_centre()
    pois.append({"id": "spawn_enemy", "kind": "spawn_enemy", "name": "Enemy spawn (scramble crossing)", "pos": [_r(sc[0], 1), _r(sc[1], 1), _r(terrain.height(sc[0], sc[1]))], "yaw_deg": 270.0})
    yb = layout.hlines[TL.PLAZA_BOULEVARD][0]
    for nm, dx, yaw in (("a", -105.0, 0.0), ("b", 105.0, 180.0)):
        w = layout.warp(0.0 + dx, yb)
        pois.append({"id": "spawn_duel_" + nm, "kind": "spawn_duel_" + nm, "name": "Duel spawn %s (boulevard)" % nm.upper(), "pos": [_r(w[0], 1), _r(w[1], 1), _r(terrain.height(w[0], w[1]))],
                     "yaw_deg": yaw})
    emb = layout.embankment_pts
    for nm, dx, yaw in (("a", -105.0, 0.0), ("b", 105.0, 180.0)):
        xx = 0.0 + dx
        i = min(range(len(emb)), key=lambda k: abs(emb[k][0] - xx))
        yy = emb[i][1]
        pois.append({"id": "duel_waterfront_" + nm, "kind": "duel_point", "name": "Waterfront duel point %s (embankment)" % nm.upper(), "pos": [_r(xx, 1), _r(yy, 1), _r(terrain.height(xx, yy))],
                     "yaw_deg": yaw})
    H = {b["hero_kind"]: b for b in buildings if b["type"] == "hero"}

    def hc(k):
        return centroid([tuple(p) for p in H[k]["footprint"]])

    lat, gl, st, tg, br, ex = hc("tower_lattice"), hc("glass_tower"), hc("brick_station"), hc("temple_gate"), hc("suspension_bridge"), hc("expressway")
    cams = [("cam_shore", "Seawall wide", (-250.0, terrain.coast_y(-250.0) - 120.0, 35.0), (0.0, 700.0, 80.0), 55.0),
            ("cam_lattice", "Lattice tower from the avenue", (lat[0] + 60.0, lat[1] - 230.0, 28.0), (lat[0], lat[1], 150.0), 45.0),
            ("cam_scramble", "Scramble crossing", (sc[0] + 10.0, sc[1] - 150.0, 20.0), (sc[0], sc[1], 25.0), 50.0),
            ("cam_bridge", "Suspension bridge from the sea", (br[0] - 140.0, 10.0, 24.0), (br[0], br[1], 55.0), 55.0),
            ("cam_expressway", "Expressway collapse", (ex[0] - 120.0, ex[1] - 70.0, 30.0), (ex[0], ex[1], 14.0), 50.0),
            ("cam_glass", "Glass tower", (gl[0] - 150.0, gl[1] - 120.0, 25.0), (gl[0], gl[1], 120.0), 40.0),
            ("cam_station", "Brick terminal", (st[0] - 110.0, st[1] - 130.0, 18.0), (st[0], st[1], 14.0), 50.0),
            ("cam_temple", "Thunder Gate", (tg[0] + 30.0, tg[1] - 40.0, 6.0), (tg[0], tg[1], 8.0), 55.0)]
    for cid, name, pos, look, fov in cams:
        pois.append({"id": cid, "kind": "camera", "name": name, "pos": [_r(pos[0], 1), _r(pos[1], 1), _r(pos[2], 1)], "look_at": [_r(look[0], 1), _r(look[1], 1), _r(look[2], 1)], "fov_deg": fov})
    return pois


def _lights(props, buildings, rng):
    """World light points for the evening / night preset: street lamps, neon signs, lit window blocks, billboards (screen walls)."""
    r = rng.fork("lights")
    out = []
    n = [0]

    def add(kind, pos, color, inten):
        n[0] += 1
        out.append({"id": "light_%04d" % n[0], "kind": kind, "pos": [_r(pos[0], 1), _r(pos[1], 1), _r(pos[2], 1)], "color": list(color), "intensity_hint": _r(inten, 2)})

    for p in props:
        if p["kind"] == "lamp":
            add("street", (p["pos"][0], p["pos"][1], p["pos"][2] + 7.5), (255, 214, 150), 1.0)
        elif p["kind"] == "sign" and p.get("emissive"):
            add("neon_sign", p["pos"], TP.SIGN_RGB[p["variant"]], 0.6 + 0.8 * min(1.0, p["size"][0] * p["size"][1] / 20.0))
        elif p["kind"] == "traffic_light":
            add("street", (p["pos"][0], p["pos"][1], p["pos"][2] + 5.5), (120, 255, 150) if r.chance(0.5) else (255, 80, 60), 0.5)
    for b in buildings:
        if b["type"] != "generic" and b.get("hero_kind") not in ("glass_tower", "tower_lattice", "twin_tower_hall"):
            continue
        if b["height"] < 36.0:
            continue
        poly = b["footprint"]
        for k in range(len(poly)):
            a, c = poly[k], poly[(k + 1) % len(poly)]
            if k % 2:
                continue
            for zf in (0.28, 0.55, 0.82):
                if r.chance(0.55):
                    add("window_block", ((a[0] + c[0]) / 2.0, (a[1] + c[1]) / 2.0, b["base_z"] + b["height"] * zf), (255, 232, 190) if r.chance(0.7) else (200, 225, 255), 0.4 + 0.5 * r.random())
    for b in buildings:
        if b.get("hero_kind") == "scramble_crossing":
            for part in b["parts"]:
                if part["kind"] == "screen_wall":
                    a, c = part["a"], part["b"]
                    add("billboard", ((a[0] + c[0]) / 2.0, (a[1] + c[1]) / 2.0, (part["z0"] + part["z1"]) / 2.0), (170, 235, 255), 2.5)
    return out


def _infrastructure(layout, terrain, buildings, wires, quay, rng):
    cr = next(b for b in buildings if b.get("hero_kind") == "port_crane")
    cc = centroid([tuple(p) for p in cr["footprint"]])
    containers = []
    k = 0
    x0 = min(p[0] for p in quay) + 10.0
    for i in range(8):
        for j in range(3):
            c = (x0 + i * 15.0, quay[0][1] + 8.0 + j * 9.0)
            if abs(c[0] - cc[0]) < 26.0 and abs(c[1] - cc[1]) < 20.0:
                continue
            if rng.chance(0.15):
                continue
            k += 1
            containers.append({"id": "cnt_%03d" % k, "pos": [_r(c[0], 1), _r(c[1], 1)], "yaw_deg": 0.0, "levels": rng.randint(1, 4), "variant": rng.randint(0, 5)})
    prom = layout.road_by_id(layout.promenade)
    seaward = [[p[0], _r(p[1] - prom["width"] / 2.0 + 1.0, 1), _r(terrain.height(p[0], p[1] - 18.0))] for p in prom["points"]]
    rails = [{"id": "rail_promenade", "points": seaward, "height": 1.1}]
    canal = layout.canal
    rails.append({"id": "rail_canal_south", "points": [[p[0], p[1], _r(terrain.height(p[0], p[1] - 1.0))] for p in canal["south_bank"]], "height": 1.1})
    rails.append({"id": "rail_canal_north", "points": [[p[0], p[1], _r(terrain.height(p[0], p[1] + 1.0))] for p in canal["north_bank"]], "height": 1.1})
    return {"canal": canal, "bridges": layout.bridges, "expressway_id": "hero_expressway", "suspension_bridge_id": "hero_suspension_bridge",
            "port": {"quay": [[_r(p[0], 1), _r(p[1], 1)] for p in quay], "containers": containers, "cranes": ["hero_port_crane"]}, "guardrails": rails, "wires": wires}


def _hazards(layout, terrain, buildings):
    hz = []
    ex = next(b for b in buildings if b.get("hero_kind") == "expressway")
    wl = ex["structure"]["weak_lines"][0]
    cols = {c["id"]: c for c in ex["structure"]["columns"]}
    xs = [cols[i]["pos"][0] for i in wl["columns"]]
    ys = [cols[i]["pos"][1] for i in wl["columns"]]
    x0, x1, y0, y1 = min(xs) - 30.0, max(xs) + 30.0, min(ys) - 30.0, max(ys) + 30.0
    hz.append({"id": "haz_expressway_collapse", "kind": "expressway_collapse", "polygon": [[_r(x0, 1), _r(y0, 1)], [_r(x1, 1), _r(y0, 1)], [_r(x1, 1), _r(y1, 1)], [_r(x0, 1), _r(y1, 1)]],
               "source": ex["id"], "effect": "weakened piers: the deck between them tips onto the embankment road; debris and dust over the canal side"})
    c = layout.canal
    poly = [[p[0], _r(p[1] - 10.0, 1)] for p in c["south_bank"]] + [[p[0], _r(p[1] + 10.0, 1)] for p in reversed(c["north_bank"])]
    hz.append({"id": "haz_canal_flood", "kind": "canal_flood", "polygon": poly, "effect": "canal surge: water overtops the banks when a heavy body falls in; slows movement, cools the reactor"})
    return hz


def build_tokyo(seed):
    root = Rng(seed)
    terrain = TL.TokyoTerrain(seed, [])
    layout = TL.TokyoLayout(seed, terrain, root.fork("layout"))
    gen = TB.TokyoBuildingGen(layout, terrain, root.fork("buildings"))
    buildings = gen.generate()
    for b in buildings:                                         # pads under every footprint (the pier of the sphere / the quay become land)
        if b.get("hero_kind") in ("suspension_bridge", "expressway", "scramble_crossing"):
            continue
        terrain.flatten([tuple(p) for p in b["footprint"]], b["base_z"], 10.0 if b["type"] == "generic" else 14.0)
    if gen.quay:
        terrain.flatten(gen.quay, TB.PIER_Z, 8.0)
    terrain._update_range()
    heroes = [b for b in buildings if b["type"] == "hero"]
    polys = [[tuple(p) for p in b["footprint"]] for b in buildings if b.get("hero_kind") not in NO_BLOCK_HEROES]
    props, wires = TP.make_props(layout, terrain, root.fork("props"), polys, buildings, heroes)
    pois = _pois(layout, terrain, buildings)
    lights = _lights(props, buildings, root)
    infra = _infrastructure(layout, terrain, buildings, wires, gen.quay or [], root.fork("port"))
    hazards = _hazards(layout, terrain, buildings)
    doc = {
        "schema_version": SCHEMA_VERSION_V2,
        "style": "tokyo",
        "seed": seed,
        "bounds": {"units": "meters", "axes": "x right, y from the sea toward the city, z up",
                   "playable": {"x_min": -800.0, "x_max": 800.0, "y_min": 0.0, "y_max": 1200.0},
                   "terrain": {"x_min": Tm.X0, "x_max": Tm.X1, "y_min": Tm.Y0, "y_max": Tm.Y1}},
        "terrain": terrain.metadata(),
        "water": {"level_z": 0.0, "sea_floor_z": Tm.SEA_FLOOR, "shoreline": terrain.shoreline(), "flood_zones": [h["id"] for h in hazards if h["kind"] in ("flood", "canal_flood")]},
        "roads": layout.roads,
        "blocks": layout.blocks,
        "buildings": buildings,
        "infrastructure": infra,
        "props": props,
        "lights": lights,
        "pois": pois,
        "hazards": hazards,
    }
    return doc, terrain
