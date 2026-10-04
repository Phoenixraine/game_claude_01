#include "IVCombat.h"
#include "IVMechPawn.h"
#include "IVFXManager.h"
#include "IVHelicopter.h"
#include "EngineUtils.h"
#include "IVAudio.h"
#include "IVEnvironment.h"
#include "IVAbilities.h"
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
		I.lungeHeld = P.bLungeHeld;
		if (bEdges)
		{
			I.jump = P.bJump; I.chop = P.bChop; I.slide = P.bSlide; I.mash = P.bMash; I.berserk = P.bBerserk; I.qte = P.bQte;
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
	if (Player.IsValid()) Player->OnCrash.AddUObject(this, &AIVCombatDirector::OnMechCrash);
	if (Enemy.IsValid()) Enemy->OnCrash.AddUObject(this, &AIVCombatDirector::OnMechCrash);
	Restart();
}

void AIVCombatDirector::Restart()
{
	Duel = MakeUnique<iv::Duel>(BotSeed, true);
	Bot = MakeUnique<iv::Ai>(BotStyle, BotLevel, BotSeed + 7);
	Duel->SetAiLevel(iv::Side::B, bHumanB ? -1 : static_cast<int>(BotLevel));
	Duel->SetAiLevel(iv::Side::A, PlayerBot.IsValid() ? static_cast<int>(BotLevel) : -1);
	if (PlayerBot.IsValid()) PlayerBot = MakeUnique<iv::Ai>(iv::Archetype::LimbHunter, BotLevel, BotSeed + 99);
	Acc = 0.0;
	EndText.Empty();
	SinceEnd = 0.f;
	bEndHandled = false;
	PlayerIn = FIVCombatInput();
	PlayerIn2 = FIVCombatInput();
	UGameplayStatics::SetGlobalTimeDilation(this, 1.f);
	ScoopCooldown[0] = ScoopCooldown[1] = 0.f;
	HitStop = 0.f;
	if (Player.IsValid()) Player->ResetForNewMatch();
	if (Enemy.IsValid()) Enemy->ResetForNewMatch();
}

void AIVCombatDirector::EnableAutoPlayer(iv::Archetype Style, iv::Difficulty Level)
{
	PlayerBot = MakeUnique<iv::Ai>(Style, Level, BotSeed + 99);
	if (Duel.IsValid()) Duel->SetAiLevel(iv::Side::A, static_cast<int>(Level));
}

void AIVCombatDirector::SetHumanB(bool b)
{
	bHumanB = b;
	if (Duel.IsValid()) Duel->SetAiLevel(iv::Side::B, b ? -1 : static_cast<int>(BotLevel));
	if (Enemy.IsValid()) Enemy->SetExternalControl(true);
}

void AIVCombatDirector::SetAutopilot(iv::Side S, bool bOn)
{
	if (Duel.IsValid()) Duel->fighter(S).set_autopilot(bOn);
}

void AIVCombatDirector::RepairBreakdown(iv::Side S, int32 Levels)
{
	if (!Duel.IsValid()) return;
	Duel->RepairBreakdown(S, Levels);
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

	if (!Duel->cinematic().active && !Duel->result().over)
	{
		for (int32 s = 0; s < 2; ++s) ScoopCooldown[s] = FMath::Max(0.f, ScoopCooldown[s] - Dt);
	}
	if (HitStop > 0.f)
	{
		HitStop -= Dt;   // Dt is already dilated: it shrinks slowly in game time, which is the point
		if (HitStop <= 0.f && !Duel->result().over) UGameplayStatics::SetGlobalTimeDilation(this, 1.f);
	}
	// the enemy always faces the player
	if (!bHumanB) E->SetAim((P->GetActorLocation() - E->GetActorLocation()).Rotation().Yaw, 0.f);

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
	{	// everything the cockpit monitors and alarms show
		FIVCockpitFeed Fd;
		const iv::Fighter& FA = Duel->fighter(iv::Side::A);
		const iv::Fighter& FB = Duel->fighter(iv::Side::B);
		for (int32 z = 0; z < iv::kZoneCount; ++z)
		{
			const iv::Zone Zn = static_cast<iv::Zone>(z);
			Fd.Armor[z] = FMath::Clamp(FA.body.layer(Zn, iv::Layer::Armor) / iv::tune::kArmorMax[z], 0.f, 1.f);
			Fd.Mech[z] = FMath::Clamp(FA.body.layer(Zn, iv::Layer::Mechanism) / iv::tune::kMechanismMax[z], 0.f, 1.f);
			Fd.State[z] = uint8(FA.body.state(Zn));
			Fd.EnemyArmor[z] = FMath::Clamp(FB.body.layer(Zn, iv::Layer::Armor) / iv::tune::kArmorMax[z], 0.f, 1.f);
			Fd.EnemyState[z] = uint8(FB.body.state(Zn));
		}
		Fd.Overall = FA.body.Integrity(); Fd.EnemyOverall = FB.body.Integrity();
		Fd.Stability = FA.res.stability / 100.f; Fd.Heat = FA.res.heat / 100.f; Fd.Energy = FA.res.energy / 100.f; Fd.Ultimate = FA.ultimate / 100.f;
		Fd.EnemyStability = FB.res.stability / 100.f; Fd.EnemyEnergy = FB.res.energy / 100.f;
		const FVector To = E->GetActorLocation() - P->GetActorLocation();
		Fd.DistM = To.Size2D() / 100.f;
		Fd.BearingDeg = FRotator::NormalizeAxis(To.Rotation().Yaw - P->GetAimYaw());
		const iv::WeaponKind Ks[3] = { iv::WeaponKind::SuppressionRockets, iv::WeaponKind::RailSpear, iv::WeaponKind::PlasmaCannon };
		for (int32 i = 0; i < 3; ++i)
		{
			Fd.WeaponReady[i] = FA.AmmoOf(Ks[i]) == 0 ? 0.f : 1.f - FMath::Clamp(float(FA.CooldownOf(Ks[i])) / float(iv::tune::kWeapons[iv::Index(Ks[i])].cooldownTicks), 0.f, 1.f);
			if (FA.weapon == Ks[i]) Fd.Weapon = i;
		}
		Fd.Scoop = GetScoopReady01(iv::Side::A);
		Fd.bBurn = FA.burnTicks > 0; Fd.bBlind = FA.Blind(); Fd.bStrikeLock = FA.strikeLockTicks > 0;
		Fd.Speed01 = P->GetSpeedRatio();
		Fd.bValid = true;
		P->SetCockpitFeed(Fd);
	}

	if (Duel->lock().active)
	{
		LockSparkAcc += Dt;
		if (LockSparkAcc > 0.07f)
		{
			LockSparkAcc = 0.f;
			FVector B0, T0, B1, T1;
			P->GetBladeSegment(B0, T0);
			E->GetBladeSegment(B1, T1);
			const FVector At = (T0 + T1) * 0.5f;
			if (AIVFXManager* FX = AIVFXManager::Get(GetWorld())) { FX->SpawnSparks(At, FVector(0, 0, 1), 18, 6000.f); FX->SpawnFlash(At, FLinearColor(1.f, 0.85f, 0.5f), 1.2e5f, 0.1f, 9000.f); }
			P->AddCockpitImpulse(FMath::RandRange(-1.f, 1.f), FMath::RandRange(-0.5f, 0.5f), 0.55f);
			E->AddCockpitImpulse(FMath::RandRange(-1.f, 1.f), FMath::RandRange(-0.5f, 0.5f), 0.35f);
		}
	}
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

	if (PlayerIn.WeaponSelect >= 0)
	{
		static const iv::WeaponKind Map[3] = { iv::WeaponKind::RailSpear, iv::WeaponKind::SuppressionRockets, iv::WeaponKind::PlasmaCannon };
		Duel->SelectWeapon(iv::Side::A, Map[FMath::Clamp<int32>(PlayerIn.WeaponSelect, 0, 2)]);
		PlayerIn.WeaponSelect = -1;
	}
	if (PlayerIn.bScoop) { TryScoop(iv::Side::A); PlayerIn.bScoop = false; }
	iv::Input A = BuildInput(PlayerIn, bFirstOfFrame);
	if (PlayerBot.IsValid()) { A = PlayerBot->Decide(iv::MakeObservation(*Duel, iv::Side::A)); P->SetMoveIntent(FVector2D(0.f, float(A.move))); }
	const iv::Input B = bHumanB ? BuildInput(PlayerIn2, bFirstOfFrame) : Bot->Decide(iv::MakeObservation(*Duel, iv::Side::B));
	iv::World W;
	W.proximity[0] = ProximityBehind(P, E);
	W.proximity[1] = ProximityBehind(E, P);
	W.coolingMult[0] = W.coolingMult[1] = 1.35f;      // rain
	Duel->Step(A, B, W);
	AiScoopTimer -= 1.f / float(iv::kTickHz);
	if (AiScoopTimer <= 0.f)
	{
		AiScoopTimer = FMath::RandRange(22.f, 40.f);
		if (BotLevel != iv::Difficulty::Easy && !PlayerBot.IsValid()) TryScoop(iv::Side::B);
	}
	{
		static int32 Dbg = 0;
		if ((Dbg++ % 180) == 0)
			UE_LOG(LogTemp, Display, TEXT("IV step dbg: units=%.2f after=%.2f A[move=%d strike=%d quick=%d guard=%d dodge=%d] B[move=%d strike=%d quick=%d guard=%d] over=%d cin=%d"),
				Units, Duel->distance(), int32(A.move), A.strikeHeld, A.quick, A.guardHeld, A.dodge, int32(B.move), B.strikeHeld, B.quick, B.guardHeld, Duel->result().over, Duel->cinematic().active);
	}

	if (bFirstOfFrame)
	{
		PlayerIn.bQuick = PlayerIn.bCancel = PlayerIn.bGrab = PlayerIn.bSwitchArm = PlayerIn.bReverse = PlayerIn.bDodge = PlayerIn.bUltimate = PlayerIn.bSetPriority = false;
		PlayerIn.bJump = PlayerIn.bChop = PlayerIn.bSlide = PlayerIn.bMash = PlayerIn.bBerserk = PlayerIn.bQte = false;
		PlayerIn2.bQuick = PlayerIn2.bCancel = PlayerIn2.bGrab = PlayerIn2.bSwitchArm = PlayerIn2.bReverse = PlayerIn2.bDodge = PlayerIn2.bUltimate = PlayerIn2.bSetPriority = false;
		PlayerIn2.bJump = PlayerIn2.bChop = PlayerIn2.bSlide = PlayerIn2.bMash = PlayerIn2.bBerserk = PlayerIn2.bQte = false;
	}

	// the enemy walks as its AI wants (the core's own distance integration is overridden every tick)
	if (!bHumanB) E->SetMoveIntent(FVector2D(0.f, float(B.move)));

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

void AIVCombatDirector::PlayEventSound(const iv::Event& Ev)
{
	using iv::EventType;
	UWorld* W = GetWorld();
	AIVMechPawn* Actor = PawnOf(Ev.actor);
	const bool bPlayerActor = (Ev.actor == iv::Side::A);
	const FVector At = Actor ? Actor->GetZoneWorldLocation(Ev.zone) : FVector::ZeroVector;
	switch (Ev.type)
	{
	case EventType::WindupStarted:
		if (Actor) IVAudio::Play3D(W, TEXT("mech_servo_arm_windup"), At, 0.9f, FMath::RandRange(0.92f, 1.05f));
		break;
	case EventType::Committed:
		if (Actor) IVAudio::Play3D(W, TEXT("mech_servo_arm_strike"), Actor->GetActorLocation() + FVector(0, 0, 4000.f), 1.f, FMath::RandRange(0.95f, 1.05f));
		break;
	case EventType::EmergencyBrake:
	case EventType::Dodge:
		if (Actor) IVAudio::Play3D(W, TEXT("mech_hydraulic_release"), Actor->GetActorLocation() + FVector(0, 0, 1500.f), 1.f);
		break;
	case EventType::HitEvent:
	{
		iv::HitInfo H;
		if (!iv::DecodeHit(Ev, &H) || !PawnOf(iv::Other(H.attacker))) break;
		AIVMechPawn* Def = PawnOf(iv::Other(H.attacker));
		const FVector Loc = Def->GetZoneWorldLocation(H.zone);
		const bool bHeavy = H.damage > 18.f;
		IVAudio::Play3D(W, bHeavy ? TEXT("hit_metal_contact_heavy") : TEXT("hit_metal_contact_light"), Loc, H.wasBlocked ? 0.6f : 1.f);
		IVAudio::Play3D(W, bHeavy ? TEXT("hit_lowfreq_thump_heavy") : TEXT("hit_lowfreq_thump_light"), Loc, 1.f);
		if (!H.wasBlocked) IVAudio::Play3D(W, IVAudio::Variant(TEXT("hit_deform_"), 3), Loc, 0.8f);
		IVAudio::Play3DDelayed(W, IVAudio::Variant(TEXT("hit_debris_delay_"), 3), Loc, 0.5f, 0.7f);
		if (Def->IsLocallyControlled())
		{
			IVAudio::Play2D(W, bHeavy ? TEXT("hit_cockpit_rumble_heavy") : TEXT("hit_cockpit_rumble_light"), H.wasBlocked ? 0.5f : 0.9f);
			IVAudio::Play2D(W, TEXT("hit_compensator_kick"), 0.5f);
		}
		break;
	}
	case EventType::Blocked: if (Actor) IVAudio::Play3D(W, TEXT("block_impact"), At, 1.f); break;
	case EventType::ParrySuccess: if (Actor) IVAudio::Play3D(W, TEXT("parry_clang"), At, 1.f); break;
	case EventType::InterceptSuccess: if (Actor) IVAudio::Play3D(W, TEXT("intercept_clash"), At, 1.f); break;
	case EventType::EnergyShift: case EventType::EnergyFlow:
		if (bPlayerActor) IVAudio::Play2D(W, TEXT("mech_power_shift"), 0.7f);
		else if (Actor) IVAudio::Play3D(W, TEXT("mech_power_shift"), Actor->GetActorLocation() + FVector(0, 0, 4500.f), 0.8f);
		break;
	case EventType::HeatWarning: if (bPlayerActor) IVAudio::Play2D(W, TEXT("cockpit_alarm_warning"), 0.8f); break;
	case EventType::SystemFailure:
		if (bPlayerActor) { IVAudio::Play2D(W, TEXT("cockpit_alarm_critical"), 0.9f); IVAudio::Play2D(W, IVAudio::Variant(TEXT("cockpit_spark_"), 4), 0.9f); }
		break;
	case EventType::ZoneState:
		if (Ev.a >= int32(iv::ZoneState::Damaged) && Ev.b < int32(iv::ZoneState::Damaged) && Actor)
		{
			IVAudio::Play3D(W, IVAudio::Variant(TEXT("mech_joint_creak_"), 3), At, 0.9f);
			if (bPlayerActor) IVAudio::Play2D(W, IVAudio::Variant(TEXT("cockpit_spark_"), 4), 0.8f);
		}
		break;
	case EventType::ArmorPlateLost: if (Actor) IVAudio::Play3D(W, TEXT("mech_armor_plate_tear"), At, 1.f); break;
	case EventType::LimbSevered:
		if (Actor) IVAudio::Play3D(W, TEXT("mech_limb_sever"), At, 1.f);
		if (bPlayerActor) IVAudio::Play2D(W, TEXT("cockpit_panel_burst"), 1.f);
		break;
	case EventType::Knockdown: if (Actor) IVAudio::Play3D(W, TEXT("env_distant_boom_01"), Actor->GetActorLocation(), 1.f); break;
	case EventType::HardStanceOn: if (Actor) IVAudio::Play3D(W, TEXT("mech_stabilizer_whine"), Actor->GetActorLocation() + FVector(0, 0, 2000.f), 0.8f); break;
	case EventType::WeaponCharging: if (Actor) IVAudio::Play3D(W, TEXT("mech_weapon_charge_peak"), Actor->GetZoneWorldLocation(iv::Zone::ShoulderR), 0.9f); break;
	case EventType::WeaponFired: if (Actor) IVAudio::Play3D(W, TEXT("mech_weapon_fire"), Actor->GetZoneWorldLocation(iv::Zone::ShoulderR), 1.f); break;
	case EventType::CinematicBegin: IVAudio::Play2D(W, TEXT("mus_commit_hit"), 0.9f); break;
	case EventType::UltimateReady: if (bPlayerActor) IVAudio::Play2D(W, TEXT("cockpit_hud_lock"), 0.9f); break;
	case EventType::Clinch: if (Actor) IVAudio::Play3D(W, TEXT("intercept_clash"), Actor->GetActorLocation() + FVector(0, 0, 3000.f), 0.9f); break;
	case EventType::StaggerBegin: if (bPlayerActor) IVAudio::Play2D(W, TEXT("cockpit_harness_creak"), 0.9f); break;
	case EventType::LungeCharging: if (Actor) IVAudio::Play3D(W, TEXT("mech_weapon_charge_peak"), Actor->GetZoneWorldLocation(iv::Zone::ArmR), 0.8f, 0.7f); break;
	case EventType::JumpStarted:
		if (Actor) { IVAudio::Play3D(W, TEXT("mech_hydraulic_release"), Actor->GetActorLocation(), 1.f, 0.8f); IVAudio::Play3D(W, TEXT("env_missile_incoming"), Actor->GetActorLocation(), 0.7f, 1.4f); }
		break;
	case EventType::JumpEvadedLunge: if (Actor) IVAudio::Play3D(W, TEXT("mech_stabilizer_whine"), Actor->GetActorLocation(), 0.9f, 1.3f); break;
	case EventType::AirChopStarted: if (Actor) IVAudio::Play3D(W, TEXT("mech_servo_arm_strike"), Actor->GetActorLocation(), 1.f, 0.8f); break;
	case EventType::SlideStarted: if (Actor) IVAudio::Play3D(W, TEXT("env_concrete_crumble"), Actor->GetActorLocation() - FVector(0, 0, 3500.f), 0.9f, 1.2f); break;
	case EventType::LockStarted: IVAudio::Play2D(W, TEXT("intercept_clash"), 1.f, 0.7f); if (Actor) IVAudio::Play3D(W, TEXT("clinch_grind_loop"), Actor->GetActorLocation() + FVector(0, 0, 3500.f), 0.9f); break;
	case EventType::LockResolved: IVAudio::Play2D(W, TEXT("parry_clang"), 1.f, 0.7f); IVAudio::Play2D(W, TEXT("hit_lowfreq_thump_heavy"), 1.f); break;
	case EventType::BerserkStarted: IVAudio::Play2D(W, TEXT("mus_commit_hit"), 1.f, 0.7f); IVAudio::Play2D(W, TEXT("cockpit_alarm_critical"), 0.8f, 0.6f); break;
	case EventType::BerserkSwing: if (Actor) IVAudio::Play3D(W, TEXT("mech_servo_arm_strike"), Actor->GetActorLocation() + FVector(0, 0, 4000.f), 1.f, 0.7f); break;
	case EventType::BerserkParried: IVAudio::Play2D(W, TEXT("parry_clang"), 1.f); break;
	case EventType::BerserkPierce: IVAudio::Play2D(W, TEXT("mech_limb_sever"), 1.f, 0.6f); IVAudio::Play2D(W, TEXT("env_missile_explosion"), 1.f); break;
	case EventType::BerserkOverload: IVAudio::Play2D(W, TEXT("cockpit_sensor_fail_static"), 1.f); IVAudio::Play2D(W, TEXT("cockpit_panel_burst"), 1.f); break;
	case EventType::CounterPunch: IVAudio::Play2D(W, TEXT("hit_lowfreq_thump_heavy"), 1.f, 0.6f); IVAudio::Play2D(W, TEXT("env_distant_boom_01"), 1.f); break;
	case EventType::BreakdownStarted: if (bPlayerActor) IVAudio::Play2D(W, TEXT("cockpit_alarm_critical"), 0.9f); break;
	case EventType::BreakdownRepaired: if (bPlayerActor) IVAudio::Play2D(W, TEXT("cockpit_hud_unlock"), 1.f); break;
	default: break;
	}
}

void AIVCombatDirector::HitCity(const iv::Event& Ev)
{
	// A missed strike (or a wall slam) lands on whatever stands behind the opponent: buildings take real damage.
	AIVMechPawn* Attacker = PawnOf(Ev.actor);
	AIVMechPawn* Target = PawnOf(iv::Other(Ev.actor));
	if (!Attacker || !Target) return;
	AIVEnvironment* Env = AIVEnvironment::Get(GetWorld());
	if (!Env) return;
	const FVector Dir = (Target->GetActorLocation() - Attacker->GetActorLocation()).GetSafeNormal2D();
	const FVector From = Attacker->GetActorLocation() + FVector(0, 0, 3200.f);
	FHitResult Hit;
	FCollisionQueryParams Q(SCENE_QUERY_STAT(IVCityHit), false, Attacker);
	Q.AddIgnoredActor(Target);
	const FVector Side = FVector::CrossProduct(Dir, FVector::UpVector).GetSafeNormal();
	const FVector To = From + (Dir + Side * (Ev.zone == iv::Zone::ArmL ? -0.45f : 0.45f)).GetSafeNormal() * 11000.f;
	if (GetWorld()->LineTraceSingleByChannel(Hit, From, To, ECC_WorldStatic, Q) && Hit.Distance < 10500.f)
	{
		const float R = Ev.type == iv::EventType::WallSlam ? 3800.f : 2600.f;
		Env->BlastAt(Hit.ImpactPoint, R, 1700.f);
		if (AIVFXManager* FX = AIVFXManager::Get(GetWorld())) FX->SpawnSparks(Hit.ImpactPoint, Hit.ImpactNormal, 40, 5000.f);
		IVAudio::Play3D(GetWorld(), TEXT("env_concrete_crumble"), Hit.ImpactPoint, 1.f);
		if (Attacker->IsLocallyControlled()) Attacker->AddCockpitImpulse(0.f, 0.f, 0.5f);
	}
}

void AIVCombatDirector::BladeImpact(AIVMechPawn* A, AIVMechPawn* B, float Scale, bool bStop)
{
	if (!A || !B) return;
	FVector A0, A1, B0, B1;
	A->GetBladeSegment(A0, A1);
	B->GetBladeSegment(B0, B1);
	FVector PA, PB;
	FMath::SegmentDistToSegment(A0, A1, B0, B1, PA, PB);
	const FVector At = (PA + PB) * 0.5f;
	if (AIVFXManager* FX = AIVFXManager::Get(GetWorld()))
	{
		FX->SpawnSparks(At, (A->GetActorForwardVector() - B->GetActorForwardVector()).GetSafeNormal() + FVector(0, 0, 0.6f), int32(260 * Scale), 9000.f);
		FX->SpawnDust(At, 2000.f * Scale, int32(14 * Scale), 0.8f);
		FX->SpawnFlash(At, FLinearColor(0.85f, 0.95f, 1.f), 2.0e5f * Scale, 0.22f, 12000.f);
	}
	A->SetSwordHeat(1.f);
	B->SetSwordHeat(1.f);
	if (bStop) ApplyHitStop(0.14f, 0.12f);
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
		// the swords really meet: sparks and a flash where the two blades are closest
		BladeImpact(Actor, Other, Ev.type == EventType::Blocked ? 0.7f : 1.15f, Ev.type != EventType::Blocked);
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
		if (Actor)
		{
			Actor->AddCockpitImpulse(0.f, -1.f, 1.f);
			if (AIVEnvironment* Env = AIVEnvironment::Get(GetWorld()))
			{
				const FVector Fall = Actor->GetActorLocation() - Actor->GetActorForwardVector() * 3600.f + FVector(0, 0, 1200.f);
				Env->BlastAt(Fall, 4600.f, 2200.f);
			}
			if (AIVFXManager* FX = AIVFXManager::Get(GetWorld())) { FX->SpawnDust(Actor->GetActorLocation(), 4200.f, 50, 2.2f); FX->SpawnSparks(Actor->GetActorLocation(), FVector::UpVector, 80, 6000.f); }
		}
		break;
	case EventType::CinematicBegin:
		if (Player.IsValid()) Player->StartCinematic(Actor, float(Ev.b) / float(iv::kTickHz), Ev.a);
		if (Actor && Other)
		{
			if (Ev.a == int32(iv::CinematicKind::UltimateBisect)) Actor->StartUltimateScript(Other, 1);
			else if (Ev.a == int32(iv::CinematicKind::UltimateSever)) Actor->StartUltimateScript(Other, 2);
			else if (Ev.a == int32(iv::CinematicKind::Ultimate)) Actor->StartUltimateScript(Other, 0);
			else Actor->PlaySequence({ FName("weapon_charge_hold"), FName("weapon_charge_peak"), FName("weapon_charge_peak"), FName("guard_neutral") }, { 0.3f, 0.5f, 0.9f, 0.6f });
		}
		break;
	case EventType::CinematicEnd:
		if (Player.IsValid()) Player->StopCinematic();
		break;
	case EventType::WeaponFired:
		if (Actor && Other)
		{
			FActorSpawnParameters Sp;
			Sp.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
			if (AIVProjectile* Pj = GetWorld()->SpawnActor<AIVProjectile>(Actor->GetZoneWorldLocation(iv::Zone::ShoulderR), FRotator::ZeroRotator, Sp))
			{
				const int32 K = FMath::Clamp(Ev.b, 0, 2);   // WeaponKind: 0 rail, 1 rockets, 2 plasma
				Pj->Launch(K == 0 ? 0 : (K == 1 ? 1 : 2), Actor->GetZoneWorldLocation(iv::Zone::ShoulderR), Other, Ev.a > 0, K == 0 ? 0.55f : (K == 1 ? 1.1f : 0.8f));
			}
		}
		break;
	// ---------------------------------------------------------------- v5 moves
	case EventType::LungeCharging:
		if (Actor && Actor->IsLocallyControlled()) Actor->AddCockpitImpulse(0.f, 0.f, 0.3f);
		break;
	case EventType::JumpStarted:
		if (Actor)
		{
			Actor->AddCockpitImpulse(0.f, 1.f, 1.2f);
			if (AIVFXManager* FX = AIVFXManager::Get(GetWorld())) { FX->SpawnDust(Actor->GetActorLocation() - FVector(0, 0, 4000.f), 3600.f, 30, 2.f); FX->SpawnFlash(Actor->GetActorLocation() - FVector(0, 0, 2800.f), FLinearColor(1.f, 0.6f, 0.25f), 3.0e5f, 0.5f, 18000.f); }
		}
		break;
	case EventType::JumpEvadedLunge:
		if (Actor && Other) { Actor->AddCockpitImpulse(0.f, 0.f, 0.5f); Other->AddCockpitImpulse(0.f, -1.f, 1.2f); }
		break;
	case EventType::AirChopStarted:
		if (Actor) Actor->PlayAction(FName(TEXT("swing_up_r_commit")), 1.6f);
		break;
	case EventType::SlideStarted:
		if (Actor)
		{
			Actor->AddVelocityImpulse(Actor->GetActorForwardVector() * 2200.f);
			if (AIVFXManager* FX = AIVFXManager::Get(GetWorld())) { FX->SpawnDust(Actor->GetActorLocation() - FVector(0, 0, 4000.f), 3600.f, 24, 1.6f); FX->SpawnSparks(Actor->GetActorLocation() - FVector(0, 0, 3900.f), FVector::UpVector, 60, 5500.f); }
		}
		break;
	case EventType::SlideEvadedChop:
		if (Other) Other->AddCockpitImpulse(0.f, -1.f, 1.4f);
		break;
	case EventType::LockStarted:
		if (Actor) Actor->StartLockPose(true);
		if (Other) Other->StartLockPose(true);
		BladeImpact(Actor, Other, 1.6f, true);
		if (Actor && Actor->IsLocallyControlled()) Actor->AddCockpitImpulse(0.f, 0.f, 1.4f);
		if (Other && Other->IsLocallyControlled()) Other->AddCockpitImpulse(0.f, 0.f, 1.4f);
		LockSparkAcc = 0.f;
		break;
	case EventType::LockResolved:
		if (Actor) Actor->StartLockPose(false);
		if (Other) Other->StartLockPose(false);
		BladeImpact(Actor, Other, 1.8f, true);
		if (Other) Other->AddCockpitImpulse(0.f, 1.f, 2.0f);
		break;
	case EventType::BerserkStarted:
		if (Actor) { Actor->SetRage(1.f); Actor->PlayAction(FName(TEXT("grab_clamp")), 1.f); }
		if (Other) Other->PlayAction(FName(TEXT("grab_clamp")), 1.f);
		if (AIVFXManager* FX = AIVFXManager::Get(GetWorld())) if (Actor) FX->SpawnFlash(Actor->GetZoneWorldLocation(iv::Zone::Torso), FLinearColor(1.f, 0.1f, 0.05f), 4.0e5f, 0.8f, 20000.f);
		break;
	case EventType::BerserkSwing:
		if (Actor) Actor->PlayBerserkSwing(static_cast<iv::SwingSide>(Ev.b));
		break;
	case EventType::BerserkParried:
		if (Actor && Other) { BladeImpact(Actor, Other, 1.3f, true); Other->AddCockpitImpulse(0.f, 0.f, 1.0f); Actor->AddCockpitImpulse(0.f, 0.f, 0.8f); }
		break;
	case EventType::BerserkPierce:
		if (Actor) Actor->SetRage(0.f);
		if (Other)
		{
			if (AIVFXManager* FX = AIVFXManager::Get(GetWorld())) { FX->SpawnExplosion(Other->GetZoneWorldLocation(iv::Zone::Torso), 1.8f); FX->SpawnSparks(Other->GetZoneWorldLocation(iv::Zone::Torso), -Other->GetActorForwardVector(), 220, 9000.f); }
			Other->AddCockpitImpulse(0.f, 1.f, 3.f);
			Other->PlaySequence({ FName(TEXT("knockdown_fall")), FName(TEXT("knockdown_down")), FName(TEXT("kneel")) }, { 0.6f, 1.6f, 2.f });
		}
		ApplyHitStop(0.5f, 0.1f);
		break;
	case EventType::BerserkOverload:
		if (Actor) { Actor->SetRage(0.f); Actor->AddCockpitImpulse(0.f, -1.f, 2.f); }
		break;
	case EventType::CounterPunch:
		if (Actor && Other) Actor->StartCounterPunch(Other);
		ApplyHitStop(0.35f, 0.15f);
		break;
	case EventType::BerserkEnded:
		if (Actor) Actor->SetRage(0.f);
		break;
	case EventType::BreakdownStarted:
		if (Actor && Actor->IsLocallyControlled() && Actor->GetCockpitFx()) { Actor->GetCockpitFx()->ForceFailures(1 + Ev.a); }
		break;
	case EventType::BreakdownRepaired:
		if (Actor && Actor->GetCockpitFx()) Actor->GetCockpitFx()->Repair(1.f);
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
	if (Ev.type >= EventType::LungeCharging && Ev.type <= EventType::BreakdownRepaired) UE_LOG(LogTemp, Display, TEXT("IV v5 event %d actor=%d a=%d b=%d v=%.2f"), int32(Ev.type), int32(Ev.actor), Ev.a, Ev.b, Ev.value);
	PlayEventSound(Ev);
	if (Ev.type == EventType::Whiff || Ev.type == EventType::WallSlam) HitCity(Ev);
	OnEvent.Broadcast(Ev);
}

void AIVCombatDirector::ApplyHitStop(float Seconds, float Dilation)
{
	HitStop = FMath::Max(HitStop, Seconds * Dilation);
	UGameplayStatics::SetGlobalTimeDilation(this, Dilation);
}

void AIVCombatDirector::TryScoop(iv::Side S)
{
	const int32 Idx = iv::Index(S);
	AIVMechPawn* A = PawnOf(S);
	AIVMechPawn* D = PawnOf(iv::Other(S));
	if (!Duel.IsValid() || !A || !D || Duel->result().over || Duel->cinematic().active) return;
	if (ScoopCooldown[Idx] > 0.f) return;
	const iv::Fighter& F = Duel->fighter(S);
	if (F.posture != iv::Posture::Standing || F.phase != iv::Phase::Idle || F.weaponCharging) return;
	AIVEnvironment* Env = AIVEnvironment::Get(GetWorld());
	FVector Base, Size;
	const FVector ToEnemy = (D->GetActorLocation() - A->GetActorLocation()).GetSafeNormal2D();
	// a helicopter on a low pass is the better grab: hurled whole, it burns and blows up on the head
	{
		AIVHelicopter* Best = nullptr;
		float BestD = 16000.f;
		for (TActorIterator<AIVHelicopter> It(GetWorld()); It; ++It)
		{
			if (!It->IsGrabbable()) continue;
			const FVector To = It->GetActorLocation() - A->GetActorLocation();
			const float Dd = To.Size();
			if (Dd < BestD && FVector::DotProduct(To.GetSafeNormal2D(), A->GetActorForwardVector().GetSafeNormal2D()) > -0.2f) { BestD = Dd; Best = *It; }
		}
		if (Best)
		{
			UE_LOG(LogTemp, Display, TEXT("IV heli grabbed at %.0f cm"), BestD);
			ScoopCooldown[Idx] = kScoopCooldownSec;
			A->PlayAction(FName(TEXT("grab_clamp")), 1.2f);
			TWeakObjectPtr<AIVCombatDirector> Self(this);
			Best->GrabAndThrow(A, D, 0.55f, 1.2f, [Self, S](const FVector&)
			{
				if (!Self.IsValid() || !Self->Duel.IsValid() || Self->Duel->result().over) return;
				Self->Duel->ExternalHit(iv::Other(S), iv::Zone::Head, iv::tune::kDebrisDamage * 1.5f, iv::tune::kDebrisStability * 1.4f, 0, iv::StatusKind::Blind, iv::tune::kDebrisBlindTicks);
			});
			if (A->IsLocallyControlled()) A->AddCockpitImpulse(0.f, 0.f, 1.0f);
			return;
		}
	}
	if (!Env || !Env->FindScoopBuilding(A->GetActorLocation(), ToEnemy, Base, Size))
	{
		if (A->IsLocallyControlled()) IVAudio::Play2D(GetWorld(), TEXT("cockpit_alarm_warning"), 0.6f);
		return;
	}
	ScoopCooldown[Idx] = kScoopCooldownSec;
	A->PlayAction(FName(TEXT("grab_clamp")), 1.2f);
	// the lower part of the building gives way
	Env->BlastAt(Base + FVector(0, 0, 900.f), FMath::Max(Size.X, Size.Y) * 0.62f, 2600.f);
	if (AIVFXManager* FX = AIVFXManager::Get(GetWorld()))
	{
		FX->SpawnDust(Base + FVector(0, 0, 600.f), FMath::Max(Size.X, Size.Y) * 0.8f, 40, 2.5f);
		FX->SpawnSparks(Base + FVector(0, 0, 600.f), FVector::UpVector, 90, 6000.f);
	}
	IVAudio::Play3D(GetWorld(), TEXT("env_concrete_crumble"), Base, 1.f);
	IVAudio::Play3D(GetWorld(), TEXT("env_distant_boom_01"), Base, 1.f);
	if (A->IsLocallyControlled()) A->AddCockpitImpulse(0.f, 0.f, 1.0f);
	FActorSpawnParameters Sp;
	Sp.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
	const FVector From = Base + FVector(0, 0, FMath::Min(Size.Z * 0.45f, 5000.f));
	if (AIVThrownDebris* T = GetWorld()->SpawnActor<AIVThrownDebris>(From, FRotator::ZeroRotator, Sp))
	{
		TWeakObjectPtr<AIVCombatDirector> Self(this);
		T->Launch(From, D, D->GetZoneWorldLocation(iv::Zone::Head), 1.15f, 1.f, [Self, S](const FVector&)
		{
			if (!Self.IsValid() || !Self->Duel.IsValid() || Self->Duel->result().over) return;
			Self->Duel->ExternalHit(iv::Other(S), iv::Zone::Head, iv::tune::kDebrisDamage, iv::tune::kDebrisStability, 0, iv::StatusKind::Blind, iv::tune::kDebrisBlindTicks);
		});
	}
}

void AIVCombatDirector::HealFighter(iv::Side S)
{
	if (!Duel.IsValid()) return;
	iv::Fighter& F = Duel->fighter(S);
	F.body.Reset();
	F.res = iv::Resources();
	F.posture = iv::Posture::Standing;
	F.blindTicks = F.strikeLockTicks = F.burnTicks = 0;
	if (AIVMechPawn* P = PawnOf(S)) P->ResetForNewMatch();
}

void AIVCombatDirector::FillUltimate(iv::Side S)
{
	if (Duel.IsValid()) Duel->fighter(S).ultimate = iv::tune::kUltimateMax;
}

void AIVCombatDirector::SetDummyScript(int32 Which)
{
	if (!Duel.IsValid()) return;
	std::vector<iv::DummyStepDef> V;
	const int32 Gap = iv::tune::kDummyScriptGapTicks;
	const int32 Hold = iv::tune::kWindupMinTicks + 6;
	if (Which == 2)
	{
		V.push_back({ Gap, iv::StrikeKind::Heavy, iv::SwingSide::Left, iv::Arm::R, Hold });
		V.push_back({ Gap, iv::StrikeKind::Heavy, iv::SwingSide::Right, iv::Arm::R, Hold });
	}
	else
	{
		V.push_back({ Gap, iv::StrikeKind::Heavy, iv::SwingSide::Up, iv::Arm::R, Hold });
		V.push_back({ Gap, iv::StrikeKind::Heavy, iv::SwingSide::Right, iv::Arm::R, Hold });
		V.push_back({ Gap, iv::StrikeKind::Heavy, iv::SwingSide::Left, iv::Arm::R, Hold });
		V.push_back({ Gap, iv::StrikeKind::Heavy, iv::SwingSide::Down, iv::Arm::R, Hold });
	}
	Duel->dummy(iv::Side::B).SetScript(V);
}

void AIVCombatDirector::OnMechCrash(AIVMechPawn* Pawn, float Strength)
{
	if (!Duel.IsValid() || Duel->result().over || Duel->cinematic().active) return;
	const iv::Side S = (Pawn == Player.Get()) ? iv::Side::A : iv::Side::B;
	Duel->ExternalHit(S, (FMath::RandBool() ? iv::Zone::LegL : iv::Zone::LegR), 3.5f * Strength, 9.f * Strength, 1);
}
