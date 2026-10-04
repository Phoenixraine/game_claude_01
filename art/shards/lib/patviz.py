"""matplotlib visualisation of the fracture patterns: cells exploded away from the centre, coloured by volume."""
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection


def draw(patterns, names, path, explode=0.35):
    fig = plt.figure(figsize=(13, 7.2), dpi=90, facecolor="#0b1016")
    cols = 2
    rows = (len(names) + 1) // 2
    cmap = plt.get_cmap("turbo")
    byname = {p["name"]: p for p in patterns["patterns"]}
    for k, n in enumerate(names):
        p = byname[n]
        ax = fig.add_subplot(rows, cols, k + 1, projection="3d", facecolor="#0b1016")
        vols = [sum(1 for _ in c["polys"]) for c in p["cells"]]
        for ci, c in enumerate(p["cells"]):
            V = np.array(c["verts"])
            cen = V.mean(axis=0)
            off = cen * explode
            faces = [[V[i] + off for i in poly["v"]] for poly in c["polys"]]
            shade = cmap(0.15 + 0.7 * ((ci * 37) % 100) / 100.0)
            pc = Poly3DCollection(faces, facecolor=shade, edgecolor="#0b1016", linewidths=0.4, alpha=0.95)
            ax.add_collection3d(pc)
        ax.set_xlim(-0.8, 0.8)
        ax.set_ylim(-0.8, 0.8)
        ax.set_zlim(-0.8, 0.8)
        ax.set_box_aspect((1, 1, 1))
        ax.view_init(elev=18, azim=-55)
        ax.set_axis_off()
        ax.set_title("%s  (%s, %d pieces)" % (p["name"], p["kind"], p["fragments"]), color="#cfe3ee", fontsize=9)
    fig.text(0.01, 0.01, "facade = -Y (front, towards the camera), Z up; exploded x%.2f" % explode, color="#7f98a8", fontsize=7)
    fig.tight_layout()
    fig.savefig(path, facecolor=fig.get_facecolor())
    plt.close(fig)
