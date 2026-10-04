import io
SRC = r"F:\IVUnreal\Source\ImpactVector"


def rd(n):
    s = io.open(SRC + "\\" + n, encoding="utf-8").read()
    return s.replace("\r\n", "\n"), ("\r\n" in s)


def wr(n, s, crlf):
    io.open(SRC + "\\" + n, "w", encoding="utf-8", newline="\r\n" if crlf else "\n").write(s)


def ins_after(text, key, block):
    lines = text.split("\n")
    for i, l in enumerate(lines):
        if key in l:
            ind = l[:len(l) - len(l.lstrip("\t"))]
            add = [(ind + bl if bl.strip() else bl) for bl in block.strip("\n").split("\n")]
            lines[i + 1:i + 1] = add
            return "\n".join(lines)
    raise AssertionError(key)


h, crlf = rd("IVMechPawn.h")
if "BuildPlates" not in h:
    h = ins_after(h, "void BuildGreebles();", """void BuildPlates();
struct FIVPlate { TObjectPtr<UStaticMeshComponent> C; iv::Zone Z = iv::Zone::Torso; FVector Size = FVector::OneVector; bool bGone = false; };
TArray<FIVPlate> Plates;
UPROPERTY() TObjectPtr<UMaterialInstanceDynamic> PlateMID;""")
    wr("IVMechPawn.h", h, crlf)

c, crlf = rd("IVMechPawn.cpp")
if "void AIVMechPawn::BuildPlates" not in c:
    c = ins_after(c, "if (GreebleComps.Num() == 0 && !FParse::Param", "if (Plates.Num() == 0 && !FParse::Param(FCommandLine::Get(), TEXT(\"IVNoPlates\"))) BuildPlates();")
    # replace the body of OnArmorPlateLost: use a real plate when one is left
    old = "void AIVMechPawn::OnArmorPlateLost(iv::Zone Z, int32 Index, int32 Count)\n{\n	const FVector Loc = GetZoneWorldLocation(Z);\n"
    assert old in c
    c = c.replace(old, old + """	for (FIVPlate& P : Plates)
	{
		if (P.bGone || P.Z != Z || !P.C) continue;
		P.bGone = true;
		const FTransform Xf = P.C->GetComponentTransform();
		P.C->SetVisibility(false);
		static UStaticMesh* PCube = []{ UStaticMesh* M = LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Cube.Cube")); if (M) M->AddToRoot(); return M; }();
		FActorSpawnParameters Sp2;
		Sp2.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
		FRandomStream R2(Index * 211 + int32(Z) * 29 + 3);
		if (AIVDebris* D = GetWorld()->SpawnActor<AIVDebris>(Xf.GetLocation(), Xf.GetRotation().Rotator(), Sp2))
		{
			const FVector Out = (Xf.GetLocation() - GetActorLocation() + FVector(0, 0, 900.f)).GetSafeNormal();
			D->Init(PCube, PlateMID, P.Size, (Out + R2.VRand() * 0.35f) * R2.FRandRange(1400.f, 2600.f) + FVector(0, 0, 700.f), R2.VRand() * R2.FRandRange(80.f, 240.f));
		}
		if (AIVFXManager* FX = AIVFXManager::Get(GetWorld()))
		{
			FX->SpawnSparks(Xf.GetLocation(), FVector::UpVector, 50, 5500.f);
			FX->SpawnChunks(Xf.GetLocation(), (Xf.GetLocation() - GetActorLocation()).GetSafeNormal() + FVector(0, 0, 0.6f), 3, EIVChunk::Armor, 2.4f, 3200.f, 0.8f);
		}
		IVAudio::Play3D(GetWorld(), TEXT("mech_armor_plate_tear"), Xf.GetLocation(), 1.f);
		return;
	}
""", 1)
    c += r'''

// ---------------------------------------------------------------------------------------------------------- armour plates (they come off one by one as the zone takes damage)
void AIVMechPawn::BuildPlates()
{
	if (!RigMesh) return;
	UStaticMesh* Cube = LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Cube.Cube"));
	UMaterialInterface* Armor = LoadObject<UMaterialInterface>(nullptr, TEXT("/Game/Materials/M_MechArmor.M_MechArmor"));
	if (!Cube || !Armor) return;
	PlateMID = UMaterialInstanceDynamic::Create(Armor, this);
	PlateMID->SetVectorParameterValue(TEXT("Tint"), HullTint * 2.6f + FLinearColor(0.03f, 0.03f, 0.035f));
	PlateMID->SetScalarParameterValue(TEXT("Metallic"), 0.7f);
	PlateMID->SetScalarParameterValue(TEXT("Wear"), 0.8f);
	const FQuat Q = GetActorQuat();
	const FVector Fw = Q.GetForwardVector(), Rt = Q.GetRightVector(), Up = FVector::UpVector;
	struct FSpec { const TCHAR* A; const TCHAR* B; iv::Zone Z; FVector Local; FVector Size; float Roll; };   // Local: offset from the segment centre in (fwd, right, up); Size in cm
	const FSpec Specs[] = {
		// chest and back
		{ TEXT("torso"), TEXT("torso"), iv::Zone::Torso, FVector(900, 0, 350), FVector(260, 1500, 1050), 0.f },
		{ TEXT("torso"), TEXT("torso"), iv::Zone::Torso, FVector(850, -750, -450), FVector(240, 700, 640), 0.f },
		{ TEXT("torso"), TEXT("torso"), iv::Zone::Torso, FVector(850, 750, -450), FVector(240, 700, 640), 0.f },
		{ TEXT("torso"), TEXT("torso"), iv::Zone::Torso, FVector(-900, 0, 450), FVector(260, 1300, 1100), 0.f },
		// head
		{ TEXT("head"), TEXT("head"), iv::Zone::Head, FVector(380, -420, 80), FVector(180, 360, 520), 0.f },
		{ TEXT("head"), TEXT("head"), iv::Zone::Head, FVector(380, 420, 80), FVector(180, 360, 520), 0.f },
		// pauldrons
		{ TEXT("shoulder_l"), TEXT("upperarm_l"), iv::Zone::ShoulderL, FVector(0, -330, 330), FVector(900, 780, 280), 0.f },
		{ TEXT("shoulder_r"), TEXT("upperarm_r"), iv::Zone::ShoulderR, FVector(0, 330, 330), FVector(900, 780, 280), 0.f },
		{ TEXT("shoulder_l"), TEXT("upperarm_l"), iv::Zone::ShoulderL, FVector(0, -520, 40), FVector(700, 200, 640), 0.f },
		{ TEXT("shoulder_r"), TEXT("upperarm_r"), iv::Zone::ShoulderR, FVector(0, 520, 40), FVector(700, 200, 640), 0.f },
		// bracers
		{ TEXT("forearm_l"), TEXT("hand_l"), iv::Zone::ArmL, FVector(260, -90, 0), FVector(240, 500, 1250), 0.f },
		{ TEXT("forearm_r"), TEXT("hand_r"), iv::Zone::ArmR, FVector(260, 90, 0), FVector(240, 500, 1250), 0.f },
		{ TEXT("upperarm_l"), TEXT("forearm_l"), iv::Zone::ArmL, FVector(300, -80, 0), FVector(240, 560, 900), 0.f },
		{ TEXT("upperarm_r"), TEXT("forearm_r"), iv::Zone::ArmR, FVector(300, 80, 0), FVector(240, 560, 900), 0.f },
		// legs
		{ TEXT("thigh_l"), TEXT("shin_l"), iv::Zone::LegL, FVector(420, -60, 0), FVector(260, 620, 1500), 0.f },
		{ TEXT("thigh_r"), TEXT("shin_r"), iv::Zone::LegR, FVector(420, 60, 0), FVector(260, 620, 1500), 0.f },
		{ TEXT("shin_l"), TEXT("foot_l"), iv::Zone::LegL, FVector(470, -40, 0), FVector(260, 620, 1500), 0.f },
		{ TEXT("shin_r"), TEXT("foot_r"), iv::Zone::LegR, FVector(470, 40, 0), FVector(260, 620, 1500), 0.f },
	};
	for (const FSpec& S : Specs)
	{
		if (RigMesh->GetBoneIndex(FName(S.A)) == INDEX_NONE || RigMesh->GetBoneIndex(FName(S.B)) == INDEX_NONE) continue;
		const FVector PA = RigMesh->GetBoneLocation(FName(S.A), EBoneSpaces::WorldSpace), PB = RigMesh->GetBoneLocation(FName(S.B), EBoneSpaces::WorldSpace);
		const bool bSeg = S.A != S.B && (PB - PA).Size() > 300.f;
		const FVector Mid = bSeg ? (PA + PB) * 0.5f : PA;
		const FVector Pos = Mid + Fw * S.Local.X + Rt * S.Local.Y + Up * S.Local.Z;
		// plates are laid out in actor space: thin along X (facing out), long along Z (or along the limb when it is a segment)
		FQuat Rot = Q;
		if (bSeg)
		{
			const FVector Ax = (PB - PA).GetSafeNormal();
			Rot = FRotationMatrix::MakeFromZX(Ax, Fw).ToQuat();
		}
		UStaticMeshComponent* C = NewObject<UStaticMeshComponent>(this);
		C->SetStaticMesh(Cube);
		C->SetMaterial(0, PlateMID);
		C->SetCollisionEnabled(ECollisionEnabled::NoCollision);
		C->SetCastShadow(true);
		C->RegisterComponent();
		const FVector Size = S.Size;
		C->SetWorldTransform(FTransform(Rot, Pos, Size / 100.f));
		C->AttachToComponent(RigMesh, FAttachmentTransformRules::KeepWorldTransform, FName(S.A));
		FIVPlate P;
		P.C = C; P.Z = S.Z; P.Size = Size;
		Plates.Add(P);
	}
	UE_LOG(LogTemp, Display, TEXT("IV plates: %d"), Plates.Num());
}
'''
    wr("IVMechPawn.cpp", c, crlf)
# hide in first person too
c, crlf = rd("IVMechPawn.cpp")
if "for (FIVPlate& Pl : Plates)" not in c:
    c = c.replace("	for (UStaticMeshComponent* G : GrowthComps) if (G) G->SetOwnerNoSee(bFirstPerson);\n", "	for (UStaticMeshComponent* G : GrowthComps) if (G) G->SetOwnerNoSee(bFirstPerson);\n	for (FIVPlate& Pl : Plates) if (Pl.C) Pl.C->SetOwnerNoSee(bFirstPerson);\n", 1)
    wr("IVMechPawn.cpp", c, crlf)
print("plates patched")
