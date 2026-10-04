import io
SRC = r"F:\IVUnreal\Source\ImpactVector"


def rd(n):
    s = io.open(SRC + "\\" + n, encoding="utf-8").read()
    return s.replace("\r\n", "\n"), ("\r\n" in s)


def wr(n, s, crlf):
    io.open(SRC + "\\" + n, "w", encoding="utf-8", newline="\r\n" if crlf else "\n").write(s)


# ------------------------------------------------------------------ FX manager: arbitrary-mesh flying pieces
h, crlf = rd("IVFXManager.h")
if "SpawnPiece" not in h:
    h = h.replace("	float Scale = 1.f, Radius = 50.f;", "	float Scale = 1.f, Radius = 50.f;\n	FVector Scale3 = FVector::OneVector;", 1)
    h = h.replace("	/** Short light flash (clashes, muzzle, lightning-like). */", "	/** A whole piece (armour shell) torn off: keeps its mesh, scale and orientation, tumbles, burns, lies on the street. */\n	void SpawnPiece(UStaticMesh* Mesh, UMaterialInterface* Mat, const FTransform& Xf, const FVector& Vel, const FVector& Spin, float Heat);\n	/** Short light flash (clashes, muzzle, lightning-like). */", 1)
    h = h.replace("	TArray<float> ChunkRadius;", "	TArray<float> ChunkRadius;\n	TMap<UStaticMesh*, int32> PieceSlots;", 1)
    wr("IVFXManager.h", h, crlf)
c, crlf = rd("IVFXManager.cpp")
if "AIVFXManager::SpawnPiece" not in c:
    c = c.replace("void AIVFXManager::SpawnChunks(", r'''void AIVFXManager::SpawnPiece(UStaticMesh* Mesh, UMaterialInterface* Mat, const FTransform& Xf, const FVector& Vel, const FVector& Spin, float Heat)
{
	if (!Mesh || Chunks.Num() >= MaxChunks) return;
	int32* Found = PieceSlots.Find(Mesh);
	int32 Slot;
	if (Found) Slot = *Found;
	else
	{
		UInstancedStaticMeshComponent* I = NewObject<UInstancedStaticMeshComponent>(this);
		I->SetStaticMesh(Mesh);
		I->SetupAttachment(RootComponent);
		I->SetCollisionEnabled(ECollisionEnabled::NoCollision);
		I->SetCastShadow(true);
		I->NumCustomDataFloats = 3;
		I->SetCullDistances(0, 0);
		I->bUseAsOccluder = false;
		I->SetCanEverAffectNavigation(false);
		if (Mat) for (int32 s = 0; s < Mesh->GetStaticMaterials().Num(); ++s) I->SetMaterial(s, Mat);
		I->RegisterComponent();
		Slot = ChunkISM.Add(I);
		ChunkRadius.Add(Mesh->GetBounds().SphereRadius);
		PieceSlots.Add(Mesh, Slot);
	}
	FIVChunk C;
	C.Slot = Slot;
	C.Kind = 3.f;
	C.Scale = 1.f;
	C.Scale3 = Xf.GetScale3D();
	C.Radius = ChunkRadius[Slot] * C.Scale3.GetMax() * 0.5f;
	C.Pos = Xf.GetLocation();
	C.Rot = Xf.GetRotation();
	C.Vel = Vel;
	C.AngVel = Spin;
	C.Life = 18.f;
	C.Heat = Heat;
	C.Seed = Rng.FRand();
	Chunks.Add(C);
}

void AIVFXManager::SpawnChunks(''', 1)
    c = c.replace("T.Add(FTransform(C.Rot, C.Pos, FVector(C.Scale * Fade)));", "T.Add(FTransform(C.Rot, C.Pos, C.Scale3 * (C.Scale * Fade)));", 1)
    wr("IVFXManager.cpp", c, crlf)

# ------------------------------------------------------------------ mech pawn: shell armour
p, crlf = rd("IVMechPawn.cpp")
a = p.index("// ---------------------------------------------------------------------------------------------------------- armour plates")
p = p[:a] + r'''// ---------------------------------------------------------------------------------------------------------- armour plates
// Curved shells authored in Blender (art/armor/build_armor.py): they hug the limbs, are bolted to the bones and come off in pieces
// (the whole shell tumbles away, burning) as the zone beneath is damaged.
void AIVMechPawn::BuildPlates()
{
	if (!RigMesh) return;
	UMaterialInterface* Armor = LoadObject<UMaterialInterface>(nullptr, TEXT("/Game/Materials/M_MechArmor.M_MechArmor"));
	if (!Armor) return;
	PlateMID = UMaterialInstanceDynamic::Create(Armor, this);
	PlateMID->SetVectorParameterValue(TEXT("Tint"), HullTint * 2.0f + FLinearColor(0.025f, 0.025f, 0.03f));
	PlateMID->SetScalarParameterValue(TEXT("Metallic"), 0.8f);
	PlateMID->SetScalarParameterValue(TEXT("Wear"), 0.7f);
	auto Mesh = [](const TCHAR* N) { return LoadObject<UStaticMesh>(nullptr, *FString::Printf(TEXT("/Game/Armor/%s.%s"), N, N)); };
	const FQuat Q = GetActorQuat();
	const FVector Fw = Q.GetForwardVector(), Rt = Q.GetRightVector(), Up = FVector::UpVector;
	auto Bone = [&](const TCHAR* B) { return RigMesh->GetBoneLocation(FName(B), EBoneSpaces::WorldSpace); };
	auto Add = [&](const TCHAR* MeshName, const TCHAR* AttachBone, iv::Zone Z, const FVector& Pos, const FVector& Axis, const FVector& Out, const FVector& Scale)
	{
		UStaticMesh* M = Mesh(MeshName);
		if (!M || RigMesh->GetBoneIndex(FName(AttachBone)) == INDEX_NONE) return;
		UStaticMeshComponent* C = NewObject<UStaticMeshComponent>(this);
		C->SetStaticMesh(M);
		C->SetMaterial(0, PlateMID);
		C->SetCollisionEnabled(ECollisionEnabled::NoCollision);
		C->SetCastShadow(true);
		C->RegisterComponent();
		C->SetWorldTransform(FTransform(FRotationMatrix::MakeFromZX(Axis.GetSafeNormal(), Out).ToQuat(), Pos, Scale));
		C->AttachToComponent(RigMesh, FAttachmentTransformRules::KeepWorldTransform, FName(AttachBone));
		FIVPlate P;
		P.C = C; P.Z = Z; P.Size = Scale;
		Plates.Add(P);
	};
	// torso
	{
		const FVector Ctr = Bone(TEXT("torso")) + Fw * -250.f + Up * 780.f;
		Add(TEXT("Armor_Chest"), TEXT("torso"), iv::Zone::Torso, Ctr, Up, Fw, FVector(11.5f, 11.5f, 22.f));
		Add(TEXT("Armor_Back"), TEXT("reactor"), iv::Zone::Reactor, Ctr - Fw * 80.f, Up, Fw, FVector(11.5f, 11.5f, 21.f));
		Add(TEXT("Armor_Skirt"), TEXT("pelvis"), iv::Zone::Torso, Bone(TEXT("pelvis")) + Fw * -100.f - Up * 250.f, Up, Fw, FVector(19.f, 19.f, 9.f));
		Add(TEXT("Armor_Head"), TEXT("head"), iv::Zone::Head, Bone(TEXT("head")) + Up * 220.f, Up, Fw, FVector(8.f, 8.f, 8.f));
	}
	for (int32 sd = -1; sd <= 1; sd += 2)
	{
		const bool L = sd < 0;
		const FVector Side = Rt * float(sd);
		const iv::Zone ZS = L ? iv::Zone::ShoulderL : iv::Zone::ShoulderR, ZA = L ? iv::Zone::ArmL : iv::Zone::ArmR, ZL = L ? iv::Zone::LegL : iv::Zone::LegR;
		const TCHAR* BSh = L ? TEXT("shoulder_l") : TEXT("shoulder_r");
		const TCHAR* BUa = L ? TEXT("upperarm_l") : TEXT("upperarm_r");
		const TCHAR* BFa = L ? TEXT("forearm_l") : TEXT("forearm_r");
		const TCHAR* BHa = L ? TEXT("hand_l") : TEXT("hand_r");
		const TCHAR* BTh = L ? TEXT("thigh_l") : TEXT("thigh_r");
		const TCHAR* BSn = L ? TEXT("shin_l") : TEXT("shin_r");
		const TCHAR* BFt = L ? TEXT("foot_l") : TEXT("foot_r");
		// pauldron on top of the shoulder, facing out and forward
		Add(TEXT("Armor_Pauldron"), BSh, ZS, Bone(BSh) + Side * 380.f + Up * 260.f, (Up + Side * 0.9f).GetSafeNormal(), Fw, FVector(12.f, 12.f, 11.f));
		// guards follow the real limb axis
		auto Guard = [&](const TCHAR* MeshName, const TCHAR* A, const TCHAR* B, iv::Zone Z, float RadiusCm, float R0, const FVector& OutBias, float LenScale)
		{
			const FVector PA = Bone(A), PB = Bone(B);
			const float Len = (PB - PA).Size();
			const FVector Ax = (PB - PA).GetSafeNormal();
			const FVector Out = (OutBias - Ax * FVector::DotProduct(OutBias, Ax)).GetSafeNormal();
			const float S = RadiusCm / R0;
			Add(MeshName, A, Z, (PA + PB) * 0.5f + Out * 60.f, Ax, Out, FVector(S, S, FMath::Max(Len * LenScale, 300.f) / 100.f));
		};
		Guard(TEXT("Armor_Bracer"), BUa, BFa, ZA, 560.f, 46.f, Fw * 0.7f + Side * 0.5f, 0.9f);
		Guard(TEXT("Armor_Bracer"), BFa, BHa, ZA, 470.f, 46.f, Fw * 0.8f + Side * 0.3f, 1.0f);
		Guard(TEXT("Armor_Thigh"), BTh, BSn, ZL, 650.f, 52.f, Fw, 0.95f);
		Guard(TEXT("Armor_Shin"), BSn, BFt, ZL, 560.f, 50.f, Fw, 1.0f);
		Add(TEXT("Armor_Cap"), BFa, ZA, Bone(BFa) + Fw * 140.f, Up, Fw + Side * 0.4f, FVector(8.f, 8.f, 8.f));
		Add(TEXT("Armor_Cap"), BSn, ZL, Bone(BSn) + Fw * 260.f, Up, Fw, FVector(10.f, 10.f, 10.f));
	}
	UE_LOG(LogTemp, Display, TEXT("IV plates: %d"), Plates.Num());
}
'''
# destruction: whole shell flies off
old = p[p.index("	for (FIVPlate& P : Plates)\n	{\n		if (P.bGone || P.Z != Z || !P.C) continue;"):p.index("	static UStaticMesh* Cube = []")]
new = '''	for (FIVPlate& P : Plates)
	{
		if (P.bGone || P.Z != Z || !P.C) continue;
		P.bGone = true;
		const FTransform Xf = P.C->GetComponentTransform();
		P.C->SetVisibility(false);
		FRandomStream R2(Index * 211 + int32(Z) * 29 + 3);
		if (AIVFXManager* FX = AIVFXManager::Get(GetWorld()))
		{
			const FVector Out = (Xf.GetLocation() - GetActorLocation() + FVector(0, 0, 900.f)).GetSafeNormal();
			FX->SpawnPiece(P.C->GetStaticMesh(), PlateMID, Xf, (Out + R2.VRand() * 0.35f) * R2.FRandRange(1600.f, 3200.f) + FVector(0, 0, 900.f), R2.VRand() * R2.FRandRange(1.f, 4.f), 0.9f);
			FX->SpawnSparks(Xf.GetLocation(), FVector::UpVector, 50, 5500.f);
		}
		IVAudio::Play3D(GetWorld(), TEXT("mech_armor_plate_tear"), Xf.GetLocation(), 1.f);
		return;
	}
'''
p = p.replace(old, new, 1)
wr("IVMechPawn.cpp", p, crlf)
print("shells patched")
