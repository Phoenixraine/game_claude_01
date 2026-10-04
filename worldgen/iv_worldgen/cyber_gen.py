"""Assembles district.json (schema_version 3) of the cyberpunk layer: Takeshita-dori / Shibuya-scramble arenas with glass towers, shop rows, mega signs,
1500+ light points, destruction data, fog maps, crowd spawners (TASK-019)."""
import json

from . import cyber_buildings as CB
from . import cyber_data as CD
from . import cyber_lights as CL
from . import cyber_props as CP
from . import cyber_signs as CS
from . import terrain as Tm
from . import tokyo_gen as TG
from . import tokyo_layout as TL
from . import tokyo_props as TP
from .rng import Rng

SCHEMA_VERSION_V3 = 3
ARENAS = ("takeshita", "shibuya_scramble")


def _pois(layout, terrain, buildings, arena):
    pois = TG._pois(layout, terrain, buildings)
    pc = layout.plaza["center"]
    for p in pois:
        if p["kind"] in ("spawn_duel_a", "spawn_duel_b"):
            dx = -70.0 if p["kind"].endswith("a") else 70.0
            p["pos"] = [round(pc[0] + dx, 1), pc[1], round(terrain.height(pc[0] + dx, pc[1]), 2)]
            p["name"] = "Duel spawn %s (battle plaza)" % p["kind"][-1].upper()
    south = (pc[0], pc[1] - 150.0, 24.0) if arena == "takeshita" else (pc[0] - 150.0, pc[1], 24.0)
    pois.append({"id": "cam_plaza", "kind": "camera", "name": "Battle plaza from the %s" % ("street" if arena == "takeshita" else "boulevard"),
                 "pos": [round(south[0], 1), round(south[1], 1), south[2]], "look_at": [pc[0], pc[1] + 40.0, 70.0], "fov_deg": 55.0})
    pois.append({"id": "cam_neon", "kind": "camera", "name": "Neon wall", "pos": [pc[0], pc[1], 14.0], "look_at": [pc[0] + 30.0, pc[1] + 120.0, 120.0], "fov_deg": 70.0})
    return pois


def build_cyber(seed, arena="takeshita"):
    if arena not in ARENAS:
        raise ValueError("arena must be one of %s" % (ARENAS,))
    root = Rng(seed)
    terrain = TL.TokyoTerrain(seed, [])
    layout = TL.TokyoLayout(seed, terrain, root.fork("layout"), arena=arena)
    gen = CB.CyberBuildingGen(layout, terrain, root.fork("buildings"))
    buildings = gen.generate()
    for b in buildings:
        if b.get("hero_kind") in ("suspension_bridge", "expressway", "scramble_crossing"):
            continue
        terrain.flatten([tuple(p) for p in b["footprint"]], b["base_z"], 10.0 if b["type"] == "generic" else 14.0)
    if gen.quay:
        terrain.flatten(gen.quay, 2.8, 8.0)
    terrain._update_range()
    heroes = [b for b in buildings if b["type"] == "hero"]
    polys = [[tuple(p) for p in b["footprint"]] for b in buildings if b.get("hero_kind") not in TG.NO_BLOCK_HEROES]
    placer, wires = TP.make_props(layout, terrain, root.fork("props"), polys, buildings, heroes, return_placer=True)
    spawners = CP.make_extras(layout, terrain, root, buildings, placer, wires, arena)
    props = placer.props
    glyphs = CD.make_glyph_sets()
    view = tuple(layout.plaza["center"])
    signs = CS.place_mega_signs(buildings, layout, root.fork("signs"), view, glyphs)
    pois = _pois(layout, terrain, buildings, arena)
    lights = CL.make_lights(layout, terrain, root, buildings, props, signs, arena)
    report = CL.light_report(lights, layout.blocks)
    infra = TG._infrastructure(layout, terrain, buildings, wires, gen.quay or [], root.fork("port"))
    hazards = TG._hazards(layout, terrain, buildings)
    fog_d, fog_g, fog_meta, _, _ = CL.make_fog(layout, terrain, lights, props, layout.roads)
    doc = {
        "schema_version": SCHEMA_VERSION_V3,
        "style": "cyber",
        "arena": {"name": arena, "plaza": layout.plaza, "street": None if arena != "takeshita" else {
            "road_id": layout.strip["road"], "name": "Takeshita-dori", "width_m": 12.0, "length_m": round(layout.strip["y_end"] - layout.strip["y_start"] + 28.0, 1),
            "entrance_torii": 3, "options": list(ARENAS) + ["nakamise"]}, "free_zone_m": layout.plaza["size"]},
        "seed": seed,
        "bounds": {"units": "meters", "axes": "x right, y from the sea toward the city, z up",
                   "playable": {"x_min": -800.0, "x_max": 800.0, "y_min": 0.0, "y_max": 1200.0},
                   "terrain": {"x_min": Tm.X0, "x_max": Tm.X1, "y_min": Tm.Y0, "y_max": Tm.Y1}},
        "terrain": terrain.metadata(),
        "water": {"level_z": 0.0, "sea_floor_z": Tm.SEA_FLOOR, "shoreline": terrain.shoreline(), "flood_zones": [h["id"] for h in hazards if h["kind"] in ("flood", "canal_flood")]},
        "roads": layout.roads,
        "blocks": layout.blocks + [{"id": "block_plaza", "kind": "plaza", "district": "civic", "col": 0, "row": 0, "polygon": layout.plaza["polygon"], "name": "battle_plaza"}],
        "buildings": buildings,
        "mega_signs": signs,
        "infrastructure": infra,
        "props": props,
        "crowd_spawners": spawners,
        "lights": lights,
        "light_report": {k: v for k, v in report.items() if k != "dominant_neon_hues_per_block"} | {"dominant_neon_hues_per_block": report["dominant_neon_hues_per_block"]},
        "fog_map": fog_meta,
        "resources": {"towers": "towers.json", "glyph_sets": "glyph_sets.json", "fracture_patterns": "art/shards/fracture_patterns.json (TASK-016)"},
        "pois": pois,
        "hazards": hazards,
    }
    terrain.extras = {"fog_density.png": fog_d, "fog_glow.png": fog_g,
                      "towers.json": json.dumps({"version": 1, "presets": CD.TOWER_PRESETS}, indent=1).encode("utf-8"),
                      "glyph_sets.json": json.dumps(glyphs, indent=1).encode("utf-8"),
                      "light_report.json": json.dumps(report, indent=1).encode("utf-8")}
    return doc, terrain
