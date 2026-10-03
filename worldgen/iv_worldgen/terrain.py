"""Terrain: sea floor sloping 0..-25 m away from the shore, promenade, gentle land, flood basins."""
import math
import struct

from . import noise

X0, X1 = -800.0, 800.0
Y0, Y1 = -400.0, 1200.0
N = 1009                      # Unreal Landscape compatible vertex count
CELL = (X1 - X0) / (N - 1)    # ~1.587 m
SEA_FLOOR = -25.0
ZERO_VALUE = 32768            # r16 value of z = 0
UNITS_PER_M = 128.0           # Unreal Landscape: 1/128 m per unit at Z scale 100


def _smooth(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


NC = 253                       # coarse noise grid (spacing ~6.3 m): plenty for 90-240 m wavelengths


class Terrain:
    def __init__(self, seed, basins):
        self.seed = seed
        self.basins = basins          # list of (cx, cy, radius, depth)
        self.coast = [self._coast_y(X0 + i * CELL) for i in range(N)]
        cs = (X1 - X0) / (NC - 1)
        self.sea_noise = [[noise.fbm2((X0 + k * cs) / 90.0, (Y0 + r * (Y1 - Y0) / (NC - 1)) / 90.0, seed + 3, 2) for k in range(NC)] for r in range(NC)]
        self.land_noise = [[noise.fbm2((X0 + k * cs) / 240.0, (Y0 + r * (Y1 - Y0) / (NC - 1)) / 240.0, seed + 5, 3) for k in range(NC)] for r in range(NC)]
        # fine -> coarse x lookup tables
        self._kx = []
        for i in range(N):
            f = i * (NC - 1) / (N - 1)
            k = min(NC - 2, int(f))
            self._kx.append((k, f - k))
        self.h = [self._row(j) for j in range(N)]
        self._update_range()

    def _update_range(self):
        zs = [z for row in self.h for z in row]
        self.min_z, self.max_z = min(zs), max(zs)

    def _coast_y(self, x):
        return 245.0 + 36.0 * (noise.value1(x / 360.0, self.seed + 11) * 2 - 1) + 14.0 * (noise.value1(x / 110.0, self.seed + 12) * 2 - 1)

    def coast_y(self, x):
        f = (x - X0) / CELL
        i = max(0, min(N - 2, int(f)))
        t = f - i
        return self.coast[i] * (1 - t) + self.coast[i + 1] * t

    def _interp_row(self, grid, j):
        f = j * (NC - 1) / (N - 1)
        r = min(NC - 2, int(f))
        ty = f - r
        a, b = grid[r], grid[r + 1]
        line = [a[k] + (b[k] - a[k]) * ty for k in range(NC)]
        kx = self._kx
        return [line[k] + (line[k + 1] - line[k]) * t for k, t in kx]

    def _row(self, j):
        y = Y0 + j * CELL
        sea = self._interp_row(self.sea_noise, j)
        land = self._interp_row(self.land_noise, j)
        coast = self.coast
        basins = [b for b in self.basins if abs(y - b[1]) < b[2]]
        row = []
        for i in range(N):
            c = coast[i]
            if y < c:
                t = (c - y) / 175.0                           # gentle slope: ~175 m from the shore to -25 m
                t = 1.0 if t > 1.0 else t
                w = t * t * (3.0 - 2.0 * t)
                row.append(SEA_FLOOR * w + 1.0 * sea[i] * w)
            else:
                d = y - c
                u = d / 40.0
                u = 1.0 if u > 1.0 else u
                v = d / 120.0
                v = 1.0 if v > 1.0 else v
                z = 0.0045 * d + 2.8 * (u * u * (3 - 2 * u)) + 2.4 * land[i] * (v * v * (3 - 2 * v))   # beach, then the raised promenade
                for cx, cy, r, depth in basins:               # low-lying flood basins
                    x = X0 + i * CELL
                    rr = ((x - cx) ** 2 + (y - cy) ** 2) / (r * r)
                    if rr < 1.0:
                        z -= depth * (1.0 - rr) ** 2
                row.append(z)
        return row

    # --- queries ---------------------------------------------------------------------------
    def height(self, x, y):
        fx = (min(max(x, X0), X1) - X0) / CELL
        fy = (min(max(y, Y0), Y1) - Y0) / CELL
        i = min(N - 2, int(fx))
        j = min(N - 2, int(fy))
        tx, ty = fx - i, fy - j
        h = self.h
        a = h[j][i] * (1 - tx) + h[j][i + 1] * tx
        b = h[j + 1][i] * (1 - tx) + h[j + 1][i + 1] * tx
        return a * (1 - ty) + b * ty

    def is_water(self, x, y):
        return self.height(x, y) < 0.0

    def flatten(self, poly, z, margin=10.0):
        """Pad under a footprint: set heights inside the polygon to z and blend out over `margin` metres."""
        from .geom import bbox, dist_to_poly_edges, point_in_poly
        x0, y0, x1, y1 = bbox(poly)
        i0 = max(0, int((x0 - margin - X0) / CELL))
        i1 = min(N - 1, int((x1 + margin - X0) / CELL) + 1)
        j0 = max(0, int((y0 - margin - Y0) / CELL))
        j1 = min(N - 1, int((y1 + margin - Y0) / CELL) + 1)
        for j in range(j0, j1 + 1):
            y = Y0 + j * CELL
            row = self.h[j]
            for i in range(i0, i1 + 1):
                x = X0 + i * CELL
                if point_in_poly((x, y), poly):
                    row[i] = z
                else:
                    d, _ = dist_to_poly_edges((x, y), poly)
                    if d < margin:
                        t = d / margin
                        t = t * t * (3 - 2 * t)
                        row[i] = z * (1 - t) + row[i] * t

    def to_r16(self):
        out = bytearray()
        for row in self.h:
            vals = [min(65535, max(0, int(round(ZERO_VALUE + z * UNITS_PER_M)))) for z in row]
            out += struct.pack("<%dH" % N, *vals)
        return bytes(out)

    def metadata(self):
        return {
            "heightmap": "heightmap.r16",
            "format": "r16_little_endian",
            "resolution": N,
            "row_order": "y_ascending",          # row 0 = y_min (sea side), column 0 = x_min
            "extent": {"x_min": X0, "x_max": X1, "y_min": Y0, "y_max": Y1},
            "cell_size_m": round(CELL, 4),
            "height_encoding": {"zero_value": ZERO_VALUE, "units_per_meter": UNITS_PER_M},
            "min_z": round(self.min_z, 2),
            "max_z": round(self.max_z, 2),
            "sea_level_z": 0.0,
            "unreal_landscape_hint": "Import as r16, 1009x1009; Z scale 100 maps 1 unit to 1/128 m; flip Y on import if the "
                                     "landscape origin is at y_max.",
        }

    def shoreline(self, step=40.0):
        pts = []
        x = X0
        while x <= X1 + 1e-6:
            pts.append([round(x, 1), round(self.coast_y(x), 1)])
            x += step
        return pts
