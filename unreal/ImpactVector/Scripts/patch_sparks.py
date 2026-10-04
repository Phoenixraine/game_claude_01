import io
import re
SRC = r"F:\IVUnreal\Source\ImpactVector"


def rd(n):
    s = io.open(SRC + "\\" + n, encoding="utf-8").read()
    return s.replace("\r\n", "\n"), ("\r\n" in s)


def wr(n, s, crlf):
    io.open(SRC + "\\" + n, "w", encoding="utf-8", newline="\r\n" if crlf else "\n").write(s)


def rep(t, old, new):
    assert old in t, old[:70]
    return t.replace(old, new, 1)


h, c = rd("IVMechPawn.h")
if "ContactSparkCool" not in h:
    h = rep(h, "	float BladeBlock = 0.f, BladeBlockHold = 0.f;", "	float BladeBlock = 0.f, BladeBlockHold = 0.f;\n	float ContactSparkCool = 0.f, ContactSoundCool = 0.f;\n	bool bWasTouching = false;\n	/** Sparks, flash and clang where the blade meets the other blade (bBlade) or the other body. */\n	void EmitContactSparks(const FVector& At, bool bBlade, float Strength);")
    wr("IVMechPawn.h", h, c)

p, c = rd("IVMechPawn.cpp")
if "EmitContactSparks" not in p:
    # 1) body contact point
    p = rep(p, "		float Pen = 0.f;\n		if (O && O->RigMesh && O->bRigActive)", "		float Pen = 0.f;\n		FVector ContactAt = FVector::ZeroVector;\n		float BodyPen = 0.f, BladePen = 0.f;\n		if (O && O->RigMesh && O->bRigActive)") if False else p
    p = rep(p, "	float Pen = 0.f;\n	if (O && O->RigMesh && O->bRigActive)\n	{", "	float Pen = 0.f;\n	FVector ContactAt = FVector::ZeroVector;\n	float BodyPen = 0.f, BladePen = 0.f;\n	if (O && O->RigMesh && O->bRigActive)\n	{")
    p = rep(p, "			Pen = FMath::Max(Pen, K.R - (P1 - P2).Size());\n", "			const float D = K.R - (P1 - P2).Size();\n			if (D > BodyPen) { BodyPen = D; ContactAt = P1; }\n			Pen = FMath::Max(Pen, D);\n")
    # 2) blade-blade: replace the old spark line by contact bookkeeping
    NL, TB = chr(10), chr(9)
    a = p.index("if (Dd < 330.f)")
    b = p.index(NL + TB + TB + "}" + NL, a) + 5
    blk = ["if (Dd < 330.f)", TB + TB + "{", TB * 3 + "Pen = FMath::Max(Pen, 330.f - Dd + 40.f);", TB * 3 + "BladePen = 330.f - Dd;", TB * 3 + "ContactAt = (P1 + P2) * 0.5f;", TB + TB + "}", ""]
    p = p[:a] + NL.join(blk) + p[b:]
    # 3) emit after pen computed (before the city trace block's end): insert before "const bool bStriking"
    old = "	const bool bStriking = CombatAnim.phase == iv::Phase::Strike || CombatAnim.phase == iv::Phase::Contact;"
    new = """	// sparks + flash + clang while the steel is touching (only one of the two pawns reports a blade-blade clash)
	{
		ContactSparkCool -= Dt; ContactSoundCool -= Dt;
		const bool bFighting = CombatAnim.phase != iv::Phase::Idle || (O && O->CombatAnim.phase != iv::Phase::Idle);
		const bool bBlade = BladePen > 10.f && (!O || this < O);
		const bool bBody = BodyPen > 10.f && CombatAnim.phase != iv::Phase::Idle;
		const bool bTouch = bFighting && (bBlade || bBody);
		if (bTouch)
		{
			const float Str = FMath::Clamp(FMath::Max(BladePen, BodyPen) / 200.f, 0.4f, 1.6f);
			if (!bWasTouching || ContactSparkCool <= 0.f) { EmitContactSparks(ContactAt, bBlade, bWasTouching ? 0.45f * Str : Str); ContactSparkCool = 0.05f; }
		}
		bWasTouching = bTouch;
	}
""" + old
    p = rep(p, old, new)
    p += r'''

void AIVMechPawn::EmitContactSparks(const FVector& At, bool bBlade, float Strength)
{
	UWorld* W = GetWorld();
	if (AIVFXManager* FX = AIVFXManager::Get(W))
	{
		const FVector Out = (At - GetActorLocation()).GetSafeNormal2D();
		FX->SpawnSparks(At, (Out + FVector(0, 0, 0.5f)).GetSafeNormal(), FMath::RoundToInt(10.f + 14.f * Strength), 4500.f + 2500.f * Strength);
		FX->SpawnSparks(At, FVector::UpVector, FMath::RoundToInt(4.f * Strength), 3000.f);
		FX->SpawnFlash(At, bBlade ? FLinearColor(1.f, 0.82f, 0.5f) : FLinearColor(1.f, 0.55f, 0.25f), 5.0e5f * Strength, 0.12f, 9000.f);
	}
	if (ContactSoundCool <= 0.f)
	{
		IVAudio::Play3D(W, bBlade ? TEXT("parry_clang") : TEXT("hit_metal_contact_light"), At, FMath::Clamp(0.5f + 0.4f * Strength, 0.4f, 1.f), FMath::RandRange(0.9f, 1.15f));
		ContactSoundCool = 0.28f;
	}
}
'''
    wr("IVMechPawn.cpp", p, c)
print("sparks patched")
