"""Street grid, blocks, plaza, dead-end alley and hero sites for the coastal district.

Layout (x right, y from the sea toward the city, metres). Columns from west to east (block widths in m):
  130 | street 44 | 240 (stadium column) | street 50 | 130 | AVENUE 90 | 140 | street 50 | 150 | AVENUE 90 | 320 (port / power) | street 44 | 122
Cross streets (along X): y = 520 (50 m), 720 (60 m), 930 (50 m); a promenade runs along the shoreline.
"""
import math

from . import noise
from .geom import polys_intersect

COLS = [("block", 130), ("street", 44), ("block", 240), ("street", 50), ("block", 130), ("avenue", 90), ("block", 140),
        ("street", 50), ("block", 150), ("avenue", 90), ("block", 320), ("street", 44), ("block", 122)]
CROSS = [(520.0, 50.0), (720.0, 60.0), (945.0, 50.0)]
Y_TOP = 1200.0           # roads run to the arena edge
BLOCK_TOP = 1178.0       # blocks stop short of it (keeps the last row within 120-250 m)
X_MIN = -800.0
PLAZA_Y = (745.0, 925.0)


class Layout:
    def __init__(self, seed, terrain, rng):
        self.seed = seed
        self.terrain = terrain
        self.rng = rng
        self.roads = []
        self.blocks = []
        self.sites = {}
        self.vlines = []     # (x_center, width, kind)
        self.block_cols = [] # (x_left, x_right)
        x = X_MIN
        for kind, w in COLS:
            if kind == "block":
                self.block_cols.append((x, x + w))
            else:
                self.vlines.append((x + w / 2.0, float(w), kind))
            x += w
        assert abs(x - 800.0) < 1e-6, x
        self._build()

    # --- distortion: smooth warp applied consistently to roads and blocks ------------------------
    def warp(self, x, y):
        s = self.seed
        dx = 22.0 * (noise.fbm2(x / 380.0, y / 380.0, s + 21, 2))
        dy = 22.0 * (noise.fbm2(x / 380.0 + 7.3, y / 380.0 + 3.1, s + 22, 2))
        return (x + dx, y + dy)

    def _row_edges(self, col_x0, col_x1):
        """List of (y_bottom, y_top) block rows for a column; row 0 follows the shoreline."""
        t = self.terrain
        yb0 = max(t.coast_y(col_x0), t.coast_y(col_x1), t.coast_y((col_x0 + col_x1) / 2.0)) + 62.0
        edges = []
        prev = yb0
        for yc, w in CROSS:
            edges.append((prev, yc - w / 2.0))
            prev = yc + w / 2.0
        edges.append((prev, BLOCK_TOP))
        return edges

    def _quad(self, x0, y0, x1, y1):
        pts = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
        return [self.warp(px, py) for px, py in pts]

    def _line(self, a, b, step=60.0):
        n = max(2, int(math.hypot(b[0] - a[0], b[1] - a[1]) / step) + 1)
        return [self.warp(a[0] + (b[0] - a[0]) * i / n, a[1] + (b[1] - a[1]) * i / n) for i in range(n + 1)]

    def _road(self, kind, name, width, pts, dead_end=False):
        rid = "road_%02d" % (len(self.roads) + 1)
        self.roads.append({"id": rid, "kind": kind, "name": name, "width": float(width),
                           "points": [[round(p[0], 1), round(p[1], 1)] for p in pts], "dead_end": dead_end})
        return rid

    def _build(self):
        t = self.terrain
        # promenade along the shore
        pts = []
        x = -800.0
        while x <= 800.0 + 1e-6:
            pts.append((x, t.coast_y(x) + 30.0))
            x += 80.0
        self._road("promenade", "Seaside Promenade", 40.0, pts)
        # vertical streets and avenues
        for k, (xc, w, kind) in enumerate(self.vlines):
            y0 = t.coast_y(xc) + 30.0
            if abs(xc - self._plaza_street_x()) < 1.0:
                self._road(kind, "Street V%d south" % (k + 1), w, self._line((xc, y0), (xc, PLAZA_Y[0])))
                self._road(kind, "Street V%d north" % (k + 1), w, self._line((xc, PLAZA_Y[1]), (xc, Y_TOP)))
            else:
                self._road("avenue" if kind == "avenue" else "street", ("Avenue %d" if kind == "avenue" else "Street V%d") % (k + 1), w,
                           self._line((xc, y0), (xc, Y_TOP)))
        # cross streets
        for j, (yc, w) in enumerate(CROSS):
            self._road("street", "Cross Street %d" % (j + 1), w, self._line((-800.0, yc), (800.0, yc)))
        # blocks
        stadium_col = 1
        for c, (x0, x1) in enumerate(self.block_cols):
            rows = self._row_edges(x0, x1)
            for r, (yb, yt) in enumerate(rows):
                kind = "block"
                district = self._district(c, r)
                poly = self._quad(x0, yb, x1, yt)
                if c == 5:
                    kind = "site"                      # the wide port / power-station column
                if r == 2 and c in (3, 4):
                    continue                           # merged into the plaza below
                if c == 1 and r == 3:
                    # dead-end alley splits this block (length ~200 m, width 40 m)
                    xm = (x0 + x1) / 2.0
                    self._road("alley", "Dead-end Alley", 40.0, self._line((xm, CROSS[2][0] + CROSS[2][1] / 2.0), (xm, yt - 45.0), 50.0), dead_end=True)
                    for (a, b) in ((x0, xm - 20.0), (xm + 20.0, x1)):
                        self._add_block("block", district, c, r, self._quad(a, yb, b, yt), sub=True)
                    continue
                self._add_block(kind, district, c, r, poly, name=("stadium_site" if (c == stadium_col and r == 1) else None))
        # plaza = blocks (3,2)+(4,2) plus the street between them
        x0 = self.block_cols[3][0]
        x1 = self.block_cols[4][1]
        poly = self._quad(x0, PLAZA_Y[0] - 5.0, x1, PLAZA_Y[1] + 5.0)
        self._add_block("plaza", "civic", 3, 2, poly, name="central_plaza")

    def _plaza_street_x(self):
        # the vertical street lying between block columns 3 and 4 is the one interrupted by the plaza
        return self.block_cols[3][1] + (self.block_cols[4][0] - self.block_cols[3][1]) / 2.0

    def _district(self, c, r):
        if c >= 5 and r <= 1:
            return "industrial"
        if 2 <= c <= 4 and 1 <= r <= 3:
            return "downtown"
        if c <= 1:
            return "residential"
        return "mixed"

    def _add_block(self, kind, district, c, r, poly, name=None, sub=False):
        bid = "block_%02d" % (len(self.blocks) + 1)
        b = {"id": bid, "kind": kind, "district": district, "col": c, "row": r, "polygon": [[round(p[0], 1), round(p[1], 1)] for p in poly]}
        if name:
            b["name"] = name
        if sub:
            b["sub_block"] = True          # one side of the dead-end alley: narrower than a regular block
        self.blocks.append(b)
        if name:
            self.sites[name] = b
        return b

    # --- lot subdivision --------------------------------------------------------------------------
    @staticmethod
    def bilinear(poly, u, v):
        """poly: [(x0,y0),(x1,y0),(x1,y1),(x0,y1)] warped corners; u,v in [0,1]."""
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
