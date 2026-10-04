import io
SRC = r"F:\IVUnreal\Source\ImpactVector"


def rd(n):
    s = io.open(SRC + "\\" + n, encoding="utf-8").read()
    return s.replace("\r\n", "\n"), ("\r\n" in s)


def wr(n, s, crlf):
    io.open(SRC + "\\" + n, "w", encoding="utf-8", newline="\r\n" if crlf else "\n").write(s)


def rep(t, old, new):
    assert old in t, old[:60]
    return t.replace(old, new, 1)


h, c = rd("IVPlayerController.h")
if "IsTrailGuard" not in h:
    h = rep(h, "	bool IsTrailLive() const { return bStrikeWasDown || bGuardWasDown; }", "	bool IsTrailLive() const { return bStrikeWasDown || bGuardWasDown; }\n	bool IsTrailGuard() const { return bTrailGuard; }\n	bool bTrailGuard = false;")
    h = rep(h, "GetTrailFade() const { return FMath::Clamp(1.f - TrailAge / 0.6f, 0.f, 1.f); }", "GetTrailFade() const { return FMath::Clamp(1.f - TrailAge / 1.1f, 0.f, 1.f); }")
    wr("IVPlayerController.h", h, c)
p, c = rd("IVPlayerController.cpp")
if "bTrailGuard = bGuardDown" not in p:
    p = rep(p, "		TrailAge = 0.f;\n	}\n	else\n	{\n		TrailAge += Dt;\n		if (TrailAge > 0.6f) Trail.Reset();", "		TrailAge = 0.f;\n		bTrailGuard = bGuardDown && !bStrikeDown;\n	}\n	else\n	{\n		TrailAge += Dt;\n		if (TrailAge > 1.1f) Trail.Reset();")
    wr("IVPlayerController.cpp", p, c)
hd, c = rd("IVHUD.cpp")
if "Catmull" not in hd:
    a = hd.index("	// the stroke itself: thick soft pass + bright core, widening towards the head of the stroke")
    b = hd.index("void AIVHUD::", a)
    # find end of function: last closing brace before next function
    end = hd.rindex("}\n", a, b) + 2
    new = r'''	// the stroke itself: a smoothed (Catmull-Rom) ribbon with a wide soft glow, a bright core and a hot tip; red-orange for a strike, green-cyan for a block
	{
		const bool bGd = PC->IsTrailGuard();
		const FLinearColor Glow = bGd ? FLinearColor(0.1f, 0.9f, 0.55f) : FLinearColor(1.f, 0.35f, 0.08f);
		const FLinearColor Core = bGd ? FLinearColor(0.75f, 1.f, 0.9f) : FLinearColor(1.f, 0.9f, 0.6f);
		TArray<FVector2D> Pts;
		const int32 N = T.Num();
		for (int32 i = 0; i + 1 < N; ++i)
		{
			const FVector2D P0 = T[FMath::Max(i - 1, 0)], P1 = T[i], P2 = T[i + 1], P3 = T[FMath::Min(i + 2, N - 1)];
			for (int32 k = 0; k < 4; ++k)
			{
				const float u = k / 4.f, u2 = u * u, u3 = u2 * u;
				Pts.Add(0.5f * ((2.f * P1) + (-P0 + P2) * u + (2.f * P0 - 5.f * P1 + 4.f * P2 - P3) * u2 + (-P0 + 3.f * P1 - 3.f * P2 + P3) * u3));
			}
		}
		Pts.Add(T.Last());
		const int32 M = Pts.Num();
		for (int32 i = 1; i < M; ++i)
		{
			const FVector2D a = P(Pts[i - 1]), b = P(Pts[i]);
			const float K = float(i) / float(M);
			const float Wd = 4.f + 14.f * K * K;
			DrawLine(a.X, a.Y, b.X, b.Y, A(Glow, 0.12f * Fade), Wd * 2.6f);
			DrawLine(a.X, a.Y, b.X, b.Y, A(Glow, 0.35f * Fade), Wd * 1.35f);
			DrawLine(a.X, a.Y, b.X, b.Y, A(Core, (0.45f + 0.55f * K) * Fade), Wd * 0.45f);
		}
		const FVector2D Tip = P(T.Last());
		for (int32 g = 3; g >= 1; --g) DrawRect(A(Glow, 0.16f * Fade * (4 - g)), Tip.X - 7.f * g, Tip.Y - 7.f * g, 14.f * g, 14.f * g);
		DrawRect(A(Core, Fade), Tip.X - 5.f, Tip.Y - 5.f, 10.f, 10.f);
		// arrow head along the last segment
		if (M > 3)
		{
			const FVector2D d = (P(Pts[M - 1]) - P(Pts[M - 4])).GetSafeNormal();
			const FVector2D n(-d.Y, d.X);
			DrawLine(Tip.X, Tip.Y, Tip.X - d.X * 22.f + n.X * 11.f, Tip.Y - d.Y * 22.f + n.Y * 11.f, A(Core, Fade), 3.f);
			DrawLine(Tip.X, Tip.Y, Tip.X - d.X * 22.f - n.X * 11.f, Tip.Y - d.Y * 22.f - n.Y * 11.f, A(Core, Fade), 3.f);
		}
		Text(bGd ? TEXT("БЛОК") : TEXT("УДАР"), CX, CY + R + 16.f, A(Glow, 0.9f * Fade), 0.8f, 1, 1);
	}
}
'''
    hd = hd[:a] + new + hd[end:]
    wr("IVHUD.cpp", hd, c)
print("trail patched")
