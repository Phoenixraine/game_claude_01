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


# ---------------- pawn: left-arm rocket pose overlay
h, c = rd("IVMechPawn.h")
if "RocketArmT" not in h:
    h = rep(h, "	void ApplySettings();", "	void ApplySettings();\n	/** The off hand raises and launches a rocket salvo (after a parry): drives the left-arm pose overlay. */\n	void StartRocketArm() { RocketArmT = 0.001f; }")
    h = rep(h, "	float SetFov = 98.f,", "	float RocketArmT = 0.f;\n	float SetFov = 98.f,")
    wr("IVMechPawn.h", h, c)
p, c = rd("IVMechPawn.cpp")
if "RocketArmT" not in p:
    old = "	// hit kick: torso recoil on top of everything, decays quickly"
    p = rep(p, old, """	// off-hand rocket salvo after a parry: the left arm punches out and holds, the launcher fires, then it drops back
	if (RocketArmT > 0.f)
	{
		RocketArmT += Dt;
		const float U = RocketArmT / 0.9f;
		const float Wt = U < 0.25f ? Ease(U / 0.25f) : (U < 0.7f ? 1.f : FMath::Max(0.f, 1.f - Ease((U - 0.7f) / 0.3f)));
		if (const FIVPoseAngles* Rk = P(TEXT("quick_piston_l_strike")))
			for (const TCHAR* N : { TEXT("shoulder_l"), TEXT("upperarm_l"), TEXT("forearm_l"), TEXT("hand_l") })
			{
				const FName B(N);
				const FVector* Tg = Rk->Joint.Find(B);
				FVector* Cur = Pose.Joint.Find(B);
				if (Tg && Cur) *Cur = FMath::Lerp(*Cur, *Tg, Wt);
			}
		if (U >= 1.f) RocketArmT = 0.f;
	}
""" + old)
    wr("IVMechPawn.cpp", p, c)

# ---------------- director: parry -> rocket salvo
dh, c = rd("IVCombat.h")
if "FireParryRockets" not in dh:
    dh = rep(dh, "	void HandleBoardingEvent(const iv::Event& Ev);", "	void HandleBoardingEvent(const iv::Event& Ev);\n	void FireParryRockets(iv::Side Defender);")
    wr("IVCombat.h", dh, c)
d, c = rd("IVCombat.cpp")
if "AIVCombatDirector::FireParryRockets" not in d:
    d = rep(d, "	case EventType::ParrySuccess:\n	case EventType::InterceptSuccess:\n		if (Actor)", "	case EventType::ParrySuccess:\n		FireParryRockets(Ev.actor);\n		[[fallthrough]];\n	case EventType::Blocked:\n	case EventType::InterceptSuccess:\n		if (Actor)") if False else d
    d += r'''

// A clean parry: the blades bind, the off hand swings up and a rocket salvo hits the attacker (extra damage + a stagger on top of the parry's own).
void AIVCombatDirector::FireParryRockets(iv::Side Defender)
{
	AIVMechPawn* Def = PawnOf(Defender);
	AIVMechPawn* Atk = PawnOf(iv::Other(Defender));
	if (!Def || !Atk || !Duel.IsValid() || Duel->result().over) return;
	Def->StartRocketArm();
	if (Def->IsLocallyControlled()) Def->AddCockpitImpulse(0.f, 0.f, 0.6f);
	TWeakObjectPtr<AIVCombatDirector> Self(this);
	const iv::Side Victim = iv::Other(Defender);
	FTimerHandle H;
	GetWorldTimerManager().SetTimer(H, FTimerDelegate::CreateLambda([Self, Def = TWeakObjectPtr<AIVMechPawn>(Def), Atk = TWeakObjectPtr<AIVMechPawn>(Atk), Victim]()
	{
		if (!Self.IsValid() || !Def.IsValid() || !Atk.IsValid() || !Self->Duel.IsValid() || Self->Duel->result().over) return;
		FActorSpawnParameters Sp;
		Sp.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
		const FVector From = Def->GetZoneWorldLocation(iv::Zone::ArmL) + FVector(0, 0, 200.f);
		if (AIVProjectile* Pj = Self->GetWorld()->SpawnActor<AIVProjectile>(From, FRotator::ZeroRotator, Sp)) Pj->Launch(1, From, Atk, true, 0.55f);
		IVAudio::Play3D(Self->GetWorld(), TEXT("env_missile_incoming"), From, 1.f, 1.2f);
	}), 0.28f, false);
	FTimerHandle H2;
	GetWorldTimerManager().SetTimer(H2, FTimerDelegate::CreateLambda([Self, Victim]()
	{
		if (!Self.IsValid() || !Self->Duel.IsValid() || Self->Duel->result().over) return;
		Self->Duel->ExternalHit(Victim, iv::Zone::Torso, 7.f, 10.f, 4);
	}), 0.9f, false);
}
'''
    # call on ParrySuccess in Dispatch
    d = rep(d, "	case EventType::ZoneState:\n		if (Actor) Actor->OnZoneState(", "	case EventType::ParrySuccess:\n		FireParryRockets(Ev.actor);\n		break;\n	case EventType::ZoneState:\n		if (Actor) Actor->OnZoneState(")
    wr("IVCombat.cpp", d, c)
print("parry patched")
