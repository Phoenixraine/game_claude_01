"""Tokyo-style layout (TASK-015): reclaimed waterfront with a promenade, a canal (two bridges) and an embankment road under the expressway;
behind it a dense grid of 90-180 m blocks cut by main streets (44-90 m), a 90 m boulevard, two 90 m avenues and 24-36 m alleys.

Coordinates as in v1: x right, y from the sea toward the city, z up. Everything is deterministic (own PCG32 / hash noise)."""
import math

from . import noise
from .geom import dist_point_polyline, nearest_on_segment, point_in_poly
from .terrain import CELL, N, X0, Y0, Terrain

X_MIN, X_MAX = -800.0, 800.0
Y_ROW0 = 470.0              # south edge of the first block row (the waterfront belt lies below it)
BLOCK_TOP = 1180.0
Y_TOP = 1200.0
EMBANK_W = 48.0
PROM_W = 40.0
EXPRESSWAY_W = 26.0
DECK_Z = 14.0
STATION_W = 320.0
PLAZA_BOULEVARD = 1         # cross street index (0..2) that is the 90 m boulevard of the scramble


class TokyoTerrain(Terrain):
    """Reclaimed, almost straight seawall (+-12 m) instead of the natural shore of v1."""

    def _coast_y(self, x):
        return 245.0 + 9.0 * (noise.value1(x / 420.0, self.seed + 11) * 2 - 1) + 3.0 * (noise.value1(x / 130.0, self.seed + 12) * 2 - 1)

    def carve_canal(self, centre_fn, width_fn, depth=6.0, bank=9.0, bank_z=2.8):
        """Water channel along y = centre_fn(x): flat bottom at -depth, banks blend to the embankment height over `bank` metres."""
        for i in range(N):
            x = X0 + i * CELL
            yc, w = centre_fn(x), width_fn(x)
            hw = w / 2.0
            j0 = max(0, int((yc - hw - bank - Y0) / CELL) - 1)
            j1 = min(N - 1, int((yc + hw + bank - Y0) / CELL) + 1)
            for j in range(j0, j1 + 1):
                y = Y0 + j * CELL
                d = abs(y - yc)
                if d >= hw + bank:
                    continue
                if d <= hw:
                    t = min(1.0, (hw - d) / 5.0)
                    z = -1.0 - (depth - 1.0) * (t * t * (3 - 2 * t))
                else:
                    t = (d - hw) / bank
                    t = t * t * (3 - 2 * t)
                    z = -1.0 * (1 - t) + max(self.h[j][i], bank_z) * t
                self.h[j][i] = z
        self._update_range()


def _fit_widths(rng, n, lo, hi, total):
    """n random widths in [lo, hi] scaled to sum to `total` (clamped, remainder spread over the ones with room)."""
    w = [rng.uniform(lo, hi) for _ in range(n)]
    for _ in range(12):
        s = sum(w)
        f = total / s
        w = [min(hi, max(lo, v * f)) for v in w]
        rem = total - sum(w)
        if abs(rem) < 1e-6:
            break
        room = [i for i in range(n) if (rem > 0 and w[i] < hi - 1e-6) or (rem < 0 and w[i] > lo + 1e-6)]
        if not room:
            break
        for i in room:
            w[i] = min(hi, max(lo, w[i] + rem / len(room)))
    return w


PLAZA_SIZE = {"takeshita": 180.0, "shibuya_scramble": 170.0}
STRIP_LENGTH = 380.0         # rows 0 + 1 + the cross street between them (Takeshita-dori is ~335 m after the plaza takes its end)


class TokyoLayout:
    def __init__(self, seed, terrain, rng, arena=None):
        self.arena = arena          # None = TASK-015 (schema 2); "takeshita" | "shibuya_scramble" = TASK-019
        self.plaza = None
        self.strip_col = None
        self.strip = None
        self.seed = seed
        self.T = terrain
        self.rng = rng
        self.roads = []
        self.blocks = []
        self.vlines = []          # (x_center, width, kind, name)
        self.hlines = []          # (y_center, width, kind)
        self.block_cols = []      # (x0, x1, kind) kind: block | site
        self.block_rows = []      # (y0, y1)
        self.sites = {}
        self.alleys = []          # road ids of the alleys
        self.canal = None
        self.bridges = []
        self.embankment = None
        self.promenade = None
        self._plan_grid()
        self._waterfront()
        self._streets()
        self._blocks()

    # ---- warp (same smooth distortion on roads and blocks) -------------------------------------------------------------
    def warp(self, x, y):
        s = self.seed
        dx = 18.0 * noise.fbm2(x / 380.0, y / 380.0, s + 21, 2)
        dy = 18.0 * noise.fbm2(x / 380.0 + 7.3, y / 380.0 + 3.1, s + 22, 2)
        return (x + dx, y + dy)

    # ---- grid plan --------------------------------------------------------------------------------------------------
    def _plan_grid(self):
        r = self.rng.fork("grid")
        # vertical streets: 7 between 8 columns (column 6 is the 320 m station site); two of them are 90 m avenues
        avenue_pairs = [(1, 3), (2, 4), (1, 4), (2, 5), (3, 5)]
        av = r.choice(avenue_pairs)
        small = [44.0, 48.0, 50.0, 52.0, 56.0, 60.0]
        streets = []
        for k in range(7):
            streets.append(90.0 if k in av else r.choice(small))
        self.avenue_idx = av
        blocks_total = (X_MAX - X_MIN) - STATION_W - sum(streets)
        widths = _fit_widths(r, 7, 96.0, 176.0, blocks_total)
        widths.insert(6, STATION_W)
        x = X_MIN
        for k in range(8):
            w = widths[k]
            self.block_cols.append((x, x + w, "site" if k == 6 else "block"))
            x += w
            if k < 7:
                self.vlines.append((x + streets[k] / 2.0, streets[k], "avenue" if k in av else "street", "Avenue %d" % (av.index(k) + 1) if k in av else "Street V%d" % (k + 1)))
                x += streets[k]
        assert abs(x - X_MAX) < 1e-6, x
        # horizontal streets: 3 between 4 rows; the middle one is the 90 m boulevard (scramble)
        hs = [r.choice([44.0, 48.0, 52.0, 56.0]), 90.0, r.choice([44.0, 48.0, 52.0])]
        rows_total = (BLOCK_TOP - Y_ROW0) - sum(hs)
        if self.arena == "takeshita":
            # rows 0 and 1 (+ the street between them) form the ~380 m strip of the pedestrian street; rows 2 and 3 share the rest
            r01 = (STRIP_LENGTH - hs[0]) / 2.0
            rest = (rows_total - 2.0 * r01) / 2.0
            rh = [r01, r01, rest, rest]
            self.strip_col = self._pick_strip_column()
        else:
            rh = _fit_widths(r, 4, 96.0, 178.0, rows_total)
        y = Y_ROW0
        for k in range(4):
            self.block_rows.append((y, y + rh[k]))
            y += rh[k]
            if k < 3:
                self.hlines.append((y + hs[k] / 2.0, hs[k], "boulevard" if hs[k] >= 90.0 else "street"))
                y += hs[k]
        assert abs(y - BLOCK_TOP) < 1e-6, y

    def _pick_strip_column(self):
        """Column for the pedestrian street: a regular block column (not the station site) with room for two shop rows, near the middle of the map."""
        best = None
        for c, (x0, x1, kind) in enumerate(self.block_cols):
            if kind != "block" or c not in (2, 3, 4) or x1 - x0 < 118.0:
                continue
            d = abs((x0 + x1) / 2.0 + 150.0)
            if best is None or d < best[0]:
                best = (d, c)
        if best is None:                      # widen the search
            c = max((c for c in (2, 3, 4)), key=lambda c: self.block_cols[c][1] - self.block_cols[c][0])
            return c
        return best[1]

    # ---- waterfront: promenade, canal, embankment -------------------------------------------------------------------
    def _waterfront(self):
        t = self.T
        rng = self.rng.fork("canal")
        ph = rng.uniform(0, 100)

        def width_fn(x):
            return 64.0 + 14.0 * (noise.value1(x / 300.0 + ph, self.seed + 31) * 2 - 1)      # 50..78 m

        def centre_fn(x):
            return t.coast_y(x) + 72.0 + width_fn(x) / 2.0

        self.canal_centre, self.canal_width = centre_fn, width_fn
        t.carve_canal(centre_fn, width_fn)
        pts = []
        x = X_MIN
        while x <= X_MAX + 1e-6:
            pts.append((x, t.coast_y(x) + 32.0))
            x += 80.0
        self.promenade = self._road("promenade", "Seaside Promenade", PROM_W, pts)
        pts = []
        x = X_MIN
        while x <= X_MAX + 1e-6:
            pts.append((x, t.coast_y(x) + 72.0 + width_fn(x) + 34.0))
            x += 80.0
        self.embankment_pts = pts
        self.embankment = self._road("embankment", "Canal Embankment Road", EMBANK_W, pts)
        # canal as a centre polyline + both banks (for previews / tests)
        cp, left, right = [], [], []
        x = X_MIN
        while x <= X_MAX + 1e-6:
            yc, w = centre_fn(x), width_fn(x)
            cp.append([round(x, 1), round(yc, 1)])
            left.append([round(x, 1), round(yc - w / 2.0, 1)])
            right.append([round(x, 1), round(yc + w / 2.0, 1)])
            x += 40.0
        self.canal = {"id": "canal_01", "centre": cp, "south_bank": left, "north_bank": right, "depth": 6.0, "width_min": 50.0, "width_max": 80.0}

    # ---- streets ----------------------------------------------------------------------------------------------------
    def _road(self, kind, name, width, pts, dead_end=False):
        rid = "road_%02d" % (len(self.roads) + 1)
        self.roads.append({"id": rid, "kind": kind, "name": name, "width": float(width),
                           "points": [[round(p[0], 1), round(p[1], 1)] for p in pts], "dead_end": dead_end})
        return rid

    def _line(self, a, b, step=60.0):
        n = max(2, int(math.hypot(b[0] - a[0], b[1] - a[1]) / step) + 1)
        return [self.warp(a[0] + (b[0] - a[0]) * i / n, a[1] + (b[1] - a[1]) * i / n) for i in range(n + 1)]

    def _streets(self):
        t = self.T
        for k, (xc, w, kind, name) in enumerate(self.vlines):
            if kind == "avenue":                       # avenues cross the canal on a bridge down to the promenade
                y0 = t.coast_y(xc) + 32.0
                rid = self._road("avenue", name, w, self._line((xc, y0), (xc, Y_TOP)))
                yb0 = t.coast_y(xc) + 72.0
                yb1 = yb0 + self.canal_width(xc)
                self.bridges.append({"id": "bridge_%02d" % (len(self.bridges) + 1), "road_id": rid, "name": "%s bridge" % name, "width": w, "deck_z": 3.6,
                                     "from": [round(xc, 1), round(yb0 - 12.0, 1)], "to": [round(xc, 1), round(yb1 + 12.0, 1)],
                                     "length": round(self.canal_width(xc) + 24.0, 1)})
            else:
                y0 = t.coast_y(xc) + 72.0 + self.canal_width(xc) + 34.0       # T-junction with the embankment road
                self._road("street", name, w, self._line((xc, y0), (xc, Y_TOP)))
        for j, (yc, w, kind) in enumerate(self.hlines):
            nm = "Boulevard" if kind == "boulevard" else "Cross Street %d" % (j + 1)
            if self.arena == "takeshita" and j == 0:       # the cross street stops at the two streets flanking the pedestrian column
                xl, xr = self.vlines[self.strip_col - 1][0], self.vlines[self.strip_col][0]
                self._road("street", nm + " west", w, self._line((X_MIN, yc), (xl, yc)))
                self._road("street", nm + " east", w, self._line((xr, yc), (X_MAX, yc)))
            else:
                self._road("street", nm, w, self._line((X_MIN, yc), (X_MAX, yc)))
        self._plaza()

    # ---- blocks and alleys ------------------------------------------------------------------------------------------
    def _quad(self, x0, y0, x1, y1):
        return [self.warp(px, py) for px, py in ((x0, y0), (x1, y0), (x1, y1), (x0, y1))]

    @staticmethod
    def bilinear(poly, u, v):
        a, b, c, d = poly
        bot = (a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u)
        top = (d[0] + (c[0] - d[0]) * u, d[1] + (c[1] - d[1]) * u)
        return (bot[0] + (top[0] - bot[0]) * v, bot[1] + (top[1] - bot[1]) * v)

    def block_frame(self, block):
        poly = [tuple(p) for p in block["polygon"]]
        a, b, c, d = poly
        w = math.hypot(b[0] - a[0], b[1] - a[1])
        h = math.hypot(d[0] - a[0], d[1] - a[1])
        yaw = math.atan2(b[1] - a[1], b[0] - a[0])
        return poly, w, h, yaw

    def _district(self, c, r):
        if r >= 2 and 2 <= c <= 5:
            return "downtown"
        if c in (0, 1) and r <= 1:
            return "residential"
        if c == 6:
            return "civic"
        return "mixed"

    def _add_block(self, kind, district, c, r, poly, name=None, sub=False):
        bid = "block_%02d" % (len(self.blocks) + 1)
        b = {"id": bid, "kind": kind, "district": district, "col": c, "row": r, "polygon": [[round(p[0], 1), round(p[1], 1)] for p in poly]}
        if name:
            b["name"] = name
        if sub:
            b["sub_block"] = True
        self.blocks.append(b)
        if name:
            self.sites[name] = b
        return b

    def _plaza(self):
        """Battle plaza (>= 160 x 160 m, no buildings): at the junction of the strip and the boulevard (takeshita) or round the scramble (shibuya_scramble)."""
        if self.arena is None:
            return
        size = PLAZA_SIZE[self.arena]
        if self.arena == "takeshita":
            x0, x1, _ = self.block_cols[self.strip_col]
            cx = (x0 + x1) / 2.0
            cy = self.hlines[PLAZA_BOULEVARD][0]
        else:
            cx, cy = self.vlines[self.avenue_idx[0]][0], self.hlines[PLAZA_BOULEVARD][0]
        cx, cy = self.warp(cx, cy)
        h = size / 2.0
        self.plaza = {"id": "battle_plaza", "center": [round(cx, 1), round(cy, 1)], "size": size,
                      "polygon": [[round(cx - h, 1), round(cy - h, 1)], [round(cx + h, 1), round(cy - h, 1)], [round(cx + h, 1), round(cy + h, 1)], [round(cx - h, 1), round(cy + h, 1)]]}

    def _strip_blocks(self, c, x0, x1, district):
        """Takeshita strip: one merged column (rows 0-1) cut by the 12 m pedestrian street and three 24 m side lanes into shop blocks."""
        y_start = self.block_rows[0][0]
        y_end = self.plaza["center"][1] - self.plaza["size"] / 2.0 - 2.0
        poly = self._quad(x0, y_start, x1, y_end)
        w = x1 - x0
        h = y_end - y_start
        half = 6.0 / w
        # side lanes at ~1/4, 1/2, 3/4 of the strip
        rr = self.rng.fork("lanes")
        fs = sorted([rr.uniform(0.17, 0.27), rr.uniform(0.45, 0.55), rr.uniform(0.72, 0.82)])
        lane_w = 24.0
        edges = [0.0]
        for f in fs:
            edges += [f - lane_w / 2.0 / h, f + lane_w / 2.0 / h]
        edges.append(1.0)
        for side in (0, 1):
            u0, u1 = (0.0, 0.5 - half) if side == 0 else (0.5 + half, 1.0)
            for k in range(0, len(edges), 2):
                self._add_block("block", district, c, 0, self._sub(poly, u0, u1, edges[k], edges[k + 1]), sub=True, name=None)
        # the pedestrian street itself (south end reaches the embankment road, north end the plaza)
        pts = [self.warp((x0 + x1) / 2.0, y_start - 28.0)] + [self.bilinear(poly, 0.5, k / 6.0) for k in range(7)]
        self.strip = {"road": self._road("pedestrian", "Takeshita-dori", 12.0, pts), "u_mid": 0.5, "x0": x0, "x1": x1, "y_start": y_start, "y_end": y_end}
        for f in fs:
            a = self._alley_line([self.bilinear(poly, k / 4.0, f) for k in range(5)])
            a[0] = (a[0][0] - 24.0, a[0][1])
            a[-1] = (a[-1][0] + 24.0, a[-1][1])
            self.alleys.append(self._road("alley", "Side Lane %d" % (len(self.alleys) + 1), lane_w, a))
        self.strip_poly = poly

    def _blocks(self):
        r = self.rng.fork("alleys")
        for c, (x0, x1, kind) in enumerate(self.block_cols):
            for rr, (y0, y1) in enumerate(self.block_rows):
                district = self._district(c, rr)
                if self.arena == "takeshita" and c == self.strip_col:
                    if rr == 0:
                        self._strip_blocks(c, x0, x1, district)
                    if rr <= 1:
                        continue
                poly = self._quad(x0, y0, x1, y1)
                w, h = x1 - x0, y1 - y0
                reserved = kind == "site" or (c, rr) in self.reserved_cells()
                if reserved:
                    self._add_block("site" if kind == "site" else "block", district, c, rr, poly, name=self.reserved_cells().get((c, rr)))
                    continue
                # alleys: a N-S alley in wide blocks, an E-W alley in deep ones
                if w >= 128.0 and h >= 128.0 and r.chance(0.8):       # cross alleys: four sub-blocks
                    self._cross(poly, c, rr, district, r.uniform(0.40, 0.60), r.uniform(0.40, 0.60), r.uniform(24.0, 36.0), r.uniform(24.0, 36.0), w, h)
                elif w >= 112.0 and r.chance(0.9):
                    self._split(poly, c, rr, district, "ns", r.uniform(0.38, 0.62), r.uniform(24.0, 36.0), w, h)
                elif h >= 112.0 and r.chance(0.8):
                    self._split(poly, c, rr, district, "ew", r.uniform(0.38, 0.62), r.uniform(24.0, 36.0), w, h)
                else:
                    self._add_block("block", district, c, rr, poly)

    def reserved_cells(self):
        """(col,row) -> site name for blocks kept free for hero buildings (decided from the grid, not from random draws)."""
        if hasattr(self, "_reserved"):
            return self._reserved
        if self.arena == "takeshita":
            c = self.strip_col
            res = {(c + 1, 3): "glass_tower_site", (c - 1, 3): "tower_lattice_site", (c, 3): "twin_hall_site", (0, 1): "temple_site"}
            self._reserved = res
            return res
        # scramble crossing joins the first avenue and the boulevard; the glass tower and the twin hall flank it
        av = self.avenue_idx[0]                  # street index k lies between columns k and k+1
        res = {(av, 2): "glass_tower_site", (av + 1, 3): "tower_lattice_site"}
        # the temple precinct sits in the west
        res[(0, 1)] = "temple_site"
        # twin hall: the widest remaining block of the top two rows
        best = None
        for c, (x0, x1, kind) in enumerate(self.block_cols):
            for rr in (2, 3):
                if kind != "block" or (c, rr) in res:
                    continue
                if c in (av, av + 1):
                    continue
                if best is None or (x1 - x0) > best[0]:
                    best = (x1 - x0, c, rr)
        res[(best[1], best[2])] = "twin_hall_site"
        self._reserved = res
        return res

    def _split(self, poly, c, r, district, axis, f, wa, w, h):
        if axis == "ns":
            half = wa / 2.0 / w
            a = self._sub(poly, 0.0, f - half, 0.0, 1.0)
            b = self._sub(poly, f + half, 1.0, 0.0, 1.0)
            p0 = self.bilinear(poly, f, 0.0)
            p1 = self.bilinear(poly, f, 1.0)
            n = 4
            pts = [self.bilinear(poly, f, k / n) for k in range(n + 1)]
            # extend slightly into the bounding streets so the polylines meet
            dx, dy = pts[0][0] - pts[1][0], pts[0][1] - pts[1][1]
            ln = math.hypot(dx, dy)
            pts[0] = (pts[0][0] + dx / ln * 6.0, pts[0][1] + dy / ln * 6.0)
            dx, dy = pts[-1][0] - pts[-2][0], pts[-1][1] - pts[-2][1]
            ln = math.hypot(dx, dy)
            pts[-1] = (pts[-1][0] + dx / ln * 6.0, pts[-1][1] + dy / ln * 6.0)
        else:
            half = wa / 2.0 / h
            a = self._sub(poly, 0.0, 1.0, 0.0, f - half)
            b = self._sub(poly, 0.0, 1.0, f + half, 1.0)
            n = 4
            pts = [self.bilinear(poly, k / n, f) for k in range(n + 1)]
            dx, dy = pts[0][0] - pts[1][0], pts[0][1] - pts[1][1]
            ln = math.hypot(dx, dy)
            pts[0] = (pts[0][0] + dx / ln * 6.0, pts[0][1] + dy / ln * 6.0)
            dx, dy = pts[-1][0] - pts[-2][0], pts[-1][1] - pts[-2][1]
            ln = math.hypot(dx, dy)
            pts[-1] = (pts[-1][0] + dx / ln * 6.0, pts[-1][1] + dy / ln * 6.0)
        rid = self._road("alley", "Alley %d" % (len(self.alleys) + 1), round(wa, 1), pts)
        self.alleys.append(rid)
        self._add_block("block", district, c, r, a, sub=True)
        self._add_block("block", district, c, r, b, sub=True)

    def _alley_line(self, pts):
        n = len(pts)
        for a, b in ((0, 1), (n - 1, n - 2)):
            dx, dy = pts[a][0] - pts[b][0], pts[a][1] - pts[b][1]
            ln = math.hypot(dx, dy)
            pts[a] = (pts[a][0] + dx / ln * 6.0, pts[a][1] + dy / ln * 6.0)
        return pts

    def _cross(self, poly, c, r, district, fu, fv, wau, wav, w, h):
        hu, hv = wau / 2.0 / w, wav / 2.0 / h
        for (u0, u1) in ((0.0, fu - hu), (fu + hu, 1.0)):
            for (v0, v1) in ((0.0, fv - hv), (fv + hv, 1.0)):
                self._add_block("block", district, c, r, self._sub(poly, u0, u1, v0, v1), sub=True)
        a = self._alley_line([self.bilinear(poly, fu, k / 4.0) for k in range(5)])
        self.alleys.append(self._road("alley", "Alley %d" % (len(self.alleys) + 1), round(wau, 1), a))
        b = self._alley_line([self.bilinear(poly, k / 4.0, fv) for k in range(5)])
        self.alleys.append(self._road("alley", "Alley %d" % (len(self.alleys) + 1), round(wav, 1), b))

    def _sub(self, poly, u0, u1, v0, v1):
        return [self.bilinear(poly, u0, v0), self.bilinear(poly, u1, v0), self.bilinear(poly, u1, v1), self.bilinear(poly, u0, v1)]

    # ---- queries ----------------------------------------------------------------------------------------------------
    def road_by_id(self, rid):
        for r in self.roads:
            if r["id"] == rid:
                return r
        raise KeyError(rid)

    def scramble_centre(self):
        """Centre of the junction of the first avenue and the boulevard (the 80 x 80 m crossing)."""
        if self.plaza is not None:
            return tuple(self.plaza["center"])
        xc, w, _, _ = self.vlines[self.avenue_idx[0]]
        yc, hw, _ = self.hlines[PLAZA_BOULEVARD]
        return self.warp(xc, yc)
