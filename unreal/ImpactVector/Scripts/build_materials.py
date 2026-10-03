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
return lerp(dry, wetc, puddle);
""", unreal.CustomMaterialOutputType.CMOT_FLOAT3, ["WP", "Base", "Wet", "Sc"], -700, 0, "ground_base")
    wire_custom(col, [(wp, ""), (base_col, ""), (wet, ""), (scale, "")])
    MEL.connect_material_property(col, "", unreal.MaterialProperty.MP_BASE_COLOR)

    rough = custom(m, common + """
float dryR = 0.65 + 0.25 * n2;
float wetR = 0.04 + 0.1 * n2;
return lerp(dryR, wetR, puddle);
""", unreal.CustomMaterialOutputType.CMOT_FLOAT1, ["WP", "Wet", "Sc"], -700, 300, "ground_rough")
    wire_custom(rough, [(wp, ""), (wet, ""), (scale, "")])
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


for fn in (build_facade, build_ground, build_water, build_armor):
    try:
        fn()
        unreal.log("IV material OK: %s" % fn.__name__)
    except Exception as e:  # keep going so one failing material does not hide the others
        unreal.log_error("IV material FAILED: %s : %s" % (fn.__name__, e))
