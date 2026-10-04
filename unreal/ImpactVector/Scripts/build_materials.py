"""Builds the project's procedural master materials with the editor Python API.
Run:  UnrealEditor-Cmd ImpactVector.uproject -ExecutePythonScript=Scripts/build_materials.py -unattended -nosplash -nullrhi
Textures from TASK-008 plug in later through the texture parameters; until then everything is procedural.
"""
import unreal

MEL = unreal.MaterialEditingLibrary
TOOLS = unreal.AssetToolsHelpers.get_asset_tools()
PKG = "/Game/Materials"


def make_material(name):
    path = f"{PKG}/{name}"
    if unreal.EditorAssetLibrary.does_asset_exist(path):
        unreal.EditorAssetLibrary.delete_asset(path)
    mat = TOOLS.create_asset(name, PKG, unreal.Material, unreal.MaterialFactoryNew())
    return mat


def expr(mat, cls, x, y):
    return MEL.create_material_expression(mat, cls, x, y)


def scalar(mat, name, value, x, y):
    e = expr(mat, unreal.MaterialExpressionScalarParameter, x, y)
    e.set_editor_property("parameter_name", name)
    e.set_editor_property("default_value", value)
    return e


def vector(mat, name, color, x, y):
    e = expr(mat, unreal.MaterialExpressionVectorParameter, x, y)
    e.set_editor_property("parameter_name", name)
    e.set_editor_property("default_value", unreal.LinearColor(*color))
    return e


def custom(mat, code, out_type, input_names, x, y, desc="custom"):
    c = expr(mat, unreal.MaterialExpressionCustom, x, y)
    c.set_editor_property("code", code)
    c.set_editor_property("description", desc)
    c.set_editor_property("output_type", out_type)
    ins = []
    for n in input_names:
        ci = unreal.CustomInput()
        ci.set_editor_property("input_name", n)
        ins.append(ci)
    c.set_editor_property("inputs", ins)
    return c


def wire_custom(c, sources):
    """sources: list of (expression, output_name) in the same order as the custom inputs."""
    for i, (src, out) in enumerate(sources):
        MEL.connect_material_expressions(src, out, c, c.get_editor_property("inputs")[i].get_editor_property("input_name"))


# ---------------------------------------------------------------------------------------------------------------
def build_facade():
    """Building facade: window grid in world space, lit windows at night, per-instance variation."""
    m = make_material("M_BuildingFacade")
    m.set_editor_property("used_with_instanced_static_meshes", True)
    wp = expr(m, unreal.MaterialExpressionWorldPosition, -1200, 0)
    nrm = expr(m, unreal.MaterialExpressionVertexNormalWS, -1200, 150)
    rnd = expr(m, unreal.MaterialExpressionPerInstanceRandom, -1200, 300)
    tint = vector(m, "Tint", (0.22, 0.23, 0.25, 1), -1200, 450)
    glass = vector(m, "GlassColor", (0.025, 0.04, 0.06, 1), -1200, 600)
    spacing = scalar(m, "WindowSpacing", 400.0, -1200, 750)
    lit = scalar(m, "LitAmount", 1.0, -1200, 850)
    glassiness = scalar(m, "Glassiness", 0.55, -1200, 950)

    common = """
float3 n = normalize(Nrm);
float hRaw = lerp(WP.x, WP.y, step(0.5, abs(n.x)));
float h = hRaw / Spacing;
float v = WP.z / Spacing;
float2 f = frac(float2(h, v));
float roof = step(0.7, abs(n.z));
float fw = max(fwidth(h), fwidth(v));
float aaK = saturate(fw * 1.6);                      // far away the window grid melts into its average (no moire)
float e0 = max(fw, 0.02);
float win = smoothstep(0.14 - e0, 0.14 + e0, f.x) * smoothstep(0.86 + e0, 0.86 - e0, f.x) * smoothstep(0.2 - e0, 0.2 + e0, f.y) * smoothstep(0.78 + e0, 0.78 - e0, f.y) * (1.0 - roof);
win = lerp(win, 0.42 * (1.0 - roof), aaK);
float2 id = floor(float2(h, v));
float hash = frac(sin(dot(id + Rnd * 37.0, float2(12.9898, 78.233))) * 43758.5453);
"""
    base = custom(m, common + """
float3 wall = Tint * (0.85 + 0.3 * frac(Rnd * 7.0));
float3 gl = Glass * (0.7 + 0.6 * hash);
float band = step(0.93, f.y) * (1.0 - roof);          // slab edge line
wall *= (1.0 - 0.35 * band);
return lerp(wall, gl, win);
""", unreal.CustomMaterialOutputType.CMOT_FLOAT3, ["WP", "Nrm", "Rnd", "Tint", "Glass", "Spacing"], -700, 0, "facade_base")
    wire_custom(base, [(wp, ""), (nrm, ""), (rnd, ""), (tint, ""), (glass, ""), (spacing, "")])
    MEL.connect_material_property(base, "", unreal.MaterialProperty.MP_BASE_COLOR)

    rough = custom(m, common + """
return lerp(0.82, 0.08 + 0.2 * hash, win * Gls);
""", unreal.CustomMaterialOutputType.CMOT_FLOAT1, ["WP", "Nrm", "Rnd", "Spacing", "Gls"], -700, 350, "facade_rough")
    wire_custom(rough, [(wp, ""), (nrm, ""), (rnd, ""), (spacing, ""), (glassiness, "")])
    MEL.connect_material_property(rough, "", unreal.MaterialProperty.MP_ROUGHNESS)

    emis = custom(m, common + """
float on = lerp(step(0.6, hash) * win, 0.4 * win, aaK) * Lit;
float3 warm = lerp(float3(1.0, 0.82, 0.55), float3(0.7, 0.85, 1.0), frac(hash * 13.0));
// neon signs: whole bands of a facade glow in saturated colours (Tokyo at night)
float2 bid = floor(float2(h / 5.0, v / 7.0));
float bh = frac(sin(dot(bid + Rnd * 11.0, float2(41.3, 97.1))) * 43758.5453);
float band = step(0.93, bh) * win * (1.0 - roof);
float cr = frac(bh * 37.0);
float3 neon = cr < 0.25 ? float3(1.0, 0.1, 0.55) : (cr < 0.5 ? float3(0.1, 0.9, 1.0) : (cr < 0.75 ? float3(1.0, 0.45, 0.05) : float3(0.4, 1.0, 0.3)));
float flick = 0.85 + 0.15 * sin(frac(bh * 91.0) * 40.0);
return warm * on * 3.2 + neon * band * 9.0 * flick;
""", unreal.CustomMaterialOutputType.CMOT_FLOAT3, ["WP", "Nrm", "Rnd", "Spacing", "Lit"], -700, 650, "facade_emissive")
    wire_custom(emis, [(wp, ""), (nrm, ""), (rnd, ""), (spacing, ""), (lit, "")])
    MEL.connect_material_property(emis, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)

    metal = scalar(m, "Metallic", 0.05, -700, 900)
    MEL.connect_material_property(metal, "", unreal.MaterialProperty.MP_METALLIC)
    MEL.recompile_material(m)
    unreal.EditorAssetLibrary.save_loaded_asset(m)
    return m


def build_ground():
    """Wet asphalt/concrete: puddle mask from world-space noise, low roughness in puddles, subtle lane lines."""
    m = make_material("M_WetGround")
    wp = expr(m, unreal.MaterialExpressionWorldPosition, -1200, 0)
    base_col = vector(m, "BaseTint", (0.045, 0.047, 0.052, 1), -1200, 200)
    wet = scalar(m, "Wetness", 0.75, -1200, 350)
    scale = scalar(m, "NoiseScale", 900.0, -1200, 450)
    vc = expr(m, unreal.MaterialExpressionVertexColor, -1200, 600)
    use_vc = scalar(m, "UseVertexColor", 0.0, -1200, 750)

    common = """
float2 p = WP.xy / Sc;
float2 i = floor(p), fr = frac(p);
float2 u = fr * fr * (3.0 - 2.0 * fr);
float a = frac(sin(dot(i, float2(127.1, 311.7))) * 43758.5453);
float b = frac(sin(dot(i + float2(1,0), float2(127.1, 311.7))) * 43758.5453);
float c = frac(sin(dot(i + float2(0,1), float2(127.1, 311.7))) * 43758.5453);
float d = frac(sin(dot(i + float2(1,1), float2(127.1, 311.7))) * 43758.5453);
float n1 = lerp(lerp(a, b, u.x), lerp(c, d, u.x), u.y);
float2 p2 = WP.xy / (Sc * 0.23);
float2 i2 = floor(p2), f2 = frac(p2);
float2 u2 = f2 * f2 * (3.0 - 2.0 * f2);
float a2 = frac(sin(dot(i2, float2(127.1, 311.7))) * 43758.5453);
float b2 = frac(sin(dot(i2 + float2(1,0), float2(127.1, 311.7))) * 43758.5453);
float c2 = frac(sin(dot(i2 + float2(0,1), float2(127.1, 311.7))) * 43758.5453);
float d2 = frac(sin(dot(i2 + float2(1,1), float2(127.1, 311.7))) * 43758.5453);
float n2 = lerp(lerp(a2, b2, u2.x), lerp(c2, d2, u2.x), u2.y);
float field = n1 * 0.65 + n2 * 0.35;
float puddle = smoothstep(0.52 - 0.25 * Wet, 0.62 - 0.2 * Wet, field);
"""
    col = custom(m, common + """
float3 dry = Base * (0.8 + 0.5 * n2);
float3 wetc = Base * 0.45;
float3 cc = lerp(dry, wetc, puddle);
float sand = VCa * UseVC;
float3 sandc = VC * (0.75 + 0.5 * n2);
return lerp(cc, sandc, sand);
""", unreal.CustomMaterialOutputType.CMOT_FLOAT3, ["WP", "Base", "Wet", "Sc", "VC", "VCa", "UseVC"], -700, 0, "ground_base")
    wire_custom(col, [(wp, ""), (base_col, ""), (wet, ""), (scale, ""), (vc, ""), (vc, "A"), (use_vc, "")])
    MEL.connect_material_property(col, "", unreal.MaterialProperty.MP_BASE_COLOR)

    rough = custom(m, common + """
float dryR = 0.65 + 0.25 * n2;
float wetR = 0.04 + 0.1 * n2;
float r0 = lerp(dryR, wetR, puddle);
return lerp(r0, 0.85, VCa * UseVC);
""", unreal.CustomMaterialOutputType.CMOT_FLOAT1, ["WP", "Wet", "Sc", "VCa", "UseVC"], -700, 300, "ground_rough")
    wire_custom(rough, [(wp, ""), (wet, ""), (scale, ""), (vc, "A"), (use_vc, "")])
    MEL.connect_material_property(rough, "", unreal.MaterialProperty.MP_ROUGHNESS)

    tmg = expr(m, unreal.MaterialExpressionTime, -1200, 900)
    nrm = custom(m, common + """
// rain ripples: expanding rings in random cells, only in the puddles
float2 q = WP.xy / 140.0;
float2 cid = floor(q);
float2 cf = frac(q) - 0.5;
float h1 = frac(sin(dot(cid, float2(12.9898, 78.233))) * 43758.5453);
float h2 = frac(sin(dot(cid, float2(39.346, 11.135))) * 43758.5453);
float2 off = (float2(h1, h2) - 0.5) * 0.5;
float t = frac(T * (0.7 + h1 * 0.5) + h2);
float r = length(cf - off);
float ring = sin((r - t * 0.55) * 46.0) * exp(-t * 3.2) * (1.0 - smoothstep(0.0, 0.55, abs(r - t * 0.55) * 3.0));
float2 dir = normalize(cf - off + 1e-4);
float k = ring * 0.55 * puddle * step(0.35, h1);
return normalize(float3(dir * k, 1.0));
""", unreal.CustomMaterialOutputType.CMOT_FLOAT3, ["WP", "Wet", "Sc", "T"], -700, 800, "ground_ripple")
    wire_custom(nrm, [(wp, ""), (wet, ""), (scale, ""), (tmg, "")])
    MEL.connect_material_property(nrm, "", unreal.MaterialProperty.MP_NORMAL)
    spec = scalar(m, "Specular", 0.5, -700, 600)
    MEL.connect_material_property(spec, "", unreal.MaterialProperty.MP_SPECULAR)
    MEL.recompile_material(m)
    unreal.EditorAssetLibrary.save_loaded_asset(m)
    return m


def build_water():
    """Sea: Single Layer Water shading, travelling wave normals, murky blue-green absorption."""
    m = make_material("M_Sea")
    m.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_SINGLE_LAYER_WATER)
    m.set_editor_property("blend_mode", unreal.BlendMode.BLEND_OPAQUE)
    wp = expr(m, unreal.MaterialExpressionWorldPosition, -1200, 0)
    time = expr(m, unreal.MaterialExpressionTime, -1200, 150)
    scatter = vector(m, "ScatteringColor", (0.01, 0.06, 0.07, 1), -1200, 300)
    absorb = vector(m, "AbsorptionColor", (0.35, 0.12, 0.08, 1), -1200, 450)
    wave_h = scalar(m, "WaveScale", 5200.0, -1200, 600)

    cam = expr(m, unreal.MaterialExpressionCameraPositionWS, -1200, 750)
    nrm = custom(m, """
float2 p = WP.xy / S;
float t = T * 0.30;
// domain warp breaks the regular look of summed sines
p += 0.18 * float2(sin(p.y * 2.7 + t * 0.8), cos(p.x * 2.3 - t * 0.6));
p += 0.06 * float2(sin(p.y * 9.1 - t * 1.7), cos(p.x * 8.3 + t * 1.3));
float2 d1 = normalize(float2(1.0, 0.35)), d2 = normalize(float2(-0.55, 1.0)), d3 = normalize(float2(0.25, -1.0));
float2 d4 = normalize(float2(-1.0, -0.45)), d5 = normalize(float2(0.8, 0.9));
float2 g = float2(0, 0);
g += d1 * cos(dot(p, d1) * 6.28 * 0.8 + t * 1.1) * 0.40;
g += d2 * cos(dot(p, d2) * 6.28 * 1.9 + t * 1.6) * 0.26;
g += d3 * cos(dot(p, d3) * 6.28 * 3.7 + t * 2.3) * 0.17;
g += d4 * cos(dot(p, d4) * 6.28 * 7.3 + t * 3.1) * 0.10;
g += d5 * cos(dot(p, d5) * 6.28 * 13.1 + t * 3.9) * 0.06;
float dist = length(WP.xy - Cam.xy);
float fade = saturate(1.0 - dist / 90000.0);
return normalize(float3(-g * 0.45 * fade, 1.0));
""", unreal.CustomMaterialOutputType.CMOT_FLOAT3, ["WP", "S", "T", "Cam"], -700, 0, "sea_normal")
    wire_custom(nrm, [(wp, ""), (wave_h, ""), (time, ""), (cam, "")])
    MEL.connect_material_property(nrm, "", unreal.MaterialProperty.MP_NORMAL)

    MEL.connect_material_property(scatter, "", unreal.MaterialProperty.MP_BASE_COLOR)
    rough = scalar(m, "Roughness", 0.06, -700, 300)
    MEL.connect_material_property(rough, "", unreal.MaterialProperty.MP_ROUGHNESS)
    spec = scalar(m, "Specular", 0.55, -700, 400)
    MEL.connect_material_property(spec, "", unreal.MaterialProperty.MP_SPECULAR)
    out = expr(m, unreal.MaterialExpressionSingleLayerWaterMaterialOutput, -300, 500)
    sc = vector(m, "ScatterCoeff", (0.002, 0.012, 0.015, 1), -700, 700)
    ab = vector(m, "AbsorbCoeff", (0.0006, 0.0003, 0.0002, 1), -700, 850)
    for src, names in ((sc, ["", "Scattering", "ScatteringCoefficients", "Scattering Coefficients"]),
                       (ab, ["Absorption", "AbsorptionCoefficients", "Absorption Coefficients"])):
        for pin in names:
            if MEL.connect_material_expressions(src, "", out, pin):
                unreal.log("IV water pin ok: %r" % pin)
                break
        else:
            unreal.log_error("IV water pin FAILED for %s" % names)
    MEL.recompile_material(m)
    unreal.EditorAssetLibrary.save_loaded_asset(m)
    return m


def build_armor():
    """Grey-box / interim mech armour: tinted painted metal with panel lines from object-space position and edge dirt."""
    m = make_material("M_MechArmor")
    m.set_editor_property("used_with_instanced_static_meshes", True)
    pos = expr(m, unreal.MaterialExpressionWorldPosition, -1200, 0)
    tint = vector(m, "Tint", (0.18, 0.19, 0.2, 1), -1200, 200)
    wear = scalar(m, "Wear", 0.5, -1200, 350)
    nrm = expr(m, unreal.MaterialExpressionVertexNormalWS, -1200, 450)
    code = """
float3 n = normalize(Nrm);
float3 q = WP / 380.0;
float3 g = abs(frac(q) - 0.5);
float pnl = smoothstep(0.455, 0.49, max(max(g.x, g.y), g.z));
float h = frac(sin(dot(floor(q), float3(12.9898, 78.233, 37.719))) * 43758.5453);
float3 col = Tint * (0.8 + 0.4 * h);
col *= 1.0 - 0.5 * pnl;
col = lerp(col, float3(0.05, 0.045, 0.04), Wear * 0.25 * frac(h * 91.0) * step(0.8, h));
"""
    base = custom(m, code + "return col;", unreal.CustomMaterialOutputType.CMOT_FLOAT3, ["WP", "Nrm", "Tint", "Wear"], -700, 0, "armor_base")
    wire_custom(base, [(pos, ""), (nrm, ""), (tint, ""), (wear, "")])
    MEL.connect_material_property(base, "", unreal.MaterialProperty.MP_BASE_COLOR)
    rough = custom(m, code + "return lerp(0.38, 0.75, h * Wear) + 0.1 * pnl;", unreal.CustomMaterialOutputType.CMOT_FLOAT1, ["WP", "Nrm", "Tint", "Wear"], -700, 300, "armor_rough")
    wire_custom(rough, [(pos, ""), (nrm, ""), (tint, ""), (wear, "")])
    MEL.connect_material_property(rough, "", unreal.MaterialProperty.MP_ROUGHNESS)
    metal = scalar(m, "Metallic", 0.55, -700, 600)
    MEL.connect_material_property(metal, "", unreal.MaterialProperty.MP_METALLIC)
    MEL.recompile_material(m)
    unreal.EditorAssetLibrary.save_loaded_asset(m)
    return m


def build_mechhull(name="M_MechHull", masked=False):
    """Hull of the generated mechs (skeletal mesh): dark painted metal, rest-pose procedural panels/grime (UV0 = rest XY/82+.5,
    UV1.x = rest Z/82), vertex colour R = convexity (edge wear), G = ambient occlusion, B = zone, A = emissive mask."""
    m = make_material(name)
    m.set_editor_property("used_with_skeletal_mesh", True)
    m.set_editor_property("used_with_morph_targets", True)
    if masked:
        m.set_editor_property("blend_mode", unreal.BlendMode.BLEND_MASKED)
        m.set_editor_property("two_sided", True)
    uva = expr(m, unreal.MaterialExpressionTextureCoordinate, -1500, 0)
    uva.set_editor_property("coordinate_index", 0)
    uvb = expr(m, unreal.MaterialExpressionTextureCoordinate, -1500, 120)
    uvb.set_editor_property("coordinate_index", 1)
    vc = expr(m, unreal.MaterialExpressionVertexColor, -1500, 260)
    tint = vector(m, "Tint", (0.035, 0.037, 0.042, 1), -1500, 420)
    accent = vector(m, "Accent", (0.55, 0.02, 0.015, 1), -1500, 540)
    glow = vector(m, "Glow", (7.0, 0.35, 0.09, 1), -1500, 660)
    wear = scalar(m, "Wear", 0.8, -1500, 780)
    dmg = scalar(m, "Damage", 0.0, -1500, 880)
    accamt = scalar(m, "AccentAmount", 1.0, -1500, 980)
    rage = scalar(m, "Rage", 0.0, -1500, 1080)
    names = ["UVA", "UVB", "VC", "VCA", "Tint", "Accent", "Glow", "Wear", "Damage", "AccAmt", "Rage"]
    srcs = [(uva, ""), (uvb, ""), (vc, ""), (vc, "A"), (tint, ""), (accent, ""), (glow, ""), (wear, ""), (dmg, ""), (accamt, ""), (rage, "")]
    common = """
float3 P = float3(UVA.x - 0.5, UVA.y - 0.5, UVB.x) * 82.0;
float conv = VC.r, ao = VC.g, em = VCA;
float n = 0.0, a = 0.5; float3 p = P * 0.33;
for (int i = 0; i < 4; i++)
{
    float3 ip = floor(p), fp = frac(p);
    float3 u = fp * fp * (3.0 - 2.0 * fp);
    float3 k = float3(127.1, 311.7, 74.7);
    float c000 = frac(sin(dot(ip, k)) * 43758.5453);
    float c100 = frac(sin(dot(ip + float3(1,0,0), k)) * 43758.5453);
    float c010 = frac(sin(dot(ip + float3(0,1,0), k)) * 43758.5453);
    float c110 = frac(sin(dot(ip + float3(1,1,0), k)) * 43758.5453);
    float c001 = frac(sin(dot(ip + float3(0,0,1), k)) * 43758.5453);
    float c101 = frac(sin(dot(ip + float3(1,0,1), k)) * 43758.5453);
    float c011 = frac(sin(dot(ip + float3(0,1,1), k)) * 43758.5453);
    float c111 = frac(sin(dot(ip + float3(1,1,1), k)) * 43758.5453);
    n += a * lerp(lerp(lerp(c000, c100, u.x), lerp(c010, c110, u.x), u.y), lerp(lerp(c001, c101, u.x), lerp(c011, c111, u.x), u.y), u.z);
    p *= 2.07; a *= 0.5;
}
float3 q = P / 3.1;
float3 gq = abs(frac(q) - 0.5);
float pl = smoothstep(0.465, 0.495, max(max(gq.x, gq.y), gq.z));
float fine = frac(sin(dot(floor(P * 6.0), float3(12.9898, 78.233, 37.719))) * 43758.5453);
float edge = saturate((conv - 0.7) * 5.0) * saturate(0.35 + 1.3 * n) * Wear;
float s = frac((P.x * 0.45 + P.z * 0.55) * 0.23 + n * 0.5);
float band = smoothstep(0.80, 0.83, s) * smoothstep(0.96, 0.93, s) * smoothstep(0.35, 0.55, n) * AccAmt;
float soot = smoothstep(1.0 - Damage * 0.95, 1.0, n * 1.25 + 0.15 * (1.0 - ao));
float3 paint = Tint * 1.5 * (0.7 + 0.7 * n) * (1.0 - 0.45 * pl);
paint = lerp(paint, Accent * (0.6 + 0.8 * fine), band);
float3 metal = float3(0.3, 0.29, 0.28) * (0.8 + 0.3 * fine);
float3 col = lerp(paint, metal, edge);
col *= lerp(0.4, 1.0, ao);
col = lerp(col, float3(0.012, 0.011, 0.01), soot);
"""
    t = unreal.CustomMaterialOutputType
    base = custom(m, common + "return col;", t.CMOT_FLOAT3, names, -900, 0, "hull_base")
    wire_custom(base, srcs)
    MEL.connect_material_property(base, "", unreal.MaterialProperty.MP_BASE_COLOR)
    rough = custom(m, common + "return clamp(lerp(0.46, 0.24, edge) + 0.16 * pl + 0.3 * soot + 0.1 * (n - 0.4), 0.14, 0.9);", t.CMOT_FLOAT1, names, -900, 300, "hull_rough")
    wire_custom(rough, srcs)
    MEL.connect_material_property(rough, "", unreal.MaterialProperty.MP_ROUGHNESS)
    met = custom(m, common + "return saturate(0.4 + 0.5 * edge) * (1.0 - soot * 0.9) * (1.0 - 0.35 * band);", t.CMOT_FLOAT1, names, -900, 600, "hull_metal")
    wire_custom(met, srcs)
    MEL.connect_material_property(met, "", unreal.MaterialProperty.MP_METALLIC)
    camv = expr(m, unreal.MaterialExpressionCameraVectorWS, -1500, 1200)
    pnrm = expr(m, unreal.MaterialExpressionPixelNormalWS, -1500, 1300)
    names2 = names + ["CV", "PN"]
    srcs2 = srcs + [(camv, ""), (pnrm, "")]
    emi = custom(m, common + "float rim = pow(saturate(1.0 - abs(dot(normalize(CV), normalize(PN)))), 3.0); float3 rimc = lerp(Accent, Glow * 0.12, 0.5) * rim * 0.35 * (1.0 + Rage * 2.0); float ember = step(0.93, n) * step(0.45, Damage) * saturate(Damage * 2.0 - 0.7) * (0.5 + fine); return Glow * (em * (0.7 + 0.3 * n) + ember * 0.5) * (1.0 + Rage * 2.2) + float3(1.0, 0.08, 0.02) * Rage * (edge * 6.0 + 0.6 * smoothstep(0.55, 0.9, n)) + rimc;", t.CMOT_FLOAT3, names2, -900, 900, "hull_emissive")
    wire_custom(emi, srcs2)
    MEL.connect_material_property(emi, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    if masked:
        wpos = expr(m, unreal.MaterialExpressionWorldPosition, -1500, 1100)
        corg = vector(m, "ClipOrigin", (0, 0, 0, 1), -1500, 1250)
        cnrm = vector(m, "ClipNormal", (0, 1, 0, 1), -1500, 1350)
        side = scalar(m, "ClipSide", 1.0, -1500, 1450)
        face = expr(m, unreal.MaterialExpressionTwoSidedSign, -1500, 1550)
        mask = custom(m, "return (dot(WP - O, N) * Side > 0.0) ? 1.0 : 0.0;", t.CMOT_FLOAT1, ["WP", "O", "N", "Side"], -900, 1100, "clip_mask")
        wire_custom(mask, [(wpos, ""), (corg, ""), (cnrm, ""), (side, "")])
        MEL.connect_material_property(mask, "", unreal.MaterialProperty.MP_OPACITY_MASK)
        # the inside of the cut glows like molten metal
        glow2 = custom(m, "float k = step(Face, 0.0); return float3(4.0, 1.1, 0.18) * k * (0.7 + 0.3 * sin(T * 9.0));", t.CMOT_FLOAT3, ["Face", "T"], -900, 1300, "clip_inside")
        tm2 = expr(m, unreal.MaterialExpressionTime, -1500, 1650)
        wire_custom(glow2, [(face, ""), (tm2, "")])
        MEL.connect_material_property(glow2, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    MEL.recompile_material(m)
    unreal.EditorAssetLibrary.save_loaded_asset(m)
    return m


def build_mechhull_clip():
    return build_mechhull("M_MechHullClip", True)


def build_rain():
    """Rain streaks: every instance wraps around the camera inside a box and falls, all in the vertex shader (no CPU cost)."""
    m = make_material("M_Rain")
    m.set_editor_property("blend_mode", unreal.BlendMode.BLEND_TRANSLUCENT)
    m.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT)
    m.set_editor_property("two_sided", True)
    m.set_editor_property("used_with_instanced_static_meshes", True)
    obj = expr(m, unreal.MaterialExpressionObjectPositionWS, -1400, 0)
    cam = expr(m, unreal.MaterialExpressionCameraPositionWS, -1400, 120)
    tm = expr(m, unreal.MaterialExpressionTime, -1400, 240)
    speed = scalar(m, "Speed", 3200.0, -1400, 480)
    wind = scalar(m, "Wind", 700.0, -1400, 580)
    boxh = scalar(m, "BoxXY", 18000.0, -1400, 680)
    boxv = scalar(m, "BoxZ", 12000.0, -1400, 780)
    amount = scalar(m, "Amount", 0.8, -1400, 880)
    names = ["P0", "Cam", "T", "Speed", "Wind", "BX", "BZ", "Amt"]
    srcs = [(obj, ""), (cam, ""), (tm, ""), (speed, ""), (wind, ""), (boxh, ""), (boxv, ""), (amount, "")]
    code_pos = """
float3 R = P0 - Cam;
R.z -= Speed * T;
R.x += Wind * T;
float3 box = float3(BX, BX, BZ);
R = R + box * 0.5;
R = R - box * floor(R / box);
R = R - box * 0.5;
float3 newP = Cam + R;
"""
    t = unreal.CustomMaterialOutputType
    wpo = custom(m, code_pos + "return newP - P0;", t.CMOT_FLOAT3, names, -900, 0, "rain_wpo")
    wire_custom(wpo, srcs)
    MEL.connect_material_property(wpo, "", unreal.MaterialProperty.MP_WORLD_POSITION_OFFSET)
    op = custom(m, code_pos + "float d = length(R); float fade = smoothstep(1100.0, 3200.0, d) * (1.0 - smoothstep(6500.0, 10000.0, d)); float tw = 0.65 + 0.35 * frac(sin(dot(P0.xy, float2(12.9, 78.2))) * 43758.5); return 0.32 * fade * tw * step(frac(sin(dot(P0.xy, float2(41.7, 17.3))) * 9731.1), Amt);",
                t.CMOT_FLOAT1, names, -900, 300, "rain_opacity")
    wire_custom(op, srcs)
    MEL.connect_material_property(op, "", unreal.MaterialProperty.MP_OPACITY)
    col = vector(m, "Color", (0.55, 0.62, 0.72, 1), -900, 600)
    names2 = names + ["Col"]
    srcs2 = srcs + [(col, "")]
    # neon-lit rain: the streaks pick up the pink / cyan / amber glow of the street depending on where they fall
    em = custom(m, code_pos + """
float zone = 0.5 + 0.5 * sin(newP.x * 0.0004 + newP.y * 0.0006 + T * 0.15);
float zone2 = 0.5 + 0.5 * sin(newP.y * 0.0009 - newP.x * 0.0003 + 1.7);
float3 tint = lerp(lerp(Col, float3(1.0, 0.3, 0.75), zone * 0.8), float3(0.2, 0.9, 1.0), zone2 * 0.6);
float glow = 0.9 + 1.6 * saturate(1.0 - (newP.z - 0.0) / 6000.0);
return tint * glow;
""", t.CMOT_FLOAT3, names2, -900, 700, "rain_color")
    wire_custom(em, srcs2)
    MEL.connect_material_property(em, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    MEL.recompile_material(m)
    unreal.EditorAssetLibrary.save_loaded_asset(m)
    return m


def build_cockpit():
    """Cockpit interior: procedural by material class (UV1.y, see art/cockpit/build_cockpit.py) and local position."""
    m = make_material("M_Cockpit")
    uv0 = expr(m, unreal.MaterialExpressionTextureCoordinate, -1500, 0)
    uv0.set_editor_property("coordinate_index", 0)
    uv1 = expr(m, unreal.MaterialExpressionTextureCoordinate, -1500, 120)
    uv1.set_editor_property("coordinate_index", 1)
    tm = expr(m, unreal.MaterialExpressionTime, -1500, 240)
    power = scalar(m, "Power", 1.0, -1500, 360)
    alert = scalar(m, "Alert", 0.0, -1500, 460)
    wet = scalar(m, "Wet", 0.5, -1500, 560)
    dmg = scalar(m, "Damage", 0.0, -1500, 660)
    names = ["A", "Bq", "T", "Power", "Alert", "Wet", "Damage"]
    srcs = [(uv0, ""), (uv1, ""), (tm, ""), (power, ""), (alert, ""), (wet, ""), (dmg, "")]
    common = """
float3 P = float3((A.x - 0.5) * 2.0, (0.5 - A.y) * 2.0, (Bq.x - 0.5) * 2.0);
float cls = 1.0 - Bq.y;
float c0 = step(-0.5, cls) * step(cls, 0.5);
float c1 = step(0.5, cls) * step(cls, 1.5);
float c2 = step(1.5, cls) * step(cls, 2.5);
float c3 = step(2.5, cls) * step(cls, 3.5);
float c4 = step(3.5, cls) * step(cls, 4.5);
float c5 = step(4.5, cls) * step(cls, 5.5);
float c6 = step(5.5, cls) * step(cls, 6.5);
float c7 = step(6.5, cls) * step(cls, 7.5);
float c8 = step(7.5, cls) * step(cls, 8.5);
float c9 = step(8.5, cls) * step(cls, 9.5);
float c10 = step(9.5, cls) * step(cls, 10.5);
float c11 = step(10.5, cls) * step(cls, 11.5);
float c12 = step(11.5, cls) * step(cls, 12.5);
float c13 = step(12.5, cls) * step(cls, 13.5);
float c14 = step(13.5, cls);
float haz = step(0.5, frac((P.x + P.y + P.z) * 17.0));
float weave = 0.75 + 0.25 * sin(P.x * 420.0) * sin(P.y * 380.0 + P.z * 300.0);
float n = 0.0, a = 0.5; float3 p = P * 9.0;
for (int i = 0; i < 2; i++)
{
    float3 ip = floor(p), fp = frac(p);
    float3 u = fp * fp * (3.0 - 2.0 * fp);
    float3 k = float3(127.1, 311.7, 74.7);
    float c000 = frac(sin(dot(ip, k)) * 43758.5453);
    float c100 = frac(sin(dot(ip + float3(1,0,0), k)) * 43758.5453);
    float c010 = frac(sin(dot(ip + float3(0,1,0), k)) * 43758.5453);
    float c110 = frac(sin(dot(ip + float3(1,1,0), k)) * 43758.5453);
    float c001 = frac(sin(dot(ip + float3(0,0,1), k)) * 43758.5453);
    float c101 = frac(sin(dot(ip + float3(1,0,1), k)) * 43758.5453);
    float c011 = frac(sin(dot(ip + float3(0,1,1), k)) * 43758.5453);
    float c111 = frac(sin(dot(ip + float3(1,1,1), k)) * 43758.5453);
    n += a * lerp(lerp(lerp(c000, c100, u.x), lerp(c010, c110, u.x), u.y), lerp(lerp(c001, c101, u.x), lerp(c011, c111, u.x), u.y), u.z);
    p *= 2.13; a *= 0.5;
}
float fine = frac(sin(dot(floor(P * 90.0), float3(12.9898, 78.233, 37.719))) * 43758.5453);
float cell = frac(sin(dot(floor(P * 38.0), float3(91.7, 37.3, 11.1))) * 43758.5453);
float scan = 0.55 + 0.45 * sin(P.z * 700.0 - T * 6.0);
float grid = step(0.93, frac(P.y * 22.0)) + step(0.93, frac(P.z * 22.0));
float blink = step(0.5, frac(T * (0.4 + cell * 1.3) + cell * 9.0));
float wear = smoothstep(0.62, 0.78, n) * (0.6 + 0.4 * fine);
float streak = smoothstep(0.55, 0.9, frac(sin(floor(P.y * 140.0) * 91.7) * 437.5)) * smoothstep(0.35, 0.8, n);
"""
    t = unreal.CustomMaterialOutputType
    base = custom(m, common + """
float3 dark = float3(0.021, 0.02, 0.019) * (0.7 + 0.8 * n);
dark = lerp(dark, float3(0.2, 0.18, 0.15), wear * 0.55);
float3 grey = lerp(float3(0.085, 0.08, 0.075) * (0.7 + 0.6 * n), float3(0.26, 0.24, 0.21), wear);
float3 org = lerp(float3(0.1, 0.045, 0.015) * (0.75 + 0.5 * n), float3(0.09, 0.07, 0.055), smoothstep(0.7, 0.85, n));
float3 rub = float3(0.010, 0.010, 0.012) * (0.7 + 0.6 * fine);
float3 suit = float3(0.045, 0.05, 0.06) * weave * (0.8 + 0.5 * n);
float3 arm = lerp(float3(0.07, 0.072, 0.08) * (0.8 + 0.5 * n), float3(0.16, 0.155, 0.15), wear);
float3 col = dark * c0 + grey * c1 + org * c2 + rub * c3 + float3(0.005, 0.01, 0.012) * c4 + float3(0.02, 0.01, 0.005) * c5 + float3(0.0, 0.0, 0.0) * c6 + float3(0.02, 0.0, 0.0) * c7
    + lerp(float3(0.012, 0.012, 0.012), float3(0.3, 0.22, 0.0), haz) * c8 + float3(0.03, 0.03, 0.03) * c9 + float3(0.5, 0.5, 0.52) * c10 + float3(0.004, 0.02, 0.006) * c11
    + suit * c12 + arm * c13 + float3(0.01, 0.03, 0.04) * c14;
float3 gcell = frac(P / 0.23 + float3(0.31, 0.17, 0.53));
float3 gd = min(gcell, 1.0 - gcell) * 0.23;
float seamD = min(min(gd.x, gd.y), gd.z);
float seam = (1.0 - smoothstep(0.0, 0.006, seamD)) * (c0 + c1);
float seam2 = (1.0 - smoothstep(0.0, 0.0025, abs(seamD - 0.02))) * (c0 + c1) * 0.5;
float3 cellId = floor(P / 0.23 + float3(0.31, 0.17, 0.53));
float cellH = frac(sin(dot(cellId, float3(12.9898, 78.233, 37.719))) * 43758.5453);
col *= 1.0 - 0.7 * seam;
col *= 1.0 - 0.25 * seam2;
col *= lerp(1.0, 0.78 + 0.44 * cellH, saturate(c0 + c1));
float rivet = (1.0 - smoothstep(0.004, 0.009, length(frac(P / 0.115) - 0.5) * 0.115)) * (c0 + c1) * step(seamD, 0.03);
col += rivet * float3(0.1, 0.09, 0.08);
col *= (1.0 - 0.35 * streak * Wet);
col = lerp(col, col * 0.3, Damage * smoothstep(0.5, 0.9, n));
return col;
""", t.CMOT_FLOAT3, names, -900, 0, "cockpit_base")
    wire_custom(base, srcs)
    MEL.connect_material_property(base, "", unreal.MaterialProperty.MP_BASE_COLOR)
    rough = custom(m, common + """
float r = c0 * (0.38 + 0.3 * wear) + c1 * (0.5 + 0.35 * wear) + c2 * 0.5 + c3 * 0.92 + c4 * 0.15 + c5 * 0.3 + c6 * 0.05 + c7 * 0.3 + c8 * 0.62 + c9 * 0.3 + c10 * 0.17 + c11 * 0.3 + c12 * 0.88 + c13 * (0.4 + 0.3 * wear) + c14 * 0.2;
r = lerp(r, 0.12, Wet * 0.5 * streak * (1.0 - c3));
return clamp(r, 0.04, 0.98);
""", t.CMOT_FLOAT1, names, -900, 300, "cockpit_rough")
    wire_custom(rough, srcs)
    MEL.connect_material_property(rough, "", unreal.MaterialProperty.MP_ROUGHNESS)
    metal = custom(m, common + "return c0 * 0.85 + c1 * (0.2 + 0.7 * wear) + c2 * 0.15 + c4 * 0.1 + c10 * 1.0 + c13 * (0.25 + 0.5 * wear);", t.CMOT_FLOAT1, names, -900, 600, "cockpit_metal")
    wire_custom(metal, srcs)
    MEL.connect_material_property(metal, "", unreal.MaterialProperty.MP_METALLIC)
    emi = custom(m, common + """
float3 cyan = float3(0.05, 0.6, 0.9) * (0.35 + 0.65 * scan) * (0.6 + 0.4 * grid + 0.5 * step(0.8, n));
float3 org = float3(1.0, 0.33, 0.04) * (0.55 + 0.45 * blink);
float3 red = float3(1.0, 0.03, 0.02) * (0.4 + 0.6 * blink) * (1.0 + 2.0 * Alert);
float flick = Power * (0.92 + 0.08 * sin(T * 53.0)) * (1.0 - Damage * step(0.6, frac(T * 7.0 + cell)));
float3 core = float3(0.25, 1.1, 1.6) * (3.5 + 1.5 * sin(T * 2.2));
return (c4 * cyan * 1.5 + c5 * org * 1.9 + c7 * red * 2.0 + c9 * float3(1.0, 0.95, 0.85) * 1.6 + c11 * float3(0.12, 1.0, 0.25) * (1.5 + 1.2 * blink) + c14 * core) * flick + c2 * float3(0.4, 0.05, 0.0) * Alert * 0.2 + c12 * float3(0.0, 0.5, 0.75) * grid * 0.28 * flick;
""", t.CMOT_FLOAT3, names, -900, 900, "cockpit_emissive")
    wire_custom(emi, srcs)
    MEL.connect_material_property(emi, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    MEL.recompile_material(m)
    unreal.EditorAssetLibrary.save_loaded_asset(m)
    return m


def build_cockpit_glass():
    """Canopy glass seen from inside: rain drops (refractive lens bumps) + running streaks; mostly clear."""
    m = make_material("M_CockpitGlass")
    m.set_editor_property("blend_mode", unreal.BlendMode.BLEND_TRANSLUCENT)
    m.set_editor_property("two_sided", True)
    m.set_editor_property("refraction_method", unreal.RefractionMode.RM_PIXEL_NORMAL_OFFSET)
    uv0 = expr(m, unreal.MaterialExpressionTextureCoordinate, -1500, 0)
    uv0.set_editor_property("coordinate_index", 0)
    uv1 = expr(m, unreal.MaterialExpressionTextureCoordinate, -1500, 120)
    uv1.set_editor_property("coordinate_index", 1)
    tm = expr(m, unreal.MaterialExpressionTime, -1500, 240)
    rain = scalar(m, "Rain", 1.0, -1500, 360)
    crack = scalar(m, "Crack", 0.0, -1500, 460)
    imp0 = vector(m, "Imp0", (0, 0, 0, 0), -1500, 1000)
    imp1 = vector(m, "Imp1", (0, 0, 0, 0), -1500, 1100)
    imp2 = vector(m, "Imp2", (0, 0, 0, 0), -1500, 1200)
    names = ["A", "Bq", "T", "Rain", "Crack", "Imp0", "Imp1", "Imp2"]
    srcs = [(uv0, ""), (uv1, ""), (tm, ""), (rain, ""), (crack, ""), (imp0, ""), (imp1, ""), (imp2, "")]
    common = """
float2 g = float2((0.5 - A.y) * 2.0, (Bq.x - 0.5) * 2.0);      // lateral, height (m)
float2 q = g / 0.05;
float2 id = floor(q), f = frac(q);
float best = 9.0; float2 bo = float2(0, 0); float br = 0.1;
for (int j = -1; j <= 1; j++)
for (int i = -1; i <= 1; i++)
{
    float2 cid = id + float2(i, j);
    float h1 = frac(sin(dot(cid, float2(127.1, 311.7))) * 43758.5453);
    float h2 = frac(sin(dot(cid, float2(269.5, 183.3))) * 43758.5453);
    float h3 = frac(sin(dot(cid, float2(419.2, 371.9))) * 43758.5453);
    float2 pos = float2(i, j) + float2(h1, h2);
    float rad = 0.07 + 0.22 * h3 * h3;
    float on = step(0.5 + 0.4 * (1.0 - Rain), h3);
    float2 d = pos - f;
    float dl = length(d) / rad;
    if (on > 0.5 && dl < best) { best = dl; bo = d / rad; br = rad; }
}
float inside = step(best, 1.0);
float cap = sqrt(saturate(1.0 - best * best));
float3 nrm = float3(-bo * (1.0 - cap) * 1.4 * inside, 1.0);
float sx = frac(sin(floor(g.x * 55.0) * 91.7) * 437.5);
float sy = frac(g.y * 3.0 + sx * 7.0 - T * (0.02 + 0.05 * sx));
float run = step(0.82, sx) * smoothstep(0.0, 0.2, sy) * smoothstep(0.6, 0.2, sy) * Rain;
float web = 0.0;
// impact cracks: radial spokes with broken concentric rings around each hit, growing with its strength
float3 imps[3] = { Imp0, Imp1, Imp2 };
for (int ii = 0; ii < 3; ii++)
{
    float st = imps[ii].z;
    if (st > 0.01)
    {
        float2 d = g - imps[ii].xy;
        float r = length(d);
        float ang = atan2(d.y, d.x);
        float N = 13.0;
        float s2 = ang / 6.2832 * N + ii * 3.1;
        float sid = floor(s2);
        float jit = (frac(sin(sid * 91.7 + ii * 17.3) * 437.5) - 0.5) * 0.55;
        float fr = frac(s2) - 0.5;
        float wdt = abs(fr - jit) * r * 6.2832 / N;
        float reach = st * (0.35 + 0.9 * frac(sin(sid * 12.3 + ii * 5.1) * 913.1));
        float spoke = (1.0 - smoothstep(0.0, 0.0045 + 0.004 * st, wdt)) * step(r, reach) * smoothstep(0.012, 0.05, r);
        float ringId = floor(r / 0.085);
        float rh = frac(sin(ringId * 31.1 + ii * 7.7) * 713.3);
        float rd = abs(frac(r / 0.085) - 0.5) * 0.085;
        float seg = step(0.45, frac(sin(floor(ang * 4.0 + ringId * 3.0) * 53.1) * 321.7));
        float rg = (1.0 - smoothstep(0.0, 0.0035, rd)) * step(r, reach * 0.62) * seg * step(0.2, rh) * step(0.04, r);
        float core = (1.0 - smoothstep(0.0, 0.035, r)) * st;
        web = max(web, max(spoke, max(rg * 0.85, core)));
    }
}
// hairline scratches: always there, a little more of them as the glass takes a beating
for (int si = 0; si < 14; si++)
{
    float h0 = frac(sin(si * 12.9898 + 4.1) * 43758.5);
    float h1 = frac(sin(si * 78.233 + 1.3) * 43758.5);
    float h2 = frac(sin(si * 39.346 + 9.7) * 43758.5);
    float2 p0 = float2((h0 - 0.5) * 2.2, (h1 - 0.35) * 1.1);
    float an = (h2 - 0.5) * 3.1416;
    float2 dir = float2(cos(an), sin(an));
    float len = 0.12 + 0.35 * frac(h0 * 7.0 + h1 * 3.0);
    float tt = clamp(dot(g - p0, dir), 0.0, len);
    float dd = length(g - p0 - dir * tt);
    web = max(web, (1.0 - smoothstep(0.0, 0.0022, dd)) * 0.35 * step(si, 5.0 + 9.0 * Crack));
}
"""
    t = unreal.CustomMaterialOutputType
    nrmn = custom(m, common + "return normalize(float3(nrm.xy + float2(0, 0.35) * run, nrm.z));", t.CMOT_FLOAT3, names, -900, 0, "glass_normal")
    wire_custom(nrmn, srcs)
    MEL.connect_material_property(nrmn, "", unreal.MaterialProperty.MP_NORMAL)
    op = custom(m, common + "return saturate(0.025 + inside * (0.10 + 0.35 * (1.0 - cap)) + run * 0.12 + web * 0.9);", t.CMOT_FLOAT1, names, -900, 300, "glass_opacity")
    wire_custom(op, srcs)
    MEL.connect_material_property(op, "", unreal.MaterialProperty.MP_OPACITY)
    tint = vector(m, "Tint", (0.01, 0.02, 0.03, 1), -1500, 560)
    bc = custom(m, common + "return Tint + web * float3(1.4, 1.6, 1.8);", t.CMOT_FLOAT3, names + ["Tint"], -900, 500, "glass_base")
    wire_custom(bc, srcs + [(tint, "")])
    MEL.connect_material_property(bc, "", unreal.MaterialProperty.MP_BASE_COLOR)
    rough = scalar(m, "Roughness", 0.04, -900, 600)
    MEL.connect_material_property(rough, "", unreal.MaterialProperty.MP_ROUGHNESS)
    spec = scalar(m, "Specular", 0.9, -900, 700)
    MEL.connect_material_property(spec, "", unreal.MaterialProperty.MP_SPECULAR)
    ior = custom(m, common + "return lerp(1.0, 1.33, saturate(inside + run * 0.6));", t.CMOT_FLOAT1, names, -900, 800, "glass_ior")
    wire_custom(ior, srcs)
    MEL.connect_material_property(ior, "", unreal.MaterialProperty.MP_REFRACTION)
    MEL.recompile_material(m)
    unreal.EditorAssetLibrary.save_loaded_asset(m)
    return m


def build_sword():
    """Duel sword: dark steel with worn bright edges, a glowing plasma edge (Heat, EdgeColor), rubber grip, orange accents."""
    m = make_material("M_Sword")
    uv0 = expr(m, unreal.MaterialExpressionTextureCoordinate, -1500, 0)
    uv0.set_editor_property("coordinate_index", 0)
    uv1 = expr(m, unreal.MaterialExpressionTextureCoordinate, -1500, 120)
    uv1.set_editor_property("coordinate_index", 1)
    tm = expr(m, unreal.MaterialExpressionTime, -1500, 240)
    heat = scalar(m, "Heat", 0.35, -1500, 360)
    edge = vector(m, "EdgeColor", (3.0, 0.8, 0.12, 1), -1500, 460)
    dmg = scalar(m, "Damage", 0.0, -1500, 560)
    names = ["A", "Bq", "T", "Heat", "EdgeColor", "Damage"]
    srcs = [(uv0, ""), (uv1, ""), (tm, ""), (heat, ""), (edge, ""), (dmg, "")]
    common = """
float3 P = float3((A.x - 0.5) * 2.0, (0.5 - A.y) * 2.0, (Bq.x - 0.5) * 2.0);
float cls = 1.0 - Bq.y;
float c0 = step(-0.5, cls) * step(cls, 0.5);
float c1 = step(0.5, cls) * step(cls, 1.5);
float c2 = step(1.5, cls) * step(cls, 2.5);
float c3 = step(2.5, cls) * step(cls, 3.5);
float c4 = step(3.5, cls);
float n = 0.0, a = 0.5; float3 p = P * 0.45;
for (int i = 0; i < 4; i++)
{
    float3 ip = floor(p), fp = frac(p);
    float3 u = fp * fp * (3.0 - 2.0 * fp);
    float3 k = float3(127.1, 311.7, 74.7);
    float c000 = frac(sin(dot(ip, k)) * 43758.5453);
    float c100 = frac(sin(dot(ip + float3(1,0,0), k)) * 43758.5453);
    float c010 = frac(sin(dot(ip + float3(0,1,0), k)) * 43758.5453);
    float c110 = frac(sin(dot(ip + float3(1,1,0), k)) * 43758.5453);
    float c001 = frac(sin(dot(ip + float3(0,0,1), k)) * 43758.5453);
    float c101 = frac(sin(dot(ip + float3(1,0,1), k)) * 43758.5453);
    float c011 = frac(sin(dot(ip + float3(0,1,1), k)) * 43758.5453);
    float c111 = frac(sin(dot(ip + float3(1,1,1), k)) * 43758.5453);
    n += a * lerp(lerp(lerp(c000, c100, u.x), lerp(c010, c110, u.x), u.y), lerp(lerp(c001, c101, u.x), lerp(c011, c111, u.x), u.y), u.z);
    p *= 2.2; a *= 0.5;
}
float scratch = smoothstep(0.55, 0.75, frac(sin(floor(P.x * 5.0) * 12.9 + floor(P.y * 14.0) * 78.2) * 43758.5)) * smoothstep(0.35, 0.7, n);
float pulse = 0.82 + 0.18 * sin(T * 3.1 + P.x * 0.35);
"""
    t = unreal.CustomMaterialOutputType
    base = custom(m, common + """
float3 steel = float3(0.04, 0.042, 0.05) * (0.6 + 0.9 * n);
float3 bright = lerp(float3(0.22, 0.22, 0.23), float3(0.5, 0.5, 0.52), scratch) * (0.7 + 0.5 * n);
float3 grip = float3(0.012, 0.011, 0.012);
float3 org = float3(0.42, 0.11, 0.008) * (0.7 + 0.6 * n);
float3 col = steel * c0 + bright * c1 + float3(0.01, 0.01, 0.01) * c2 + grip * c3 + org * c4;
return lerp(col, col * 0.25, Damage * smoothstep(0.45, 0.8, n));
""", t.CMOT_FLOAT3, names, -900, 0, "sword_base")
    wire_custom(base, srcs)
    MEL.connect_material_property(base, "", unreal.MaterialProperty.MP_BASE_COLOR)
    rough = custom(m, common + "return clamp(c0 * (0.32 + 0.3 * n) + c1 * (0.22 + 0.25 * scratch) + c2 * 0.3 + c3 * 0.9 + c4 * 0.5, 0.15, 0.95);", t.CMOT_FLOAT1, names, -900, 300, "sword_rough")
    wire_custom(rough, srcs)
    MEL.connect_material_property(rough, "", unreal.MaterialProperty.MP_ROUGHNESS)
    metal = custom(m, common + "return c0 * 0.9 + c1 * 1.0 + c3 * 0.0 + c4 * 0.2;", t.CMOT_FLOAT1, names, -900, 600, "sword_metal")
    wire_custom(metal, srcs)
    MEL.connect_material_property(metal, "", unreal.MaterialProperty.MP_METALLIC)
    emi = custom(m, common + "return EdgeColor * c2 * (0.15 + 1.6 * Heat) * pulse + EdgeColor * c4 * 0.0;", t.CMOT_FLOAT3, names, -900, 900, "sword_emissive")
    wire_custom(emi, srcs)
    MEL.connect_material_property(emi, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    MEL.recompile_material(m)
    unreal.EditorAssetLibrary.save_loaded_asset(m)
    return m


def build_fire():
    """Flame / explosion sprite: additive, radial blob warped by rising noise, white-yellow -> orange -> deep red with age."""
    m = make_material("M_Fire")
    m.set_editor_property("blend_mode", unreal.BlendMode.BLEND_ADDITIVE)
    m.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT)
    m.set_editor_property("two_sided", True)
    m.set_editor_property("used_with_instanced_static_meshes", True)
    uv = expr(m, unreal.MaterialExpressionTextureCoordinate, -1200, 0)
    age = expr(m, unreal.MaterialExpressionPerInstanceCustomData, -1200, 150)
    age.set_editor_property("data_index", 0)
    seed = expr(m, unreal.MaterialExpressionPerInstanceCustomData, -1200, 300)
    seed.set_editor_property("data_index", 1)
    heat = expr(m, unreal.MaterialExpressionPerInstanceCustomData, -1200, 450)
    heat.set_editor_property("data_index", 2)
    gain = scalar(m, "Gain", 2.2, -1200, 600)
    code = """
float2 q = (UV - 0.5) * 2.0;
float r = length(q);
float2 p = q * 2.4 + Seed * 53.0 + float2(0.0, -Age * 3.2);
float n = 0.0, a = 0.5;
for (int i = 0; i < 4; i++)
{
    float2 ip = floor(p), fp = frac(p);
    float2 u = fp * fp * (3.0 - 2.0 * fp);
    float h00 = frac(sin(dot(ip, float2(127.1, 311.7))) * 43758.5453);
    float h10 = frac(sin(dot(ip + float2(1,0), float2(127.1, 311.7))) * 43758.5453);
    float h01 = frac(sin(dot(ip + float2(0,1), float2(127.1, 311.7))) * 43758.5453);
    float h11 = frac(sin(dot(ip + float2(1,1), float2(127.1, 311.7))) * 43758.5453);
    n += a * lerp(lerp(h00, h10, u.x), lerp(h01, h11, u.x), u.y);
    p *= 2.07; a *= 0.5;
}
float shape = saturate(1.0 - r);
shape = shape * shape;
float alpha = saturate(shape * (0.55 + 1.5 * n) - 0.16) * smoothstep(0.0, 0.07, Age) * pow(saturate(1.0 - Age), 1.3);
"""
    col = custom(m, code + """
float3 hot = lerp(float3(3.0, 2.2, 1.0), float3(2.4, 0.9, 0.18), saturate(Age * 2.2));
float3 cool = lerp(float3(1.8, 0.5, 0.08), float3(0.55, 0.06, 0.01), saturate(Age * 1.6));
float3 c = lerp(cool, hot, Heat) * lerp(0.7, 1.4, n);
return c * alpha * Gain;
""", unreal.CustomMaterialOutputType.CMOT_FLOAT3, ["UV", "Age", "Seed", "Heat", "Gain"], -700, 0, "fire_color")
    wire_custom(col, [(uv, ""), (age, ""), (seed, ""), (heat, ""), (gain, "")])
    MEL.connect_material_property(col, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    MEL.recompile_material(m)
    unreal.EditorAssetLibrary.save_loaded_asset(m)
    return m


def build_trail():
    """Blade trail ribbon: additive, colour = EdgeColor, vertex colour alpha = age fade, UV.y across (0 = tip, 1 = inner edge)."""
    m = make_material("M_BladeTrail")
    m.set_editor_property("blend_mode", unreal.BlendMode.BLEND_ADDITIVE)
    m.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT)
    m.set_editor_property("two_sided", True)
    uv = expr(m, unreal.MaterialExpressionTextureCoordinate, -1200, 0)
    vc = expr(m, unreal.MaterialExpressionVertexColor, -1200, 150)
    col = vector(m, "EdgeColor", (0.4, 1.4, 3.0, 1), -1200, 300)
    gain = scalar(m, "Gain", 3.0, -1200, 450)
    c = custom(m, """
float across = saturate(UV.y);
float edge = pow(saturate(1.0 - across), 1.6);
float core = smoothstep(0.0, 0.18, 1.0 - across);
float3 c = lerp(Col.rgb, float3(1.0, 1.0, 1.0) * 1.5, core * 0.55);
return c * edge * Fade * Gain;
""", unreal.CustomMaterialOutputType.CMOT_FLOAT3, ["UV", "Fade", "Col", "Gain"], -700, 0, "trail")
    wire_custom(c, [(uv, ""), (vc, "A"), (col, ""), (gain, "")])
    MEL.connect_material_property(c, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    MEL.recompile_material(m)
    unreal.EditorAssetLibrary.save_loaded_asset(m)
    return m


def build_puff():
    """Soft dust/smoke sprite: procedural radial noise, per-instance age/seed from custom data."""
    m = make_material("M_Puff")
    m.set_editor_property("blend_mode", unreal.BlendMode.BLEND_TRANSLUCENT)
    m.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT)
    m.set_editor_property("two_sided", True)
    m.set_editor_property("used_with_instanced_static_meshes", True)
    uv = expr(m, unreal.MaterialExpressionTextureCoordinate, -1200, 0)
    age = expr(m, unreal.MaterialExpressionPerInstanceCustomData, -1200, 150)
    age.set_editor_property("data_index", 0)
    seed = expr(m, unreal.MaterialExpressionPerInstanceCustomData, -1200, 300)
    seed.set_editor_property("data_index", 1)
    dark = expr(m, unreal.MaterialExpressionPerInstanceCustomData, -1200, 380)
    dark.set_editor_property("data_index", 2)
    bright = scalar(m, "Brightness", 0.2, -1200, 450)
    code = """
float2 q = (UV - 0.5) * 2.0;
float r = length(q);
float sd = Seed * 91.7;
float2 p = q * 2.2 + sd;
float n = 0.0, a = 0.5;
for (int i = 0; i < 4; i++)
{
    float2 ip = floor(p), fp = frac(p);
    float2 u = fp * fp * (3.0 - 2.0 * fp);
    float h00 = frac(sin(dot(ip, float2(127.1, 311.7))) * 43758.5453);
    float h10 = frac(sin(dot(ip + float2(1,0), float2(127.1, 311.7))) * 43758.5453);
    float h01 = frac(sin(dot(ip + float2(0,1), float2(127.1, 311.7))) * 43758.5453);
    float h11 = frac(sin(dot(ip + float2(1,1), float2(127.1, 311.7))) * 43758.5453);
    n += a * lerp(lerp(h00, h10, u.x), lerp(h01, h11, u.x), u.y);
    p *= 2.03; a *= 0.5;
}
float shape = saturate(1.0 - r);
shape = shape * shape * (3.0 - 2.0 * shape);
float fadeIn = saturate(Age * 14.0);
float fadeOut = pow(saturate(1.0 - Age), 1.6);
float alpha = saturate(shape * (0.35 + 1.1 * n) - 0.12) * fadeIn * fadeOut;
"""
    op = custom(m, code + "return alpha * 0.6;", unreal.CustomMaterialOutputType.CMOT_FLOAT1, ["UV", "Age", "Seed"], -700, 0, "puff_alpha")
    wire_custom(op, [(uv, ""), (age, ""), (seed, "")])
    col = custom(m, "float3 c = lerp(float3(0.62, 0.6, 0.57), float3(0.28, 0.27, 0.27), frac(Seed * 7.13)); return c * B * (1.0 - 0.9 * Dark);",
                 unreal.CustomMaterialOutputType.CMOT_FLOAT3, ["Seed", "B", "Dark"], -700, 250, "puff_color")
    wire_custom(col, [(seed, ""), (bright, ""), (dark, "")])
    MEL.connect_material_property(col, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    MEL.connect_material_property(op, "", unreal.MaterialProperty.MP_OPACITY)
    MEL.recompile_material(m)
    unreal.EditorAssetLibrary.save_loaded_asset(m)
    return m


def build_propcolor():
    """Generic instanced prop paint: colour comes from per-instance custom data (r, g, b)."""
    m = make_material("M_PropColor")
    m.set_editor_property("used_with_instanced_static_meshes", True)
    r = expr(m, unreal.MaterialExpressionPerInstanceCustomData, -900, 0)
    r.set_editor_property("data_index", 0)
    g = expr(m, unreal.MaterialExpressionPerInstanceCustomData, -900, 120)
    g.set_editor_property("data_index", 1)
    b = expr(m, unreal.MaterialExpressionPerInstanceCustomData, -900, 240)
    b.set_editor_property("data_index", 2)
    c = custom(m, "return float3(R, G, B);", unreal.CustomMaterialOutputType.CMOT_FLOAT3, ["R", "G", "B"], -500, 100, "prop_color")
    wire_custom(c, [(r, ""), (g, ""), (b, "")])
    MEL.connect_material_property(c, "", unreal.MaterialProperty.MP_BASE_COLOR)
    rough = scalar(m, "Roughness", 0.45, -500, 300)
    MEL.connect_material_property(rough, "", unreal.MaterialProperty.MP_ROUGHNESS)
    metal = scalar(m, "Metallic", 0.3, -500, 400)
    MEL.connect_material_property(metal, "", unreal.MaterialProperty.MP_METALLIC)
    MEL.recompile_material(m)
    unreal.EditorAssetLibrary.save_loaded_asset(m)
    return m


def build_spark():
    m = make_material("M_Spark")
    m.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT)
    m.set_editor_property("used_with_instanced_static_meshes", True)
    c = vector(m, "Color", (14.0, 5.0, 1.2, 1), -700, 0)
    MEL.connect_material_property(c, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    MEL.recompile_material(m)
    unreal.EditorAssetLibrary.save_loaded_asset(m)
    return m


def _cd(m, idx, default, x, y):
    e = expr(m, unreal.MaterialExpressionPerInstanceCustomData, x, y)
    e.set_editor_property("data_index", idx)
    e.set_editor_property("const_default_value", default)
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
    xf = nrm
    cds = [_cd(m, i, d, -1500, 360 + 110 * i) for i, d in enumerate([1.0, 0.1, 0.5, 0.1, 0.9, 1.0, 0.0, 0.0, 0.3, 0.0])]
    gain = scalar(m, "Gain", 1.0, -1500, 1400)
    names = ["UV", "T", "NL", "R1", "G1", "B1", "R2", "G2", "B2", "SA", "Seed", "Asp", "Gain", "Yaw"]
    srcs = [(uv, ""), (tm, ""), (xf, ""), (cds[0], ""), (cds[1], ""), (cds[2], ""), (cds[3], ""), (cds[4], ""), (cds[5], ""), (cds[6], ""), (cds[7], ""), (cds[8], ""), (gain, ""), (cds[9], "")]
    common = HASH_FN + """
float3 C1 = float3(R1, G1, B1), C2 = float3(R2, G2, B2);
float style = fmod(SA, 10.0), anim = floor(SA / 10.0);
float yawr = radians(Yaw);
float face = step(0.55, dot(normalize(NL), float3(cos(yawr), sin(yawr), 0)));
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
    bright = scalar(m, "Bright", 0.3, -1500, 1080)
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
float cc = h21(id + Seed);
float lit1 = step(0.88, hs) + step(0.74, hf) * step(0.3, hs) * 0.75;
float on = saturate(lit1) * glassM * Lit;
float3 warm = (cc < 0.6) ? float3(1.0, 0.78, 0.5) : ((cc < 0.9) ? float3(0.7, 0.86, 1.0) : float3(1.0, 0.4, 0.8));
float3 e = warm * on * (0.9 + 1.4 * hs);
// faked sky/city reflection: the glass glows in its own tint, brighter near the horizon and at grazing angles
float hgt = saturate(WP.z / 22000.0);
float streak = 0.5 + 0.5 * sin(hRaw / 1900.0 + Seed * 30.0 + WP.z / 9000.0);
streak = pow(streak, 5.0);
e += tint * glassM * (0.9 + 2.6 * fres) * (0.3 + 0.7 * hgt) * Bright * 2.0;
e += lerp(tint, float3(1.0, 0.5, 0.9), 0.5) * glassM * streak * 1.6 * Bright;
float3 street = lerp(float3(1.0, 0.25, 0.6), float3(0.1, 0.8, 1.0), h11(Seed * 3.3 + floor(WP.z / 1200.0) * 0.07));
e += street * glassM * (1.0 - saturate(WP.z / 6000.0)) * 0.6 * (1.0 - roof);
e *= 0.93 + 0.07 * sin(T * 0.7 + hs * 20.0);
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



def build_monitor():
    """Cockpit monitor: the render target "Tex" (drawn by the game) with scanlines, vignette, glitch and a power fade."""
    m = make_material("M_Monitor")
    uv = expr(m, unreal.MaterialExpressionTextureCoordinate, -1200, 0)
    tm = expr(m, unreal.MaterialExpressionTime, -1200, 120)
    tex = expr(m, unreal.MaterialExpressionTextureObjectParameter, -1200, 240)
    tex.set_editor_property("parameter_name", "Tex")
    tex.set_editor_property("texture", unreal.load_asset("/Engine/EngineResources/WhiteSquareTexture"))
    power = scalar(m, "Power", 1.0, -1200, 400)
    glitch = scalar(m, "Glitch", 0.0, -1200, 500)
    gain = scalar(m, "Gain", 1.7, -1200, 600)
    uo = scalar(m, "UOff", 0.0, -1200, 700)
    vo = scalar(m, "VOff", 0.0, -1200, 800)
    us = scalar(m, "USc", 1.0, -1200, 900)
    vs = scalar(m, "VSc", 1.0, -1200, 1000)
    c = custom(m, """
float2 uv = UV * float2(Us, Vs) + float2(Uo, Vo);
float row = floor(UV.y * 26.0);
float jit = frac(sin(row * 91.7 + floor(T * 11.0) * 13.1) * 437.5) - 0.5;
float hit = step(0.82, frac(sin(row * 12.3 + floor(T * 7.0) * 3.7) * 91.0));
uv.x += jit * 0.05 * Gl * hit;
float3 c = Tex.SampleLevel(TexSampler, uv, 0).rgb;
c.r = Tex.SampleLevel(TexSampler, uv + float2(0.005 * Gl, 0), 0).r;
float scan = 0.86 + 0.14 * sin(UV.y * 420.0 + T * 5.0);
float vig = smoothstep(0.0, 0.08, UV.x) * smoothstep(1.0, 0.92, UV.x) * smoothstep(0.0, 0.08, UV.y) * smoothstep(1.0, 0.92, UV.y);
float on = Pw * (1.0 - Gl * step(0.93, frac(T * 2.3 + UV.y * 1.7)));
return c * Gn * scan * (0.5 + 0.5 * vig) * on;
""", unreal.CustomMaterialOutputType.CMOT_FLOAT3, ["Tex", "UV", "T", "Pw", "Gl", "Gn", "Uo", "Vo", "Us", "Vs"], -800, 100, "monitor_emissive")
    wire_custom(c, [(tex, ""), (uv, ""), (tm, ""), (power, ""), (glitch, ""), (gain, ""), (uo, ""), (vo, ""), (us, ""), (vs, "")])
    MEL.connect_material_property(c, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    bc = expr(m, unreal.MaterialExpressionConstant3Vector, -800, 400)
    bc.set_editor_property("constant", unreal.LinearColor(0.004, 0.006, 0.008, 1))
    MEL.connect_material_property(bc, "", unreal.MaterialProperty.MP_BASE_COLOR)
    r = scalar(m, "Roughness", 0.1, -800, 500)
    MEL.connect_material_property(r, "", unreal.MaterialProperty.MP_ROUGHNESS)
    MEL.recompile_material(m)
    unreal.EditorAssetLibrary.save_loaded_asset(m)
    return m


def build_chunk():
    """Debris chunks (cloud shard library): kind from per-instance custom data 0 concrete, 1 steel, 2 glass, 3 armour plate; heat -> glowing embers."""
    m = make_material("M_Chunk")
    m.set_editor_property("used_with_instanced_static_meshes", True)
    heat = expr(m, unreal.MaterialExpressionPerInstanceCustomData, -1200, 0)
    heat.set_editor_property("data_index", 0)
    kind = expr(m, unreal.MaterialExpressionPerInstanceCustomData, -1200, 120)
    kind.set_editor_property("data_index", 1)
    seed = expr(m, unreal.MaterialExpressionPerInstanceCustomData, -1200, 240)
    seed.set_editor_property("data_index", 2)
    pos = expr(m, unreal.MaterialExpressionWorldPosition, -1200, 360)
    accent = vector(m, "Accent", (0.85, 0.2, 0.03, 1), -1200, 480)
    names = ["Heat", "Kind", "Seed", "WP", "Accent"]
    srcs = [(heat, ""), (kind, ""), (seed, ""), (pos, ""), (accent, "")]
    common = """
float n = 0.0, a = 0.5; float3 p = WP * 0.0045 + Seed * 31.7;
for (int i = 0; i < 3; i++)
{
    float3 ip = floor(p), fp = frac(p);
    float3 u = fp * fp * (3.0 - 2.0 * fp);
    float3 k = float3(127.1, 311.7, 74.7);
    float c000 = frac(sin(dot(ip, k)) * 43758.5453);
    float c100 = frac(sin(dot(ip + float3(1,0,0), k)) * 43758.5453);
    float c010 = frac(sin(dot(ip + float3(0,1,0), k)) * 43758.5453);
    float c110 = frac(sin(dot(ip + float3(1,1,0), k)) * 43758.5453);
    float c001 = frac(sin(dot(ip + float3(0,0,1), k)) * 43758.5453);
    float c101 = frac(sin(dot(ip + float3(1,0,1), k)) * 43758.5453);
    float c011 = frac(sin(dot(ip + float3(0,1,1), k)) * 43758.5453);
    float c111 = frac(sin(dot(ip + float3(1,1,1), k)) * 43758.5453);
    n += a * lerp(lerp(lerp(c000, c100, u.x), lerp(c010, c110, u.x), u.y), lerp(lerp(c001, c101, u.x), lerp(c011, c111, u.x), u.y), u.z);
    p *= 2.3; a *= 0.5;
}
float n2 = n;
float cc = step(Kind, 0.5), cs = step(0.5, Kind) * step(Kind, 1.5), cg = step(1.5, Kind) * step(Kind, 2.5), ca = step(2.5, Kind);
"""
    t = unreal.CustomMaterialOutputType
    base = custom(m, common + "float3 conc = float3(0.30, 0.29, 0.275) * (0.7 + 0.5 * n2); float3 steel = float3(0.22, 0.22, 0.24) * (0.8 + 0.4 * n); float3 gl = float3(0.35, 0.55, 0.65); float3 arm = lerp(float3(0.07, 0.075, 0.09), Accent * 0.6, step(0.8, n)); float3 c = conc * cc + steel * cs + gl * cg + arm * ca; return lerp(c, float3(0.015, 0.012, 0.01), saturate(Heat * 0.25));", t.CMOT_FLOAT3, names, -700, 0, "chunk_base")
    wire_custom(base, srcs)
    MEL.connect_material_property(base, "", unreal.MaterialProperty.MP_BASE_COLOR)
    rough = custom(m, common + "return cc * 0.85 + cs * 0.45 + cg * 0.08 + ca * 0.35;", t.CMOT_FLOAT1, names, -700, 250, "chunk_rough")
    wire_custom(rough, srcs)
    MEL.connect_material_property(rough, "", unreal.MaterialProperty.MP_ROUGHNESS)
    met = custom(m, common + "return cs * 0.9 + cg * 0.6 + ca * 0.75;", t.CMOT_FLOAT1, names, -700, 450, "chunk_metal")
    wire_custom(met, srcs)
    MEL.connect_material_property(met, "", unreal.MaterialProperty.MP_METALLIC)
    emi = custom(m, common + "float crack = smoothstep(0.42, 0.75, n); float e = saturate(Heat) * (0.15 + 1.1 * crack); return float3(4.0, 1.0, 0.12) * e * e * 2.6 + cg * float3(0.04, 0.2, 0.3) + float3(1.0, 0.25, 0.04) * saturate(Heat - 0.6) * 0.7;", t.CMOT_FLOAT3, names, -700, 650, "chunk_emissive")
    wire_custom(emi, srcs)
    MEL.connect_material_property(emi, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    MEL.recompile_material(m)
    unreal.EditorAssetLibrary.save_loaded_asset(m)
    return m


def build_emissive():
    """Plain glowing surface: Color * Intensity."""
    m = make_material("M_Emissive")
    col = vector(m, "Color", (1, 1, 1, 1), -600, 0)
    inten = scalar(m, "Intensity", 5.0, -600, 150)
    mul = expr(m, unreal.MaterialExpressionMultiply, -300, 50)
    MEL.connect_material_expressions(col, "", mul, "A")
    MEL.connect_material_expressions(inten, "", mul, "B")
    MEL.connect_material_property(mul, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    MEL.recompile_material(m)
    unreal.EditorAssetLibrary.save_loaded_asset(m)
    return m


def build_growth():
    """Infection growths: dark wet flesh/chitin with pulsing glowing veins. Params: Pulse (0..1+), Hue (violet/red mix), Boil."""
    m = make_material("M_Growth")
    pos = expr(m, unreal.MaterialExpressionWorldPosition, -1200, 0)
    tm = expr(m, unreal.MaterialExpressionTime, -1200, 120)
    pulse = scalar(m, "Pulse", 0.6, -1200, 240)
    hue = scalar(m, "Hue", 0.35, -1200, 340)
    names = ["WP", "T", "Pulse", "Hue"]
    srcs = [(pos, ""), (tm, ""), (pulse, ""), (hue, "")]
    common = """
float n = 0.0, a = 0.5; float3 p = WP * 0.006;
for (int i = 0; i < 3; i++)
{
    float3 ip = floor(p), fp = frac(p);
    float3 u = fp * fp * (3.0 - 2.0 * fp);
    float3 k = float3(127.1, 311.7, 74.7);
    float c000 = frac(sin(dot(ip, k)) * 43758.5453);
    float c100 = frac(sin(dot(ip + float3(1,0,0), k)) * 43758.5453);
    float c010 = frac(sin(dot(ip + float3(0,1,0), k)) * 43758.5453);
    float c110 = frac(sin(dot(ip + float3(1,1,0), k)) * 43758.5453);
    float c001 = frac(sin(dot(ip + float3(0,0,1), k)) * 43758.5453);
    float c101 = frac(sin(dot(ip + float3(1,0,1), k)) * 43758.5453);
    float c011 = frac(sin(dot(ip + float3(0,1,1), k)) * 43758.5453);
    float c111 = frac(sin(dot(ip + float3(1,1,1), k)) * 43758.5453);
    n += a * lerp(lerp(lerp(c000, c100, u.x), lerp(c010, c110, u.x), u.y), lerp(lerp(c001, c101, u.x), lerp(c011, c111, u.x), u.y), u.z);
    p *= 2.2; a *= 0.5;
}
float vein = 1.0 - smoothstep(0.0, 0.09, abs(n - 0.5));
float beat = 0.55 + 0.45 * sin(T * (2.0 + 2.5 * Pulse) + n * 9.0);
"""
    t = unreal.CustomMaterialOutputType
    base = custom(m, common + "return lerp(float3(0.035, 0.012, 0.02), float3(0.1, 0.03, 0.05), n) * (1.0 - vein * 0.6);", t.CMOT_FLOAT3, names, -700, 0, "growth_base")
    wire_custom(base, srcs)
    MEL.connect_material_property(base, "", unreal.MaterialProperty.MP_BASE_COLOR)
    rough = custom(m, common + "return lerp(0.22, 0.55, n);", t.CMOT_FLOAT1, names, -700, 250, "growth_rough")
    wire_custom(rough, srcs)
    MEL.connect_material_property(rough, "", unreal.MaterialProperty.MP_ROUGHNESS)
    emi = custom(m, common + "float3 c = lerp(float3(3.4, 0.35, 0.1), float3(2.2, 0.25, 3.0), Hue); return c * vein * beat * (0.5 + 1.4 * Pulse) + c * 0.08 * Pulse;", t.CMOT_FLOAT3, names, -700, 500, "growth_emissive")
    wire_custom(emi, srcs)
    MEL.connect_material_property(emi, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    MEL.recompile_material(m)
    unreal.EditorAssetLibrary.save_loaded_asset(m)
    return m


ALL = [build_facade, build_ground, build_water, build_armor, build_mechhull, build_mechhull_clip, build_rain, build_cockpit, build_cockpit_glass, build_sword, build_trail, build_fire, build_puff, build_spark, build_propcolor,
       build_neon_sign, build_glass_tower, build_trim, build_monitor, build_chunk, build_emissive, build_growth]
import os
_only = [x for x in os.environ.get("IV_ONLY", "").split(",") if x]
for fn in ALL:
    if _only and fn.__name__ not in _only:
        continue
    try:
        fn()
        unreal.log("IV material OK: %s" % fn.__name__)
    except Exception as e:  # keep going so one failing material does not hide the others
        unreal.log_error("IV material FAILED: %s : %s" % (fn.__name__, e))
