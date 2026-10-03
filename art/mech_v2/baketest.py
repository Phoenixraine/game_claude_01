import os, sys, time
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import bpy, numpy as np
from lib import hs, uv, z_all, bake
from build_params import PARAMS
hs.reset(); z_all.build_all(PARAMS)
uv.unwrap_all(verbose=False)
res = 1024
for name, fn in (("ao", lambda: bake.bake_ao(res, 8.0, 8)), ("pos", lambda: bake.bake_emit(res, bake.make_position, "pos")),
                 ("rnd", lambda: bake.bake_emit(res, bake.make_random, "rnd")), ("thk", lambda: bake.bake_emit(res, bake.make_thickness, "thk", 8)),
                 ("nrm", lambda: bake.bake_normal(res))):
    t0 = time.time()
    d = fn()
    m = d["M_CeramicGray"]
    print(name, "%.1fs" % (time.time() - t0), m.shape, float(m.min()), float(m.max()), float(m.mean()))
    np.save(os.path.join(HERE, "previews", "bk_%s.npy" % name), m)
