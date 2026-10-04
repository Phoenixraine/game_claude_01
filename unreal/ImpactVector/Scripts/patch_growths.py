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
if "BuildGrowths" not in h:
    h = ins_after(h, "bool bUseHullMaterial = true;", """/** Infected variant: mutations burst out of the armour (spikes, glowing tumours); they swell as the zone underneath is damaged. */
bool bInfected = false;""")
    h = ins_after(h, "UPROPERTY() TObjectPtr<UMaterialInstanceDynamic> HullMID;", """struct FIVGrowth { TObjectPtr<UStaticMeshComponent> C; iv::Zone Z = iv::Zone::Torso; FVector Full = FVector::OneVector; float Phase = 0.f, Cur = 0.f; bool bTumor = false; };
TArray<FIVGrowth> Growths;
UPROPERTY() TObjectPtr<UMaterialInstanceDynamic> GrowthMID;
UPROPERTY() TArray<TObjectPtr<UStaticMeshComponent>> GrowthComps;
void BuildGrowths();
void UpdateGrowths(float Dt);""")
    wr("IVMechPawn.h", h, crlf)

c, crlf = rd("IVMechPawn.cpp")
if "void AIVMechPawn::BuildGrowths" not in c:
    c = ins_after(c, "UpdateV5Fx(Dt);", "if (bInfected) UpdateGrowths(Dt);")
    c = ins_after(c, "RigMesh->SetBoundsScale(1.6f);", "if (bInfected && GrowthComps.Num() == 0) BuildGrowths();")
    c += r'''

// ---------------------------------------------------------------------------------------------------------- infection growths
void AIVMechPawn::BuildGrowths()
{
	if (!RigMesh) return;
	UStaticMesh* Cone = LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Cone.Cone"));
	UStaticMesh* Sph = LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Sphere.Sphere"));
	UMaterialInterface* GM = LoadObject<UMaterialInterface>(nullptr, TEXT("/Game/Materials/M_Growth.M_Growth"));
	if (!Cone || !Sph || !GM) return;
	GrowthMID = UMaterialInstanceDynamic::Create(GM, this);
	struct FSpec { const TCHAR* Bone; iv::Zone Z; int32 Spikes; int32 Tumors; FVector Radii; float Len; float Rad; FVector Bias; };
	static const FSpec Specs[] = {
		{ TEXT("torso"), iv::Zone::Torso, 11, 4, FVector(800, 1500, 1250), 1700.f, 230.f, FVector(-0.4f, 0.f, 0.8f) },
		{ TEXT("head"), iv::Zone::Head, 4, 0, FVector(250, 380, 380), 900.f, 130.f, FVector(-0.5f, 0.f, 1.f) },
		{ TEXT("reactor"), iv::Zone::Reactor, 0, 3, FVector(500, 600, 500), 0.f, 0.f, FVector(0.f, 0.f, 0.f) },
		{ TEXT("shoulder_l"), iv::Zone::ShoulderL, 3, 1, FVector(500, 650, 500), 1300.f, 190.f, FVector(0.f, -0.8f, 0.8f) },
		{ TEXT("shoulder_r"), iv::Zone::ShoulderR, 3, 1, FVector(500, 650, 500), 1300.f, 190.f, FVector(0.f, 0.8f, 0.8f) },
		{ TEXT("forearm_l"), iv::Zone::ArmL, 3, 0, FVector(350, 350, 350), 1000.f, 120.f, FVector(-0.3f, -0.6f, 0.6f) },
		{ TEXT("forearm_r"), iv::Zone::ArmR, 3, 0, FVector(350, 350, 350), 1000.f, 120.f, FVector(-0.3f, 0.6f, 0.6f) },
		{ TEXT("thigh_l"), iv::Zone::LegL, 2, 1, FVector(450, 450, 450), 1100.f, 150.f, FVector(-0.4f, -0.5f, 0.5f) },
		{ TEXT("thigh_r"), iv::Zone::LegR, 2, 1, FVector(450, 450, 450), 1100.f, 150.f, FVector(-0.4f, 0.5f, 0.5f) },
	};
	FRandomStream R(GetUniqueID() * 7 + 11);
	const FTransform ActorXf = GetActorTransform();
	for (const FSpec& S : Specs)
	{
		const int32 BI = RigMesh->GetBoneIndex(FName(S.Bone));
		if (BI == INDEX_NONE) continue;
		const FTransform BoneXf = RigMesh->GetBoneTransform(BI);
		auto Make = [&](UStaticMesh* M, const FVector& WorldPos, const FVector& WorldDir, const FVector& Scale, bool bTumor)
		{
			UStaticMeshComponent* C = NewObject<UStaticMeshComponent>(this);
			C->SetStaticMesh(M);
			C->SetMaterial(0, GrowthMID);
			C->SetCollisionEnabled(ECollisionEnabled::NoCollision);
			C->SetCastShadow(true);
			C->bAffectDynamicIndirectLighting = true;
			// built in world space, stored relative to the bone so it follows the animation
			const FTransform W(FRotationMatrix::MakeFromZ(WorldDir).ToQuat(), WorldPos, Scale);
			C->RegisterComponent();
			C->SetWorldTransform(W);
			C->AttachToComponent(RigMesh, FAttachmentTransformRules::KeepWorldTransform, FName(S.Bone));
			GrowthComps.Add(C);
			FIVGrowth G;
			G.C = C; G.Z = S.Z; G.Full = Scale; G.Phase = R.FRand() * 6.28f; G.bTumor = bTumor;
			Growths.Add(G);
		};
		const FVector Centre = BoneXf.GetLocation();
		auto Dir = [&](const FVector& Bias) -> FVector
		{
			for (int32 Try = 0; Try < 12; ++Try)
			{
				const FVector V = R.VRand();
				const FVector A = ActorXf.TransformVectorNoScale(FVector(V.X * S.Radii.X, V.Y * S.Radii.Y, V.Z * S.Radii.Z));
				const FVector Bw = ActorXf.TransformVectorNoScale(Bias);
				if (FVector::DotProduct(A.GetSafeNormal(), Bw.GetSafeNormal() + FVector(0.0001f)) > -0.2f || Bias.IsNearlyZero()) return V;
			}
			return R.VRand();
		};
		for (int32 i = 0; i < S.Spikes; ++i)
		{
			const FVector V = Dir(S.Bias);
			const FVector Local(V.X * S.Radii.X, V.Y * S.Radii.Y, V.Z * S.Radii.Z);
			const FVector Pos = Centre + ActorXf.TransformVectorNoScale(Local);
			FVector Out = (ActorXf.TransformVectorNoScale(Local)).GetSafeNormal();
			Out = (Out + ActorXf.TransformVectorNoScale(S.Bias) * 0.6f + R.VRand() * 0.2f).GetSafeNormal();
			const float L = S.Len * R.FRandRange(0.55f, 1.2f), Rd = S.Rad * R.FRandRange(0.7f, 1.2f);
			// the engine cone is 100 cm tall with the pivot in the middle: stand its base on the surface
			Make(Cone, Pos + Out * L * 0.42f, Out, FVector(Rd / 50.f, Rd / 50.f, L / 100.f), false);
		}
		for (int32 i = 0; i < S.Tumors; ++i)
		{
			const FVector V = Dir(S.Bias);
			const FVector Local(V.X * S.Radii.X * 0.9f, V.Y * S.Radii.Y * 0.9f, V.Z * S.Radii.Z * 0.9f);
			const FVector Pos = Centre + ActorXf.TransformVectorNoScale(Local);
			const float Rd = FMath::Max(S.Radii.GetMin() * R.FRandRange(0.35f, 0.6f), 150.f);
			Make(Sph, Pos, FVector::UpVector, FVector(Rd / 50.f), true);
		}
	}
	UE_LOG(LogTemp, Display, TEXT("IV infection: %d growths"), Growths.Num());
}

void AIVMechPawn::UpdateGrowths(float Dt)
{
	if (Growths.Num() == 0) { if (bRigActive && GrowthComps.Num() == 0) BuildGrowths(); return; }
	const float T = GetWorld()->GetTimeSeconds();
	float Worst = 0.f;
	for (int32 i = 0; i < iv::kZoneCount; ++i) Worst = FMath::Max(Worst, FMath::Clamp(float(int32(ZoneStates[i])) / 5.f, 0.f, 1.f));
	if (GrowthMID)
	{
		GrowthMID->SetScalarParameterValue(TEXT("Pulse"), FMath::Clamp(0.45f + 0.9f * Worst, 0.f, 1.6f));
		GrowthMID->SetScalarParameterValue(TEXT("Hue"), FMath::Clamp(0.25f + 0.6f * Worst, 0.f, 1.f));
	}
	for (FIVGrowth& G : Growths)
	{
		if (!G.C) continue;
		const float Dmg = FMath::Clamp(float(int32(ZoneStates[iv::Index(G.Z)])) / 5.f, 0.f, 1.f);
		const bool bGone = ZoneStates[iv::Index(G.Z)] >= iv::ZoneState::Severed;
		const float Want = bGone ? 0.f : (0.45f + 0.75f * Dmg) * (1.f + (G.bTumor ? 0.12f * FMath::Sin(T * 3.1f + G.Phase) : 0.f));
		G.Cur = FMath::FInterpTo(G.Cur, Want, Dt, 3.f);
		G.C->SetRelativeScale3D(G.Full * G.Cur);
		G.C->SetVisibility(G.Cur > 0.03f);
	}
}
'''
    wr("IVMechPawn.cpp", c, crlf)
print("growth patched")
