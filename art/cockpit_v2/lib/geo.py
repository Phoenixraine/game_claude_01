"""Pure numpy geometry kit for the cockpit v2 parts (no bpy): meshes as triangle soups with per-triangle material and UV, primitives, tubes, a few
helpers. Units: metres. Blender axes: +X right, -Y forward (the pilot looks along -Y), +Z up; the pilot's eye is the origin (contract of TASK-003)."""
import math
import random

import numpy as np

EPS = 1e-9


def V(x, y=None, z=None):
    if y is None:
        return np.array(x, float)
    return np.array([x, y, z], float)


def unit(v):
    v = np.asarray(v, float)
    n = float(np.linalg.norm(v))
    return v / n if n > EPS else np.array([0.0, 0.0, 1.0])


def frame_from(direction, hint=(0.0, 0.0, 1.0)):
    """Right-handed orthonormal frame (x = direction, y, z) with z as close to `hint` as possible."""
    x = unit(direction)
    h = np.asarray(hint, float)
    z = h - x * float(np.dot(h, x))
    if np.linalg.norm(z) < 1e-6:
        z = np.array([0.0, 1.0, 0.0]) if abs(x[1]) < 0.9 else np.array([1.0, 0.0, 0.0])
        z = z - x * float(np.dot(z, x))
    z = unit(z)
    y = np.cross(z, x)
    return np.stack([x, y, z], axis=1)          # columns


def rot_axis(axis, ang):
    a = unit(axis)
    c, s = math.cos(ang), math.sin(ang)
    x, y, z = a
    return np.array([[c + x * x * (1 - c), x * y * (1 - c) - z * s, x * z * (1 - c) + y * s],
                     [y * x * (1 - c) + z * s, c + y * y * (1 - c), y * z * (1 - c) - x * s],
                     [z * x * (1 - c) - y * s, z * y * (1 - c) + x * s, c + z * z * (1 - c)]])


def mat_to_quat(R):
    m = R
    t = m[0, 0] + m[1, 1] + m[2, 2]
    if t > 0:
        s = math.sqrt(t + 1.0) * 2
        q = [0.25 * s, (m[2, 1] - m[1, 2]) / s, (m[0, 2] - m[2, 0]) / s, (m[1, 0] - m[0, 1]) / s]
    elif m[0, 0] > m[1, 1] and m[0, 0] > m[2, 2]:
        s = math.sqrt(1.0 + m[0, 0] - m[1, 1] - m[2, 2]) * 2
        q = [(m[2, 1] - m[1, 2]) / s, 0.25 * s, (m[0, 1] + m[1, 0]) / s, (m[0, 2] + m[2, 0]) / s]
    elif m[1, 1] > m[2, 2]:
        s = math.sqrt(1.0 + m[1, 1] - m[0, 0] - m[2, 2]) * 2
        q = [(m[0, 2] - m[2, 0]) / s, (m[0, 1] + m[1, 0]) / s, 0.25 * s, (m[1, 2] + m[2, 1]) / s]
    else:
        s = math.sqrt(1.0 + m[2, 2] - m[0, 0] - m[1, 1]) * 2
        q = [(m[1, 0] - m[0, 1]) / s, (m[0, 2] + m[2, 0]) / s, (m[1, 2] + m[2, 1]) / s, 0.25 * s]
    n = math.sqrt(sum(v * v for v in q))
    return [v / n for v in q]            # w, x, y, z


class MB:
    """Triangle accumulator with deduplicated vertices, per-triangle material index and optional UVs ((3,2) in metres or 0..1)."""

    def __init__(self, mats):
        self.mats = list(mats)
        self.P = []
        self.key = {}
        self.T = []
        self.M = []
        self.UV = []

    def mat(self, name):
        if name not in self.mats:
            self.mats.append(name)
        return self.mats.index(name)

    def vert(self, p):
        k = (round(float(p[0]) * 1e5), round(float(p[1]) * 1e5), round(float(p[2]) * 1e5))
        i = self.key.get(k)
        if i is None:
            i = len(self.P)
            self.key[k] = i
            self.P.append((float(p[0]), float(p[1]), float(p[2])))
        return i

    def tri(self, a, b, c, mat, uv=None):
        pa, pb, pc = self.P[a], self.P[b], self.P[c]
        if a == b or b == c or a == c:
            return
        self.T.append((a, b, c))
        self.M.append(self.mat(mat) if isinstance(mat, str) else mat)
        if uv is None:
            n = np.cross(np.subtract(pb, pa), np.subtract(pc, pa))
            ax = int(np.argmax(np.abs(n)))
            idx = [i for i in (0, 1, 2) if i != ax]
            uv = [(p[idx[0]], p[idx[1]]) for p in (pa, pb, pc)]
        self.UV.append(uv)

    def quad(self, p0, p1, p2, p3, mat, uv=None):
        a, b, c, d = (self.vert(p) for p in (p0, p1, p2, p3))
        if uv is None:
            self.tri(a, b, c, mat)
            self.tri(a, c, d, mat)
        else:
            self.tri(a, b, c, mat, [uv[0], uv[1], uv[2]])
            self.tri(a, c, d, mat, [uv[0], uv[2], uv[3]])

    def tris(self):
        return len(self.T)

    def merge(self, other, offset=None):
        ids = {}
        for k, p in enumerate(other.P):
            ids[k] = self.vert(p if offset is None else np.add(p, offset))
        for (a, b, c), m, uv in zip(other.T, other.M, other.UV):
            self.tri(ids[a], ids[b], ids[c], other.mats[m], uv)

    def arrays(self):
        return (np.array(self.P, float).reshape(-1, 3), np.array(self.T, int).reshape(-1, 3), np.array(self.M, int), np.array(self.UV, float).reshape(-1, 3, 2))

    def bbox(self):
        p = np.array(self.P)
        return p.min(axis=0), p.max(axis=0)

    def transform(self, R=None, t=None):
        out = MB(self.mats)
        for (a, b, c), m, uv in zip(self.T, self.M, self.UV):
            ps = []
            for k in (a, b, c):
                p = np.asarray(self.P[k], float)
                if R is not None:
                    p = R @ p
                if t is not None:
                    p = p + np.asarray(t)
                ps.append(p)
            out.tri(out.vert(ps[0]), out.vert(ps[1]), out.vert(ps[2]), self.mats[m], uv)
        return out


# ------------------------------------------------------------------------------------------------------------------ primitives
def add_box(mb, c, size, R=None, mat="M_Metal", chamfer=0.0):
    """Box of `size` (x,y,z) centred at c, rotated by the 3x3 matrix R. chamfer > 0 cuts the 12 edges (44 triangles)."""
    c = np.asarray(c, float)
    R = np.eye(3) if R is None else np.asarray(R, float)
    hx, hy, hz = (size[0] / 2.0, size[1] / 2.0, size[2] / 2.0)
    w = lambda x, y, z: c + R @ np.array([x, y, z])
    if chamfer <= 0 or chamfer * 2.2 >= min(size):
        v = {(sx, sy, sz): w(sx * hx, sy * hy, sz * hz) for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)}
        faces = [((1, -1, -1), (1, 1, -1), (1, 1, 1), (1, -1, 1)), ((-1, 1, -1), (-1, -1, -1), (-1, -1, 1), (-1, 1, 1)),
                 ((1, 1, -1), (-1, 1, -1), (-1, 1, 1), (1, 1, 1)), ((-1, -1, -1), (1, -1, -1), (1, -1, 1), (-1, -1, 1)),
                 ((-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1)), ((-1, 1, -1), (1, 1, -1), (1, -1, -1), (-1, -1, -1))]
        for f in faces:
            mb.quad(v[f[0]], v[f[1]], v[f[2]], v[f[3]], mat)
        return
    cc = chamfer
    # inner box corners at (h - cc); each original corner expands to 3 vertices (one per face it touches)
    def P(sx, sy, sz, ax):
        x = sx * (hx - (cc if ax != 0 else 0.0))
        y = sy * (hy - (cc if ax != 1 else 0.0))
        z = sz * (hz - (cc if ax != 2 else 0.0))
        return w(x, y, z)
    # main faces (shrunk by the chamfer): normal axis ax, sign s
    for ax in (0, 1, 2):
        for s in (-1, 1):
            others = [a for a in (0, 1, 2) if a != ax]
            pts = []
            for (a, b) in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                sg = [0, 0, 0]
                sg[ax] = s
                sg[others[0]] = a
                sg[others[1]] = b
                pts.append(P(sg[0], sg[1], sg[2], ax))
            if (s > 0) == (ax != 1):
                mb.quad(pts[0], pts[1], pts[2], pts[3], mat)
            else:
                mb.quad(pts[0], pts[3], pts[2], pts[1], mat)
    # edge chamfers: along axis e, between faces on axes a and b
    for e in (0, 1, 2):
        a, b = [x for x in (0, 1, 2) if x != e]
        for sa in (-1, 1):
            for sb in (-1, 1):
                pts = []
                for se in (-1, 1):
                    for (fa, fb) in ((a, b), (b, a)):
                        pass
                # quad: two points on the face-a side, two on the face-b side
                def pt(se, on_axis):
                    sg = [0, 0, 0]
                    sg[e] = se
                    sg[a] = sa
                    sg[b] = sb
                    return P(sg[0], sg[1], sg[2], on_axis)
                q = [pt(-1, a), pt(1, a), pt(1, b), pt(-1, b)]
                n = np.cross(q[1] - q[0], q[3] - q[0])
                out = R @ np.array([sa if a == 0 else sb if b == 0 else 0, sa if a == 1 else sb if b == 1 else 0, sa if a == 2 else sb if b == 2 else 0])
                if np.dot(n, out) < 0:
                    q = [q[0], q[3], q[2], q[1]]
                mb.quad(q[0], q[1], q[2], q[3], mat)
    # corner triangles
    for sx in (-1, 1):
        for sy in (-1, 1):
            for sz in (-1, 1):
                t = [P(sx, sy, sz, 0), P(sx, sy, sz, 1), P(sx, sy, sz, 2)]
                n = np.cross(t[1] - t[0], t[2] - t[0])
                out = R @ np.array([sx, sy, sz], float)
                if np.dot(n, out) < 0:
                    t = [t[0], t[2], t[1]]
                mb.tri(mb.vert(t[0]), mb.vert(t[1]), mb.vert(t[2]), mat)


def add_cyl(mb, p0, p1, r0, r1=None, seg=12, mat="M_Metal", caps=(True, True)):
    p0, p1 = np.asarray(p0, float), np.asarray(p1, float)
    r1 = r0 if r1 is None else r1
    d = p1 - p0
    L = float(np.linalg.norm(d))
    if L < 1e-6:
        return
    F = frame_from(d)
    u, v = F[:, 1], F[:, 2]
    ring0 = [p0 + (u * math.cos(2 * math.pi * k / seg) + v * math.sin(2 * math.pi * k / seg)) * r0 for k in range(seg)]
    ring1 = [p1 + (u * math.cos(2 * math.pi * k / seg) + v * math.sin(2 * math.pi * k / seg)) * r1 for k in range(seg)]
    for k in range(seg):
        k2 = (k + 1) % seg
        mb.quad(ring0[k], ring0[k2], ring1[k2], ring1[k], mat)
    if caps[0] and r0 > 0:
        c = mb.vert(p0)
        for k in range(seg):
            mb.tri(c, mb.vert(ring0[(k + 1) % seg]), mb.vert(ring0[k]), mat)
    if caps[1] and r1 > 0:
        c = mb.vert(p1)
        for k in range(seg):
            mb.tri(c, mb.vert(ring1[k]), mb.vert(ring1[(k + 1) % seg]), mat)


def add_sphere(mb, c, r, seg=10, mat="M_Metal", squash=1.0, top_only=False):
    c = np.asarray(c, float)
    rings = max(3, seg // 2)
    pts = []
    for i in range(rings + 1):
        th = math.pi * i / rings
        if top_only:
            th = (math.pi / 2) * i / rings
        row = [c + np.array([r * math.sin(th) * math.cos(2 * math.pi * k / seg), r * math.sin(th) * math.sin(2 * math.pi * k / seg), r * squash * math.cos(th)]) for k in range(seg)]
        pts.append(row)
    for i in range(rings):
        for k in range(seg):
            k2 = (k + 1) % seg
            mb.quad(pts[i][k], pts[i + 1][k], pts[i + 1][k2], pts[i][k2], mat)      # outward winding (rings run from the +z pole to the equator and beyond)
    if top_only:       # close the bottom with a disc
        cc = mb.vert(c)
        for k in range(seg):
            mb.tri(cc, mb.vert(pts[-1][k]), mb.vert(pts[-1][(k + 1) % seg]), mat)


def smooth_path(pts, per_seg=6):
    """Catmull-Rom through the points (open ends doubled)."""
    P = [np.asarray(p, float) for p in pts]
    if len(P) < 3:
        return np.array(P)
    Q = [P[0]] + P + [P[-1]]
    out = []
    for i in range(1, len(Q) - 2):
        p0, p1, p2, p3 = Q[i - 1], Q[i], Q[i + 1], Q[i + 2]
        for k in range(per_seg):
            t = k / per_seg
            t2, t3 = t * t, t * t * t
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 + (-p0 + 3 * p1 - 3 * p2 + p3) * t3))
    out.append(P[-1])
    return np.array(out)


def path_length(path):
    return float(sum(np.linalg.norm(path[i + 1] - path[i]) for i in range(len(path) - 1)))


def tube_frames(path):
    n = len(path)
    tan = np.zeros((n, 3))
    for i in range(n):
        a = path[max(0, i - 1)]
        b = path[min(n - 1, i + 1)]
        tan[i] = unit(b - a)
    nor = np.zeros((n, 3))
    ref = np.array([0.0, 0.0, 1.0]) if abs(tan[0][2]) < 0.9 else np.array([1.0, 0.0, 0.0])
    nor[0] = unit(np.cross(np.cross(tan[0], ref), tan[0]))
    for i in range(1, n):
        v = nor[i - 1] - np.dot(nor[i - 1], tan[i]) * tan[i]
        nor[i] = unit(v)
    return tan, nor


def add_tube(mb, path, radius, seg=8, mat="M_Metal", caps=(True, True), taper=None):
    """Tube along a polyline. radius: float or per-point array. UV: u = around, v = metres along."""
    path = np.asarray(path, float)
    n = len(path)
    rad = np.full(n, float(radius)) if np.isscalar(radius) else np.asarray(radius, float)
    tan, nor = tube_frames(path)
    rings = []
    for i in range(n):
        b = np.cross(tan[i], nor[i])
        rings.append([path[i] + (nor[i] * math.cos(2 * math.pi * k / seg) + b * math.sin(2 * math.pi * k / seg)) * rad[i] for k in range(seg)])
    arc = [0.0]
    for i in range(n - 1):
        arc.append(arc[-1] + float(np.linalg.norm(path[i + 1] - path[i])))
    for i in range(n - 1):
        for k in range(seg):
            k2 = (k + 1) % seg
            a, b, c, d = (mb.vert(rings[i][k]), mb.vert(rings[i][k2]), mb.vert(rings[i + 1][k2]), mb.vert(rings[i + 1][k]))
            u0, u1 = k / seg, (k + 1) / seg
            mb.tri(a, b, c, mat, [(u0, arc[i]), (u1, arc[i]), (u1, arc[i + 1])])
            mb.tri(a, c, d, mat, [(u0, arc[i]), (u1, arc[i + 1]), (u0, arc[i + 1])])
    for end, cap in ((0, caps[0]), (n - 1, caps[1])):
        if not cap or rad[end] <= 0:
            continue
        c = mb.vert(path[end])
        for k in range(seg):
            k2 = (k + 1) % seg
            if end == 0:
                mb.tri(c, mb.vert(rings[end][k2]), mb.vert(rings[end][k]), mat)
            else:
                mb.tri(c, mb.vert(rings[end][k]), mb.vert(rings[end][k2]), mat)
    return rings


def point_on(path, s):
    """Point and tangent at arc length s."""
    acc = 0.0
    for i in range(len(path) - 1):
        l = float(np.linalg.norm(path[i + 1] - path[i]))
        if acc + l >= s or i == len(path) - 2:
            t = 0.0 if l < 1e-9 else max(0.0, min(1.0, (s - acc) / l))
            return path[i] + (path[i + 1] - path[i]) * t, unit(path[i + 1] - path[i])
        acc += l
    return path[-1], unit(path[-1] - path[-2])


def sub_path(path, s0, s1, step=0.05):
    """Resampled piece of a polyline between arc lengths s0 and s1."""
    n = max(2, int((s1 - s0) / step) + 1)
    return np.array([point_on(path, s0 + (s1 - s0) * k / (n - 1))[0] for k in range(n)])
