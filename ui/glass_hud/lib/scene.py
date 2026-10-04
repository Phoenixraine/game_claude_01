"""Reference HUD compositor: layout rects for any aspect ratio, the vector HUD for a state dict, and the full frame (backdrop + glass effects + HUD). Pure functions."""
import io
import os

import numpy as np
from PIL import Image

from . import background, data, masks, shapes
from .svgkit import n, svg_doc

PAL = data.PALETTE["colors"]
REF_W, REF_H = 1920.0, 1080.0
HERE = os.path.dirname(os.path.abspath(__file__))


def _scale(W, H):
    """Uniform UI scale: the 16:9 design is kept by height on wide screens and by width on taller ones."""
    return H / REF_H if W / H >= REF_W / REF_H else W / REF_W


def element_rect_px(el, W, H):
    """Pixel rect (x, y, w, h) of a layout element for a W x H screen. Corner-anchored elements keep their offset from the corner (scaled uniformly), centred ones stay centred."""
    s = _scale(W, H)
    x, y, w, h = el["rect"]
    px_w, px_h = w * REF_W * s, h * REF_H * s
    anchor = el["anchor"]
    ox_left, ox_right = x * REF_W * s, (1.0 - (x + w)) * REF_W * s
    oy_top, oy_bottom = y * REF_H * s, (1.0 - (y + h)) * REF_H * s
    if anchor.endswith("left"):
        px = ox_left
    elif anchor.endswith("right"):
        px = W - ox_right - px_w
    else:
        px = W / 2.0 + (x + w / 2.0 - 0.5) * REF_W * s - px_w / 2.0
    py = oy_top if anchor.startswith("top") else H - oy_bottom - px_h
    return px, py, px_w, px_h


def all_rects(W, H, persistent_only=False):
    out = {}
    for el in data.ELEMENTS:
        if persistent_only and not el.get("persistent"):
            continue
        out[el["id"]] = element_rect_px(el, W, H)
    return out


def free_center_px(W, H):
    fx, fy, fw, fh = data.FREE_CENTER
    return fx * W, fy * H, fw * W, fh * H


def _place(inner, vb, rect):
    """Place inner markup with local size vb = (w, h) into rect, uniform scale, centred."""
    x, y, w, h = rect
    s = min(w / vb[0], h / vb[1])
    return '<g transform="translate(%s %s) scale(%s)">%s</g>' % (n(x + (w - vb[0] * s) / 2), n(y + (h - vb[1] * s) / 2), n(s), inner)


def gauge_color(kind, v):
    g = data.STATES["gauges"][kind]
    if kind == "heat":
        if v >= g["hot"]:
            return PAL[g["hot_color"]]
        if v >= g["warm"]:
            return PAL[g["warm_color"]]
        return PAL[g["color"]]
    if kind == "ultimate":
        return PAL[g["color"]]
    if "critical" in g and v <= g["critical"]:
        return PAL[g["critical_color"]]
    if "low" in g and v <= g["low"]:
        return PAL[g["low_color"]]
    return PAL[g["color"]]


def _pct_color(v):
    return gauge_color("armor", v)


def threat_rect(direction, W, H):
    """Pixel rect of a threat arrow on its screen edge (120 design px, scaled). Chosen to stay clear of every persistent element at 16:9, 16:10 and 21:9."""
    s = _scale(W, H)
    sz = 120.0 * s
    cx = W / 2.0
    return {"up": (cx - sz / 2, 0.075 * H, sz, sz), "down": (cx - sz / 2, H - 0.075 * H - sz, sz, sz),
            "left": (0.02 * W if W / H < 1.9 else 0.02 * H * 1.78, 0.52 * H, sz, sz), "right": (W - (0.02 * W if W / H < 1.9 else 0.02 * H * 1.78) - sz, 0.52 * H, sz, sz)}[direction]


def hud_markup(state, W, H):
    """Vector HUD (everything except raster glass effects) as SVG body markup in screen pixels."""
    R = all_rects(W, H)
    blink = state.get("blink", True)
    dim = state.get("dim", 1.0)
    out = []
    pl, en = state["player"], state["enemy"]
    out.append(_place(shapes.silhouette("player", pl["zones"], blink) + shapes.layer_arcs("player", pl["zones"], pl.get("layers"), blink), (400, 540), R["body_player"]))
    out.append(_place(shapes.silhouette("enemy", en["zones"], blink) + shapes.layer_arcs("enemy", en["zones"], en.get("layers"), blink), (400, 540), R["body_enemy"]))
    # enemy status row + stability bar
    icons = state.get("enemy_status", {}).get("icons", [])
    row = ""
    for i, kind in enumerate(data.STATUSES):
        if {"Blind": "blind", "StrikeLock": "strikelock", "Burn": "burn"}[kind] in icons:
            col = PAL["red"] if kind == "Burn" else PAL["amber"]
            row += '<g transform="translate(%s 0) scale(0.84)">%s</g>' % (n(i * 62), shapes.icon_status({"Blind": "blind", "StrikeLock": "strikelock", "Burn": "burn"}[kind], col))
    out.append(_place(row, (260, 54), R["enemy_status"]))
    es = state.get("enemy_status", {}).get("stability", 1.0)
    out.append(_place(shapes.stability_bar(es, gauge_color("stability", es)), (260, 30), R["enemy_stability"]))
    out.append(_place(shapes.compass_strip(state.get("heading", 0.0)), (600, 40), R["compass"]))
    # weapons
    wrow = ""
    for i, (key, wk) in enumerate((("rail", "RailSpear"), ("rockets", "SuppressionRockets"), ("plasma", "PlasmaCannon"))):
        w = state["weapons"].get(key, {"ring": 1.0})
        col = PAL["red"] if w.get("dead") or w.get("empty") else (PAL["white"] if w.get("ring", 1.0) >= 1.0 else PAL["cyan"])
        wrow += '<g transform="translate(%s 0)">%s</g>' % (n(i * 96), shapes.icon_weapon(key, col, w.get("ring", 1.0), w.get("dead", False) or w.get("empty", False)))
    out.append(_place(wrow, (288, 64), R["weapons"]))
    for kind, el in (("armor", "gauge_armor"), ("stability", "gauge_stability"), ("heat", "gauge_heat"), ("energy", "gauge_energy")):
        v = state[kind]
        dead = state.get("dead_gauges", {}).get(kind, False)
        out.append(_place(shapes.ring_gauge(kind, v, gauge_color(kind, v), blink, dead), (256, 256), R[el]))
    la, ra = state["arm_armor"]
    out.append(_place(shapes.arm_bars(la, ra, _pct_color(la), _pct_color(ra)), (520, 22), R["arm_armor"]))
    # digits
    m, s = divmod(int(state.get("clock_s", 0)), 60)
    out.append(_place(shapes.seg_text("%d:%02d" % (m, s), 4, 4, 22, 32, PAL["cyan"]), (140, 40), R["clock"]))
    out.append(_place(shapes.seg_text("%04d" % int(state.get("distance_m", 0)), 4, 4, 28, 32, PAL["cyan"]), (170, 40), R["distance"]))
    out.append(_place(shapes.power_priority(state.get("priority", "Arms"), PAL["amber"]), (232, 60), R["priority"]))
    rd = state.get("radar", {})
    out.append(_place(shapes.radar(PAL["cyan"], rd.get("enemy_angle"), rd.get("dist", 0.5), rd.get("sweep", 40.0), rd.get("dead", False)), (200, 200), R["radar"]))
    ul = state.get("ultimate", {"value": 0.0, "ready": False})
    out.append(_place(shapes.ultimate_gauge(ul["value"], ul["ready"], blink), (256, 256), R["ultimate"]))
    # world-anchored: lock-on
    lk = state.get("lock")
    if lk:
        x, y, w, h = lk["rect"]
        px, py, pw, ph = x * W, y * H, w * W, h * H
        qc = PAL["cyan"] if lk["quality"] >= 0.75 else PAL["amber"] if lk["quality"] >= 0.4 else PAL["red"]
        sx, sy = pw / 200.0, ph / 200.0
        out.append('<g transform="translate(%s %s) scale(%s %s)">%s</g>' % (n(px), n(py), n(sx), n(sy), shapes.lockon_corners(qc, lk["quality"])))
        hx = lk.get("hex")
        if hx:
            hx_x, hx_y, hx_s = hx
            out.append('<g transform="translate(%s %s) scale(%s)">%s</g>' % (n(hx_x * W - 100 * hx_s), n(hx_y * H - 100 * hx_s), n(hx_s), shapes.lockon_hex(PAL["red"] if lk.get("hex_hot") else PAL["cyan"])))
    sk = state.get("strike")
    if sk:
        pts = [(x * W, y * H) for x, y in sk["points"]]
        out.append(shapes.strike_arc(pts, PAL["red"] if sk.get("committed") else PAL["white"], sk.get("committed", False)))
    out.append('<g transform="translate(%s %s)">%s</g>' % (n(W / 2 - 24), n(H / 2 - 24), shapes.crosshair(PAL["white"])))
    # threat arrows on the edges
    for d in state.get("threats", []):
        x, y, w, h = threat_rect(d, W, H)
        out.append('<g transform="translate(%s %s) scale(%s)">%s</g>' % (n(x), n(y), n(w / 120.0), shapes.threat_arrow(d, PAL["red"], 1.0)))
    for z, side in state.get("warning_icons", []):
        pass
    for wi in state.get("warnings", []):
        x, y = wi["pos"]
        out.append('<g transform="translate(%s %s) scale(%s)">%s</g>' % (n(x * W), n(y * H), n(0.9 * s), shapes.icon_warning(PAL[wi.get("color", "red")]) if blink else ""))
    return '<g opacity="%s">%s</g>' % (n(dim), "".join(out))


def hud_svg(state, W=1920, H=1080):
    return svg_doc(W, H, hud_markup(state, W, H))


def svg_to_rgba(svg, W, H):
    import cairosvg
    png = cairosvg.svg2png(bytestring=svg.encode("utf-8"), output_width=W, output_height=H)
    return np.asarray(Image.open(io.BytesIO(png)).convert("RGBA"), dtype=np.float32) / 255.0


def load_mask(rel):
    return np.asarray(Image.open(os.path.join(os.path.dirname(HERE), rel)))


def _over(dst, rgb, a):
    return dst * (1 - a[..., None]) + np.asarray(rgb, np.float32) * a[..., None]


def _resize(arr, W, H):
    return np.asarray(Image.fromarray(arr).resize((W, H), Image.BILINEAR))


def compose_frame(state, W=1920, H=1080, bg=None):
    """Full reference frame as RGB uint8: backdrop, drops, soot, vector HUD, cracks, glitch, alarm frame."""
    img = bg if bg is not None else background.city(W, H, enemy=state.get("enemy_pos_px"))
    img = img.copy()
    gl = state.get("glass", {})
    for k in gl.get("soot", []):
        m = _resize(load_mask("png/soot_mask_%02d.png" % (k % 4)), W, H).astype(np.float32) / 255.0
        img *= (1.0 - 0.75 * m)[..., None]
    if gl.get("drops"):
        rs = np.random.RandomState(5)
        atlas = np.asarray(Image.open(os.path.join(os.path.dirname(HERE), "png/rain_drops_atlas.png")).convert("RGBA"))
        cs = atlas.shape[0] // 4
        for _ in range(gl["drops"]):
            j, i = rs.randint(0, 4), rs.randint(0, 4)
            tile = atlas[j * cs:(j + 1) * cs, i * cs:(i + 1) * cs].astype(np.float32) / 255.0
            sc = rs.uniform(0.18, 0.5)
            tw = max(8, int(cs * sc))
            t = np.asarray(Image.fromarray((tile * 255).astype(np.uint8)).resize((tw, tw), Image.BILINEAR)).astype(np.float32) / 255.0
            x0, y0 = rs.randint(0, W - tw), rs.randint(0, H - tw)
            a = t[..., 3] * 0.55
            reg = img[y0:y0 + tw, x0:x0 + tw]
            hl = t[..., 2:3] * 0.55
            img[y0:y0 + tw, x0:x0 + tw] = reg * (1 - a[..., None] * 0.25) + a[..., None] * 0.08 + hl * a[..., None]
    hud = svg_to_rgba(hud_svg(state, W, H), W, H)
    img = _over(img, hud[..., :3], hud[..., 3])
    for k in gl.get("cracks", []):
        m = _resize(load_mask("png/crack_mask_%02d.png" % (k % 8)), W, H).astype(np.float32) / 255.0
        img = _over(img, (0.92, 0.97, 1.0), 0.42 * m)
    gs = gl.get("glitch", 0.0)
    if gs > 0:
        rs = np.random.RandomState(int(gs * 100))
        for q in range(int(1 + gs * 5)):
            strip = np.asarray(Image.open(os.path.join(os.path.dirname(HERE), "png/glitch_strip_%02d.png" % rs.randint(0, 8))).convert("RGBA"))
            strip = np.asarray(Image.fromarray(strip).resize((W, int(H * 0.05)), Image.BILINEAR)).astype(np.float32) / 255.0
            y0 = rs.randint(0, H - strip.shape[0])
            img[y0:y0 + strip.shape[0]] += strip[..., :3] * strip[..., 3:4] * 0.45 * gs
    al = gl.get("alarm", 0.0)
    if al > 0:
        fr = _resize(masks.alarm_frame(), W, H).astype(np.float32) / 255.0
        img = _over(img, fr[..., :3], fr[..., 3] * al)
    return (np.clip(img, 0, 1) * 255 + 0.5).astype(np.uint8)
