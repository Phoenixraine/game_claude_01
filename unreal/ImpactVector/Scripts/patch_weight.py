import io
SRC = r"F:\IVUnreal\Source\ImpactVector"


def rd(n):
    s = io.open(SRC + "\\" + n, encoding="utf-8").read()
    return s.replace("\r\n", "\n"), ("\r\n" in s)


def wr(n, s, crlf):
    io.open(SRC + "\\" + n, "w", encoding="utf-8", newline="\r\n" if crlf else "\n").write(s)


h, crlf = rd("IVMechPawn.h")
if "CombatVel" not in h:
    h = h.replace("float BladeBlock = 0.f, BladeBlockHold = 0.f;", "float BladeBlock = 0.f, BladeBlockHold = 0.f;\nTMap<FName, FVector> CombatVel;       // joint velocities of the spring-driven combat pose (weight and follow-through)\nfloat SwingWeightPitch = 0.f, SwingWeightYaw = 0.f, PelvisDip = 0.f;", 1)
    wr("IVMechPawn.h", h, crlf)

c, crlf = rd("IVMechPawn.cpp")
old = """	const float K = 1.f - FMath::Exp(-16.f * Dt);
	CombatPose = FIVPoseAngles::Lerp(CombatPose, Target, K);
"""
assert old in c
new = """	const float K = 1.f - FMath::Exp(-16.f * Dt);
	{
		// spring-damper per joint: heavy limbs lag and overshoot a little (mass), light ones keep up. The strike is stiff so the blade lands on time,
		// the recovery is soft so the arm has to be hauled back.
		const float Phase = (S.phase == iv::Phase::Strike) ? 1.7f : ((S.phase == iv::Phase::Recovery) ? 0.62f : ((S.phase == iv::Phase::Windup) ? 0.85f : 1.f));
		const float Zeta = (S.phase == iv::Phase::Strike) ? 0.78f : 0.6f;
		const float Dtc = FMath::Min(Dt, 1.f / 30.f);
		for (int32 Sub = 0; Sub < 2; ++Sub)
		{
			const float H = Dtc * 0.5f;
			for (const TPair<FName, FVector>& Kv : Target.Joint)
			{
				const FString N = Kv.Key.ToString();
				float W0 = 11.f;
				if (N.Contains(TEXT("torso"))) W0 = 6.5f;
				else if (N.Contains(TEXT("head"))) W0 = 7.5f;
				else if (N.Contains(TEXT("shoulder"))) W0 = 8.5f;
				else if (N.Contains(TEXT("upperarm"))) W0 = 10.f;
				else if (N.Contains(TEXT("forearm"))) W0 = 12.5f;
				else if (N.Contains(TEXT("hand"))) W0 = 15.f;
				else if (N.Contains(TEXT("pelvis")) || N.Contains(TEXT("thigh")) || N.Contains(TEXT("shin")) || N.Contains(TEXT("foot"))) W0 = 9.f;
				const float Wn = W0 * Phase;
				FVector& Cur = CombatPose.Joint.FindOrAdd(Kv.Key, Kv.Value);
				FVector& Vel = CombatVel.FindOrAdd(Kv.Key);
				const FVector Acc = (Kv.Value - Cur) * (Wn * Wn) - Vel * (2.f * Zeta * Wn);
				Vel += Acc * H;
				Cur += Vel * H;
			}
		}
		CombatPose.RootPosM = FMath::Lerp(CombatPose.RootPosM, Target.RootPosM, K);
		CombatPose.RootRotDeg = FMath::Lerp(CombatPose.RootRotDeg, Target.RootRotDeg, K);
	}
	// body english: a heavy swing drags the torso round and drops the pelvis; the dip is released as a footfall-like thump at contact
	{
		const float WantYaw = (S.phase == iv::Phase::Windup) ? -9.f * ((S.side == iv::SwingSide::Left) ? 1.f : -1.f) : ((S.phase == iv::Phase::Strike) ? 14.f * ((S.side == iv::SwingSide::Left) ? 1.f : -1.f) : 0.f);
		const float WantDip = (S.phase == iv::Phase::Windup) ? 0.4f : ((S.phase == iv::Phase::Strike || S.phase == iv::Phase::Contact) ? 1.f : 0.f);
		SwingWeightYaw = FMath::FInterpTo(SwingWeightYaw, (S.kind == iv::StrikeKind::Heavy || S.kind == iv::StrikeKind::Lunge) ? WantYaw : 0.f, Dt, 5.f);
		PelvisDip = FMath::FInterpTo(PelvisDip, (S.kind == iv::StrikeKind::Heavy || S.kind == iv::StrikeKind::Lunge) ? WantDip : 0.f, Dt, 6.f);
		if (FVector* T = CombatPose.Joint.Find(FName(TEXT("torso")))) T->Y += SwingWeightYaw;
		Pose.RootPosM.Z -= 0.35f * PelvisDip;
	}
"""
c = c.replace(old, new, 1)
wr("IVMechPawn.cpp", c, crlf)
print("weight patched")
