"""Vector drawings of the HUD pieces. Every function returns inner SVG markup in its own local coordinate system (documented per function)."""
import math

from . import data
from .svgkit import arc_d, blend_hex, fill_poly, glow, n, poly_d

PAL = data.PALETTE["colors"]
ST = data.STATES

# ------------------------------------------------------------------------------------------------------------------ body silhouette (viewBox 400 x 540)
BODY_W, BODY_H = 400.0, 540.0


def _mx(points):
    return [(400.0 - x, y) for x, y in points]


_R = {
    "Head": [(182, 36), (218, 36), (228, 56), (214, 78), (186, 78), (172, 56)],
    "Torso": [(158, 96), (242, 96), (256, 150), (246, 236), (154, 236), (144, 150)],
    "Reactor": [(200, 134), (222, 147), (222, 173), (200, 186), (178, 173), (178, 147)],
    "ShoulderR": [(248, 88), (312, 86), (334, 118), (324, 158), (264, 156), (254, 128)],
    "ArmR": [(298, 166), (332, 170), (346, 246), (356, 318), (364, 366), (352, 396), (326, 396), (320, 330), (304, 252)],
    "LegR": [(206, 244), (262, 244), (276, 330), (270, 420), (284, 500), (292, 522), (236, 522), (232, 424), (208, 330)],
}
# Zones as seen from behind the player's own mech (the pilot's left is screen-left). The enemy faces the pilot: its silhouette is mirrored.
OUTLINE_PLAYER = {
    "Head": _R["Head"], "Torso": _R["Torso"], "Reactor": _R["Reactor"],
    "ShoulderR": _R["ShoulderR"], "ShoulderL": _mx(_R["ShoulderR"]), "ArmR": _R["ArmR"], "ArmL": _mx(_R["ArmR"]), "LegR": _R["LegR"], "LegL": _mx(_R["LegR"]),
}
OUTLINE_ENEMY = {z: _mx(p) for z, p in OUTLINE_PLAYER.items()}

# where the 3 layer arcs of a zone sit: (centre, base radius, centre angle in degrees (screen), clockwise)
ARC_ANCHOR = {
    "Head": ((200, 57), 30, 270), "Torso": ((200, 166), 62, 90), "Reactor": ((200, 160), 30, 90),
    "ShoulderL": ((100, 124), 36, 270), "ShoulderR": ((300, 124), 36, 270),
    "ArmL": ((56, 286), 40, 180), "ArmR": ((344, 286), 40, 0), "LegL": ((120, 380), 62, 180), "LegR": ((280, 380), 62, 0),
}


def _outline(side):
    return OUTLINE_PLAYER if side == "player" else OUTLINE_ENEMY


def zone_style(state):
    s = ST["zone_state_style"][state]
    return PAL[s["color"]], s


def silhouette(side, zones=None, blink_on=True):
    """Front silhouette of a mech, 9 zone polygons with ids zone_<Zone>. zones: {Zone: state_name}; the default is everything Intact. viewBox 0 0 400 540."""
    zones = zones or {}
    out = []
    for z in data.ZONES:
        state = zones.get(z, "Intact")
        col, s = zone_style(state)
        pts = _outline(side)[z]
        d = poly_d(pts)
        op = 1.0
        if s["blink_hz"] > 0 and not blink_on:
            op = 0.25
        parts = [fill_poly(d, col, s["fill_opacity"] * (1.0 if blink_on else 0.4)), glow(d, col, s["width"], op, dash=s["dash"])]
        if s.get("slash"):
            xs, ys = [p[0] for p in pts], [p[1] for p in pts]
            parts.append(glow("M%s %s L%s %s" % (n(min(xs)), n(max(ys)), n(max(xs)), n(min(ys))), col, 1.6, 0.9))
        out.append('<g id="zone_%s" data-state="%s">%s</g>' % (z, state, "".join(parts)))
    # decorative inner lines (spine, hips) in a faint neutral so the silhouette reads as a machine
    deco = ""
    for d in ("M200 78 L200 96", "M158 236 L242 236", "M178 120 L222 120"):
        deco += glow(d, PAL["neutral"], 1.6, 0.35)
    return '<g id="body_%s">%s%s</g>' % (side, deco, "".join(out))


def layer_arcs(side, zones=None, layers=None, blink_on=True):
    """Three thin arcs per zone (Armor outermost, Mechanism, System innermost) with ids arc_<Zone>_<Layer>. layers: {Zone: [a, m, s]} remaining fractions 0..1. viewBox 0 0 400 540."""
    zones, layers = zones or {}, layers or {}
    sweep = ST["layer_arc"]["sweep_deg"]
    step = ST["layer_arc"]["radius_step"]
    out = []
    for z in data.ZONES:
        c, r0, ang = (ARC_ANCHOR if side == "player" else enemy_fix_angles())[z]
        state = zones.get(z, "Intact")
        col, s = zone_style(state)
        fr = layers.get(z, [1.0, 1.0, 1.0])
        for i, ln in enumerate(data.LAYERS):
            r = r0 + step * (2 - i) if z != "Reactor" else r0 + step * i
            a0, a1 = ang - sweep / 2, ang + sweep / 2
            track = arc_d(c[0], c[1], r, a0, a1)
            g = glow(track, PAL["lost"], 1.2, 0.3, dash="2 4")
            f = 0.0 if state in ("Destroyed", "Severed") else max(0.0, min(1.0, fr[i]))
            if f > 0.01:
                op = 1.0 if (s["blink_hz"] == 0 or blink_on) else 0.3
                g += glow(arc_d(c[0], c[1], r, a0, a0 + (a1 - a0) * f), col, 2.6, op)
            out.append('<g id="arc_%s_%s">%s</g>' % (z, ln, g))
    return '<g id="layer_arcs_%s">%s</g>' % (side, "".join(out))


def enemy_fix_angles():
    """Mirrored arc anchors for the enemy silhouette: x flips, so the 0 / 180 degree centre angles swap."""
    return {z: (((400 - c[0], c[1]), r, {0: 180, 180: 0}.get(a, a))) for z, (c, r, a) in ARC_ANCHOR.items()}


# ------------------------------------------------------------------------------------------------------------------ ring gauges (viewBox 0 0 256 256)
RING_START, RING_SWEEP = 135.0, 270.0


def ring_gauge(kind, value, color, blink_on=True, dead=False, icon=True):
    """270-degree ring gauge from the lower left, clockwise. value 0..1. kind selects ticks / segments. Returns markup in a 256 x 256 box."""
    cx = cy = 128.0
    r = 98.0
    g = ST["gauges"][kind]
    segs = g.get("segments", 0)
    out = [glow(arc_d(cx, cy, r, RING_START, RING_START + RING_SWEEP), PAL["lost"], 3.0, 0.3, dash=None)]
    if kind == "heat":
        for k in range(0, 28):
            a = math.radians(RING_START + RING_SWEEP * k / 27.0)
            r0, r1 = r + 8, r + (16 if k % 3 == 0 else 12)
            out.append(glow("M%s %s L%s %s" % (n(cx + r0 * math.cos(a)), n(cy + r0 * math.sin(a)), n(cx + r1 * math.cos(a)), n(cy + r1 * math.sin(a))), PAL["neutral"], 1.5, 0.5))
    if dead:
        return "".join(out) + glow(arc_d(cx, cy, r, RING_START, RING_START + RING_SWEEP), PAL["lost"], 2.0, 0.7, dash="3 8")
    v = max(0.0, min(1.0, value))
    if v > 0.004:
        a1 = RING_START + RING_SWEEP * v
        if segs:
            seg_deg = RING_SWEEP / segs
            for k in range(segs):
                s0 = RING_START + seg_deg * k
                if s0 + seg_deg * 0.15 > a1:
                    break
                e = min(s0 + seg_deg * 0.82, a1)
                out.append(glow(arc_d(cx, cy, r, s0, e), color, 7.0, 1.0, cap="butt"))
        else:
            out.append(glow(arc_d(cx, cy, r, RING_START, a1), color, 7.0, 1.0 if blink_on else 0.45, cap="butt"))
    # inner ring + pictogram per kind
    out.append(glow(arc_d(cx, cy, 70, 0, 359.9), color, 1.2, 0.35))
    if icon:
        out.append(_gauge_icon(kind, color))
    return "".join(out)


def _gauge_icon(kind, color):
    if kind == "armor":    # shield
        return glow("M128 98 L158 108 L156 138 Q150 158 128 168 Q106 158 100 138 L98 108 Z", color, 2.2, 0.9)
    if kind == "stability":  # stance: wide A-frame legs on a base line
        return glow("M104 170 L128 96 L152 170 M112 146 L144 146 M92 176 L164 176", color, 2.2, 0.9)
    if kind == "heat":      # thermometer
        return glow("M128 92 L128 146 M118 92 Q128 84 138 92 L138 150 A16 16 0 1 1 118 150 Z", color, 2.2, 0.9)
    return glow("M134 90 L108 138 L126 138 L120 172 L150 120 L130 120 Z", color, 2.2, 0.9)  # energy bolt


def ultimate_gauge(value, ready, blink_on=True):
    """Segmented ring (12 blocks, 270 deg) with a double-chevron symbol; ready = full and blinking white. 256 x 256."""
    g = ST["gauges"]["ultimate"]
    col = PAL[g["ready_color"]] if ready else PAL[g["color"]]
    op = 1.0 if (blink_on or not ready) else 0.4
    return ring_gauge("ultimate", value, col, blink_on, icon=False) + glow("M104 150 L128 112 L152 150 M104 176 L128 138 L152 176", col, 2.4, op)


# ------------------------------------------------------------------------------------------------------------------ icons (viewBox 0 0 64 64)
def icon_weapon(kind, color, ring=1.0, dead=False):
    """Weapon pictograms: rail spear (long bolt), rockets (3 small), plasma (core + arcs). ring = cooldown completion arc around the icon."""
    c = PAL["lost"] if dead else color
    dash = "2 4" if dead else None
    if kind == "rail":
        g = glow("M8 52 L56 12 M44 10 L58 10 L58 24 M14 46 L22 54", c, 2.2, 1.0, dash=dash)
    elif kind == "rockets":
        g = "".join(glow("M%s 50 L%s 22 L%s 14 L%s 22 L%s 50" % (x, x - 4, x, x + 4, x + 4), c, 1.8, 1.0, dash=dash) for x in (16, 32, 48))
    else:
        g = glow(arc_d(32, 32, 9, 0, 359.9), c, 2.2, 1.0, dash=dash) + "".join(glow(arc_d(32, 32, 17 + 6 * i, -40 + 30 * i, 40 + 30 * i), c, 1.6, 0.9, dash=dash) for i in range(2))
    r = glow(arc_d(32, 32, 30, -90, -90 + 359.0 * max(0.02, min(1.0, ring))), c, 1.4, 0.8)
    return g + r


def icon_status(kind, color):
    """Status pictograms: blind (eye with slash), strikelock (padlock), burn (flame). 64 x 64."""
    if kind == "blind":
        return glow("M6 32 Q32 8 58 32 Q32 56 6 32 Z", color, 2.0) + glow(arc_d(32, 32, 8, 0, 359.9), color, 2.0) + glow("M12 54 L52 10", color, 2.4)
    if kind == "strikelock":
        return glow("M18 30 L18 22 A14 14 0 0 1 46 22 L46 30 M12 30 L52 30 L52 56 L12 56 Z M32 40 L32 48", color, 2.0)
    return glow("M32 6 C40 20 52 26 50 42 A18 18 0 0 1 14 42 C14 32 22 28 24 18 C28 24 30 26 32 6 Z M32 56 C26 56 24 48 32 40 C40 48 38 56 32 56", color, 2.0)


def icon_warning(color):
    """Triangle with an exclamation mark (no text). 64 x 64."""
    return glow("M32 8 L58 54 L6 54 Z", color, 2.4) + glow("M32 24 L32 40", color, 3.0) + glow(arc_d(32, 47, 0.8, 0, 359.9), color, 3.2)


def threat_arrow(direction, color, strength=1.0):
    """A wedge pointing INTO the screen from an edge: direction up|down|left|right = the edge it sits on. viewBox 0 0 120 120, drawn for 'up' then rotated."""
    rot = {"up": 0, "right": 90, "down": 180, "left": 270}[direction]
    sector = "M60 14 L100 70 L60 52 L20 70 Z"
    body = fill_poly(sector, color, 0.22 * strength) + glow(sector, color, 2.4, 1.0) + glow("M60 76 L88 108 L60 96 L32 108 Z", color, 2.0, 0.7 * strength + 0.3)
    return '<g transform="rotate(%d 60 60)">%s</g>' % (rot, body)


# ------------------------------------------------------------------------------------------------------------------ lock-on (viewBox 0 0 200 200)
def lockon_corners(color, quality=1.0, size=200.0, arm=36.0):
    """Four corner brackets (the reference's thin cyan frame). Quality < 1 shortens the arms. 200 x 200."""
    a = arm * (0.55 + 0.45 * quality)
    m = 6.0
    d = ""
    for sx, sy, x, y in ((1, 1, m, m), (-1, 1, size - m, m), (1, -1, m, size - m), (-1, -1, size - m, size - m)):
        d += "M%s %s L%s %s L%s %s " % (n(x + sx * a), n(y), n(x), n(y), n(x), n(y + sy * a))
    return glow(d, color, 2.4, 1.0)


def lockon_hex(color, pulse=1.0):
    """Hex outline of the selected zone (one big hex + inner hex). 200 x 200."""
    pts = [(100 + 80 * math.cos(math.radians(60 * k - 90)), 100 + 80 * math.sin(math.radians(60 * k - 90))) for k in range(6)]
    pts2 = [(100 + 58 * math.cos(math.radians(60 * k - 90)), 100 + 58 * math.sin(math.radians(60 * k - 90))) for k in range(6)]
    return fill_poly(poly_d(pts), color, 0.1 * pulse) + glow(poly_d(pts), color, 2.4, 1.0) + glow(poly_d(pts2), color, 1.2, 0.6)


def lockon_ring_frame(k, frames=16, color=None, size=128.0):
    """Frame k of the acquisition animation: a ring that contracts from 1.0 to 0.55 with a rotating dash and corner ticks. 128 x 128."""
    color = color or PAL["cyan"]
    t = k / float(frames - 1)
    r = size * (0.5 - 0.20 * t) - 3
    ang = 360.0 * t * 0.5
    out = []
    for i in range(4):
        a0 = ang + 90 * i + 8
        out.append(glow(arc_d(size / 2, size / 2, r, a0, a0 + 56), color, 2.2, 0.4 + 0.6 * t))
    for i in range(4):
        a = math.radians(45 + 90 * i)
        out.append(glow("M%s %s L%s %s" % (n(size / 2 + (r + 3) * math.cos(a)), n(size / 2 + (r + 3) * math.sin(a)), n(size / 2 + (r + 9 - 5 * t) * math.cos(a)), n(size / 2 + (r + 9 - 5 * t) * math.sin(a))), color, 1.6, 0.8))
    if k == frames - 1:
        out.append(glow(arc_d(size / 2, size / 2, r - 7, 0, 359.9), color, 1.2, 0.9))
    return "".join(out)


def strike_arc(points, color, committed=False):
    """The player's strike line: a thin curve through the given points (viewBox is the whole screen of the caller). Template: an S-curve in 400 x 200."""
    d = "M20 160 C120 20 260 20 380 120" if points is None else "M" + " L".join("%s %s" % (n(x), n(y)) for x, y in points)
    return glow(d, color, 2.0, 1.0, dash=None if committed else "10 5") + glow("M374 112 L384 122 L370 126", color, 2.0)


def crosshair(color):
    """Tiny reticle: ring with a gap cross. 48 x 48."""
    return glow(arc_d(24, 24, 9, 0, 359.9), color, 1.4, 0.9) + glow("M24 4 L24 12 M24 36 L24 44 M4 24 L12 24 M36 24 L44 24", color, 1.4, 0.9)


# ------------------------------------------------------------------------------------------------------------------ radar, compass, digits
def radar(color, enemy_angle=None, enemy_dist=0.0, sweep_deg=40.0, dead=False):
    """Round radar, 200 x 200: 3 rings, cross, 12 ticks, a sweep wedge and the enemy blip (angle in degrees from forward = up, dist 0..1). Dead = dotted outline."""
    out = []
    dash = "2 5" if dead else None
    c = PAL["lost"] if dead else color
    for r in (92, 62, 32):
        out.append(glow(arc_d(100, 100, r, 0, 359.9), c, 1.6 if r == 92 else 1.0, 0.9 if r == 92 else 0.45, dash=dash))
    out.append(glow("M100 8 L100 192 M8 100 L192 100", c, 0.9, 0.3, dash=dash))
    for k in range(12):
        a = math.radians(30 * k - 90)
        out.append(glow("M%s %s L%s %s" % (n(100 + 92 * math.cos(a)), n(100 + 92 * math.sin(a)), n(100 + 86 * math.cos(a)), n(100 + 86 * math.sin(a))), c, 1.2, 0.8))
    if dead:
        return "".join(out)
    a0 = math.radians(sweep_deg - 90 - 24)
    a1 = math.radians(sweep_deg - 90)
    out.append(fill_poly("M100 100 L%s %s A92 92 0 0 1 %s %s Z" % (n(100 + 92 * math.cos(a0)), n(100 + 92 * math.sin(a0)), n(100 + 92 * math.cos(a1)), n(100 + 92 * math.sin(a1))), color, 0.18))
    out.append(glow("M100 100 L%s %s" % (n(100 + 92 * math.cos(a1)), n(100 + 92 * math.sin(a1))), color, 1.4, 0.8))
    out.append('<path d="M100 82 L108 100 L100 96 L92 100 Z" fill="%s" stroke="none"/>' % PAL["red"])   # own mech marker (forward = up)
    if enemy_angle is not None:
        a = math.radians(enemy_angle - 90)
        rr = 18 + 70 * max(0.0, min(1.0, enemy_dist))
        x, y = 100 + rr * math.cos(a), 100 + rr * math.sin(a)
        out.append(glow(arc_d(x, y, 5, 0, 359.9), PAL["red"], 2.0, 1.0, fill=PAL["red"]))
        out.append(glow(arc_d(x, y, 10, 0, 359.9), PAL["red"], 1.0, 0.5))
    return "".join(out)


def compass_strip(heading=0.0, color=None):
    """Horizontal compass tape, 600 x 40: ticks every 5 degrees over a 120-degree window; long ticks every 15; a triangle for north; a fixed index at the centre."""
    color = color or PAL["cyan"]
    out = [glow("M0 8 L600 8", color, 0.8, 0.35)]
    for deg in range(-60, 61, 5):
        h = (heading + deg) % 360
        x = 300 + deg * 5.0
        major = round(h) % 15 == 0
        d = "M%s 8 L%s %s" % (n(x), n(x), n(24 if major else 16))
        out.append(glow(d, color, 1.2 if major else 0.9, 0.9 if major else 0.55))
        if abs(((h + 180) % 360) - 180) < 2.6:   # north marker: a small triangle
            out.append(glow("M%s 28 L%s 38 L%s 38 Z" % (n(x), n(x - 5), n(x + 5)), PAL["red"], 1.4))
    out.append(glow("M300 2 L295 -3 M300 2 L305 -3", PAL["white"], 1.4, 1.0))
    return "".join(out)


_SEG = {"0": "abcdef", "1": "bc", "2": "abdeg", "3": "abcdg", "4": "bcfg", "5": "acdfg", "6": "acdefg", "7": "abc", "8": "abcdefg", "9": "abcdfg"}


def _seg_lines(x, y, w, h):
    """Segment end points of a 7-segment digit box (x, y = top left)."""
    mx, my, b = y + h / 2.0, 0, 0
    return {"a": ((x, y), (x + w, y)), "b": ((x + w, y), (x + w, y + h / 2)), "c": ((x + w, y + h / 2), (x + w, y + h)), "d": ((x, y + h), (x + w, y + h)),
            "e": ((x, y + h / 2), (x, y + h)), "f": ((x, y), (x, y + h / 2)), "g": ((x, y + h / 2), (x + w, y + h / 2))}


def seg_char(ch, x, y, w, h, color, width=1.8, dim=True):
    """One character in 7-segment style: digits 0-9, '%' (two rings + slash) and ':' (two dots). Unlit segments are drawn faint when dim."""
    if ch == "%":
        return glow(arc_d(x + w * 0.22, y + h * 0.22, h * 0.14, 0, 359.9), color, width) + glow(arc_d(x + w * 0.78, y + h * 0.78, h * 0.14, 0, 359.9), color, width) + glow("M%s %s L%s %s" % (n(x + w), n(y), n(x), n(y + h)), color, width)
    if ch == ":":
        return glow(arc_d(x + w / 2, y + h * 0.3, 0.9, 0, 359.9), color, width * 1.6) + glow(arc_d(x + w / 2, y + h * 0.7, 0.9, 0, 359.9), color, width * 1.6)
    on = _SEG[ch]
    out = []
    for k, ((x0, y0), (x1, y1)) in _seg_lines(x, y, w, h).items():
        d = "M%s %s L%s %s" % (n(x0), n(y0), n(x1), n(y1))
        if k in on:
            out.append(glow(d, color, width))
        elif dim:
            out.append(glow(d, color, width * 0.5, 0.07))
    return "".join(out)


def seg_text(text, x, y, cw, ch, color, gap=None, width=1.8):
    gap = cw * 0.55 if gap is None else gap
    out = []
    for i, c in enumerate(text):
        out.append(seg_char(c, x + i * (cw + gap), y, cw if c != ":" else cw * 0.5, ch, color, width))
    return "".join(out)


def power_priority(current, color):
    """Four pictograms in a row (Arms, Legs, Guard, Weapon), the active one bright with a faint plate; viewBox 232 x 60."""
    out = []
    for i, name in enumerate(data.PRIORITIES):
        on = name == current
        c = color if on else PAL["lost"]
        op = 1.0 if on else 0.5
        if name == "Arms":
            g = glow("M10 50 L22 10 L26 10 M42 50 L30 10 L26 10 M12 50 L40 50", c, 2.0, op)
        elif name == "Legs":
            g = glow("M14 8 L14 52 M38 8 L38 52 M8 52 L20 52 M32 52 L44 52", c, 2.0, op)
        elif name == "Guard":
            g = glow("M26 6 L46 14 L44 32 Q40 46 26 54 Q12 46 8 32 L6 14 Z", c, 2.0, op)
        else:
            g = glow(arc_d(26, 30, 14, 0, 359.9), c, 2.0, op) + glow("M26 6 L26 18 M26 42 L26 54 M2 30 L14 30 M38 30 L50 30", c, 2.0, op)
        if on:
            g = fill_poly("M0 2 h52 v56 h-52 Z", c, 0.12) + g
        out.append('<g transform="translate(%s 0)">%s</g>' % (n(i * 60), g))
    return "".join(out)


def arm_bars(left, right, color_l, color_r):
    """Two short horizontal bars for the arm armour percentage, viewBox 520 x 22: left arm grows from the left, right arm from the right; the middle is empty."""
    out = []
    for side, v, col, x0, sgn in (("L", left, color_l, 0, 1), ("R", right, color_r, 520, -1)):
        out.append(glow("M%s 11 L%s 11" % (n(x0), n(x0 + sgn * 240)), PAL["lost"], 1.2, 0.35))
        for k in range(12):
            if (k + 0.5) / 12.0 <= v + 1e-6:
                xa = x0 + sgn * (k * 20 + 2)
                out.append(glow("M%s 11 L%s 11" % (n(xa), n(xa + sgn * 16)), col, 5.0, 1.0, cap="butt"))
    return "".join(out)


def stability_bar(value, color, label_dead=False):
    """Horizontal stability bar of the enemy, viewBox 260 x 30: a thin track with 20 ticks and the filled part drawn as short blocks."""
    out = [glow("M0 22 L260 22", PAL["lost"], 1.0, 0.35)]
    for k in range(20):
        x = k * 13
        if (k + 0.5) / 20.0 <= value + 1e-6 and not label_dead:
            out.append(glow("M%s 16 L%s 16" % (n(x + 1), n(x + 11)), color, 6.0, 1.0, cap="butt"))
        out.append(glow("M%s 24 L%s 28" % (n(x), n(x)), PAL["neutral"], 0.8, 0.4))
    out.append(glow("M0 4 L10 4 L10 10 M250 4 L260 4 L260 10", color, 1.4, 0.8))   # corner ticks
    return "".join(out)
