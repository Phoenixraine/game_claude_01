// Decoration of the arena district: neon signs, LED strips, tower crowns, lantern strings and the point lights that make the fog glow.
#include "IVDistrict.h"
#include "IVBuilding.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Components/PointLightComponent.h"
#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"
#include "Math/RandomStream.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"

void AIVDistrict::Tick(float Dt)
{
	Super::Tick(Dt);
	NeonTime += Dt;
	for (FIVNeonLight& N : NeonLights)
	{
		if (!N.L || !N.L->IsVisible()) continue;
		float K = 1.f;
		if (N.Flicker == 1)
		{
			const float Ft = FMath::FloorToFloat(NeonTime * 7.f + N.Phase);
			const float H = FMath::Frac(FMath::Sin(Ft * 12.9898f + N.Phase * 78.233f) * 43758.5453f);
			K = (H > 0.82f) ? 0.15f : 1.f;
		}
		N.L->SetIntensity(N.Base * K);
	}
}

int32 AIVDistrict::FindBuildingAt(const FVector& P, float Pad) const
{
	for (int32 i = 0; i < Buildings.Num(); ++i)
	{
		const FIVDistrictBuilding& B = Buildings[i];
		const FVector L = FRotator(0, -B.YawDeg, 0).RotateVector(P - B.Center);
		if (FMath::Abs(L.X) <= B.Size.X * 0.5f + Pad && FMath::Abs(L.Y) <= B.Size.Y * 0.5f + Pad && FMath::Abs(L.Z) <= B.Size.Z * 0.5f + Pad) return i;
	}
	return -1;
}

void AIVDistrict::RebuildDecoOne(UInstancedStaticMeshComponent* C, const TArray<FIVDeco>& L, int32 NumCD)
{
	C->ClearInstances();
	TArray<FTransform> Tr;
	TArray<const FIVDeco*> Keep;
	for (const FIVDeco& D : L)
	{
		if (D.Bld >= 0 && Buildings.IsValidIndex(D.Bld) && Buildings[D.Bld].bActive) continue;
		Tr.Add(D.T);
		Keep.Add(&D);
	}
	if (Tr.Num() == 0) return;
	C->AddInstances(Tr, false, true);
	for (int32 i = 0; i < Keep.Num(); ++i) C->SetCustomData(i, MakeArrayView(Keep[i]->CD, NumCD), false);
	C->MarkRenderStateDirty();
}

void AIVDistrict::RebuildDeco()
{
	RebuildDecoOne(Signs, DecoSigns, 10);
	RebuildDecoOne(TrimBox, DecoTrimBox, 5);
	RebuildDecoOne(TrimBall, DecoTrimBall, 5);
	RebuildDecoOne(ConcCyl, DecoCyl, 4);
	RebuildDecoOne(ExtraGlass, DecoGlass, 4);
	RebuildDecoOne(ExtraConc, DecoConc, 4);
	for (FIVNeonLight& N : NeonLights)
	{
		if (N.Bld >= 0 && Buildings.IsValidIndex(N.Bld) && Buildings[N.Bld].bActive && N.L) N.L->SetVisibility(false);
	}
}

void AIVDistrict::ApplyDrawDistance(float Cm)
{
	UInstancedStaticMeshComponent* Comps[] = { Concrete, Glass, Hero, Cars, TreeTrunks, TreeCrowns, Lamps, Glow, Cones, Containers, Chimneys, Signs, TrimBox, TrimBall, ConcCyl, ExtraGlass, ExtraConc };
	for (UInstancedStaticMeshComponent* I : Comps)
		if (I) { I->SetCullDistances(int32(Cm * 0.85f), int32(Cm)); I->bUseAsOccluder = false; }
	for (FIVNeonLight& L : NeonLights) if (L.L) { L.L->MaxDrawDistance = Cm * 0.9f; L.L->MaxDistanceFadeRange = Cm * 0.2f; }
}

void AIVDistrict::SetNeonScale(float Scale)
{
	for (FIVNeonLight& L : NeonLights) if (L.L) L.L->SetIntensity(L.Base * Scale);
	if (Signs) if (UMaterialInstanceDynamic* M = Cast<UMaterialInstanceDynamic>(Signs->GetMaterial(0))) M->SetScalarParameterValue(TEXT("Gain"), Scale);
}

void AIVDistrict::SetLightBudget(int32 N)
{
	MaxNeonLights = N;
	int32 On = 0;
	for (FIVNeonLight& L : NeonLights)
	{
		if (!L.L) continue;
		const bool bAlive = !(L.Bld >= 0 && Buildings.IsValidIndex(L.Bld) && Buildings[L.Bld].bActive);
		L.L->SetVisibility(bAlive && On++ < N);
	}
}

void AIVDistrict::DecorateBuilding(int32 Bi, const FString& Crown, FRandomStream& R)
{
	const FIVDistrictBuilding& B = Buildings[Bi];
	const float Hh = B.Size.Z;
	const float Yaw = B.YawDeg;
	const FRotator Rot(0, Yaw, 0);
	auto LocalToWorld = [&](const FVector& L) { return B.Center + Rot.RotateVector(L); };
	auto Pal = [&]() -> FLinearColor
	{
		static const FLinearColor P[] = { FLinearColor(1, 0.08f, 0.55f), FLinearColor(0.05f, 0.85f, 1), FLinearColor(1, 0.45f, 0.05f), FLinearColor(0.55f, 0.15f, 1), FLinearColor(0.1f, 1, 0.45f), FLinearColor(1, 0.85f, 0.2f) };
		return P[R.RandRange(0, 5)];
	};
	auto Trim = [&](const FVector& LocalCenter, const FVector& SizeCm, const FLinearColor& Col, float I, float Blink)
	{
		FIVDeco D; D.Bld = Bi;
		D.T = FTransform(FRotator(0, Yaw, 0), LocalToWorld(LocalCenter), SizeCm / 100.f);
		D.CD[0] = Col.R; D.CD[1] = Col.G; D.CD[2] = Col.B; D.CD[3] = I; D.CD[4] = Blink;
		DecoTrimBox.Add(D);
	};
	auto Ball = [&](const FVector& LocalCenter, float RadiusCm, const FLinearColor& Col, float I, float Blink)
	{
		FIVDeco D; D.Bld = Bi;
		D.T = FTransform(FRotator::ZeroRotator, LocalToWorld(LocalCenter), FVector(RadiusCm / 50.f));
		D.CD[0] = Col.R; D.CD[1] = Col.G; D.CD[2] = Col.B; D.CD[3] = I; D.CD[4] = Blink;
		DecoTrimBall.Add(D);
	};
	auto GlassBox = [&](const FVector& LocalCenter, const FVector& SizeCm, float Pitch)
	{
		FIVDeco D; D.Bld = Bi;
		D.T = FTransform(FRotator(Pitch, Yaw, 0), LocalToWorld(LocalCenter), SizeCm / 100.f);
		D.CD[0] = B.Tint.R; D.CD[1] = B.Tint.G; D.CD[2] = B.Tint.B; D.CD[3] = B.Seed + 0.17f;
		DecoGlass.Add(D);
	};
	auto ConcBox = [&](const FVector& LocalCenter, const FVector& SizeCm)
	{
		FIVDeco D; D.Bld = Bi;
		D.T = FTransform(FRotator(0, Yaw, 0), LocalToWorld(LocalCenter), SizeCm / 100.f);
		D.CD[0] = 0.07f; D.CD[1] = 0.075f; D.CD[2] = 0.085f; D.CD[3] = B.Seed;
		DecoConc.Add(D);
	};
	auto Cyl = [&](const FVector& LocalCenter, float RadiusCm, float HeightCm)
	{
		FIVDeco D; D.Bld = Bi;
		D.T = FTransform(FRotator::ZeroRotator, LocalToWorld(LocalCenter), FVector(RadiusCm / 50.f, RadiusCm / 50.f, HeightCm / 100.f));
		D.CD[0] = 0.06f; D.CD[1] = 0.065f; D.CD[2] = 0.07f; D.CD[3] = B.Seed;
		DecoCyl.Add(D);
	};
	const float SX = B.Size.X, SY = B.Size.Y;
	const float TopL = Hh * 0.5f;                 // local z of the roof
	const FLinearColor Acc = Pal();
	const FLinearColor Acc2 = Pal();
	const FLinearColor Beacon(1.f, 0.04f, 0.03f);

	if (B.StyleId == 2)
	{
		// shopfront: LED roof line, a lit fascia band and a dark awning on the street side (UE Y = 0 is the street axis)
		Trim(FVector(0, 0, TopL + 12), FVector(SX + 10, SY + 10, 24), Acc, 5.f, 0.f);
		const float Dir = (B.Center.Y > 0.f) ? -1.f : 1.f;
		const float C = FMath::Abs(FMath::Cos(FMath::DegreesToRadians(Yaw))), S = FMath::Abs(FMath::Sin(FMath::DegreesToRadians(Yaw)));
		const float HalfY = C * SY * 0.5f + S * SX * 0.5f;
		const float HalfX = C * SX * 0.5f + S * SY * 0.5f;
		FIVDeco Band; Band.Bld = Bi;
		Band.T = FTransform(FRotator::ZeroRotator, FVector(B.Center.X, B.Center.Y + Dir * (HalfY + 6.f), B.Center.Z - Hh * 0.5f + 360.f), FVector(HalfX * 2.f * 0.94f / 100.f, 0.14f, 0.45f));
		Band.CD[0] = Acc2.R; Band.CD[1] = Acc2.G; Band.CD[2] = Acc2.B; Band.CD[3] = 4.5f; Band.CD[4] = 0.f;
		DecoTrimBox.Add(Band);
		FIVDeco Aw; Aw.Bld = Bi;
		Aw.T = FTransform(FRotator(0, 0, Dir * 10.f), FVector(B.Center.X, B.Center.Y + Dir * (HalfY + 90.f), B.Center.Z - Hh * 0.5f + 330.f), FVector(HalfX * 2.f * 0.9f / 100.f, 1.8f, 0.08f));
		Aw.CD[0] = Acc.R * 0.25f; Aw.CD[1] = Acc.G * 0.25f; Aw.CD[2] = Acc.B * 0.25f; Aw.CD[3] = B.Seed;
		DecoConc.Add(Aw);
		return;
	}

	// corner LED strips and ring lights (tall towers only)
	if (B.StyleId == 1 && Hh > 6000.f)
	{
		const int32 Strips = R.RandRange(1, 3);
		for (int32 i = 0; i < Strips; ++i)
		{
			const float sx = (R.FRand() < 0.5f) ? -1.f : 1.f, sy = (R.FRand() < 0.5f) ? -1.f : 1.f;
			Trim(FVector(sx * (SX * 0.5f + 14.f), sy * (SY * 0.5f + 14.f), 0), FVector(36, 36, Hh * 0.97f), (i == 0) ? Acc : Acc2, 6.5f, 0.f);
		}
		const int32 Rings = R.RandRange(1, 3);
		for (int32 r = 0; r < Rings; ++r)
		{
			const float z = (r == 0) ? TopL - 140.f : FMath::Lerp(-TopL * 0.2f, TopL * 0.8f, R.FRand());
			const FLinearColor Cc = (r == 0) ? Acc : Pal();
			Trim(FVector(0, SY * 0.5f + 12.f, z), FVector(SX + 24, 22, 70), Cc, 5.f, 0.f);
			Trim(FVector(0, -SY * 0.5f - 12.f, z), FVector(SX + 24, 22, 70), Cc, 5.f, 0.f);
			Trim(FVector(SX * 0.5f + 12.f, 0, z), FVector(22, SY + 24, 70), Cc, 5.f, 0.f);
			Trim(FVector(-SX * 0.5f - 12.f, 0, z), FVector(22, SY + 24, 70), Cc, 5.f, 0.f);
		}
	}

	const float Wmin = FMath::Min(SX, SY);
	if (Crown == TEXT("spire") && Hh > 9000.f)
	{
		const float SH = FMath::Min(8000.f, Hh * 0.28f);
		GlassBox(FVector(0, 0, TopL + 900), FVector(SX * 0.72f, SY * 0.72f, 1800), 0.f);
		GlassBox(FVector(0, 0, TopL + 1800 + 700), FVector(SX * 0.45f, SY * 0.45f, 1400), 0.f);
		Cyl(FVector(0, 0, TopL + 2500 + SH * 0.5f), 90.f, SH);
		Trim(FVector(0, 0, TopL + 2500 + SH * 0.62f), FVector(520, 520, 40), Acc, 8.f, 0.f);
		Trim(FVector(0, 0, TopL + 2500 + SH * 0.8f), FVector(360, 360, 40), Acc2, 8.f, 0.f);
		Ball(FVector(0, 0, TopL + 2500 + SH + 70), 110.f, Beacon, 14.f, 0.9f);
	}
	else if (Crown == TEXT("stepped"))
	{
		GlassBox(FVector(0, 0, TopL + 750), FVector(SX * 0.7f, SY * 0.7f, 1500), 0.f);
		Trim(FVector(0, 0, TopL + 40), FVector(SX * 0.7f + 30, SY * 0.7f + 30, 50), Acc, 6.f, 0.f);
		GlassBox(FVector(0, 0, TopL + 1500 + 550), FVector(SX * 0.42f, SY * 0.42f, 1100), 0.f);
		Trim(FVector(0, 0, TopL + 1500 + 20), FVector(SX * 0.42f + 30, SY * 0.42f + 30, 40), Acc2, 6.f, 0.f);
		Ball(FVector(0, 0, TopL + 2600 + 60), 90.f, Beacon, 14.f, 0.9f);
	}
	else if (Crown == TEXT("slanted"))
	{
		GlassBox(FVector(0, 0, TopL + 600), FVector(SX * 0.96f, SY * 0.96f, 1200), 0.f);
		GlassBox(FVector(SX * 0.12f, 0, TopL + 1200 + 300), FVector(SX * 0.7f, SY * 0.9f, 700), 14.f);
		Trim(FVector(0, 0, TopL + 20), FVector(SX + 30, SY + 30, 40), Acc, 5.f, 0.f);
		Ball(FVector(0, 0, TopL + 2300), 90.f, Beacon, 14.f, 0.9f);
	}
	else if (Crown == TEXT("halo"))
	{
		const float Hx = SX * 0.5f + 160.f, Hy = SY * 0.5f + 160.f, Hz = TopL + 900.f;
		Trim(FVector(0, Hy, Hz), FVector(SX + 320, 40, 40), Acc, 9.f, 0.f);
		Trim(FVector(0, -Hy, Hz), FVector(SX + 320, 40, 40), Acc, 9.f, 0.f);
		Trim(FVector(Hx, 0, Hz), FVector(40, SY + 320, 40), Acc, 9.f, 0.f);
		Trim(FVector(-Hx, 0, Hz), FVector(40, SY + 320, 40), Acc, 9.f, 0.f);
		for (int32 k = 0; k < 4; ++k) Trim(FVector((k & 1) ? Hx : -Hx, (k & 2) ? Hy : -Hy, TopL + 450), FVector(40, 40, 900), Acc2, 6.f, 0.f);
		Ball(FVector(0, 0, TopL + 300), 90.f, Beacon, 14.f, 0.9f);
	}
	else
	{
		ConcBox(FVector(R.FRandRange(-0.3f, 0.3f) * SX, R.FRandRange(-0.3f, 0.3f) * SY, TopL + 160), FVector(Wmin * 0.28f, Wmin * 0.22f, 320));
		ConcBox(FVector(R.FRandRange(-0.3f, 0.3f) * SX, R.FRandRange(-0.3f, 0.3f) * SY, TopL + 110), FVector(Wmin * 0.2f, Wmin * 0.3f, 220));
		Trim(FVector(0, 0, TopL + 14), FVector(SX + 20, SY + 20, 28), Acc, 4.f, 0.f);
		if (Crown == TEXT("antenna_cluster") && Hh > 5000.f)
		{
			const int32 N = R.RandRange(3, 5);
			float Tall = 0.f; FVector TallP = FVector::ZeroVector;
			for (int32 i = 0; i < N; ++i)
			{
				const float H = R.FRandRange(1500.f, 6000.f);
				const FVector P(R.FRandRange(-0.35f, 0.35f) * SX, R.FRandRange(-0.35f, 0.35f) * SY, TopL + H * 0.5f);
				Cyl(P, R.FRandRange(18.f, 40.f), H);
				if (H > Tall) { Tall = H; TallP = P + FVector(0, 0, H * 0.5f + 40.f); }
			}
			Ball(TallP, 70.f, Beacon, 14.f, 0.9f);
		}
		else if (Hh > 5000.f)
		{
			Ball(FVector(SX * 0.4f, SY * 0.4f, TopL + 60), 55.f, Beacon, 12.f, 0.7f);
		}
	}
}

void AIVDistrict::BuildDecor(const TSharedPtr<FJsonObject>& Rootj)
{
	FRandomStream R(7771);
	FParse::Value(FCommandLine::Get(), TEXT("-IVLights="), MaxNeonLights);
	if (FParse::Param(FCommandLine::Get(), TEXT("IVNoDeco"))) return;
	for (int32 i = 0; i < Buildings.Num(); ++i)
	{
		if (Buildings[i].bHero) continue;
		DecorateBuilding(i, Buildings[i].Crown, R);
	}
	if (Rootj->HasTypedField<EJson::Array>(TEXT("signs")))
	{
		for (const TSharedPtr<FJsonValue>& SV : Rootj->GetArrayField(TEXT("signs")))
		{
			const TSharedPtr<FJsonObject> S = SV->AsObject();
			const TArray<TSharedPtr<FJsonValue>>& P = S->GetArrayField(TEXT("pos"));
			const TArray<TSharedPtr<FJsonValue>>& Sz = S->GetArrayField(TEXT("size"));
			const TArray<TSharedPtr<FJsonValue>>& C1 = S->GetArrayField(TEXT("color"));
			const TArray<TSharedPtr<FJsonValue>>& C2 = S->GetArrayField(TEXT("color2"));
			const FString Style = S->GetStringField(TEXT("style"));
			const float W = Sz[0]->AsNumber(), H = Sz[1]->AsNumber();
			const float Depth = S->HasField(TEXT("depth")) ? S->GetNumberField(TEXT("depth")) : 0.6f;
			const float YawUe = YawToUE(float(S->GetNumberField(TEXT("yaw_deg"))));
			const FVector Pos = ToUE(P[0]->AsNumber(), P[1]->AsNumber(), P[2]->AsNumber());
			const FVector N = FRotator(0, YawUe, 0).Vector();
			FIVDeco D;
			D.Bld = FindBuildingAt(Pos - N * 120.f, 60.f);
			D.T = FTransform(FRotator(0, YawUe, 0), Pos + N * Depth * 50.f, FVector(Depth, W, H));
			D.CD[0] = C1[0]->AsNumber(); D.CD[1] = C1[1]->AsNumber(); D.CD[2] = C1[2]->AsNumber();
			D.CD[3] = C2[0]->AsNumber(); D.CD[4] = C2[1]->AsNumber(); D.CD[5] = C2[2]->AsNumber();
			const int32 StyleId = Style == TEXT("banner") ? 0 : (Style == TEXT("billboard") ? 1 : (Style == TEXT("strip") ? 2 : 3));
			D.CD[6] = StyleId + 10.f * int32(S->GetNumberField(TEXT("anim")));
			D.CD[7] = float(int32(S->GetNumberField(TEXT("seed"))) % 997) * 0.37f + 1.f;
			D.CD[8] = W / FMath::Max(H, 0.01f);
			D.CD[9] = YawUe;
			DecoSigns.Add(D);
		}
	}
	if (Rootj->HasTypedField<EJson::Array>(TEXT("strings")))
	{
		for (const TSharedPtr<FJsonValue>& SV : Rootj->GetArrayField(TEXT("strings")))
		{
			const TSharedPtr<FJsonObject> S = SV->AsObject();
			const TArray<TSharedPtr<FJsonValue>>& A = S->GetArrayField(TEXT("a"));
			const TArray<TSharedPtr<FJsonValue>>& Bq = S->GetArrayField(TEXT("b"));
			const TArray<TSharedPtr<FJsonValue>>& Co = S->GetArrayField(TEXT("color"));
			const FVector PA = ToUE(A[0]->AsNumber(), A[1]->AsNumber(), A[2]->AsNumber());
			const FVector PB = ToUE(Bq[0]->AsNumber(), Bq[1]->AsNumber(), Bq[2]->AsNumber());
			const int32 N = int32(S->GetNumberField(TEXT("beads")));
			const float Sag = S->GetNumberField(TEXT("sag")) * 100.f;
			for (int32 k = 0; k <= N; ++k)
			{
				const float t = float(k) / N;
				FVector P = FMath::Lerp(PA, PB, t);
				P.Z -= Sag * 4.f * t * (1.f - t);
				FIVDeco D;
				D.T = FTransform(FRotator::ZeroRotator, P, FVector(0.42f));
				D.CD[0] = Co[0]->AsNumber(); D.CD[1] = Co[1]->AsNumber(); D.CD[2] = Co[2]->AsNumber(); D.CD[3] = 7.f; D.CD[4] = 0.f;
				DecoTrimBall.Add(D);
			}
		}
	}
	if (Rootj->HasTypedField<EJson::Array>(TEXT("lights")))
	{
		struct FL { FVector Pos; FLinearColor Col; float I, Rad; int32 Fl; float Score; };
		TArray<FL> Ls;
		const FVector Focus = ToUE(0.0, 395.0, 0.0);
		for (const TSharedPtr<FJsonValue>& LV : Rootj->GetArrayField(TEXT("lights")))
		{
			const TSharedPtr<FJsonObject> O = LV->AsObject();
			const TArray<TSharedPtr<FJsonValue>>& P = O->GetArrayField(TEXT("pos"));
			const TArray<TSharedPtr<FJsonValue>>& C = O->GetArrayField(TEXT("color"));
			FL L;
			L.Pos = ToUE(P[0]->AsNumber(), P[1]->AsNumber(), P[2]->AsNumber());
			L.Col = FLinearColor(C[0]->AsNumber(), C[1]->AsNumber(), C[2]->AsNumber());
			L.I = O->GetNumberField(TEXT("intensity"));
			L.Rad = O->GetNumberField(TEXT("radius")) * 100.f;
			L.Fl = int32(O->GetNumberField(TEXT("flicker")));
			const float Pr = O->HasField(TEXT("prio")) ? O->GetNumberField(TEXT("prio")) : 10.f;
			L.Score = Pr / (1.f + FVector::Dist2D(L.Pos, Focus) / 12000.f);
			Ls.Add(L);
		}
		Ls.Sort([](const FL& A, const FL& B) { return A.Score > B.Score; });
		const int32 Cap = FMath::Min(Ls.Num(), 140);
		for (int32 i = 0; i < Cap; ++i)
		{
			const FL& L = Ls[i];
			UPointLightComponent* PL = NewObject<UPointLightComponent>(this);
			PL->SetMobility(EComponentMobility::Movable);
			PL->SetupAttachment(Root);
			PL->RegisterComponent();
			PL->SetWorldLocation(L.Pos);
			PL->SetLightColor(L.Col);
			PL->SetIntensityUnits(ELightUnits::Candelas);
			PL->SetIntensity(L.I * 450.f);
			PL->SetAttenuationRadius(L.Rad);
			PL->SetCastShadows(false);
			PL->SetVolumetricScatteringIntensity(2.5f);
			PL->SetSourceRadius(40.f);
			PL->SetVisibility(i < MaxNeonLights);
			FIVNeonLight N; N.L = PL; N.Bld = FindBuildingAt(L.Pos, 2400.f); N.Base = L.I * 450.f; N.Flicker = L.Fl; N.Phase = i * 1.7f;
			NeonLights.Add(N);
		}
	}
	RebuildDeco();
	UE_LOG(LogTemp, Display, TEXT("IV decor: %d signs, %d trim boxes, %d beads, %d glass pieces, %d lights"), DecoSigns.Num(), DecoTrimBox.Num(), DecoTrimBall.Num(), DecoGlass.Num(), NeonLights.Num());
}
