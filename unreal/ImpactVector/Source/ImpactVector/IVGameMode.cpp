#include "IVGameMode.h"
#include "IVMechPawn.h"
#include "IVPlayerController.h"
#include "IVHUD.h"
#include "IVEnvironment.h"
#include "IVDistrict.h"
#include "IVCombat.h"
#include "Engine/World.h"
#include "Engine/Engine.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "UnrealClient.h"
#include "HAL/IConsoleManager.h"
#include "Kismet/KismetSystemLibrary.h"
#include "Kismet/GameplayStatics.h"

AIVGameMode::AIVGameMode()
{
	PrimaryActorTick.bCanEverTick = true;
	DefaultPawnClass = AIVMechPawn::StaticClass();
	PlayerControllerClass = AIVPlayerController::StaticClass();
	HUDClass = AIVHUD::StaticClass();
}

void AIVGameMode::StartPlay()
{
	Super::StartPlay();

	UWorld* W = GetWorld();
	W->SpawnActor<AIVEnvironment>(FVector::ZeroVector, FRotator::ZeroRotator);

	FActorSpawnParameters P;
	P.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
	FVector EnemyLoc(6000.f, 0.f, 4100.f);
	float EnemyYaw = 180.f;
	FVector PlayerLoc(-24000.f, 0.f, 4100.f);
	float PlayerYaw = 0.f;
	bool bDistrict = false;
	if (AIVEnvironment* Env = AIVEnvironment::Get(W))
	{
		if (AIVDistrict* Dist = Env->GetDistrict())
		{
			bDistrict = true;
			FVector L; float Y;
			if (Dist->GetPoi(TEXT("spawn_enemy"), L, Y)) { EnemyLoc = FVector(L.X, L.Y, Dist->SampleHeightCm(L.X, L.Y) + 4100.f); EnemyYaw = Y + 180.f; }
			if (Dist->GetPoi(TEXT("spawn_player"), L, Y)) { PlayerLoc = FVector(L.X, L.Y, Dist->SampleHeightCm(L.X, L.Y) + 4100.f); PlayerYaw = Y; }
		}
	}
	EnemyMech = W->SpawnActor<AIVMechPawn>(EnemyLoc, FRotator(0.f, EnemyYaw, 0.f), P);
	if (EnemyMech)
	{
		EnemyMech->bAIControlled = true;
		EnemyMech->SetBodyTint(FLinearColor(0.9f, 0.45f, 0.4f));
	}

	{
		float StartX = PlayerLoc.X, StartY = PlayerLoc.Y, StartYaw = PlayerYaw;
		FParse::Value(FCommandLine::Get(), TEXT("-IVX="), StartX);
		FParse::Value(FCommandLine::Get(), TEXT("-IVY="), StartY);
		FParse::Value(FCommandLine::Get(), TEXT("-IVYaw="), StartYaw);
		if (APlayerController* PC = W->GetFirstPlayerController())
		{
			if (APawn* Pawn = PC->GetPawn())
			{
				Pawn->SetActorLocationAndRotation(FVector(StartX, StartY, PlayerLoc.Z), FRotator(0.f, StartYaw, 0.f), false, nullptr, ETeleportType::TeleportPhysics);
				float StartPitch = 0.f; FParse::Value(FCommandLine::Get(), TEXT("-IVPitch="), StartPitch);
				if (AIVMechPawn* M = Cast<AIVMechPawn>(Pawn)) M->SetAim(StartYaw, StartPitch);
			}
		}
	}

	// combat: the player is side A, the enemy mech side B
	if (!FParse::Param(FCommandLine::Get(), TEXT("IVNoCombat")))
	{
		if (APlayerController* PC = W->GetFirstPlayerController())
		{
			if (AIVMechPawn* PlayerMech = Cast<AIVMechPawn>(PC->GetPawn()))
			{
				AIVCombatDirector* Dir = W->SpawnActor<AIVCombatDirector>(FVector::ZeroVector, FRotator::ZeroRotator);
				int32 Style = 0, Level = 1;
				FParse::Value(FCommandLine::Get(), TEXT("-IVStyle="), Style);
				FParse::Value(FCommandLine::Get(), TEXT("-IVLevel="), Level);
				if (EnemyMech)
				{
					EnemyMech->bAIControlled = false;
					Dir->Setup(PlayerMech, EnemyMech, static_cast<iv::Archetype>(FMath::Clamp(Style, 0, iv::kArchetypeCount - 1)), static_cast<iv::Difficulty>(FMath::Clamp(Level, 0, iv::kDifficultyCount - 1)), 20261003ull);
					if (FParse::Param(FCommandLine::Get(), TEXT("IVAutoFight")))
					{
						Dir->EnableAutoPlayer(iv::Archetype::LimbHunter, iv::Difficulty::Normal);
						// face to face on the plaza, 60 core units apart
						const FVector Mid = EnemyMech->GetActorLocation();
						PlayerMech->SetActorLocationAndRotation(Mid + FVector(-(60.f + AIVCombatDirector::kBodyGapUnits) * 100.f, 0.f, 0.f), FRotator::ZeroRotator, false, nullptr, ETeleportType::TeleportPhysics);
						EnemyMech->SetActorRotation(FRotator(0.f, 180.f, 0.f));
						PlayerMech->SetAim(0.f, 0.f);
					}
					int32 Dummy = 0;
					if (FParse::Value(FCommandLine::Get(), TEXT("-IVDummy="), Dummy) && Dummy > 0) Dir->SetDummy(static_cast<iv::DummyMode>(Dummy));
				}
			}
		}
	}

	FString Value;
	if (FParse::Value(FCommandLine::Get(), TEXT("-IVCam="), Value))
	{
		IConsoleManager::Get().FindConsoleVariable(TEXT("iv.Cam"))->Set(FCString::Atoi(*Value));
	}
	if (FParse::Value(FCommandLine::Get(), TEXT("-IVShots="), Value, false))
	{
		TArray<FString> Parts;
		Value.ParseIntoArray(Parts, TEXT(","));
		for (const FString& S : Parts) PendingShots.Add(FCString::Atof(*S));
	}
	FParse::Value(FCommandLine::Get(), TEXT("-IVBlast="), BlastAt);
	{ int32 N = 1; FParse::Value(FCommandLine::Get(), TEXT("-IVBlastN="), N); BlastsLeft = (BlastAt >= 0.f) ? N : 0; }
	FParse::Value(FCommandLine::Get(), TEXT("-IVCollapse="), CollapseAt);
	{
		FString A;
		if (FParse::Value(FCommandLine::Get(), TEXT("-IVAction="), A, false))
		{
			FString N, T;
			if (A.Split(TEXT("@"), &N, &T)) { ActionName = FName(*N); ActionAt = FCString::Atof(*T); }
		}
	}
	float Q = -1.f;
	if (FParse::Value(FCommandLine::Get(), TEXT("-IVQuit="), Q)) QuitAt = Q;
}

void AIVGameMode::Tick(float Dt)
{
	Super::Tick(Dt);
	Elapsed += Dt;
	if (PendingShots.IsValidIndex(ShotIndex) && Elapsed >= PendingShots[ShotIndex])
	{
		if (FScreenshotRequest::IsScreenshotRequested())
		{
			UE_LOG(LogTemp, Display, TEXT("IV: previous screenshot still pending at t=%.1f"), Elapsed);
		}
		else
		{
			const FString Name = FString::Printf(TEXT("IV_shot_%02d_t%.0f.png"), ShotIndex, PendingShots[ShotIndex]);
			UE_LOG(LogTemp, Display, TEXT("IV: requesting %s at t=%.1f"), *Name, Elapsed);
			FScreenshotRequest::RequestScreenshot(Name, false, false);
			++ShotIndex;
		}
	}
	if (BlastsLeft > 0 && Elapsed >= BlastAt && Elapsed >= NextBlast)
	{
		if (AIVMechPawn* M = Cast<AIVMechPawn>(UGameplayStatics::GetPlayerPawn(this, 0))) { float R = 2400.f; FParse::Value(FCommandLine::Get(), TEXT("-IVBlastR="), R); M->DebugBlast(R); }
		--BlastsLeft;
		NextBlast = Elapsed + 1.0f;
	}
	if (CollapseAt >= 0.f && Elapsed >= CollapseAt)
	{
		CollapseAt = -1.f;
		if (APawn* P = UGameplayStatics::GetPlayerPawn(this, 0))
			if (AIVEnvironment* Env = AIVEnvironment::Get(GetWorld()))
			{
				const int32 N = Env->CollapseNearestAhead(P->GetActorLocation(), P->GetActorForwardVector());
				UE_LOG(LogTemp, Display, TEXT("IV: collapse test destroyed %d cells"), N);
			}
	}
	if (ActionAt >= 0.f && Elapsed >= ActionAt)
	{
		ActionAt = -1.f;
		if (AIVMechPawn* M = Cast<AIVMechPawn>(UGameplayStatics::GetPlayerPawn(this, 0))) M->PlayAction(ActionName);
	}
	if (QuitAt > 0.f && Elapsed >= QuitAt)
	{
		UKismetSystemLibrary::QuitGame(this, nullptr, EQuitPreference::Quit, false);
		QuitAt = -1.f;
	}
}
