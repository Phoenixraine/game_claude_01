"""Builders for every object of the shard library. Pure numpy (no bpy): each builder returns an `Asset` with a triangle `Mesh`, an optional UCX
collision solid and a few facts for the manifest. Everything is deterministic per (name, index)."""
import math

import numpy as np

from . import geom as g
from .geom import MB, Solid, Face, box_solid, clip_solid, rock_solid, rng_for, unit

MATS = ["M_Concrete_Old", "M_Fracture", "M_Glass_Shard", "M_Steel_Rust", "M_Rebar", "M_Gravel"]
DENSITY = {"M_Concrete_Old": 2400.0, "M_Fracture": 2400.0, "M_Glass_Shard": 2500.0, "M_Steel_Rust": 7850.0, "M_Rebar": 7850.0, "M_Gravel": 2600.0}
GROUPS = ["Concrete", "Structure", "Glass", "Gravel", "Metal"]


class Asset:
    def __init__(self, name, category, size_class, group, mesh, ucx=None, extra=None):
        self.name, self.category, self.size_class, self.group = name, category, size_class, group
        self.mesh, self.ucx, self.extra = mesh, ucx, extra or {}
        self.pivot = np.zeros(3)


def _mark_old(solid, tag="old", pick="largest"):
    fs = solid.faces
    if pick == "largest":
        k = max(range(len(fs)), key=lambda i: fs[i].area())
        fs[k].mat, fs[k].tag = "M_Concrete_Old", tag
    return solid


# ------------------------------------------------------------------------------------------------------------------ concrete shards
CONCRETE = {
    # size class: (longest extent range m, planes range, tessellation level, rough, triangle limits)
    "S": ((0.25, 0.60), (7, 11), 0, 0.15, (40, 120)),
    "M": ((0.60, 1.50), (3, 5), 1, 0.15, (60, 260)),
    "L": ((1.50, 4.00), (3, 6), 1, 0.13, (120, 380)),
    "XL": ((4.00, 10.0), (5, 8), 1, 0.11, (160, 400)),
}


def concrete_shard(cls, idx):
    (lo, hi), (pl0, pl1), level, rough, (tmin, tmax) = CONCRETE[cls]
    name = "Shard_Concrete_%s_%02d" % (cls, idx)
    for attempt in range(60):
        r = rng_for("shard", cls, idx, attempt)
        L = lo + (hi - lo) * (0.08 + 0.84 * (idx + r.uniform(-0.3, 0.3)) / 9.0) if idx < 10 else r.uniform(lo, hi)
        L = min(hi, max(lo, L))
        a, b = r.uniform(0.45, 1.0), r.uniform(0.18, 0.7)
        if r.random() < 0.35:
            b = r.uniform(0.12, 0.3)         # plate-like
        ex = np.array([L, L * a, L * b])
        ex = ex[r.sample(range(3), 3)]
        solid = rock_solid(r, ex, r.randint(pl0, pl1))
        _mark_old(solid)
        mb = MB(MATS)
        g.tessellate(mb, solid, level=level, rough=rough, seed=idx * 31 + len(cls), old_tag="old", rough_old=0.12, corner_jit=rough * 0.35)
        mesh = mb.finish(name)
        if tmin <= mesh.tris() <= tmax:
            return Asset(name, "Shard_Concrete", cls, "Concrete", mesh, ucx=solid, extra={"old_face": True})
    raise RuntimeError("could not meet the triangle budget for " + name)


# ------------------------------------------------------------------------------------------------------------------ rebar
def _bar_path(r, length, bends, p0=(0, 0, 0), d0=(0, 0, 1), n=8, drift=0.05):
    """Polyline of a rebar: starts at p0 going along d0, gentle random drift and `bends` sharp bends."""
    p = np.array(p0, float)
    d = unit(d0)
    pts = [p.copy()]
    bend_at = sorted(r.sample(range(1, n), min(bends, n - 1))) if bends else []
    for i in range(n):
        if i in bend_at:
            ax = unit(np.cross(d, g.rand_dir(r)))
            d = unit(g.rot_axis(ax, r.uniform(0.5, 1.2)) @ d)
        else:
            ax = unit(np.cross(d, g.rand_dir(r)))
            d = unit(g.rot_axis(ax, r.gauss(0, drift)) @ d)
        p = p + d * (length / n)
        pts.append(p.copy())
    return np.array(pts)


def _add_bar(mb, pts, radius, mat="M_Rebar", sides=6):
    k = len(pts)
    prof = g.circle(sides, radius)
    g.sweep(mb, pts, prof, mat)


def rebar_single(idx):
    name = "Rebar_Single_%02d" % idx
    r = rng_for("rebar", idx)
    mb = MB(MATS)
    pts = _bar_path(r, r.uniform(0.8, 3.0), r.choice([0, 1, 1, 2]), n=r.randint(7, 10), drift=0.06)
    _add_bar(mb, pts, r.uniform(0.008, 0.02), sides=6)
    return Asset(name, "Rebar_Single", "", "Structure", mb.finish(name))


def rebar_bundle(idx):
    name = "Rebar_Bundle_%02d" % idx
    r = rng_for("bundle", idx)
    mb = MB(MATS)
    n_bars = r.randint(5, 9)
    L = r.uniform(0.9, 2.2)
    rad = r.uniform(0.010, 0.016)
    base = _bar_path(r, L, 1, d0=(1, 0, 0), n=8, drift=0.02)
    spread = r.uniform(0.04, 0.08)
    for b in range(n_bars):
        a = 2 * math.pi * b / n_bars
        off = np.array([0.0, math.cos(a) * spread, math.sin(a) * spread])
        pts = base.copy()
        for i in range(len(pts)):
            t = i / (len(pts) - 1)
            pts[i] = pts[i] + off * (1.0 + 2.0 * t * t * r.uniform(0.6, 1.4))
        _add_bar(mb, pts, rad, sides=5)
    for t in (0.18, 0.55):                       # tie wires
        i = int(t * (len(base) - 1))
        c = base[i]
        ring = np.array([c + np.array([0, math.cos(a), math.sin(a)]) * (spread + rad * 1.5) for a in np.linspace(0, 2 * math.pi, 13)])
        g.sweep(mb, ring, g.circle(4, 0.004), "M_Rebar", caps=(False, False))
    return Asset(name, "Rebar_Bundle", "", "Structure", mb.finish(name))


# ------------------------------------------------------------------------------------------------------------------ slabs / columns
def slab(idx):
    name = "Slab_Concrete_%02d" % idx
    for attempt in range(40):
        r = rng_for("slab", idx, attempt)
        Lx, Ly, T = r.uniform(2.0, 4.2), r.uniform(1.4, 3.0), r.uniform(0.16, 0.30)
        s = box_solid((Lx * 1.2, Ly * 1.2, T), mat="M_Concrete_Old")
        for f in s.faces:
            if f.tag in ("+x", "-x", "+y", "-y"):
                f.mat = "M_Fracture"
        for _ in range(r.randint(3, 5)):                       # ragged outline: near-vertical cuts
            a = r.uniform(0, 2 * math.pi)
            nrm = unit([math.cos(a), math.sin(a), r.uniform(-0.25, 0.25)])
            sup = abs(nrm[0]) * Lx / 2 + abs(nrm[1]) * Ly / 2
            res = clip_solid(s, nrm, sup * r.uniform(0.72, 0.98))
            if res is not None and res.volume() > 0.45 * Lx * Ly * T:
                s = res
        for f in s.faces:
            if f.tag == "+z" or f.tag == "-z":
                f.mat, f.tag = "M_Concrete_Old", "old"
        mb = MB(MATS)
        g.tessellate(mb, s, level=1, rough=0.03, seed=idx, old_tag="old", rough_old=0.1)
        bars = 0
        for f in s.faces:                                       # rebars stick out of cut faces
            if f.mat != "M_Fracture" or f.area() < 0.06:
                continue
            n = f.normal()
            if abs(n[2]) > 0.6:
                continue
            c = f.centroid()
            tang = unit(np.cross(n, [0, 0, 1]))
            width = float(np.ptp(f.v @ tang))
            for _k in range(r.randint(2, 5)):
                off = tang * (r.uniform(-0.45, 0.45) * width) + np.array([0, 0, r.uniform(-0.3, 0.3) * T])
                p0 = c + off - n * 0.03
                d = unit(n + tang * r.uniform(-0.25, 0.25) + np.array([0, 0, r.uniform(-0.3, 0.3)]))
                pts = _bar_path(r, r.uniform(0.25, 0.9), r.choice([0, 1]), p0=p0, d0=d, n=4, drift=0.08)
                _add_bar(mb, pts, r.uniform(0.007, 0.012), sides=5)
                bars += 1
        mesh = mb.finish(name)
        if mesh.tris() <= 1400:
            return Asset(name, "Slab_Concrete", "", "Structure", mesh, ucx=s, extra={"rebars": bars})
    raise RuntimeError(name)


def column(idx):
    name = "Column_Broken_%02d" % idx
    for attempt in range(40):
        r = rng_for("column", idx, attempt)
        w, h = r.uniform(0.35, 0.7), r.uniform(1.5, 3.4)
        octa = idx % 2 == 1
        s = box_solid((w, w * r.uniform(0.9, 1.1), h), mat="M_Concrete_Old")
        for f in s.faces:
            if f.tag in ("+z", "-z"):
                f.mat = "M_Fracture"
        if octa:
            for k in range(4):
                a = math.pi / 4 + k * math.pi / 2
                s = clip_solid(s, [math.cos(a), math.sin(a), 0], w * 0.5 * 0.88, cap_mat="M_Concrete_Old", cap_tag="old") or s
        for f in s.faces:
            if f.mat == "M_Concrete_Old":
                f.tag = "old"
        for top in (True, False):                              # broken ends: tilted cuts (the bottom end only sometimes)
            if not top and r.random() < 0.5:
                continue
            for _ in range(r.randint(1, 3)):
                a = r.uniform(0, 2 * math.pi)
                tilt = r.uniform(0.35, 0.9)
                nrm = unit([math.cos(a) * math.sin(tilt), math.sin(a) * math.sin(tilt), math.cos(tilt) * (1 if top else -1)])
                off = (h / 2) * r.uniform(0.82, 0.97)
                s = clip_solid(s, nrm, off) or s
        mb = MB(MATS)
        g.tessellate(mb, s, level=1, rough=0.025, seed=idx + 3, old_tag="old", rough_old=0.1)
        top_faces = [f for f in s.faces if f.normal()[2] > 0.3 and f.mat == "M_Fracture"]
        nb = r.randint(4, 8)
        zt = max(float(f.v[:, 2].max()) for f in top_faces) if top_faces else h / 2
        ring_r = w * 0.36
        for b in range(nb):
            a = 2 * math.pi * b / nb + r.uniform(-0.1, 0.1)
            x, y = math.cos(a) * ring_r, math.sin(a) * ring_r
            z0 = zt - 0.15
            for f in s.faces:                                  # start inside the concrete under the cut
                pass
            pts = _bar_path(r, r.uniform(0.35, 1.0), r.choice([0, 1]), p0=(x, y, z0), d0=(math.cos(a) * 0.25, math.sin(a) * 0.25, 1), n=5, drift=0.07)
            _add_bar(mb, pts, r.uniform(0.009, 0.014), sides=5)
        for z in (zt + 0.12, zt + 0.32):                       # two stirrup rings around the exposed bars
            sq = [(-ring_r, -ring_r), (ring_r, -ring_r), (ring_r, ring_r), (-ring_r, ring_r), (-ring_r, -ring_r)]
            path = np.array([(x * 1.05, y * 1.05, z) for x, y in sq] + [(sq[0][0] * 1.05, sq[0][1] * 1.05, z)])
            g.sweep(mb, path[:5], g.circle(4, 0.005), "M_Rebar", caps=(False, False))
        mesh = mb.finish(name)
        if mesh.tris() <= 1400:
            return Asset(name, "Column_Broken", "", "Structure", mesh, ucx=s, extra={"bars": nb})
    raise RuntimeError(name)


# ------------------------------------------------------------------------------------------------------------------ glass / frames
def glass_shard(idx):
    name = "Glass_Shard_%02d" % idx
    r = rng_for("glass", idx)
    L = 0.02 + (0.40 - 0.02) * ((idx / 17.0) ** 1.6) * r.uniform(0.8, 1.1)
    L = min(0.40, max(0.02, L))
    k = r.choice([3, 3, 4, 5])
    aspect = r.choice([1.0, 0.7, 0.5, 0.3, 0.15])
    ang = sorted(r.uniform(0, 2 * math.pi) for _ in range(k))
    while True:
        gaps = [(ang[(i + 1) % k] - ang[i]) % (2 * math.pi) for i in range(k)]
        if max(gaps) < math.pi * 0.95:
            break
        ang = sorted(r.uniform(0, 2 * math.pi) for _ in range(k))
    poly = np.array([[math.cos(a) * L / 2 * r.uniform(0.7, 1.0), math.sin(a) * L / 2 * aspect * r.uniform(0.7, 1.0)] for a in ang])
    poly = poly * (L / max(1e-6, float((poly.max(axis=0) - poly.min(axis=0)).max())))     # longest side = L exactly
    t = r.uniform(0.003, 0.006)
    mb = MB(MATS)
    ids_t = [mb.vert((p[0], p[1], t / 2)) for p in poly]
    ids_b = [mb.vert((p[0], p[1], -t / 2)) for p in poly]
    it, ib = mb.island(), mb.island()
    for i in range(1, k - 1):
        mb.tri(ids_t[0], ids_t[i], ids_t[i + 1], "M_Glass_Shard", it)
        mb.tri(ids_b[0], ids_b[i + 1], ids_b[i], "M_Glass_Shard", ib)
    for i in range(k):
        j = (i + 1) % k
        isl = mb.island()
        mb.tri(ids_b[i], ids_b[j], ids_t[j], "M_Glass_Shard", isl)
        mb.tri(ids_b[i], ids_t[j], ids_t[i], "M_Glass_Shard", isl)
    return Asset(name, "Glass_Shard", "", "Glass", mb.finish(name))


def window_frame(idx):
    name = "Window_Frame_Broken_%02d" % idx
    for attempt in range(40):
        r = rng_for("wframe", idx, attempt)
        W, H = r.uniform(0.9, 1.6), r.uniform(1.1, 2.0)
        bar, dep = r.uniform(0.04, 0.07), r.uniform(0.05, 0.09)
        parts = [box_solid((bar, dep, H), (-W / 2 + bar / 2, 0, 0), "M_Steel_Rust"), box_solid((bar, dep, H), (W / 2 - bar / 2, 0, 0), "M_Steel_Rust"),
                 box_solid((W, dep, bar), (0, 0, H / 2 - bar / 2), "M_Steel_Rust"), box_solid((W, dep, bar), (0, 0, -H / 2 + bar / 2), "M_Steel_Rust"),
                 box_solid((W, dep * 0.8, bar * 0.7), (0, 0, r.uniform(-0.1, 0.2) * H), "M_Steel_Rust")]
        out = []
        for p in parts:
            for _ in range(r.randint(0, 2)):                   # tear: random cut planes, some members gone
                a = r.uniform(0, 2 * math.pi)
                nrm = unit([math.cos(a), r.uniform(-0.2, 0.2), math.sin(a)])
                p2 = clip_solid(p, nrm, r.uniform(-0.1, 0.5) * max(W, H) / 2 + 0.05, cap_mat="M_Steel_Rust")
                if p2 is not None:
                    p = p2
            if r.random() > 0.12:
                out.append(p)
        mb = MB(MATS)
        for p in out:
            g.tessellate(mb, p, center=False)
        for _ in range(r.randint(3, 6)):                       # glass fangs left in the frame
            x = r.uniform(-W / 2 + bar, W / 2 - bar)
            z = r.choice([-1, 1]) * (H / 2 - bar)
            hh = r.uniform(0.04, 0.16)
            w2 = r.uniform(0.02, 0.07)
            d = -1 if z > 0 else 1
            tri = [(x - w2, 0, z), (x + w2, 0, z), (x + r.uniform(-0.03, 0.03), 0, z + d * hh)]
            isl = mb.island()
            for side, th in ((1, 0.002), (-1, -0.002)):
                ids = [mb.vert((p[0], th, p[2])) for p in tri]
                if side == 1:
                    mb.tri(ids[0], ids[1], ids[2], "M_Glass_Shard", isl)
                else:
                    mb.tri(ids[0], ids[2], ids[1], "M_Glass_Shard", mb.island())
        mesh = mb.finish(name)
        if mesh.tris() <= 1400 and mesh.tris() > 20:
            return Asset(name, "Window_Frame_Broken", "", "Glass", mesh)
    raise RuntimeError(name)


# ------------------------------------------------------------------------------------------------------------------ gravel
def _pebble_solid(r, size, angular, planes=None):
    ex = np.array([size, size * r.uniform(0.55, 1.0), size * r.uniform(0.35, 0.8)])
    ex = ex[r.sample(range(3), 3)]
    if planes is None:
        planes = r.randint(4, 7) if angular else r.randint(9, 12)
    return rock_solid(r, ex, planes, lo=0.55 if angular else 0.78, hi=0.92 if angular else 0.97, mat="M_Gravel")


def pebble(idx):
    name = "Pebble_%02d" % idx
    for attempt in range(60):
        r = rng_for("pebble", idx, attempt)
        angular = idx % 3 == 0
        size = r.uniform(0.03, 0.12)
        s = _pebble_solid(r, size, angular)
        mb = MB(MATS)
        g.tessellate(mb, s, center=False)
        m = mb.finish(name, smooth=not angular)
        if 20 <= m.tris() <= 60:
            return Asset(name, "Pebble", "", "Gravel", m, extra={"angular": angular})
    raise RuntimeError(name)


def _cluster(idx, n, rad):
    r = rng_for("cluster", idx, "stones")
    mb = MB(MATS)
    for k in range(n):
        size = r.uniform(0.03, 0.08)
        s = _pebble_solid(r, size, True, planes=r.randint(2, 4))
        a = r.uniform(0, 2 * math.pi)
        d = rad * math.sqrt(r.random())
        R = g.rot_axis(g.rand_dir(r), r.uniform(0, 2 * math.pi))
        s = s.transformed(R=R)
        zmin = float(s.verts()[:, 2].min())
        lift = 0.05 * (1 - (d / rad) ** 2) * r.random()              # stones rest on the mound / on each other: lowest point at the local pile height
        s = s.transformed(t=[math.cos(a) * d, math.sin(a) * d, lift - zmin])
        g.tessellate(mb, s, center=False)
    return mb.finish("Gravel_Cluster_%02d" % idx)


def gravel_cluster(idx):
    name = "Gravel_Cluster_%02d" % idx
    r = rng_for("cluster", idx)
    n = r.randint(30, 80)
    rad = r.uniform(0.15, 0.32)
    mesh = _cluster(idx, n, rad)
    while mesh.tris() > 1450 and n > 30:        # keep the whole cluster inside the per-mesh budget
        n -= 3
        mesh = _cluster(idx, n, rad)
    mesh.name = name
    return Asset(name, "Gravel_Cluster", "", "Gravel", mesh, extra={"stones": n})


# ------------------------------------------------------------------------------------------------------------------ steel plates
def _bent_plate(mb, name_mat, W, H, t, nx, ny, bend_x, bend_ang, bend_r, ripple, r, jag=0.0, seed=0, mat="M_Steel_Rust"):
    """Thick plate: a grid bent along x = bend_x (smooth arc), optional ripple and a jagged right edge. Returns the corner vertex lists."""
    xs = np.linspace(-W / 2, W / 2, nx + 1)
    ys = np.linspace(-H / 2, H / 2, ny + 1)
    def surf(x, y, row):
        xe = x
        if jag > 0 and x > 0:
            xe = x * (1 - jag * (0.5 + 0.5 * g.vnoise((row * 1.7, 0.3, seed), seed)))
        # fold: for xe beyond bend_x the plate rotates by bend_ang about the line, joined by an arc of radius bend_r
        s = xe - bend_x
        arc = bend_r * bend_ang
        if s <= -arc / 2:
            px, pz = xe, 0.0
        elif s >= arc / 2:
            a2 = bend_ang
            ex = bend_x - arc / 2 + bend_r * math.sin(a2)
            ez = bend_r * (1 - math.cos(a2))
            rem = s - arc / 2
            px, pz = ex + rem * math.cos(a2), ez + rem * math.sin(a2)
        else:
            a = (s + arc / 2) / bend_r
            px, pz = bend_x - arc / 2 + bend_r * math.sin(a), bend_r * (1 - math.cos(a))
        pz += ripple * math.sin(y * 7.0 + x * 3.0)
        return np.array([px, y, pz])
    top = [[surf(x, y, j) for x in xs] for j, y in enumerate(ys)]
    # normals for the thickness offset
    def nrm(i, j):
        i0, i1 = max(0, i - 1), min(nx, i + 1)
        j0, j1 = max(0, j - 1), min(ny, j + 1)
        du = top[j][i1] - top[j][i0]
        dv = top[j1][i] - top[j0][i]
        return unit(np.cross(du, dv))
    bot = [[top[j][i] - nrm(i, j) * t for i in range(nx + 1)] for j in range(ny + 1)]
    isl_t, isl_b = mb.island(), mb.island()
    arcx = [0.0]
    for i in range(nx):
        arcx.append(arcx[-1] + float(np.linalg.norm(top[ny // 2][i + 1] - top[ny // 2][i])))
    ysv = [y - ys[0] for y in ys]
    for j in range(ny):
        for i in range(nx):
            a, b, c, d = (mb.vert(top[j][i]), mb.vert(top[j][i + 1]), mb.vert(top[j + 1][i + 1]), mb.vert(top[j + 1][i]))
            uv = lambda p, q: (arcx[p], ysv[q])
            mb.tri(a, b, c, mat, isl_t, uv=[uv(i, j), uv(i + 1, j), uv(i + 1, j + 1)])
            mb.tri(a, c, d, mat, isl_t, uv=[uv(i, j), uv(i + 1, j + 1), uv(i, j + 1)])
            a, b, c, d = (mb.vert(bot[j][i]), mb.vert(bot[j][i + 1]), mb.vert(bot[j + 1][i + 1]), mb.vert(bot[j + 1][i]))
            mb.tri(a, c, b, mat, isl_b, uv=[uv(i, j), uv(i + 1, j + 1), uv(i + 1, j)])
            mb.tri(a, d, c, mat, isl_b, uv=[uv(i, j), uv(i, j + 1), uv(i + 1, j + 1)])
    def side(p0, p1, q0, q1, length):
        isl = mb.island()
        a, b, c, d = mb.vert(p0), mb.vert(p1), mb.vert(q1), mb.vert(q0)
        mb.tri(a, b, c, mat, isl, uv=[(0, 0), (length, 0), (length, t)])
        mb.tri(a, c, d, mat, isl, uv=[(0, 0), (length, t), (0, t)])
    for i in range(nx):      # bottom edge y=-H/2 and top edge y=+H/2
        L = float(np.linalg.norm(top[0][i + 1] - top[0][i]))
        side(top[0][i + 1], top[0][i], bot[0][i + 1], bot[0][i], L)
        side(top[ny][i], top[ny][i + 1], bot[ny][i], bot[ny][i + 1], L)
    for j in range(ny):
        L = float(np.linalg.norm(top[j + 1][0] - top[j][0]))
        side(top[j][0], top[j + 1][0], bot[j][0], bot[j + 1][0], L)
        L = float(np.linalg.norm(top[j + 1][nx] - top[j][nx]))
        side(top[j + 1][nx], top[j][nx], bot[j + 1][nx], bot[j][nx], L)
    return top, bot


def steel_plate(idx):
    name = "Steel_Plate_Bent_%02d" % idx
    r = rng_for("plate", idx)
    W, H, t = r.uniform(0.6, 2.4), r.uniform(0.5, 1.6), r.uniform(0.008, 0.03)
    mb = MB(MATS)
    _bent_plate(mb, name, W, H, t, 9, 6, r.uniform(-0.15, 0.25) * W, r.uniform(0.35, 1.2), r.uniform(0.05, 0.25), r.uniform(0.004, 0.02), r, jag=r.uniform(0.0, 0.3), seed=idx)
    return Asset(name, "Steel_Plate_Bent", "", "Metal", mb.finish(name))


def sign_torn(idx):
    name = "Sign_Torn_%02d" % idx
    r = rng_for("sign", idx)
    W, H, t = r.uniform(1.4, 3.4), r.uniform(0.8, 1.6), 0.03
    mb = MB(MATS)
    _bent_plate(mb, name, W, H, t, 10, 5, r.uniform(0.1, 0.35) * W, r.uniform(0.25, 0.9), r.uniform(0.1, 0.3), 0.01, r, jag=r.uniform(0.1, 0.45), seed=idx + 9)
    fr = 0.05
    for (c, s) in (((0, -H / 2 - fr / 2, 0.0), (W * 0.95, fr, 0.06)), ((0, H / 2 + fr / 2, 0.0), (W * 0.7, fr, 0.06)), ((-W / 2 - fr / 2, 0, 0.0), (fr, H, 0.06))):
        b = box_solid(s, c, "M_Steel_Rust")
        a = r.uniform(0, 2 * math.pi)
        b = clip_solid(b, [math.cos(a), math.sin(a), 0.0], r.uniform(0.2, 0.5) * max(s), cap_mat="M_Steel_Rust") or b
        g.tessellate(mb, b, center=False)
    for sx in (-0.3, 0.3):
        arm = _bar_path(r, r.uniform(0.35, 0.7), 1, p0=(sx * W, 0, -t), d0=(0, 0.2, -1), n=4, drift=0.1)
        g.sweep(mb, arm, g.circle(6, 0.02), "M_Steel_Rust")
    return Asset(name, "Sign_Torn", "", "Metal", mb.finish(name))


def girder(idx):
    name = "Girder_Twisted_%02d" % idx
    r = rng_for("girder", idx)
    L = r.uniform(2.0, 6.0)
    w, d = r.uniform(0.14, 0.30), r.uniform(0.2, 0.42)
    tf, tw = r.uniform(0.012, 0.022), r.uniform(0.008, 0.014)
    prof = np.array([(-w / 2, -d / 2), (w / 2, -d / 2), (w / 2, -d / 2 + tf), (tw / 2, -d / 2 + tf), (tw / 2, d / 2 - tf), (w / 2, d / 2 - tf), (w / 2, d / 2), (-w / 2, d / 2),
                     (-w / 2, d / 2 - tf), (-tw / 2, d / 2 - tf), (-tw / 2, -d / 2 + tf), (-w / 2, -d / 2 + tf)])
    n = r.randint(12, 16)
    ts = np.linspace(0, 1, n)
    bendA, bendB = r.uniform(-0.25, 0.25) * L, r.uniform(-0.15, 0.15) * L
    pts = np.array([[L * t, bendA * math.sin(math.pi * t) + 0.15 * L * t * t, bendB * math.sin(math.pi * t * 1.3)] for t in ts])
    tw_tot = r.uniform(0.5, 1.4) * r.choice([-1, 1])
    twist = [tw_tot * (t ** 1.7) for t in ts]
    jit = np.ones((n, len(prof)))
    shift = np.zeros((n, len(prof)))
    for end in (0, n - 1):
        for j in range(len(prof)):
            shift[end][j] = r.uniform(-0.12, 0.12) * (1 if end else -1) * d
            jit[end][j] = r.uniform(0.85, 1.05)
    mb = MB(MATS)
    g.sweep(mb, pts, prof, "M_Steel_Rust", twist=twist, ring_jitter=jit, shift=shift)
    return Asset(name, "Girder_Twisted", "", "Metal", mb.finish(name))


def pipe(idx):
    name = "Pipe_Broken_%02d" % idx
    r = rng_for("pipe", idx)
    R = r.uniform(0.04, 0.20)
    wall = R * r.uniform(0.12, 0.22)
    L = r.uniform(1.0, 3.0)
    n = r.randint(9, 13)
    ts = np.linspace(0, 1, n)
    ang = r.uniform(0.3, 1.1)
    bend_at = r.uniform(0.35, 0.65)
    pts = []
    p = np.zeros(3)
    d = np.array([1.0, 0, 0])
    ax = unit([0, r.uniform(-0.3, 0.3), 1])
    for i in range(n):
        pts.append(p.copy())
        t = ts[i]
        s = 1.0 / (1.0 + math.exp(-(t - bend_at) * 14))
        dd = g.rot_axis(ax, ang * s) @ d
        p = p + dd * (L / (n - 1))
    pts = np.array(pts)
    k = 14
    shift_o = np.zeros((n, k))
    for end in (0, n - 1):
        for j in range(k):
            shift_o[end][j] = r.uniform(0.0, 0.5) * R * (1 if end else -1) * (1 if r.random() < 0.8 else 0)
    mb = MB(MATS)
    outer = g.sweep(mb, pts, g.circle(k, R), "M_Steel_Rust", caps=(False, False), shift=shift_o)
    inner = g.sweep(mb, pts, g.circle(k, R - wall), "M_Steel_Rust", caps=(False, False), shift=shift_o, inner=True)
    isl = mb.island()
    for end, flip in ((0, True), (n - 1, False)):
        for j in range(k):
            j2 = (j + 1) % k
            a, b, c, d2 = outer[end][j], outer[end][j2], inner[end][j2], inner[end][j]
            if flip:
                mb.tri(a, c, b, "M_Steel_Rust", isl, uv=[(j * 0.1, end), (j * 0.1 + 0.1, end + wall), (j * 0.1 + 0.1, end)])
                mb.tri(a, d2, c, "M_Steel_Rust", isl, uv=[(j * 0.1, end), (j * 0.1, end + wall), (j * 0.1 + 0.1, end + wall)])
            else:
                mb.tri(a, b, c, "M_Steel_Rust", isl, uv=[(j * 0.1, end), (j * 0.1 + 0.1, end), (j * 0.1 + 0.1, end + wall)])
                mb.tri(a, c, d2, "M_Steel_Rust", isl, uv=[(j * 0.1, end), (j * 0.1 + 0.1, end + wall), (j * 0.1, end + wall)])
    return Asset(name, "Pipe_Broken", "", "Metal", mb.finish(name))


def cable(idx):
    name = "Cable_Dangling_%02d" % idx
    r = rng_for("cable", idx)
    L = r.uniform(1.0, 4.0)
    sag = r.uniform(0.15, 0.5) * L
    n = 18
    kinks = [r.uniform(-0.03, 0.03) for _ in range(n)]
    pts = np.array([[L * t, 0.02 * math.sin(t * 9 + idx) + kinks[i] * 0.4, -sag * 4 * t * (1 - t) * (1 - 0.3 * t) + 0.0] for i, t in enumerate(np.linspace(0, 1, n))])
    rad = r.uniform(0.008, 0.02)
    mb = MB(MATS)
    g.sweep(mb, pts, g.circle(5, rad), "M_Rebar", caps=(True, False))
    end = pts[-1]
    dirv = unit(pts[-1] - pts[-2])
    for _ in range(3):                                        # frayed wires
        d = unit(dirv + g.rand_dir(r) * 0.6)
        fp = np.array([end, end + d * r.uniform(0.05, 0.15) * 0.5, end + d * r.uniform(0.08, 0.2)])
        g.sweep(mb, fp, g.circle(3, rad * 0.35), "M_Rebar")
    clamp = box_solid((0.06, 0.05, 0.05), pts[0] - [0.02, 0, 0], "M_Steel_Rust")
    g.tessellate(mb, clamp, center=False)
    return Asset(name, "Cable_Dangling", "", "Metal", mb.finish(name))


# ------------------------------------------------------------------------------------------------------------------ facade panels / AC
PANEL = {"S": (2.0, 2.6, 2, 2), "M": (3.2, 3.9, 3, 3), "L": (4.8, 5.6, 4, 4)}


def facade_panel(cls, var):
    name = "Panel_Facade_Torn_%s_%02d" % (cls, var)
    for attempt in range(40):
        r = rng_for("panel", cls, var, attempt)
        W, H, cols, rows = PANEL[cls]
        dep = r.uniform(0.22, 0.34)
        fw, fh = W / cols, H / rows
        ww, wh = fw * 0.62, fh * 0.56
        solids = []
        for rr in range(rows):                                  # spandrel (floor band) under each window row
            z0 = -H / 2 + rr * fh
            solids.append(box_solid((W, dep, fh - wh), (0, 0, z0 + (fh - wh) / 2), "M_Concrete_Old"))
            for cc in range(cols + 1):                          # piers between windows
                x = -W / 2 + cc * fw
                pw = (fw - ww) / (2 if 0 < cc < cols else 1)
                xc = x + (pw / 2 if cc == 0 else -pw / 2 if cc == cols else 0.0)
                if cc == 0:
                    xc = -W / 2 + pw / 2
                elif cc == cols:
                    xc = W / 2 - pw / 2
                solids.append(box_solid((pw if 0 < cc < cols else pw, dep, wh), (xc, 0, z0 + (fh - wh) + wh / 2), "M_Concrete_Old"))
        solids.append(box_solid((W, dep, fh - wh), (0, 0, H / 2 - (fh - wh) / 2 + 0.0), "M_Concrete_Old") if False else box_solid((W, dep * 0.9, 0.05), (0, 0, H / 2), "M_Concrete_Old"))
        frames = []
        for rr in range(rows):
            for cc in range(cols):
                cx = -W / 2 + (cc + 0.5) * fw
                cz = -H / 2 + rr * fh + (fh - wh) + wh / 2
                if r.random() < 0.18:
                    continue
                b = 0.045
                frames += [box_solid((b, 0.07, wh), (cx - ww / 2 + b / 2, 0, cz), "M_Steel_Rust"), box_solid((b, 0.07, wh), (cx + ww / 2 - b / 2, 0, cz), "M_Steel_Rust"),
                           box_solid((ww, 0.07, b), (cx, 0, cz - wh / 2 + b / 2), "M_Steel_Rust"), box_solid((ww, 0.07, b), (cx, 0, cz + wh / 2 - b / 2), "M_Steel_Rust")]
        planes = []
        for _ in range(r.randint(2, 4)):
            a = r.uniform(0, 2 * math.pi)
            nrm = unit([math.cos(a), r.uniform(-0.08, 0.08), math.sin(a)])
            sup = abs(nrm[0]) * W / 2 + abs(nrm[2]) * H / 2
            planes.append((nrm, sup * r.uniform(0.62, 0.92)))
        mb = MB(MATS)
        for s in solids + frames:
            keep = s
            for nrm, off in planes:
                keep = clip_solid(keep, nrm, off, cap_mat="M_Fracture" if keep.faces[0].mat != "M_Steel_Rust" else "M_Steel_Rust")
                if keep is None:
                    break
            if keep is None:
                continue
            for f in keep.faces:
                if f.mat == "M_Concrete_Old" and f.tag in ("+y", "-y"):
                    pass
                elif f.mat == "M_Concrete_Old":
                    f.mat = "M_Fracture" if f.tag == "cut" else "M_Concrete_Old"
            g.tessellate(mb, keep, center=False)
        mesh = mb.finish(name)
        if 100 < mesh.tris() <= 1450:
            return Asset(name, "Panel_Facade_Torn", cls, "Structure", mesh, extra={"windows": cols * rows})
    raise RuntimeError(name)


def ac_unit(idx):
    name = "AC_Unit_Broken_%02d" % idx
    r = rng_for("ac", idx)
    W, D, H = r.uniform(0.7, 1.0), r.uniform(0.28, 0.4), r.uniform(0.55, 0.8)
    body = box_solid((W, D, H), mat="M_Steel_Rust")
    for _ in range(r.randint(1, 2)):                          # crushed corner
        a = r.choice([-1, 1]), r.choice([-1, 1])
        nrm = unit([a[0], r.uniform(-0.4, 0.4), a[1]])
        body = clip_solid(body, nrm, (abs(nrm[0]) * W + abs(nrm[2]) * H) / 2 * r.uniform(0.7, 0.9), cap_mat="M_Steel_Rust") or body
    mb = MB(MATS)
    g.tessellate(mb, body, center=False)
    rr = H * 0.34
    c = np.array([r.uniform(-0.1, 0.1) * W, -D / 2 - 0.01, 0.0])
    ring = np.array([c + [math.cos(a) * rr, 0, math.sin(a) * rr] for a in np.linspace(0, 2 * math.pi, 17)])
    g.sweep(mb, ring, g.circle(5, 0.012), "M_Steel_Rust", caps=(False, False))
    for k in range(r.randint(3, 5)):                          # grille bars, some bent
        a = math.pi * k / 4 + r.uniform(-0.2, 0.2)
        p0 = c + [math.cos(a) * rr, 0, math.sin(a) * rr]
        p1 = c - [math.cos(a) * rr, 0, math.sin(a) * rr]
        mid = (p0 + p1) / 2 + [0, -r.uniform(0.0, 0.08), 0]
        g.sweep(mb, np.array([p0, mid, p1]), g.circle(4, 0.007), "M_Steel_Rust")
    leg = _bar_path(r, r.uniform(0.3, 0.7), 1, p0=(W * 0.3, D / 2, -H / 2), d0=(0, 0.6, -1), n=4, drift=0.1)
    g.sweep(mb, leg, g.circle(6, 0.025), "M_Steel_Rust")
    leg2 = _bar_path(r, r.uniform(0.3, 0.7), 1, p0=(-W * 0.3, D / 2, -H / 2), d0=(0, 0.2, -1), n=4, drift=0.1)
    g.sweep(mb, leg2, g.circle(6, 0.025), "M_Steel_Rust")
    return Asset(name, "AC_Unit_Broken", "", "Metal", mb.finish(name))


# ------------------------------------------------------------------------------------------------------------------ library
COUNTS = {"Concrete": 10, "Slab": 8, "Column": 8, "Bundle": 6, "Single": 10, "Glass": 18, "Frame": 6, "Pebble": 30, "Cluster": 8, "Plate": 8, "Girder": 6, "Pipe": 6, "Cable": 6,
          "Panel": 3, "AC": 4, "Sign": 5}


def build_library():
    out = []
    for cls in ("S", "M", "L", "XL"):
        for i in range(COUNTS["Concrete"]):
            out.append(concrete_shard(cls, i))
    for i in range(COUNTS["Slab"]):
        out.append(slab(i))
    for i in range(COUNTS["Column"]):
        out.append(column(i))
    for i in range(COUNTS["Bundle"]):
        out.append(rebar_bundle(i))
    for i in range(COUNTS["Single"]):
        out.append(rebar_single(i))
    for i in range(COUNTS["Glass"]):
        out.append(glass_shard(i))
    for i in range(COUNTS["Frame"]):
        out.append(window_frame(i))
    for i in range(COUNTS["Pebble"]):
        out.append(pebble(i))
    for i in range(COUNTS["Cluster"]):
        out.append(gravel_cluster(i))
    for i in range(COUNTS["Plate"]):
        out.append(steel_plate(i))
    for i in range(COUNTS["Girder"]):
        out.append(girder(i))
    for i in range(COUNTS["Pipe"]):
        out.append(pipe(i))
    for i in range(COUNTS["Cable"]):
        out.append(cable(i))
    for cls in ("S", "M", "L"):
        for i in range(COUNTS["Panel"]):
            out.append(facade_panel(cls, i))
    for i in range(COUNTS["AC"]):
        out.append(ac_unit(i))
    for i in range(COUNTS["Sign"]):
        out.append(sign_torn(i))
    for a in out:
        finalize(a)
    return out


def finalize(a):
    """Pivot at the centre of mass (UCX moves with it), UV packing, mass hint."""
    vol, cen = a.mesh.volume_centroid()
    a.pivot = cen
    a.mesh.recentre(cen)
    if a.ucx is not None:
        a.ucx = a.ucx.transformed(t=-cen)
    g.pack_uv(a.mesh)
    dens = {}
    for m, t in zip(a.mesh.m, a.mesh.t):
        v = a.mesh.v[t]
        ar = float(np.linalg.norm(np.cross(v[1] - v[0], v[2] - v[0])) / 2)
        dens[a.mesh.mats[m]] = dens.get(a.mesh.mats[m], 0.0) + ar
    main = max(dens, key=dens.get)
    a.extra["volume_m3"] = vol
    a.extra["mass_kg"] = vol * DENSITY[main]
    return a
