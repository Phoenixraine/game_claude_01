#include "IVGameMode.h"
#include "IVSettings.h"
#include "IVFXManager.h"
#include "IVHelicopter.h"
#include "RenderCore.h"
#include "RHI.h"
#include "IVMechPawn.h"
#include "IVPlayerController.h"
#include "IVHUD.h"
#include "IVEnvironment.h"
#include "IVFlow.h"
#include "EngineUtils.h"
#include "IVDistrict.h"
#include "IVCombat.h"
#include "IVAudio.h"
#include "IVGraphics.h"
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

UClass* AIVGameMode::GetDefaultPawnClassForController_Implementation(AController* InController)
{
	if (APlayerController* PCtl = Cast<APlayerController>(InController))
		if (UGameplayStatics::GetPlayerControllerID(PCtl) >= 1) return nullptr;
	return Super::GetDefaultPawnClassForController_Implementation(InController);
}

void AIVGameMode::StartPlay()
{
	Super::StartPlay();

	UWorld* W = GetWorld();
	IVGraphics::ApplyAtStart(W);
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
	EnemyMech = W->SpawnActorDeferred<AIVMechPawn>(AIVMechPawn::StaticClass(), FTransform(FRotator(0.f, EnemyYaw, 0.f), EnemyLoc), nullptr, nullptr, ESpawnActorCollisionHandlingMethod::AlwaysSpawn);
	if (EnemyMech)
	{
		if (!FParse::Param(FCommandLine::Get(), TEXT("IVOldEnemy")))
		{
			EnemyMech->RigAssetPath = TEXT("/Game/Mechs/Enemy/ENEMY_01.ENEMY_01");
			EnemyMech->bUseHullMaterial = true;
			EnemyMech->HullTint = FLinearColor(0.075f, 0.078f, 0.088f);
			EnemyMech->HullAccent = FLinearColor(0.55f, 0.02f, 0.015f);
			EnemyMech->HullGlow = FLinearColor(4.5f, 0.2f, 0.05f);
			EnemyMech->HullAccentAmount = 1.f;
			EnemyMech->SwordEdge = FLinearColor(3.2f, 0.12f, 0.05f);
			EnemyMech->LampColor = FLinearColor(1.f, 0.28f, 0.12f);
			EnemyMech->LampPower = 0.12f;
			EnemyMech->bLampsDown = true;
			EnemyMech->bInfected = IVSettings::GetBool(TEXT("infected")) && !FParse::Param(FCommandLine::Get(), TEXT("IVNoInfect"));
		}
		EnemyMech->FinishSpawning(FTransform(FRotator(0.f, EnemyYaw, 0.f), EnemyLoc));
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

	if (!FParse::Param(FCommandLine::Get(), TEXT("IVNoHeli")))
		AIVHelicopter::SpawnFleet(W, (PlayerLoc + EnemyLoc) * 0.5f, IVSettings::GetInt(TEXT("helis")));

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

	// game flow: title menu -> tutorial -> duel (the command line can skip straight to a state for automated captures)
	if (!FParse::Param(FCommandLine::Get(), TEXT("IVNoCombat")) && !FParse::Param(FCommandLine::Get(), TEXT("IVAutoFight")) && !FParse::Param(FCommandLine::Get(), TEXT("IVNoFlow")))
	{
		if (APawn* Pw = UGameplayStatics::GetPlayerPawn(this, 0))
		{
			AIVCombatDirector* Dr = nullptr;
			for (TActorIterator<AIVCombatDirector> It(W); It; ++It) { Dr = *It; break; }
			if (AIVMechPawn* Pl = Cast<AIVMechPawn>(Pw))
			{
				if (Dr && EnemyMech)
				{
					EIVFlowState Start = EIVFlowState::Menu;
					FString StartName;
					if (FParse::Value(FCommandLine::Get(), TEXT("-IVStart="), StartName))
					{
						if (StartName.Equals(TEXT("tutorial"), ESearchCase::IgnoreCase)) Start = EIVFlowState::Tutorial;
						else if (StartName.Equals(TEXT("duel"), ESearchCase::IgnoreCase)) Start = EIVFlowState::Duel;
						else if (StartName.Equals(TEXT("versus"), ESearchCase::IgnoreCase)) Start = EIVFlowState::Join;
					}
					AIVGameFlow* Fl = W->SpawnActor<AIVGameFlow>(FVector::ZeroVector, FRotator::ZeroRotator);
					if (Fl) Fl->Begin(Pl, EnemyMech, Dr, Start);
				}
			}
		}
	}

	// ambience beds (2D loops)
	if (!FParse::Param(FCommandLine::Get(), TEXT("IVNoAudio")))
	{
		IVAudio::StartLoop2D(W, TEXT("env_rain_loop"), 0.35f);
		IVAudio::StartLoop2D(W, TEXT("env_wind_loop_city"), 0.30f);
		IVAudio::StartLoop2D(W, TEXT("env_siren_distant_loop"), 0.12f);
		IVAudio::StartLoop2D(W, TEXT("env_water_loop_sea"), 0.18f);
		IVAudio::StartLoop2D(W, TEXT("cockpit_reactor_loop"), 0.30f);
		IVAudio::StartLoop2D(W, TEXT("cockpit_breath_loop"), 0.15f);
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
	FParse::Value(FCommandLine::Get(), TEXT("-IVChunkTest="), ChunkTestAt);
	FParse::Value(FCommandLine::Get(), TEXT("-IVProfileAt="), ProfileAt);
	{	// -IVExecAt="12:r.Foo 1|22:r.Bar 2" : console commands at given game times (A/B perf tests in one run)
		FString X;
		if (FParse::Value(FCommandLine::Get(), TEXT("-IVExecAt="), X, false))
		{
			TArray<FString> Items;
			X.ParseIntoArray(Items, TEXT("|"));
			for (const FString& It : Items) { FString T, C; if (It.Split(TEXT(":"), &T, &C)) ExecAt.Add(TPair<float, FString>(FCString::Atof(*T), C)); }
		}
	}
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
	if (!bGfxReapplied && Elapsed > 1.0f) { bGfxReapplied = true; IVGraphics::ApplyAtStart(GetWorld()); IVSettings::Apply(GetWorld()); }   // the viewport has its real size by now
	{	// frame-rate log every 10 s (find it with "IV perf" in the log)
		PerfAcc += Dt; ++PerfFrames; PerfMin = FMath::Min(PerfMin, 1.f / FMath::Max(Dt, 1e-4f));
		if (PerfAcc >= 10.f)
		{
			UE_LOG(LogTemp, Display, TEXT("IV perf: avg %.1f fps, worst frame %.1f fps | game %.1f ms render %.1f ms gpu %.1f ms"), PerfFrames / PerfAcc, PerfMin, FPlatformTime::ToMilliseconds(GGameThreadTime), FPlatformTime::ToMilliseconds(GRenderThreadTime), FPlatformTime::ToMilliseconds(RHIGetGPUFrameCycles(0)));
			PerfAcc = 0.f; PerfFrames = 0; PerfMin = 1e9f;
		}
	}
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
				float YawOff = 0.f; FParse::Value(FCommandLine::Get(), TEXT("-IVCollapseYaw="), YawOff);
				const int32 N = Env->CollapseNearestAhead(P->GetActorLocation(), FRotator(0.f, YawOff, 0.f).RotateVector(P->GetActorForwardVector()));
				UE_LOG(LogTemp, Display, TEXT("IV: collapse test destroyed %d cells"), N);
			}
	}
	for (TPair<float, FString>& E : ExecAt)
		if (E.Key >= 0.f && Elapsed >= E.Key)
		{
			E.Key = -1.f;
			GEngine->Exec(GetWorld(), *E.Value);
			UE_LOG(LogTemp, Display, TEXT("IV exec: %s"), *E.Value);
		}
	if (ProfileAt >= 0.f && Elapsed >= ProfileAt)
	{
		ProfileAt = -1.f;
		GEngine->Exec(GetWorld(), TEXT("ProfileGPU"));
	}
	if (ChunkTestAt >= 0.f && Elapsed >= ChunkTestAt)
	{
		ChunkTestAt = -1.f;
		if (APawn* P = UGameplayStatics::GetPlayerPawn(this, 0))
			if (AIVFXManager* FX = AIVFXManager::Get(GetWorld()))
			{
				const FVector C = P->GetActorLocation() + P->GetActorForwardVector() * 5000.f + FVector(0, 0, 1500.f);
				FX->SpawnChunks(C, FVector(0, 0, 1), 16, EIVChunk::Armor, 3.5f, 5000.f, 1.f);
				FX->SpawnChunks(C, FVector(0, 0, 1), 20, EIVChunk::Concrete, 4.f, 4500.f);
				FX->SpawnChunks(C, FVector(0, 0, 1), 20, EIVChunk::Glass, 5.f, 4500.f);
				FX->SpawnChunks(C, FVector(0, 0, 1), 10, EIVChunk::Steel, 3.f, 4500.f, 0.8f);
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
