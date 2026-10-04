#include "IVDistrict.h"
#include "IVBuilding.h"
#include "ProceduralMeshComponent.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "Misc/FileHelper.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "UObject/ConstructorHelpers.h"
#include "Components/PointLightComponent.h"
#include "HAL/IConsoleManager.h"

namespace
{
	FVector2D P2(const TSharedPtr<FJsonValue>& V)
	{
		const TArray<TSharedPtr<FJsonValue>>& A = V->AsArray();
		return FVector2D(A[0]->AsNumber(), A[1]->AsNumber());
	}
	// district metres (x right, y forward) -> UE cm xy
	FVector2D ToUE2(const FVector2D& D) { return FVector2D(D.Y * 100.0, D.X * 100.0); }

	FLinearColor CarColor(const FString& V, int32 Seed)
	{
		static const FLinearColor Pal[] = {
			FLinearColor(0.02f, 0.02f, 0.025f), FLinearColor(0.35f, 0.35f, 0.37f), FLinearColor(0.55f, 0.56f, 0.58f),
			FLinearColor(0.09f, 0.12f, 0.2f), FLinearColor(0.3f, 0.04f, 0.035f), FLinearColor(0.07f, 0.16f, 0.12f), FLinearColor(0.6f, 0.58f, 0.52f) };
		if (V == TEXT("taxi")) return FLinearColor(0.7f, 0.5f, 0.04f);
		if (V == TEXT("police")) return FLinearColor(0.02f, 0.03f, 0.06f);
		if (V == TEXT("bus")) return FLinearColor(0.12f, 0.2f, 0.32f);
		return Pal[FMath::Abs(Seed) % UE_ARRAY_COUNT(Pal)];
	}
	FVector CarSize(const FString& V)
	{
		if (V == TEXT("bus")) return FVector(1150, 270, 320);
		if (V == TEXT("truck")) return FVector(820, 250, 330);
		if (V == TEXT("van")) return FVector(560, 205, 210);
		if (V == TEXT("suv")) return FVector(480, 200, 175);
		return FVector(450, 185, 145);
	}
}

AIVDistrict::AIVDistrict()
{
	PrimaryActorTick.bCanEverTick = true;
	static ConstructorHelpers::FObjectFinder<UStaticMesh> CubeF(TEXT("/Engine/BasicShapes/Cube.Cube"));
	static ConstructorHelpers::FObjectFinder<UStaticMesh> CylF(TEXT("/Engine/BasicShapes/Cylinder.Cylinder"));
	static ConstructorHelpers::FObjectFinder<UStaticMesh> SphF(TEXT("/Engine/BasicShapes/Sphere.Sphere"));
	CubeMesh = CubeF.Object; CylMesh = CylF.Object; SphereMesh = SphF.Object;

	Root = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
	RootComponent = Root;

	auto ISM = [&](const TCHAR* Name, UStaticMesh* M, bool bCollide) {
		UInstancedStaticMeshComponent* C = CreateDefaultSubobject<UInstancedStaticMeshComponent>(Name);
		C->SetupAttachment(Root);
		C->SetStaticMesh(M);
		C->SetCollisionProfileName(bCollide ? TEXT("BlockAll") : TEXT("NoCollision"));
		return C;
	};
	Concrete = ISM(TEXT("Concrete"), CubeMesh, true);
	Glass = ISM(TEXT("Glass"), CubeMesh, true);
	Hero = ISM(TEXT("HeroStatic"), CubeMesh, true);
	Cars = ISM(TEXT("Cars"), CubeMesh, false);
	TreeTrunks = ISM(TEXT("TreeTrunks"), CylMesh, false);
	TreeCrowns = ISM(TEXT("TreeCrowns"), SphereMesh, false);
	Lamps = ISM(TEXT("Lamps"), CylMesh, false);
	static ConstructorHelpers::FObjectFinder<UStaticMesh> ConeF(TEXT("/Engine/BasicShapes/Cone.Cone"));
	Glow = ISM(TEXT("Glow"), CubeMesh, false);
	Cones = ISM(TEXT("Cones"), ConeF.Object, false);
	Containers = ISM(TEXT("Containers"), CubeMesh, true);
	Chimneys = ISM(TEXT("Chimneys"), CylMesh, true);
	for (UInstancedStaticMeshComponent* C : { Cars.Get(), TreeTrunks.Get(), TreeCrowns.Get(), Lamps.Get(), Containers.Get(), Glow.Get(), Cones.Get() })
	{
		C->NumCustomDataFloats = 3;
	}
	Signs = ISM(TEXT("Signs"), CubeMesh, false);
	TrimBox = ISM(TEXT("TrimBox"), CubeMesh, false);
	TrimBall = ISM(TEXT("TrimBall"), SphereMesh, false);
	ConcCyl = ISM(TEXT("ConcCyl"), CylMesh, false);
	ExtraGlass = ISM(TEXT("ExtraGlass"), CubeMesh, false);
	ExtraConc = ISM(TEXT("ExtraConc"), CubeMesh, false);
	Signs->NumCustomDataFloats = 10;
	TrimBox->NumCustomDataFloats = 5;
	TrimBall->NumCustomDataFloats = 5;
	ConcCyl->NumCustomDataFloats = 4;
	ExtraGlass->NumCustomDataFloats = 4;
	ExtraConc->NumCustomDataFloats = 4;
	Concrete->NumCustomDataFloats = 4;
	Glass->NumCustomDataFloats = 4;
	for (UInstancedStaticMeshComponent* C : { Signs.Get(), TrimBox.Get(), TrimBall.Get() }) { C->SetCastShadow(false); }
	PrimaryActorTick.bCanEverTick = true;

	Terrain = CreateDefaultSubobject<UProceduralMeshComponent>(TEXT("Terrain"));
	Terrain->SetupAttachment(Root);
	Terrain->bUseComplexAsSimpleCollision = true;
	Terrain->SetCollisionProfileName(TEXT("BlockAll"));
	Roads = CreateDefaultSubobject<UProceduralMeshComponent>(TEXT("Roads"));
	Roads->SetupAttachment(Root);
	Roads->SetCollisionEnabled(ECollisionEnabled::NoCollision);

	Sea = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Sea"));
	Sea->SetupAttachment(Root);
	Sea->SetStaticMesh(CubeMesh);
	Sea->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	Sea->SetCastShadow(false);
}

UMaterialInstanceDynamic* AIVDistrict::MakeMID(const TCHAR* Path, UMaterialInterface* Fallback)
{
	UMaterialInterface* M = LoadObject<UMaterialInterface>(nullptr, Path);
	if (!M) M = Fallback;
	return M ? UMaterialInstanceDynamic::Create(M, this) : nullptr;
}

double AIVDistrict::HeightM(int32 Col, int32 Row) const
{
	Col = FMath::Clamp(Col, 0, Res - 1);
	Row = FMath::Clamp(Row, 0, Res - 1);
	return (double(Heights[Row * Res + Col]) - 32768.0) / 128.0;
}

double AIVDistrict::SampleHeightM(double Xd, double Yd) const
{
	if (Res <= 1) return 0.0;
	const double Fc = (Xd - XMin) / CellM, Fr = (Yd - YMin) / CellM;
	const int32 C0 = FMath::FloorToInt(Fc), R0 = FMath::FloorToInt(Fr);
	const double Tc = Fc - C0, Tr = Fr - R0;
	const double A = FMath::Lerp(HeightM(C0, R0), HeightM(C0 + 1, R0), Tc);
	const double B = FMath::Lerp(HeightM(C0, R0 + 1), HeightM(C0 + 1, R0 + 1), Tc);
	return FMath::Lerp(A, B, Tr);
}

float AIVDistrict::SampleHeightCm(float XUe, float YUe) const
{
	return float(SampleHeightM(YUe / 100.0, XUe / 100.0) * 100.0);   // x_d = Y_ue/100, y_d = X_ue/100
}

bool AIVDistrict::GetPoi(const FString& Id, FVector& OutLoc, float& OutYaw) const
{
	if (const TPair<FVector, float>* P = Pois.Find(Id)) { OutLoc = P->Key; OutYaw = P->Value; return true; }
	return false;
}

bool AIVDistrict::Load(const FString& JsonPath, const FString& HeightPath)
{
	FString Text;
	TArray<uint8> Raw;
	if (!FFileHelper::LoadFileToString(Text, *JsonPath) || !FFileHelper::LoadFileToArray(Raw, *HeightPath))
	{
		UE_LOG(LogTemp, Warning, TEXT("IV district: missing %s or %s"), *JsonPath, *HeightPath);
		return false;
	}
	TSharedPtr<FJsonObject> Rootj;
	if (!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text), Rootj) || !Rootj.IsValid())
	{
		UE_LOG(LogTemp, Warning, TEXT("IV district: bad json"));
		return false;
	}
	const TSharedPtr<FJsonObject> T = Rootj->GetObjectField(TEXT("terrain"));
	Res = int32(T->GetNumberField(TEXT("resolution")));
	const TSharedPtr<FJsonObject> Ext = T->GetObjectField(TEXT("extent"));
	XMin = Ext->GetNumberField(TEXT("x_min"));
	YMin = Ext->GetNumberField(TEXT("y_min"));
	CellM = T->GetNumberField(TEXT("cell_size_m"));
	if (Raw.Num() < Res * Res * 2) { UE_LOG(LogTemp, Warning, TEXT("IV district: heightmap too small")); return false; }
	Heights.SetNumUninitialized(Res * Res);
	FMemory::Memcpy(Heights.GetData(), Raw.GetData(), Res * Res * 2);

	// facade materials
	UMaterialInterface* Fb = LoadObject<UMaterialInterface>(nullptr, TEXT("/Engine/BasicShapes/BasicShapeMaterial.BasicShapeMaterial"));
	FacadeConcrete = MakeMID(TEXT("/Game/Materials/M_BuildingFacade.M_BuildingFacade"), Fb);
	FacadeGlass = MakeMID(TEXT("/Game/Materials/M_BuildingFacade.M_BuildingFacade"), Fb);
	if (FacadeConcrete)
	{
		FacadeConcrete->SetVectorParameterValue(TEXT("Tint"), FLinearColor(0.2f, 0.21f, 0.22f));
		FacadeConcrete->SetVectorParameterValue(TEXT("GlassColor"), FLinearColor(0.03f, 0.045f, 0.06f));
		FacadeConcrete->SetScalarParameterValue(TEXT("Glassiness"), 0.5f);
		Concrete->SetMaterial(0, FacadeConcrete);
		Hero->SetMaterial(0, FacadeConcrete);
		Containers->SetMaterial(0, FacadeConcrete);
		Chimneys->SetMaterial(0, FacadeConcrete);
	}
	if (FacadeGlass)
	{
		FacadeGlass->SetVectorParameterValue(TEXT("Tint"), FLinearColor(0.07f, 0.1f, 0.13f));
		FacadeGlass->SetVectorParameterValue(TEXT("GlassColor"), FLinearColor(0.02f, 0.05f, 0.08f));
		FacadeGlass->SetScalarParameterValue(TEXT("WindowSpacing"), 330.f);
		FacadeGlass->SetScalarParameterValue(TEXT("Glassiness"), 0.9f);
		Glass->SetMaterial(0, FacadeGlass);
	}
	if (UMaterialInstanceDynamic* Gt = MakeMID(TEXT("/Game/Materials/M_GlassTower.M_GlassTower"), nullptr))
	{
		FacadeGlass = Gt;
		Glass->SetMaterial(0, Gt);
		ExtraGlass->SetMaterial(0, Gt);
	}
	if (FacadeConcrete) ExtraConc->SetMaterial(0, FacadeConcrete), ConcCyl->SetMaterial(0, FacadeConcrete);
	if (UMaterialInstanceDynamic* Ns = MakeMID(TEXT("/Game/Materials/M_NeonSign.M_NeonSign"), Fb)) Signs->SetMaterial(0, Ns);
	if (UMaterialInstanceDynamic* Tr = MakeMID(TEXT("/Game/Materials/M_Trim.M_Trim"), Fb)) { TrimBox->SetMaterial(0, Tr); TrimBall->SetMaterial(0, Tr); }
	if (UMaterialInstanceDynamic* Prop = MakeMID(TEXT("/Game/Materials/M_PropColor.M_PropColor"), Fb))
	{
		for (UInstancedStaticMeshComponent* C : { Cars.Get(), TreeTrunks.Get(), TreeCrowns.Get(), Lamps.Get(), Cones.Get() })
		{
			C->SetMaterial(0, Prop);
		}
	}
	if (UMaterialInstanceDynamic* Gl = MakeMID(TEXT("/Game/Materials/M_PropGlow.M_PropGlow"), Fb)) Glow->SetMaterial(0, Gl);
	Glow->SetCastShadow(false);

	// POIs
	for (const TSharedPtr<FJsonValue>& V : Rootj->GetArrayField(TEXT("pois")))
	{
		const TSharedPtr<FJsonObject> O = V->AsObject();
		const TArray<TSharedPtr<FJsonValue>>& P = O->GetArrayField(TEXT("pos"));
		const FVector Loc = ToUE(P[0]->AsNumber(), P[1]->AsNumber(), P[2]->AsNumber());
		const double Yd = O->HasField(TEXT("yaw_deg")) ? O->GetNumberField(TEXT("yaw_deg")) : 0.0;
		Pois.Add(O->GetStringField(TEXT("id")), TPair<FVector, float>(Loc, YawToUE(float(Yd))));
	}

	bArena = Rootj->HasField(TEXT("arena"));
	BuildTerrain();
	BuildRoads(Rootj->GetArrayField(TEXT("roads")));
	BuildBuildings(Rootj->GetArrayField(TEXT("buildings")));
	BuildProps(Rootj->GetArrayField(TEXT("props")));
	BuildDecor(Rootj);
	if (Rootj->HasTypedField<EJson::Object>(TEXT("infrastructure"))) BuildPort(Rootj->GetObjectField(TEXT("infrastructure")));

	// sea slab: top at z = 0, covers the sea and runs under the land
	if (UMaterialInstanceDynamic* SeaM = MakeMID(TEXT("/Game/Materials/M_Sea.M_Sea"), Fb)) Sea->SetMaterial(0, SeaM);
	Sea->SetRelativeLocation(FVector(-150000.0, 0, -150));
	Sea->SetRelativeScale3D(FVector(3000.0, 4200.0, 3.0));       // 3 km x 4.2 km, 3 m thick

	bLoaded = true;
	UE_LOG(LogTemp, Display, TEXT("IV district loaded: %d buildings, %d pois"), Buildings.Num(), Pois.Num());
	return true;
}

void AIVDistrict::BuildTerrain()
{
	const int32 Stride = 3;
	const int32 Quads = (Res - 1) / Stride;          // 336
	const int32 Sections = 4;
	const int32 QPer = Quads / Sections;             // 84
	UMaterialInstanceDynamic* GroundM = MakeMID(TEXT("/Game/Materials/M_WetGround.M_WetGround"), nullptr);
	if (GroundM)
	{
		GroundM->SetVectorParameterValue(TEXT("BaseTint"), bArena ? FLinearColor(0.05f, 0.052f, 0.06f) : FLinearColor(0.11f, 0.115f, 0.12f));
		GroundM->SetScalarParameterValue(TEXT("Wetness"), bArena ? 0.55f : 0.35f);
		GroundM->SetScalarParameterValue(TEXT("UseVertexColor"), bArena ? 0.f : 1.f);
		GroundM->SetScalarParameterValue(TEXT("Layout"), bArena ? 1.f : 0.f);
		Terrain->SetMaterial(0, GroundM);
	}

	int32 SectionIndex = 0;
	for (int32 sy = 0; sy < Sections; ++sy)
	{
		for (int32 sx = 0; sx < Sections; ++sx)
		{
			TArray<FVector> V; TArray<FVector> N; TArray<FVector2D> UV; TArray<FLinearColor> Col; TArray<int32> Tri; TArray<FProcMeshTangent> Tan;
			const int32 Verts1 = QPer + 1;
			V.Reserve(Verts1 * Verts1);
			for (int32 r = 0; r <= QPer; ++r)
			{
				for (int32 c = 0; c <= QPer; ++c)
				{
					const int32 Col0 = (sx * QPer + c) * Stride, Row0 = (sy * QPer + r) * Stride;
					const double Xd = XMin + Col0 * CellM, Yd = YMin + Row0 * CellM;
					const double Z = HeightM(Col0, Row0);
					V.Add(ToUE(Xd, Yd, Z));
					const double Dzdx = (HeightM(Col0 + Stride, Row0) - HeightM(Col0 - Stride, Row0)) / (2.0 * Stride * CellM);
					const double Dzdy = (HeightM(Col0, Row0 + Stride) - HeightM(Col0, Row0 - Stride)) / (2.0 * Stride * CellM);
					const FVector Nd(-Dzdx, -Dzdy, 1.0);                // district frame
					N.Add(FVector(Nd.Y, Nd.X, Nd.Z).GetSafeNormal());   // swapped into UE frame
					UV.Add(FVector2D(Xd / 20.0, Yd / 20.0));
					// sand on the beach, plain concrete elsewhere
					const float Sand = FMath::Clamp(float((2.4 - Z) / 1.2), 0.f, 1.f) * FMath::Clamp(float((Z + 8.0) / 3.0), 0.f, 1.f);
					Col.Add(FLinearColor(0.55f, 0.5f, 0.38f, Sand));
				}
			}
			for (int32 r = 0; r < QPer; ++r)
			{
				for (int32 c = 0; c < QPer; ++c)
				{
					const int32 i00 = r * Verts1 + c, i10 = i00 + 1, i01 = i00 + Verts1, i11 = i01 + 1;
					// district-CCW (x right, y fwd) == UE front-facing after the axis swap
					Tri.Add(i00); Tri.Add(i10); Tri.Add(i11);
					Tri.Add(i00); Tri.Add(i11); Tri.Add(i01);
				}
			}
			Terrain->CreateMeshSection_LinearColor(SectionIndex, V, Tri, N, UV, Col, Tan, true);
			if (GroundM) Terrain->SetMaterial(SectionIndex, GroundM);
			++SectionIndex;
		}
	}
}

void AIVDistrict::BuildRoads(const TArray<TSharedPtr<FJsonValue>>& RoadsJson)
{
	UMaterialInstanceDynamic* RoadM = MakeMID(TEXT("/Game/Materials/M_WetGround.M_WetGround"), nullptr);
	if (RoadM)
	{
		RoadM->SetVectorParameterValue(TEXT("BaseTint"), FLinearColor(0.032f, 0.034f, 0.038f));
		RoadM->SetScalarParameterValue(TEXT("Wetness"), 0.8f);
	}
	int32 Sec = 0;
	for (const TSharedPtr<FJsonValue>& RV : RoadsJson)
	{
		const TSharedPtr<FJsonObject> R = RV->AsObject();
		const double Width = R->GetNumberField(TEXT("width"));
		TArray<FVector2D> Pts;
		for (const TSharedPtr<FJsonValue>& PV : R->GetArrayField(TEXT("points"))) Pts.Add(P2(PV));
		// densify to ~12 m so the strip follows the terrain
		TArray<FVector2D> Dense;
		for (int32 i = 0; i + 1 < Pts.Num(); ++i)
		{
			const double Len = FVector2D::Distance(Pts[i], Pts[i + 1]);
			const int32 N = FMath::Max(1, FMath::CeilToInt(Len / 12.0));
			for (int32 k = 0; k < N; ++k) Dense.Add(FMath::Lerp(Pts[i], Pts[i + 1], double(k) / N));
		}
		if (Pts.Num() > 0) Dense.Add(Pts.Last());
		if (Dense.Num() < 2) continue;

		TArray<FVector> V; TArray<FVector> Nrm; TArray<FVector2D> UV; TArray<FLinearColor> Col; TArray<int32> Tri; TArray<FProcMeshTangent> Tan;
		for (int32 i = 0; i < Dense.Num(); ++i)
		{
			const FVector2D A = Dense[FMath::Max(0, i - 1)], B = Dense[FMath::Min(Dense.Num() - 1, i + 1)];
			FVector2D Tg = (B - A).GetSafeNormal();
			const FVector2D Nl(-Tg.Y, Tg.X);
			for (int32 s = -1; s <= 1; s += 2)
			{
				const FVector2D P = Dense[i] + Nl * (Width * 0.5 * s);
				V.Add(ToUE(P.X, P.Y, SampleHeightM(P.X, P.Y) + 0.07));
				Nrm.Add(FVector::UpVector);
				UV.Add(FVector2D(s > 0 ? 1.f : 0.f, i * 0.1f));
				Col.Add(FLinearColor(0, 0, 0, 0));
			}
		}
		for (int32 i = 0; i + 1 < Dense.Num(); ++i)
		{
			const int32 a = i * 2, b = a + 1, c = a + 2, d = a + 3;
			// strip: left(a) right(b) next-left(c) next-right(d); orient front-facing upward
			Tri.Add(a); Tri.Add(c); Tri.Add(b);
			Tri.Add(b); Tri.Add(c); Tri.Add(d);
		}
		Roads->CreateMeshSection_LinearColor(Sec, V, Tri, Nrm, UV, Col, Tan, false);
		if (RoadM) Roads->SetMaterial(Sec, RoadM);
		++Sec;
	}
}

void AIVDistrict::BuildBuildings(const TArray<TSharedPtr<FJsonValue>>& BuildingsJson)
{
	UMaterialInterface* Fb = LoadObject<UMaterialInterface>(nullptr, TEXT("/Engine/BasicShapes/BasicShapeMaterial.BasicShapeMaterial"));
	for (const TSharedPtr<FJsonValue>& BV : BuildingsJson)
	{
		const TSharedPtr<FJsonObject> B = BV->AsObject();
		const FString Id = B->GetStringField(TEXT("id"));
		const FString Type = B->GetStringField(TEXT("type"));
		const FString Kind = (Type == TEXT("hero")) ? B->GetStringField(TEXT("hero_kind")) : B->GetStringField(TEXT("building_type"));
		if (Kind == TEXT("overpass") || Kind == TEXT("crane") || Kind == TEXT("port_crane")) { BuildHeroStatics(B); continue; }

		TArray<FVector2D> Poly;
		for (const TSharedPtr<FJsonValue>& PV : B->GetArrayField(TEXT("footprint"))) Poly.Add(ToUE2(P2(PV)));
		if (Poly.Num() < 3) continue;
		const double BaseZ = B->GetNumberField(TEXT("base_z")), Height = B->GetNumberField(TEXT("height"));

		// oriented frame: quads use their first edge, polygons use yaw_deg
		FVector2D Centroid(0, 0);
		for (const FVector2D& P : Poly) Centroid += P;
		Centroid /= Poly.Num();
		float YawUe;
		if (Poly.Num() == 4) YawUe = FMath::RadiansToDegrees(FMath::Atan2(Poly[1].Y - Poly[0].Y, Poly[1].X - Poly[0].X));
		else YawUe = YawToUE(float(B->GetNumberField(TEXT("yaw_deg"))));
		const FVector2D Ax = FVector2D(FMath::Cos(FMath::DegreesToRadians(YawUe)), FMath::Sin(FMath::DegreesToRadians(YawUe)));
		const FVector2D Ay(-Ax.Y, Ax.X);
		FVector2D Mn(1e12, 1e12), Mx(-1e12, -1e12);
		TArray<FVector2D> Local;
		for (const FVector2D& P : Poly)
		{
			const FVector2D D = P - Centroid;
			const FVector2D L(D | Ax, D | Ay);
			Local.Add(L);
			Mn.X = FMath::Min(Mn.X, L.X); Mn.Y = FMath::Min(Mn.Y, L.Y);
			Mx.X = FMath::Max(Mx.X, L.X); Mx.Y = FMath::Max(Mx.Y, L.Y);
		}
		const FVector2D MidL = (Mn + Mx) * 0.5;
		const FVector2D Mid = Centroid + Ax * MidL.X + Ay * MidL.Y;
		for (FVector2D& L : Local) L -= MidL;      // polygon relative to box centre
		FIVDistrictBuilding D;
		D.Id = Id;
		D.YawDeg = YawUe;
		D.Size = FVector(Mx.X - Mn.X, Mx.Y - Mn.Y, (Height + 3.0) * 100.0);
		D.Center = FVector(Mid.X, Mid.Y, (BaseZ - 3.0) * 100.0 + D.Size.Z * 0.5);
		D.bHero = (Type == TEXT("hero"));
		const FString Facade = B->GetStringField(TEXT("facade_style"));
		D.bGlass = Facade.Contains(TEXT("glass")) || Kind == TEXT("glass_tower");
		{
			FString Style;
			if (B->TryGetStringField(TEXT("style"), Style)) { D.StyleId = Style == TEXT("glass_tower") ? 1 : (Style == TEXT("shop") ? 2 : 0); D.bGlass = (D.StyleId == 1); }
			const TArray<TSharedPtr<FJsonValue>>* Tn = nullptr;
			if (B->TryGetArrayField(TEXT("tint"), Tn) && Tn->Num() >= 3) D.Tint = FLinearColor((*Tn)[0]->AsNumber(), (*Tn)[1]->AsNumber(), (*Tn)[2]->AsNumber());
			B->TryGetStringField(TEXT("crown"), D.Crown);
			D.Seed = float(FCrc::StrCrc32(*Id) % 1000) / 1000.f;
		}

		const bool bQuad = (Poly.Num() == 4);
		if (bQuad && !D.bHero)
		{
			Buildings.Add(D);          // intact: one cube instance until the first hit
		}
		else
		{
			// complex footprint / hero: voxel building from the start (coarser cells)
			AIVBuilding* Bld = GetWorld()->SpawnActor<AIVBuilding>(FVector::ZeroVector, FRotator::ZeroRotator);
			if (!Bld) continue;
			const float Cell = FMath::Clamp(FMath::Max(D.Size.X, D.Size.Y) / 22.f, 600.f, 1300.f);
			const float Hollow = (Kind == TEXT("stadium")) ? 0.62f : 0.f;
			Bld->Init(D.Center, D.YawDeg, D.Size, D.bGlass ? Cast<UMaterialInterface>(FacadeGlass) : Cast<UMaterialInterface>(FacadeConcrete), Cell, bQuad ? TArray<FVector2D>() : Local, Hollow);
			D.Actor = Bld;
			D.bActive = true;
			Buildings.Add(D);
			if (Kind == TEXT("power_station") && B->HasField(TEXT("parts")))
			{
				for (const TSharedPtr<FJsonValue>& PV : B->GetArrayField(TEXT("parts")))
				{
					const TSharedPtr<FJsonObject> Pt = PV->AsObject();
					if (Pt->GetStringField(TEXT("kind")) != TEXT("chimney")) continue;
					const TArray<TSharedPtr<FJsonValue>>& Pa = Pt->GetArrayField(TEXT("pos"));
					const FVector2D C = ToUE2(FVector2D(Pa[0]->AsNumber(), Pa[1]->AsNumber()));
					const double Rm = Pt->GetNumberField(TEXT("radius")), Hm = Pt->GetNumberField(TEXT("height"));
					Chimneys->AddInstance(FTransform(FRotator::ZeroRotator, FVector(C.X, C.Y, (BaseZ + Hm * 0.5) * 100.0), FVector(Rm * 2.0, Rm * 2.0, Hm)));
				}
			}
		}
	}
	RebuildStaticInstances();
	Hero->AddInstances(HeroStaticTransforms, false, true);
}

void AIVDistrict::RebuildStaticInstances()
{
	Concrete->ClearInstances();
	Glass->ClearInstances();
	TArray<FTransform> C, G;
	TArray<const FIVDistrictBuilding*> CB, GB;
	for (const FIVDistrictBuilding& D : Buildings)
	{
		if (D.bActive) continue;
		const FTransform T(FRotator(0, D.YawDeg, 0), D.Center, D.Size / 100.f);
		if (D.bGlass) { G.Add(T); GB.Add(&D); } else { C.Add(T); CB.Add(&D); }
	}
	auto Fill = [](UInstancedStaticMeshComponent* Comp, const TArray<FTransform>& Tr, const TArray<const FIVDistrictBuilding*>& Bl)
	{
		if (Tr.Num() == 0) return;
		Comp->AddInstances(Tr, false, true);
		for (int32 i = 0; i < Bl.Num(); ++i)
		{
			const float CD[4] = { Bl[i]->Tint.R, Bl[i]->Tint.G, Bl[i]->Tint.B, Bl[i]->Seed };
			Comp->SetCustomData(i, MakeArrayView(CD, 4), false);
		}
		Comp->MarkRenderStateDirty();
	};
	Fill(Concrete, C, CB);
	Fill(Glass, G, GB);
	if (bLoaded) RebuildDeco();
}

void AIVDistrict::BuildHeroStatics(const TSharedPtr<FJsonObject>& B)
{
	const FString Kind = B->GetStringField(TEXT("hero_kind"));
	const double BaseZ = B->GetNumberField(TEXT("base_z"));
	auto Box = [&](const FVector2D& CUe, double Z0, double Z1, double Sx, double Sy, float YawUe)
	{
		HeroStaticTransforms.Add(FTransform(FRotator(0, YawUe, 0), FVector(CUe.X, CUe.Y, (Z0 + Z1) * 50.0), FVector(Sx, Sy, (Z1 - Z0) * 100.0) / 100.f));
	};
	TArray<FVector2D> Poly;
	for (const TSharedPtr<FJsonValue>& PV : B->GetArrayField(TEXT("footprint"))) Poly.Add(ToUE2(P2(PV)));
	if (Kind == TEXT("overpass"))
	{
		const double DeckZ = B->GetNumberField(TEXT("deck_z")), Len = B->GetNumberField(TEXT("length")), W = B->GetNumberField(TEXT("width"));
		FVector2D Mid(0, 0);
		for (const FVector2D& P : Poly) Mid += P;
		Mid /= Poly.Num();
		const float Yaw = FMath::RadiansToDegrees(FMath::Atan2(Poly[1].Y - Poly[0].Y, Poly[1].X - Poly[0].X));
		// the first footprint edge is the short end edge (across the deck); the deck runs along the perpendicular
		const FVector2D EdgeA = Poly[1] - Poly[0], EdgeB = Poly[3] - Poly[0];
		const bool bAcross = EdgeA.Size() < EdgeB.Size();
		const FVector2D Along = (bAcross ? EdgeB : EdgeA).GetSafeNormal();
		const float DeckYaw = FMath::RadiansToDegrees(FMath::Atan2(Along.Y, Along.X));
		HeroStaticTransforms.Add(FTransform(FRotator(0, DeckYaw, 0), FVector(Mid.X, Mid.Y, (DeckZ - 1.0) * 100.0), FVector(Len * 100.0, W * 100.0, 200.0) / 100.f));
		// parapets
		const FVector2D Side(-Along.Y, Along.X);
		for (int32 s = -1; s <= 1; s += 2)
		{
			const FVector2D P = Mid + Side * (W * 50.0 * s);
			HeroStaticTransforms.Add(FTransform(FRotator(0, DeckYaw, 0), FVector(P.X, P.Y, (DeckZ + 0.6) * 100.0), FVector(Len * 100.0, 60.0, 120.0) / 100.f));
		}
		for (const TSharedPtr<FJsonValue>& CV : B->GetObjectField(TEXT("structure"))->GetArrayField(TEXT("columns")))
		{
			const TSharedPtr<FJsonObject> Co = CV->AsObject();
			const TArray<TSharedPtr<FJsonValue>>& P = Co->GetArrayField(TEXT("pos"));
			const FVector2D C = ToUE2(FVector2D(P[0]->AsNumber(), P[1]->AsNumber()));
			const double Z0 = P[2]->AsNumber() - 3.0;
			Box(C, Z0, DeckZ - 2.0, 380, 380, DeckYaw);
		}
	}
	else    // port crane: portal frame + boom
	{
		const double H = B->GetNumberField(TEXT("height"));
		FVector2D Mid(0, 0);
		for (const FVector2D& P : Poly) Mid += P;
		Mid /= Poly.Num();
		const float Yaw = FMath::RadiansToDegrees(FMath::Atan2(Poly[1].Y - Poly[0].Y, Poly[1].X - Poly[0].X));
		for (const FVector2D& P : Poly)
		{
			const FVector2D Leg = Mid + (P - Mid) * 0.82;
			Box(Leg, BaseZ - 2.0, BaseZ + H * 0.82, 360, 360, Yaw);
		}
		Box(Mid, BaseZ + H * 0.78, BaseZ + H * 0.86, (Poly[1] - Poly[0]).Size() * 0.9, (Poly[3] - Poly[0]).Size() * 0.95, Yaw);
		Box(Mid, BaseZ + H * 0.9, BaseZ + H, (Poly[1] - Poly[0]).Size() * 0.5, (Poly[3] - Poly[0]).Size() * 0.6, Yaw);
		if (B->HasField(TEXT("parts")))
		{
			for (const TSharedPtr<FJsonValue>& PV : B->GetArrayField(TEXT("parts")))
			{
				const TSharedPtr<FJsonObject> Pt = PV->AsObject();
				if (Pt->GetStringField(TEXT("kind")) != TEXT("boom")) continue;
				const TArray<TSharedPtr<FJsonValue>>& Fa = Pt->GetArrayField(TEXT("from"));
				const TArray<TSharedPtr<FJsonValue>>& Ta = Pt->GetArrayField(TEXT("to"));
				const FVector2D F = ToUE2(FVector2D(Fa[0]->AsNumber(), Fa[1]->AsNumber()));
				const FVector2D T = ToUE2(FVector2D(Ta[0]->AsNumber(), Ta[1]->AsNumber()));
				const FVector2D Dir = (T - F);
				const FVector2D C = (T + F) * 0.5;
				const float BY = FMath::RadiansToDegrees(FMath::Atan2(Dir.Y, Dir.X));
				const double Hh = Pt->GetNumberField(TEXT("height"));
				HeroStaticTransforms.Add(FTransform(FRotator(0, BY, 0), FVector(C.X, C.Y, (BaseZ + Hh) * 100.0), FVector(Dir.Size(), 420.0, 420.0) / 100.f));
			}
		}
	}
}

void AIVDistrict::BuildProps(const TArray<TSharedPtr<FJsonValue>>& PropsJson)
{
	// Street furniture and traffic are assembled from boxes, cylinders and spheres (paint ISMs) plus glowing parts (Glow ISM). All sizes in cm,
	// local frame: +X forward (the way a car drives / a kiosk faces), +Y right, Z up from the ground.
	static const FLinearColor Neon[] = { FLinearColor(1.f, 0.12f, 0.45f), FLinearColor(0.08f, 0.85f, 1.f), FLinearColor(1.f, 0.6f, 0.08f), FLinearColor(0.2f, 1.f, 0.4f), FLinearColor(0.6f, 0.3f, 1.f) };
	static const FLinearColor Cloth[] = { FLinearColor(0.02f, 0.02f, 0.025f), FLinearColor(0.05f, 0.05f, 0.07f), FLinearColor(0.12f, 0.03f, 0.03f), FLinearColor(0.03f, 0.07f, 0.12f), FLinearColor(0.1f, 0.1f, 0.1f), FLinearColor(0.15f, 0.12f, 0.04f) };
	const FLinearColor Dark(0.015f, 0.016f, 0.02f), Conc(0.2f, 0.2f, 0.215f), GlassC(0.008f, 0.012f, 0.018f);
	int32 Seed = 0;
	for (const TSharedPtr<FJsonValue>& PV : PropsJson)
	{
		const TSharedPtr<FJsonObject> P = PV->AsObject();
		const FString Kind = P->GetStringField(TEXT("kind"));
		const TArray<TSharedPtr<FJsonValue>>& Pos = P->GetArrayField(TEXT("pos"));
		const FVector Loc = ToUE(Pos[0]->AsNumber(), Pos[1]->AsNumber(), Pos[2]->AsNumber());
		const float Yaw = YawToUE(float(P->HasField(TEXT("yaw_deg")) ? P->GetNumberField(TEXT("yaw_deg")) : 0.0));
		const FString Var = P->HasField(TEXT("variant")) ? P->GetStringField(TEXT("variant")) : FString();
		++Seed;
		FRandomStream Rs(Seed * 7919 + 13);
		const FQuat Q = FRotator(0, Yaw, 0).Quaternion();
		auto SetCol = [](UInstancedStaticMeshComponent* C, int32 Index, const FLinearColor& Col)
		{
			C->SetCustomDataValue(Index, 0, Col.R, false);
			C->SetCustomDataValue(Index, 1, Col.G, false);
			C->SetCustomDataValue(Index, 2, Col.B, false);
		};
		// one part: component, local centre (relative to the ground point), full size, colour, extra local rotation
		auto Part = [&](UInstancedStaticMeshComponent* C, const FVector& Local, const FVector& Size, const FLinearColor& Col, float LYaw = 0.f, float LPitch = 0.f, float LRoll = 0.f)
		{
			const FQuat Qp = Q * FRotator(LPitch, LYaw, LRoll).Quaternion();
			const int32 I = C->AddInstance(FTransform(Qp, Loc + Q.RotateVector(Local), Size / 100.f));
			SetCol(C, I, Col);
		};
		const FLinearColor Accent = Neon[Rs.RandRange(0, 4)];
		if (Kind == TEXT("car"))
		{
			const FVector S = CarSize(Var);
			const FLinearColor Body = CarColor(Var, Seed * 7919);
			const float H0 = 28.f;
			const bool bBig = (Var == TEXT("bus") || Var == TEXT("truck") || Var == TEXT("van"));
			if (bBig)
			{
				Part(Cars, FVector(0, 0, H0 + (S.Z - H0) * 0.5f), FVector(S.X, S.Y, S.Z - H0), Body);
				if (Var == TEXT("truck")) Part(Cars, FVector(S.X * 0.36f, 0, H0 + (S.Z - H0) * 0.2f), FVector(S.X * 0.28f, S.Y * 1.02f, (S.Z - H0) * 0.42f), GlassC);
				else Part(Cars, FVector(0, 0, H0 + (S.Z - H0) * 0.68f), FVector(S.X * 0.94f, S.Y * 1.012f, (S.Z - H0) * 0.3f), GlassC);
				if (Var == TEXT("bus")) Part(Glow, FVector(S.X * 0.5f, 0, S.Z * 0.9f), FVector(8, S.Y * 0.5f, 22), FLinearColor(1.f, 0.55f, 0.1f));
			}
			else
			{
				Part(Cars, FVector(0, 0, H0 + S.Z * 0.25f), FVector(S.X, S.Y, S.Z * 0.5f), Body);
				Part(Cars, FVector(-S.X * 0.06f, 0, H0 + S.Z * 0.5f + S.Z * 0.2f), FVector(S.X * 0.52f, S.Y * 0.9f, S.Z * 0.42f), GlassC);
				Part(Cars, FVector(-S.X * 0.06f, 0, H0 + S.Z * 0.5f + S.Z * 0.42f), FVector(S.X * 0.5f, S.Y * 0.88f, 6.f), Body);
				if (Var == TEXT("taxi")) Part(Glow, FVector(-S.X * 0.06f, 0, H0 + S.Z * 0.5f + S.Z * 0.42f + 14.f), FVector(55, 28, 16), FLinearColor(1.f, 0.7f, 0.1f));
			}
			for (int32 sx = -1; sx <= 1; sx += 2)
				for (int32 sy = -1; sy <= 1; sy += 2)
					Part(Lamps, FVector(sx * S.X * 0.32f, sy * S.Y * 0.47f, 38.f), FVector(76, 76, 28), Dark, 0.f, 0.f, 90.f);
			for (int32 sy = -1; sy <= 1; sy += 2)
			{
				Part(Glow, FVector(S.X * 0.5f, sy * S.Y * 0.3f, H0 + S.Z * 0.28f), FVector(10, S.Y * 0.22f, 16), FLinearColor(1.f, 0.93f, 0.75f));
				Part(Glow, FVector(-S.X * 0.5f, sy * S.Y * 0.3f, H0 + S.Z * 0.3f), FVector(10, S.Y * 0.22f, 14), FLinearColor(1.f, 0.03f, 0.02f));
			}
		}
		else if (Kind == TEXT("tree"))
		{
			const float H = 380.f + 60.f * (Seed % 5);
			Part(Lamps, FVector(0, 0, 25), FVector(150, 150, 50), Conc);                           // planter
			Part(TreeTrunks, FVector(0, 0, H * 0.5f), FVector(55, 55, H), FLinearColor(0.06f, 0.04f, 0.03f));
			const FLinearColor Leaf(0.02f + 0.01f * (Seed % 3), 0.07f + 0.02f * (Seed % 4), 0.035f);
			for (int32 k = 0; k < 4; ++k)
			{
				const float R = 260.f + 60.f * Rs.FRand();
				Part(TreeCrowns, FVector(Rs.FRandRange(-120.f, 120.f), Rs.FRandRange(-120.f, 120.f), H + 120.f + Rs.FRandRange(-60.f, 160.f)), FVector(R, R, R * 0.8f), Leaf * Rs.FRandRange(0.8f, 1.3f));
			}
			if (Seed % 3 == 0) Part(Glow, FVector(0, 0, 60), FVector(190, 190, 6), Accent * 0.5f);   // uplight ring
		}
		else if (Kind == TEXT("lamp"))
		{
			Part(Lamps, FVector(0, 0, 450), FVector(28, 28, 900), Dark);
			Part(Cars, FVector(110, 0, 893), FVector(230, 16, 16), Dark);
			Part(Glow, FVector(215, 0, 878), FVector(110, 46, 10), (Seed % 2) ? FLinearColor(1.f, 0.62f, 0.3f) : FLinearColor(0.45f, 0.85f, 1.f));
		}
		else if (Kind == TEXT("barrier"))
		{
			Part(Cars, FVector(0, 0, 47), FVector(300, 70, 95), Conc);
			Part(Cars, FVector(0, 0, 80), FVector(302, 72, 16), FLinearColor(0.9f, 0.3f, 0.02f));
			if (Seed % 2) Part(Glow, FVector(140, 0, 106), FVector(24, 24, 18), FLinearColor(1.f, 0.55f, 0.05f));
		}
		else if (Kind == TEXT("cone"))
		{
			Part(Cones, FVector(0, 0, 35), FVector(42, 42, 70), FLinearColor(0.9f, 0.22f, 0.02f));
		}
		else if (Kind == TEXT("dumpster"))
		{
			Part(Cars, FVector(0, 0, 68), FVector(240, 110, 116), Seed % 2 ? FLinearColor(0.03f, 0.12f, 0.06f) : FLinearColor(0.03f, 0.06f, 0.16f));
			Part(Cars, FVector(0, 0, 130), FVector(246, 116, 10), Dark);
		}
		else if (Kind == TEXT("kiosk"))
		{
			Part(Cars, FVector(0, 0, 125), FVector(300, 260, 250), Cloth[Seed % 6] * 2.f);
			Part(Cars, FVector(0, 0, 255), FVector(330, 290, 12), Dark);
			Part(Cars, FVector(190, 0, 225), FVector(110, 280, 10), Accent * 0.35f, 0.f, 14.f);                     // awning
			Part(Glow, FVector(152, 0, 150), FVector(6, 240, 90), Accent);                                          // lit window
			Part(Glow, FVector(100, 0, 287), FVector(8, 220, 40), Neon[(Seed + 2) % 5]);                            // roof sign
		}
		else if (Kind == TEXT("busstop"))
		{
			for (int32 sy = -1; sy <= 1; sy += 2) Part(Lamps, FVector(0, sy * 160.f, 130), FVector(10, 10, 260), Dark);
			Part(Cars, FVector(0, 0, 264), FVector(150, 380, 10), Dark);
			Part(Cars, FVector(-62, 0, 140), FVector(4, 340, 210), GlassC);
			Part(Glow, FVector(-58, 0, 150), FVector(5, 300, 180), Accent * 0.9f);
			Part(Cars, FVector(-25, 0, 45), FVector(45, 300, 8), Dark);
		}
		else if (Kind == TEXT("vending"))
		{
			Part(Cars, FVector(0, 0, 95), FVector(90, 80, 190), Cloth[Seed % 6] * 2.f);
			Part(Glow, FVector(46, 0, 105), FVector(4, 66, 150), Accent);
		}
		else if (Kind == TEXT("hydrant"))
		{
			Part(Lamps, FVector(0, 0, 35), FVector(34, 34, 70), FLinearColor(0.5f, 0.03f, 0.02f));
			Part(Lamps, FVector(0, 0, 76), FVector(44, 44, 12), FLinearColor(0.45f, 0.03f, 0.02f));
		}
		else if (Kind == TEXT("bollard"))
		{
			Part(Lamps, FVector(0, 0, 45), FVector(28, 28, 90), Conc);
			Part(Glow, FVector(0, 0, 92), FVector(30, 30, 5), Accent);
		}
		else if (Kind == TEXT("bench"))
		{
			Part(Cars, FVector(0, 0, 45), FVector(180, 50, 8), FLinearColor(0.1f, 0.06f, 0.03f));
			Part(Cars, FVector(-22, 0, 72), FVector(6, 180, 40), FLinearColor(0.1f, 0.06f, 0.03f));
			for (int32 sy = -1; sy <= 1; sy += 2) Part(Cars, FVector(0, sy * 70.f, 22), FVector(36, 8, 44), Dark);
		}
		else if (Kind == TEXT("crate"))
		{
			Part(Cars, FVector(0, 0, 45), FVector(95, 95, 90), FLinearColor(0.18f, 0.1f, 0.05f));
			if (Seed % 2) Part(Cars, FVector(Rs.FRandRange(-10.f, 10.f), 0, 135), FVector(80, 80, 80), FLinearColor(0.15f, 0.09f, 0.045f), Rs.FRandRange(-25.f, 25.f));
		}
		else if (Kind == TEXT("person"))
		{
			const FLinearColor Coat = Cloth[Seed % 6];
			Part(Lamps, FVector(0, 0, 90), FVector(46, 46, 140), Coat);
			Part(TreeCrowns, FVector(0, 0, 178), FVector(30, 30, 32), FLinearColor(0.18f, 0.12f, 0.09f));
			if (Rs.FRand() < 0.72f)
			{
				Part(Lamps, FVector(0, 0, 215), FVector(3, 3, 80), Dark);
				Part(TreeCrowns, FVector(0, 0, 250), FVector(160, 160, 34), Neon[Seed % 5] * 0.55f);
			}
		}
		else if (Kind == TEXT("stall"))
		{
			Part(Cars, FVector(0, 0, 45), FVector(150, 300, 90), Cloth[Seed % 6] * 2.5f);
			Part(Cars, FVector(0, 0, 255), FVector(210, 340, 10), Accent * 0.4f, 0.f, 0.f, 0.f);
			Part(Cars, FVector(0, 0, 262), FVector(210, 330, 6), (Seed % 2) ? FLinearColor(0.9f, 0.9f, 0.9f) * 0.25f : Accent * 0.25f);
			for (int32 sx = -1; sx <= 1; sx += 2)
				for (int32 sy = -1; sy <= 1; sy += 2) Part(Lamps, FVector(sx * 90.f, sy * 160.f, 125), FVector(8, 8, 250), Dark);
			Part(Glow, FVector(40, 0, 245), FVector(110, 280, 5), FLinearColor(1.f, 0.72f, 0.4f));                  // lamp strip under the awning
			Part(Glow, FVector(76, 0, 110), FVector(4, 270, 30), Accent);                                           // goods
		}
		else if (Kind == TEXT("trafficlight"))
		{
			Part(Lamps, FVector(0, 0, 300), FVector(25, 25, 600), Dark);
			Part(Cars, FVector(210, 0, 590), FVector(420, 18, 18), Dark);
			Part(Cars, FVector(380, 0, 540), FVector(40, 36, 120), Dark);
			const int32 On = Seed % 3;
			const FLinearColor Lc[3] = { FLinearColor(1.f, 0.02f, 0.02f), FLinearColor(1.f, 0.6f, 0.02f), FLinearColor(0.05f, 1.f, 0.2f) };
			for (int32 k = 0; k < 3; ++k) Part(Glow, FVector(401, 0, 575 - 35 * k), FVector(6, 26, 26), Lc[k] * (k == On ? 1.f : 0.04f));
		}
		else if (Kind == TEXT("trash"))
		{
			for (int32 k = 0; k < 4; ++k) Part(Cars, FVector(Rs.FRandRange(-90.f, 90.f), Rs.FRandRange(-60.f, 60.f), 18), FVector(Rs.FRandRange(30.f, 55.f), Rs.FRandRange(30.f, 55.f), Rs.FRandRange(25.f, 40.f)), FLinearColor(0.012f, 0.012f, 0.015f), Rs.FRandRange(0.f, 90.f));
			Part(Lamps, FVector(120, 0, 45), FVector(55, 55, 90), Conc * 0.8f);
		}
		else if (Kind == TEXT("sign"))
		{
			Part(Lamps, FVector(0, 0, 150), FVector(10, 10, 300), Dark);
			Part(Glow, FVector(6, 0, 280), FVector(5, 90, 90), (Seed % 2) ? FLinearColor(0.1f, 0.4f, 1.f) : FLinearColor(1.f, 0.15f, 0.1f));
		}
	}
}

void AIVDistrict::BuildPort(const TSharedPtr<FJsonObject>& Infra)
{
	if (!Infra->HasTypedField<EJson::Object>(TEXT("port"))) return;
	const TSharedPtr<FJsonObject> Port = Infra->GetObjectField(TEXT("port"));
	if (!Port->HasTypedField<EJson::Array>(TEXT("containers"))) return;
	int32 K = 0;
	for (const TSharedPtr<FJsonValue>& CV : Port->GetArrayField(TEXT("containers")))
	{
		const TSharedPtr<FJsonObject> C = CV->AsObject();
		const TArray<TSharedPtr<FJsonValue>>& Pos = C->GetArrayField(TEXT("pos"));
		const FVector Loc = ToUE(Pos[0]->AsNumber(), Pos[1]->AsNumber(), Pos.Num() > 2 ? Pos[2]->AsNumber() : 0.0);
		const int32 Levels = C->HasField(TEXT("levels")) ? int32(C->GetNumberField(TEXT("levels"))) : 1;
		const float Yaw = YawToUE(float(C->HasField(TEXT("yaw_deg")) ? C->GetNumberField(TEXT("yaw_deg")) : 0.0));
		for (int32 L = 0; L < Levels; ++L)
		{
			Containers->AddInstance(FTransform(FRotator(0, Yaw, 0), Loc + FVector(0, 0, 130.f + L * 260.f), FVector(12.2f, 2.45f, 2.6f)));
		}
		++K;
	}
}

int32 AIVDistrict::BlastAt(const FVector& Center, float Radius, float Impulse)
{
	int32 Total = 0;
	bool bChanged = false;
	UMaterialInterface* Fb = nullptr;
	for (FIVDistrictBuilding& D : Buildings)
	{
		// conservative world AABB of the rotated box
		const float Ext = D.Size.Size2D() * 0.5f;
		if (FMath::Abs(Center.X - D.Center.X) > Ext + Radius || FMath::Abs(Center.Y - D.Center.Y) > Ext + Radius) continue;
		if (Center.Z > D.Center.Z + D.Size.Z * 0.5f + Radius || Center.Z < D.Center.Z - D.Size.Z * 0.5f - Radius) continue;
		if (!D.bActive)
		{
			// reject if the sphere does not touch the oriented box
			const FVector L = FRotator(0, -D.YawDeg, 0).RotateVector(Center - D.Center);
			const FVector Q(FMath::Clamp(L.X, -D.Size.X * 0.5f, D.Size.X * 0.5f), FMath::Clamp(L.Y, -D.Size.Y * 0.5f, D.Size.Y * 0.5f), FMath::Clamp(L.Z, -D.Size.Z * 0.5f, D.Size.Z * 0.5f));
			if (FVector::Dist(L, Q) > Radius) continue;
			AIVBuilding* Bld = GetWorld()->SpawnActor<AIVBuilding>(FVector::ZeroVector, FRotator::ZeroRotator);
			if (!Bld) continue;
			const float Cell = FMath::Clamp(FMath::Max(D.Size.X, D.Size.Y) / 14.f, 750.f, 1100.f);
			Bld->Init(D.Center, D.YawDeg, D.Size, D.bGlass ? Cast<UMaterialInterface>(FacadeGlass) : Cast<UMaterialInterface>(FacadeConcrete), Cell);
			D.Actor = Bld;
			D.bActive = true;
			bChanged = true;
		}
		if (AIVBuilding* Bld = D.Actor.Get()) Total += Bld->ApplyBlast(Center, Radius, Impulse);
	}
	if (bChanged) RebuildStaticInstances();
	return Total;
}


bool AIVDistrict::FindBuildingNear(const FVector& From, const FVector& Dir, float MinD, float MaxD, FVector& OutBase, FVector& OutSize) const
{
	float Best = 1e12f;
	bool bFound = false;
	for (const FIVDistrictBuilding& B : Buildings)
	{
		if (B.bHero) continue;
		if (B.bActive && B.Actor.IsValid() && B.Actor->IsMostlyGone()) continue;
		const FVector To = B.Center - From;
		const float D2 = To.Size2D() - 0.5f * FMath::Min(B.Size.X, B.Size.Y);
		if (D2 < MinD || D2 > MaxD || B.Size.Z < 3500.f) continue;
		if (FVector::DotProduct(To.GetSafeNormal2D(), Dir) < -0.25f) continue;
		if (D2 < Best) { Best = D2; OutBase = FVector(B.Center.X, B.Center.Y, B.Center.Z - B.Size.Z * 0.5f); OutSize = B.Size; bFound = true; }
	}
	return bFound;
}
