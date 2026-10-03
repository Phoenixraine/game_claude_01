#include "IVAudio.h"
#include "Engine/World.h"
#include "Kismet/GameplayStatics.h"
#include "Sound/SoundBase.h"
#include "Sound/SoundAttenuation.h"
#include "Components/AudioComponent.h"
#include "TimerManager.h"

namespace
{
	TMap<FString, TObjectPtr<USoundBase>> GCache;
	TObjectPtr<USoundAttenuation> GAtten;

	USoundAttenuation* Attenuation()
	{
		if (!GAtten)
		{
			GAtten = NewObject<USoundAttenuation>(GetTransientPackage());
			GAtten->AddToRoot();
			FSoundAttenuationSettings& S = GAtten->Attenuation;
			S.bAttenuate = true;
			S.bSpatialize = true;
			S.AttenuationShape = EAttenuationShape::Sphere;
			S.AttenuationShapeExtents = FVector(12000.f);    // full volume within 120 m (the mechs are 82 m tall)
			S.FalloffDistance = 90000.f;                     // fades out over the next 900 m
			S.DistanceAlgorithm = EAttenuationDistanceModel::NaturalSound;
		}
		return GAtten;
	}
}

namespace IVAudio
{
	USoundBase* Get(const FString& Id)
	{
		if (TObjectPtr<USoundBase>* F = GCache.Find(Id)) return *F;
		USoundBase* S = LoadObject<USoundBase>(nullptr, *FString::Printf(TEXT("/Game/Audio/%s.%s"), *Id, *Id));
		if (S) S->AddToRoot();   // the cache is a plain global: without this the garbage collector frees the waves after a minute
		GCache.Add(Id, S);
		return S;
	}

	FString Variant(const TCHAR* Base, int32 Count)
	{
		return FString::Printf(TEXT("%s%02d"), Base, FMath::RandRange(1, FMath::Max(1, Count)));
	}

	void Play3D(UWorld* World, const FString& Id, const FVector& Location, float Volume, float Pitch)
	{
		if (!World) return;
		if (USoundBase* S = Get(Id)) UGameplayStatics::PlaySoundAtLocation(World, S, Location, FRotator::ZeroRotator, Volume, Pitch, 0.f, Attenuation());
	}

	void Play2D(UWorld* World, const FString& Id, float Volume, float Pitch)
	{
		if (!World) return;
		if (USoundBase* S = Get(Id)) UGameplayStatics::PlaySound2D(World, S, Volume, Pitch);
	}

	void Play3DDelayed(UWorld* World, const FString& Id, const FVector& Location, float Delay, float Volume, float Pitch)
	{
		if (!World) return;
		FTimerHandle H;
		TWeakObjectPtr<UWorld> W(World);
		World->GetTimerManager().SetTimer(H, FTimerDelegate::CreateLambda([W, Id, Location, Volume, Pitch]() { if (W.IsValid()) Play3D(W.Get(), Id, Location, Volume, Pitch); }), FMath::Max(Delay, 0.01f), false);
	}

	UAudioComponent* StartLoop2D(UWorld* World, const FString& Id, float Volume)
	{
		if (!World) return nullptr;
		USoundBase* S = Get(Id);
		return S ? UGameplayStatics::SpawnSound2D(World, S, Volume) : nullptr;
	}
}
