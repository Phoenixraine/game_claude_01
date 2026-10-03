"""Silhouette study: python art/mech_v2/blockout.py [tag]  -> previews/silhouette_<tag>_{front,side,three_quarter}.png (Workbench, flat shading)."""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bpy
from lib import design, hs, render
from build_params import PARAMS

tag = sys.argv[1] if len(sys.argv) > 1 else "a"
design.blockout(PARAMS)
sc = render.setup_scene((700, 900), 16, bg=(0.85, 0.87, 0.9))
render.lights()
mo = bpy.data.materials.new("Clay"); mo.use_nodes = True
mo.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.5, 0.55, 0.62, 1)
mo.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.6
bpy.context.view_layer.material_override = mo
H = PARAMS["height"]
out = os.path.join(HERE, "previews"); os.makedirs(out, exist_ok=True)
for name, loc, ortho in (("front", (0, -400, H / 2), True), ("side", (400, 0, H / 2), True)):
    render.ortho_view(os.path.join(out, "silhouette_%s_%s.png" % (tag, name)), loc, (0, 0, H / 2), H * 1.1, res=(700, 900), samples=16)
render.hero(os.path.join(out, "silhouette_%s_three_quarter.png" % tag), (75, -115, 44), (0, 0, 41), lens=50, res=(900, 900), samples=16)
