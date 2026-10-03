// Thin audio helper: sounds are SoundWave assets under /Game/Audio named after the ids of audio/manifest.json.
#pragma once

#include "CoreMinimal.h"

class UWorld;
class USoundBase;
class UAudioComponent;

namespace IVAudio
{
	USoundBase* Get(const FString& Id);
	/** Picks "base_01".."base_NN" at random. */
	FString Variant(const TCHAR* Base, int32 Count);
	void Play3D(UWorld* World, const FString& Id, const FVector& Location, float Volume = 1.f, float Pitch = 1.f);
	void Play2D(UWorld* World, const FString& Id, float Volume = 1.f, float Pitch = 1.f);
	/** Plays after Delay seconds. */
	void Play3DDelayed(UWorld* World, const FString& Id, const FVector& Location, float Delay, float Volume = 1.f, float Pitch = 1.f);
	UAudioComponent* StartLoop2D(UWorld* World, const FString& Id, float Volume);
}
