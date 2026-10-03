// Combat director: runs the platform-independent combat core (`core/`, synced into IVCore/) at a fixed 60 Hz,
// feeds it the player's input and the AI's decisions, binds its abstract distance to the real positions of the two mechs
// and turns the event stream into animation, camera shake, FX and HUD state.
#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "iv/Ai.h"
#include "iv/Anim.h"
#include "IVCombat.generated.h"

class AIVMechPawn;

/** Continuous state + one-shot edges of the player's combat controls (filled by the player controller). */
struct FIVCombatInput
{
	bool bStrikeHeld = false;
	iv::SwingSide Side = iv::SwingSide::Up;
	iv::Zone Target = iv::Zone::Torso;
	iv::Footwork Footwork = iv::Footwork::Hold;
	iv::Arm Arm = iv::Arm::R;
	bool bGuardHeld = false;
	iv::SwingSide GuardSide = iv::SwingSide::Up;
	bool bHardStance = false;
	int8 Move = 0;
	int8 DodgeDir = 1;
	bool bWeaponHeld = false;
	iv::EnergyPriority Priority = iv::EnergyPriority::Guard;
	// edges: consumed by the first simulation step after they were set
	bool bQuick = false, bCancel = false, bGrab = false, bSwitchArm = false, bReverse = false, bDodge = false, bUltimate = false, bSetPriority = false;
};

DECLARE_MULTICAST_DELEGATE_OneParam(FIVCombatEventSignature, const iv::Event&);

UCLASS()
class IMPACTVECTOR_API AIVCombatDirector : public AActor
{
	GENERATED_BODY()

public:
	AIVCombatDirector();
	virtual void Tick(float Dt) override;

	/** Player = side A, Enemy = side B. */
	void Setup(AIVMechPawn* InPlayer, AIVMechPawn* InEnemy, iv::Archetype Style, iv::Difficulty Level, uint64 Seed);
	void SetDummy(iv::DummyMode Mode);
	void Restart();
	void EnableAutoPlayer(iv::Archetype Style, iv::Difficulty Level);

	FIVCombatInput PlayerIn;
	FIVCombatEventSignature OnEvent;

	const iv::Duel* GetDuel() const { return Duel.Get(); }
	const iv::AnimState& GetAnim(iv::Side S) const { return Anim[iv::Index(S)]; }
	bool IsMatchOver() const { return Duel.IsValid() && Duel->result().over; }
	bool IsCinematic() const { return Duel.IsValid() && Duel->cinematic().active; }
	FString GetEndText() const { return EndText; }
	float GetSecondsSinceEnd() const { return SinceEnd; }
	iv::Side PlayerSide() const { return iv::Side::A; }

	/** UE <-> core distance mapping: core units are metres between the facing surfaces of the two mechs. */
	static constexpr float kBodyGapUnits = 44.f;

private:
	TUniquePtr<iv::Duel> Duel;
	TUniquePtr<iv::Ai> Bot;
	TUniquePtr<iv::Ai> PlayerBot;   // demo mode (-IVAutoFight): side A is played by a second AI
	TWeakObjectPtr<AIVMechPawn> Player, Enemy;
	iv::AnimState Anim[2];
	iv::Archetype BotStyle = iv::Archetype::Counterpuncher;
	iv::Difficulty BotLevel = iv::Difficulty::Normal;
	uint64 BotSeed = 1;
	double Acc = 0.0;
	FString EndText;
	float SinceEnd = 0.f;
	bool bEndHandled = false;

	void StepOnce(bool bFirstOfFrame);
	float ProximityBehind(AIVMechPawn* Pawn, AIVMechPawn* Other) const;
	void Dispatch(const iv::Event& E);
	AIVMechPawn* PawnOf(iv::Side S) const;
};
