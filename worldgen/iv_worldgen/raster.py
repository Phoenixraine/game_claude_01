"""Tiny software rasteriser (RGB bytearray) with a built-in 5x7 font; enough for map previews."""

_FONT_ROWS = {
    "A": "01110 10001 10001 11111 10001 10001 10001", "B": "11110 10001 10001 11110 10001 10001 11110",
    "C": "01110 10001 10000 10000 10000 10001 01110", "D": "11110 10001 10001 10001 10001 10001 11110",
    "E": "11111 10000 10000 11110 10000 10000 11111", "F": "11111 10000 10000 11110 10000 10000 10000",
    "G": "01110 10001 10000 10111 10001 10001 01111", "H": "10001 10001 10001 11111 10001 10001 10001",
    "I": "01110 00100 00100 00100 00100 00100 01110", "J": "00111 00010 00010 00010 00010 10010 01100",
    "K": "10001 10010 10100 11000 10100 10010 10001", "L": "10000 10000 10000 10000 10000 10000 11111",
    "M": "10001 11011 10101 10101 10001 10001 10001", "N": "10001 11001 10101 10011 10001 10001 10001",
    "O": "01110 10001 10001 10001 10001 10001 01110", "P": "11110 10001 10001 11110 10000 10000 10000",
    "Q": "01110 10001 10001 10001 10101 10010 01101", "R": "11110 10001 10001 11110 10100 10010 10001",
    "S": "01111 10000 10000 01110 00001 00001 11110", "T": "11111 00100 00100 00100 00100 00100 00100",
    "U": "10001 10001 10001 10001 10001 10001 01110", "V": "10001 10001 10001 10001 10001 01010 00100",
    "W": "10001 10001 10001 10101 10101 11011 10001", "X": "10001 10001 01010 00100 01010 10001 10001",
    "Y": "10001 10001 01010 00100 00100 00100 00100", "Z": "11111 00001 00010 00100 01000 10000 11111",
    "0": "01110 10001 10011 10101 11001 10001 01110", "1": "00100 01100 00100 00100 00100 00100 01110",
    "2": "01110 10001 00001 00010 00100 01000 11111", "3": "11110 00001 00001 01110 00001 00001 11110",
    "4": "00010 00110 01010 10010 11111 00010 00010", "5": "11111 10000 11110 00001 00001 10001 01110",
    "6": "00110 01000 10000 11110 10001 10001 01110", "7": "11111 00001 00010 00100 01000 01000 01000",
    "8": "01110 10001 10001 01110 10001 10001 01110", "9": "01110 10001 10001 01111 00001 00010 01100",
    " ": "00000 00000 00000 00000 00000 00000 00000", "-": "00000 00000 00000 11111 00000 00000 00000",
    ".": "00000 00000 00000 00000 00000 01100 01100", ":": "00000 01100 01100 00000 01100 01100 00000",
    "(": "00010 00100 01000 01000 01000 00100 00010", ")": "01000 00100 00010 00010 00010 00100 01000",
    "/": "00001 00001 00010 00100 01000 10000 10000", "+": "00000 00100 00100 11111 00100 00100 00000",
    "=": "00000 00000 11111 00000 11111 00000 00000", ",": "00000 00000 00000 00000 01100 00100 01000",
    "%": "11001 11010 00010 00100 01000 01011 10011", "_": "00000 00000 00000 00000 00000 00000 11111",
}
FONT = {ch: [[c == "1" for c in row] for row in spec.split()] for ch, spec in _FONT_ROWS.items()}


class Canvas:
    def __init__(self, width, height, bg=(0, 0, 0)):
        self.w = width
        self.h = height
        self.buf = bytearray(bytes(bg) * (width * height))

    def px(self, x, y, c):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 3
            self.buf[i] = c[0]
            self.buf[i + 1] = c[1]
            self.buf[i + 2] = c[2]

    def blend(self, x, y, c, a):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 3
            b = self.buf
            b[i] = int(b[i] + (c[0] - b[i]) * a)
            b[i + 1] = int(b[i + 1] + (c[1] - b[i + 1]) * a)
            b[i + 2] = int(b[i + 2] + (c[2] - b[i + 2]) * a)

    def hline(self, x0, x1, y, c):
        if not (0 <= y < self.h):
            return
        x0 = max(0, x0)
        x1 = min(self.w - 1, x1)
        if x1 < x0:
            return
        i = (y * self.w + x0) * 3
        self.buf[i:i + (x1 - x0 + 1) * 3] = bytes(c) * (x1 - x0 + 1)

    def rect(self, x0, y0, x1, y1, c):
        for y in range(max(0, y0), min(self.h - 1, y1) + 1):
            self.hline(x0, x1, y, c)

    def polygon(self, pts, c, alpha=1.0):
        """Scanline even-odd fill; pts are pixel coordinates."""
        if len(pts) < 3:
            return
        ymin = max(0, int(min(p[1] for p in pts)))
        ymax = min(self.h - 1, int(max(p[1] for p in pts)))
        n = len(pts)
        for y in range(ymin, ymax + 1):
            yc = y + 0.5
            xs = []
            for i in range(n):
                x0, y0 = pts[i]
                x1, y1 = pts[(i + 1) % n]
                if (y0 <= yc < y1) or (y1 <= yc < y0):
                    xs.append(x0 + (yc - y0) * (x1 - x0) / (y1 - y0))
            xs.sort()
            for k in range(0, len(xs) - 1, 2):
                a = int(round(xs[k]))
                b = int(round(xs[k + 1])) - 1
                if alpha >= 1.0:
                    self.hline(a, b, y, c)
                else:
                    for x in range(max(0, a), min(self.w - 1, b) + 1):
                        self.blend(x, y, c, alpha)

    def line(self, p0, p1, c, width=1):
        x0, y0 = p0
        x1, y1 = p1
        dx = x1 - x0
        dy = y1 - y0
        steps = int(max(abs(dx), abs(dy))) + 1
        r = max(0, (width - 1) // 2)
        for i in range(steps + 1):
            t = i / steps if steps else 0.0
            x = int(round(x0 + dx * t))
            y = int(round(y0 + dy * t))
            for ox in range(-r, r + 1):
                for oy in range(-r, r + 1):
                    self.px(x + ox, y + oy, c)

    def thick_line(self, p0, p1, half_width, c):
        """Filled quad around a segment (road ribbons)."""
        x0, y0 = p0
        x1, y1 = p1
        dx = x1 - x0
        dy = y1 - y0
        ln = (dx * dx + dy * dy) ** 0.5
        if ln < 1e-9:
            return
        nx = -dy / ln * half_width
        ny = dx / ln * half_width
        self.polygon([(x0 + nx, y0 + ny), (x1 + nx, y1 + ny), (x1 - nx, y1 - ny), (x0 - nx, y0 - ny)], c)

    def disc(self, cx, cy, r, c):
        for y in range(int(cy - r), int(cy + r) + 1):
            for x in range(int(cx - r), int(cx + r) + 1):
                if (x - cx) ** 2 + (y - cy) ** 2 <= r * r:
                    self.px(x, y, c)

    def outline(self, pts, c, width=1):
        for i in range(len(pts)):
            self.line(pts[i], pts[(i + 1) % len(pts)], c, width)

    def text(self, x, y, s, c, scale=1):
        cx = x
        for ch in s.upper():
            glyph = FONT.get(ch, FONT[" "])
            for ry, row in enumerate(glyph):
                for rx, on in enumerate(row):
                    if on:
                        for sy in range(scale):
                            for sx in range(scale):
                                self.px(cx + rx * scale + sx, y + ry * scale + sy, c)
            cx += 6 * scale
        return cx

    @staticmethod
    def text_width(s, scale=1):
        return len(s) * 6 * scale
