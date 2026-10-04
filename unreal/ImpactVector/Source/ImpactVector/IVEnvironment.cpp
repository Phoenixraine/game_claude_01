#include "IVEnvironment.h"
#include "Components/DirectionalLightComponent.h"
#include "Components/SkyAtmosphereComponent.h"
#include "Components/SkyLightComponent.h"
#include "Components/ExponentialHeightFogComponent.h"
#include "Components/VolumetricCloudComponent.h"
#include "Components/PostProcessComponent.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Engine/StaticMesh.h"
#include "UObject/ConstructorHelpers.h"
#include "Math/RandomStream.h"
#include "IVBuilding.h"
#include "IVDistrict.h"
#include "Misc/Paths.h"
#include "Misc/FileHelper.h"
#include "EngineUtils.h"
#include "Engine/World.h"
#include "IVRain.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"

AIVEnvironment::AIVEnvironment()
{
	PrimaryActorTick.bCanEverTick = false;

	static ConstructorHelpers::FObjectFinder<UStaticMesh> CubeF(TEXT("/Engine/BasicShapes/Cube.Cube"));
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> MatF(TEXT("/Engine/BasicShapes/BasicShapeMaterial.BasicShapeMaterial"));

	Root = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
	RootComponent = Root;

	Sun = CreateDefaultSubobject<UDirectionalLightComponent>(TEXT("Sun"));
	Sun->SetupAttachment(Root);
	Sun->SetRelativeRotation(FRotator(5.f, 215.f, 0.f));   // just under the horizon: deep blue twilight sky
	Sun->SetIntensity(3.f);
	Sun->SetLightColor(FLinearColor(0.62f, 0.72f, 1.0f).ToFColor(true));
	Sun->SetAtmosphereSunLight(true);
	Sun->SetMobility(EComponentMobility::Movable);
	Sun->SetCastShadows(true);

	Moon = CreateDefaultSubobject<UDirectionalLightComponent>(TEXT("Moon"));
	Moon->SetupAttachment(Root);
	Moon->SetRelativeRotation(FRotator(-38.f, 140.f, 0.f));
	Moon->SetIntensity(4.f);
	Moon->SetLightColor(FLinearColor(0.55f, 0.66f, 1.0f).ToFColor(true));
	Moon->SetMobility(EComponentMobility::Movable);
	Moon->SetCastShadows(true);
	Moon->SetVolumetricScatteringIntensity(3.f);
	Moon->SetAtmosphereSunLight(false);

	Atmosphere = CreateDefaultSubobject<USkyAtmosphereComponent>(TEXT("Atmosphere"));
	Atmosphere->SetupAttachment(Root);

	SkyLight = CreateDefaultSubobject<USkyLightComponent>(TEXT("SkyLight"));
	SkyLight->SetupAttachment(Root);
	SkyLight->SetMobility(EComponentMobility::Movable);
	SkyLight->bRealTimeCapture = true;
	SkyLight->SetIntensity(1.6f);

	Fog = CreateDefaultSubobject<UExponentialHeightFogComponent>(TEXT("Fog"));
	Fog->SetupAttachment(Root);
	Fog->SetFogDensity(0.06f);
	Fog->SetFogHeightFalloff(0.012f);
	Fog->SetVolumetricFog(true);
	Fog->SetVolumetricFogDistance(30000.f);
	Fog->SetFogInscatteringColor(FLinearColor(0.13f, 0.12f, 0.22f));
	Fog->SkyAtmosphereAmbientContributionColorScale = FLinearColor(0.12f, 0.16f, 0.26f);
	Fog->SetFogMaxOpacity(1.f);
	Fog->SetStartDistance(0.f);

	Clouds = CreateDefaultSubobject<UVolumetricCloudComponent>(TEXT("Clouds"));
	Clouds->SetupAttachment(Root);
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> CloudMat(TEXT("/Engine/EngineSky/VolumetricClouds/m_SimpleVolumetricCloud_Inst.m_SimpleVolumetricCloud_Inst"));
	if (CloudMat.Succeeded()) Clouds->SetMaterial(CloudMat.Object);

	PostProcess = CreateDefaultSubobject<UPostProcessComponent>(TEXT("PostProcess"));
	PostProcess->SetupAttachment(Root);
	PostProcess->bUnbound = true;
	FPostProcessSettings& S = PostProcess->Settings;
	S.bOverride_AutoExposureMethod = true;
	S.AutoExposureMethod = EAutoExposureMethod::AEM_Histogram;
	S.bOverride_AutoExposureMinBrightness = true; S.AutoExposureMinBrightness = 1.6f;
	S.bOverride_AutoExposureMaxBrightness = true; S.AutoExposureMaxBrightness = 1.6f;
	S.bOverride_AutoExposureBias = true; S.AutoExposureBias = 0.4f;
	S.bOverride_BloomIntensity = true; S.BloomIntensity = 0.8f;
	S.bOverride_VignetteIntensity = true; S.VignetteIntensity = 0.45f;
	S.bOverride_FilmGrainIntensity = true; S.FilmGrainIntensity = 0.08f;
	S.bOverride_DynamicGlobalIlluminationMethod = true; S.DynamicGlobalIlluminationMethod = EDynamicGlobalIlluminationMethod::Lumen;
	S.bOverride_ReflectionMethod = true; S.ReflectionMethod = EReflectionMethod::Lumen;
	S.bOverride_ColorSaturation = true; S.ColorSaturation = FVector4(1.08f, 1.08f, 1.14f, 1.0f);
	S.bOverride_ColorContrast = true; S.ColorContrast = FVector4(1.12f, 1.12f, 1.12f, 1.0f);
	S.bOverride_ColorGain = true; S.ColorGain = FVector4(0.97f, 0.985f, 1.06f, 1.0f);
	S.bOverride_ColorGainShadows = true; S.ColorGainShadows = FVector4(0.9f, 0.96f, 1.12f, 1.0f);
	S.bOverride_ColorGainHighlights = true; S.ColorGainHighlights = FVector4(1.08f, 1.0f, 0.96f, 1.0f);
	S.bOverride_SceneFringeIntensity = true; S.SceneFringeIntensity = 0.35f;

	auto MakeSlab = [&](const TCHAR* Name) {
		UStaticMeshComponent* M = CreateDefaultSubobject<UStaticMeshComponent>(Name);
		M->SetupAttachment(Root);
		M->SetStaticMesh(CubeF.Object);
		return M;
	};
	Ground = MakeSlab(TEXT("Ground"));
	Ground->SetRelativeLocation(FVector(45000.f, 0, -100));
	Ground->SetRelativeScale3D(FVector(2100.f, 3000.f, 2.f));        // land: x from -60 km... -60000 cm (quay edge) to +150000
	Ground->SetCollisionProfileName(TEXT("BlockAll"));
	Sea = MakeSlab(TEXT("Sea"));
	Sea->SetRelativeLocation(FVector(-210000.f, 0, -1700));
	Sea->SetRelativeScale3D(FVector(3000.f, 6000.f, 2.f));           // top at z = -1600: a 16 m drop from the quay
	Sea->SetCollisionProfileName(TEXT("BlockAll"));

	Concrete = CreateDefaultSubobject<UInstancedStaticMeshComponent>(TEXT("Concrete"));
	Concrete->SetupAttachment(Root);
	Concrete->SetStaticMesh(CubeF.Object);
	Concrete->SetCollisionProfileName(TEXT("BlockAll"));
	Glass = CreateDefaultSubobject<UInstancedStaticMeshComponent>(TEXT("Glass"));
	Glass->SetupAttachment(Root);
	Glass->SetStaticMesh(CubeF.Object);
	Glass->SetCollisionProfileName(TEXT("BlockAll"));
}

void AIVEnvironment::OnConstruction(const FTransform&)
{
}

void AIVEnvironment::BeginPlay()
{
	Super::BeginPlay();
	{	// weather overrides for tuning: -IVFog= -IVFogFall= -IVSun= -IVSunPitch= -IVSky= ; -IVNoRain
		float V = 0.f;
		if (FParse::Value(FCommandLine::Get(), TEXT("-IVFog="), V)) Fog->SetFogDensity(V);
		if (FParse::Value(FCommandLine::Get(), TEXT("-IVFogFall="), V)) Fog->SetFogHeightFalloff(V);
		if (FParse::Value(FCommandLine::Get(), TEXT("-IVSun="), V)) Moon->SetIntensity(V);
		if (FParse::Value(FCommandLine::Get(), TEXT("-IVSunPitch="), V)) Moon->SetRelativeRotation(FRotator(V, 140.f, 0.f));
		if (FParse::Value(FCommandLine::Get(), TEXT("-IVSky="), V)) SkyLight->SetIntensity(V);
		if (FParse::Value(FCommandLine::Get(), TEXT("-IVExp="), V)) { FPostProcessSettings& PS = PostProcess->Settings; PS.AutoExposureMinBrightness = V; PS.AutoExposureMaxBrightness = V; }
		Clouds->SetVisibility(false);
		if (!FParse::Param(FCommandLine::Get(), TEXT("IVNoRain"))) GetWorld()->SpawnActor<AIVRain>(FVector::ZeroVector, FRotator::ZeroRotator);
	}
	UMaterialInterface* Fallback = LoadObject<UMaterialInterface>(nullptr, TEXT("/Engine/BasicShapes/BasicShapeMaterial.BasicShapeMaterial"));
	UMaterialInterface* Facade = LoadObject<UMaterialInterface>(nullptr, TEXT("/Game/Materials/M_BuildingFacade.M_BuildingFacade"));
	UMaterialInterface* GroundM = LoadObject<UMaterialInterface>(nullptr, TEXT("/Game/Materials/M_WetGround.M_WetGround"));
	UMaterialInterface* SeaM = LoadObject<UMaterialInterface>(nullptr, TEXT("/Game/Materials/M_Sea.M_Sea"));

	auto Apply = [this](UPrimitiveComponent* C, UMaterialInterface* Src, UMaterialInterface* Fb,
		TFunctionRef<void(UMaterialInstanceDynamic*)> Setup)
	{
		UMaterialInterface* Use = Src ? Src : Fb;
		if (!Use) return;
		UMaterialInstanceDynamic* M = UMaterialInstanceDynamic::Create(Use, this);
		Setup(M);
		C->SetMaterial(0, M);
	};
	Apply(Ground, GroundM, Fallback, [](UMaterialInstanceDynamic* M) {
		M->SetVectorParameterValue(TEXT("BaseTint"), FLinearColor(0.045f, 0.047f, 0.052f));
		M->SetVectorParameterValue(TEXT("Color"), FLinearColor(0.06f, 0.065f, 0.07f));
	});
	Apply(Sea, SeaM, Fallback, [](UMaterialInstanceDynamic* M) {
		M->SetVectorParameterValue(TEXT("Color"), FLinearColor(0.012f, 0.03f, 0.05f));
	});
	Apply(Concrete, Facade, Fallback, [](UMaterialInstanceDynamic* M) {
		M->SetVectorParameterValue(TEXT("Tint"), FLinearColor(0.2f, 0.21f, 0.22f));
		M->SetVectorParameterValue(TEXT("GlassColor"), FLinearColor(0.03f, 0.045f, 0.06f));
		M->SetScalarParameterValue(TEXT("Glassiness"), 0.5f);
		M->SetVectorParameterValue(TEXT("Color"), FLinearColor(0.2f, 0.21f, 0.22f));
	});
	Apply(Glass, Facade, Fallback, [](UMaterialInstanceDynamic* M) {
		M->SetVectorParameterValue(TEXT("Tint"), FLinearColor(0.07f, 0.1f, 0.13f));
		M->SetVectorParameterValue(TEXT("GlassColor"), FLinearColor(0.02f, 0.05f, 0.08f));
		M->SetScalarParameterValue(TEXT("WindowSpacing"), 330.f);
		M->SetScalarParameterValue(TEXT("Glassiness"), 0.9f);
		M->SetVectorParameterValue(TEXT("Color"), FLinearColor(0.04f, 0.07f, 0.1f));
	});
	FString JsonPath = FPaths::ProjectContentDir() / TEXT("Data/district_arena.json");
	FString HeightPath = FPaths::ProjectContentDir() / TEXT("Data/heightmap_arena.r16");
	if (FParse::Param(FCommandLine::Get(), TEXT("IVBayMap")) || !FPaths::FileExists(JsonPath))
	{
		JsonPath = FPaths::ProjectContentDir() / TEXT("Data/district.json");
		HeightPath = FPaths::ProjectContentDir() / TEXT("Data/heightmap.r16");
	}
	if (FPaths::FileExists(JsonPath) && FPaths::FileExists(HeightPath))
	{
		District = GetWorld()->SpawnActor<AIVDistrict>(FVector::ZeroVector, FRotator::ZeroRotator);
		if (District && District->Load(JsonPath, HeightPath))
		{
			Ground->SetVisibility(false); Ground->SetCollisionEnabled(ECollisionEnabled::NoCollision);
			Sea->SetVisibility(false); Sea->SetCollisionEnabled(ECollisionEnabled::NoCollision);
			return;
		}
		if (District) { District->Destroy(); District = nullptr; }
	}
	BuildCityBlockout();
	RebuildStaticInstances();
}

void AIVEnvironment::BuildCityBlockout()
{
	FRandomStream R(1337);
	const float Block = 26000.f, Street = 9000.f;
	const float Lot = Block - Street;
	for (int32 bx = -2; bx <= 6; ++bx)
	{
		for (int32 by = -5; by <= 5; ++by)
		{
			const FVector2D Origin(bx * Block, by * Block);
			// keep the central avenue (y within +-7500) free for the duel
			for (int32 sx = 0; sx < 2; ++sx)
			{
				for (int32 sy = 0; sy < 2; ++sy)
				{
					const float W = Lot * 0.5f - 600.f;
					const FVector2D C = Origin + FVector2D((sx - 0.5f) * (Lot * 0.5f), (sy - 0.5f) * (Lot * 0.5f));
					if (FMath::Abs(C.Y) < 7500.f + W * 0.5f) continue;
					if (C.X < -9000.f && C.X > -60000.f) continue;   // plaza on the shore
					const float H = R.FRandRange(4500.f, 22000.f) * (R.FRand() < 0.15f ? 1.6f : 1.f);
					const float Wx = W * R.FRandRange(0.7f, 1.f), Wy = W * R.FRandRange(0.7f, 1.f);
					FIVBuildingDef D;
					D.Center = FVector(C.X, C.Y, H * 0.5f);
					D.Size = FVector(Wx, Wy, H);
					D.bGlass = R.FRand() < 0.4f;
					Defs.Add(D);
					PodiumTransforms.Add(FTransform(FRotator::ZeroRotator, FVector(C.X, C.Y, 600.f), FVector(Wx * 1.08f / 100.f, Wy * 1.08f / 100.f, 12.f)));
				}
			}
		}
	}
}

void AIVEnvironment::RebuildStaticInstances()
{
	Concrete->ClearInstances();
	Glass->ClearInstances();
	TArray<FTransform> C, G;
	for (const FIVBuildingDef& D : Defs)
	{
		if (D.bActive) continue;
		(D.bGlass ? G : C).Add(FTransform(FRotator::ZeroRotator, D.Center, D.Size / 100.f));
	}
	C.Append(PodiumTransforms);
	Concrete->AddInstances(C, false, true);
	Glass->AddInstances(G, false, true);
}

AIVEnvironment* AIVEnvironment::Get(UWorld* World)
{
	for (TActorIterator<AIVEnvironment> It(World); It; ++It) return *It;
	return nullptr;
}

int32 AIVEnvironment::BlastAt(const FVector& Center, float Radius, float Impulse)
{
	if (District) return District->BlastAt(Center, Radius, Impulse);
	int32 Total = 0;
	bool bChanged = false;
	for (FIVBuildingDef& D : Defs)
	{
		const FBox B = FBox::BuildAABB(D.Center, D.Size * 0.5f).ExpandBy(Radius);
		if (!B.IsInside(Center)) continue;
		if (!D.bActive)
		{
			AIVBuilding* Bld = GetWorld()->SpawnActor<AIVBuilding>(FVector::ZeroVector, FRotator::ZeroRotator);
			if (!Bld) continue;
			UMaterialInterface* M = (D.bGlass ? Glass : Concrete)->GetMaterial(0);
			Bld->Init(D.Center, 0.f, D.Size, M, 1100.f);
			D.Actor = Bld;
			D.bActive = true;
			bChanged = true;
		}
		if (AIVBuilding* Bld = D.Actor.Get()) Total += Bld->ApplyBlast(Center, Radius, Impulse);
	}
	if (bChanged) RebuildStaticInstances();
	return Total;
}

int32 AIVEnvironment::CollapseNearestAhead(const FVector& From, const FVector& Dir)
{
	if (District) return District->BlastAt(From + Dir.GetSafeNormal2D() * 9000.f + FVector(0, 0, 1000.f), 2600.f, 1500.f);
	int32 Best = INDEX_NONE;
	float BestD = 1e9f;
	const FVector D2 = Dir.GetSafeNormal2D();
	for (int32 i = 0; i < Defs.Num(); ++i)
	{
		const FVector To = Defs[i].Center - From;
		const float Dist = To.Size2D();
		if (Dist < 4000.f || Dist > 60000.f) continue;
		if (FVector::DotProduct(To.GetSafeNormal2D(), D2) < 0.9f) continue;
		if (Dist < BestD) { BestD = Dist; Best = i; }
	}
	if (Best == INDEX_NONE) return 0;
	const FIVBuildingDef& B = Defs[Best];
	const FVector BaseCenter(B.Center.X, B.Center.Y, 1000.f);
	const float R = FMath::Max(B.Size.X, B.Size.Y) * 0.78f;
	return BlastAt(BaseCenter, R, 1500.f);
}

bool AIVEnvironment::FindScoopBuilding(const FVector& From, const FVector& Dir, FVector& OutBase, FVector& OutSize) const
{
	if (District) return District->FindBuildingNear(From, Dir, 1500.f, 17000.f, OutBase, OutSize);
	return false;
}
