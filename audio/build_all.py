#!/usr/bin/env python3
"""Build every sound: python audio/build_all.py [--only SUBSTR] [--jobs N] [--no-spectrograms] [--out DIR].

Deterministic: each sound is seeded from its id (zlib.crc32), so a rebuild from scratch yields identical WAV files
on one machine/library version. Outputs: out/*.wav, manifest.json, out/spectrograms/<group>.png, out/.gitignore.
"""
import argparse
import importlib
import json
import os
import sys
import time
from multiprocessing import Pool
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

MODULES = [m for m in ["mech", "hits", "cockpit", "env", "ui", "music"] if (HERE / "gen" / (m + ".py")).exists()]
GIT_LIMIT = 4.8 * 1024 * 1024   # CLAUDE.md: no binaries above 5 MB in git; larger files are built, not committed


def load():
    from gen.registry import REGISTRY
    for m in MODULES:
        importlib.import_module("gen." + m)
    return REGISTRY


def _build_one(args):
    sid, out = args
    from gen import render
    reg = load()
    snd = reg[sid]
    t0 = time.time()
    x = render.render(snd)
    path = Path(out) / (sid + ".wav")
    render.write_wav(path, x)
    return sid, time.time() - t0


def entry(snd, out):
    from gen import render
    x, sr = render.read_wav(Path(out) / (snd.id + ".wav"))
    return {
        "id": snd.id,
        "file": "out/%s.wav" % snd.id,
        "duration_s": round(len(x) / sr, 3),
        "sample_rate": sr,
        "bit_depth": 16,
        "channels": 1 if x.ndim == 1 else 2,
        "loop": snd.loop,
        "bus": snd.bus,
        "volume_db": snd.vol_db,
        "attenuation_radius_m": snd.radius,
        "variation_group": snd.group,
        "peak_dbfs": round(render.db(abs(x).max()), 2),
        "rms_dbfs": round(render.db(render.rms(x)), 2),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="", help="build only ids containing this substring")
    ap.add_argument("--jobs", type=int, default=min(4, os.cpu_count() or 1))
    ap.add_argument("--no-spectrograms", action="store_true")
    ap.add_argument("--out", default=str(HERE / "out"))
    a = ap.parse_args()
    out = Path(a.out)
    (out / "spectrograms").mkdir(parents=True, exist_ok=True)
    reg = load()
    ids = [i for i in reg if a.only in i]
    t0 = time.time()
    work = [(i, str(out)) for i in ids]
    if a.jobs > 1:
        with Pool(a.jobs) as p:
            res = p.map(_build_one, work, chunksize=1)
    else:
        res = [_build_one(w) for w in work]
    slow = sorted(res, key=lambda r: -r[1])[:3]
    print("rendered %d sounds in %.1f s (slowest: %s)" % (len(ids), time.time() - t0, ", ".join("%s %.1fs" % s for s in slow)))

    # manifest always covers the whole registry; entries are read back from the files on disk
    man = {"format": 1, "sample_rate": 48000, "bit_depth": 16,
           "buses": {"sfx_ext": "3D exterior effects", "sfx_cockpit": "interior effects (stereo, 2D)", "ambient": "ambient beds and loops",
                     "ui": "menu/HUD sounds", "music": "music"},
           "sounds": []}
    missing = [i for i in reg if not (out / (i + ".wav")).exists()]
    if missing:
        print("manifest skipped, files missing for: %s" % ", ".join(missing[:5]))
    else:
        man["sounds"] = [entry(reg[i], out) for i in reg]
        (HERE / "manifest.json").write_text(json.dumps(man, indent=1) + "\n", encoding="utf-8")
        total = sum((out / (i + ".wav")).stat().st_size for i in reg)
        print("manifest.json: %d sounds, %.1f MB of WAV" % (len(man["sounds"]), total / 1048576))

    big = sorted(i + ".wav" for i in reg if (out / (i + ".wav")).exists() and (out / (i + ".wav")).stat().st_size > GIT_LIMIT)
    (out / ".gitignore").write_text("# files above 5 MB are rebuilt by build_all.py, not committed (CLAUDE.md)\n" + "".join(b + "\n" for b in big))
    if big:
        print("not for git (>5 MB): " + ", ".join(big))

    if not a.no_spectrograms:
        from gen import render, spectro
        groups = {}
        for i in ids:
            groups.setdefault(reg[i].group, []).append(i)
        for g, members in groups.items():
            mem = [(i, render.read_wav(out / (i + ".wav"))[0]) for i in members]
            if not spectro.sheet(out / "spectrograms" / (g + ".png"), mem, g):
                print("matplotlib not installed: spectrograms skipped")
                break
        print("spectrograms: %d groups" % len(groups))


if __name__ == "__main__":
    main()
