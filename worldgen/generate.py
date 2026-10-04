#!/usr/bin/env python3
"""IMPACT VECTOR coastal district generator.

    python3 worldgen/generate.py --seed 7 --out worldgen/out/

Deterministic: the same seed gives byte-identical district.json and heightmap.r16 (see tests).
Only the standard library is used.
"""
import argparse
import hashlib
import json
import math
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from iv_worldgen import SCHEMA_VERSION, buildings as B, infra, layout as Lm, props, render, terrain as Tm
from iv_worldgen.geom import centroid
from iv_worldgen.png import write_png
from iv_worldgen.rng import Rng


def _r(v, n=2):
    return round(v, n)


def _basins(rng):
    r = rng.fork("basins")
    return [(r.uniform(430.0, 560.0), r.uniform(330.0, 400.0), r.uniform(75.0, 100.0), 2.2),
            (r.uniform(-420.0, -300.0), r.uniform(320.0, 380.0), r.uniform(60.0, 80.0), 2.0)]


def _pois(layout, terrain, buildings, rng):
    pois = []
    x = 60.0
    yp = terrain.coast_y(x) - 95.0
    pois.append({"id": "spawn_player", "kind": "spawn_player", "name": "Player spawn (rising from the sea)", "pos": [_r(x, 1), _r(yp, 1), _r(terrain.height(x, yp), 2)],
                 "yaw_deg": 90.0})
    plaza = next(b for b in layout.blocks if b["kind"] == "plaza")
    c = centroid([tuple(p) for p in plaza["polygon"]])
    pois.append({"id": "spawn_enemy", "kind": "spawn_enemy", "name": "Enemy spawn (central plaza)", "pos": [_r(c[0], 1), _r(c[1], 1), _r(terrain.height(c[0], c[1]), 2)],
                 "yaw_deg": 270.0})
    av = [v for v in layout.vlines if v[2] == "avenue"][0]
    for k, (nm, yy, yaw) in enumerate((("a", 590.0, 90.0), ("b", 800.0, 270.0))):
        w = layout.warp(av[0], yy)
        pois.append({"id": "spawn_duel_" + nm, "kind": "spawn_duel_" + nm, "name": "Duel spawn " + nm.upper(), "pos": [_r(w[0], 1), _r(w[1], 1), _r(terrain.height(w[0], w[1]), 2)],
                     "yaw_deg": yaw})
    heroes = {b["hero_kind"]: b for b in buildings if b["type"] == "hero"}

    def hc(k):
        return centroid([tuple(p) for p in heroes[k]["footprint"]])

    cams = [("cam_shore", "Shoreline wide", (-300.0, terrain.coast_y(-300.0) - 140.0, 40.0), (0.0, 700.0, 60.0), 55.0),
            ("cam_tower", "Glass tower from the avenue", (hc("glass_tower")[0] + 160.0, hc("glass_tower")[1] - 120.0, 30.0),
             (hc("glass_tower")[0], hc("glass_tower")[1], 120.0), 40.0),
            ("cam_plaza", "Plaza duel", (c[0] - 140.0, c[1] - 60.0, 18.0), (c[0], c[1], 40.0), 45.0),
            ("cam_overpass", "Overpass collapse", (hc("overpass")[0] + 150.0, hc("overpass")[1] - 40.0, 25.0), (hc("overpass")[0], hc("overpass")[1], 20.0), 50.0),
            ("cam_port", "Port crane", (hc("port_crane")[0] - 130.0, hc("port_crane")[1] + 110.0, 22.0), (hc("port_crane")[0], hc("port_crane")[1], 55.0), 45.0),
            ("cam_power", "Power station", (hc("power_station")[0] - 160.0, hc("power_station")[1] - 120.0, 35.0), (hc("power_station")[0], hc("power_station")[1], 45.0), 45.0)]
    for cid, name, pos, look, fov in cams:
        pois.append({"id": cid, "kind": "camera", "name": name, "pos": [_r(pos[0], 1), _r(pos[1], 1), _r(pos[2], 1)], "look_at": [_r(look[0], 1), _r(look[1], 1), _r(look[2], 1)],
                     "fov_deg": fov})
    return pois


def _guardrails(layout, terrain, buildings, port):
    rails = []
    prom = layout.roads[0]
    pts = prom["points"]
    seaward = []
    for i in range(len(pts)):
        x, y = pts[i]
        seaward.append([_r(x, 1), _r(y - prom["width"] / 2.0 + 1.0, 1), _r(terrain.height(x, y - 18.0), 2)])
    rails.append({"id": "rail_promenade", "points": seaward, "height": 1.1})
    ov = next(b for b in buildings if b.get("hero_kind") == "overpass")
    poly = ov["footprint"]
    rails.append({"id": "rail_overpass_a", "points": [[poly[0][0], poly[0][1], ov["deck_z"]], [poly[1][0], poly[1][1], ov["deck_z"]]], "height": 1.2})
    rails.append({"id": "rail_overpass_b", "points": [[poly[3][0], poly[3][1], ov["deck_z"]], [poly[2][0], poly[2][1], ov["deck_z"]]], "height": 1.2})
    q = port["quay"]
    half = len(q) // 2
    rails.append({"id": "rail_quay", "points": [[p[0], p[1], 2.0] for p in q[:half]], "height": 1.0})
    return rails


def build(seed, style="generic", arena="takeshita"):
    """style 'generic' = the v1 district (schema_version 1, unchanged); 'tokyo' = the Tokyo district (schema_version 2)."""
    if style == "tokyo":
        from iv_worldgen import tokyo_gen
        return tokyo_gen.build_tokyo(seed)
    if style == "cyber":
        from iv_worldgen import cyber_gen
        return cyber_gen.build_cyber(seed, arena)
    root = Rng(seed)
    basins = _basins(root)
    terrain = Tm.Terrain(seed, basins)
    layout = Lm.Layout(seed, terrain, root.fork("layout"))
    gen = B.BuildingGen(layout, terrain, root.fork("buildings"))
    buildings = gen.generate()
    for b in buildings:                                   # level pads under every footprint (done after base_z is recorded)
        terrain.flatten([tuple(p) for p in b["footprint"]], b["base_z"], 10.0 if b["type"] == "generic" else 14.0)
    terrain._update_range()
    polys = [[tuple(p) for p in b["footprint"]] for b in buildings]
    port = infra.make_port(layout, terrain, root.fork("port"), buildings)
    substation = infra.make_substation(buildings)
    metro = infra.make_metro(layout, terrain)
    hazards = infra.make_hazards(layout, terrain, buildings, substation, metro)
    prop_list = props.make_props(layout, terrain, root.fork("props"), polys, buildings)
    pois = _pois(layout, terrain, buildings, root.fork("pois"))
    rails = _guardrails(layout, terrain, buildings, port)
    doc = {
        "schema_version": SCHEMA_VERSION,
        "seed": seed,
        "bounds": {"units": "meters", "axes": "x right, y from the sea toward the city, z up",
                   "playable": {"x_min": -800.0, "x_max": 800.0, "y_min": 0.0, "y_max": 1200.0},
                   "terrain": {"x_min": Tm.X0, "x_max": Tm.X1, "y_min": Tm.Y0, "y_max": Tm.Y1}},
        "terrain": terrain.metadata(),
        "water": {"level_z": 0.0, "sea_floor_z": Tm.SEA_FLOOR, "shoreline": terrain.shoreline(),
                  "flood_zones": [h["id"] for h in hazards if h["kind"] == "flood"]},
        "roads": layout.roads,
        "blocks": layout.blocks,
        "buildings": buildings,
        "infrastructure": {"port": port, "substation": substation, "metro": metro, "overpass_id": "hero_overpass", "guardrails": rails},
        "props": prop_list,
        "pois": pois,
        "hazards": hazards,
    }
    return doc, terrain


def canonical(doc):
    return json.dumps(doc, separators=(",", ":"), ensure_ascii=True)


def digest(doc, terrain):
    h = hashlib.sha256()
    h.update(canonical(doc).encode("ascii"))
    h.update(terrain.to_r16())
    for name, blob in sorted(getattr(terrain, "extras", {}).items()):
        h.update(name.encode("ascii"))
        h.update(blob)
    return h.hexdigest()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--out", default="worldgen/out")
    ap.add_argument("--no-preview", action="store_true")
    ap.add_argument("--style", choices=("tokyo", "generic", "cyber"), default="tokyo", help="tokyo = schema_version 2 (default); cyber = schema_version 3 (TASK-019); generic = the v1 coastal district")
    ap.add_argument("--arena", choices=("takeshita", "shibuya_scramble"), default="takeshita", help="cyber style: battle arena (Takeshita-dori or the Shibuya scramble)")
    ap.add_argument("--preview-dir", default=None, help="where the cyber previews go (default: <out>/previews)")
    a = ap.parse_args(argv)
    t0 = time.time()
    doc, terrain = build(a.seed, a.style, a.arena)
    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.out, "district.json"), "w", encoding="ascii") as f:
        f.write(canonical(doc))
    with open(os.path.join(a.out, "heightmap.r16"), "wb") as f:
        f.write(terrain.to_r16())
    if not a.no_preview:
        if a.style == "cyber":
            from iv_worldgen import cyber_render
            pdir = a.preview_dir or os.path.join(a.out, "previews")
            os.makedirs(pdir, exist_ok=True)
            cyber_render.render_all(doc, terrain, pdir)
        elif a.style == "tokyo":
            from iv_worldgen import tokyo_render as R
            cv = R.render_topdown(doc, terrain)
            write_png(os.path.join(a.out, "preview_topdown.png"), cv.w, cv.h, cv.buf)
            cv = R.render_skyline(doc, terrain)
            write_png(os.path.join(a.out, "preview_skyline.png"), cv.w, cv.h, cv.buf)
        else:
            cv = render.render_topdown(doc, terrain, None)
            write_png(os.path.join(a.out, "preview_topdown.png"), cv.w, cv.h, cv.buf)
            cv = render.render_skyline(doc, terrain)
            write_png(os.path.join(a.out, "preview_skyline.png"), cv.w, cv.h, cv.buf)
    for name, blob in sorted(getattr(terrain, "extras", {}).items()):
        with open(os.path.join(a.out, name), "wb") as f:
            f.write(blob)
    d = digest(doc, terrain)
    with open(os.path.join(a.out, "district.sha256"), "w") as f:
        f.write(d + "\n")
    n_hero = sum(1 for b in doc["buildings"] if b["type"] == "hero")
    print("seed %d [%s%s]: %d buildings (%d hero), %d roads, %d props, sha256 %s, %.1fs" % (a.seed, a.style, ("/" + a.arena) if a.style == "cyber" else "", len(doc["buildings"]), n_hero, len(doc["roads"]),
                                                                                       len(doc["props"]), d[:16], time.time() - t0))
    return 0


if __name__ == "__main__":
    sys.exit(main())
