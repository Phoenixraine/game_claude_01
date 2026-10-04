#!/usr/bin/env python3
"""Glass HUD build: JSON contracts + SVG layers + PNG exports + raster masks + preview frames. Source of truth = lib/data.py, lib/shapes.py, lib/masks.py.

  python3 ui/glass_hud/build_hud.py [--out DIR] [--no-previews]
Deterministic (fixed seeds). cairosvg + Pillow + numpy are required."""
import hashlib
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

from lib import data, masks, presets, scene, shapes  # noqa: E402
from lib.svgkit import glow, svg_doc  # noqa: E402

PAL = data.PALETTE["colors"]


def wjson(path, doc):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=1, ensure_ascii=False)
        f.write("\n")


def wtext(path, text):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def svg_png(svg, path, w, h=None):
    import cairosvg
    cairosvg.svg2png(bytestring=svg.encode("utf-8"), write_to=path, output_width=w, output_height=h)


def schema_doc():
    rect = {"type": "array", "items": {"type": "number", "minimum": 0, "maximum": 1}, "minItems": 4, "maxItems": 4}
    return {
        "$schema": "http://json-schema.org/draft-07/schema#", "title": "glass_hud layout.json", "type": "object",
        "required": ["version", "reference", "free_center", "max_persistent_coverage", "aspects", "elements", "world_elements", "fullscreen_layers", "bindings"],
        "properties": {
            "version": {"type": "integer", "enum": [1]},
            "reference": {"type": "object", "required": ["width", "height"]},
            "free_center": rect, "max_persistent_coverage": {"type": "number", "minimum": 0, "maximum": 1},
            "aspects": {"type": "object"},
            "elements": {"type": "array", "items": {"type": "object", "required": ["id", "file", "anchor", "rect", "persistent"], "properties": {
                "id": {"type": "string"}, "file": {"type": "string"}, "rect": rect, "persistent": {"type": "boolean"},
                "anchor": {"type": "string", "enum": ["top_left", "top_right", "top_center", "bottom_left", "bottom_right", "bottom_center"]}}}},
            "world_elements": {"type": "array", "items": {"type": "object", "required": ["id", "file"]}},
            "fullscreen_layers": {"type": "array", "items": {"type": "object", "required": ["id"]}},
            "bindings": {"type": "array", "items": {"type": "object", "required": ["event", "element", "behavior"]}},
        },
    }


def layout_doc():
    return {
        "version": 1,
        "reference": {"width": 1920, "height": 1080, "note": "rects are fractions [x, y, w, h] of the 16:9 reference frame; anchor says which corner/edge the element keeps its distance from on other aspect ratios"},
        "safe_margin": {"x": 0.02, "y": 0.03},
        "free_center": data.FREE_CENTER, "max_persistent_coverage": data.MAX_PERSISTENT_COVERAGE,
        "aspects": {k: {"ratio": round(v, 4), "rule": "uniform UI scale = height/1080 for ratio >= 16:9, width/1920 below; corner offsets scale with it; centred elements stay centred"} for k, v in data.ASPECTS.items()},
        "elements": data.ELEMENTS, "world_elements": data.WORLD_ELEMENTS, "fullscreen_layers": data.FULLSCREEN_LAYERS,
        "bindings": [{"event": e, "element": el, "behavior": b} for e, el, b in data.BINDINGS],
        "state_inputs": {
            "note": "What the game passes each frame (lib/presets.py shows complete examples).",
            "player/enemy": "zones{Zone: ZoneState name}, layers{Zone: [armor, mechanism, system] remaining 0..1}",
            "scalars": ["armor", "stability", "heat", "energy", "ultimate{value, ready}", "arm_armor[L, R]", "priority (EnergyPriority)", "heading", "distance_m", "clock_s"],
            "weapons": "{rail|rockets|plasma: {ring 0..1, dead, empty}}", "lock": "{rect (fractions), quality 0..1, hex, hex_hot}", "strike": "{points (fractions), committed}",
            "threats": "list of up|down|left|right", "glass": "{cracks[idx], soot[idx], drops N, glitch 0..1, alarm 0..1}",
        },
    }


def build_svgs(out):
    sv = os.path.join(out, "svg")
    os.makedirs(sv, exist_ok=True)
    W = lambda name, w, h, inner, view=None: wtext(os.path.join(sv, name), svg_doc(w, h, inner, view, title=name[:-4]))
    W("silhouette_body_player.svg", 400, 540, shapes.silhouette("player"))
    W("silhouette_body_enemy.svg", 400, 540, shapes.silhouette("enemy"))
    W("zone_layers_arcs.svg", 400, 540, shapes.layer_arcs("player"))
    W("zone_layers_arcs_enemy.svg", 400, 540, shapes.layer_arcs("enemy"))
    W("lockon_corners.svg", 200, 200, shapes.lockon_corners(PAL["cyan"]))
    W("lockon_zone_hexes.svg", 200, 200, shapes.lockon_hex(PAL["cyan"]))
    W("strike_arc.svg", 400, 200, shapes.strike_arc(None, PAL["white"]))
    W("crosshair.svg", 48, 48, shapes.crosshair(PAL["white"]))
    for kind in ("armor", "stability", "heat", "energy"):
        W("bar_%s.svg" % kind, 256, 256, shapes.ring_gauge(kind, 0.75, scene.gauge_color(kind, 0.75)))
    W("ultimate_gauge.svg", 256, 256, shapes.ultimate_gauge(0.75, False))
    for key in ("rockets", "rail", "plasma"):
        W("weapon_icons_%s.svg" % key, 64, 64, shapes.icon_weapon(key, PAL["white"]))
    row = "".join('<g transform="translate(%d 0)">%s</g>' % (i * 96, shapes.icon_weapon(k, PAL["white"])) for i, k in enumerate(("rail", "rockets", "plasma")))
    W("weapon_icons_row.svg", 288, 64, row)
    for key, col in (("blind", PAL["amber"]), ("strikelock", PAL["amber"]), ("burn", PAL["red"])):
        W("status_icons_%s.svg" % key, 64, 64, shapes.icon_status(key, col))
    row = "".join('<g transform="translate(%d 0) scale(0.84)">%s</g>' % (i * 62, shapes.icon_status(k, PAL["lost"])) for i, k in enumerate(("blind", "strikelock", "burn")))
    W("status_icons_row.svg", 260, 54, row)
    for d in ("up", "left", "right", "down"):
        W("threat_arrows_%s.svg" % d, 120, 120, shapes.threat_arrow(d, PAL["red"]))
    W("icon_warning.svg", 64, 64, shapes.icon_warning(PAL["red"]))
    W("radar.svg", 200, 200, shapes.radar(PAL["cyan"], 20, 0.55, 70))
    W("compass_strip.svg", 600, 40, shapes.compass_strip(0))
    W("power_priority.svg", 232, 60, shapes.power_priority("Arms", PAL["amber"]))
    W("arm_armor_bars.svg", 520, 22, shapes.arm_bars(0.9, 0.6, PAL["neutral"], PAL["neutral"]))
    W("stability_bar_h.svg", 260, 30, shapes.stability_bar(0.7, PAL["cyan"]))
    W("clock_digits.svg", 140, 40, shapes.seg_text("1:34", 4, 4, 22, 32, PAL["cyan"]))
    W("distance_digits.svg", 170, 40, shapes.seg_text("0024", 4, 4, 28, 32, PAL["cyan"]))
    W("digits_atlas.svg", 520, 80, shapes.seg_text("0123456789", 4, 6, 28, 60, PAL["cyan"], gap=18, width=2.4) if False else "".join('<g transform="translate(%d 0)">%s</g>' % (i * 46, shapes.seg_char(c, 6, 10, 28, 60, PAL["cyan"], 2.4)) for i, c in enumerate("0123456789%")))
    W("alarm_frame.svg", 1024, 576, '<defs><radialGradient id="g" cx="50%" cy="50%" r="75%"><stop offset="0.55" stop-color="#ff4a3d" stop-opacity="0"/><stop offset="1" stop-color="#ff4a3d" stop-opacity="0.9"/></radialGradient></defs>'
      '<rect width="1024" height="576" fill="url(#g)"/>' + glow("M18 18 L1006 18 L1006 558 L18 558 Z", PAL["red"], 2.0, 0.8, dash="30 14"))
    for i in range(8):                                    # glitch strips are raster-only; the SVG list stays honest
        pass


def build_rasters(out):
    pn = os.path.join(out, "png")
    os.makedirs(pn, exist_ok=True)
    for kind in ("armor", "stability", "heat", "energy"):
        masks.save_rgba(masks.gauge_mask(kind), os.path.join(pn, "bar_%s.png" % kind))
    # ultimate mask: 12 blocks like energy
    masks.save_rgba(masks.gauge_mask("energy"), os.path.join(pn, "ultimate_gauge.png"))
    for i in range(8):
        masks.save_gray(masks.crack_mask(100 + 13 * i, cracks=6 + i, rings=1 + i % 3), os.path.join(pn, "crack_mask_%02d.png" % i))
    for i in range(4):
        masks.save_gray(masks.soot_mask(7 + i), os.path.join(pn, "soot_mask_%02d.png" % i))
    for i in range(8):
        masks.save_rgba(masks.glitch_strip(31 + i), os.path.join(pn, "glitch_strip_%02d.png" % i))
    masks.save_rgba(masks.rain_atlas(), os.path.join(pn, "rain_drops_atlas.png"))
    masks.save_rgba(masks.alarm_frame(), os.path.join(pn, "alarm_frame.png"))
    # lock-on ring animation strip: 16 frames, 4 x 4 cells of 128 px
    sheet = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
    for k in range(16):
        svg = svg_doc(128, 128, shapes.lockon_ring_frame(k))
        import cairosvg
        png = cairosvg.svg2png(bytestring=svg.encode("utf-8"), output_width=128, output_height=128)
        sheet.paste(Image.open(io.BytesIO(png)).convert("RGBA"), ((k % 4) * 128, (k // 4) * 128))
    sheet.save(os.path.join(pn, "lockon_ring_anim_strip.png"), optimize=True)
    # PNG exports of the vector layers (RGBA): big ones 2048 px high, icons 256
    sv = os.path.join(out, "svg")
    big = {"silhouette_body_player": (1024, 1382), "silhouette_body_enemy": (1024, 1382), "zone_layers_arcs": (1024, 1382), "zone_layers_arcs_enemy": (1024, 1382),
           "radar": (1024, None), "lockon_corners": (512, None), "lockon_zone_hexes": (512, None), "compass_strip": (1200, None), "digits_atlas": (1040, None)}
    for name, (w, h) in big.items():
        svg_png(open(os.path.join(sv, name + ".svg"), encoding="utf-8").read(), os.path.join(pn, name + ".png"), w, h)
    for name in ("weapon_icons_rockets", "weapon_icons_rail", "weapon_icons_plasma", "status_icons_blind", "status_icons_strikelock", "status_icons_burn",
                 "threat_arrows_up", "threat_arrows_left", "threat_arrows_right", "threat_arrows_down", "icon_warning"):
        svg_png(open(os.path.join(sv, name + ".svg"), encoding="utf-8").read(), os.path.join(pn, name + ".png"), 256, 256)


def build_previews(out):
    pv = os.path.join(out, "previews")
    os.makedirs(pv, exist_ok=True)
    for name, fn in presets.PRESETS.items():
        st = fn()
        frame = scene.compose_frame(st)
        Image.fromarray(frame).save(os.path.join(pv, "hud_%s.jpg" % name), quality=90, optimize=True)
        print("preview", name)
    # layout schematic: persistent rects on 3 aspect ratios + the free centre
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axs = plt.subplots(1, 3, figsize=(18, 4.6), dpi=100)
    fig.patch.set_facecolor("#0b1220")
    for ax, (nm, ratio) in zip(axs, data.ASPECTS.items()):
        Hh = 1080.0
        Ww = Hh * ratio
        ax.set_facecolor("#05080d")
        fx, fy, fw, fh = scene.free_center_px(Ww, Hh)
        ax.add_patch(plt.Rectangle((fx, fy), fw, fh, fc="#1d3a2a", ec="#4caf50", alpha=0.35, lw=1))
        for el in data.ELEMENTS:
            x, y, w, h = scene.element_rect_px(el, Ww, Hh)
            col = "#7fe4ff" if el["persistent"] else "#ffd24a"
            ax.add_patch(plt.Rectangle((x, y), w, h, fc=col, ec=col, alpha=0.35, lw=1))
            ax.text(x + 4, y + 14, el["id"], color="w", fontsize=6)
        ax.set_xlim(0, Ww)
        ax.set_ylim(Hh, 0)
        ax.set_aspect("equal")
        ax.set_title("%s (free centre green)" % nm, color="w", fontsize=9)
        ax.tick_params(colors="#889", labelsize=6)
    fig.savefig(os.path.join(pv, "layout_aspects.png"), facecolor=fig.get_facecolor())


def manifest(out):
    rows = []
    for sub in ("svg", "png", "previews"):
        d = os.path.join(out, sub)
        if not os.path.isdir(d):
            continue
        for f in sorted(os.listdir(d)):
            p = os.path.join(d, f)
            rows.append({"path": "%s/%s" % (sub, f), "bytes": os.path.getsize(p), "sha256": hashlib.sha256(open(p, "rb").read()).hexdigest()[:16]})
    return {"version": 1, "files": rows}


def main(argv):
    out = HERE
    if "--out" in argv:
        out = argv[argv.index("--out") + 1]
    os.makedirs(out, exist_ok=True)
    wjson(os.path.join(out, "palette.json"), data.PALETTE)
    wjson(os.path.join(out, "states.json"), data.STATES)
    wjson(os.path.join(out, "layout.json"), layout_doc())
    wjson(os.path.join(out, "schema.json"), schema_doc())
    build_svgs(out)
    build_rasters(out)
    if "--no-previews" not in argv:
        build_previews(out)
    wjson(os.path.join(out, "assets_manifest.json"), manifest(out))
    print("done")


if __name__ == "__main__":
    main(sys.argv[1:])
