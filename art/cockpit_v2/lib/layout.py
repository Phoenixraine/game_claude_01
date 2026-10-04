"""Layout of cockpit v2: places every part (pure numpy; no bpy). Blender axes: +X right, -Y forward, +Z up, the eye is the origin."""
import math
import random

import numpy as np

from . import geo, parts as P
from .geo import MB, unit
from .parts import Empty, Panel, Part

N = lambda n: "%02d" % n
FLOOR_Z = -1.62
CEIL_Z = 1.06


class Model:
    def __init__(self):
        self.parts = []
        self.empties = []
        self.pipes = []        # route dicts for the json
        self.wires = []
        self.monitors = []

    def add(self, part):
        self.parts.append(part)
        return part

    def empty(self, *a, **k):
        e = Empty(*a, **k)
        self.empties.append(e)
        return e


def _offset_path(path, off_dir, amount):
    return np.asarray(path, float) + np.asarray(off_dir, float) * amount


def build_model(seed=20261004):
    rng = random.Random(seed)
    M = Model()
    # ------------------------------------------------------------------ glass and frame
    R_G, CY = 2.6, 1.05
    M.add(P.glass_part("Glass_Front", (0.0, CY), R_G, -math.radians(38), math.radians(38), -0.56, 1.08, nu=30, nv=8))
    M.add(P.glass_part("Glass_SideL", (0.0, CY), R_G, -math.radians(78), -math.radians(38), -0.30, 1.08, nu=10, nv=4))
    M.add(P.glass_part("Glass_SideR", (0.0, CY), R_G, math.radians(38), math.radians(78), -0.30, 1.08, nu=10, nv=4))
    M.add(P.flat_glass_part("Glass_Top", (-1.15, -1.40, 1.12), (1.15, -1.40, 1.12), (1.0, -0.45, 1.06), (-1.0, -0.45, 1.06)))
    for sx, nm in ((-1, "L"), (1, "R")):
        M.add(P.beam_part("Frame_Pillar" + nm, (sx * 1.34, -1.08, -0.55), (sx * 1.22, -1.46, 1.08), 0.075, 0.06, (0, 1, 0)))
        M.add(P.beam_part("Frame_PillarSide" + nm, (sx * 1.62, -0.60, -0.30), (sx * 1.40, -0.62, 1.08), 0.07, 0.06, (0, 1, 0)))
    M.add(P.beam_part("Frame_Header", (-1.25, -1.45, 1.09), (1.25, -1.45, 1.09), 0.09, 0.07, (0, 1, 0)))
    for k, x in enumerate((-0.8, -0.27, 0.27, 0.8)):
        M.add(P.beam_part("Frame_Rib_" + N(k), (x * 0.9, -0.2, 1.08), (x, -1.45, 1.08), 0.045, 0.05, (0, 1, 0)))
    M.add(P.block_part("Frame_Floor", (0.0, -0.4, FLOOR_Z - 0.025), (3.1, 2.4, 0.05), None, "M_Frame", 0.01, "Frame"))
    M.add(P.block_part("Frame_RearWall", (0.0, 0.95, -0.25), (3.0, 0.06, 2.6), None, "M_Frame", 0.01, "Frame"))
    grating = MB(["M_MetalDark"])
    for k in range(10):
        geo.add_box(grating, (-0.5 + k * 0.11, -0.45, FLOOR_Z + 0.004), (0.045, 0.9, 0.008), None, "M_MetalDark")
    M.add(Part("Floor_Grating", grating, "Frame"))
    # seat (a simple shell: the pilot's body is not part of this kit)
    seat = MB(["M_Rubber", "M_Frame"])
    geo.add_box(seat, (0.0, 0.18, -1.0), (0.62, 0.55, 0.14), None, "M_Rubber", chamfer=0.03)
    geo.add_box(seat, (0.0, 0.52, -0.55), (0.6, 0.12, 1.0), geo.rot_axis((1, 0, 0), 0.12), "M_Rubber", chamfer=0.03)
    geo.add_box(seat, (0.0, 0.5, 0.12), (0.34, 0.1, 0.22), None, "M_Rubber", chamfer=0.02)
    geo.add_cyl(seat, (0.0, 0.2, FLOOR_Z), (0.0, 0.2, -1.08), 0.07, 0.07, 12, "M_Frame")
    M.add(Part("Seat", seat, "Frame"))

    # ------------------------------------------------------------------ consoles
    # front console: sloping top, v axis points to the pilot (near edge down)
    slope = unit((0.0, 0.96, -0.28))
    cf_o = np.array([0.0, -1.22, -0.64])
    CF = Panel.from_axes(cf_o, (1.0, 0.0, 0.0), slope)
    M.add(P.block_part("Console_Front", cf_o - CF.n * 0.075, (2.3, 0.62, 0.15), CF.R, "M_Frame", 0.012))
    M.add(P.block_part("Console_FrontBase", (0.0, -1.27, -1.12), (2.2, 0.5, 1.0), None, "M_FrameDark", 0.012))
    # side consoles: top plane tilts towards the pilot
    def side_panel(sx):
        o = np.array([sx * 1.24, -0.52, -0.80])
        ux = np.array([0.0, -1.0, 0.0])                     # forward
        uy = unit((-sx * 0.30, 0.0, 0.95)) if False else unit((-sx * 0.26, 0.0, 0.97))
        return Panel.from_axes(o, ux, uy) if sx > 0 else Panel.from_axes(o, ux, uy)
    CL, CR = side_panel(-1), side_panel(1)
    for nm, pan, sx in (("L", CL, -1), ("R", CR, 1)):
        M.add(P.block_part("Console_" + nm, pan.o - pan.n * 0.06, (0.95, 0.52, 0.12), pan.R, "M_Frame", 0.012))
        M.add(P.block_part("Console_%sBase" % nm, (sx * 1.26, -0.52, -1.18), (0.5, 0.9, 0.85), None, "M_FrameDark", 0.012))
    CC = Panel.from_axes(np.array([0.0, -0.62, CEIL_Z - 0.02]), (1.0, 0.0, 0.0), (0.0, -1.0, 0.0))        # ceiling console: normal points down
    M.add(P.block_part("Console_Ceiling", CC.o + CC.n * -0.0 + np.array([0, 0, 0.04]), (1.9, 0.95, 0.08), None, "M_Frame", 0.012))
    # hatches in the ceiling (wire exits)
    hatches = [(-0.95, -0.35), (-0.5, -0.95), (0.0, -1.1), (0.5, -0.95), (0.95, -0.35), (0.0, -0.1)]
    for k, (hx, hy) in enumerate(hatches):
        hb = MB(["M_FrameDark", "M_MetalDark"])
        geo.add_box(hb, (hx, hy, CEIL_Z - 0.03), (0.24, 0.24, 0.05), None, "M_FrameDark", chamfer=0.006)
        geo.add_box(hb, (hx, hy, CEIL_Z - 0.057), (0.16, 0.16, 0.012), None, "M_MetalDark", chamfer=0.003)
        M.add(Part("Hatch_" + N(k), hb, "Frame"))

    # ------------------------------------------------------------------ monitors (14)
    mon_specs = []
    for (u, v, shape, w, h, d) in [(0.0, 0.0, "radar", 0.24, 0.24, 0.05), (-0.36, 0.02, "flat", 0.27, 0.18, 0.05), (0.36, 0.02, "flat", 0.27, 0.18, 0.05),
                                    (-0.70, 0.02, "crt", 0.21, 0.16, 0.08), (0.70, 0.02, "crt", 0.21, 0.16, 0.08), (-0.40, -0.22, "strip", 0.55, 0.06, 0.03), (0.40, -0.22, "strip", 0.55, 0.06, 0.03)]:
        mon_specs.append((CF, u, v, shape, w, h, d))
    for pan in (CL, CR):
        mon_specs += [(pan, 0.0, -0.12, "flat", 0.2, 0.14, 0.04), (pan, 0.0, 0.12, "curved", 0.3, 0.07, 0.03)]
    mon_specs += [(CC, -0.5, 0.0, "strip", 0.4, 0.07, 0.03), (CC, 0.5, 0.0, "strip", 0.4, 0.07, 0.03), (CF, -1.0, -0.1, "radar", 0.14, 0.14, 0.04)]
    for k, (pan, u, v, shape, w, h, d) in enumerate(mon_specs):
        part, c = P.monitor_part("Mon_" + N(k), pan, u, v, shape, w, h, d, rng)
        part.meta["panel"] = "front" if pan is CF else "ceiling" if pan is CC else "left" if pan is CL else "right"
        M.add(part)
        M.empty("MonitorAnchor_" + N(k), c, "MonitorAnchor", pan.n, {"monitor": "Mon_" + N(k)})
        M.monitors.append({"name": "Mon_" + N(k), "shape": shape, "screen_m": [round(w, 3), round(h, 3)], "pos": [round(float(x), 3) for x in c]})

    # ------------------------------------------------------------------ buttons (88), dials, sliders, caps
    types = ["push_square", "push_round", "toggle", "rocker", "lever", "selector"]
    nb = 0

    def add_btn(pan, u, v, kind=None):
        nonlocal nb
        kind = kind or types[nb % 6] if kind is None else kind
        M.add(P.button_part("Btn_" + N(nb), pan, u, v, kind, rng))
        nb += 1

    for i in range(4):                                       # front left / right grids
        for j in range(3):
            add_btn(CF, -1.05 + i * 0.06, -0.12 + j * 0.075, types[(i + j) % 5])
            add_btn(CF, 1.05 - i * 0.06, -0.12 + j * 0.075, types[(i + j + 2) % 5])
    for i in range(9):                                       # toggle bank at the far edge
        add_btn(CF, -0.64 + i * 0.16, -0.255, "toggle")
    for i in range(6):                                       # selectors along the near edge
        add_btn(CF, -0.5 + i * 0.2, 0.235, "selector" if i % 2 == 0 else "lever")
    for pan in (CL, CR):                                     # side consoles
        for i in range(4):
            for j in range(3):
                add_btn(pan, -0.25 + i * 0.075, -0.06 + j * 0.075, types[(i + 2 * j) % 6])
        for i in range(4):
            add_btn(pan, -0.22 + i * 0.12, 0.21, "toggle")
    for i in range(14):                                      # ceiling toggles
        add_btn(CC, -0.78 + (i % 7) * 0.26, -0.22 + (i // 7) * 0.2, "toggle" if i % 3 else "rocker")
    n_btn = nb
    nd = 0
    for pan, uvs in ((CF, [(-0.55, 0.2), (-0.18, 0.2), (0.18, 0.2), (0.55, 0.2)]), (CL, [(0.0, 0.16), (0.14, 0.16)]), (CR, [(0.0, 0.16), (-0.14, 0.16)]), (CC, [(-0.1, 0.18), (0.1, 0.18)]),
                     (CF, [(-0.85, 0.2), (0.85, 0.2)])):
        for (u, v) in uvs:
            M.add(P.dial_part("Dial_" + N(nd), pan, u, v, rng.choice((0.03, 0.035, 0.04, 0.05)), rng))
            nd += 1
    ns = 0
    for pan, uvs in ((CF, [(-0.18, -0.02), (0.18, -0.02)]), (CL, [(-0.28, 0.0)]), (CR, [(0.28, 0.0)]), (CC, [(0.0, 0.3)])):
        for (u, v) in uvs:
            M.add(P.slider_part("Slider_" + N(ns), pan, u, v, rng.uniform(0.12, 0.2), rng))
            ns += 1
    nc = 0
    for pan, u, v in ((CF, -0.64, -0.255), (CF, 0.64, -0.255), (CF, -0.32, -0.255), (CC, -0.78, -0.22), (CC, 0.78, -0.22), (CL, -0.22, 0.21), (CR, 0.22, 0.21), (CF, 0.0, -0.255)):
        M.add(P.cap_part("Cap_" + N(nc), pan, u, v))
        nc += 1

    # ------------------------------------------------------------------ lamps (44), beacons (4), strobes (4)
    nw = nk = 0
    lamp_rows = [(CF, -0.62, -0.20, 0.1, 10), (CF, -0.62, 0.15, 0.1, 10), (CC, -0.8, 0.28, 0.2, 9), (CL, -0.2, 0.1, 0.09, 5), (CR, -0.2, 0.1, 0.09, 5), (CF, -1.0, -0.2, 0.0, 0)]
    for (pan, u0, v0, pitch, cnt) in lamp_rows:
        for i in range(cnt):
            warn = (nw + nk) % 2 == 0
            nm = ("Lamp_Warn_" + N(nw)) if warn else ("Lamp_Ok_" + N(nk))
            if warn and nw >= 22 or (not warn and nk >= 22):
                continue
            M.add(P.lamp_part(nm, pan, u0 + i * pitch, v0 if pan is not CL and pan is not CR else v0, "Warn" if warn else "Ok", rng))
            if warn:
                nw += 1
            else:
                nk += 1
    j = 0
    while nw < 22 or nk < 22:                                # fill the counts up on the ceiling console rows
        warn = nw < 22 and (nk >= 22 or j % 2 == 0)
        u = -0.85 + (j % 14) * 0.13
        v = -0.34 + (j // 14) * 0.07
        nm = ("Lamp_Warn_" + N(nw)) if warn else ("Lamp_Ok_" + N(nk))
        M.add(P.lamp_part(nm, CC, u, v, "Warn" if warn else "Ok", rng))
        if warn:
            nw += 1
        else:
            nk += 1
        j += 1
    for k, (bx, by, bz) in enumerate(((-1.18, -1.2, 1.06), (1.18, -1.2, 1.06), (-0.9, 0.45, 1.02), (0.9, 0.45, 1.02))):
        M.add(P.beacon_part("AlarmBeacon_" + N(k), (bx, by, bz), (0, 0, -1), rng))
        M.empty("AlarmBeaconAxis_" + N(k), (bx, by, bz - 0.06), "AlarmBeaconAxis", (0, 0, -1), {"beacon": "AlarmBeacon_" + N(k)})
    for k, (pan, u, v, w, h) in enumerate(((CC, -0.9, 0.38, 0.22, 0.05), (CC, 0.9, 0.38, 0.22, 0.05), (CF, -1.12, 0.0, 0.05, 0.22), (CF, 1.12, 0.0, 0.05, 0.22))):
        M.add(P.strobe_part("StrobePanel_" + N(k), pan, u, v, w, h))

    # ------------------------------------------------------------------ pipes (44) + steam ports + burst variants
    mirror = lambda path: np.array([[-p[0], p[1], p[2]] for p in path])
    trunks = [
        ([(-1.40, -0.95, -1.0), (-1.34, -1.05, -0.2), (-1.26, -1.38, 0.9), (-0.9, -1.38, 1.1)], [0.03, 0.045, 0.02], (1, 0, 0), 0.06),
        ([(1.40, -0.95, -1.0), (1.34, -1.05, -0.2), (1.26, -1.38, 0.9), (0.9, -1.38, 1.1)], [0.03, 0.045, 0.02], (-1, 0, 0), 0.06),
        ([(-1.3, -0.2, 1.0), (-0.6, -0.4, 1.04), (0.6, -0.4, 1.04), (1.3, -0.2, 1.0)], [0.02, 0.03, 0.04, 0.025, 0.05, 0.015], (0, -1, 0), 0.075),
        ([(-1.1, -0.2, 1.0), (-1.32, 0.3, 0.9), (-1.38, 0.7, 0.2), (-1.3, 0.8, -1.0)], [0.025, 0.035, 0.05, 0.02], (0.4, 0, 0), 0.07),
        ([(1.1, -0.2, 1.0), (1.32, 0.3, 0.9), (1.38, 0.7, 0.2), (1.3, 0.8, -1.0)], [0.025, 0.035, 0.05, 0.02], (-0.4, 0, 0), 0.07),
        ([(-1.15, -1.15, -0.98), (-0.5, -1.26, -1.02), (0.5, -1.26, -1.02), (1.15, -1.15, -0.98)], [0.04, 0.03, 0.065, 0.02, 0.05, 0.035], (0, 0, 1), 0.075),
        ([(-1.1, -1.0, -1.1), (-1.3, -0.8, -1.3), (-1.36, -0.3, -1.4), (-1.3, 0.3, -1.45)], [0.03, 0.045, 0.02, 0.08], (0, 0, 1), 0.08),
        ([(1.1, -1.0, -1.1), (1.3, -0.8, -1.3), (1.36, -0.3, -1.4), (1.3, 0.3, -1.45)], [0.03, 0.045, 0.02, 0.08], (0, 0, 1), 0.08),
        ([(-0.9, -0.95, -1.57), (-0.4, -0.7, -1.5), (0.4, -0.7, -1.5), (0.9, -0.95, -1.57)], [0.05, 0.12, 0.03], (0, 1, 0), 0.1),
        ([(-1.45, -0.7, -0.4), (-1.4, -0.9, 0.3), (-1.3, -1.1, 0.8)], [0.015, 0.018, 0.012, 0.022, 0.02], (0.25, 0, 0), 0.05),
        ([(0.9, -0.9, 1.0), (0.4, -1.0, 1.05), (-0.4, -1.0, 1.05), (-0.9, -0.9, 1.0)], [0.02, 0.03, 0.012, 0.018], (0, -1, 0), 0.06),
    ]
    npipe = 0
    steam_ids = []
    burst_src = []
    for path, radii, off_dir, pitch in trunks:
        for k, r in enumerate(radii):
            base = np.asarray(path, float)
            off = (k - (len(radii) - 1) / 2.0) * pitch
            lateral = np.array(off_dir, float)
            pts = base + unit(lateral) * off + np.array([rng.uniform(-0.015, 0.015), rng.uniform(-0.015, 0.015), rng.uniform(-0.015, 0.015)])
            sm = geo.smooth_path(pts, 6)
            steam = (npipe % 3 == 0) and len(steam_ids) < 14
            part = P.pipe_part("Pipe_" + N(npipe), sm, r, rng, steam=steam)
            part.meta["trunk"] = trunks.index((path, radii, off_dir, pitch))
            M.add(part)
            M.pipes.append({"name": part.name, "radius": r, "length": part.meta["length"], "points": [[round(float(x), 3) for x in p] for p in sm[::3]], "steam": steam})
            if steam:
                steam_ids.append(npipe)
                s = geo.path_length(sm) * rng.uniform(0.25, 0.75)
                p, t = geo.point_on(sm, s)
                F = geo.frame_from(t)
                a = rng.uniform(0, 6.28)
                d = unit(F[:, 1] * math.cos(a) + F[:, 2] * math.sin(a) + np.array([0, 0, 0.3]))
                M.empty("SteamPort_" + N(len(steam_ids) - 1), p + d * r, "SteamPort", d, {"pipe": part.name})
                if len(burst_src) < 12:
                    burst_src.append((npipe, sm, r))
            npipe += 1
    for k, (pi, sm, r) in enumerate(burst_src):
        bp, lp, ld = P.pipe_burst_part("Pipe_Burst_" + N(k), sm, r, rng)
        bp.meta["replaces"] = "Pipe_" + N(pi)
        M.add(bp)
        M.empty("LeakPoint_" + N(k), lp, "LeakPoint", ld, {"burst": bp.name})

    # ------------------------------------------------------------------ wires (64) + anchors, snapped variants (24) + spark ports
    nwire = 0
    wire_defs = []
    for k in range(20):                                       # hanging from the ceiling hatches
        hx, hy = hatches[k % len(hatches)]
        top = np.array([hx + rng.uniform(-0.07, 0.07), hy + rng.uniform(-0.07, 0.07), CEIL_Z - 0.06])
        bottom = top + np.array([rng.uniform(-0.15, 0.15), rng.uniform(-0.1, 0.1), -rng.uniform(0.25, 0.6)])
        wire_defs.append((top, bottom, rng.uniform(0.02, 0.07), rng.choice((0.005, 0.006, 0.008, 0.01)), False, "hanging"))
    for k in range(14):                                       # along the pillars
        sx = -1 if k % 2 == 0 else 1
        z0 = rng.uniform(-0.3, 0.2)
        top = np.array([sx * rng.uniform(1.18, 1.34), rng.uniform(-1.4, -1.1), z0 + rng.uniform(0.5, 0.9)])
        bottom = np.array([sx * rng.uniform(1.3, 1.5), rng.uniform(-1.0, -0.7), z0 - rng.uniform(0.2, 0.5)])
        wire_defs.append((top, bottom, rng.uniform(0.02, 0.06), rng.choice((0.006, 0.008, 0.012)), False, "pillar"))
    for k in range(12):                                       # side consoles to the floor
        sx = -1 if k % 2 == 0 else 1
        top = np.array([sx * rng.uniform(1.0, 1.4), rng.uniform(-0.9, -0.1), -0.74])
        bottom = np.array([sx * rng.uniform(0.9, 1.3), rng.uniform(-0.8, 0.2), FLOOR_Z + 0.01])
        wire_defs.append((top, bottom, rng.uniform(0.03, 0.1), rng.choice((0.008, 0.01, 0.015)), False, "floor"))
    for k in range(10):                                       # sticking up from the console hatches
        x = rng.uniform(-1.0, 1.0)
        top = np.array([x, -1.38, -0.55])
        bottom = np.array([x + rng.uniform(-0.12, 0.12), -1.38 - rng.uniform(0.02, 0.1), -0.55 + rng.uniform(0.12, 0.3)])
        wire_defs.append((top, bottom, -0.04, rng.choice((0.005, 0.007)), False, "sticking"))
    for k in range(8):                                        # thick bundles from the ceiling to the front console
        top = np.array([rng.uniform(-1.1, 1.1), rng.uniform(-1.3, -0.5), CEIL_Z - 0.05])
        bottom = np.array([top[0] + rng.uniform(-0.2, 0.2), top[1] - rng.uniform(0.0, 0.15), 0.35 + rng.uniform(0.0, 0.3)])
        wire_defs.append((top, bottom, rng.uniform(0.04, 0.09), rng.uniform(0.016, 0.026), True, "bundle"))
    snapped = 0
    for (top, bottom, sag, r, bundle, cls) in wire_defs:
        path = P.wire_path(top, bottom, sag, rng, wobble=0.02, n=12)
        part, pts = P.wire_part("Wire_" + N(nwire), path, r, rng, bundle=bundle)
        part.meta["class"] = cls
        M.add(part)
        M.empty("WireAnchor_" + N(nwire), pts[0], "WireAnchor", pts[1] - pts[0], {"wire": part.name, "class": cls, "swing": cls in ("hanging", "bundle")})
        M.wires.append({"name": part.name, "class": cls, "radius": round(r, 4), "points": [[round(float(x), 3) for x in p] for p in pts], "anchor": "WireAnchor_" + N(nwire)})
        if snapped < 24 and nwire % 8 not in (3, 5):
            sp, end, t = P.wire_snapped_part("Wire_Snapped_" + N(snapped), pts, r, rng, bundle=bundle)
            sp.meta["replaces"] = part.name
            M.add(sp)
            M.empty("SparkPort_" + N(snapped), end, "SparkPort", t, {"wire": sp.name})
            snapped += 1
        nwire += 1

    # ------------------------------------------------------------------ fire sockets (8) and scorch decals (6)
    fire_pos = [(CF, -0.55, -0.1), (CF, 0.55, -0.1), (CF, 0.0, 0.1), (CL, 0.0, -0.1), (CR, 0.0, -0.1), (CC, 0.0, -0.1), (None, (-0.4, -0.5, FLOOR_Z + 0.05), None), (None, (0.4, -0.5, FLOOR_Z + 0.05), None)]
    for k, (pan, u, v) in enumerate(fire_pos):
        if pan is None:
            M.empty("Fire_Socket_" + N(k), u, "Fire_Socket", (0, 0, 1))
        else:
            M.empty("Fire_Socket_" + N(k), pan.pt(u, v, 0.03), "Fire_Socket", pan.n)
    for k, (pan, u, v) in enumerate([(CF, -0.55, -0.1), (CF, 0.55, -0.1), (CF, 0.0, 0.1), (CL, 0.0, -0.1), (CR, 0.0, -0.1), (CC, 0.0, -0.1)]):
        M.add(P.decal_part("Scorch_Decal_" + N(k), pan, u, v, rng.uniform(0.35, 0.55), rng.uniform(0.3, 0.45), rng.uniform(0, 6.28)))
    return M
