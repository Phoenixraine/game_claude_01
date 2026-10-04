"""Renders the small PNG previews in previews/ from the tables (matplotlib; deterministic). Run: python3 data/damage_fx/make_previews.py"""
import math
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import fxmath as fx

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "previews")
BG, FG, GRID = "#0b1016", "#cfe3ee", "#233241"
COL = ["#5b7a8c", "#3fb6d6", "#ffd34e", "#ff8a3d", "#ff3b3b"]
plt.rcParams.update({"figure.facecolor": BG, "axes.facecolor": BG, "axes.edgecolor": GRID, "axes.labelcolor": FG, "xtick.color": FG, "ytick.color": FG, "text.color": FG,
                     "axes.grid": True, "grid.color": GRID, "font.size": 8, "savefig.facecolor": BG})


def norm(v):
    return math.sqrt(sum(c * c for c in v))


def shake_png():
    fig, ax = plt.subplots(2, 3, figsize=(11, 5.2), dpi=90)
    for sev in range(5):
        s = fx.shake_for_event("HitEvent", 22.0, "Torso", severity=sev, seed=4, direction="Left")
        ax[0][0].plot(s["t"], [norm(p) for p in s["pos_cm"]], color=COL[sev], label="S%d" % sev)
        ax[0][1].plot(s["t"], [norm(r) for r in s["rot_deg"]], color=COL[sev])
        ax[0][2].plot(s["t"], s["chroma"], color=COL[sev])
    L = fx.table("shake_profiles")["limits"]
    ax[0][0].axhline(L["max_pos_cm"], color="#ff3b3b", ls="--", lw=0.8)
    ax[0][1].axhline(L["max_rot_deg"], color="#ff3b3b", ls="--", lw=0.8)
    ax[0][0].set_title("|position| cm (limit 12)")
    ax[0][1].set_title("|rotation| deg (limit 4)")
    ax[0][2].set_title("chromatic aberration 0..1")
    ax[0][0].legend(loc="upper right")
    for i, ev in enumerate(["BladesClash", "Knockdown", "UltimateFinisher"]):
        for sev in (1, 3, 4):
            s = fx.shake_for_event(ev, 25.0, "Torso", severity=sev, seed=2)
            ax[1][i].plot(s["t"], [norm(p) for p in s["pos_cm"]], color=COL[sev], label="S%d" % sev)
        ax[1][i].set_title(ev + " |pos| cm")
        ax[1][i].set_xlabel("s")
    ax[1][0].legend()
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "shake_curves.png"))
    plt.close(fig)

    fig, ax = plt.subplots(1, 2, figsize=(11, 3.2), dpi=90)
    zs = ["Head", "ShoulderL", "ShoulderR", "LegL", "Reactor"]
    shakes = [fx.shake_for_event("HitEvent", 40.0, z, severity=4, seed=i) for i, z in enumerate(zs)]
    m = fx.mix_shakes(shakes, [0.0, 0.03, 0.06, 0.1, 0.15])
    raw_n = max(int(round(o * 120)) + len(s["t"]) for s, o in zip(shakes, [0.0, 0.03, 0.06, 0.1, 0.15]))
    raw = [[0.0, 0.0, 0.0] for _ in range(raw_n)]
    for s, o in zip(shakes, [0.0, 0.03, 0.06, 0.1, 0.15]):
        k = int(round(o * 120))
        for i, p in enumerate(s["pos_cm"]):
            for a in range(3):
                raw[k + i][a] += p[a]
    ax[0].plot([i / 120 for i in range(raw_n)], [norm(p) for p in raw], color="#5b7a8c", label="sum without limiter")
    ax[0].plot(m["t"], [norm(p) for p in m["pos_cm"]], color="#ff8a3d", label="mixed + limited")
    ax[0].axhline(12, color="#ff3b3b", ls="--", lw=0.8)
    ax[0].set_title("5 S4 hits within 0.15 s: |pos| cm")
    ax[0].legend()
    for i, sev in enumerate((2, 4)):
        s = fx.shake_for_event("HitEvent", 40.0, "Torso", severity=sev, seed=3)
        for a, name in enumerate(("right", "up", "fwd")):
            ax[1].plot(s["t"], [p[a] for p in s["pos_cm"]], color=COL[sev], alpha=0.5 + 0.2 * a, lw=0.9)
    ax[1].set_title("components right/up/fwd, S2 (blue) and S4 (red)")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "shake_mix.png"))
    plt.close(fig)


def cockpit_png():
    fig, ax = plt.subplots(2, 1, figsize=(11, 6.4), dpi=90, gridspec_kw={"height_ratios": [1, 1.6]})
    for sev in range(5):
        cv = fx.red_light_curve(sev)
        ax[0].plot([t for t, _ in cv], [v for _, v in cv], color=COL[sev], label="S%d" % sev)
    ax[0].set_title("red cockpit light (peak, pulsing, fade)")
    ax[0].legend(ncol=5)
    st = None
    rows = []
    for i, sev in enumerate((2, 3, 4)):
        cmds, st = fx.plan_cockpit_effects(sev, 10 + i, st)
        st = dict(st, time=st["time"] + 6.0)
        rows += cmds
    cmds, st = fx.plan_fire_spread(st, 5, 20.0, 4)
    rows += cmds
    kinds = sorted({c["action"] for c in rows})
    cmap = {k: plt.cm.tab20(i / max(1, len(kinds))) for i, k in enumerate(kinds)}
    for c in rows:
        y = kinds.index(c["action"])
        ax[1].barh(y, max(c["duration_s"], 0.15), left=c["t"], height=0.6, color=cmap[c["action"]], alpha=0.8)
    ax[1].set_yticks(range(len(kinds)))
    ax[1].set_yticklabels(kinds)
    ax[1].set_title("cockpit commands: S2 at 0 s, S3 at ~6 s, S4 at ~12 s, then the fire spreads (%d commands)" % len(rows))
    ax[1].set_xlabel("s")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "cockpit_timeline.png"))
    plt.close(fig)


def chunks_png():
    fig, ax = plt.subplots(1, 2, figsize=(11, 4.4), dpi=90)
    R = fx.table("mech_chunks")["ballistics"]["owner_capsule_radius_m"]["default"]
    for a in ax:
        a.add_patch(plt.Rectangle((-R, 0), 2 * R, 85, color="#1b2a38"))
        a.add_patch(plt.Rectangle((-42 - R, 0), 2 * R, 85, color="#1b2a38"))
        a.set_aspect("equal")
    cases = [("LimbSevered ArmL", {"type": "LimbSevered", "zone": "ArmL"}), ("ReactorBreach (back)", {"type": "ReactorBreach"})]
    enemy = {"x": 0.0, "y": -42.0, "r": R, "h": 85.0}
    owner = {"x": 0.0, "y": 0.0, "r": R, "h": 85.0}
    for a, (title, e) in zip(ax, cases):
        n = 0
        for seed in range(6):
            for c in fx.plan_chunks(e, seed):
                r = fx.simulate_chunk(c, [owner, enemy])
                a.plot([p[1] for p in r["points"]], [p[2] for p in r["points"]], color="#ff8a3d" if c["fire"]["on"] else "#6fb7d6", lw=0.7, alpha=0.8)
                n += 1
        a.set_xlim(-150, 100)
        a.set_ylim(0, 110)
        a.set_title("%s: %d chunks, 6 seeds" % (title, n))
        a.set_xlabel("y, m (side view; grey = mechs 42 m apart, attacker at -42)")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "chunks_trajectories.png"))
    plt.close(fig)


def building_png():
    B = fx.table("building_destruction")
    fig, ax = plt.subplots(1, 3, figsize=(11, 3.6), dpi=90)
    energies = [30, 100, 300, 1000, 3000, 10000, 30000, 1e5]
    for kind, col in zip(B["scenarios"], COL):
        ax[0].plot(energies, [fx.plan_building_break(kind, e, (0, -1, 0), {}, 1)["totals"]["large_shards"] for e in energies], marker="o", ms=3, color=col, label=kind)
        ax[1].plot(energies, [fx.plan_building_break(kind, e, (0, -1, 0), {}, 1)["totals"]["small_shards"] for e in energies], marker="o", ms=3, color=col)
        ax[2].plot(energies, [fx.plan_building_break(kind, e, (0, -1, 0), {}, 1)["totals"]["smoke_puffs"] for e in energies], marker="o", ms=3, color=col)
    for a, cap, t in zip(ax, (B["budgets"]["large_shards"], B["budgets"]["small_shards"], B["budgets"]["smoke_puffs"]), ("large shards", "small shards", "smoke puffs")):
        a.axhline(cap, color="#ff3b3b", ls="--", lw=0.8)
        a.set_xscale("log")
        a.set_title("%s (budget %d)" % (t, cap))
        a.set_xlabel("energy, kJ")
    ax[0].legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "building_budgets.png"))
    plt.close(fig)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    shake_png()
    cockpit_png()
    chunks_png()
    building_png()
    print("previews written to", OUT)
