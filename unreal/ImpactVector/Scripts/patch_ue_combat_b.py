"""UE combat director: presentation of the v5 events."""
C = r"F:\IVUnreal\Source\ImpactVector\IVCombat.cpp"
s = open(C, encoding="utf-8").read()


def rep(a, b):
    global s
    assert a in s, a[:90]
    s = s.replace(a, b, 1)


rep("""	case EventType::MatchEnd:
	{
		const bool bPlayerLost""", """	// ---------------------------------------------------------------- v5 moves
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
		const bool bPlayerLost""")

# sounds for new events
rep("""	case EventType::StaggerBegin: if (bPlayerActor) IVAudio::Play2D(W, TEXT("cockpit_harness_creak"), 0.9f); break;""",
    """	case EventType::StaggerBegin: if (bPlayerActor) IVAudio::Play2D(W, TEXT("cockpit_harness_creak"), 0.9f); break;
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
	case EventType::BreakdownRepaired: if (bPlayerActor) IVAudio::Play2D(W, TEXT("cockpit_hud_unlock"), 1.f); break;""")

# lock sparks while locked: in Tick after the duel step
rep("""	const bool bFrozen = Duel->result().over || Duel->cinematic().active;
	auto Locked =""", """	if (Duel->lock().active)
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
			P->AddCockpitImpulse(FMath::RandRange(-1.f, 1.f), FMath::RandRange(-0.5f, 0.5f), 0.35f);
			E->AddCockpitImpulse(FMath::RandRange(-1.f, 1.f), FMath::RandRange(-0.5f, 0.5f), 0.35f);
		}
	}
	const bool bFrozen = Duel->result().over || Duel->cinematic().active;
	auto Locked =""")
open(C, "w", encoding="utf-8").write(s)

H = r"F:\IVUnreal\Source\ImpactVector\IVCombat.h"
t = open(H, encoding="utf-8").read()
t = t.replace("	float HitStop = 0.f;\n", "	float HitStop = 0.f;\n	float LockSparkAcc = 0.f;\n", 1)
open(H, "w", encoding="utf-8").write(t)
print("combat b ok")
