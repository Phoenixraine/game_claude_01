def _cd(m, idx, default, x, y):
    e = expr(m, unreal.MaterialExpressionPerInstanceCustomData, x, y)
    e.set_editor_property("data_index", idx)
    e.set_editor_property("default_value", default)
    return e


HASH_FN = """
#define h11(x) frac(sin((x) * 127.1) * 43758.5453)
#define h21(p) frac(sin(dot((p), float2(127.1, 311.7))) * 43758.5453)
"""


def build_neon_sign():
    """Building-sized neon signs. Per-instance custom data: 0-2 colour, 3-5 colour2, 6 = style + 10*anim, 7 = seed, 8 = aspect (w/h).
    Styles: 0 vertical banner of pseudo-kanji, 1 animated LED billboard, 2 horizontal strip of glyphs, 3 plain glowing tube."""
    m = make_material("M_NeonSign")
    m.set_editor_property("used_with_instanced_static_meshes", True)
    m.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_DEFAULT_LIT)
    uv = expr(m, unreal.MaterialExpressionTextureCoordinate, -1500, 0)
    tm = expr(m, unreal.MaterialExpressionTime, -1500, 120)
    nrm = expr(m, unreal.MaterialExpressionVertexNormalWS, -1500, 240)
    xf = expr(m, unreal.MaterialExpressionTransform, -1350, 240)
    xf.set_editor_property("transform_source_type", unreal.MaterialVectorCoordTransformSource.TRANSFORMSOURCE_WORLD)
    xf.set_editor_property("transform_type", unreal.MaterialVectorCoordTransform.TRANSFORM_LOCAL)
    MEL.connect_material_expressions(nrm, "", xf, "")
    cds = [_cd(m, i, d, -1500, 360 + 110 * i) for i, d in enumerate([1.0, 0.1, 0.5, 0.1, 0.9, 1.0, 0.0, 0.0, 0.3])]
    gain = scalar(m, "Gain", 1.0, -1500, 1400)
    names = ["UV", "T", "NL", "R1", "G1", "B1", "R2", "G2", "B2", "SA", "Seed", "Asp", "Gain"]
    srcs = [(uv, ""), (tm, ""), (xf, ""), (cds[0], ""), (cds[1], ""), (cds[2], ""), (cds[3], ""), (cds[4], ""), (cds[5], ""), (cds[6], ""), (cds[7], ""), (cds[8], ""), (gain, "")]
    common = HASH_FN + """
float3 C1 = float3(R1, G1, B1), C2 = float3(R2, G2, B2);
float style = fmod(SA, 10.0), anim = floor(SA / 10.0);
float face = step(0.55, NL.x);
float2 uv = float2(UV.x, 1.0 - UV.y);
float asp = max(Asp, 0.02);
float flick = 1.0;
if (anim > 0.5 && anim < 1.5) { float ft = floor(T * 7.0 + Seed); flick = (h11(ft + Seed * 3.1) > 0.82) ? 0.12 : 1.0; flick *= 0.9 + 0.1 * sin(T * 40.0); }
float chase = 1.0;
if (anim > 1.5) chase = 0.55 + 0.45 * sin(T * 3.0 - uv.y * 9.0 + Seed);
float3 emis = float3(0, 0, 0);
// ---- which glyph cell are we in?  (q = 0..1 inside the cell, gs = glyph seed, on = inside the drawn area)
float2 q = float2(0, 0); float gs = 0; float on = 0; float rowid = 0;
if (style < 0.5)
{
    float n = max(1.0, floor(1.0 / max(asp, 0.05)));
    float py = uv.y * n;
    rowid = floor(py);
    q = float2((uv.x - 0.1) / 0.8, (frac(py) - 0.08) / 0.84);
    gs = floor(h21(float2(rowid, Seed)) * 60.0) + Seed;
    on = step(0.0, q.x) * step(q.x, 1.0) * step(0.0, q.y) * step(q.y, 1.0);
}
else if (style < 1.5)
{
    q = float2(frac(uv.x * asp * 5.0), frac(uv.y * 5.0));
    float2 cid = float2(floor(uv.x * asp * 5.0), floor(uv.y * 5.0));
    rowid = cid.x + cid.y * 7.0;
    gs = floor(h21(cid + Seed) * 80.0);
    on = step(0.22, uv.y) * step(uv.y, 0.78) * step(0.1, uv.x) * step(uv.x, 0.9) * step(0.55, h21(cid + Seed * 2.0));
}
else if (style < 2.5)
{
    float n = max(1.0, floor(asp));
    float px = uv.x * n;
    rowid = floor(px);
    q = float2((frac(px) - 0.1) / 0.8, (uv.y - 0.12) / 0.76);
    gs = floor(h21(float2(rowid, Seed)) * 60.0) + Seed;
    on = step(0.0, q.x) * step(q.x, 1.0) * step(0.0, q.y) * step(q.y, 1.0);
}
// ---- the glyph: a few random strokes snapped to a 3x3 grid (kana / kanji look-alike)
float gd = 1e3;
for (int i = 0; i < 5; i++)
{
    float k = gs * 7.13 + i * 3.7;
    float2 a = floor(float2(h11(k), h11(k + 1.3)) * 3.0) / 2.0 * 0.62 + 0.19;
    float2 b = floor(float2(h11(k + 2.9), h11(k + 4.1)) * 3.0) / 2.0 * 0.62 + 0.19;
    if (h11(k + 7.7) > 0.5) b.y = a.y; else b.x = a.x;
    if (i == 4 && h11(gs) > 0.5) { a = float2(0.5, 0.15); b = float2(0.5, 0.85); }
    float2 pa = q - a, ba = b - a;
    float hh = saturate(dot(pa, ba) / max(dot(ba, ba), 1e-4));
    gd = min(gd, length(pa - ba * hh));
}
if (style < 2.5)
{
    float bd = min(min(uv.x * asp, (1.0 - uv.x) * asp), min(uv.y, 1.0 - uv.y));
    float bw = (style > 0.5 && style < 1.5) ? 0.012 : 0.02;
    float tube = smoothstep(bw * 1.6, bw * 0.8, abs(bd - bw * 2.0));
    emis += C2 * tube * 9.0 * flick;
}
if (style < 0.5)
{
    float stroke = smoothstep(0.075, 0.04, gd) * on;
    float halo = exp(-gd * 18.0) * on * 0.35;
    float3 col = (frac(rowid * 0.5) > 0.4) ? C1 : lerp(C1, C2, 0.65);
    emis += col * (stroke * 11.0 + halo * 2.4) * flick * chase;
}
else if (style < 1.5)
{
    float t = T * (0.5 + 0.8 * h11(Seed));
    float2 p = float2(uv.x * asp * 2.0, uv.y * 2.0);
    float ring = abs(frac(length(p - float2(asp * (1.0 + 0.7 * sin(t)), 1.0)) * 1.6 - t * 0.6) - 0.5);
    float bars = step(0.5, frac((uv.x * 6.0 * asp + uv.y * 2.0) - t * 0.7));
    float cyc = 0.5 + 0.5 * sin(t * 1.3 + Seed);
    float3 bg = lerp(C1, C2, cyc) * (0.25 + 0.55 * bars * smoothstep(0.1, 0.4, ring));
    float txt = smoothstep(0.09, 0.05, gd) * on;
    float scan = 0.85 + 0.15 * sin(uv.y * 400.0);
    emis += (bg * 2.6 + lerp(C2, C1, cyc) * txt * 7.0) * scan * flick;
}
else if (style < 2.5)
{
    float stroke = smoothstep(0.08, 0.04, gd) * on;
    float halo = exp(-gd * 14.0) * on * 0.35;
    float3 col = (frac(rowid * 0.5) > 0.4) ? C1 : C2;
    emis += col * (stroke * 10.0 + halo * 2.0) * flick * chase;
}
else
{
    emis += C1 * 7.0 * flick * chase * (0.8 + 0.2 * sin(uv.y * 30.0 + T * 2.0));
}
emis *= face * Gain;
return emis;
"""
    t = unreal.CustomMaterialOutputType
    emi = custom(m, common, t.CMOT_FLOAT3, names, -900, 0, "sign_emissive")
    wire_custom(emi, srcs)
    MEL.connect_material_property(emi, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    base = scalar(m, "BaseDark", 0.02, -900, 600)
    bc = expr(m, unreal.MaterialExpressionConstant3Vector, -900, 650)
    bc.set_editor_property("constant", unreal.LinearColor(0.02, 0.02, 0.025, 1))
    MEL.connect_material_property(bc, "", unreal.MaterialProperty.MP_BASE_COLOR)
    rough = scalar(m, "Roughness", 0.35, -900, 800)
    MEL.connect_material_property(rough, "", unreal.MaterialProperty.MP_ROUGHNESS)
    metal = scalar(m, "Metallic", 0.6, -900, 900)
    MEL.connect_material_property(metal, "", unreal.MaterialProperty.MP_METALLIC)
    MEL.recompile_material(m)
    unreal.EditorAssetLibrary.save_loaded_asset(m)
    return m


def build_glass_tower():
    """Curtain-wall glass tower: mullion grid, spandrel bands, lit offices, fake city-glow reflections; Lumen reflects the neon in it.
    Per-instance custom data: 0-2 glass tint, 3 seed."""
    m = make_material("M_GlassTower")
    m.set_editor_property("used_with_instanced_static_meshes", True)
    wp = expr(m, unreal.MaterialExpressionWorldPosition, -1500, 0)
    nrm = expr(m, unreal.MaterialExpressionVertexNormalWS, -1500, 120)
    cam = expr(m, unreal.MaterialExpressionCameraVectorWS, -1500, 240)
    tm = expr(m, unreal.MaterialExpressionTime, -1500, 360)
    r = _cd(m, 0, 0.08, -1500, 480)
    g = _cd(m, 1, 0.2, -1500, 600)
    b = _cd(m, 2, 0.3, -1500, 720)
    sd = _cd(m, 3, 0.0, -1500, 840)
    lit = scalar(m, "LitAmount", 1.0, -1500, 960)
    bright = scalar(m, "Bright", 1.0, -1500, 1080)
    names = ["WP", "Nrm", "Cam", "T", "R", "G", "B", "Seed", "Lit", "Bright"]
    srcs = [(wp, ""), (nrm, ""), (cam, ""), (tm, ""), (r, ""), (g, ""), (b, ""), (sd, ""), (lit, ""), (bright, "")]
    common = HASH_FN + """
float3 n = normalize(Nrm);
float3 tint = float3(R, G, B);
float roof = step(0.7, abs(n.z));
float hRaw = lerp(WP.x, WP.y, step(0.5, abs(n.x)));
float cw = 150.0, fh = 400.0;
float2 g2 = float2(hRaw / cw, WP.z / fh);
float2 f = frac(g2);
float2 id = floor(g2);
float hs = h21(id + Seed * 13.7);
float hf = h21(float2(id.y, Seed * 5.1));                 // floor-wide factor (whole storeys lit/dark)
float mull = smoothstep(0.0, 0.05, f.x) * smoothstep(0.0, 0.05, 1.0 - f.x);
float slab = smoothstep(0.17, 0.2, f.y) * smoothstep(1.0, 0.985, f.y);
float glassM = mull * slab * (1.0 - roof);
float fres = pow(1.0 - saturate(abs(dot(n, normalize(Cam)))), 2.5);
"""
    t = unreal.CustomMaterialOutputType
    base = custom(m, common + """
float3 frame = float3(0.025, 0.027, 0.032) * (0.8 + 0.4 * hs);
float3 gl = tint * 0.12 * (0.8 + 0.4 * hs);
float3 roofc = float3(0.045, 0.047, 0.05);
return lerp(lerp(frame, gl, glassM), roofc, roof);
""", t.CMOT_FLOAT3, names, -900, 0, "gt_base")
    wire_custom(base, srcs)
    MEL.connect_material_property(base, "", unreal.MaterialProperty.MP_BASE_COLOR)
    rough = custom(m, common + "return lerp(lerp(0.32, 0.045 + 0.06 * hs, glassM), 0.8, roof);", t.CMOT_FLOAT1, names, -900, 300, "gt_rough")
    wire_custom(rough, srcs)
    MEL.connect_material_property(rough, "", unreal.MaterialProperty.MP_ROUGHNESS)
    met = custom(m, common + "return lerp(0.85, 0.0, glassM) * (1.0 - roof);", t.CMOT_FLOAT1, names, -900, 600, "gt_metal")
    wire_custom(met, srcs)
    MEL.connect_material_property(met, "", unreal.MaterialProperty.MP_METALLIC)
    spec = custom(m, common + "return lerp(0.5, 1.0, glassM);", t.CMOT_FLOAT1, names, -900, 800, "gt_spec")
    wire_custom(spec, srcs)
    MEL.connect_material_property(spec, "", unreal.MaterialProperty.MP_SPECULAR)
    emi = custom(m, common + """
float on = step(0.52, hs) * step(0.25, hf) * glassM * Lit;
float cc = h21(id + Seed);
float3 warm = (cc < 0.55) ? float3(1.0, 0.72, 0.42) : ((cc < 0.8) ? float3(0.62, 0.82, 1.0) : float3(1.0, 0.35, 0.75));
float3 e = warm * on * (1.4 + 1.6 * hs);
// faked sky/city reflection on the glass: bright grazing sheen + glow that climbs from the street
float hgt = saturate(WP.z / 25000.0);
e += tint * glassM * (0.45 + 1.5 * fres) * (0.35 + 0.65 * hgt) * Bright * 1.4;
float3 street = lerp(float3(1.0, 0.25, 0.6), float3(0.1, 0.8, 1.0), h11(Seed * 3.3 + floor(WP.z / 1200.0) * 0.07));
e += street * glassM * (1.0 - saturate(WP.z / 5000.0)) * 0.9 * (1.0 - roof);
// slow lit-floor pulse for life
e *= 0.92 + 0.08 * sin(T * 0.7 + hs * 20.0);
return e;
""", t.CMOT_FLOAT3, names, -900, 1000, "gt_emissive")
    wire_custom(emi, srcs)
    MEL.connect_material_property(emi, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    MEL.recompile_material(m)
    unreal.EditorAssetLibrary.save_loaded_asset(m)
    return m


def build_trim():
    """Emissive trim: LED strips, beads, beacons. Custom data: 0-2 colour, 3 intensity, 4 blink rate (0 = steady)."""
    m = make_material("M_Trim")
    m.set_editor_property("used_with_instanced_static_meshes", True)
    tm = expr(m, unreal.MaterialExpressionTime, -900, 0)
    cds = [_cd(m, i, d, -900, 120 + 110 * i) for i, d in enumerate([1.0, 0.2, 0.5, 6.0, 0.0])]
    c = custom(m, """
float3 col = float3(R, G, B) * I;
if (Bl > 0.01) { col *= step(0.5, frac(T * Bl)); }
return col;
""", unreal.CustomMaterialOutputType.CMOT_FLOAT3, ["R", "G", "B", "I", "Bl", "T"], -500, 100, "trim_emissive")
    wire_custom(c, [(cds[0], ""), (cds[1], ""), (cds[2], ""), (cds[3], ""), (cds[4], ""), (tm, "")])
    MEL.connect_material_property(c, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    bc = expr(m, unreal.MaterialExpressionConstant3Vector, -500, 400)
    bc.set_editor_property("constant", unreal.LinearColor(0.02, 0.02, 0.02, 1))
    MEL.connect_material_property(bc, "", unreal.MaterialProperty.MP_BASE_COLOR)
    MEL.recompile_material(m)
    unreal.EditorAssetLibrary.save_loaded_asset(m)
    return m


