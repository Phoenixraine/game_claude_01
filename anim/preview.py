"""Silhouette sheets of poses (front and side) drawn with matplotlib: python -m anim.preview [--out anim/out/preview]."""
import os

import numpy as np

from . import rig

COLORS = {"l": "#3b82c4", "r": "#d9822b", "c": "#5a6470"}


def _col(b):
    return COLORS["l"] if b.endswith("_l") else COLORS["r"] if b.endswith("_r") else COLORS["c"]


def draw_pose(ax, F, view, com=None, title=None, lim=(-60, 60), zlim=(-5, 90), root_pos=None):
    seg = rig.segment_endpoints(F)
    ix = 0 if view == "front" else 1
    order = sorted(seg, key=lambda b: (F[b][1, 3] if view == "front" else -F[b][0, 3]) * (-1 if view == "front" else 1))
    for b in order:
        s, e = seg[b]
        w = rig.THICK.get(b, 8)
        ax.plot([s[ix], e[ix]], [s[2], e[2]], color=_col(b), lw=w * 0.9, solid_capstyle="round", alpha=0.92, zorder=2)
    for b in order:  # joints
        ax.plot([F[b][ix, 3]], [F[b][2, 3]], "o", color="#111", ms=2.5, zorder=3)
    ax.axhline(0, color="#444", lw=1)
    if com is not None:
        ax.plot([com[ix]], [com[2]], "x", color="#c00", ms=7, mew=2, zorder=4)
        ax.plot([com[ix], com[ix]], [0, com[2]], ":", color="#c00", lw=0.8, zorder=1)
    ax.set_xlim(*lim)
    ax.set_ylim(*zlim)
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])
    if title:
        ax.set_title(title, fontsize=6)


def sheet(path, pose_list, cols=6, size=2.0):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    rows = (len(pose_list) + cols - 1) // cols
    fig, axes = plt.subplots(rows * 2, cols, figsize=(cols * size, rows * 2 * size * 1.15), squeeze=False)
    for ax in axes.flat:
        ax.axis("off")
    for i, p in enumerate(pose_list):
        r, c = divmod(i, cols)
        F = p.F if hasattr(p, "F") else p
        com = rig.com(F)
        axes[2 * r][c].axis("on")
        axes[2 * r + 1][c].axis("on")
        draw_pose(axes[2 * r][c], F, "front", com, p.name if hasattr(p, "name") else None)
        draw_pose(axes[2 * r + 1][c], F, "side", com, None, lim=(-50, 70))
    fig.tight_layout(pad=0.3)
    fig.savefig(path, dpi=80)
    plt.close(fig)


def filmstrip(path, frames, count=10, title="", cols=10, view_span=None):
    """Evenly sampled frames of a clip (dicts with joints/root_pos), front row and side row."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    idx = np.linspace(0, len(frames) - 1, count).astype(int)
    fig, axes = plt.subplots(2, count, figsize=(count * 1.9, 4.8), squeeze=False)
    for k, i in enumerate(idx):
        fr = frames[i]
        F = rig.fk(fr["joints"], fr["root_pos"])
        c = rig.com(F)
        cx, cy = F["pelvis"][0, 3], F["pelvis"][1, 3]
        draw_pose(axes[0][k], F, "front", c, "%s t=%.2f" % (title, fr["t"]) if k == 0 else "t=%.2f" % fr["t"], lim=(cx - 45, cx + 45))
        draw_pose(axes[1][k], F, "side", c, None, lim=(cy - 55, cy + 55))
    fig.tight_layout(pad=0.3)
    fig.savefig(path, dpi=80)
    plt.close(fig)


def main():
    import argparse
    from . import poses
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "out", "preview"))
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    P = poses.all_poses()
    groups = {}
    for p in P:
        groups.setdefault(p.group, []).append(p)
    for g, lst in groups.items():
        sheet(os.path.join(a.out, "poses_%s.png" % g), lst, cols=min(8, len(lst)) if g != "swing" else 8)
        print("sheet", g, len(lst))
    from . import locomotion, damage, clips
    lib = {p.name: p for p in P}
    filmstrip(os.path.join(a.out, "clip_walk.png"), locomotion.walk_cycle("walk", 2).frames, 10, "walk")
    filmstrip(os.path.join(a.out, "clip_run.png"), locomotion.walk_cycle("run", 2).frames, 10, "run")
    filmstrip(os.path.join(a.out, "clip_limp_left_leg.png"), damage.limp_walk({"LegL": "Damaged"}, "walk", 4).frames, 10, "limp")
    filmstrip(os.path.join(a.out, "clip_turn_left.png"), locomotion.turn_in_place("left").frames, 10, "turn")
    for name in ("swing_up_right", "dodge_left", "fall_back"):
        c = clips.build_clip(name, clips.KEYS[name], lib)
        filmstrip(os.path.join(a.out, "clip_%s.png" % name), c["frames"], 10, name)
    print("clip strips done")


if __name__ == "__main__":
    main()
