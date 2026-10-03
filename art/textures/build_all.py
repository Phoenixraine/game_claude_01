#!/usr/bin/env python3
"""Build all textures: python art/textures/build_all.py [--scale 1] [--only SUBSTR] [--out DIR].

--scale S divides every resolution by S (S=1: 2048 materials, 4096 trim sheet, 2048 atlases; the tests use --scale 8).
Outputs go to <out>/ (default art/textures/out, git-ignored: it is ~1 GB of PNG); the manifest and previews are committed."""
import argparse
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from lib import decals, maps, materials, misc, trim, vfx  # noqa: E402

PRESET = dict(material=2048, decal=512, trim=4096, atlas_frame=256, mask=1024)


def sizes(scale):
    return {k: max(16, v // scale) for k, v in PRESET.items()}


def prev_sheet(path, tiles, cols, size=256, bg=0.2):
    rows = (len(tiles) + cols - 1) // cols
    sheet = np.full((rows * size, cols * size, 3), bg, np.float32)
    for i, t in enumerate(tiles):
        r, c = divmod(i, cols)
        sheet[r * size:(r + 1) * size, c * size:(c + 1) * size] = np.asarray(Image.fromarray(maps.to_u8(t)).resize((size, size), Image.LANCZOS), np.float32) / 255.0
    os.makedirs(os.path.dirname(path), exist_ok=True)
    Image.fromarray(maps.to_u8(sheet)).save(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scale", type=int, default=1)
    ap.add_argument("--only", default="")
    ap.add_argument("--out", default=str(HERE / "out"))
    ap.add_argument("--previews", default=str(HERE / "previews"))
    ap.add_argument("--no-previews", action="store_true")
    a = ap.parse_args()
    S = sizes(a.scale)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    man = {"format": 1, "generated_with_scale": a.scale, "sizes": S,
           "conventions": {"Normal": "tangent space, OpenGL (Y+), RGB = n*0.5+0.5", "ORM": "R = ambient occlusion, G = roughness, B = metallic (Linear)",
                           "BaseColor": "sRGB", "atlas": "8x8 flipbook, row-major from the top-left, 64 frames, RGBA premultiplied alpha",
                           "decals": "RGBA straight alpha, alpha = 0 on the border"},
           "materials": [], "decals": [], "trim_sheet": None, "vfx": [], "luts": [], "masks": []}
    t0 = time.time()
    prevs = {}
    # ---- tileable materials
    thumbs = []
    for fn in materials.MATERIALS:
        if a.only and a.only not in fn.__name__:
            continue
        m = materials.build_material(fn, S["material"])
        files = m.write(str(out))
        man["materials"].append({"name": m.name, "size": S["material"], "tile": True, "files": files, "note": m.note})
        ts = 192
        tile = np.tile(m.base, (2, 2, 1))
        thumbs.append((m.name, [m.base, maps.encode_normal(m.normal), m.orm, np.stack([m.height] * 3, -1), tile]))
        print("material", m.name)
    if thumbs and not a.no_previews:
        for gi in range(0, len(thumbs), 3):
            grp = thumbs[gi:gi + 3]
            tiles = [t for _, ts_ in grp for t in ts_]
            prev_sheet(os.path.join(a.previews, "materials_%02d.png" % (gi // 3 + 1)), tiles, 5, 256)
    # ---- decals
    if not a.only or "decal" in a.only:
        dd = out / "decals"
        dl = decals.all_decals(S["decal"])
        for d in dl:
            files = d.write(str(dd))
            man["decals"].append({"name": d.name, "size": S["decal"], "kind": d.kind, "files": files, "note": d.note})
        if not a.no_previews:
            tiles = []
            for d in dl:
                bg = np.full((S["decal"], S["decal"], 3), 0.3, np.float32)
                bg[::max(1, S["decal"] // 16)] += 0.05
                tiles.append(bg * (1 - d.alpha[..., None]) + d.rgb * d.alpha[..., None])
            prev_sheet(os.path.join(a.previews, "decals.png"), tiles, 10, 160)
        print("decals", len(dl))
    # ---- trim sheet
    if not a.only or "trim" in a.only:
        m, regions = trim.build_trim(S["trim"])
        files = m.write(str(out))
        man["trim_sheet"] = {"name": "trim_sheet", "size": S["trim"], "files": files, "regions": regions,
                             "convention": "regions are horizontal strips tileable along U; uv_top_left has V from the top (Unreal), uv_bottom_left from the bottom (Blender)"}
        (out / "trim_sheet").mkdir(parents=True, exist_ok=True)
        with open(out / "trim_sheet" / "trim_sheet.json", "w") as f:
            json.dump(man["trim_sheet"], f, indent=1)
        if not a.no_previews:
            prev_sheet(os.path.join(a.previews, "trim_sheet.png"), [m.base, maps.encode_normal(m.normal), np.stack([m.height] * 3, -1)], 3, 512)
        print("trim sheet")
    # ---- VFX
    if not a.only or "vfx" in a.only:
        f = S["atlas_frame"]
        (out / "vfx").mkdir(parents=True, exist_ok=True)
        tiles = []
        for name, spec in vfx.ATLASES.items():
            fr = spec["fn"](f)
            atlas = vfx.to_atlas(fr)
            maps.save_png(str(out / "vfx" / (name + ".png")), atlas)
            man["vfx"].append({"name": name, "file": "out/vfx/%s.png" % name, "size": 8 * f, "frame": f, "grid": [8, 8], "frames": 64,
                               "fps": spec["fps"], "blend": spec["blend"], "loop": spec["loop"], "premultiplied": True, "note": spec["note"],
                               "colorspace": "sRGB"})
            bg = 0.18
            row = []
            for i in (6, 16, 28, 40, 52):
                al = fr[i][..., 3:4]
                row.append(np.clip(fr[i][..., :3] + (bg * (1 - al) if spec["blend"] == "alpha" else bg), 0, 1))
            tiles += row
            print("vfx", name)
        if not a.no_previews:
            prev_sheet(os.path.join(a.previews, "vfx.png"), tiles, 5, 192)
    # ---- LUTs and masks
    if not a.only or "lut" in a.only or "mask" in a.only:
        (out / "luts").mkdir(parents=True, exist_ok=True)
        h = misc.heat_lut(256)
        maps.save_png(str(out / "luts" / "heat_lut.png"), h)
        d = misc.damage_lut(256)
        maps.save_png(str(out / "luts" / "damage_color_lut.png"), d)
        man["luts"] = [{"name": "heat_lut", "file": "out/luts/heat_lut.png", "size": [256, 1], "colorspace": "sRGB", "note": "0 cold (deep blue) .. 1 hottest (white)", "stops": misc.HEAT_STOPS},
                       {"name": "damage_color_lut", "file": "out/luts/damage_color_lut.png", "size": [256, 2], "colorspace": "sRGB",
                        "note": "row 0 = 5 hard bands, row 1 = smooth blend; order neutral, exposed, damaged, critical, lost (pitch §21)",
                        "steps": [{"name": n, "rgb": list(c)} for n, c in misc.DAMAGE_STEPS]}]
        (out / "masks").mkdir(parents=True, exist_ok=True)
        S_m = S["mask"]
        mk = []
        for kind, fn in (("Dent", misc.mask_dent), ("Crack", misc.mask_crack), ("Burn", misc.mask_burn)):
            for i in range(4):
                arr = fn(S_m, i)
                name = "mask_%s_%02d" % (kind.lower(), i + 1)
                maps.save_png(str(out / "masks" / (name + ".png")), arr)
                man["masks"].append({"name": name, "kind": kind, "variant": i, "file": "out/masks/%s.png" % name, "size": S_m, "colorspace": "Linear", "tile": True})
                mk.append(np.stack([arr] * 3, -1))
        man["mask_zone_variants"] = misc.zone_variants()
        if not a.no_previews:
            prev_sheet(os.path.join(a.previews, "masks.png"), mk, 4, 192)
            lut = np.concatenate([np.repeat(h, 24, 0), np.repeat(d[:1], 24, 0), np.repeat(d[1:], 24, 0)], 0)[..., :3]
            Image.fromarray(maps.to_u8(lut)).resize((768, 144), Image.NEAREST).save(os.path.join(a.previews, "luts.png"))
        print("luts + masks")
    # the committed manifest.json is only written by a full-resolution full build; other runs write next to their outputs
    full = a.only == "" and a.scale == 1
    man_path = HERE / "manifest.json" if full else out / "manifest.json"
    with open(man_path, "w") as f:
        json.dump(man, f, indent=1)
        f.write("\n")
    total = sum(p.stat().st_size for p in out.rglob("*.png"))
    print("done in %.0f s, %.1f MB of PNG in %s" % (time.time() - t0, total / 1048576, out))


if __name__ == "__main__":
    main()
