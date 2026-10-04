"""Builds the whole shard library: meshes -> checks -> manifest -> fracture patterns -> exports -> previews.
Usage:  python3 art/shards/build_shards.py [--no-previews] [--no-export]"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from lib import builders, checks     # noqa: E402

OUT = os.path.join(HERE, "out")
PREV = os.path.join(HERE, "previews")


def main(argv):
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(PREV, exist_ok=True)
    t0 = time.time()
    lib = builders.build_library()
    print("built %d assets, %d triangles in %.1fs" % (len(lib), sum(a.mesh.tris() for a in lib), time.time() - t0))
    problems = checks.check_library(lib)
    for p in problems:
        print("PROBLEM:", p)
    if problems:
        sys.exit(1)
    manifest = checks.manifest(lib)
    with open(os.path.join(HERE, "shards_manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=1)
        f.write("\n")
    print("manifest: %d entries" % len(manifest["assets"]))
    from lib import fracture, patviz
    pats = fracture.make_patterns(manifest)
    with open(os.path.join(HERE, "fracture_patterns.json"), "w", encoding="utf-8") as f:
        json.dump(pats, f, separators=(",", ":"))
        f.write("\n")
    print("fracture patterns: %d" % len(pats["patterns"]))
    patviz.draw(pats, ["voronoi_16", "radial_center", "layers_4", "diagonal_50"], os.path.join(PREV, "fracture_patterns.png"))
    if "--previews-only" in argv:
        argv = argv + ["--no-export"]
    if "--no-export" not in argv or "--no-previews" not in argv:
        from lib import export
        if "--no-export" not in argv:
            export.export_all(lib, OUT)
            bad = export.verify_exports(lib, OUT)
            print("re-import check: %d problems" % len(bad))
            for b in bad:
                print("PROBLEM:", b)
            if bad:
                sys.exit(1)
        if "--no-previews" not in argv:
            only = [a.split("=", 1)[1].split(",") for a in argv if a.startswith("--only=")]
            export.previews(lib, PREV, only[0] if only else None)
    print("done in %.1fs" % (time.time() - t0))


if __name__ == "__main__":
    main(sys.argv[1:])
