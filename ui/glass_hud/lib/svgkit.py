"""Tiny SVG helpers: number formatting, glow-by-stacked-strokes (cairosvg has no blur filter), colour maths for the contrast tests."""
import math


def n(v):
    s = ("%.2f" % v).rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def attrs(d):
    return " ".join('%s="%s"' % (k.replace("_", "-"), v) for k, v in d.items() if v is not None)


def pts(points):
    return " ".join("%s,%s" % (n(x), n(y)) for x, y in points)


def poly_d(points, close=True):
    d = "M" + " L".join("%s %s" % (n(x), n(y)) for x, y in points)
    return d + (" Z" if close else "")


def arc_d(cx, cy, r, a0, a1):
    """SVG path of a circular arc from angle a0 to a1 (degrees, 0 = +X, clockwise on screen because Y points down)."""
    x0, y0 = cx + r * math.cos(math.radians(a0)), cy + r * math.sin(math.radians(a0))
    x1, y1 = cx + r * math.cos(math.radians(a1)), cy + r * math.sin(math.radians(a1))
    large = 1 if abs(a1 - a0) > 180 else 0
    sweep = 1 if a1 > a0 else 0
    return "M%s %s A%s %s 0 %d %d %s %s" % (n(x0), n(y0), n(r), n(r), large, sweep, n(x1), n(y1))


def glow(d, color, w=2.0, opacity=1.0, fill="none", dash=None, halo="#0b1220", cap="round", extra=""):
    """A thin AR line: dark halo (readable on bright backgrounds), three faint wider strokes (glow) and the bright core. d = path data."""
    da = ' stroke-dasharray="%s"' % dash if dash else ""
    base = 'fill="%s" stroke-linecap="%s" stroke-linejoin="round"%s %s' % (fill, cap, da, extra)
    out = ['<path d="%s" %s stroke="%s" stroke-width="%s" stroke-opacity="%s"/>' % (d, base, halo, n(w + 2.4), n(0.5 * opacity))]
    for k, o in ((4.0, 0.07), (2.6, 0.13), (1.6, 0.25)):
        out.append('<path d="%s" %s stroke="%s" stroke-width="%s" stroke-opacity="%s"/>' % (d, base, color, n(w * k), n(o * opacity)))
    out.append('<path d="%s" %s stroke="%s" stroke-width="%s" stroke-opacity="%s"/>' % (d, base, color, n(w), n(opacity)))
    return "".join(out)


def fill_poly(d, color, opacity=0.18):
    return '<path d="%s" fill="%s" fill-opacity="%s" stroke="none"/>' % (d, color, n(opacity))


def svg_doc(w, h, inner, view=None, title=None, defs=""):
    vb = view or (0, 0, w, h)
    t = "<title>%s</title>" % title if title else ""
    return ('<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="%s" height="%s" viewBox="%s %s %s %s">%s%s%s</svg>\n'
            % (n(w), n(h), n(vb[0]), n(vb[1]), n(vb[2]), n(vb[3]), t, ("<defs>%s</defs>" % defs) if defs else "", inner))


def hex_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def luminance(h):
    def c(v):
        v /= 255.0
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (c(v) for v in hex_rgb(h))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    la, lb = luminance(a), luminance(b)
    if la < lb:
        la, lb = lb, la
    return (la + 0.05) / (lb + 0.05)


def blend_hex(a, b, t):
    ra, rb = hex_rgb(a), hex_rgb(b)
    return "#%02x%02x%02x" % tuple(int(round(x + (y - x) * t)) for x, y in zip(ra, rb))
