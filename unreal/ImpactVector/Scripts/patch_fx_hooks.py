import io
SRC = r"F:\IVUnreal\Source\ImpactVector"


def rd(n):
    return io.open(SRC + "\\" + n, encoding="utf-8").read()


def wr(n, s):
    io.open(SRC + "\\" + n, "w", encoding="utf-8", newline="\r\n").write(s)


def ins_after(text, key, block):
    """Insert block after the line containing key, prefixing the block with that line's indent."""
    lines = text.split("\n")
    for i, l in enumerate(lines):
        if key in l:
            ind = l[:len(l) - len(l.lstrip("\t"))]
            add = [(ind + bl if bl.strip() else bl) for bl in block.strip("\n").split("\n")]
            lines[i + 1:i + 1] = add
            return "\n".join(lines)
    raise AssertionError(key)


# ---- mech: armour plates fly off on hits and zone failures
c = rd("IVMechPawn.cpp")
if "EIVChunk::Armor" not in c:
    c = ins_after(c, "if (Strength01 > 0.35f && !bBlocked) FX->SpawnDust(Loc, 900.f", """
if (Strength01 > 0.3f && !bBlocked)
{
	const FVector Out = GetActorForwardVector() * 0.6f + GetActorRightVector() * ZoneSide(Z) * 0.8f + FVector(0, 0, 0.7f);
	FX->SpawnChunks(Loc, Out, 1 + int32(5.f * Strength01), EIVChunk::Armor, 2.4f + 1.6f * Strength01, 2600.f + 3600.f * Strength01, 0.5f + 0.5f * Strength01);
}
""")
    c = ins_after(c, "if (NewState >= iv::ZoneState::Damaged && OldState < iv::ZoneState::Damaged) FX->SpawnDust(Loc, 700.f", """
if (NewState >= iv::ZoneState::Damaged && OldState < iv::ZoneState::Damaged)
	FX->SpawnChunks(Loc, GetActorForwardVector() * 0.5f + FVector(0, 0, 0.8f), 3, EIVChunk::Armor, 3.f, 3200.f, 0.6f);
if (NewState >= iv::ZoneState::Critical && OldState < iv::ZoneState::Critical)
	FX->SpawnChunks(Loc, FVector(0, 0, 1.f), 7, EIVChunk::Armor, 3.6f, 4800.f, 1.f, 1.1f);
if (NewState >= iv::ZoneState::Destroyed && OldState < iv::ZoneState::Destroyed)
{
	FX->SpawnChunks(Loc, FVector(0, 0, 1.f), 12, EIVChunk::Armor, 4.4f, 6200.f, 1.f, 1.3f);
	FX->SpawnChunks(Loc, FVector(0, 0, 1.f), 6, EIVChunk::Steel, 3.f, 5200.f, 0.9f, 1.3f);
}
""")
    wr("IVMechPawn.cpp", c)

# ---- buildings: shards, glass, slabs and gravel on every blast
b = rd("IVBuilding.cpp")
if "EIVChunk::Concrete" not in b:
    b = ins_after(b, "FX->SpawnDust(C, Radius * 1.2f, FMath::Clamp(Killed / 3, 6, 40));", """
{
	const FVector Out = FVector(0, 0, 0.6f);
	const float Cell = FMath::Max3(CellSz.X, CellSz.Y, CellSz.Z);
	const float Sc = FMath::Clamp(Cell / 170.f, 3.f, 7.f);
	FX->SpawnChunks(C, Out, FMath::Clamp(Killed / 2, 6, 44), EIVChunk::Concrete, Sc, 2800.f + Impulse * 0.5f, 0.f, 1.3f);
	FX->SpawnChunks(C, Out, FMath::Clamp(Killed / 6, 2, 10), EIVChunk::Slab, Sc * 0.9f, 2200.f + Impulse * 0.3f, 0.f, 1.2f);
	FX->SpawnChunks(C, Out, FMath::Clamp(Killed / 2, 8, 40), EIVChunk::Glass, Sc * 1.3f, 3200.f + Impulse * 0.4f, 0.f, 1.5f);
	FX->SpawnChunks(C, Out, FMath::Clamp(Killed, 10, 50), EIVChunk::Gravel, Sc * 1.4f, 3600.f, 0.f, 1.6f);
}
""")
    wr("IVBuilding.cpp", b)
print("hooks patched")
