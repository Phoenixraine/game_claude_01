"""Bake all geometry maps (4 Cycles passes, cached as .npz), extend them over the island margins, synthesise the PBR sets for both factions and
write the PNGs + manifest. Cache key = resolution; delete work/ or pass --rebake to redo."""
import os
import time

import numpy as np

from . import bake, hs, textures
from . import noise as nz

PAD = 8


def _extend(arrs, cover0, pad=PAD):
    """Fill the texels within `pad` px of an island with the value of the nearest island texel (instead of Cycles' margin)."""
    from scipy import ndimage
    d, (iy, ix) = ndimage.distance_transform_edt(~cover0, return_indices=True)
    ext = d <= pad
    return [a[iy, ix] for a in arrs], ext


def bake_maps(work, res, rebake=False):
    path = os.path.join(work, "maps_%d.npz" % res)
    if os.path.exists(path) and not rebake:
        z = np.load(path)
        return {k: z[k] for k in z.files}
    t0 = time.time()
    print("  baking maps at %d px (4 Cycles passes) ..." % res, flush=True)
    pos = bake.bake_emit(res, bake.make_position, "pos", 1, 0)
    print("   position pass %.0fs" % (time.time() - t0), flush=True)
    nrm = bake.bake_normal(res)
    print("   normal pass %.0fs" % (time.time() - t0), flush=True)
    pk = bake.bake_emit(res, bake.make_packed_ao, "pk", 8, 0)
    print("   ao/thickness pass %.0fs" % (time.time() - t0), flush=True)
    rc = bake.bake_emit(res, bake.make_rid_cover, "rc", 1, 0)
    print("   id/coverage pass %.0fs" % (time.time() - t0), flush=True)
    out = {}
    for m in hs.MATERIALS:
        cover0 = rc[m][..., 1] > 0.5
        (p, n, ao_s, ao_l, thk, rid), ext = _extend([pos[m], nrm[m], pk[m][..., 0], pk[m][..., 1], pk[m][..., 2], rc[m][..., 0]], cover0)
        out[m + "|pos"] = p.astype(np.float32)
        out[m + "|nrm"] = n.astype(np.float16)
        out[m + "|ao_s"] = ao_s.astype(np.float16)
        out[m + "|ao_l"] = ao_l.astype(np.float16)
        out[m + "|thk"] = thk.astype(np.float16)
        out[m + "|rid"] = rid.astype(np.float16)
        out[m + "|cover0"] = cover0
        out[m + "|cover"] = ext
    np.savez(path, **out)
    return out


def run(work, tex_dir, res, rebake=False):
    maps = bake_maps(work, res, rebake)
    manifest = {"resolution": res, "convention": {"BaseColor": "sRGB", "Normal": "linear, tangent space, OpenGL (+Y up)", "ORM": "linear: R=AO G=Roughness B=Metallic",
                                                  "Emissive": "sRGB colour, strength set in the material"}, "sets": {}, "bake_passes": ["position", "normal", "ao_short+ao_long+thickness", "object_id+coverage"]}
    for faction, prefix in (("player", "BASTION"), ("enemy", "ENEMY")):
        files = {}
        for i, m in enumerate(hs.MATERIALS):
            t0 = time.time()
            mm = {k: maps["%s|%s" % (m, k)].astype(np.float32) if k not in ("cover0", "cover") else maps["%s|%s" % (m, k)].astype(np.float32)
                  for k in ("pos", "nrm", "ao_s", "ao_l", "thk", "rid", "cover0", "cover")}
            tex = textures.synth(m, mm, res, faction, seed=10 + i)
            files[m] = textures.save_set(tex_dir, prefix, m, tex)
            print("   %s %-18s %.0fs" % (faction, m, time.time() - t0), flush=True)
        manifest["sets"]["T_%s" % prefix] = files
    return manifest
