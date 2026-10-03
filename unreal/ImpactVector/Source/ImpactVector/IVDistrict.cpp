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
	PrimaryActorTick.bCanEverTick = false;
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
	Containers = ISM(TEXT("Containers"), CubeMesh, true);
	Chimneys = ISM(TEXT("Chimneys"), CylMesh, true);
	for (UInstancedStaticMeshComponent* C : { Cars.Get(), TreeTrunks.Get(), TreeCrowns.Get(), Lamps.Get(), Containers.Get() })
	{
		C->NumCustomDataFloats = 3;
	}

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
	if (UMaterialInstanceDynamic* Prop = MakeMID(TEXT("/Game/Materials/M_PropColor.M_PropColor"), Fb))
	{
		for (UInstancedStaticMeshComponent* C : { Cars.Get(), TreeTrunks.Get(), TreeCrowns.Get(), Lamps.Get() })
		{
			C->SetMaterial(0, Prop);
		}
	}

	// POIs
	for (const TSharedPtr<FJsonValue>& V : Rootj->GetArrayField(TEXT("pois")))
	{
		const TSharedPtr<FJsonObject> O = V->AsObject();
		const TArray<TSharedPtr<FJsonValue>>& P = O->GetArrayField(TEXT("pos"));
		const FVector Loc = ToUE(P[0]->AsNumber(), P[1]->AsNumber(), P[2]->AsNumber());
		const double Yd = O->HasField(TEXT("yaw_deg")) ? O->GetNumberField(TEXT("yaw_deg")) : 0.0;
		Pois.Add(O->GetStringField(TEXT("id")), TPair<FVector, float>(Loc, YawToUE(float(Yd))));
	}

	BuildTerrain();
	BuildRoads(Rootj->GetArrayField(TEXT("roads")));
	BuildBuildings(Rootj->GetArrayField(TEXT("buildings")));
	BuildProps(Rootj->GetArrayField(TEXT("props")));
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
		GroundM->SetVectorParameterValue(TEXT("BaseTint"), FLinearColor(0.11f, 0.115f, 0.12f));
		GroundM->SetScalarParameterValue(TEXT("Wetness"), 0.35f);
		GroundM->SetScalarParameterValue(TEXT("UseVertexColor"), 1.f);
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
	for (const FIVDistrictBuilding& D : Buildings)
	{
		if (D.bActive) continue;
		const FTransform T(FRotator(0, D.YawDeg, 0), D.Center, D.Size / 100.f);
		(D.bGlass ? G : C).Add(T);
	}
	Concrete->AddInstances(C, false, true);
	Glass->AddInstances(G, false, true);
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
		auto SetCol = [](UInstancedStaticMeshComponent* C, int32 Index, const FLinearColor& Col)
		{
			C->SetCustomDataValue(Index, 0, Col.R, false);
			C->SetCustomDataValue(Index, 1, Col.G, false);
			C->SetCustomDataValue(Index, 2, Col.B, false);
		};
		if (Kind == TEXT("car"))
		{
			const FVector S = CarSize(Var);
			const int32 I = Cars->AddInstance(FTransform(FRotator(0, Yaw, 0), Loc + FVector(0, 0, S.Z * 0.5f + 20.f), S / 100.f));
			SetCol(Cars, I, CarColor(Var, Seed * 7919));
		}
		else if (Kind == TEXT("tree"))
		{
			const float H = 420.f + 60.f * (Seed % 5);
			const int32 I = TreeTrunks->AddInstance(FTransform(FRotator::ZeroRotator, Loc + FVector(0, 0, H * 0.5f), FVector(0.55f, 0.55f, H / 100.f)));
			SetCol(TreeTrunks, I, FLinearColor(0.07f, 0.045f, 0.03f));
			const float CR = 520.f + 50.f * (Seed % 4);
			const int32 J = TreeCrowns->AddInstance(FTransform(FRotator::ZeroRotator, Loc + FVector(0, 0, H + CR * 0.35f), FVector(CR / 100.f, CR / 100.f, CR * 0.85f / 100.f)));
			SetCol(TreeCrowns, J, FLinearColor(0.025f + 0.01f * (Seed % 3), 0.07f + 0.015f * (Seed % 4), 0.03f));
		}
		else if (Kind == TEXT("lamp"))
		{
			const int32 I = Lamps->AddInstance(FTransform(FRotator::ZeroRotator, Loc + FVector(0, 0, 450.f), FVector(0.28f, 0.28f, 9.f)));
			SetCol(Lamps, I, FLinearColor(0.08f, 0.085f, 0.09f));
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
