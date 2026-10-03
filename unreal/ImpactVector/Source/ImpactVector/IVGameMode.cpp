#include "IVGameMode.h"
#include "IVMechPawn.h"
#include "IVPlayerController.h"
#include "IVHUD.h"
#include "IVEnvironment.h"
#include "Engine/World.h"
#include "Engine/Engine.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "UnrealClient.h"
#include "HAL/IConsoleManager.h"
#include "Kismet/KismetSystemLibrary.h"

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
	EnemyMech = W->SpawnActor<AIVMechPawn>(FVector(6000.f, 0.f, 4100.f), FRotator(0.f, 180.f, 0.f), P);
	if (EnemyMech)
	{
		EnemyMech->bAIControlled = true;
		EnemyMech->SetBodyTint(FLinearColor(0.9f, 0.45f, 0.4f));
	}

	{
		float StartX = -24000.f, StartY = 0.f, StartYaw = 0.f;
		FParse::Value(FCommandLine::Get(), TEXT("-IVX="), StartX);
		FParse::Value(FCommandLine::Get(), TEXT("-IVY="), StartY);
		FParse::Value(FCommandLine::Get(), TEXT("-IVYaw="), StartYaw);
		if (APlayerController* PC = W->GetFirstPlayerController())
		{
			if (APawn* Pawn = PC->GetPawn())
			{
				Pawn->SetActorLocationAndRotation(FVector(StartX, StartY, 4100.f), FRotator(0.f, StartYaw, 0.f), false, nullptr, ETeleportType::TeleportPhysics);
				if (AIVMechPawn* M = Cast<AIVMechPawn>(Pawn)) M->SetAim(StartYaw, 0.f);
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
	if (QuitAt > 0.f && Elapsed >= QuitAt)
	{
		UKismetSystemLibrary::QuitGame(this, nullptr, EQuitPreference::Quit, false);
		QuitAt = -1.f;
	}
}
