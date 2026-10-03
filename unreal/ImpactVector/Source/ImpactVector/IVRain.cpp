#include "IVRain.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "Kismet/GameplayStatics.h"
#include "UObject/ConstructorHelpers.h"
#include "Math/RandomStream.h"
#include "Camera/PlayerCameraManager.h"

AIVRain::AIVRain()
{
	PrimaryActorTick.bCanEverTick = true;
	PrimaryActorTick.TickGroup = TG_PostUpdateWork;
	static ConstructorHelpers::FObjectFinder<UStaticMesh> Cyl(TEXT("/Engine/BasicShapes/Cylinder.Cylinder"));
	ISM = CreateDefaultSubobject<UInstancedStaticMeshComponent>(TEXT("Streaks"));
	RootComponent = ISM;
	if (Cyl.Succeeded()) ISM->SetStaticMesh(Cyl.Object);
	ISM->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	ISM->SetCastShadow(false);
	ISM->bAffectDistanceFieldLighting = false;
	ISM->bAffectDynamicIndirectLighting = false;
	ISM->SetCanEverAffectNavigation(false);
	ISM->SetBoundsScale(4.f);
}

void AIVRain::BeginPlay()
{
	Super::BeginPlay();
	if (UMaterialInterface* M = LoadObject<UMaterialInterface>(nullptr, TEXT("/Game/Materials/M_Rain.M_Rain")))
	{
		UMaterialInstanceDynamic* MID = UMaterialInstanceDynamic::Create(M, this);
		MID->SetScalarParameterValue(TEXT("BoxXY"), BoxXY);
		MID->SetScalarParameterValue(TEXT("BoxZ"), BoxZ);
		ISM->SetMaterial(0, MID);
	}
	FRandomStream R(777);
	TArray<FTransform> T;
	T.Reserve(Count);
	const FQuat Tilt = FRotator(0.f, 0.f, -12.f).Quaternion();   // lean into the wind (+X)
	for (int32 i = 0; i < Count; ++i)
	{
		const FVector P(R.FRandRange(-BoxXY * 0.5f, BoxXY * 0.5f), R.FRandRange(-BoxXY * 0.5f, BoxXY * 0.5f), R.FRandRange(-BoxZ * 0.5f, BoxZ * 0.5f));
		const float L = R.FRandRange(2.0f, 3.4f), W = R.FRandRange(0.025f, 0.05f);
		T.Add(FTransform(Tilt, P, FVector(W, W, L)));
	}
	ISM->AddInstances(T, false);
}

void AIVRain::Tick(float Dt)
{
	Super::Tick(Dt);
	if (APlayerCameraManager* PCM = UGameplayStatics::GetPlayerCameraManager(this, 0))
	{
		const FVector C = PCM->GetCameraLocation();
		SetActorLocation(FVector(FMath::RoundToFloat(C.X / BoxXY) * BoxXY, FMath::RoundToFloat(C.Y / BoxXY) * BoxXY, FMath::RoundToFloat(C.Z / BoxZ) * BoxZ));
	}
}
