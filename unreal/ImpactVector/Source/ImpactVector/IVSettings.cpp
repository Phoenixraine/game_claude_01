#include "IVSettings.h"
#include "IVEnvironment.h"
#include "IVDistrict.h"
#include "IVGraphics.h"
#include "IVHelicopter.h"
#include "IVRain.h"
#include "IVMechPawn.h"
#include "IVPlayerController.h"
#include "EngineUtils.h"
#include "Engine/World.h"
#include "HAL/IConsoleManager.h"
#include "Misc/ConfigCacheIni.h"
#include "Misc/Paths.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"

namespace IVSettings
{
	namespace
	{
		TArray<FSetting> GList;
		TMap<FString, float> GVals;
		bool bLoaded = false;

		FString IniPath() { return FPaths::ProjectSavedDir() / TEXT("Config/WindowsNoEditor/IVSettings.ini"); }

		FSetting Mk(const TCHAR* Id, const TCHAR* Label, const TCHAR* Hint, int32 Tab, EKind K, float Mn, float Mx, float St, float Df, const TCHAR* Unit = TEXT(""), float Show = 1.f)
		{
			FSetting S; S.Id = Id; S.Label = Label; S.Hint = Hint; S.Tab = Tab; S.Kind = K; S.Min = Mn; S.Max = Mx; S.Step = St; S.Def = Df; S.Unit = Unit; S.Show = Show;
			return S;
		}

		void Build()
		{
			if (GList.Num()) return;
			// ---- tab 0: battle
			FSetting D = Mk(TEXT("difficulty"), TEXT("СЛОЖНОСТЬ ПРОТИВНИКА"), TEXT("Как быстро и точно реагирует пилот-ИИ: парирует, уклоняется, использует спецприёмы."), 0, EKind::Choice, 0, 2, 1, 1);
			D.Names = { TEXT("ЛЁГКАЯ"), TEXT("СРЕДНЯЯ"), TEXT("ТЯЖЁЛАЯ") };
			GList.Add(D);
			FSetting St = Mk(TEXT("enemy_style"), TEXT("СТИЛЬ ПРОТИВНИКА"), TEXT("Авто — стили сменяются от боя к бою. Или выбери один и тренируйся против него."), 0, EKind::Choice, 0, 6, 1, 0);
			St.Names = { TEXT("АВТО"), TEXT("КОНТРБОЙЦОВЩИК"), TEXT("ОХОТНИК НА КОНЕЧНОСТИ"), TEXT("ОБМАНЩИК"), TEXT("ГРОМИЛА"), TEXT("БОРЕЦ"), TEXT("СТРЕЛОК") };
			GList.Add(St);
			GList.Add(Mk(TEXT("fight_speed"), TEXT("СКОРОСТЬ БОЯ"), TEXT("Темп всего боя и анимаций. Меньше — тяжелее и медленнее, больше — быстрее и резче."), 0, EKind::Slider, 0.5f, 1.3f, 0.02f, 0.82f, TEXT("%"), 100.f));
			GList.Add(Mk(TEXT("min_dist"), TEXT("МИН. ДИСТАНЦИЯ МЕЖДУ МЕХАМИ"), TEXT("Ближе этого расстояния роботы не сходятся. От +20 м роботы идут с усилием."), 0, EKind::Slider, 30.f, 80.f, 5.f, 50.f, TEXT(" м")));
			GList.Add(Mk(TEXT("hit_stop"), TEXT("ОТДАЧА УДАРОВ (ЗАМЕДЛЕНИЕ)"), TEXT("Сила кратких остановок кадра при попаданиях."), 0, EKind::Slider, 0.f, 2.f, 0.1f, 1.f, TEXT("%"), 100.f));
			GList.Add(Mk(TEXT("infected"), TEXT("ЗАРАЖЁННЫЙ ПРОТИВНИК"), TEXT("Мутации прорываются сквозь броню врага."), 0, EKind::Toggle, 0, 1, 1, 1));
			// ---- tab 1: world
			GList.Add(Mk(TEXT("fog"), TEXT("ТУМАН"), TEXT("Плотность тумана. Меньше — дальше видно, больше — гуще и мрачнее."), 1, EKind::Slider, 0.f, 3.f, 0.1f, 1.f, TEXT("%"), 100.f));
			GList.Add(Mk(TEXT("brightness"), TEXT("ЯРКОСТЬ СЦЕНЫ"), TEXT("Экспозиция мира в ступенях (EV)."), 1, EKind::Slider, -2.f, 2.f, 0.1f, 0.f, TEXT(" EV")));
			GList.Add(Mk(TEXT("neon"), TEXT("ЯРКОСТЬ НЕОНА И ВЫВЕСОК"), TEXT("Свечение вывесок и подсветка улиц."), 1, EKind::Slider, 0.2f, 2.5f, 0.1f, 1.f, TEXT("%"), 100.f));
			GList.Add(Mk(TEXT("rain"), TEXT("ДОЖДЬ"), TEXT("Плотность дождя. 0 — без дождя."), 1, EKind::Slider, 0.f, 1.f, 0.1f, 0.8f, TEXT("%"), 100.f));
			GList.Add(Mk(TEXT("helis"), TEXT("ВЕРТОЛЁТЫ"), TEXT("Количество вертолётов с прожекторами (их можно схватить и бросить)."), 1, EKind::Slider, 0.f, 3.f, 1.f, 2.f));
			GList.Add(Mk(TEXT("mist"), TEXT("ДЫМКА НАД ЗЕМЛЁЙ"), TEXT("Низкие клубы тумана, в которых слабо читается рельеф улиц."), 1, EKind::Toggle, 0, 1, 1, 0));
			GList.Add(Mk(TEXT("lights"), TEXT("ИСТОЧНИКИ НЕОНА"), TEXT("Сколько неоновых источников света работает одновременно (влияет на fps)."), 1, EKind::Slider, 10.f, 140.f, 10.f, 70.f));
			// ---- tab 2: graphics
			GList.Add(Mk(TEXT("preset"), TEXT("ПРЕСЕТ ГРАФИКИ"), TEXT("Общий уровень качества. RTX — аппаратная трассировка лучей (нужна видеокарта RTX)."), 2, EKind::Choice, 0, 4, 1, -1));
			GList.Last().Names = { TEXT("НИЗКАЯ"), TEXT("СРЕДНЯЯ"), TEXT("ВЫСОКАЯ"), TEXT("УЛЬТРА"), TEXT("RTX") };
			GList.Add(Mk(TEXT("render_scale"), TEXT("МАСШТАБ РЕНДЕРА (АПСКЕЙЛ)"), TEXT("Игра рисуется в меньшем разрешении и растягивается встроенным апскейлером TSR. 0 — авто по пресету."), 2, EKind::Slider, 0.f, 1.f, 0.05f, 0.f, TEXT("%"), 100.f));
			GList.Add(Mk(TEXT("draw_dist"), TEXT("ДАЛЬНОСТЬ ПРОРИСОВКИ ГОРОДА"), TEXT("Дальше этого расстояния здания не рисуются (скрыты туманом). Меньше — быстрее."), 2, EKind::Slider, 300.f, 1500.f, 50.f, 700.f, TEXT(" м")));
			GList.Add(Mk(TEXT("fps_cap"), TEXT("ОГРАНИЧЕНИЕ FPS"), TEXT("Верхний предел частоты кадров."), 2, EKind::Choice, 0, 5, 1, 0));
			GList.Last().Names = { TEXT("НЕТ"), TEXT("60"), TEXT("75"), TEXT("90"), TEXT("120"), TEXT("144") };
			GList.Add(Mk(TEXT("vsync"), TEXT("ВЕРТИКАЛЬНАЯ СИНХРОНИЗАЦИЯ"), TEXT("Убирает разрывы кадра, но добавляет задержку."), 2, EKind::Toggle, 0, 1, 1, 0));
			GList.Add(Mk(TEXT("bloom"), TEXT("СВЕЧЕНИЕ (BLOOM)"), TEXT("Сила ореолов вокруг ярких источников."), 2, EKind::Slider, 0.f, 2.f, 0.1f, 0.8f, TEXT("%"), 100.f));
			GList.Add(Mk(TEXT("motion_blur"), TEXT("РАЗМЫТИЕ ДВИЖЕНИЯ"), TEXT("Кинематографичное размытие при быстром движении."), 2, EKind::Slider, 0.f, 1.f, 0.1f, 0.f, TEXT("%"), 100.f));
			GList.Add(Mk(TEXT("fps_counter"), TEXT("СЧЁТЧИК FPS"), TEXT("Небольшой счётчик в углу кабины (F3)."), 2, EKind::Toggle, 0, 1, 1, 1));
			// ---- tab 3: controls and camera
			GList.Add(Mk(TEXT("fov"), TEXT("УГОЛ ОБЗОРА"), TEXT("Поле зрения камеры из кабины."), 3, EKind::Slider, 70.f, 115.f, 1.f, 98.f, TEXT("°")));
			GList.Add(Mk(TEXT("shake"), TEXT("ТРЯСКА КАМЕРЫ"), TEXT("Сила тряски кабины от ударов и шагов."), 3, EKind::Slider, 0.f, 2.f, 0.1f, 1.f, TEXT("%"), 100.f));
			GList.Add(Mk(TEXT("mouse"), TEXT("ЧУВСТВИТЕЛЬНОСТЬ МЫШИ"), TEXT("Скорость поворота корпуса мышью."), 3, EKind::Slider, 0.3f, 3.f, 0.1f, 1.f, TEXT("%"), 100.f));
			GList.Add(Mk(TEXT("pad_look"), TEXT("ЧУВСТВИТЕЛЬНОСТЬ ПРАВОГО СТИКА"), TEXT("Скорость обзора стиком."), 3, EKind::Slider, 0.3f, 2.5f, 0.1f, 1.f, TEXT("%"), 100.f));
			GList.Add(Mk(TEXT("rumble"), TEXT("ВИБРАЦИЯ ГЕЙМПАДА"), TEXT("Сила отдачи на геймпаде."), 3, EKind::Slider, 0.f, 1.5f, 0.1f, 1.f, TEXT("%"), 100.f));
			GList.Add(Mk(TEXT("hud_scale"), TEXT("РАЗМЕР ИНТЕРФЕЙСА"), TEXT("Масштаб надписей и приборов на стекле."), 3, EKind::Slider, 0.7f, 1.5f, 0.05f, 1.f, TEXT("%"), 100.f));
		}
	}

	const TCHAR* TabName(int32 Tab)
	{
		static const TCHAR* N[kTabCount] = { TEXT("БОЙ"), TEXT("МИР"), TEXT("ГРАФИКА"), TEXT("УПРАВЛЕНИЕ") };
		return N[FMath::Clamp(Tab, 0, kTabCount - 1)];
	}

	const TArray<FSetting>& All() { Build(); return GList; }

	TArray<int32> OfTab(int32 Tab)
	{
		Build();
		TArray<int32> R;
		for (int32 i = 0; i < GList.Num(); ++i) if (GList[i].Tab == Tab) R.Add(i);
		return R;
	}

	void Load()
	{
		Build();
		for (const FSetting& S : GList)
		{
			float V = S.Def;
			if (S.Def < -0.5f && FCString::Strcmp(S.Id, TEXT("preset")) == 0) V = float(IVGraphics::Load());
			GConfig->GetFloat(TEXT("IV"), S.Id, V, IniPath());
			GVals.Add(S.Id, FMath::Clamp(V, S.Min, S.Max));
		}
		bLoaded = true;
	}

	float Get(const TCHAR* Id)
	{
		if (!bLoaded) Load();
		const float* V = GVals.Find(Id);
		return V ? *V : 0.f;
	}
	int32 GetInt(const TCHAR* Id) { return FMath::RoundToInt(Get(Id)); }
	bool GetBool(const TCHAR* Id) { return Get(Id) > 0.5f; }

	void Set(const TCHAR* Id, float Value)
	{
		if (!bLoaded) Load();
		for (const FSetting& S : GList)
			if (FCString::Strcmp(S.Id, Id) == 0)
			{
				Value = FMath::Clamp(Value, S.Min, S.Max);
				GVals.Add(Id, Value);
				GConfig->SetFloat(TEXT("IV"), Id, Value, IniPath());
				GConfig->Flush(false, IniPath());
				if (FCString::Strcmp(Id, TEXT("preset")) == 0) IVGraphics::Save(FMath::RoundToInt(Value));
				return;
			}
	}

	void Adjust(int32 Index, int32 Dir, bool bFast)
	{
		Build();
		if (!GList.IsValidIndex(Index)) return;
		const FSetting& S = GList[Index];
		float V = Get(S.Id);
		if (S.Kind == EKind::Toggle) V = (V > 0.5f) ? 0.f : 1.f;
		else if (S.Kind == EKind::Choice) { const int32 N = int32(S.Max - S.Min) + 1; V = S.Min + float((FMath::RoundToInt(V - S.Min) + Dir + N) % N); }
		else V += Dir * S.Step * (bFast ? 4.f : 1.f);
		Set(S.Id, FMath::RoundToFloat(V / S.Step) * S.Step);
	}

	FString ValueText(int32 Index)
	{
		Build();
		const FSetting& S = GList[Index];
		const float V = Get(S.Id);
		if (S.Kind == EKind::Toggle) return V > 0.5f ? TEXT("ВКЛ") : TEXT("ВЫКЛ");
		if (S.Kind == EKind::Choice) return S.Names.IsValidIndex(FMath::RoundToInt(V)) ? S.Names[FMath::RoundToInt(V)] : FString();
		if (FCString::Strcmp(S.Id, TEXT("render_scale")) == 0 && V < 0.01f) return TEXT("АВТО");
		const float X = V * S.Show;
		return (S.Step * S.Show < 0.99f && FMath::Abs(S.Show - 1.f) < 0.01f) ? FString::Printf(TEXT("%.1f%s"), X, S.Unit) : FString::Printf(TEXT("%d%s"), FMath::RoundToInt(X), S.Unit);
	}

	void ResetAll()
	{
		Build();
		for (const FSetting& S : GList) Set(S.Id, S.Def < -0.5f ? 2.f : S.Def);
	}

	void Apply(UWorld* World)
	{
		if (!World) return;
		IConsoleManager& CM = IConsoleManager::Get();
		auto CV = [&](const TCHAR* N, float V) { if (IConsoleVariable* C = CM.FindConsoleVariable(N)) C->Set(V, ECVF_SetByGameSetting); };
		// graphics preset first (it sets the resolution scale), then the manual overrides on top
		int32 Pre = GetInt(TEXT("preset"));
		FParse::Value(FCommandLine::Get(), TEXT("-IVGfx="), Pre);
		IVGraphics::Apply(World, Pre);
		const float RS = Get(TEXT("render_scale"));
		if (RS > 0.01f) CV(TEXT("r.ScreenPercentage"), RS * 100.f);
		CV(TEXT("t.MaxFPS"), 0.f);
		static const float Caps[6] = { 0.f, 60.f, 75.f, 90.f, 120.f, 144.f };
		CV(TEXT("t.MaxFPS"), Caps[FMath::Clamp(GetInt(TEXT("fps_cap")), 0, 5)]);
		CV(TEXT("r.VSync"), GetBool(TEXT("vsync")) ? 1.f : 0.f);
		CV(TEXT("r.MotionBlurQuality"), Get(TEXT("motion_blur")) > 0.01f ? 3.f : 0.f);
		if (AIVEnvironment* Env = AIVEnvironment::Get(World)) Env->ApplySettings(Get(TEXT("fog")), Get(TEXT("brightness")), Get(TEXT("neon")), Get(TEXT("bloom")), Get(TEXT("motion_blur")), Get(TEXT("rain")), GetBool(TEXT("mist")));
		if (AIVEnvironment* Env2 = AIVEnvironment::Get(World)) if (AIVDistrict* Dst = Env2->GetDistrict()) { Dst->ApplyDrawDistance(Get(TEXT("draw_dist")) * 100.f); Dst->SetLightBudget(GetInt(TEXT("lights"))); }
		AIVHelicopter::SetFleetSize(World, GetInt(TEXT("helis")));
		for (TActorIterator<AIVMechPawn> It(World); It; ++It) It->ApplySettings();
		for (TActorIterator<AIVPlayerController> It(World); It; ++It) It->ApplySettings();
	}
}
