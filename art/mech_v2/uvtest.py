import os, sys, time
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import bpy
from lib import hs, uv, z_all
from build_params import PARAMS
hs.reset(); z_all.build_all(PARAMS)
import numpy as np
t0=time.time()
tgt, dens = uv.unwrap_all()
print("unwrap %.1fs target density %.5f uv/m = %.1f px/m at 2048" % (time.time()-t0, tgt, tgt*2048))
print(uv.island_density_spread(hs.REG.parts))
