import io
SRC = r"F:\IVUnreal\Source\ImpactVector"


def rd(n):
    s = io.open(SRC + "\\" + n, encoding="utf-8").read()
    return s.replace("\r\n", "\n"), ("\r\n" in s)


def wr(n, s, crlf):
    io.open(SRC + "\\" + n, "w", encoding="utf-8", newline="\r\n" if crlf else "\n").write(s)


def ins_after(text, key, block):
    lines = text.split("\n")
    for i, l in enumerate(lines):
        if key in l:
            ind = l[:len(l) - len(l.lstrip("\t"))]
            add = [(ind + bl if bl.strip() else bl) for bl in block.strip("\n").split("\n")]
            lines[i + 1:i + 1] = add
            return "\n".join(lines)
    raise AssertionError(key)


h, crlf = rd("IVMechPawn.h")
if "BladeBlock" not in h:
    h = ins_after(h, "void BuildGreebles();", "void UpdateBladeContact(float Dt, FIVPoseAngles& Pose);\nfloat BladeBlock = 0.f, BladeBlockHold = 0.f;\nTWeakObjectPtr<AIVMechPawn> OtherMechCache;")
    wr("IVMechPawn.h", h, crlf)

c, crlf = rd("IVMechPawn.cpp")
if "UpdateBladeContact" not in c:
    c = ins_after(c, "if (bCombat) BuildCombatPose(Pose, Dt);", "if (bCombat) UpdateBladeContact(Dt, Pose);")
    c += r'''

// ---------------------------------------------------------------------------------------------------------- blade contact
// The blade must not pass through the opponent's body or the city: the animation says where the arm WANTS to go, this layer measures how deep
// the blade is inside a solid (from last frame's real transforms) and pulls the arms back towards the guard until it rests on the surface.
// The block is held through the strike so the blade stays pressed against the target, then eases off in recovery.
void AIVMechPawn::UpdateBladeContact(float Dt, FIVPoseAngles& Pose)
{
	if (!bRigActive || !RigMesh || !SwordMesh || FParse::Param(FCommandLine::Get(), TEXT("IVNoBladeBlock"))) return;
	if (!OtherMechCache.IsValid()) for (TActorIterator<AIVMechPawn> It(GetWorld()); It; ++It) if (*It != this) { OtherMechCache = *It; break; }
	AIVMechPawn* O = OtherMechCache.Get();
	FVector B0, T0;
	GetBladeSegment(B0, T0);
	const FVector Bm = B0 + (T0 - B0) * 0.12f;
	float Pen = 0.f;
	if (O && O->RigMesh && O->bRigActive)
	{
		struct FCap { const TCHAR* A; const TCHAR* B; float R; };
		static const FCap Caps[] = {
			{ TEXT("pelvis"), TEXT("torso"), 1000.f }, { TEXT("torso"), TEXT("head"), 900.f }, { TEXT("head"), TEXT("head"), 650.f },
			{ TEXT("shoulder_l"), TEXT("upperarm_l"), 520.f }, { TEXT("upperarm_l"), TEXT("forearm_l"), 420.f }, { TEXT("forearm_l"), TEXT("hand_l"), 380.f },
			{ TEXT("shoulder_r"), TEXT("upperarm_r"), 520.f }, { TEXT("upperarm_r"), TEXT("forearm_r"), 420.f }, { TEXT("forearm_r"), TEXT("hand_r"), 380.f },
			{ TEXT("thigh_l"), TEXT("shin_l"), 560.f }, { TEXT("shin_l"), TEXT("foot_l"), 470.f }, { TEXT("thigh_r"), TEXT("shin_r"), 560.f }, { TEXT("shin_r"), TEXT("foot_r"), 470.f } };
		for (const FCap& K : Caps)
		{
			const FVector A = O->RigMesh->GetBoneLocation(FName(K.A), EBoneSpaces::WorldSpace);
			const FVector Bp = O->RigMesh->GetBoneLocation(FName(K.B), EBoneSpaces::WorldSpace);
			FVector P1, P2;
			FMath::SegmentDistToSegment(Bm, T0, A, Bp, P1, P2);
			Pen = FMath::Max(Pen, K.R - (P1 - P2).Size());
		}
	}
	// the city: a trace along the blade
	{
		FHitResult Hit;
		FCollisionQueryParams Q(SCENE_QUERY_STAT(IVBladeWorld), false, this);
		if (O) Q.AddIgnoredActor(O);
		if (GetWorld()->LineTraceSingleByChannel(Hit, Bm, T0, ECC_WorldStatic, Q))
			Pen = FMath::Max(Pen, (1.f - Hit.Time) * (T0 - Bm).Size() * 0.5f + 60.f);
	}
	const bool bStriking = CombatAnim.phase == iv::Phase::Strike || CombatAnim.phase == iv::Phase::Contact;
	if (Pen > 20.f && CombatAnim.phase != iv::Phase::Idle)
	{
		const float Target = FMath::Clamp(Pen / 260.f, 0.f, 1.f);
		BladeBlock = FMath::Max(BladeBlock, FMath::FInterpTo(BladeBlock, Target, Dt, 14.f));
		BladeBlockHold = 0.18f;
	}
	else
	{
		BladeBlockHold -= Dt;
		if (!bStriking || BladeBlockHold <= 0.f) BladeBlock = FMath::FInterpTo(BladeBlock, 0.f, Dt, 3.2f);
	}
	if (BladeBlock < 0.01f) return;
	const FIVPoseAngles* Guard = RigData ? RigData->FindPose(FName(TEXT("guard_neutral"))) : nullptr;
	if (!Guard) return;
	static const TCHAR* Arm[] = { TEXT("shoulder_l"), TEXT("upperarm_l"), TEXT("forearm_l"), TEXT("hand_l"), TEXT("shoulder_r"), TEXT("upperarm_r"), TEXT("forearm_r"), TEXT("hand_r"), TEXT("torso") };
	for (int32 i = 0; i < UE_ARRAY_COUNT(Arm); ++i)
	{
		const FName B(Arm[i]);
		FVector* V = Pose.Joint.Find(B);
		const FVector* G = Guard->Joint.Find(B);
		if (V && G) *V = FMath::Lerp(*V, *G, BladeBlock * (i == 8 ? 0.35f : 0.82f));
	}
}
'''
    wr("IVMechPawn.cpp", c, crlf)
print("contact patched")
