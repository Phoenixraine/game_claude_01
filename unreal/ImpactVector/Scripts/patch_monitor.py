import io
SRC = r"F:\IVUnreal\Source\ImpactVector"


def rd(n):
    s = io.open(SRC + "\\" + n, encoding="utf-8").read()
    return s.replace("\r\n", "\n"), ("\r\n" in s)


def wr(n, s, crlf):
    io.open(SRC + "\\" + n, "w", encoding="utf-8", newline="\r\n" if crlf else "\n").write(s)


def rep(t, old, new):
    assert old in t, old[:90]
    return t.replace(old, new, 1)


b, c = rd("ImpactVector.Build.cs")
if "ApplicationCore" not in b:
    b = rep(b, '"Slate", "SlateCore",', '"Slate", "SlateCore", "ApplicationCore",')
    wr("ImpactVector.Build.cs", b, c)

s, c = rd("IVSettings.cpp")
if "ApplyMonitor" not in s:
    s = rep(s, '#include "Misc/Parse.h"', '#include "Misc/Parse.h"\n#include "GenericPlatform/GenericApplication.h"\n#include "Framework/Application/SlateApplication.h"\n#include "Widgets/SWindow.h"\n#include "Engine/Engine.h"\n#include "Engine/GameViewportClient.h"\n#include "GameFramework/GameUserSettings.h"\n#include "Containers/Ticker.h"')
    # the setting: 0 = leave the window where it is, 1..N = that monitor
    s = rep(s, '			GList.Add(Mk(TEXT("draw_dist"),', '''			{
				FDisplayMetrics Dm;
				FDisplayMetrics::RebuildDisplayMetrics(Dm);
				const int32 N = FMath::Clamp(Dm.MonitorInfo.Num(), 1, 6);
				GList.Add(Mk(TEXT("monitor"), TEXT("МОНИТОР"), TEXT("На каком мониторе показывать игру. «Текущий» — не трогать окно. Переключение мгновенное."), 2, EKind::Choice, 0, float(N), 1, 0));
				GList.Last().Names.Add(TEXT("ТЕКУЩИЙ"));
				for (int32 i = 0; i < N; ++i)
				{
					const FMonitorInfo* Mi = Dm.MonitorInfo.IsValidIndex(i) ? &Dm.MonitorInfo[i] : nullptr;
					GList.Last().Names.Add(Mi ? FString::Printf(TEXT("МОНИТОР %d  %d×%d%s"), i + 1, Mi->NativeWidth, Mi->NativeHeight, Mi->bIsPrimary ? TEXT("  (ОСНОВНОЙ)") : TEXT("")) : FString::Printf(TEXT("МОНИТОР %d"), i + 1));
				}
			}
			GList.Add(Mk(TEXT("draw_dist"),''')
    # the move itself (before Apply)
    s = rep(s, "	void Apply(UWorld* World)\n	{", '''	// Moves the game window to the chosen monitor (1-based; 0 = leave it). Fullscreen is dropped to a window, moved, and restored a moment later
	// (windowed fullscreen always fills the monitor the window currently sits on).
	void ApplyMonitor(int32 Choice)
	{
		static int32 Last = 0;
		int32 Cli = 0;
		if (FParse::Value(FCommandLine::Get(), TEXT("-IVMonitor="), Cli)) Choice = Cli;
		if (Choice <= 0 || Choice == Last || !GEngine || !GEngine->GameViewport) return;
		TSharedPtr<SWindow> Win = GEngine->GameViewport->GetWindow();
		if (!Win.IsValid()) return;
		FDisplayMetrics Dm;
		FDisplayMetrics::RebuildDisplayMetrics(Dm);
		if (!Dm.MonitorInfo.IsValidIndex(Choice - 1)) return;
		const FMonitorInfo& Mi = Dm.MonitorInfo[Choice - 1];
		const FPlatformRect R = Mi.WorkArea;
		const EWindowMode::Type Mode = Win->GetWindowMode();
		const FVector2D Size = Win->GetSizeInScreen();
		Last = Choice;
		UE_LOG(LogTemp, Display, TEXT("IV monitor: -> %d (%s) work area %d,%d - %d,%d, window mode %d"), Choice, *Mi.Name, R.Left, R.Top, R.Right, R.Bottom, int32(Mode));
		if (Mode == EWindowMode::Windowed)
		{
			Win->MoveWindowTo(FVector2D(R.Left + 40, R.Top + 40));
			TWeakPtr<SWindow> Wk = Win;
			FTSTicker::GetCoreTicker().AddTicker(FTickerDelegate::CreateLambda([Wk](float) { if (TSharedPtr<SWindow> W3 = Wk.Pin()) UE_LOG(LogTemp, Display, TEXT("IV monitor: window now at %s size %s"), *W3->GetPositionInScreen().ToString(), *W3->GetSizeInScreen().ToString()); return false; }), 1.0f);
			return;
		}
		// fullscreen: leave it, jump to the other monitor as a window, then go back to fullscreen there
		Win->SetWindowMode(EWindowMode::Windowed);
		Win->ReshapeWindow(FVector2D(R.Left + 60, R.Top + 60), FVector2D(FMath::Min<float>(Size.X, (R.Right - R.Left) - 120), FMath::Min<float>(Size.Y, (R.Bottom - R.Top) - 120)));
		TWeakPtr<SWindow> WeakWin = Win;
		FTSTicker::GetCoreTicker().AddTicker(FTickerDelegate::CreateLambda([WeakWin, Mode](float)
		{
			if (TSharedPtr<SWindow> W2 = WeakWin.Pin()) W2->SetWindowMode(Mode);
			return false;
		}), 0.4f);
	}

	void Apply(UWorld* World)
	{''')
    s = rep(s, "		const int32 Fsr = GetInt(TEXT(\"fsr\"));", "		ApplyMonitor(GetInt(TEXT(\"monitor\")));\n		const int32 Fsr = GetInt(TEXT(\"fsr\"));")
    wr("IVSettings.cpp", s, c)
print("monitor patched")
