import io
SRC = r"F:\IVUnreal\Source\ImpactVector"


def rd(n):
    s = io.open(SRC + "\\" + n, encoding="utf-8").read()
    return s.replace("\r\n", "\n"), ("\r\n" in s)


def wr(n, s, crlf):
    io.open(SRC + "\\" + n, "w", encoding="utf-8", newline="\r\n" if crlf else "\n").write(s)


def rep(t, old, new):
    assert old in t, old[:70]
    return t.replace(old, new, 1)


h, c = rd("IVDistrict.h")
if "Glow;" not in h:
    h = rep(h, "	UPROPERTY() TObjectPtr<UInstancedStaticMeshComponent> Lamps;", "	UPROPERTY() TObjectPtr<UInstancedStaticMeshComponent> Lamps;\n	UPROPERTY() TObjectPtr<UInstancedStaticMeshComponent> Glow;    // emissive prop parts (lamp heads, shop panels, tail lights)\n	UPROPERTY() TObjectPtr<UInstancedStaticMeshComponent> Cones;")
    wr("IVDistrict.h", h, c)

d, c = rd("IVDistrict.cpp")
if "Glow = ISM" not in d:
    d = rep(d, '	Lamps = ISM(TEXT("Lamps"), CylMesh, false);', '	Lamps = ISM(TEXT("Lamps"), CylMesh, false);\n	static ConstructorHelpers::FObjectFinder<UStaticMesh> ConeF(TEXT("/Engine/BasicShapes/Cone.Cone"));\n	Glow = ISM(TEXT("Glow"), CubeMesh, false);\n	Cones = ISM(TEXT("Cones"), ConeF.Object, false);')
    d = rep(d, "for (UInstancedStaticMeshComponent* C : { Cars.Get(), TreeTrunks.Get(), TreeCrowns.Get(), Lamps.Get(), Containers.Get() })\n	{\n		C->NumCustomDataFloats = 3;", "for (UInstancedStaticMeshComponent* C : { Cars.Get(), TreeTrunks.Get(), TreeCrowns.Get(), Lamps.Get(), Containers.Get(), Glow.Get(), Cones.Get() })\n	{\n		C->NumCustomDataFloats = 3;")
    d = rep(d, "		for (UInstancedStaticMeshComponent* C : { Cars.Get(), TreeTrunks.Get(), TreeCrowns.Get(), Lamps.Get() })\n		{\n			C->SetMaterial(0, Prop);\n		}\n	}",
            "		for (UInstancedStaticMeshComponent* C : { Cars.Get(), TreeTrunks.Get(), TreeCrowns.Get(), Lamps.Get(), Cones.Get() })\n		{\n			C->SetMaterial(0, Prop);\n		}\n	}\n	if (UMaterialInstanceDynamic* Gl = MakeMID(TEXT(\"/Game/Materials/M_PropGlow.M_PropGlow\"), Fb)) Glow->SetMaterial(0, Gl);\n	Glow->SetCastShadow(false);")
    a = d.index("void AIVDistrict::BuildProps(")
    b = d.index("void AIVDistrict::BuildPort(")
    new = io.open(r"F:\IVUnreal\Scripts\_buildprops.cpp.txt", encoding="utf-8").read().replace("0.f, 90.f);", "0.f, 0.f, 90.f);")
    d = d[:a] + new + d[b:]
    wr("IVDistrict.cpp", d, c)

dd, c = rd("IVDistrictDecor.cpp")
if "Glow.Get()" not in dd and "Cars, TreeTrunks, TreeCrowns, Lamps, Containers" in dd:
    dd = rep(dd, "Cars, TreeTrunks, TreeCrowns, Lamps, Containers,", "Cars, TreeTrunks, TreeCrowns, Lamps, Glow, Cones, Containers,")
    wr("IVDistrictDecor.cpp", dd, c)
print("props patched")
