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
    lit = scalar(m, "LitAmount", 0.0, -1200, 850)
    glassiness = scalar(m, "Glassiness", 0.55, -1200, 950)

    common = """
float3 n = normalize(Nrm);
float hRaw = lerp(WP.x, WP.y, step(0.5, abs(n.x)));
float h = hRaw / Spacing;
float v = WP.z / Spacing;
float2 f = frac(float2(h, v));
float roof = step(0.7, abs(n.z));
float win = step(0.14, f.x) * step(f.x, 0.86) * step(0.2, f.y) * step(f.y, 0.78) * (1.0 - roof);
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
float on = step(0.82, hash) * win * Lit;
float3 warm = lerp(float3(1.0, 0.82, 0.55), float3(0.7, 0.85, 1.0), frac(hash * 13.0));
return warm * on * 6.0;
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


def build_mechhull():
    """Hull of the generated mechs (skeletal mesh): dark painted metal, rest-pose procedural panels/grime (UV0 = rest XY/82+.5,
    UV1.x = rest Z/82), vertex colour R = convexity (edge wear), G = ambient occlusion, B = zone, A = emissive mask."""
    m = make_material("M_MechHull")
    m.set_editor_property("used_with_skeletal_mesh", True)
    m.set_editor_property("used_with_morph_targets", True)
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
    names = ["UVA", "UVB", "VC", "VCA", "Tint", "Accent", "Glow", "Wear", "Damage", "AccAmt"]
    srcs = [(uva, ""), (uvb, ""), (vc, ""), (vc, "A"), (tint, ""), (accent, ""), (glow, ""), (wear, ""), (dmg, ""), (accamt, "")]
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
float3 paint = Tint * (0.7 + 0.7 * n) * (1.0 - 0.45 * pl);
paint = lerp(paint, Accent * (0.6 + 0.8 * fine), band);
float3 metal = float3(0.30, 0.29, 0.28) * (0.8 + 0.3 * fine);
float3 col = lerp(paint, metal, edge);
col *= lerp(0.4, 1.0, ao);
col = lerp(col, float3(0.012, 0.011, 0.01), soot);
"""
    t = unreal.CustomMaterialOutputType
    base = custom(m, common + "return col;", t.CMOT_FLOAT3, names, -900, 0, "hull_base")
    wire_custom(base, srcs)
    MEL.connect_material_property(base, "", unreal.MaterialProperty.MP_BASE_COLOR)
    rough = custom(m, common + "return clamp(lerp(0.52, 0.28, edge) + 0.18 * pl + 0.22 * soot + 0.12 * (n - 0.4), 0.2, 0.95);", t.CMOT_FLOAT1, names, -900, 300, "hull_rough")
    wire_custom(rough, srcs)
    MEL.connect_material_property(rough, "", unreal.MaterialProperty.MP_ROUGHNESS)
    met = custom(m, common + "return saturate(0.25 + 0.75 * edge) * (1.0 - soot);", t.CMOT_FLOAT1, names, -900, 600, "hull_metal")
    wire_custom(met, srcs)
    MEL.connect_material_property(met, "", unreal.MaterialProperty.MP_METALLIC)
    emi = custom(m, common + "float ember = step(0.93, n) * step(0.45, Damage) * saturate(Damage * 2.0 - 0.7) * (0.5 + fine); return Glow * (em * (0.7 + 0.3 * n) + ember * 0.5);", t.CMOT_FLOAT3, names, -900, 900, "hull_emissive")
    wire_custom(emi, srcs)
    MEL.connect_material_property(emi, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
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
    bright = scalar(m, "Brightness", 0.55, -1200, 450)
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
    op = custom(m, code + "return alpha * 0.85;", unreal.CustomMaterialOutputType.CMOT_FLOAT1, ["UV", "Age", "Seed"], -700, 0, "puff_alpha")
    wire_custom(op, [(uv, ""), (age, ""), (seed, "")])
    col = custom(m, "float3 c = lerp(float3(0.62, 0.6, 0.57), float3(0.28, 0.27, 0.27), frac(Seed * 7.13)); return c * B;",
                 unreal.CustomMaterialOutputType.CMOT_FLOAT3, ["Seed", "B"], -700, 250, "puff_color")
    wire_custom(col, [(seed, ""), (bright, "")])
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


for fn in (build_facade, build_ground, build_water, build_armor, build_mechhull, build_puff, build_spark, build_propcolor):
    try:
        fn()
        unreal.log("IV material OK: %s" % fn.__name__)
    except Exception as e:  # keep going so one failing material does not hide the others
        unreal.log_error("IV material FAILED: %s : %s" % (fn.__name__, e))
