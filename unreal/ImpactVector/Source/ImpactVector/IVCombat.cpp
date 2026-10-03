#include "IVCombat.h"
#include "IVMechPawn.h"
#include "IVFXManager.h"
#include "Engine/World.h"
#include "Kismet/GameplayStatics.h"

namespace
{
	iv::Input BuildInput(const FIVCombatInput& P, bool bEdges)
	{
		iv::Input I;
		I.strikeHeld = P.bStrikeHeld;
		I.side = P.Side;
		I.target = P.Target;
		I.footwork = P.Footwork;
		I.arm = P.Arm;
		I.guardHeld = P.bGuardHeld;
		I.guardSide = P.GuardSide;
		I.hardStance = P.bHardStance;
		I.move = P.Move;
		I.dodgeDir = P.DodgeDir;
		I.weaponHeld = P.bWeaponHeld;
		I.priority = P.Priority;
		if (bEdges)
		{
			I.quick = P.bQuick; I.cancel = P.bCancel; I.toGrab = P.bGrab; I.switchArm = P.bSwitchArm;
			I.reverse = P.bReverse; I.dodge = P.bDodge; I.ultimate = P.bUltimate; I.setPriority = P.bSetPriority;
		}
		return I;
	}
}

AIVCombatDirector::AIVCombatDirector()
{
	PrimaryActorTick.bCanEverTick = true;
	PrimaryActorTick.TickGroup = TG_PrePhysics;
}

void AIVCombatDirector::Setup(AIVMechPawn* InPlayer, AIVMechPawn* InEnemy, iv::Archetype Style, iv::Difficulty Level, uint64 Seed)
{
	Player = InPlayer;
	Enemy = InEnemy;
	BotStyle = Style;
	BotLevel = Level;
	BotSeed = Seed;
	if (Enemy.IsValid()) Enemy->SetExternalControl(true);
	Restart();
}

void AIVCombatDirector::Restart()
{
	Duel = MakeUnique<iv::Duel>(BotSeed, true);
	Bot = MakeUnique<iv::Ai>(BotStyle, BotLevel, BotSeed + 7);
	if (PlayerBot.IsValid()) PlayerBot = MakeUnique<iv::Ai>(iv::Archetype::LimbHunter, BotLevel, BotSeed + 99);
	Acc = 0.0;
	EndText.Empty();
	SinceEnd = 0.f;
	bEndHandled = false;
	PlayerIn = FIVCombatInput();
	UGameplayStatics::SetGlobalTimeDilation(this, 1.f);
}

void AIVCombatDirector::EnableAutoPlayer(iv::Archetype Style, iv::Difficulty Level)
{
	PlayerBot = MakeUnique<iv::Ai>(Style, Level, BotSeed + 99);
}

void AIVCombatDirector::SetDummy(iv::DummyMode Mode)
{
	if (Duel.IsValid()) Duel->SetDummy(iv::Side::B, Mode);
}

AIVMechPawn* AIVCombatDirector::PawnOf(iv::Side S) const
{
	return S == iv::Side::A ? Player.Get() : Enemy.Get();
}

float AIVCombatDirector::ProximityBehind(AIVMechPawn* Pawn, AIVMechPawn* Other) const
{
	if (!Pawn || !Other) return 0.f;
	const FVector From = Pawn->GetActorLocation() + FVector(0, 0, 2500.f);
	const FVector Back = (Pawn->GetActorLocation() - Other->GetActorLocation()).GetSafeNormal2D();
	const float Reach = 7000.f;
	FHitResult Hit;
	FCollisionQueryParams Q(SCENE_QUERY_STAT(IVProx), false, Pawn);
	Q.AddIgnoredActor(Other);
	if (GetWorld()->LineTraceSingleByChannel(Hit, From, From + Back * Reach, ECC_WorldStatic, Q))
	{
		return FMath::Clamp(1.f - Hit.Distance / Reach, 0.f, 1.f);
	}
	return 0.f;
}

void AIVCombatDirector::Tick(float Dt)
{
	Super::Tick(Dt);
	AIVMechPawn* P = Player.Get();
	AIVMechPawn* E = Enemy.Get();
	if (!Duel.IsValid() || !P || !E) return;

	// the enemy always faces the player
	E->SetAim((P->GetActorLocation() - E->GetActorLocation()).Rotation().Yaw, 0.f);

	Acc += FMath::Min<double>(Dt, 0.1);
	const double Step = 1.0 / double(iv::kTickHz);
	bool bFirst = true;
	for (int32 n = 0; Acc >= Step && n < 6; ++n)
	{
		StepOnce(bFirst);
		bFirst = false;
		Acc -= Step;
	}

	Anim[0] = iv::MakeAnimState(Duel->fighter(iv::Side::A));
	Anim[1] = iv::MakeAnimState(Duel->fighter(iv::Side::B));
	P->SetCombatAnim(Anim[0]);
	E->SetCombatAnim(Anim[1]);

	const bool bFrozen = Duel->result().over || Duel->cinematic().active;
	auto Locked = [&](const iv::AnimState& S) {
		return bFrozen || S.legsLocked || (S.posture != iv::Posture::Standing && S.posture != iv::Posture::Dodging);
	};
	P->SetMovementLocked(Locked(Anim[0]));
	E->SetMovementLocked(Locked(Anim[1]));

	static float LogT = 0.f;
	LogT += Dt;
	if (LogT > 4.f)
	{
		LogT = 0.f;
		const iv::Fighter& FA = Duel->fighter(iv::Side::A);
		const iv::Fighter& FB = Duel->fighter(iv::Side::B);
		auto Z = [](const iv::Fighter& F) { FString S; for (int32 z = 0; z < iv::kZoneCount; ++z) S += FString::FromInt(int32(F.body.state(static_cast<iv::Zone>(z)))); return S; };
		UE_LOG(LogTemp, Display, TEXT("IV combat status: t=%.1fs dist=%.1f A[stab=%.2f heat=%.2f ult=%.2f zones=%s phase=%d] B[stab=%.2f heat=%.2f zones=%s phase=%d] over=%d"),
			Duel->tick() / 60.f, Duel->distance(), Anim[0].stability01, Anim[0].heat01, Anim[0].ultimate01, *Z(FA), int32(Anim[0].phase), Anim[1].stability01, Anim[1].heat01, *Z(FB), int32(Anim[1].phase), Duel->result().over ? 1 : 0);
	}
	if (Duel->result().over)
	{
		SinceEnd += Dt;
	}
}

void AIVCombatDirector::StepOnce(bool bFirstOfFrame)
{
	AIVMechPawn* P = Player.Get();
	AIVMechPawn* E = Enemy.Get();
	const FVector Pl = P->GetActorLocation(), En = E->GetActorLocation();
	const float Units = FMath::Clamp((En - Pl).Size2D() / 100.f - kBodyGapUnits, iv::tune::kMinDistance, iv::tune::kMaxDistance);
	Duel->set_distance(Units);

	iv::Input A = BuildInput(PlayerIn, bFirstOfFrame);
	if (PlayerBot.IsValid()) { A = PlayerBot->Decide(iv::MakeObservation(*Duel, iv::Side::A)); P->SetMoveIntent(FVector2D(0.f, float(A.move))); }
	const iv::Input B = Bot->Decide(iv::MakeObservation(*Duel, iv::Side::B));
	iv::World W;
	W.proximity[0] = ProximityBehind(P, E);
	W.proximity[1] = ProximityBehind(E, P);
	W.coolingMult[0] = W.coolingMult[1] = 1.35f;      // rain
	Duel->Step(A, B, W);
	{
		static int32 Dbg = 0;
		if ((Dbg++ % 180) == 0)
			UE_LOG(LogTemp, Display, TEXT("IV step dbg: units=%.2f after=%.2f A[move=%d strike=%d quick=%d guard=%d dodge=%d] B[move=%d strike=%d quick=%d guard=%d] over=%d cin=%d"),
				Units, Duel->distance(), int32(A.move), A.strikeHeld, A.quick, A.guardHeld, A.dodge, int32(B.move), B.strikeHeld, B.quick, B.guardHeld, Duel->result().over, Duel->cinematic().active);
	}

	if (bFirstOfFrame)
	{
		PlayerIn.bQuick = PlayerIn.bCancel = PlayerIn.bGrab = PlayerIn.bSwitchArm = PlayerIn.bReverse = PlayerIn.bDodge = PlayerIn.bUltimate = PlayerIn.bSetPriority = false;
	}

	// the enemy walks as its AI wants (the core's own distance integration is overridden every tick)
	E->SetMoveIntent(FVector2D(0.f, float(B.move)));

	// strikes with a step-in / step-back change the gap: move both mechs symmetrically along the line between them
	const float Delta = Duel->distance() - Units;
	if (FMath::Abs(Delta) > 0.002f && FMath::Abs(Delta) < 25.f && !Duel->cinematic().active)
	{
		const FVector Dir = (En - Pl).GetSafeNormal2D();
		const FVector Shift = Dir * (Delta * 100.f * 0.5f);
		// tiny per-tick displacements: no sweep (the capsule bottoms touch the terrain and sweeps would stick); the pawns re-snap to the ground
		P->AddActorWorldOffset(-Shift, false);
		E->AddActorWorldOffset(Shift, false);
	}

	for (const iv::Event& Ev : Duel->log().events()) Dispatch(Ev);
	Duel->log().Clear();
}

void AIVCombatDirector::Dispatch(const iv::Event& Ev)
{
	using iv::EventType;
	AIVMechPawn* Actor = PawnOf(Ev.actor);
	AIVMechPawn* Other = PawnOf(iv::Other(Ev.actor));
	switch (Ev.type)
	{
	case EventType::HitEvent:
	{
		iv::HitInfo H;
		if (iv::DecodeHit(Ev, &H))
		{
			AIVMechPawn* Defender = PawnOf(iv::Other(H.attacker));
			if (Defender) Defender->OnCombatHit(H.zone, FMath::Clamp(H.damage / 30.f, 0.15f, 1.f), H.wasBlocked, H.wasParried, H.direction);
		}
		break;
	}
	case EventType::Blocked:
	case EventType::ParrySuccess:
	case EventType::InterceptSuccess:
		if (Actor) Actor->OnDefenceEffect(Ev.type == EventType::ParrySuccess, Ev.type == EventType::InterceptSuccess);
		break;
	case EventType::ZoneState:
		if (Actor) Actor->OnZoneState(Ev.zone, static_cast<iv::ZoneState>(Ev.a), static_cast<iv::ZoneState>(Ev.b));
		break;
	case EventType::LimbSevered:
		if (Actor) Actor->OnLimbSevered(Ev.zone);
		break;
	case EventType::ArmorPlateLost:
		if (Actor) Actor->OnArmorPlateLost(Ev.zone, Ev.a, Ev.b);
		break;
	case EventType::Dodge:
		if (Actor) Actor->AddVelocityImpulse(Actor->GetActorRightVector() * (Ev.a >= 0 ? 1.f : -1.f) * 1400.f);
		break;
	case EventType::Knockdown:
		if (Actor) Actor->AddCockpitImpulse(0.f, -1.f, 1.f);
		break;
	case EventType::CinematicBegin:
		if (Player.IsValid()) Player->StartCinematic(Actor, float(Ev.b) / float(iv::kTickHz), Ev.a);
		break;
	case EventType::CinematicEnd:
		if (Player.IsValid()) Player->StopCinematic();
		break;
	case EventType::WeaponFired:
		if (Actor && Other)
		{
			if (AIVFXManager* FX = AIVFXManager::Get(GetWorld()))
			{
				const FVector A = Actor->GetZoneWorldLocation(iv::Zone::ShoulderR);
				const FVector T = Other->GetZoneWorldLocation(iv::Zone::Torso);
				for (int32 i = 0; i < 24; ++i) FX->SpawnSparks(FMath::Lerp(A, T, i / 23.f), (T - A).GetSafeNormal(), 3, 2500.f);
				if (Ev.a > 0) FX->SpawnDust(T, 3500.f, 20, 1.2f);
			}
		}
		break;
	case EventType::MatchEnd:
	{
		const bool bPlayerLost = (Ev.actor == iv::Side::A) && Ev.b == 0;
		UE_LOG(LogTemp, Display, TEXT("IV combat MatchEnd: reason=%d actor=%d b=%d tick=%d"), Ev.a, int32(Ev.actor), Ev.b, Ev.tick);
		EndText = (Ev.b == 1) ? TEXT("DRAW") : (bPlayerLost ? TEXT("DEFEAT") : TEXT("VICTORY"));
		UGameplayStatics::SetGlobalTimeDilation(this, 0.35f);
		bEndHandled = true;
		break;
	}
	default:
		break;
	}
	OnEvent.Broadcast(Ev);
}
