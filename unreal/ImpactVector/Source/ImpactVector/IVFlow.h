// Game flow: title menu -> tutorial (a training dummy and a list of exercises) -> real duel -> result screen.
// Also owns the texts the HUD shows (menu, tutorial prompt, banners).
#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "iv/Events.h"
#include "iv/Types.h"
#include "IVFlow.generated.h"

class AIVMechPawn;
class AIVCombatDirector;
class AIVPlayerController;
class UAudioComponent;

enum class EIVFlowState : uint8 { Menu, Tutorial, Duel, Result };

enum class ETutGoal : uint8 { Timer, Walk, Look, HeavyHit, QuickHit, Defend, Evade, Counter, Ability, Scoop, Ultimate };

struct FIVTutorialStep
{
	FString Title;
	FString Body;
	FString Keys;
	ETutGoal Goal = ETutGoal::Timer;
	int32 Count = 1;
	float Seconds = 0.f;               // for timers
	iv::DummyMode Dummy = iv::DummyMode::Passive;
	int32 Script = 0;                  // 0 default, 1 any-side heavies, 2 lateral only
	bool bFullUltimate = false;
};

UCLASS()
class IMPACTVECTOR_API AIVGameFlow : public AActor
{
	GENERATED_BODY()

public:
	AIVGameFlow();
	virtual void Tick(float Dt) override;

	void Begin(AIVMechPawn* InPlayer, AIVMechPawn* InEnemy, AIVCombatDirector* InDir, EIVFlowState Initial);

	EIVFlowState GetState() const { return State; }
	// ---- menu
	TArray<FString> GetMenuItems() const;
	int32 GetMenuIndex() const { return MenuIndex; }
	FString GetDifficultyName() const;
	// ---- prompts
	bool HasPrompt() const { return State == EIVFlowState::Tutorial && Steps.IsValidIndex(Step); }
	const FIVTutorialStep& GetStep() const { return Steps[Step]; }
	int32 GetStepIndex() const { return Step; }
	int32 GetStepCount() const { return Steps.Num(); }
	float GetStepProgress01() const;
	float GetStepDoneFlash() const { return StepDoneFlash; }
	// ---- banners
	const FString& GetBanner() const { return Banner; }
	float GetBannerAlpha() const { return FMath::Clamp(BannerLeft / 0.6f, 0.f, 1.f); }
	const FString& GetSubBanner() const { return SubBanner; }
	float GetResultTime() const { return ResultT; }
	FString GetStatsLine() const;

private:
	UPROPERTY() TObjectPtr<AIVMechPawn> Player;
	UPROPERTY() TObjectPtr<AIVMechPawn> Enemy;
	UPROPERTY() TObjectPtr<AIVCombatDirector> Dir;

	EIVFlowState State = EIVFlowState::Menu;
	int32 MenuIndex = 0;
	int32 Difficulty = 1;
	int32 NextStyle = 0;
	FTransform PlayerHome, EnemyHome;

	TArray<FIVTutorialStep> Steps;
	int32 Step = 0;
	int32 Progress = 0;
	float StepTimer = 0.f, StepDoneFlash = 0.f;
	bool bStepDone = false;
	float WalkAcc = 0.f, LookAcc = 0.f;
	FVector LastPlayerPos = FVector::ZeroVector;
	float LastYaw = 0.f;
	float SinceDefence = 99.f;

	FString Banner, SubBanner;
	float BannerLeft = 0.f;
	float ResultT = 0.f;
	float EndDelay = -1.f;
	float DuelClock = 0.f;
	int32 HitsLanded = 0, HitsTaken = 0, Parries = 0;

	void BuildSteps();
	void EnterMenu();
	void EnterTutorial();
	void EnterDuel();
	void EnterResult();
	void BeginStep(int32 Index);
	void AdvanceStep();
	void PlaceMechs(float CoreUnits);
	void SetBanner(const FString& Main, const FString& Sub, float Seconds);
	void OnCombatEvent(const iv::Event& Ev);
	void MenuInput();
	AIVPlayerController* PC() const;

	// ---- music: stems that fade in with the intensity of the fight
	UPROPERTY() TArray<TObjectPtr<UAudioComponent>> MusicStems;   // 0 drums 1 bass 2 synth 3 lead
	UPROPERTY() TObjectPtr<UAudioComponent> MenuMusic;
	float Intensity = 0.f, LastAction = 0.f;
	void StartBattleMusic();
	void StopBattleMusic();
	void StartMenuMusic(float Volume);
	void UpdateMusic(float Dt);
	FDelegateHandle EventHandle;
};
