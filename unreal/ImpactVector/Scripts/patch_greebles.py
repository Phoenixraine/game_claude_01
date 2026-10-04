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
if "BuildGreebles" not in h:
    h = ins_after(h, "void BuildGrowths();", "void BuildGreebles();\nUPROPERTY() TArray<TObjectPtr<UStaticMeshComponent>> GreebleComps;\nUPROPERTY() TObjectPtr<UMaterialInstanceDynamic> GreebleMID;")
    wr("IVMechPawn.h", h, crlf)

c, crlf = rd("IVMechPawn.cpp")
if "void AIVMechPawn::BuildGreebles" not in c:
    c = ins_after(c, "if (bInfected && GrowthComps.Num() == 0) BuildGrowths();", "if (GreebleComps.Num() == 0 && !FParse::Param(FCommandLine::Get(), TEXT(\"IVNoGreeble\"))) BuildGreebles();")
    c += r'''

// ---------------------------------------------------------------------------------------------------------- hydraulics and hardware
void AIVMechPawn::BuildGreebles()
{
	if (!RigMesh) return;
	UStaticMesh* Cyl = LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Cylinder.Cylinder"));
	UStaticMesh* Cube = LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Cube.Cube"));
	UStaticMesh* Sph = LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Sphere.Sphere"));
	UMaterialInterface* Armor = LoadObject<UMaterialInterface>(nullptr, TEXT("/Game/Materials/M_MechArmor.M_MechArmor"));
	UMaterialInterface* Emi = LoadObject<UMaterialInterface>(nullptr, TEXT("/Game/Materials/M_Emissive.M_Emissive"));
	if (!Cyl || !Cube || !Sph || !Armor) return;
	UMaterialInstanceDynamic* Chrome = UMaterialInstanceDynamic::Create(Armor, this);
	Chrome->SetVectorParameterValue(TEXT("Tint"), FLinearColor(0.62f, 0.64f, 0.7f));
	Chrome->SetScalarParameterValue(TEXT("Metallic"), 1.f);
	Chrome->SetScalarParameterValue(TEXT("Wear"), 0.2f);
	GreebleMID = Chrome;
	UMaterialInstanceDynamic* Lamp = nullptr;
	if (Emi)
	{
		Lamp = UMaterialInstanceDynamic::Create(Emi, this);
		Lamp->SetVectorParameterValue(TEXT("Color"), LampColor);
		Lamp->SetScalarParameterValue(TEXT("Intensity"), 22.f);
	}
	const FTransform ActorXf = GetActorTransform();
	const FVector TorsoC = RigMesh->GetBoneLocation(FName(TEXT("torso")), EBoneSpaces::WorldSpace);
	auto Attach = [&](UStaticMesh* M, UMaterialInterface* Mat, const FName& Bone, const FVector& Pos, const FQuat& Rot, const FVector& Scale)
	{
		UStaticMeshComponent* C = NewObject<UStaticMeshComponent>(this);
		C->SetStaticMesh(M);
		if (Mat) C->SetMaterial(0, Mat);
		C->SetCollisionEnabled(ECollisionEnabled::NoCollision);
		C->SetCastShadow(true);
		C->RegisterComponent();
		C->SetWorldTransform(FTransform(Rot, Pos, Scale));
		C->AttachToComponent(RigMesh, FAttachmentTransformRules::KeepWorldTransform, Bone);
		GreebleComps.Add(C);
	};
	struct FSeg { const TCHAR* A; const TCHAR* B; float Side; };
	static const FSeg Segs[] = {
		{ TEXT("upperarm_l"), TEXT("forearm_l"), -1.f }, { TEXT("forearm_l"), TEXT("hand_l"), -1.f }, { TEXT("upperarm_r"), TEXT("forearm_r"), 1.f }, { TEXT("forearm_r"), TEXT("hand_r"), 1.f },
		{ TEXT("thigh_l"), TEXT("shin_l"), -1.f }, { TEXT("shin_l"), TEXT("foot_l"), -1.f }, { TEXT("thigh_r"), TEXT("shin_r"), 1.f }, { TEXT("shin_r"), TEXT("foot_r"), 1.f } };
	for (const FSeg& S : Segs)
	{
		const int32 IA = RigMesh->GetBoneIndex(FName(S.A)), IB = RigMesh->GetBoneIndex(FName(S.B));
		if (IA == INDEX_NONE || IB == INDEX_NONE) continue;
		const FVector PA = RigMesh->GetBoneLocation(FName(S.A), EBoneSpaces::WorldSpace), PB = RigMesh->GetBoneLocation(FName(S.B), EBoneSpaces::WorldSpace);
		const FVector Axis = (PB - PA);
		const float Len = Axis.Size();
		if (Len < 200.f) continue;
		const FVector Ax = Axis / Len;
		// push the hydraulics out of the limb: away from the body centre line, a little forward
		FVector Out = (PA + PB) * 0.5f - TorsoC;
		Out -= Ax * FVector::DotProduct(Out, Ax);
		Out = (Out.GetSafeNormal() * 0.6f + ActorXf.GetRotation().GetForwardVector() * 0.5f + ActorXf.GetRotation().GetRightVector() * S.Side * 0.3f).GetSafeNormal();
		const float Off = FMath::Min(Len * 0.14f, 420.f);
		const FVector P0 = PA + Ax * Len * 0.12f + Out * Off, P1 = PB - Ax * Len * 0.1f + Out * Off * 0.8f;
		const FVector Mid = (P0 + P1) * 0.5f;
		const FVector D = (P1 - P0);
		const float L = D.Size();
		const FQuat Q = FRotationMatrix::MakeFromZ(D / L).ToQuat();
		const float R = FMath::Clamp(Len * 0.028f, 40.f, 110.f);
		Attach(Cyl, Chrome, FName(S.A), Mid, Q, FVector(R / 50.f, R / 50.f, L / 100.f));                         // outer cylinder
		Attach(Cyl, Chrome, FName(S.B), Mid + (D / L) * L * 0.3f, Q, FVector(R / 90.f, R / 90.f, L * 0.55f / 100.f));  // piston rod
		Attach(Sph, Chrome, FName(S.A), P0, Q, FVector(R / 38.f));                                                // pivots
		Attach(Sph, Chrome, FName(S.B), P1, Q, FVector(R / 38.f));
	}
	// back stacks and shoulder lamps
	if (RigMesh->GetBoneIndex(FName(TEXT("torso"))) != INDEX_NONE)
	{
		const FVector Back = -ActorXf.GetRotation().GetForwardVector(), Right = ActorXf.GetRotation().GetRightVector(), Up = FVector::UpVector;
		for (int32 s = -1; s <= 1; s += 2)
		{
			const FVector Base = TorsoC + Back * 650.f + Right * s * 520.f + Up * 700.f;
			Attach(Cyl, Chrome, FName(TEXT("torso")), Base + Up * 520.f, FQuat::Identity, FVector(1.5f, 1.5f, 11.f));
			if (Lamp) Attach(Cyl, Lamp, FName(TEXT("torso")), Base + Up * 1080.f, FQuat::Identity, FVector(1.3f, 1.3f, 0.3f));
			if (Lamp) Attach(Sph, Lamp, FName(TEXT("torso")), TorsoC + Right * s * 1300.f + Up * 1500.f + ActorXf.GetRotation().GetForwardVector() * 300.f, FQuat::Identity, FVector(1.1f));
			for (int32 k = 0; k < 3; ++k)   // vent grille
				Attach(Cube, Chrome, FName(TEXT("torso")), TorsoC + Back * 780.f + Right * s * 220.f + Up * (250.f + 130.f * k), FQuat::Identity, FVector(0.4f, 3.0f, 0.5f));
		}
	}
	UE_LOG(LogTemp, Display, TEXT("IV greebles: %d parts"), GreebleComps.Num());
}
'''
    wr("IVMechPawn.cpp", c, crlf)
print("greebles patched")
