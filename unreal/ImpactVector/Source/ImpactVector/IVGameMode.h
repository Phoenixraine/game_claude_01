#pragma once

#include "CoreMinimal.h"
#include "GameFramework/GameModeBase.h"
#include "IVGameMode.generated.h"

class AIVMechPawn;

/** Combat Lab game mode: spawns the environment, the player mech and an enemy mech.
 *  Command line (for automated captures):  -IVCam=N  -IVShots=t1,t2,..  -IVQuit=seconds  -IVAuto=1 */
UCLASS()
class IMPACTVECTOR_API AIVGameMode : public AGameModeBase
{
	GENERATED_BODY()

public:
	AIVGameMode();
	virtual void StartPlay() override;
	virtual void Tick(float DeltaSeconds) override;
	/** The second local player (split screen) gets no pawn of its own: it takes over the enemy mech. */
	virtual UClass* GetDefaultPawnClassForController_Implementation(AController* InController) override;

	UPROPERTY() TObjectPtr<AIVMechPawn> EnemyMech;

private:
	TArray<float> PendingShots;
	int32 ShotIndex = 0;
	float QuitAt = -1.f;
	float BlastAt = -1.f;
	int32 BlastsLeft = 0;
	float NextBlast = 0.f;
	float CollapseAt = -1.f;
	float ChunkTestAt = -1.f;
	float ActionAt = -1.f;
	FName ActionName;
	float Elapsed = 0.f;
	float PerfAcc = 0.f, PerfMin = 1e9f; int32 PerfFrames = 0;
};
