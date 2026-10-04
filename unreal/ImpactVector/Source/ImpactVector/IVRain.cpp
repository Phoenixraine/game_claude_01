#include "IVRain.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "Kismet/GameplayStatics.h"
#include "UObject/ConstructorHelpers.h"
#include "Math/RandomStream.h"
#include "Camera/PlayerCameraManager.h"
#include "Components/PostProcessComponent.h"

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
	RainPP = CreateDefaultSubobject<UPostProcessComponent>(TEXT("RainPP"));
	RainPP->SetupAttachment(RootComponent);
	RainPP->bUnbound = true;
	RainPP->Priority = 5.f;
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
		RainMID = MID;
	}
	if (UMaterialInterface* PM = LoadObject<UMaterialInterface>(nullptr, TEXT("/Game/Materials/M_RainPP.M_RainPP")))
	{
		RainPPMID = UMaterialInstanceDynamic::Create(PM, this);
		RainPP->Settings.AddBlendable(RainPPMID, 1.f);
	}
	FRandomStream R(777);
	TArray<FTransform> T;
	T.Reserve(Count);
	const FQuat Tilt = FRotator(0.f, 0.f, -12.f).Quaternion();   // lean into the wind (+X)
	for (int32 i = 0; i < Count; ++i)
	{
		const FVector P(R.FRandRange(-BoxXY * 0.5f, BoxXY * 0.5f), R.FRandRange(-BoxXY * 0.5f, BoxXY * 0.5f), R.FRandRange(-BoxZ * 0.5f, BoxZ * 0.5f));
		const float L = R.FRandRange(1.6f, 3.2f), W = R.FRandRange(0.008f, 0.016f);   // thin: the dense layer is the post-process one
		T.Add(FTransform(Tilt, P, FVector(W, W, L)));
	}
	ISM->AddInstances(T, false);
}

void AIVRain::SetAmount(float A)
{
	if (RainMID) RainMID->SetScalarParameterValue(TEXT("Amount"), A);
	if (RainPPMID) RainPPMID->SetScalarParameterValue(TEXT("Amount"), A);
	if (RainPP) RainPP->SetVisibility(A > 0.02f);
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
