"""Pure-numpy geometry kit for the shard library (no bpy): deterministic RNG and noise, convex solids built by half-space clipping,
tessellation with crack-free roughening, tube sweeps, UV island packing. Units: metres, +Z up, right-handed.

A `Solid` is a convex polyhedron: a list of `Face`s (CCW seen from outside). Library objects are unions of convex solids and tubes, all
accumulated into one triangle `Mesh` by `MB`."""
import math
import random

import numpy as np

EPS = 1e-9


# ------------------------------------------------------------------------------------------------------------------ rng / noise
def rng_for(*parts):
    """Independent deterministic stream per key (string seeding is stable across platforms)."""
    return random.Random("|".join(str(p) for p in parts))


def _h(ix, iy, iz, seed):
    n = (ix * 73856093) ^ (iy * 19349663) ^ (iz * 83492791) ^ (seed * 2654435761)
    n &= 0xFFFFFFFF
    n ^= n >> 15
    n = (n * 0x2C1B3C6D) & 0xFFFFFFFF
    n ^= n >> 12
    n = (n * 0x297A2D39) & 0xFFFFFFFF
    n ^= n >> 15
    return (n & 0xFFFFFF) / 0x7FFFFF - 1.0          # [-1, 1]


def vnoise(p, seed=0):
    """Smooth 3D value noise in [-1, 1] (integer-hash lattice, smoothstep interpolation)."""
    x, y, z = p
    ix, iy, iz = math.floor(x), math.floor(y), math.floor(z)
    fx, fy, fz = x - ix, y - iy, z - iz
    fx, fy, fz = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy), fz * fz * (3 - 2 * fz)
    c = [[[_h(ix + i, iy + j, iz + k, seed) for k in (0, 1)] for j in (0, 1)] for i in (0, 1)]
    x00 = c[0][0][0] * (1 - fx) + c[1][0][0] * fx
    x10 = c[0][1][0] * (1 - fx) + c[1][1][0] * fx
    x01 = c[0][0][1] * (1 - fx) + c[1][0][1] * fx
    x11 = c[0][1][1] * (1 - fx) + c[1][1][1] * fx
    y0 = x00 * (1 - fy) + x10 * fy
    y1 = x01 * (1 - fy) + x11 * fy
    return y0 * (1 - fz) + y1 * fz


def fbm(p, seed=0, octaves=3):
    a, f, s = 1.0, 1.0, 0.0
    tot = 0.0
    for o in range(octaves):
        s += a * vnoise((p[0] * f, p[1] * f, p[2] * f), seed + o * 17)
        tot += a
        a *= 0.5
        f *= 2.07
    return s / tot


def unit(v):
    v = np.asarray(v, float)
    n = float(np.linalg.norm(v))
    return v / n if n > EPS else np.array([0.0, 0.0, 1.0])


def rand_dir(r):
    while True:
        v = np.array([r.gauss(0, 1), r.gauss(0, 1), r.gauss(0, 1)])
        n = np.linalg.norm(v)
        if n > 1e-6:
            return v / n


def rot_axis(axis, ang):
    a = unit(axis)
    c, s = math.cos(ang), math.sin(ang)
    x, y, z = a
    return np.array([[c + x * x * (1 - c), x * y * (1 - c) - z * s, x * z * (1 - c) + y * s],
                     [y * x * (1 - c) + z * s, c + y * y * (1 - c), y * z * (1 - c) - x * s],
                     [z * x * (1 - c) - y * s, z * y * (1 - c) + x * s, c + z * z * (1 - c)]])


# ------------------------------------------------------------------------------------------------------------------ convex solids
class Face:
    __slots__ = ("v", "mat", "tag")

    def __init__(self, v, mat, tag=""):
        self.v = np.asarray(v, float)
        self.mat = mat
        self.tag = tag

    def normal(self):
        v = self.v
        n = np.zeros(3)
        for i in range(1, len(v) - 1):
            n += np.cross(v[i] - v[0], v[i + 1] - v[0])
        return unit(n)

    def area(self):
        v = self.v
        n = np.zeros(3)
        for i in range(1, len(v) - 1):
            n += np.cross(v[i] - v[0], v[i + 1] - v[0])
        return 0.5 * float(np.linalg.norm(n))

    def centroid(self):
        return self.v.mean(axis=0)


class Solid:
    def __init__(self, faces):
        self.faces = faces

    def copy(self):
        return Solid([Face(f.v.copy(), f.mat, f.tag) for f in self.faces])

    def verts(self):
        return np.concatenate([f.v for f in self.faces]) if self.faces else np.zeros((0, 3))

    def centroid(self):
        v = self.verts()
        return v.mean(axis=0)

    def volume(self):
        """Volume of the convex solid (divergence theorem over fan triangles)."""
        if not self.faces:
            return 0.0
        c = self.centroid()
        vol = 0.0
        for f in self.faces:
            for i in range(1, len(f.v) - 1):
                vol += abs(np.dot(f.v[0] - c, np.cross(f.v[i] - c, f.v[i + 1] - c))) / 6.0
        return vol

    def transformed(self, R=None, t=None, s=None):
        out = []
        for f in self.faces:
            v = f.v.copy()
            if s is not None:
                v = v * np.asarray(s)
            if R is not None:
                v = v @ np.asarray(R).T
            if t is not None:
                v = v + np.asarray(t)
            if s is not None and np.prod(s) < 0:
                v = v[::-1]
            out.append(Face(v, f.mat, f.tag))
        return Solid(out)


def box_solid(size, center=(0, 0, 0), mat="M_Fracture"):
    sx, sy, sz = (size[0] / 2, size[1] / 2, size[2] / 2)
    c = np.asarray(center, float)
    P = lambda x, y, z: c + np.array([x * sx, y * sy, z * sz])
    q = [([+1, -1, -1], [+1, +1, -1], [+1, +1, +1], [+1, -1, +1]),   # +x
         ([-1, +1, -1], [-1, -1, -1], [-1, -1, +1], [-1, +1, +1]),   # -x
         ([+1, +1, -1], [-1, +1, -1], [-1, +1, +1], [+1, +1, +1]),   # +y
         ([-1, -1, -1], [+1, -1, -1], [+1, -1, +1], [-1, -1, +1]),   # -y
         ([-1, -1, +1], [+1, -1, +1], [+1, +1, +1], [-1, +1, +1]),   # +z
         ([-1, +1, -1], [+1, +1, -1], [+1, -1, -1], [-1, -1, -1])]   # -z
    tags = ["+x", "-x", "+y", "-y", "+z", "-z"]
    return Solid([Face([P(*p) for p in face], mat, t) for face, t in zip(q, tags)])


def _clip_poly(pts, n, d):
    out = []
    k = len(pts)
    for i in range(k):
        a, b = pts[i], pts[(i + 1) % k]
        sa, sb = float(np.dot(n, a)) - d, float(np.dot(n, b)) - d
        if sa <= 1e-9:
            out.append(a)
        if (sa < -1e-9 and sb > 1e-9) or (sa > 1e-9 and sb < -1e-9):
            t = sa / (sa - sb)
            out.append(a + (b - a) * t)
    return out


def clip_solid(solid, n, d, cap_mat="M_Fracture", cap_tag="cut"):
    """Keeps the half-space n.x <= d of a convex solid; the new cap face gets `cap_mat`. Returns None when nothing is left."""
    n = unit(n)
    faces = []
    cut = []
    for f in solid.faces:
        pts = _clip_poly(list(f.v), n, d)
        if len(pts) >= 3:
            nf = Face(np.array(pts), f.mat, f.tag)
            if nf.area() > 1e-10:
                faces.append(nf)
        for p in pts:
            if abs(float(np.dot(n, p)) - d) < 1e-7:
                cut.append(p)
    if not faces:
        return None
    uniq = []
    for p in cut:
        if not any(np.linalg.norm(p - q) < 1e-6 for q in uniq):
            uniq.append(p)
    if len(uniq) >= 3:
        c = np.mean(uniq, axis=0)
        a1 = unit(uniq[0] - c)
        a2 = np.cross(n, a1)
        ang = [math.atan2(float(np.dot(p - c, a2)), float(np.dot(p - c, a1))) for p in uniq]
        order = np.argsort(ang)
        cap = Face(np.array([uniq[i] for i in order]), cap_mat, cap_tag)
        if cap.area() > 1e-10:
            faces.append(cap)
    if len(faces) < 4:
        return None
    return Solid(faces)


def rock_solid(r, extents, n_planes, jitter=0.18, lo=0.62, hi=0.97, mat="M_Fracture"):
    """Rock-like convex solid: a box of the given extents trimmed by tangent-ish planes of an ellipsoid with random radii."""
    ex = np.asarray(extents, float)
    s = box_solid(ex * 1.15, mat=mat)
    for _ in range(n_planes):
        d = rand_dir(r)
        sup = math.sqrt(sum((ex[i] / 2 * d[i]) ** 2 for i in range(3)))
        off = sup * r.uniform(lo, hi)
        d = unit(d + np.array([r.uniform(-jitter, jitter) for _ in range(3)]))
        res = clip_solid(s, d, off, cap_mat=mat)
        if res is not None and res.volume() > 0.25 * (ex[0] * ex[1] * ex[2]) * 0.5236:
            s = res
    return s


# ------------------------------------------------------------------------------------------------------------------ meshes
class MB:
    """Triangle accumulator: vertices deduplicated by position, per-triangle material / UV island / optional UV in metres."""

    def __init__(self, mats):
        self.mats = list(mats)
        self.P = []
        self.key = {}
        self.T = []
        self.M = []
        self.I = []
        self.UV = []
        self.n_isl = 0

    def vert(self, p):
        k = (round(float(p[0]) * 1e6), round(float(p[1]) * 1e6), round(float(p[2]) * 1e6))
        i = self.key.get(k)
        if i is None:
            i = len(self.P)
            self.key[k] = i
            self.P.append([float(p[0]), float(p[1]), float(p[2])])
        return i

    def island(self):
        self.n_isl += 1
        return self.n_isl - 1

    def tri(self, a, b, c, mat, isl, uv=None):
        if a == b or b == c or a == c:
            return
        self.T.append((a, b, c))
        self.M.append(self.mats.index(mat) if isinstance(mat, str) else mat)
        self.I.append(isl)
        self.UV.append(uv)

    def _cull_internal(self):
        """Removes back-to-back triangle pairs (faces of abutting solids hidden inside the object) and exact duplicates."""
        seen = {}
        for i, tr in enumerate(self.T):
            seen.setdefault(tuple(sorted(tr)), []).append(i)
        drop = set()
        for key, idx in seen.items():
            if len(idx) < 2:
                continue
            wind = {}
            for i in idx:
                a, b, c = self.T[i]
                cyc = min((a, b, c), (b, c, a), (c, a, b))
                wind.setdefault(cyc, []).append(i)
            if len(wind) >= 2:
                drop.update(idx)            # opposite windings: an internal wall
            else:
                drop.update(idx[1:])        # same winding: duplicate
        if drop:
            keep = [i for i in range(len(self.T)) if i not in drop]
            self.T = [self.T[i] for i in keep]
            self.M = [self.M[i] for i in keep]
            self.I = [self.I[i] for i in keep]
            self.UV = [self.UV[i] for i in keep]

    def finish(self, name, smooth=False):
        self._cull_internal()
        return Mesh(name, self.mats, np.array(self.P, float).reshape(-1, 3), np.array(self.T, int).reshape(-1, 3), np.array(self.M, int), np.array(self.I, int),
                    self.UV, smooth)


class Mesh:
    def __init__(self, name, mats, v, t, m, isl, uvm, smooth=False):
        self.name, self.mats, self.v, self.t, self.m, self.isl, self.uvm, self.smooth = name, mats, v, t, m, isl, uvm, smooth
        self.uv = None           # (T,3,2) in [0,1], set by pack_uv()

    def tris(self):
        return len(self.t)

    def bbox(self):
        return self.v.min(axis=0), self.v.max(axis=0)

    def signed_volume(self):
        a, b, c = self.v[self.t[:, 0]], self.v[self.t[:, 1]], self.v[self.t[:, 2]]
        return float(np.einsum("ij,ij->i", a, np.cross(b, c)).sum() / 6.0)

    def volume_centroid(self):
        """(volume, centroid). Closed outward-wound meshes give the true values; open / overlapping unions fall back to the area-weighted centroid."""
        a, b, c = self.v[self.t[:, 0]], self.v[self.t[:, 1]], self.v[self.t[:, 2]]
        dv = np.einsum("ij,ij->i", a, np.cross(b, c)) / 6.0
        vol = float(dv.sum())
        cen = ((a + b + c) / 4.0 * dv[:, None]).sum(axis=0)
        area = np.linalg.norm(np.cross(b - a, c - a), axis=1) / 2.0
        ac = ((a + b + c) / 3.0 * area[:, None]).sum(axis=0) / max(1e-12, area.sum())
        if vol > 1e-9 and np.all(np.isfinite(cen)):
            cen = cen / vol
            lo, hi = self.bbox()
            if np.all(cen > lo - 1e-6) and np.all(cen < hi + 1e-6):
                return vol, cen
        return abs(vol), ac

    def recentre(self, offset):
        self.v = self.v - np.asarray(offset)

    def area(self):
        a, b, c = self.v[self.t[:, 0]], self.v[self.t[:, 1]], self.v[self.t[:, 2]]
        return float((np.linalg.norm(np.cross(b - a, c - a), axis=1) / 2.0).sum())


def tessellate(mb, solid, level=0, rough=0.0, seed=0, old_tag=None, rough_old=0.2, base_mat=None, center=True, corner_jit=0.0):
    """Adds `solid` to `mb`: every face is a fan around its centroid, subdivided `level` times (x4 triangles each); non-corner vertices are displaced
    along the averaged normals of the incident faces by value-noise (crack-free: shared vertices get identical displacement). Faces tagged `old_tag`
    are roughened by `rough_old` times less (an original, finished surface). Each face is its own UV island."""
    faces = solid.faces
    if not center:      # cheap path: fan from the first vertex, no roughening
        isl_of = {}
        for fi, f in enumerate(faces):
            isl_of[fi] = mb.island()
            ids = [mb.vert(p) for p in f.v]
            for i in range(1, len(ids) - 1):
                mb.tri(ids[0], ids[i], ids[i + 1], base_mat if base_mat else f.mat, isl_of[fi])
        return isl_of
    vid = {}
    pos = []
    fnorm = []
    inc = []
    corner = []

    def vget(p, is_corner, f):
        k = (round(float(p[0]) * 1e6), round(float(p[1]) * 1e6), round(float(p[2]) * 1e6))
        i = vid.get(k)
        if i is None:
            i = len(pos)
            vid[k] = i
            pos.append(np.asarray(p, float))
            inc.append(set())
            corner.append(is_corner)
        if is_corner:
            corner[i] = True
        inc[i].add(f)
        return i

    tris = []
    for fi, f in enumerate(faces):
        fnorm.append(f.normal())
        ids = [vget(p, True, fi) for p in f.v]
        c = vget(f.v.mean(axis=0), False, fi)
        k = len(ids)
        for i in range(k):
            tris.append((c, ids[i], ids[(i + 1) % k], fi))
    mid = {}
    for _ in range(level):
        nt = []
        for a, b, c, fi in tris:
            def m(x, y):
                key = (min(x, y), max(x, y))
                if key not in mid:
                    mid[key] = vget((pos[x] + pos[y]) / 2.0, False, fi)
                else:
                    inc[mid[key]].add(fi)
                return mid[key]
            ab, bc, ca = m(a, b), m(b, c), m(c, a)
            nt += [(a, ab, ca, fi), (ab, b, bc, fi), (ca, bc, c, fi), (ab, bc, ca, fi)]
        tris = nt
        mid = {}
    if rough > 0:
        lo = np.min([p for p in pos], axis=0)
        hi = np.max([p for p in pos], axis=0)
        size = float(np.max(hi - lo))
        newpos = []
        for i, p in enumerate(pos):
            if corner[i]:
                if corner_jit > 0:        # corners move as a function of position only, so shared corners stay shared
                    q = p * (4.0 / max(size, 0.05))
                    jv = np.array([vnoise(q, seed + 101), vnoise(q, seed + 202), vnoise(q, seed + 303)])
                    fac = min((rough_old if (old_tag and faces[f].tag == old_tag) else 1.0) for f in inc[i])
                    p = p + jv * corner_jit * size * fac
                newpos.append(p)
                continue
            n = unit(sum(fnorm[f] for f in inc[i]))
            fac = min((rough_old if (old_tag and faces[f].tag == old_tag) else 1.0) for f in inc[i])
            amp = rough * size * fac
            d = amp * (0.7 * fbm(p * (3.0 / max(size, 0.05)) + 11.3, seed) + 0.3 * vnoise(p * (9.0 / max(size, 0.05)), seed + 5))
            newpos.append(p + n * d)
        pos = newpos
    isl_of = {}
    for a, b, c, fi in tris:
        if fi not in isl_of:
            isl_of[fi] = mb.island()
        mt = base_mat if base_mat else faces[fi].mat
        mb.tri(mb.vert(pos[a]), mb.vert(pos[b]), mb.vert(pos[c]), mt, isl_of[fi])
    return isl_of


# ------------------------------------------------------------------------------------------------------------------ tubes
def _frames(pts):
    """Rotation-minimising frames along a polyline: returns tangents and one normal per point."""
    pts = np.asarray(pts, float)
    n = len(pts)
    tan = np.zeros((n, 3))
    for i in range(n):
        a = pts[max(0, i - 1)]
        b = pts[min(n - 1, i + 1)]
        tan[i] = unit(b - a)
    nor = np.zeros((n, 3))
    ref = np.array([0.0, 0.0, 1.0]) if abs(tan[0][2]) < 0.9 else np.array([1.0, 0.0, 0.0])
    nor[0] = unit(np.cross(np.cross(tan[0], ref), tan[0]))
    for i in range(1, n):
        v = nor[i - 1] - np.dot(nor[i - 1], tan[i]) * tan[i]
        nor[i] = unit(v)
    return tan, nor


def ear_clip(poly):
    """Triangulates a simple 2D polygon (any orientation) by ear clipping; returns index triples wound like the input."""
    P = [tuple(map(float, p)) for p in poly]
    n = len(P)
    area = sum(P[i][0] * P[(i + 1) % n][1] - P[(i + 1) % n][0] * P[i][1] for i in range(n))
    idx = list(range(n)) if area > 0 else list(range(n - 1, -1, -1))
    out = []

    def cross(a, b, c):
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

    def inside(p, a, b, c):
        return cross(a, b, p) >= -1e-12 and cross(b, c, p) >= -1e-12 and cross(c, a, p) >= -1e-12

    guard = 0
    while len(idx) > 3 and guard < 10000:
        guard += 1
        for k in range(len(idx)):
            i0, i1, i2 = idx[k - 1], idx[k], idx[(k + 1) % len(idx)]
            a, b, c = P[i0], P[i1], P[i2]
            if cross(a, b, c) <= 1e-12:
                continue
            if any(inside(P[j], a, b, c) for j in idx if j not in (i0, i1, i2)):
                continue
            out.append((i0, i1, i2) if area > 0 else (i2, i1, i0))
            idx.pop(k)
            break
        else:
            break
    if len(idx) == 3:
        out.append((idx[0], idx[1], idx[2]) if area > 0 else (idx[2], idx[1], idx[0]))
    elif len(idx) > 3:
        for k in range(1, len(idx) - 1):
            out.append((idx[0], idx[k], idx[k + 1]))
    return out


def sweep(mb, pts, profile, mat, caps=(True, True), scale=None, twist=None, smooth_uv=True, ring_jitter=None, inner=False, shift=None):
    """Sweeps a closed 2D `profile` (k,2) along a polyline. scale[i] scales the profile at point i (default 1), twist[i] rotates it (radians).
    ring_jitter: optional (n_rings, k) array of per-vertex radial factors (used to ragged the broken end of tubes). UVs: u = perimeter, v = length in metres.
    Returns the first ring index list for further use. inner=True flips winding (inside surface of a pipe)."""
    pts = np.asarray(pts, float)
    prof = np.asarray(profile, float)
    k = len(prof)
    n = len(pts)
    tan, nor = _frames(pts)
    rings = []
    for i in range(n):
        s = 1.0 if scale is None else scale[i]
        a = 0.0 if twist is None else twist[i]
        b = np.cross(tan[i], nor[i])
        ca, sa = math.cos(a), math.sin(a)
        ring = []
        for j in range(k):
            x, y = prof[j]
            x, y = x * ca - y * sa, x * sa + y * ca
            f = 1.0 if ring_jitter is None else ring_jitter[i][j]
            p = pts[i] + (nor[i] * x + b * y) * s * f
            if shift is not None:
                p = p + tan[i] * shift[i][j]
            ring.append(p)
        rings.append(ring)
    per = np.cumsum([0.0] + [float(np.linalg.norm(prof[(j + 1) % k] - prof[j])) for j in range(k)])
    arc = np.concatenate([[0.0], np.cumsum([np.linalg.norm(pts[i + 1] - pts[i]) for i in range(n - 1)])])
    isl = mb.island()
    ids = [[mb.vert(p) for p in ring] for ring in rings]
    for i in range(n - 1):
        for j in range(k):
            j2 = (j + 1) % k
            a, b, c, d = ids[i][j], ids[i][j2], ids[i + 1][j2], ids[i + 1][j]
            u0, u1 = per[j], per[j + 1]
            v0, v1 = arc[i], arc[i + 1]
            if inner:
                mb.tri(a, c, b, mat, isl, uv=[(u0, v0), (u1, v1), (u1, v0)])
                mb.tri(a, d, c, mat, isl, uv=[(u0, v0), (u0, v1), (u1, v1)])
            else:
                mb.tri(a, b, c, mat, isl, uv=[(u0, v0), (u1, v0), (u1, v1)])
                mb.tri(a, c, d, mat, isl, uv=[(u0, v0), (u1, v1), (u0, v1)])
    tri2d = ear_clip(prof)
    for end, cap in ((0, caps[0]), (n - 1, caps[1])):
        if not cap:
            continue
        ci = mb.island()
        ring = rings[end]
        c = np.mean(ring, axis=0)
        b = np.cross(tan[end], nor[end])
        uvp = [(float(np.dot(x - c, nor[end])), float(np.dot(x - c, b))) for x in ring]
        for (ia, ib, ic) in tri2d:
            if end == 0:
                mb.tri(ids[end][ia], ids[end][ic], ids[end][ib], mat, ci, uv=[uvp[ia], uvp[ic], uvp[ib]])
            else:
                mb.tri(ids[end][ia], ids[end][ib], ids[end][ic], mat, ci, uv=[uvp[ia], uvp[ib], uvp[ic]])
    return ids


def circle(k, r=1.0, phase=0.0):
    return np.array([[r * math.cos(phase + 2 * math.pi * j / k), r * math.sin(phase + 2 * math.pi * j / k)] for j in range(k)])


# ------------------------------------------------------------------------------------------------------------------ UV packing
def pack_uv(mesh, margin=0.012, tile_m=None):
    """Assigns mesh.uv (T,3,2) in [0,1]: every island is planar-projected (or uses the metre UVs given by the builder), then shelf-packed with a margin.
    Islands never overlap by construction (disjoint rectangles); self-overlap of a single island is avoided by projecting onto its area-weighted plane
    (builders keep islands near-planar or give their own unrolled UVs)."""
    T = len(mesh.t)
    loc = np.zeros((T, 3, 2))
    for isl in np.unique(mesh.isl):
        idx = np.where(mesh.isl == isl)[0]
        if all(mesh.uvm[i] is not None for i in idx):
            for i in idx:
                loc[i] = np.asarray(mesh.uvm[i], float)
            continue
        A = mesh.v[mesh.t[idx, 0]]
        B = mesh.v[mesh.t[idx, 1]]
        C = mesh.v[mesh.t[idx, 2]]
        nrm = np.cross(B - A, C - A).sum(axis=0)
        n = unit(nrm)
        e = mesh.v[mesh.t[idx]].reshape(-1, 3)
        # u axis: the longest in-plane direction from the principal axis of the projected points
        P = e - n * (e @ n)[:, None]
        cen = P.mean(axis=0)
        cov = (P - cen).T @ (P - cen)
        w, V = np.linalg.eigh(cov)
        u = unit(V[:, 2] - n * np.dot(V[:, 2], n))
        v = np.cross(n, u)
        for i in idx:
            for c in range(3):
                p = mesh.v[mesh.t[i, c]]
                loc[i, c] = (float(np.dot(p, u)), float(np.dot(p, v)))
    isls = list(np.unique(mesh.isl))
    boxes = {}
    for isl in isls:
        idx = np.where(mesh.isl == isl)[0]
        pts = loc[idx].reshape(-1, 2)
        lo, hi = pts.min(axis=0), pts.max(axis=0)
        boxes[isl] = (lo, hi)
    pad = margin
    # unit scale so that the packed layout fits in 1x1: first compute in metres with padding proportional to the largest island
    big = max(max(hi[0] - lo[0], hi[1] - lo[1]) for lo, hi in boxes.values())
    padm = pad * big * 4.0
    order = sorted(isls, key=lambda i: -(boxes[i][1][1] - boxes[i][0][1]))
    area = sum((boxes[i][1][0] - boxes[i][0][0] + padm) * (boxes[i][1][1] - boxes[i][0][1] + padm) for i in order)
    width = max(math.sqrt(area) * 1.25, max(boxes[i][1][0] - boxes[i][0][0] + padm for i in order))
    x = y = rowh = 0.0
    place = {}
    for i in order:
        lo, hi = boxes[i]
        w, h = hi[0] - lo[0] + padm, hi[1] - lo[1] + padm
        if x + w > width + 1e-9:
            x = 0.0
            y += rowh
            rowh = 0.0
        place[i] = (x + padm / 2 - lo[0], y + padm / 2 - lo[1])
        x += w
        rowh = max(rowh, h)
    total_h = y + rowh
    s = 1.0 / max(width, total_h)
    uv = np.zeros((T, 3, 2))
    for isl in isls:
        idx = np.where(mesh.isl == isl)[0]
        ox, oy = place[isl]
        uv[idx] = (loc[idx] + np.array([ox, oy])) * s
    mesh.uv = uv
    mesh.uv_rects = {int(i): ((boxes[i][0] + np.array(place[i])) * s, (boxes[i][1] + np.array(place[i])) * s) for i in isls}
    return mesh
