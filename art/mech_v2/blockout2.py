"""Quick clay render of the current detailed build: python blockout2.py <tag> [front,side,tq,legs...]."""
import os, sys, time
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import bpy
from lib import hs, render, z_all
from build_params import PARAMS
tag = sys.argv[1]
views = sys.argv[2].split(",") if len(sys.argv) > 2 else ["front", "tq"]
t0 = time.time(); hs.reset(); z_all.build_all(PARAMS)
print("built %d parts, %d tris in %.1fs" % (len(hs.REG.parts), sum(len(p.vertices) - 2 for o in hs.REG.parts for p in o.data.polygons), time.time() - t0))
render.setup_scene((900, 1100), 24, bg=(0.85, 0.87, 0.9)); render.lights()
mo = bpy.data.materials.new("Clay"); mo.use_nodes = True
mo.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.5, 0.55, 0.62, 1)
mo.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.55
if "--clay" in sys.argv: bpy.context.view_layer.material_override = mo
out = os.path.join(HERE, "previews"); os.makedirs(out, exist_ok=True)
H = PARAMS["height"]
V = {"front": ((0, -400, H / 2), (0, 0, H / 2), 1.1 * H, None), "side": ((400, 0, H / 2), (0, 0, H / 2), 1.1 * H, None),
     "tq": ((75, -115, 44), (0, 0, 41), None, 50), "legs": ((50, -60, 20), (0, 0, 20), None, 40), "legs_side": ((90, -25, 20), (0, 0, 20), None, 45),
     "torso": ((55, -70, 58), (0, 0, 58), None, 40), "arm": ((60, -55, 45), (14, 0, 46), None, 45), "head": ((24, -30, 74), (0, -3, 74), None, 50),
     "back": ((-60, 90, 50), (0, 0, 45), None, 40), "tq2": ((-80, -105, 44), (0, 0, 41), None, 50)}
for v in views:
    loc, tgt, orth, lens = V[v]
    p = os.path.join(out, "wip_%s_%s.png" % (tag, v))
    if orth: render.ortho_view(p, loc, tgt, orth, res=(800, 1000), samples=16)
    else: render.hero(p, loc, tgt, lens=lens, res=(1000, 1000), samples=24)
