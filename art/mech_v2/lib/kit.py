"""Detail kit for BASTION v2: conforming armour shells (variable chamfer, crown, taper, dents), bolts, ribs, vent slats, panel inserts.
Everything is placed on a `forms.Tube` surface by parameters (u along the axis, v = angle in degrees) so plates follow the organic body."""
import math

import bpy  # noqa: F401  (must come before mathutils/bmesh when used as a module)
import random

from mathutils import Vector

from . import forms, hs
from .forms import Sec, Tube, _add_vert, _face


def vt(secs, n=28, ref=(1, 0, 0)):
    """Vertical tube: sections sorted bottom -> top, so v = 270 deg is the FRONT (-Y), 90 deg the back (+Y), 0 deg +X, 180 deg -X."""
    secs = sorted(secs, key=lambda s: s.c.z)
    return Tube(secs, n, ref)


PLATE_SCALE = 0.78
RES_SCALE = 1.6       # plate grid resolution multiplier
RIVET_SPACING = 3.6   # metres between edge rivets (0 = off)
FRONT, BACK, LEFT, RIGHT = 270.0, 90.0, 0.0, 180.0


def mirror_secs(secs):
    return [Sec((-s.c.x, s.c.y, s.c.z), s.rx, s.ry, s.power, -s.twist, s.flat_front, (-s.shift[0], s.shift[1])) for s in secs]


# --------------------------------------------------------------------------------------------------- patch
def patch(part, surf, u, v, off, th, cham=(1, 1, 1, 1), nu=5, nv=6, taper=0.0, crown=0.0, mat=None, dent=0.0, seed=0, skew=0.0, bottom=True,
          cham_w=0.2, lip=0.45, hfn=None):
    """A shell plate floating `off` above `surf`. u = (u0, u1) along the tube (0..1), v = (a0, a1) angles in degrees.
    `cham` = relative chamfer width for the (u0, u1, v0, v1) edges, `taper` narrows the v range linearly towards u1 (trapezoid),
    `skew` shifts the v range with u (parallelogram), `crown` raises the middle of the top, `dent` crumples it (dent variant).
    Returns (top grid, rim loop points) for decorations."""
    bm = part.bm
    mi = part._mi(mat or part.mat)
    rng = random.Random(seed)
    u0, u1 = u
    a0, a1 = [math.radians(a) for a in v]
    dv0, dv1 = a1 - a0, None

    def vrange(uu):
        f = (uu - u0) / (u1 - u0) if u1 != u0 else 0.0
        mid = (a0 + a1) * 0.5 + skew * math.radians(1.0) * f * (a1 - a0)
        half = (a1 - a0) * 0.5 * (1.0 - taper * f)
        return mid - half, mid + half

    def P(s, t, h, shrink=(0, 0, 0, 0)):
        # s,t in 0..1 over the plate; shrink = chamfer insets (u0,u1,v0,v1) in plate fractions
        s2 = shrink[0] + (1 - shrink[0] - shrink[1]) * s
        t2 = shrink[2] + (1 - shrink[2] - shrink[3]) * t
        uu = u0 + (u1 - u0) * s2
        va, vb = vrange(uu)
        vv = va + (vb - va) * t2
        return surf.point(uu, vv) + surf.normal(uu, vv) * h

    shr = tuple(c * cham_w for c in cham)

    def height(s, t):
        if hfn is not None:
            return hfn(s, t)
        k = 1.0 - ((2 * s - 1) ** 2 + (2 * t - 1) ** 2) * 0.5
        return off + th + crown * max(k, 0.0)

    top = [[None] * (nv + 1) for _ in range(nu + 1)]
    dent_pts = [(rng.random(), rng.random(), rng.uniform(0.25, 0.6)) for _ in range(5)] if dent else []
    for i in range(nu + 1):
        for j in range(nv + 1):
            s, t = i / nu, j / nv
            h = height(s, t)
            if dent:
                d = 0.0
                for ds, dt, r in dent_pts:
                    d += math.exp(-(((s - ds) ** 2 + (t - dt) ** 2) / (r * r * 0.25)))
                h -= dent * min(d, 1.4) * th * 2.2 + rng.uniform(-0.1, 0.1) * dent * th
            top[i][j] = _add_vert(bm, P(s, t, h, shr))
    rim_idx = [(i, 0) for i in range(nu + 1)] + [(nu, j) for j in range(1, nv + 1)] + [(i, nv) for i in range(nu - 1, -1, -1)] + [(0, j) for j in range(nv - 1, 0, -1)]
    rim = [_add_vert(bm, P(i / nu, j / nv, off + th * lip)) for i, j in rim_idx]
    base = [_add_vert(bm, P(i / nu, j / nv, off)) for i, j in rim_idx]
    topb = [top[i][j] for i, j in rim_idx]
    m = len(rim_idx)
    for i in range(nu):
        for j in range(nv):
            _face(bm, [top[i][j], top[i + 1][j], top[i + 1][j + 1], top[i][j + 1]], mi)
    for k in range(m):
        k2 = (k + 1) % m
        _face(bm, [topb[k], topb[k2], rim[k2], rim[k]], mi)
        _face(bm, [rim[k], rim[k2], base[k2], base[k]], mi)
    if bottom:
        if abs(a1 - a0) > math.radians(90):
            # wide curved plate: the underside follows the surface (a single n-gon would cut across the arc and break the volume)
            bidx = {rim_idx[k]: base[k] for k in range(m)}
            bot = [[bidx.get((i, j)) or _add_vert(bm, P(i / nu, j / nv, off)) for j in range(nv + 1)] for i in range(nu + 1)]
            for i in range(nu):
                for j in range(nv):
                    _face(bm, [bot[i][j + 1], bot[i + 1][j + 1], bot[i + 1][j], bot[i][j]], mi, 2)
        else:
            _face(bm, list(reversed(base)), mi, 2)
    return P, height


def bolt(part, pos, normal, r=0.28, h=0.2, segs=6, mat="M_DarkMetal"):
    pos, n = Vector(pos), Vector(normal).normalized()
    up = Vector((0, 0, 1)) if abs(n.z) < 0.9 else Vector((1, 0, 0))
    a = n.cross(up).normalized()
    b = n.cross(a)
    ring0 = [pos + (a * math.cos(2 * math.pi * k / segs) + b * math.sin(2 * math.pi * k / segs)) * r for k in range(segs)]
    ring1 = [pos + n * h + (a * math.cos(2 * math.pi * k / segs) + b * math.sin(2 * math.pi * k / segs)) * r * 0.82 for k in range(segs)]
    forms.add_rings(part, [ring0, ring1], True, True, mat, tag=1)


def bolts_on(part, P, height, pts, r=0.28, h=0.2, mat="M_DarkMetal", segs=6, shr=(0, 0, 0, 0)):
    """Bolts at points (s, t) of the flat TOP of a plate (fractions of the top domain, i.e. inside the chamfer)."""
    for s, t in pts:
        s, t = shr[0] + (1 - shr[0] - shr[1]) * s, shr[2] + (1 - shr[2] - shr[3]) * t
        p = P(s, t, height(s, t))
        px = P(min(1.0, s + 0.02), t, height(min(1.0, s + 0.02), t)) - P(max(0.0, s - 0.02), t, height(max(0.0, s - 0.02), t))
        py = P(s, min(1.0, t + 0.02), height(s, min(1.0, t + 0.02))) - P(s, max(0.0, t - 0.02), height(s, max(0.0, t - 0.02)))
        n = px.cross(py)
        if n.length < 1e-9:
            continue
        n.normalize()
        # orient outward: away from the surface point below
        below = P(s, t, 0.0)
        if n.dot(p - below) < 0:
            n = -n
        bolt(part, p - n * 0.03, n, r, h, segs, mat)


def rivet(part, pos, normal, r=0.2, h=0.16, mat="M_DarkMetal"):
    """Low dome rivet: 6-gon base ring, smaller ring on top, apex (tagged 1: shares the bolt UV tile)."""
    pos, n = Vector(pos), Vector(normal).normalized()
    up = Vector((0, 0, 1)) if abs(n.z) < 0.9 else Vector((1, 0, 0))
    a = n.cross(up).normalized()
    b = n.cross(a)
    bm = part.bm
    mi = part._mi(mat)
    ring0 = [_add_vert(bm, pos + (a * math.cos(2 * math.pi * k / 6) + b * math.sin(2 * math.pi * k / 6)) * r) for k in range(6)]
    ring1 = [_add_vert(bm, pos + n * h * 0.75 + (a * math.cos(2 * math.pi * k / 6) + b * math.sin(2 * math.pi * k / 6)) * r * 0.6) for k in range(6)]
    apex = _add_vert(bm, pos + n * h)
    for k in range(6):
        k2 = (k + 1) % 6
        _face(bm, [ring0[k], ring0[k2], ring1[k2], ring1[k]], mi, 1)
        _face(bm, [ring1[k], ring1[k2], apex], mi, 1)


def edge_rivets(part, P, height, nu_len, nv_len, ins=0.05, shr=(0, 0, 0, 0), spacing=None, r=0.15):
    """Rivets along the 4 edges of a plate's top (in the flat part inside the chamfer); `nu_len`,`nv_len` = plate extents in metres."""
    sp = spacing or RIVET_SPACING
    if not sp:
        return
    for edge, length in (((0, 1), nv_len), ((1, 1), nv_len), ((0, 0), nu_len), ((1, 0), nu_len)):
        cnt = max(1, int(length / sp))
        for q in range(cnt):
            f = (q + 0.5) / cnt
            s, t = (edge[0] * (1 - 2 * ins) + ins, f) if edge[1] == 1 else (f, edge[0] * (1 - 2 * ins) + ins)
            s2, t2 = shr[0] + (1 - shr[0] - shr[1]) * s, shr[2] + (1 - shr[2] - shr[3]) * t
            p = P(s2, t2, height(s2, t2))
            ex = P(min(1.0, s2 + 0.02), t2, height(min(1.0, s2 + 0.02), t2)) - P(max(0.0, s2 - 0.02), t2, height(max(0.0, s2 - 0.02), t2))
            ey = P(s2, min(1.0, t2 + 0.02), height(s2, min(1.0, t2 + 0.02))) - P(s2, max(0.0, t2 - 0.02), height(s2, max(0.0, t2 - 0.02)))
            nrm = ex.cross(ey)
            if nrm.length < 1e-9:
                continue
            nrm.normalize()
            if nrm.dot(p - P(s2, t2, 0.0)) < 0:
                nrm = -nrm
            rivet(part, p - nrm * 0.02, nrm, r, r * 0.8)


def corner_pts(inset=0.1, mid=0):
    pts = [(inset, inset), (inset, 1 - inset), (1 - inset, inset), (1 - inset, 1 - inset)]
    if mid:
        pts += [(0.5, inset), (0.5, 1 - inset)]
    return pts


def edge_pts(n, inset=0.1):
    pts = []
    for k in range(n):
        s = inset + (1 - 2 * inset) * k / max(1, n - 1)
        pts += [(s, inset), (s, 1 - inset)]
    return pts


SPECS = {}      # plate name -> (args, kwargs): lets `variants` rebuild the same plate crumpled (Armor_<Zone>_<NN>_dent)


def plate(zone, bone, surf, u, v, off=0.6, th=0.9, kind="shell", mat="M_CeramicGray", cham=(1, 1, 1, 1), nu=5, nv=6, taper=0.0, crown=0.0, bolts=0,
          skew=0.0, dent=0.0, seed=0, panel=None, ribs=0, vent=0, accent=None, name_suffix="", bolt_r=0.28, cham_w=0.2, lip=0.45, extra=None, name=None, variant=False, rivets=True):
    """Create + commit one Armor_<Zone>_<NN> object. kinds: shell (plain), stepped (raised inset panel), ribbed (raised ribs along the
    tube), vent (louvre slats), wedge (strong taper + big chamfers)."""
    if abs(v[1] - v[0]) >= 330.0 and not variant:       # a closed ring cannot be unwrapped without self-overlap: two half-rings
        mid = (v[0] + v[1]) / 2.0
        kw = dict(off=off, th=th, kind=kind, mat=mat, cham=cham, nu=nu, nv=max(2, nv // 2), taper=taper, crown=crown, bolts=bolts, skew=skew, dent=dent, seed=seed, panel=panel,
                  ribs=ribs, vent=vent, accent=accent, name_suffix=name_suffix, bolt_r=bolt_r, cham_w=cham_w, lip=lip, extra=extra, name=None, variant=variant, rivets=rivets)
        plate(zone, bone, surf, u, (v[0], mid - 1.0), **kw)
        return plate(zone, bone, surf, u, (mid + 1.0, v[1]), **kw)
    spec = (dict(zone=zone, bone=bone, surf=surf, u=u, v=v, off=off, th=th, kind=kind, mat=mat, cham=cham, nu=nu, nv=nv, taper=taper, crown=crown, bolts=bolts,
                 skew=skew, seed=seed, panel=panel, ribs=ribs, vent=vent, accent=accent, bolt_r=bolt_r, cham_w=cham_w, lip=lip, extra=extra, rivets=rivets))
    off, th = off * PLATE_SCALE, th * PLATE_SCALE
    nu, nv = max(2, int(round(nu * RES_SCALE))), max(2, int(round(nv * RES_SCALE)))
    if name:
        p = hs.Part(name, bone, zone, "armor", mat)
    else:
        p = hs.armor(zone, bone, mat)
    p.variant = variant
    if name_suffix:
        p.name += name_suffix
    if not variant:
        SPECS[p.name] = spec
    P, height = patch(p, surf, u, v, off, th, cham, nu, nv, taper, crown, mat, dent, seed, skew, cham_w=cham_w, lip=lip)
    if kind == "stepped" or panel:
        pc = panel or {}
        ins = pc.get("inset", 0.16)
        pm = pc.get("mat", "M_Graphite")
        u0, u1 = u
        a0, a1 = v
        du, dv = (u1 - u0), (a1 - a0)
        lift = pc.get("th", th * 0.35)
        w = 1.0 - 2 * ins
        base_off = off + th * 0.5

        def hp(s_, t_, _h=height, _ins=ins, _w=w, _lift=lift):
            return _h(_ins + _w * s_, _ins * 0.9 + (1 - 1.8 * _ins) * t_) + _lift

        patch(p, surf, (u0 + du * ins, u1 - du * ins), (a0 + dv * ins * 0.9, a1 - dv * ins * 0.9), base_off, th, (1, 1, 1, 1), 3, 3,
              0.0, 0.0, pm, 0.0, seed + 1, skew, cham_w=0.3, hfn=hp)
    if kind == "ribbed" or ribs:
        n = ribs or 3
        u0, u1 = u
        a0, a1 = v
        for k in range(n):
            f = (k + 0.5) / n
            ua = u0 + (u1 - u0) * (f - 0.2 / n)
            ub = u0 + (u1 - u0) * (f + 0.2 / n)
            patch(p, surf, (ua, ub), (a0 + (a1 - a0) * 0.1, a1 - (a1 - a0) * 0.1), off + th * 0.9 + crown * 0.5, th * 0.45, (1, 1, 1, 1), 1, 4, taper, 0.0, mat, 0.0, 0, skew, bottom=False, cham_w=0.4)
    if kind == "vent" or vent:
        n = vent or 4
        u0, u1 = u
        a0, a1 = v
        for k in range(n):
            f = (k + 0.5) / n
            ua = u0 + (u1 - u0) * (f - 0.18 / n) * 0.85 - (u1 - u0) * 0.0
            ub = u0 + (u1 - u0) * (f + 0.18 / n) * 0.85 + (u1 - u0) * 0.0
            patch(p, surf, (u0 + (u1 - u0) * (0.12 + 0.76 * (k + 0.2) / n), u0 + (u1 - u0) * (0.12 + 0.76 * (k + 0.75) / n)), (a0 + (a1 - a0) * 0.18, a1 - (a1 - a0) * 0.18),
                  off + th * 0.9, th * 0.5, (1, 1, 1, 1), 1, 3, taper, 0.0, "M_DarkMetal", 0.0, 0, skew, cham_w=0.5)
    if accent:
        u0, u1 = u
        a0, a1 = v
        fa, fb = accent
        patch(p, surf, (u0 + (u1 - u0) * fa[0], u0 + (u1 - u0) * fa[1]), (a0 + (a1 - a0) * fb[0], a0 + (a1 - a0) * fb[1]), off + th * 0.98 + crown * 0.5, th * 0.22, (1, 1, 1, 1), 2, 3,
              taper, 0.0, "M_AccentOrange", 0.0, 0, skew, cham_w=0.25)
    if bolts:
        bolts_on(p, P, height, corner_pts(0.12, 1 if bolts > 4 else 0) if bolts <= 6 else edge_pts((bolts + 1) // 2), bolt_r, bolt_r * 0.7, shr=tuple(c * cham_w for c in cham))
    if rivets:
        dims = _plate_extent(surf, u, v)
        edge_rivets(p, P, height, dims[0], dims[1], 0.07, tuple(c * cham_w for c in cham))
    if extra:
        extra(p, P, height)
    return p.commit()


def _plate_extent(surf, u, v):
    """Approximate size (m) of a plate along u and along v, measured on the surface at the plate centre."""
    uc, vc = (u[0] + u[1]) / 2, math.radians((v[0] + v[1]) / 2)
    L_u = (surf.point(u[1], vc) - surf.point(u[0], vc)).length
    L_v = (surf.point(uc, math.radians(v[1])) - surf.point(uc, math.radians(v[0]))).length
    return L_u, max(L_v, 0.1)


# ----------------------------------------------------------------------------------------------- inner mechanics
def piston(sleeve_part, rod_part, a, b, r=0.9, ext=0.5, collars=2):
    forms.hydraulic(sleeve_part, rod_part, a, b, r, "M_DarkMetal", "M_Hydraulic", ext, collars)


def ring(part, center, axis, r_out, r_in, width, segs=24, mat=None, power=2.0):
    """Annulus (collar/bearing race) around `axis` through `center`."""
    c = Vector(center)
    n = Vector(axis).normalized()
    up = Vector((0, 0, 1)) if abs(n.z) < 0.9 else Vector((1, 0, 0))
    a = n.cross(up).normalized()
    b = n.cross(a)
    mi = part._mi(mat or part.mat)
    bm = part.bm
    rings = []
    for z, r in ((-width / 2, r_out), (-width / 2, r_in), (width / 2, r_in), (width / 2, r_out)):
        rings.append([_add_vert(bm, c + n * z + (a * math.cos(2 * math.pi * k / segs) + b * math.sin(2 * math.pi * k / segs)) * r) for k in range(segs)])
    for q in range(4):
        r0, r1 = rings[q], rings[(q + 1) % 4]
        for k in range(segs):
            k2 = (k + 1) % segs
            _face(bm, [r0[k], r0[k2], r1[k2], r1[k]] if q != 3 else [r1[k], r1[k2], r0[k2], r0[k]], mi)


def sphere_joint(part, center, r, mat=None, lat=8, lon=16):
    forms.add_ellipsoid(part, center, (r, r, r), lat=lat, lon=lon, mat=mat)


def box_tube(part, p0, p1, w, h, mat=None, power=4.0, n=16):
    """Rounded-rectangle bar from p0 to p1 with section w x h (w along the cross direction of the mech's X axis)."""
    forms.add_tube(part, Tube([Sec(p0, w, h, power), Sec(Vector(p0).lerp(Vector(p1), 0.5), w, h, power), Sec(p1, w, h, power)], n), True, mat)
