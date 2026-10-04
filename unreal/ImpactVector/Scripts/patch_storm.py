import io
SRC = r"F:\IVUnreal\Source\ImpactVector"


def rd(n):
    s = io.open(SRC + "\\" + n, encoding="utf-8").read()
    return s.replace("\r\n", "\n"), ("\r\n" in s)


def wr(n, s, crlf):
    io.open(SRC + "\\" + n, "w", encoding="utf-8", newline="\r\n" if crlf else "\n").write(s)


def rep(t, old, new):
    assert old in t, old[:70]
    return t.replace(old, new, 1)


h, c = rd("IVEnvironment.h")
if "StormClock" not in h:
    h = rep(h, "	virtual void BeginPlay() override;\n", "	virtual void BeginPlay() override;\n	virtual void Tick(float Dt) override;\n	/** Test helper / console: strike now. */\n	void Lightning();\n	void DistantExplosion();\n", )
    h = rep(h, "	UPROPERTY() TObjectPtr<AActor> RainActor;", "	UPROPERTY() TObjectPtr<AActor> RainActor;\n	// storm: lightning pulses lift the moon and sky light for a moment; thunder and far-off blasts follow with a delay\n	float StormClock = 5.f, ExplClock = 11.f, BoltT = -1.f, BoltAmp = 1.f, BoltDelay = 0.f;\n	float MoonBase = 2.6f, SkyBase = 0.8f;\n	bool bStorm = true;\n	struct FDelayed { float T; int32 Kind; FVector P; };\n	TArray<FDelayed> Delayed;")
    wr("IVEnvironment.h", h, c)

p, c = rd("IVEnvironment.cpp")
if "AIVEnvironment::Lightning" not in p:
    p = rep(p, "	PrimaryActorTick.bCanEverTick = false;", "	PrimaryActorTick.bCanEverTick = true;")
    p = rep(p, '#include "Misc/Parse.h"', '#include "Misc/Parse.h"\n#include "Kismet/GameplayStatics.h"\n#include "Camera/PlayerCameraManager.h"\n#include "IVAudio.h"')
    p += r'''

// ---------------------------------------------------------------------------------------------------------- storm
void AIVEnvironment::Tick(float Dt)
{
	Super::Tick(Dt);
	if (!bStorm) return;
	if (Moon) { if (MoonBase <= 0.f) MoonBase = Moon->Intensity; }
	StormClock -= Dt;
	ExplClock -= Dt;
	if (StormClock <= 0.f) { Lightning(); StormClock = FMath::FRandRange(6.f, 16.f); }
	if (ExplClock <= 0.f) { DistantExplosion(); ExplClock = FMath::FRandRange(9.f, 24.f); }
	if (BoltT >= 0.f)
	{
		BoltT += Dt;
		// two or three quick pulses with a decaying afterglow
		static const float Starts[3] = { 0.f, 0.11f, 0.30f };
		static const float Amps[3] = { 1.f, 0.7f, 0.9f };
		float L = 0.f;
		for (int32 i = 0; i < 3; ++i) if (BoltT >= Starts[i]) L = FMath::Max(L, Amps[i] * FMath::Exp(-(BoltT - Starts[i]) * 16.f));
		L *= BoltAmp;
		if (Moon) Moon->SetIntensity(MoonBase + 26.f * L);
		if (SkyLight) SkyLight->SetIntensity(SkyBase * (1.f + 7.f * L));
		if (BoltT > 1.1f)
		{
			BoltT = -1.f;
			if (Moon) Moon->SetIntensity(MoonBase);
			if (SkyLight) SkyLight->SetIntensity(SkyBase);
		}
	}
	for (int32 i = Delayed.Num() - 1; i >= 0; --i)
	{
		Delayed[i].T -= Dt;
		if (Delayed[i].T > 0.f) continue;
		const FDelayed D = Delayed[i];
		Delayed.RemoveAt(i);
		if (D.Kind == 0) IVAudio::Play2D(GetWorld(), TEXT("env_distant_boom_0") + FString::FromInt(FMath::RandRange(1, 3)), 0.85f, FMath::FRandRange(0.55f, 0.8f));
		else if (D.Kind == 1)
		{
			IVAudio::Play2D(GetWorld(), TEXT("env_distant_boom_0") + FString::FromInt(FMath::RandRange(1, 3)), 0.6f, FMath::FRandRange(0.8f, 1.05f));
		}
	}
}

void AIVEnvironment::Lightning()
{
	if (BoltT >= 0.f) return;
	BoltT = 0.f;
	BoltAmp = FMath::FRandRange(0.6f, 1.f);
	if (Moon)
	{
		MoonBase = Moon->Intensity > 20.f ? 2.6f : Moon->Intensity;
		Moon->SetWorldRotation(FRotator(FMath::FRandRange(-72.f, -40.f), FMath::FRandRange(0.f, 360.f), 0.f));
	}
	Delayed.Add({ FMath::FRandRange(0.4f, 3.2f), 0, FVector::ZeroVector });
}

void AIVEnvironment::DistantExplosion()
{
	APlayerCameraManager* PCM = UGameplayStatics::GetPlayerCameraManager(this, 0);
	if (!PCM) return;
	const FVector C = PCM->GetCameraLocation();
	const float Ang = FMath::FRandRange(0.f, 360.f), Dist = FMath::FRandRange(45000.f, 90000.f);
	const FVector P = C + FRotator(0.f, Ang, 0.f).Vector() * Dist + FVector(0, 0, FMath::FRandRange(2000.f, 12000.f));
	if (AIVFXManager* FX = AIVFXManager::Get(GetWorld()))
	{
		FX->SpawnExplosion(P, 14.f);
		FX->SpawnFlash(P, FLinearColor(1.f, 0.5f, 0.2f), 4.0e7f, 0.9f, 80000.f);
	}
	Delayed.Add({ Dist / 34000.f, 1, P });
}
'''
    wr("IVEnvironment.cpp", p, c)
print("storm patched")
