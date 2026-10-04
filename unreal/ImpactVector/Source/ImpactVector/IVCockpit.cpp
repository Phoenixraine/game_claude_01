#include "IVCockpit.h"
#include "IVAudio.h"
#include "Components/StaticMeshComponent.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Components/PointLightComponent.h"
#include "ProceduralMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "Engine/Engine.h"
#include "Engine/Font.h"
#include "Engine/Canvas.h"
#include "Engine/TextureRenderTarget2D.h"
#include "Kismet/KismetRenderingLibrary.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "CanvasItem.h"
#include "RenderUtils.h"
#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"

namespace
{
	// Blender (x forward, y left, z up, metres) -> cockpit space (cm, y right)
	FVector B2U(const TArray<TSharedPtr<FJsonValue>>& A) { return FVector(A[0]->AsNumber() * 100.0, -A[1]->AsNumber() * 100.0, A[2]->AsNumber() * 100.0); }
	FVector Vec3(const TSharedPtr<FJsonObject>& O, const TCHAR* K) { return B2U(O->GetArrayField(K)); }

	UStaticMesh* LoadSM(const TCHAR* Path) { return LoadObject<UStaticMesh>(nullptr, Path); }

	FVector2D Uv0(const FVector& Cm) { const FVector B(Cm.X / 100.f, -Cm.Y / 100.f, Cm.Z / 100.f); return FVector2D(B.X * 0.5f + 0.5f, 0.5f - B.Y * 0.5f); }
	FVector2D Uv1(const FVector& Cm, float Cls) { return FVector2D(Cm.Z / 100.f * 0.5f + 0.5f, 1.f - Cls); }

	FVector CatmullRom(const FVector& P0, const FVector& P1, const FVector& P2, const FVector& P3, float T)
	{
		const float T2 = T * T, T3 = T2 * T;
		return 0.5f * ((2.f * P1) + (-P0 + P2) * T + (2.f * P0 - 5.f * P1 + 4.f * P2 - P3) * T2 + (-P0 + 3.f * P1 - 3.f * P2 + P3) * T3);
	}

	struct FTubeMesh
	{
		TArray<FVector> V, N;
		TArray<FVector2D> UV0, UV1;
		TArray<int32> Tri;
	};

	/** Tube along Path[From..To] (inclusive) with radius R; Cls via UV1; optional end cap. */
	void AppendTube(FTubeMesh& M, const TArray<FVector>& Path, int32 From, int32 To, float R, float Cls, bool bCapStart, bool bCapEnd, float RaggedA = 0.f, float RaggedB = 0.f, FRandomStream* Rng = nullptr)
	{
		const int32 Sides = 8;
		if (To - From < 1) return;
		FVector Tn = (Path[From + 1] - Path[From]).GetSafeNormal();
		FVector Nrm = FVector::CrossProduct(Tn, FMath::Abs(Tn.Z) < 0.9f ? FVector::UpVector : FVector::RightVector).GetSafeNormal();
		const int32 Base0 = M.V.Num();
		const int32 Tri0 = M.Tri.Num();
		for (int32 i = From; i <= To; ++i)
		{
			const FVector Prev = Path[FMath::Max(i - 1, From)], Next = Path[FMath::Min(i + 1, To)];
			Tn = (Next - Prev).GetSafeNormal();
			Nrm = (Nrm - Tn * FVector::DotProduct(Nrm, Tn)).GetSafeNormal();
			const FVector Bn = FVector::CrossProduct(Tn, Nrm);
			const bool bFirst = (i == From), bLast = (i == To);
			for (int32 s = 0; s < Sides; ++s)
			{
				const float A = 2.f * PI * s / Sides;
				float Rr = R;
				FVector Off = FVector::ZeroVector;
				if (Rng && bFirst && RaggedA > 0.f) { Rr *= 1.f + Rng->FRandRange(-0.25f, 0.55f); Off = Tn * Rng->FRandRange(0.f, RaggedA) * (s % 2 ? 1.f : 0.35f); }
				if (Rng && bLast && RaggedB > 0.f) { Rr *= 1.f + Rng->FRandRange(-0.25f, 0.55f); Off = -Tn * Rng->FRandRange(0.f, RaggedB) * (s % 2 ? 1.f : 0.35f); }
				const FVector Dir = Nrm * FMath::Cos(A) + Bn * FMath::Sin(A);
				const FVector P = Path[i] + Dir * Rr + Off;
				M.V.Add(P);
				M.N.Add(Dir);
				M.UV0.Add(Uv0(P));
				M.UV1.Add(Uv1(P, ((bFirst && RaggedA > 0.f) || (bLast && RaggedB > 0.f)) ? 5.f : Cls));
			}
		}
		const int32 Rings = To - From + 1;
		for (int32 r = 0; r + 1 < Rings; ++r)
		{
			for (int32 s = 0; s < Sides; ++s)
			{
				const int32 a = Base0 + r * Sides + s, b = Base0 + r * Sides + (s + 1) % Sides, c = a + Sides, d = b + Sides;
				M.Tri.Add(a); M.Tri.Add(c); M.Tri.Add(b);
				M.Tri.Add(b); M.Tri.Add(c); M.Tri.Add(d);
			}
		}
		auto Cap = [&](int32 RingIdx, const FVector& Out)
		{
			const int32 Cn = M.V.Num();
			FVector Ctr = FVector::ZeroVector;
			for (int32 s = 0; s < Sides; ++s) Ctr += M.V[Base0 + RingIdx * Sides + s];
			Ctr /= Sides;
			M.V.Add(Ctr); M.N.Add(Out); M.UV0.Add(Uv0(Ctr)); M.UV1.Add(Uv1(Ctr, 0.f));
			for (int32 s = 0; s < Sides; ++s)
			{
				const int32 s1 = (s + 1) % Sides;
				const FVector Va = M.V[Base0 + RingIdx * Sides + s], Vb = M.V[Base0 + RingIdx * Sides + s1];
				const FVector2D Ua = M.UV0[Base0 + RingIdx * Sides + s], Ub = M.UV0[Base0 + RingIdx * Sides + s1];
				const float Za = M.UV1[Base0 + RingIdx * Sides + s].X, Zb = M.UV1[Base0 + RingIdx * Sides + s1].X;
				const int32 a = M.V.Num();
				M.V.Add(Va); M.N.Add(Out); M.UV0.Add(Ua); M.UV1.Add(FVector2D(Za, 1.f));
				const int32 b = M.V.Num();
				M.V.Add(Vb); M.N.Add(Out); M.UV0.Add(Ub); M.UV1.Add(FVector2D(Zb, 1.f));
				if (FVector::DotProduct(FVector::CrossProduct(Vb - Ctr, Va - Ctr), Out) > 0.f) { M.Tri.Add(Cn); M.Tri.Add(a); M.Tri.Add(b); }
				else { M.Tri.Add(Cn); M.Tri.Add(b); M.Tri.Add(a); }
			}
		};
		if (bCapStart) Cap(0, -(Path[From + 1] - Path[From]).GetSafeNormal());
		if (bCapEnd) Cap(Rings - 1, (Path[To] - Path[To - 1]).GetSafeNormal());
		// Unreal's front face is the one whose (v1-v0)x(v2-v0) points away from the viewer: make every triangle agree with its vertex normals
		for (int32 t = Tri0; t + 2 < M.Tri.Num(); t += 3)
		{
			const FVector Cr = FVector::CrossProduct(M.V[M.Tri[t + 1]] - M.V[M.Tri[t]], M.V[M.Tri[t + 2]] - M.V[M.Tri[t]]);
			const FVector Nn = M.N[M.Tri[t]] + M.N[M.Tri[t + 1]] + M.N[M.Tri[t + 2]];
			if (FVector::DotProduct(Cr, Nn) > 0.f) Swap(M.Tri[t + 1], M.Tri[t + 2]);
		}
	}

	// ---- canvas helpers (monitor drawing)
	void FillR(FCanvas* C, float X, float Y, float W, float H, const FLinearColor& Col)
	{
		FCanvasTileItem T(FVector2D(X, Y), GWhiteTexture, FVector2D(W, H), Col);
		T.BlendMode = SE_BLEND_Translucent;
		C->DrawItem(T);
	}
	void Ln(FCanvas* C, float X0, float Y0, float X1, float Y1, const FLinearColor& Col, float Th = 1.5f)
	{
		FCanvasLineItem L(FVector2D(X0, Y0), FVector2D(X1, Y1));
		L.SetColor(Col);
		L.LineThickness = Th;
		L.BlendMode = SE_BLEND_Translucent;
		C->DrawItem(L);
	}
	void Frame(FCanvas* C, float X, float Y, float W, float H, const FLinearColor& Col, float Th = 1.5f)
	{
		Ln(C, X, Y, X + W, Y, Col, Th); Ln(C, X, Y + H, X + W, Y + H, Col, Th); Ln(C, X, Y, X, Y + H, Col, Th); Ln(C, X + W, Y, X + W, Y + H, Col, Th);
	}
	void Txt(FCanvas* C, const FString& S, float X, float Y, const FLinearColor& Col, float Scale = 1.f, int32 Align = 0)
	{
		UFont* F = GEngine->GetSmallFont();
		int32 Wi = 0, Hi = 0;
		F->GetStringHeightAndWidth(S, Hi, Wi);
		const float W = Wi * Scale;
		const float X0 = Align == 1 ? X - W * 0.5f : (Align == 2 ? X - W : X);
		FCanvasTextItem T(FVector2D(X0, Y), FText::FromString(S), F, Col);
		T.Scale = FVector2D(Scale, Scale);
		T.BlendMode = SE_BLEND_Translucent;
		C->DrawItem(T);
	}
	void Circle(FCanvas* C, float Cx, float Cy, float R, const FLinearColor& Col, float Th = 1.5f, int32 N = 40, float A0 = 0.f, float A1 = 2.f * PI)
	{
		for (int32 i = 0; i < N; ++i)
		{
			const float a = FMath::Lerp(A0, A1, float(i) / N), b = FMath::Lerp(A0, A1, float(i + 1) / N);
			Ln(C, Cx + FMath::Cos(a) * R, Cy + FMath::Sin(a) * R, Cx + FMath::Cos(b) * R, Cy + FMath::Sin(b) * R, Col, Th);
		}
	}
	FLinearColor Al(FLinearColor C, float A) { C.A = A; return C; }

	const FLinearColor kCy(0.2f, 0.9f, 1.f), kOr(1.f, 0.55f, 0.15f), kRd(1.f, 0.2f, 0.12f), kGn(0.35f, 1.f, 0.5f), kYe(1.f, 0.9f, 0.3f), kWh(0.9f, 0.96f, 1.f);
	const FLinearColor kState[7] = {
		FLinearColor(0.3f, 0.9f, 1.f), FLinearColor(0.55f, 0.95f, 0.75f), FLinearColor(1.f, 0.9f, 0.3f), FLinearColor(1.f, 0.55f, 0.12f),
		FLinearColor(1.f, 0.18f, 0.1f), FLinearColor(0.35f, 0.05f, 0.04f), FLinearColor(0.12f, 0.02f, 0.02f) };

	void Schematic(FCanvas* C, float X, float Y, float S, const float* Armor, const uint8* State, bool bFront, float Time)
	{
		struct R { int32 Z; float x, y, w, h; };
		static const R Parts[] = {
			{ 0, -0.24f, 0.00f, 0.48f, 0.42f }, { 1, -0.52f, 0.46f, 1.04f, 0.78f }, { 2, -0.18f, 0.62f, 0.36f, 0.30f },
			{ 3, -1.00f, 0.46f, 0.44f, 0.34f }, { 4, 0.56f, 0.46f, 0.44f, 0.34f }, { 5, -1.02f, 0.84f, 0.38f, 0.92f }, { 6, 0.64f, 0.84f, 0.38f, 0.92f },
			{ 7, -0.50f, 1.30f, 0.44f, 1.05f }, { 8, 0.06f, 1.30f, 0.44f, 1.05f } };
		for (const R& P : Parts)
		{
			float x = P.x;
			if (bFront) x = -(P.x + P.w);
			const int32 St = FMath::Clamp<int32>(State[P.Z], 0, 6);
			FLinearColor Col = kState[St];
			const float Pulse = (St >= 4 && St < 5) ? 0.55f + 0.45f * FMath::Sin(Time * 9.f) : 1.f;
			const float x0 = X + x * S, y0 = Y + P.y * S, w = P.w * S, h = P.h * S;
			FillR(C, x0, y0, w, h, Al(Col, 0.22f * Pulse));
			FillR(C, x0, y0 + h * (1.f - Armor[P.Z]), w, h * Armor[P.Z], Al(Col, 0.34f * Pulse));
			Frame(C, x0, y0, w, h, Al(Col, 0.95f * Pulse), 2.f);
			Ln(C, x0, y0 + h * 0.5f, x0 + w, y0 + h * 0.5f, Al(Col, 0.25f), 1.f);
			if (St == 6) { Ln(C, x0, y0, x0 + w, y0 + h, kRd, 2.5f); Ln(C, x0 + w, y0, x0, y0 + h, kRd, 2.5f); }
			if (w > 22.f) Txt(C, FString::Printf(TEXT("%d"), int32(Armor[P.Z] * 100.f)), x0 + w * 0.5f, y0 + h * 0.5f - 4.f, Al(kWh, 0.85f), 0.7f, 1);
		}
	}
}

// =====================================================================================================================
UIVCockpitComponent::UIVCockpitComponent()
{
	PrimaryComponentTick.bCanEverTick = true;
	PrimaryComponentTick.TickGroup = TG_PostUpdateWork;
	Rng.Initialize(4242);
}

bool UIVCockpitComponent::LoadLayout()
{
	FString Text;
	if (!FFileHelper::LoadFileToString(Text, *(FPaths::ProjectContentDir() / TEXT("Data/cockpit_layout.json")))) return false;
	TSharedPtr<FJsonObject> Rootj;
	if (!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text), Rootj) || !Rootj.IsValid()) return false;

	for (const TSharedPtr<FJsonValue>& V : Rootj->GetArrayField(TEXT("pipes")))
	{
		const TSharedPtr<FJsonObject> O = V->AsObject();
		FIVCockpitPipe P;
		P.Id = O->GetStringField(TEXT("id"));
		for (const TSharedPtr<FJsonValue>& Pt : O->GetArrayField(TEXT("pts"))) P.Ctrl.Add(B2U(Pt->AsArray()));
		P.R = O->GetNumberField(TEXT("r")) * 100.f;
		P.Cls = int32(O->GetNumberField(TEXT("cls")));
		P.Steam = O->GetNumberField(TEXT("steam"));
		P.bBreakable = O->GetBoolField(TEXT("breakable"));
		if (P.Ctrl.Num() >= 2) Pipes.Add(MoveTemp(P));
	}
	for (const TSharedPtr<FJsonValue>& V : Rootj->GetArrayField(TEXT("wires")))
	{
		const TSharedPtr<FJsonObject> O = V->AsObject();
		FIVCockpitWire W;
		W.Anchor = Vec3(O, TEXT("a"));
		const TArray<TSharedPtr<FJsonValue>>& D = O->GetArrayField(TEXT("d"));
		W.Dir = FVector(D[0]->AsNumber(), -D[1]->AsNumber(), D[2]->AsNumber()).GetSafeNormal();
		const float Len = O->GetNumberField(TEXT("len")) * 100.f;
		W.SegLen = Len / 7.f;
		W.R = O->GetNumberField(TEXT("r")) * 100.f;
		const FString Cn = O->GetStringField(TEXT("color"));
		W.Col = Cn == TEXT("orange") ? FLinearColor(0.9f, 0.3f, 0.03f) : (Cn == TEXT("red") ? FLinearColor(0.7f, 0.03f, 0.03f) : (Cn == TEXT("blue") ? FLinearColor(0.05f, 0.18f, 0.6f) : (Cn == TEXT("grey") ? FLinearColor(0.22f, 0.22f, 0.24f) : FLinearColor(0.012f, 0.012f, 0.014f))));
		W.bStick = O->GetStringField(TEXT("kind")) == TEXT("stick");
		Wires.Add(MoveTemp(W));
	}
	for (const TSharedPtr<FJsonValue>& V : Rootj->GetArrayField(TEXT("monitors")))
	{
		const TSharedPtr<FJsonObject> O = V->AsObject();
		FIVCockpitMonitor M;
		M.Id = O->GetStringField(TEXT("id"));
		M.C = Vec3(O, TEXT("c"));
		auto Dir = [&](const TCHAR* K) { const TArray<TSharedPtr<FJsonValue>>& A = O->GetArrayField(K); return FVector(A[0]->AsNumber(), -A[1]->AsNumber(), A[2]->AsNumber()).GetSafeNormal(); };
		M.Right = Dir(TEXT("right")); M.Up = Dir(TEXT("up")); M.N = Dir(TEXT("n"));
		M.W = O->GetNumberField(TEXT("w")) * 100.f; M.H = O->GetNumberField(TEXT("h")) * 100.f;
		Monitors.Add(MoveTemp(M));
	}
	for (const TSharedPtr<FJsonValue>& V : Rootj->GetArrayField(TEXT("sockets")))
	{
		const TSharedPtr<FJsonObject> O = V->AsObject();
		FIVLayoutSocket S;
		const FString K = O->GetStringField(TEXT("kind"));
		S.Kind = K == TEXT("steam") ? 0 : (K == TEXT("spark") ? 1 : 2);
		S.P = Vec3(O, TEXT("p"));
		const TArray<TSharedPtr<FJsonValue>>& D = O->GetArrayField(TEXT("d"));
		S.D = FVector(D[0]->AsNumber(), -D[1]->AsNumber(), D[2]->AsNumber()).GetSafeNormal();
		S.Tag = O->GetStringField(TEXT("tag"));
		Sockets.Add(S);
	}
	for (const TSharedPtr<FJsonValue>& V : Rootj->GetArrayField(TEXT("lamps")))
	{
		const TSharedPtr<FJsonObject> O = V->AsObject();
		UPointLightComponent* L = NewObject<UPointLightComponent>(GetOwner());
		L->SetupAttachment(this);
		L->RegisterComponent();
		L->SetRelativeLocation(Vec3(O, TEXT("p")));
		const TArray<TSharedPtr<FJsonValue>>& C = O->GetArrayField(TEXT("color"));
		L->SetLightColor(FLinearColor(C[0]->AsNumber(), C[1]->AsNumber(), C[2]->AsNumber()));
		L->SetIntensityUnits(ELightUnits::Candelas);
		const float I = O->GetNumberField(TEXT("i")) * 1.0f;
		L->SetIntensity(I);
		L->SetAttenuationRadius(O->GetNumberField(TEXT("radius")) * 100.f);
		L->SetCastShadows(false);
		L->SetSourceRadius(6.f);
		L->SetLightingChannels(false, true, false);
		Lamps.Add(L);
		LampKinds.Add(O->GetStringField(TEXT("kind")));
		LampBase.Add(I);
	}
	return true;
}

void UIVCockpitComponent::EnsureBuilt()
{
	if (bBuilt) return;
	bBuilt = true;
	if (!LoadLayout()) { UE_LOG(LogTemp, Warning, TEXT("IV cockpit: layout missing")); return; }
	UMaterialInterface* PropM = LoadObject<UMaterialInterface>(nullptr, TEXT("/Game/Materials/M_PropColor.M_PropColor"));
	if (PropM) PropMID = UMaterialInstanceDynamic::Create(PropM, this);
	BuildBody();
	BuildPipes();
	BuildWires();
	BuildMonitors();

	auto MakeISM = [&](const TCHAR* Name, UStaticMesh* Mesh, UMaterialInterface* Mat, int32 NumCD) -> UInstancedStaticMeshComponent*
	{
		UInstancedStaticMeshComponent* C = NewObject<UInstancedStaticMeshComponent>(GetOwner(), Name);
		C->SetStaticMesh(Mesh);
		if (Mat) C->SetMaterial(0, Mat);
		C->NumCustomDataFloats = NumCD;
		C->SetCollisionEnabled(ECollisionEnabled::NoCollision);
		C->SetCastShadow(false);
		C->SetOnlyOwnerSee(true);
		C->bAffectDynamicIndirectLighting = false;
		C->SetLightingChannels(false, true, false);
		C->SetupAttachment(this);
		C->RegisterComponent();
		return C;
	};
	UStaticMesh* Plane = LoadSM(TEXT("/Engine/BasicShapes/Plane.Plane"));
	UStaticMesh* Cube = LoadSM(TEXT("/Engine/BasicShapes/Cube.Cube"));
	UMaterialInterface* PuffM = LoadObject<UMaterialInterface>(nullptr, TEXT("/Game/Materials/M_Puff.M_Puff"));
	UMaterialInterface* SparkM = LoadObject<UMaterialInterface>(nullptr, TEXT("/Game/Materials/M_Spark.M_Spark"));
	UMaterialInterface* FireM = LoadObject<UMaterialInterface>(nullptr, TEXT("/Game/Materials/M_Fire.M_Fire"));
	UMaterialInstanceDynamic* SteamMID = PuffM ? UMaterialInstanceDynamic::Create(PuffM, this) : nullptr;
	if (SteamMID) SteamMID->SetScalarParameterValue(TEXT("Brightness"), 3.6f);
	PuffISM = MakeISM(TEXT("CkPuffs"), Plane, SteamMID ? Cast<UMaterialInterface>(SteamMID) : PuffM, 3);
	SparkISM = MakeISM(TEXT("CkSparks"), Cube, SparkM, 0);
	FlameISM = MakeISM(TEXT("CkFlames"), Plane, FireM, 3);
	PuffISM->SetCullDistances(0, 0); FlameISM->SetCullDistances(0, 0); SparkISM->SetCullDistances(0, 0);

	FireLight = NewObject<UPointLightComponent>(GetOwner());
	FireLight->SetupAttachment(this);
	FireLight->RegisterComponent();
	FireLight->SetIntensityUnits(ELightUnits::Candelas);
	FireLight->SetIntensity(0.f);
	FireLight->SetLightColor(FLinearColor(1.f, 0.45f, 0.12f));
	FireLight->SetAttenuationRadius(260.f);
	FireLight->SetCastShadows(false);
	FireLight->SetLightingChannels(false, true, false);
	SetShown(bShown);
	if (Pipes.Num() && Pipes[0].Mesh)
	{
		UProceduralMeshComponent* PM = Pipes[0].Mesh;
		UE_LOG(LogTemp, Display, TEXT("IV pipe0: sections %d visible %d verts %d dense %d bounds %s mat %s onlyowner %d"), PM->GetNumSections(), PM->IsVisible(), PM->GetProcMeshSection(0) ? PM->GetProcMeshSection(0)->ProcVertexBuffer.Num() : -1, Pipes[0].Dense.Num(), *PM->Bounds.Origin.ToString(), PM->GetMaterial(0) ? *PM->GetMaterial(0)->GetName() : TEXT("none"), PM->bOnlyOwnerSee);
	}
	UE_LOG(LogTemp, Display, TEXT("IV cockpit built: %d pipes, %d wires, %d monitors, %d lamps, %d sockets"), Pipes.Num(), Wires.Num(), Monitors.Num(), Lamps.Num(), Sockets.Num());
	LogLine(TEXT("СИСТЕМЫ: ЗАПУСК"));
	LogLine(TEXT("РЕАКТОР: СТАБИЛЕН"));
	LogLine(TEXT("СВЯЗЬ ПИЛОТ-МЕХ: УСТАНОВЛЕНА"));
}

void UIVCockpitComponent::SetShown(bool bShow)
{
	bShown = bShow;
	if (!bBuilt) return;
	TArray<USceneComponent*> Kids;
	GetChildrenComponents(true, Kids);
	for (USceneComponent* K : Kids) K->SetVisibility(bShow, false);
}

void UIVCockpitComponent::SetMotion(const FVector& InVel, float InSpeed01, const FVector& InAccel, float InLean, float InTwist)
{
	LocalVel = InVel; Speed01 = InSpeed01; LocalAccel = InAccel; Lean = InLean; Twist = InTwist;
}

// ----------------------------------------------------------------------------------------------------------- body
void UIVCockpitComponent::BuildBody()
{
	BodyPivot.SetNum(B_Count);
	auto Pivot = [&](int32 I, USceneComponent* Parent, const FVector& Loc)
	{
		USceneComponent* P = NewObject<USceneComponent>(GetOwner());
		P->SetupAttachment(Parent);
		P->SetRelativeLocation(Loc);
		P->RegisterComponent();
		BodyPivot[I] = P;
		return P;
	};
	auto Mesh = [&](int32 I, const TCHAR* Path, float YScale)
	{
		UStaticMeshComponent* M = NewObject<UStaticMeshComponent>(GetOwner());
		M->SetStaticMesh(LoadSM(Path));
		M->SetupAttachment(BodyPivot[I]);
		M->SetRelativeScale3D(FVector(1.f, YScale, 1.f));
		M->SetCollisionEnabled(ECollisionEnabled::NoCollision);
		M->SetCastShadow(false);
		M->SetOnlyOwnerSee(true);
		M->bAffectDynamicIndirectLighting = false;
		M->SetLightingChannels(false, true, false);
		if (CockpitMat) M->SetMaterial(0, CockpitMat);
		M->RegisterComponent();
		BodyParts.Add(M);
	};
	const float Hz = -82.f;
	Pivot(B_Pelvis, this, FVector(0, 0, Hz));
	Mesh(B_Pelvis, TEXT("/Game/Cockpit/V3/SM_Body_Pelvis.SM_Body_Pelvis"), 1.f);
	Pivot(B_Torso, BodyPivot[B_Pelvis], FVector(0, 0, 0));
	Mesh(B_Torso, TEXT("/Game/Cockpit/V3/SM_Body_Torso.SM_Body_Torso"), 1.f);
	for (int32 s = 0; s < 2; ++s)
	{
		const float Y = (s == 0 ? -1.f : 1.f) * 11.5f;      // s 0 = left (UE -Y)
		const float Sc = (s == 0 ? 1.f : -1.f);
		Pivot(B_ThighL + s, this, FVector(0, Y, Hz));
		Mesh(B_ThighL + s, TEXT("/Game/Cockpit/V3/SM_Body_Thigh.SM_Body_Thigh"), Sc);
		Pivot(B_ShinL + s, BodyPivot[B_ThighL + s], FVector(0, 0, -38.f));
		Mesh(B_ShinL + s, TEXT("/Game/Cockpit/V3/SM_Body_Shin.SM_Body_Shin"), Sc);
		Pivot(B_BootL + s, BodyPivot[B_ShinL + s], FVector(0, 0, -36.f));
		Mesh(B_BootL + s, TEXT("/Game/Cockpit/V3/SM_Body_Boot.SM_Body_Boot"), Sc);
	}
}

void UIVCockpitComponent::UpdateBody(float Dt)
{
	if (BodyPivot.Num() < B_Count) return;
	// the pilot walks in place on the platform: alternate leg lifts proportional to the mech's speed
	const float Freq = FMath::Lerp(0.18f, 0.62f, FMath::Clamp(Speed01, 0.f, 1.f)) * (Speed01 > 0.03f ? 1.f : 0.f);
	GaitPhase += Freq * Dt * 2.f * PI;
	StepPulse = FMath::FInterpTo(StepPulse, 0.f, Dt, 7.f);
	const float Amp = FMath::Clamp(Speed01 * 1.3f, 0.f, 1.f);
	BodyLean = FMath::FInterpTo(BodyLean, Lean, Dt, 6.f);
	const float Breath = FMath::Sin(Time * 1.7f);
	for (int32 s = 0; s < 2; ++s)
	{
		const float Ph = FMath::Sin(GaitPhase + (s == 0 ? 0.f : PI));
		const float Lift = FMath::Max(0.f, Ph) * Amp;
		BodyPivot[B_ThighL + s]->SetRelativeRotation(FRotator(Lift * 38.f - 3.f + BodyLean * 0.2f, 0.f, 0.f));
		BodyPivot[B_ShinL + s]->SetRelativeRotation(FRotator(-Lift * 62.f - 2.f, 0.f, 0.f));
		BodyPivot[B_BootL + s]->SetRelativeRotation(FRotator(Lift * 30.f * 0.8f + 4.f, 0.f, 0.f));
	}
	const float Bob = -StepPulse * 1.6f + 0.35f * Breath;
	BodyPivot[B_Pelvis]->SetRelativeLocation(FVector(0, 0, -82.f + Bob));
	BodyPivot[B_Pelvis]->SetRelativeRotation(FRotator(BodyLean * 0.4f, Twist * 0.5f, 0.f));
	BodyPivot[B_Torso]->SetRelativeRotation(FRotator(BodyLean * 0.9f + 0.5f * Breath, Twist, FMath::Clamp(-LocalAccel.Y * 0.002f, -4.f, 4.f)));
}

// ----------------------------------------------------------------------------------------------------------- pipes
void UIVCockpitComponent::BuildPipes()
{
	for (FIVCockpitPipe& P : Pipes)
	{
		P.Dense.Reset();
		const int32 N = P.Ctrl.Num();
		for (int32 i = 0; i + 1 < N; ++i)
		{
			const FVector P0 = P.Ctrl[FMath::Max(i - 1, 0)], P1 = P.Ctrl[i], P2 = P.Ctrl[i + 1], P3 = P.Ctrl[FMath::Min(i + 2, N - 1)];
			for (int32 k = 0; k < 8; ++k) P.Dense.Add(CatmullRom(P0, P1, P2, P3, float(k) / 8.f));
		}
		P.Dense.Add(P.Ctrl.Last());
		if (P.Steam > 0.f && P.Dense.Num() > 6)
		{
			for (float T : { 0.3f, 0.7f })
			{
				const int32 I = FMath::Clamp(int32(T * P.Dense.Num()), 1, P.Dense.Num() - 2);
				const FVector Tn = (P.Dense[I + 1] - P.Dense[I - 1]).GetSafeNormal();
				FVector Out = FVector::CrossProduct(Tn, FVector::UpVector);
				if (Out.IsNearlyZero()) Out = FVector::RightVector;
				P.Ports.Add(P.Dense[I]);
				P.PortDirs.Add((Out.GetSafeNormal() * (Rng.FRand() < 0.5f ? 1.f : -1.f) + FVector(0, 0, 0.6f)).GetSafeNormal());
			}
		}
		UProceduralMeshComponent* M = NewObject<UProceduralMeshComponent>(GetOwner());
		M->SetupAttachment(this);
		M->SetCollisionEnabled(ECollisionEnabled::NoCollision);
		M->SetCastShadow(false);
		M->SetOnlyOwnerSee(true);
		M->SetLightingChannels(false, true, false);
		M->bAffectDynamicIndirectLighting = false;
		M->RegisterComponent();
		P.Mesh = M;
		RebuildPipeMesh(P);
		if (CockpitMat) M->SetMaterial(0, CockpitMat);
	}
}

void UIVCockpitComponent::RebuildPipeMesh(FIVCockpitPipe& P)
{
	FTubeMesh M;
	const int32 N = P.Dense.Num();
	if (!P.bBurst)
	{
		AppendTube(M, P.Dense, 0, N - 1, P.R, float(P.Cls), true, true);
		// flanges every ~26 cm
		float Acc = 0.f;
		for (int32 i = 1; i + 2 < N; ++i)
		{
			Acc += FVector::Dist(P.Dense[i], P.Dense[i - 1]);
			if (Acc > 26.f)
			{
				Acc = 0.f;
				TArray<FVector> Seg = { P.Dense[i] - (P.Dense[i + 1] - P.Dense[i - 1]).GetSafeNormal() * 1.2f, P.Dense[i] + (P.Dense[i + 1] - P.Dense[i - 1]).GetSafeNormal() * 1.2f };
				AppendTube(M, Seg, 0, 1, P.R * 1.4f, 1.f, true, true);
			}
		}
	}
	else
	{
		FRandomStream R(GetTypeHash(P.Id));
		const int32 B = FMath::Clamp(P.BreakIdx, 3, N - 4);
		AppendTube(M, P.Dense, 0, B - 1, P.R, float(P.Cls), true, true, 0.f, P.R * 1.8f, &R);
		AppendTube(M, P.Dense, B + 2, N - 1, P.R, float(P.Cls), true, true, P.R * 1.8f, 0.f, &R);
	}
	P.Mesh->ClearAllMeshSections();
	TArray<FVector2D> E;
	P.Mesh->CreateMeshSection(0, M.V, M.Tri, M.N, M.UV0, M.UV1, E, E, TArray<FColor>(), TArray<FProcMeshTangent>(), false);
	if (CockpitMat) P.Mesh->SetMaterial(0, CockpitMat);
}

void UIVCockpitComponent::BurstPipe(int32 Index)
{
	if (!Pipes.IsValidIndex(Index)) return;
	FIVCockpitPipe& P = Pipes[Index];
	if (P.bBurst || !P.bBreakable) return;
	P.bBurst = true;
	P.BreakIdx = FMath::Clamp(int32(P.Dense.Num() * Rng.FRandRange(0.3f, 0.7f)), 3, P.Dense.Num() - 4);
	const int32 B = P.BreakIdx;
	P.JetA = P.Dense[B - 1]; P.DirA = (P.Dense[B - 1] - P.Dense[B - 3]).GetSafeNormal();
	P.JetB = P.Dense[B + 2]; P.DirB = (P.Dense[B + 2] - P.Dense[B + 4 < P.Dense.Num() ? B + 4 : P.Dense.Num() - 1]).GetSafeNormal();
	P.JetTime = 0.f;
	P.JetPower = 1.f;
	RebuildPipeMesh(P);
	EmitSteam(P.JetA, P.DirA, 18, 360.f, 20.f);
	EmitSteam(P.JetB, P.DirB, 18, 360.f, 20.f);
	EmitSparks(P.JetA, P.DirA, 24, 520.f);
	IVAudio::Play2D(GetWorld(), TEXT("cockpit_panel_burst"), 0.9f, FMath::RandRange(0.9f, 1.1f));
	LogLine(TEXT("КОНТУР ОХЛАЖДЕНИЯ: РАЗРЫВ"));
}

void UIVCockpitComponent::UpdatePipes(float Dt)
{
	for (FIVCockpitPipe& P : Pipes)
	{
		if (P.bBurst)
		{
			P.JetTime += Dt;
			P.JetPower = FMath::Max(P.JetPower - Dt * 0.012f, 0.25f);
			if (Rng.FRand() < Dt * 24.f * P.JetPower)
			{
				EmitSteam(P.JetA + Rng.VRand() * 1.f, (P.DirA + Rng.VRand() * 0.35f).GetSafeNormal(), 1, Rng.FRandRange(160.f, 340.f), Rng.FRandRange(12.f, 22.f));
			}
			if (Rng.FRand() < Dt * 24.f * P.JetPower)
			{
				EmitSteam(P.JetB + Rng.VRand() * 1.f, (P.DirB + Rng.VRand() * 0.35f).GetSafeNormal(), 1, Rng.FRandRange(160.f, 340.f), Rng.FRandRange(12.f, 22.f));
			}
			if (Rng.FRand() < Dt * 1.2f) EmitSparks(P.JetA, P.DirA, 4, 380.f);
		}
		else if (P.Steam > 0.f && Speed01 > 0.05f)
		{
			for (int32 i = 0; i < P.Ports.Num(); ++i)
			{
				if (Rng.FRand() < Dt * 9.f * P.Steam * Speed01) EmitSteam(P.Ports[i], P.PortDirs[i], 1, Rng.FRandRange(30.f, 70.f), Rng.FRandRange(5.f, 9.f));
			}
		}
	}
}

// ----------------------------------------------------------------------------------------------------------- wires
void UIVCockpitComponent::BuildWires()
{
	UStaticMesh* Cyl = LoadSM(TEXT("/Engine/BasicShapes/Cylinder.Cylinder"));
	WireISM = NewObject<UInstancedStaticMeshComponent>(GetOwner(), TEXT("CkWires"));
	WireISM->SetStaticMesh(Cyl);
	if (PropMID) WireISM->SetMaterial(0, PropMID);
	WireISM->NumCustomDataFloats = 3;
	WireISM->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	WireISM->SetCastShadow(false);
	WireISM->SetOnlyOwnerSee(true);
	WireISM->bAffectDynamicIndirectLighting = false;
	WireISM->SetLightingChannels(false, true, false);
	WireISM->SetupAttachment(this);
	WireISM->RegisterComponent();
	TArray<FTransform> T;
	int32 Idx = 0;
	for (FIVCockpitWire& W : Wires)
	{
		W.Base = Idx;
		W.P.SetNum(8); W.Prev.SetNum(8);
		FVector Cur = W.Anchor;
		for (int32 i = 0; i < 8; ++i)
		{
			W.P[i] = W.Prev[i] = Cur;
			Cur += W.Dir * W.SegLen;
			if (!W.bStick) W.Dir = (W.Dir + FVector(0, 0, -0.05f)).GetSafeNormal();
		}
		for (int32 i = 0; i < 7; ++i) { T.Add(FTransform::Identity); ++Idx; }
	}
	WireISM->AddInstances(T, false, false);
	int32 K = 0;
	for (FIVCockpitWire& W : Wires)
	{
		for (int32 i = 0; i < 7; ++i)
		{
			const float C[3] = { W.Col.R, W.Col.G, W.Col.B };
			WireISM->SetCustomData(K++, MakeArrayView(C, 3), false);
		}
	}
}

void UIVCockpitComponent::SnapWire(int32 Index)
{
	if (!Wires.IsValidIndex(Index)) return;
	FIVCockpitWire& W = Wires[Index];
	if (W.bSnapped) return;
	W.bSnapped = true;
	W.SnapTime = 0.f;
	W.bStick = false;
	// the cut end whips away
	for (int32 i = 0; i < 8; ++i) W.Prev[i] = W.P[i] - FVector(Rng.FRandRange(-1.f, 1.f), Rng.FRandRange(-1.f, 1.f), Rng.FRandRange(-0.5f, 0.5f)) * 3.f;
	EmitSparks(W.P[0], FVector::DownVector, 14, 420.f);
	IVAudio::Play2D(GetWorld(), IVAudio::Variant(TEXT("cockpit_spark_"), 4), 0.8f, FMath::RandRange(0.9f, 1.15f));
}

void UIVCockpitComponent::UpdateWires(float Dt)
{
	if (!WireISM) return;
	const float H = FMath::Min(Dt, 0.033f);
	TArray<FTransform> T;
	T.Reserve(Wires.Num() * 7);
	const FVector Inertia = -LocalAccel * 0.0009f * 100.f + FVector(0, -Lean * 0.0f, 0);
	for (FIVCockpitWire& W : Wires)
	{
		const int32 N = W.P.Num();
		const FVector Wobble(Rng.FRandRange(-1.f, 1.f), Rng.FRandRange(-1.f, 1.f), 0.f);
		if (W.bSnapped) W.SnapTime += Dt;
		for (int32 i = 1; i < N; ++i)
		{
			const FVector Vel = (W.P[i] - W.Prev[i]) * 0.985f;
			FVector Acc = FVector(0, 0, W.bStick ? -420.f : -980.f) + Inertia * 55.f + Wobble * (6.f + 90.f * ShakeLevel);
			if (W.bStick)
			{
				const FVector Rest = W.Anchor + W.Dir * W.SegLen * i;
				Acc += (Rest - W.P[i]) * 55.f;
			}
			W.Prev[i] = W.P[i];
			W.P[i] += Vel + Acc * H * H;
		}
		if (!W.bSnapped) { W.P[0] = W.Anchor; W.Prev[0] = W.Anchor; }
		else
		{
			const FVector Vel = (W.P[0] - W.Prev[0]) * 0.985f;
			W.Prev[0] = W.P[0];
			W.P[0] += Vel + FVector(0, 0, -980.f) * H * H;
		}
		for (int32 It = 0; It < 4; ++It)
		{
			for (int32 i = 0; i + 1 < N; ++i)
			{
				const FVector D = W.P[i + 1] - W.P[i];
				const float L = D.Size();
				if (L < 1e-3f) continue;
				const float Diff = (L - W.SegLen) / L;
				if (i == 0 && !W.bSnapped) W.P[i + 1] -= D * Diff;
				else { W.P[i] += D * Diff * 0.5f; W.P[i + 1] -= D * Diff * 0.5f; }
			}
			if (!W.bSnapped) W.P[0] = W.Anchor;
			for (FVector& P : W.P) P.Z = FMath::Max(P.Z, -168.f);
		}
		if (W.bSnapped && W.SnapTime < 7.f)
		{
			W.SparkAcc += Dt;
			if (W.SparkAcc > 0.35f + 0.5f * Rng.FRand()) { W.SparkAcc = 0.f; EmitSparks(W.P[0], FVector(0, 0, 1), 5, 260.f); IVAudio::Play2D(GetWorld(), IVAudio::Variant(TEXT("cockpit_spark_"), 4), 0.4f, FMath::RandRange(1.f, 1.3f)); }
		}
		for (int32 i = 0; i + 1 < N; ++i)
		{
			const FVector D = W.P[i + 1] - W.P[i];
			const float L = FMath::Max(D.Size(), 0.01f);
			T.Add(FTransform(FRotationMatrix::MakeFromZ(D / L).ToQuat(), (W.P[i] + W.P[i + 1]) * 0.5f, FVector(W.R / 50.f, W.R / 50.f, L / 100.f * 1.05f)));
		}
	}
	WireISM->BatchUpdateInstancesTransforms(0, T, false, true, true);
}

// ----------------------------------------------------------------------------------------------------------- particles
void UIVCockpitComponent::EmitSteam(const FVector& P, const FVector& Dir, int32 Count, float Speed, float Size)
{
	for (int32 i = 0; i < Count && Puffs.Num() < 240; ++i)
	{
		FIVCockpitPuff F;
		F.P = P;
		F.V = (Dir + Rng.VRand() * 0.25f).GetSafeNormal() * Speed * Rng.FRandRange(0.5f, 1.f);
		F.Life = Rng.FRandRange(0.9f, 1.9f);
		F.S0 = Size * 0.5f; F.S1 = Size * Rng.FRandRange(2.f, 3.4f);
		F.Roll = Rng.FRandRange(0.f, 360.f);
		F.Rise = Rng.FRandRange(10.f, 40.f);
		F.Drag = Rng.FRandRange(1.2f, 2.2f);
		F.Seed = Rng.FRand();
		Puffs.Add(F);
	}
}

void UIVCockpitComponent::EmitSparks(const FVector& P, const FVector& Dir, int32 Count, float Speed)
{
	for (int32 i = 0; i < Count && Sparks.Num() < 260; ++i)
	{
		FIVCockpitSpark S;
		S.P = P;
		S.V = (Dir + Rng.VRand() * 0.9f).GetSafeNormal() * Speed * Rng.FRandRange(0.25f, 1.f);
		S.Life = Rng.FRandRange(0.3f, 0.9f);
		S.Len = Rng.FRandRange(2.f, 7.f);
		Sparks.Add(S);
	}
}

void UIVCockpitComponent::AddFire(int32 SocketIndex)
{
	if (!Sockets.IsValidIndex(SocketIndex)) return;
	Sockets[SocketIndex].Burn = FMath::Max(Sockets[SocketIndex].Burn, 1.f);
}

void UIVCockpitComponent::UpdateParticles(float Dt)
{
	// steam
	for (int32 i = Puffs.Num() - 1; i >= 0; --i)
	{
		FIVCockpitPuff& P = Puffs[i];
		P.Age += Dt;
		if (P.Age >= P.Life) { Puffs.RemoveAtSwap(i); continue; }
		P.V *= FMath::Exp(-P.Drag * Dt);
		P.V.Z += P.Rise * Dt;
		P.P += P.V * Dt;
	}
	{
		TArray<FTransform> T;
		T.Reserve(Puffs.Num());
		for (const FIVCockpitPuff& P : Puffs)
		{
			const float A = P.Age / P.Life;
			const float Size = FMath::Lerp(P.S0, P.S1, 1.f - FMath::Square(1.f - FMath::Min(A * 1.5f, 1.f)));
			FVector ToEye = -P.P;
			if (!ToEye.Normalize()) ToEye = FVector::UpVector;
			const FQuat Q = FQuat::FindBetweenNormals(FVector::UpVector, ToEye) * FQuat(FVector::UpVector, FMath::DegreesToRadians(P.Roll));
			T.Add(FTransform(Q, P.P, FVector(Size / 100.f)));
		}
		if (PuffISM->GetInstanceCount() != T.Num()) { PuffISM->ClearInstances(); PuffISM->NumCustomDataFloats = 3; if (T.Num()) PuffISM->AddInstances(T, false, false); }
		else if (T.Num()) PuffISM->BatchUpdateInstancesTransforms(0, T, false, true, true);
		for (int32 i = 0; i < T.Num(); ++i)
		{
			const float C[3] = { Puffs[i].Age / Puffs[i].Life, Puffs[i].Seed, Puffs[i].Dark };
			PuffISM->SetCustomData(i, MakeArrayView(C, 3), i == T.Num() - 1);
		}
	}
	// sparks
	for (int32 i = Sparks.Num() - 1; i >= 0; --i)
	{
		FIVCockpitSpark& S = Sparks[i];
		S.Age += Dt;
		if (S.Age >= S.Life) { Sparks.RemoveAtSwap(i); continue; }
		S.V.Z -= 700.f * Dt;
		S.V *= FMath::Exp(-0.6f * Dt);
		S.P += S.V * Dt;
	}
	{
		TArray<FTransform> T;
		T.Reserve(Sparks.Num());
		for (const FIVCockpitSpark& S : Sparks)
		{
			const float Fade = 1.f - S.Age / S.Life;
			T.Add(FTransform(FRotationMatrix::MakeFromX(S.V.GetSafeNormal()).ToQuat(), S.P, FVector(S.Len / 100.f, 0.012f, 0.012f) * (0.4f + 0.6f * Fade)));
		}
		if (SparkISM->GetInstanceCount() != T.Num()) { SparkISM->ClearInstances(); if (T.Num()) SparkISM->AddInstances(T, false, false); }
		else if (T.Num()) SparkISM->BatchUpdateInstancesTransforms(0, T, false, true, true);
	}
	// flames from burning sockets
	float FireSum = 0.f;
	for (const FIVLayoutSocket& S : Sockets)
	{
		if (S.Kind != 2 || S.Burn <= 0.f) continue;
		FireSum += S.Burn;
		if (Rng.FRand() < Dt * 22.f * S.Burn && Flames.Num() < 120)
		{
			FIVCockpitFlame F;
			F.P = S.P + FVector(Rng.FRandRange(-5.f, 5.f), Rng.FRandRange(-5.f, 5.f), Rng.FRandRange(0.f, 4.f));
			F.V = FVector(Rng.FRandRange(-8.f, 8.f), Rng.FRandRange(-8.f, 8.f), 0.f) + S.D * Rng.FRandRange(10.f, 30.f);
			F.Life = Rng.FRandRange(0.5f, 1.0f);
			F.S0 = Rng.FRandRange(7.f, 12.f); F.S1 = F.S0 * Rng.FRandRange(1.5f, 2.3f);
			F.Roll = Rng.FRandRange(0.f, 360.f);
			F.Rise = Rng.FRandRange(60.f, 140.f);
			F.Heat = Rng.FRandRange(0.4f, 1.f);
			F.Seed = Rng.FRand();
			Flames.Add(F);
			if (Rng.FRand() < 0.15f) EmitSteam(F.P, FVector(0, 0, 1), 1, 60.f, 14.f);
		}
	}
	for (int32 i = Flames.Num() - 1; i >= 0; --i)
	{
		FIVCockpitFlame& F = Flames[i];
		F.Age += Dt;
		if (F.Age >= F.Life) { Flames.RemoveAtSwap(i); continue; }
		F.V *= FMath::Exp(-1.2f * Dt);
		F.V.Z += F.Rise * Dt;
		F.P += F.V * Dt;
	}
	{
		TArray<FTransform> T;
		T.Reserve(Flames.Num());
		for (const FIVCockpitFlame& F : Flames)
		{
			const float A = F.Age / F.Life;
			const float Size = FMath::Lerp(F.S0, F.S1, FMath::Sqrt(A));
			FVector ToEye = -F.P;
			if (!ToEye.Normalize()) ToEye = FVector::UpVector;
			T.Add(FTransform(FQuat::FindBetweenNormals(FVector::UpVector, ToEye) * FQuat(FVector::UpVector, FMath::DegreesToRadians(F.Roll)), F.P, FVector(Size / 100.f)));
		}
		if (FlameISM->GetInstanceCount() != T.Num()) { FlameISM->ClearInstances(); FlameISM->NumCustomDataFloats = 3; if (T.Num()) FlameISM->AddInstances(T, false, false); }
		else if (T.Num()) FlameISM->BatchUpdateInstancesTransforms(0, T, false, true, true);
		for (int32 i = 0; i < T.Num(); ++i)
		{
			const float C[3] = { Flames[i].Age / Flames[i].Life, Flames[i].Seed, Flames[i].Heat };
			FlameISM->SetCustomData(i, MakeArrayView(C, 3), i == T.Num() - 1);
		}
	}
	{
		static float DbgT = 0.f; DbgT += Dt;
		if (DbgT > 1.f) { DbgT = 0.f; if (Puffs.Num() + Flames.Num() > 0) UE_LOG(LogTemp, Display, TEXT("IV cockpit fx: puffs %d (ism %d) sparks %d flames %d first puff %s age %.2f"), Puffs.Num(), PuffISM->GetInstanceCount(), Sparks.Num(), Flames.Num(), Puffs.Num() ? *Puffs[0].P.ToString() : TEXT("-"), Puffs.Num() ? Puffs[0].Age : 0.f); }
	}
	FireIntensity = FMath::FInterpTo(FireIntensity, FMath::Min(FireSum, 3.f), Dt, 3.f);
	if (FireLight)
	{
		FVector Pos = FVector::ZeroVector; float Wsum = 0.f;
		for (const FIVLayoutSocket& S : Sockets) if (S.Kind == 2 && S.Burn > 0.f) { Pos += S.P * S.Burn; Wsum += S.Burn; }
		if (Wsum > 0.f) FireLight->SetRelativeLocation(Pos / Wsum + FVector(0, 0, 15.f));
		FireLight->SetIntensity(FireIntensity * 38.f * (0.7f + 0.3f * FMath::Sin(Time * 31.f) * FMath::Sin(Time * 17.f)));
	}
}

// ----------------------------------------------------------------------------------------------------------- lamps
void UIVCockpitComponent::UpdateLamps(float Dt)
{
	for (int32 i = 0; i < Lamps.Num(); ++i)
	{
		float K = 1.f;
		const FString& Kind = LampKinds[i];
		if (Kind == TEXT("beacon"))
		{
			const float Ph = 0.5f + 0.5f * FMath::Sin(Time * 6.2f + i * 2.1f);
			K = AlertSmooth * (0.05f + 0.95f * Ph * Ph) * 1.2f;
		}
		else if (Kind == TEXT("strobe"))
		{
			K = (FMath::Frac(Time * 1.4f) < 0.08f ? 1.f : 0.f) * AlertSmooth;
		}
		else
		{
			K = PowerLevel * (1.f - 0.5f * Glitch * (FMath::Frac(Time * 9.f + i) < 0.4f ? 1.f : 0.f));
		}
		Lamps[i]->SetIntensity(LampBase[i] * K);
	}
}

// ----------------------------------------------------------------------------------------------------------- monitors
void UIVCockpitComponent::BuildMonitors()
{
	UStaticMesh* Plane = LoadSM(TEXT("/Engine/BasicShapes/Plane.Plane"));
	UMaterialInterface* MonM = LoadObject<UMaterialInterface>(nullptr, TEXT("/Game/Materials/M_Monitor.M_Monitor"));
	const int32 Sizes[8][2] = { { 512, 512 }, { 512, 512 }, { 512, 256 }, { 512, 256 }, { 256, 256 }, { 512, 256 }, { 512, 256 }, { 512, 128 } };
	for (int32 i = 0; i < 8; ++i) Targets.Add(UKismetRenderingLibrary::CreateRenderTarget2D(this, Sizes[i][0], Sizes[i][1], RTF_RGBA8, FLinearColor::Black, false));
	for (FIVCockpitMonitor& M : Monitors)
	{
		int32 Fd = 6;
		if (M.Id == TEXT("main_L")) Fd = 0;
		else if (M.Id == TEXT("main_R")) Fd = 1;
		else if (M.Id == TEXT("aux_L")) Fd = 2;
		else if (M.Id == TEXT("aux_R")) Fd = 3;
		else if (M.Id == TEXT("overhead")) Fd = 7;
		else { const uint32 H = GetTypeHash(M.Id); static const int32 Map[4] = { 4, 5, 6, 7 }; Fd = Map[H % 4]; if (M.Id.StartsWith(TEXT("wall"))) { static const int32 W[4] = { 6, 5, 2, 4 }; Fd = W[H % 4]; } }
		M.Feed = Fd;
		UStaticMeshComponent* C = NewObject<UStaticMeshComponent>(GetOwner());
		C->SetStaticMesh(Plane);
		C->SetupAttachment(this);
		C->SetCollisionEnabled(ECollisionEnabled::NoCollision);
		C->SetCastShadow(false);
		C->SetOnlyOwnerSee(true);
		C->bAffectDynamicIndirectLighting = false;
		C->SetLightingChannels(false, true, false);
		C->SetRelativeLocation(M.C + M.N * 0.35f);
		C->SetRelativeRotation(FRotationMatrix::MakeFromXZ(M.Right, M.N).Rotator());
		C->SetRelativeScale3D(FVector(M.W / 100.f, M.H / 100.f, 1.f));
		C->RegisterComponent();
		if (MonM)
		{
			M.MID = UMaterialInstanceDynamic::Create(MonM, this);
			M.MID->SetTextureParameterValue(TEXT("Tex"), Targets[Fd]);
			C->SetMaterial(0, M.MID);
		}
		M.Mesh = C;
	}
}

void UIVCockpitComponent::LogLine(const FString& S)
{
	LogLines.Add(S);
	if (LogLines.Num() > 14) LogLines.RemoveAt(0);
}

void UIVCockpitComponent::UpdateMonitors(float Dt)
{
	MonAcc += Dt;
	if (MonAcc < 1.f / 30.f) return;
	MonAcc = 0.f;
	// two targets per refresh keep the cost flat
	for (int32 k = 0; k < 2; ++k)
	{
		const int32 I = (MonRound++) % 8;
		DrawMonitor(I, Targets[I]);
	}
	for (FIVCockpitMonitor& M : Monitors)
	{
		if (!M.MID) continue;
		M.MID->SetScalarParameterValue(TEXT("Power"), PowerLevel * (0.75f + 0.25f * FMath::Clamp(Feed.Overall * 2.f, 0.f, 1.f)));
		M.MID->SetScalarParameterValue(TEXT("Glitch"), Glitch);
	}
}

void UIVCockpitComponent::DrawMonitor(int32 Type, UTextureRenderTarget2D* RT)
{
	if (!RT) return;
	UCanvas* Cv = nullptr;
	FVector2D Size;
	FDrawToRenderTargetContext Ctx;
	UKismetRenderingLibrary::BeginDrawCanvasToRenderTarget(this, RT, Cv, Size, Ctx);
	if (!Cv || !Cv->Canvas) { UKismetRenderingLibrary::EndDrawCanvasToRenderTarget(this, Ctx); return; }
	FCanvas* C = Cv->Canvas;
	const float W = Size.X, H = Size.Y;
	const float T = Time;
	const bool bAlert = AlertSmooth > 0.5f;
	const FLinearColor Back(0.0f, 0.025f, 0.04f, 1.f);
	FillR(C, 0, 0, W, H, Back);
	// grid
	for (float x = 0; x < W; x += 32.f) Ln(C, x, 0, x, H, Al(kCy, 0.07f), 1.f);
	for (float y = 0; y < H; y += 32.f) Ln(C, 0, y, W, y, Al(kCy, 0.07f), 1.f);
	Frame(C, 3, 3, W - 6, H - 6, Al(bAlert ? kRd : kCy, 0.7f), 2.f);
	auto Title = [&](const TCHAR* S) { FillR(C, 6, 6, W - 12, 20, Al(bAlert ? kRd : kCy, 0.18f)); Txt(C, S, 12, 9, Al(kWh, 0.95f), 1.f); };
	auto Bar = [&](float X, float Y, float BW, float BH, float V, const FLinearColor& Col, const TCHAR* Label)
	{
		FillR(C, X, Y, BW, BH, Al(Col, 0.12f));
		FillR(C, X, Y, BW * FMath::Clamp(V, 0.f, 1.f), BH, Al(Col, 0.85f));
		Frame(C, X, Y, BW, BH, Al(Col, 0.8f), 1.f);
		Txt(C, Label, X, Y - 13.f, Al(Col, 0.95f), 0.8f);
		Txt(C, FString::Printf(TEXT("%d%%"), int32(V * 100.f)), X + BW, Y - 13.f, Al(kWh, 0.9f), 0.8f, 2);
	};
	switch (Type)
	{
	case 0:   // own mech schematic
	{
		Title(TEXT("СТРУКТУРА  ·  ТВОЙ МЕХ"));
		Schematic(C, W * 0.5f, 40.f, FMath::Min(W, H) * 0.19f, Feed.Armor, Feed.State, false, T);
		Txt(C, FString::Printf(TEXT("ЦЕЛОСТНОСТЬ %d%%"), int32(Feed.Overall * 100.f)), 14, H - 34.f, Al(Feed.Overall < 0.4f ? kRd : kCy, 1.f), 1.3f);
		Bar(14, H - 78.f, W - 28.f, 12.f, Feed.Stability, kCy, TEXT("УСТОЙЧИВОСТЬ"));
		break;
	}
	case 1:   // enemy
	{
		Title(TEXT("ЦЕЛЬ  ·  ПРОТИВНИК"));
		Schematic(C, W * 0.5f, 40.f, FMath::Min(W, H) * 0.19f, Feed.EnemyArmor, Feed.EnemyState, true, T);
		Txt(C, FString::Printf(TEXT("ДИСТАНЦИЯ %.0f М"), Feed.DistM), 14, H - 34.f, Al(kRd, 1.f), 1.2f);
		Bar(14, H - 78.f, W - 28.f, 12.f, Feed.EnemyStability, kRd, TEXT("УСТОЙЧИВОСТЬ ЦЕЛИ"));
		Circle(C, W - 46.f, 70.f, 24.f, Al(kRd, 0.8f), 2.f);
		Ln(C, W - 46.f - 30.f, 70.f, W - 46.f + 30.f, 70.f, Al(kRd, 0.6f), 1.f); Ln(C, W - 46.f, 40.f, W - 46.f, 100.f, Al(kRd, 0.6f), 1.f);
		break;
	}
	case 2:   // power
	{
		Title(TEXT("ПИТАНИЕ  ·  ТЕПЛО"));
		Bar(14, 52.f, W - 28.f, 12.f, Feed.Energy, kGn, TEXT("ЭНЕРГИЯ"));
		Bar(14, 92.f, W - 28.f, 12.f, Feed.Heat, Feed.Heat > 0.65f ? kRd : kOr, TEXT("ТЕПЛО"));
		Bar(14, 132.f, W - 28.f, 12.f, Feed.Ultimate, kYe, TEXT("УЛЬТИМЕЙТ"));
		// reactor trace
		const float Y0 = H - 54.f;
		Ln(C, 12, Y0, W - 12, Y0, Al(kCy, 0.25f), 1.f);
		float Px = 12.f, Py = Y0;
		for (int32 i = 0; i < 60; ++i)
		{
			const float X = 12.f + (W - 24.f) * i / 59.f;
			const float Y = Y0 - (12.f + 10.f * Feed.Heat) * (FMath::Sin(T * 3.f + i * 0.4f) * 0.6f + FMath::Sin(T * 7.7f + i * 0.9f) * 0.4f);
			if (i) Ln(C, Px, Py, X, Y, Al(kGn, 0.9f), 1.5f);
			Px = X; Py = Y;
		}
		break;
	}
	case 3:   // weapons
	{
		Title(TEXT("ВООРУЖЕНИЕ"));
		const TCHAR* Names[3] = { TEXT("РАКЕТЫ"), TEXT("КОПЬЁ"), TEXT("ПЛАЗМА") };
		for (int32 i = 0; i < 3; ++i)
		{
			const float Cx = W * (0.2f + 0.3f * i), Cy = H * 0.55f;
			const bool bRdy = Feed.WeaponReady[i] > 0.99f;
			const FLinearColor Col = i == Feed.Weapon ? kYe : (bRdy ? kGn : kOr);
			Circle(C, Cx, Cy, 34.f, Al(Col, 0.25f), 6.f, 40);
			Circle(C, Cx, Cy, 34.f, Al(Col, 0.95f), 6.f, 40, -PI * 0.5f, -PI * 0.5f + 2.f * PI * Feed.WeaponReady[i]);
			Txt(C, Names[i], Cx, Cy + 40.f, Al(kWh, 0.9f), 0.9f, 1);
			Txt(C, FString::Printf(TEXT("%d"), i + 1), Cx, Cy - 8.f, Al(Col, 1.f), 1.6f, 1);
		}
		Txt(C, FString::Printf(TEXT("ЗДАНИЕ  %d%%"), int32(Feed.Scoop * 100.f)), 14, H - 22.f, Al(Feed.Scoop > 0.99f ? kGn : kOr, 0.95f), 0.9f);
		break;
	}
	case 4:   // radar
	{
		Title(TEXT("РАДАР"));
		const float Cx = W * 0.5f, Cy = H * 0.55f, R = FMath::Min(W, H) * 0.38f;
		for (int32 i = 1; i <= 3; ++i) Circle(C, Cx, Cy, R * i / 3.f, Al(kCy, 0.35f), 1.f, 36);
		Ln(C, Cx - R, Cy, Cx + R, Cy, Al(kCy, 0.3f), 1.f); Ln(C, Cx, Cy - R, Cx, Cy + R, Al(kCy, 0.3f), 1.f);
		const float Sw = T * 2.2f;
		for (int32 i = 0; i < 14; ++i) Ln(C, Cx, Cy, Cx + FMath::Cos(Sw - i * 0.06f) * R, Cy + FMath::Sin(Sw - i * 0.06f) * R, Al(kGn, 0.5f * (1.f - i / 14.f)), 2.f);
		const float Ang = FMath::DegreesToRadians(Feed.BearingDeg - 90.f);
		const float Rr = FMath::Clamp(Feed.DistM / 160.f, 0.1f, 1.f) * R;
		FillR(C, Cx + FMath::Cos(Ang) * Rr - 4, Cy + FMath::Sin(Ang) * Rr - 4, 8, 8, Al(kRd, 0.6f + 0.4f * FMath::Sin(T * 8.f)));
		FillR(C, Cx - 3, Cy - 3, 6, 6, Al(kCy, 1.f));
		break;
	}
	case 5:   // waveform
	{
		Title(TEXT("РЕАКТОР  ·  ЛИНИЯ"));
		for (int32 k = 0; k < 3; ++k)
		{
			float Px = 8.f, Py = H * (0.35f + 0.22f * k);
			for (int32 i = 0; i < 64; ++i)
			{
				const float X = 8.f + (W - 16.f) * i / 63.f;
				const float Y = H * (0.35f + 0.22f * k) - 14.f * FMath::Sin(T * (2.f + k) + i * (0.3f + 0.1f * k)) * (0.4f + 0.6f * FMath::Sin(T * 0.7f + k));
				if (i) Ln(C, Px, Py, X, Y, Al(k == 1 ? kOr : kCy, 0.85f), 1.5f);
				Px = X; Py = Y;
			}
		}
		break;
	}
	case 6:   // log
	{
		Title(TEXT("ЖУРНАЛ СИСТЕМ"));
		float Y = 32.f;
		for (int32 i = FMath::Max(0, LogLines.Num() - 7); i < LogLines.Num(); ++i)
		{
			const bool bBad = LogLines[i].Contains(TEXT("РАЗРЫВ")) || LogLines[i].Contains(TEXT("ПОЖАР")) || LogLines[i].Contains(TEXT("КРИТ")) || LogLines[i].Contains(TEXT("ОТКАЗ"));
			Txt(C, LogLines[i], 12, Y, Al(bBad ? kRd : kCy, 0.95f), 0.9f);
			Y += 15.f;
		}
		Txt(C, TEXT("_"), 12, Y, Al(kCy, FMath::Frac(T * 1.7f) < 0.5f ? 1.f : 0.f), 0.9f);
		break;
	}
	default:  // alerts
	{
		Title(TEXT("ТРЕВОГИ"));
		const int32 Fail = ActiveFailures();
		if (Fail > 0 || AlertSmooth > 0.2f)
		{
			FillR(C, 6, 30, W - 12, H - 36, Al(kRd, 0.15f + 0.2f * (0.5f + 0.5f * FMath::Sin(T * 8.f))));
			Txt(C, FString::Printf(TEXT("!  ОТКАЗОВ: %d"), Fail), W * 0.5f, H * 0.45f, Al(kWh, 1.f), 1.8f, 1);
		}
		else Txt(C, TEXT("ВСЕ СИСТЕМЫ В НОРМЕ"), W * 0.5f, H * 0.45f, Al(kGn, 0.95f), 1.2f, 1);
		break;
	}
	}
	if (Glitch > 0.2f && FMath::Frac(T * 5.f + Type) < 0.15f) FillR(C, 0, FMath::Frac(T * 3.1f) * H, W, 6.f, Al(kWh, 0.5f));
	UKismetRenderingLibrary::EndDrawCanvasToRenderTarget(this, Ctx);
}

// ----------------------------------------------------------------------------------------------------------- events
void UIVCockpitComponent::Footfall(float Strength)
{
	StepPulse = FMath::Max(StepPulse, Strength);
	if (!bBuilt) return;
	// pistons vent on every step
	for (FIVCockpitPipe& P : Pipes)
	{
		if (P.bBurst || P.Steam <= 0.f) continue;
		for (int32 i = 0; i < P.Ports.Num(); ++i) if (Rng.FRand() < 0.5f * P.Steam * Strength) EmitSteam(P.Ports[i], P.PortDirs[i], 3, Rng.FRandRange(60.f, 120.f), Rng.FRandRange(7.f, 13.f));
	}
	ShakeLevel = FMath::Max(ShakeLevel, 0.15f * Strength);
}

void UIVCockpitComponent::Hit(float Severity, const FVector& FromDir, bool bBlocked)
{
	if (!bBuilt) return;
	const float S = bBlocked ? Severity * 0.45f : Severity;
	ShakeLevel = FMath::Max(ShakeLevel, S);
	Glitch = FMath::Max(Glitch, S * 0.9f);
	AlertTarget = FMath::Max(AlertTarget, S > 0.5f ? 1.f : 0.f);
	// sparks from the console on the side of the impact
	if (S > 0.2f)
	{
		for (int32 k = 0; k < 1 + int32(S * 3.f); ++k)
		{
			TArray<int32> Sp;
			for (int32 i = 0; i < Sockets.Num(); ++i) if (Sockets[i].Kind == 1) Sp.Add(i);
			if (Sp.Num())
			{
				const FIVLayoutSocket& So = Sockets[Sp[Rng.RandRange(0, Sp.Num() - 1)]];
				EmitSparks(So.P, So.D, int32(8 + S * 18.f), 360.f + 300.f * S);
				IVAudio::Play2D(GetWorld(), IVAudio::Variant(TEXT("cockpit_spark_"), 4), 0.5f + 0.4f * S, FMath::RandRange(0.9f, 1.2f));
			}
		}
	}
	// pipes rupture, wires snap; the closer to the hit side, the likelier
	const float Side = FromDir.Y;
	if (S > 0.35f && PipeBurstCooldown <= 0.f && Rng.FRand() < 0.35f + S * 0.6f)
	{
		PipeBurstCooldown = 0.7f;
		TArray<int32> Cand;
		for (int32 i = 0; i < Pipes.Num(); ++i) if (!Pipes[i].bBurst && Pipes[i].bBreakable) { const float Y = Pipes[i].Dense[Pipes[i].Dense.Num() / 2].Y; if (Y * Side > -40.f) Cand.Add(i); }
		if (Cand.Num()) BurstPipe(Cand[Rng.RandRange(0, Cand.Num() - 1)]);
	}
	if (S > 0.2f && WireSnapCooldown <= 0.f)
	{
		WireSnapCooldown = 0.25f;
		const int32 N = 1 + int32(S * 4.f);
		for (int32 k = 0; k < N; ++k) SnapWire(Rng.RandRange(0, Wires.Num() - 1));
	}
	if (S > 0.65f)
	{
		TArray<int32> Free;
		for (int32 i = 0; i < Sockets.Num(); ++i) if (Sockets[i].Kind == 2 && Sockets[i].Burn <= 0.f) Free.Add(i);
		if (Free.Num() && Rng.FRand() < 0.5f) { AddFire(Free[Rng.RandRange(0, Free.Num() - 1)]); LogLine(TEXT("ПОЖАР: ОТСЕК ПИЛОТА")); IVAudio::Play2D(GetWorld(), TEXT("cockpit_panel_burst"), 0.7f, 0.8f); }
	}
	LogLine(FString::Printf(TEXT("УДАР: ПОГЛОЩЕНО %d%%"), int32((1.f - S) * 100.f)));
}

void UIVCockpitComponent::ZoneChanged(iv::Zone Z, iv::ZoneState S, iv::ZoneState Old)
{
	if (!bBuilt) return;
	static const TCHAR* Names[9] = { TEXT("ГОЛОВА"), TEXT("КОРПУС"), TEXT("РЕАКТОР"), TEXT("ПЛЕЧО Л"), TEXT("ПЛЕЧО П"), TEXT("РУКА Л"), TEXT("РУКА П"), TEXT("НОГА Л"), TEXT("НОГА П") };
	if (S > Old)
	{
		LogLine(FString::Printf(TEXT("%s: %s"), Names[iv::Index(Z)], S >= iv::ZoneState::Critical ? TEXT("КРИТИЧЕСКИЙ ОТКАЗ") : (S >= iv::ZoneState::Damaged ? TEXT("ПОВРЕЖДЕНИЕ") : TEXT("ЦАРАПИНЫ"))));
		if (S >= iv::ZoneState::Damaged) { AlertTarget = FMath::Max(AlertTarget, 1.f); Glitch = FMath::Max(Glitch, 0.6f); }
		if (S >= iv::ZoneState::Critical) AlertTarget = 2.f;
		if (S >= iv::ZoneState::Damaged && Rng.FRand() < 0.6f) BurstPipe(Rng.RandRange(0, Pipes.Num() - 1));
	}
}

void UIVCockpitComponent::PanelBurst(float Strength)
{
	if (!bBuilt) return;
	EmitSparks(FVector(60.f, Rng.FRandRange(-60.f, 60.f), -60.f), FVector::UpVector, int32(30 * Strength), 500.f);
	EmitSteam(FVector(60.f, Rng.FRandRange(-60.f, 60.f), -60.f), FVector::UpVector, int32(12 * Strength), 200.f, 18.f);
}

int32 UIVCockpitComponent::ActiveFailures() const
{
	int32 N = 0;
	for (const FIVCockpitPipe& P : Pipes) if (P.bBurst) ++N;
	for (const FIVLayoutSocket& S : Sockets) if (S.Kind == 2 && S.Burn > 0.f) ++N;
	return N;
}

void UIVCockpitComponent::Repair(float Amount)
{
	if (!bBuilt) return;
	for (FIVCockpitPipe& P : Pipes)
	{
		if (P.bBurst && Rng.FRand() < Amount) { P.bBurst = false; RebuildPipeMesh(P); }
	}
	for (FIVLayoutSocket& S : Sockets) if (S.Kind == 2 && S.Burn > 0.f && Rng.FRand() < Amount) S.Burn = 0.f;
	for (FIVCockpitWire& W : Wires) if (W.bSnapped && Rng.FRand() < Amount) { W.bSnapped = false; for (int32 i = 0; i < W.P.Num(); ++i) { W.P[i] = W.Prev[i] = W.Anchor + W.Dir * W.SegLen * i; } }
	if (Amount >= 1.f) { LogLine(TEXT("СИСТЕМЫ ВОССТАНОВЛЕНЫ")); }
}

void UIVCockpitComponent::ForceFailures(int32 Count)
{
	UE_LOG(LogTemp, Display, TEXT("IV cockpit: forcing %d failures (pipes %d wires %d sockets %d puffs %d)"), Count, Pipes.Num(), Wires.Num(), Sockets.Num(), Puffs.Num());
	TArray<int32> Front;
	for (int32 i = 0; i < Pipes.Num(); ++i) if (!Pipes[i].bBurst && Pipes[i].Dense[Pipes[i].Dense.Num() / 2].X > 20.f) Front.Add(i);
	for (int32 i = 0; i < Count; ++i)
	{
		BurstPipe(Front.Num() ? Front[Rng.RandRange(0, Front.Num() - 1)] : Rng.RandRange(0, Pipes.Num() - 1));
		SnapWire(Rng.RandRange(0, Wires.Num() - 1));
	}
	TArray<int32> Free;
	for (int32 i = 0; i < Sockets.Num(); ++i) if (Sockets[i].Kind == 2) Free.Add(i);
	for (int32 i = 0; i < Count && Free.Num(); ++i) AddFire(Free[Rng.RandRange(0, Free.Num() - 1)]);
	AlertTarget = 2.f;
}

// ----------------------------------------------------------------------------------------------------------- tick
void UIVCockpitComponent::TickComponent(float Dt, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction)
{
	Super::TickComponent(Dt, TickType, ThisTickFunction);
	if (!bBuilt || !bShown) return;
	Dt = FMath::Min(Dt, 0.05f);
	Time += Dt;
	PipeBurstCooldown = FMath::Max(0.f, PipeBurstCooldown - Dt);
	WireSnapCooldown = FMath::Max(0.f, WireSnapCooldown - Dt);
	ShakeLevel = FMath::FInterpTo(ShakeLevel, 0.f, Dt, 2.2f);
	Glitch = FMath::FInterpTo(Glitch, 0.f, Dt, 1.6f);

	// alert level: damage state, active failures, burning
	float Target = 0.f;
	if (Feed.bValid)
	{
		if (Feed.Overall < 0.55f) Target = 1.f;
		if (Feed.Overall < 0.3f) Target = 2.f;
		if (Feed.bBurn) Target = FMath::Max(Target, 1.f);
	}
	const int32 Fail = ActiveFailures();
	if (Fail > 0) Target = FMath::Max(Target, Fail > 2 ? 2.f : 1.f);
	AlertTarget = FMath::Max(Target, AlertTarget - Dt * 0.4f);
	AlertSmooth = FMath::FInterpTo(AlertSmooth, FMath::Max(AlertTarget, Target), Dt, 3.f);

	// ambient: sparks from the worst consoles when the mech is hurt
	if (Feed.bValid && Feed.Overall < 0.6f)
	{
		AmbientSparkAcc += Dt;
		if (AmbientSparkAcc > 0.5f + 2.5f * Feed.Overall)
		{
			AmbientSparkAcc = 0.f;
			TArray<int32> Sp;
			for (int32 i = 0; i < Sockets.Num(); ++i) if (Sockets[i].Kind == 1) Sp.Add(i);
			if (Sp.Num()) { const FIVLayoutSocket& So = Sockets[Sp[Rng.RandRange(0, Sp.Num() - 1)]]; EmitSparks(So.P, So.D, 6, 250.f); }
		}
	}
	UpdateBody(Dt);
	UpdatePipes(Dt);
	UpdateWires(Dt);
	UpdateParticles(Dt);
	UpdateLamps(Dt);
	UpdateMonitors(Dt);
	if (Feed.bValid && Feed.Overall < 0.35f && Rng.FRand() < Dt * 0.35f) { Glitch = FMath::Max(Glitch, 0.8f); }
	LogAcc += Dt;
	if (LogAcc > 6.f + 6.f * Rng.FRand())
	{
		LogAcc = 0.f;
		static const TCHAR* Idle[] = { TEXT("ДАВЛЕНИЕ В КОНТУРЕ: НОРМА"), TEXT("ГИРОСКОПЫ: СИНХРОНИЗАЦИЯ"), TEXT("СЕРВОПРИВОДЫ: ТЕСТ ПРОЙДЕН"), TEXT("ПИЛОТ: ПУЛЬС СТАБИЛЕН"), TEXT("ПОМЕХИ НА КАНАЛЕ 3") };
		LogLine(Idle[Rng.RandRange(0, 4)]);
	}
}
