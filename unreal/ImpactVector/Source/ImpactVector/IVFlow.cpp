#include "IVFlow.h"
#include "IVMechPawn.h"
#include "IVCombat.h"
#include "IVEnvironment.h"
#include "IVDistrict.h"
#include "IVPlayerController.h"
#include "Engine/World.h"
#include "Kismet/GameplayStatics.h"
#include "Kismet/KismetSystemLibrary.h"
#include "GameFramework/PlayerController.h"
#include "HAL/IConsoleManager.h"
#include "InputCoreTypes.h"
#include "Components/AudioComponent.h"
#include "Sound/SoundBase.h"
#include "IVAudio.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"

namespace
{
	const TCHAR* kDifficulty[3] = { TEXT("Лёгкий"), TEXT("Нормальный"), TEXT("Жёсткий") };
	const iv::Archetype kRotation[6] = { iv::Archetype::Counterpuncher, iv::Archetype::LimbHunter, iv::Archetype::Trickster, iv::Archetype::Breaker, iv::Archetype::Grappler, iv::Archetype::Gunner };

	void SetCam(int32 V)
	{
		if (IConsoleVariable* C = IConsoleManager::Get().FindConsoleVariable(TEXT("iv.Cam"))) C->Set(V);
	}
}

AIVGameFlow::AIVGameFlow()
{
	PrimaryActorTick.bCanEverTick = true;
	PrimaryActorTick.TickGroup = TG_PostUpdateWork;
}

AIVPlayerController* AIVGameFlow::PC() const
{
	return Cast<AIVPlayerController>(UGameplayStatics::GetPlayerController(this, 0));
}

void AIVGameFlow::BuildSteps()
{
	Steps.Reset();
	auto Add = [this](const TCHAR* Title, const TCHAR* Body, const TCHAR* Keys, ETutGoal Goal, int32 Count, float Seconds, iv::DummyMode D, int32 Script = 0, bool bUlt = false)
	{
		FIVTutorialStep S;
		S.Title = Title; S.Body = Body; S.Keys = Keys; S.Goal = Goal; S.Count = Count; S.Seconds = Seconds; S.Dummy = D; S.Script = Script; S.bFullUltimate = bUlt;
		Steps.Add(S);
	};
	using DM = iv::DummyMode;
	Add(TEXT("ДОБРО ПОЖАЛОВАТЬ В КАБИНУ"), TEXT("Ты пилот боевого меха. Впереди тренировочный манекен. Начнём с движения."), TEXT(""), ETutGoal::Timer, 1, 5.f, DM::Passive);
	Add(TEXT("ШАГ ВПЕРЁД"), TEXT("Подойди к манекену на дистанцию удара мечом."), TEXT("W A S D — ходьба   ·   Shift — бег   ·   геймпад: левый стик"), ETutGoal::Walk, 1, 0.f, DM::Passive);
	Add(TEXT("ОБЗОР"), TEXT("Поверни корпус мышью. Tab — захват цели: камера будет следить за врагом."), TEXT("Мышь   ·   Tab — захват   ·   геймпад: правый стик, R3"), ETutGoal::Look, 1, 0.f, DM::Passive);
	Add(TEXT("ТЯЖЁЛЫЙ УДАР МЕЧОМ"), TEXT("Удерживай левую кнопку мыши и веди мышь, рисуя траекторию клинка: куда повёл — оттуда замах, где закончил — туда придётся удар (голова, плечи, руки, ноги). Отпусти — удар. 3 попадания."),
		TEXT("ЛКМ (держать) + мышь, отпустить   ·   геймпад: RT + правый стик   ·   C — отмена замаха"), ETutGoal::HeavyHit, 3, 0.f, DM::Passive);
	Add(TEXT("БЫСТРЫЙ УДАР КУЛАКОМ"), TEXT("Короткий клик ЛКМ — быстрый удар левой рукой. Слабый, но почти мгновенный: им сбивают чужой замах. 2 попадания."), TEXT("ЛКМ — короткий клик"), ETutGoal::QuickHit, 2, 0.f, DM::Passive);
	Add(TEXT("БЛОК И ПАРИРОВАНИЕ"), TEXT("Манекен будет рубить с разных сторон. Зажми ПКМ и поверни мышь туда, откуда идёт клинок. Нажми блок в последний момент перед ударом — получится парирование. Отбей 2 удара."),
		TEXT("ПКМ + мышь   ·   Ctrl при блоке — жёсткая стойка   ·   геймпад: LT + правый стик"), ETutGoal::Defend, 2, 0.f, DM::Scripted, 1);
	Add(TEXT("УКЛОНЕНИЕ"), TEXT("Q / E — шаг в сторону с поворотом корпуса. Уход спасает ТОЛЬКО от боковых ударов (слева и справа). От ударов сверху и снизу не уйти — их надо блокировать. Увернись 2 раза."),
		TEXT("Q — влево   ·   E — вправо   ·   геймпад: LB / RB"), ETutGoal::Evade, 2, 0.f, DM::Scripted, 2);
	Add(TEXT("КОНТРУДАР"), TEXT("После уклонения или парирования открывается короткое окно: бей сразу, пока враг не закрылся."), TEXT("Q / E или ПКМ, затем ЛКМ"), ETutGoal::Counter, 1, 0.f, DM::Scripted, 2);
	Add(TEXT("СТОЛКНОВЕНИЕ КЛИНКОВ"), TEXT("Если оба бьют по одной линии одновременно, клинки сталкиваются: оба удара гасятся, оба меха отлетают назад. Читай замах врага и бей навстречу."), TEXT(""), ETutGoal::Timer, 1, 9.f, DM::Passive);
	Add(TEXT("СПЕЦСПОСОБНОСТИ"), TEXT("Каждая — с долгой перезарядкой и своим эффектом. 1 — ракеты (слепят). 2 — рельсовое копьё (блокирует руки). 3 — плазма (поджигает). Держи кнопку — заряд, отпусти — выстрел. Сделай один выстрел."),
		TEXT("1 · 2 · 3 (держать и отпустить)   ·   геймпад: крестовина"), ETutGoal::Ability, 1, 0.f, DM::Passive);
	Add(TEXT("ШВЫРНУТЬ ЗДАНИЕ"), TEXT("F — вырвать кусок соседнего здания и швырнуть врагу в лицо: он ослепнет и потеряет устойчивость. Нужно здание рядом."), TEXT("F   ·   геймпад: A"), ETutGoal::Scoop, 1, 0.f, DM::Passive);
	Add(TEXT("УЛЬТИМЕЙТ"), TEXT("Шкала полна. V — удар второй рукой под грудь, прыжок и удар сверху. Если враг ослаблен — рассечёшь его пополам. Если здоров — отрубишь ему свободную руку, и ультимейт у него пропадёт."), TEXT("V   ·   геймпад: Y"), ETutGoal::Ultimate, 1, 0.f, DM::Passive, 0, true);
	Add(TEXT("ОБУЧЕНИЕ ПРОЙДЕНО"), TEXT("Теперь настоящая дуэль. Противник запоминает твои привычки и отвечает по тем же линиям — меняй рисунок боя."), TEXT(""), ETutGoal::Timer, 1, 5.f, DM::Passive);
}

void AIVGameFlow::Begin(AIVMechPawn* InPlayer, AIVMechPawn* InEnemy, AIVCombatDirector* InDir, EIVFlowState Initial)
{
	Player = InPlayer; Enemy = InEnemy; Dir = InDir;
	PlayerHome = Player->GetActorTransform();
	EnemyHome = Enemy->GetActorTransform();
	BuildSteps();
	if (Dir) EventHandle = Dir->OnEvent.AddUObject(this, &AIVGameFlow::OnCombatEvent);
	switch (Initial)
	{
	case EIVFlowState::Tutorial: EnterTutorial(); break;
	case EIVFlowState::Duel: EnterDuel(); break;
	default: EnterMenu(); break;
	}
}

void AIVGameFlow::PlaceMechs(float CoreUnits)
{
	if (!Player || !Enemy) return;
	const FVector PL = PlayerHome.GetLocation();
	const float Yaw = PlayerHome.Rotator().Yaw;
	const FVector Fwd = FRotator(0.f, Yaw, 0.f).Vector();
	FVector EL = EnemyHome.GetLocation();
	if (CoreUnits > 0.f) EL = PL + Fwd * (CoreUnits + AIVCombatDirector::kBodyGapUnits) * 100.f;
	// keep both on the ground
	AIVDistrict* Dist = AIVEnvironment::Get(GetWorld()) ? AIVEnvironment::Get(GetWorld())->GetDistrict() : nullptr;
	auto Snap = [Dist](FVector P)
	{
		if (Dist) P.Z = Dist->SampleHeightCm(P.X, P.Y) + 4100.f;
		return P;
	};
	Player->SetActorLocationAndRotation(Snap(PL), FRotator(0.f, Yaw, 0.f), false, nullptr, ETeleportType::TeleportPhysics);
	Enemy->SetActorLocationAndRotation(Snap(EL), FRotator(0.f, Yaw + 180.f, 0.f), false, nullptr, ETeleportType::TeleportPhysics);
	Player->SetAim(Yaw, 0.f);
	Enemy->SetAim(Yaw + 180.f, 0.f);
	Player->ResetMotion();
	Enemy->ResetMotion();
	LastPlayerPos = Player->GetActorLocation();
	LastYaw = Player->GetAimYaw();
}

void AIVGameFlow::SetBanner(const FString& Main, const FString& Sub, float Seconds)
{
	Banner = Main; SubBanner = Sub; BannerLeft = Seconds;
}

// ---------------------------------------------------------------------------------------------------- music
namespace
{
	UAudioComponent* Spawn2D(UWorld* W, const TCHAR* Id, float Vol)
	{
		USoundBase* S = IVAudio::Get(Id);
		if (!S) return nullptr;
		UAudioComponent* C = UGameplayStatics::SpawnSound2D(W, S, Vol, 1.f, 0.f, nullptr, false, false);
		return C;
	}
}

void AIVGameFlow::StartMenuMusic(float Volume)
{
	if (FParse::Param(FCommandLine::Get(), TEXT("IVNoAudio"))) return;
	if (!MenuMusic) MenuMusic = Spawn2D(GetWorld(), TEXT("mus_menu_loop"), Volume);
	if (MenuMusic) { MenuMusic->SetVolumeMultiplier(Volume); if (!MenuMusic->IsPlaying()) MenuMusic->Play(); }
}

void AIVGameFlow::StartBattleMusic()
{
	if (FParse::Param(FCommandLine::Get(), TEXT("IVNoAudio"))) return;
	StopBattleMusic();
	static const TCHAR* Ids[4] = { TEXT("mus_battle_drums_loop"), TEXT("mus_battle_bass_loop"), TEXT("mus_battle_synth_loop"), TEXT("mus_battle_lead_loop") };
	for (const TCHAR* Id : Ids)
	{
		UAudioComponent* C = Spawn2D(GetWorld(), Id, 0.f);
		MusicStems.Add(C);
	}
	Intensity = 0.3f;
}

void AIVGameFlow::StopBattleMusic()
{
	for (UAudioComponent* C : MusicStems) if (C) C->Stop();
	MusicStems.Reset();
}

void AIVGameFlow::UpdateMusic(float Dt)
{
	if (FParse::Param(FCommandLine::Get(), TEXT("IVNoAudio"))) return;
	const bool bMenuLike = State == EIVFlowState::Menu || State == EIVFlowState::Tutorial;
	if (MenuMusic)
	{
		const float Target = State == EIVFlowState::Menu ? 0.55f : (State == EIVFlowState::Tutorial ? 0.28f : 0.f);
		const float Cur = MenuMusic->VolumeMultiplier;
		MenuMusic->SetVolumeMultiplier(FMath::FInterpTo(Cur, Target, Dt, 0.9f));
	}
	if (MusicStems.Num() == 4 && State == EIVFlowState::Duel && Dir && Dir->GetDuel())
	{
		const iv::Duel& D = *Dir->GetDuel();
		float Target = 0.42f;
		const iv::Fighter& A = D.fighter(iv::Side::A);
		const iv::Fighter& B = D.fighter(iv::Side::B);
		if (A.phase != iv::Phase::Idle || B.phase != iv::Phase::Idle) LastAction = 0.f; else LastAction += Dt;
		if (LastAction < 2.5f) Target += 0.28f;
		if (A.body.Integrity() < 0.55f || B.body.Integrity() < 0.55f) Target += 0.22f;
		if (A.body.Integrity() < 0.3f || B.body.Integrity() < 0.3f) Target += 0.2f;
		if (D.cinematic().active) Target = 1.f;
		Intensity = FMath::FInterpTo(Intensity, Target, Dt, Target > Intensity ? 1.4f : 0.35f);
		auto Lvl = [this](float Lo, float Span) { return FMath::Clamp((Intensity - Lo) / Span, 0.f, 1.f); };
		const float V[4] = { 0.9f * Lvl(0.1f, 0.3f), 0.9f * Lvl(0.18f, 0.3f), 0.8f * Lvl(0.45f, 0.3f), 0.85f * Lvl(0.72f, 0.25f) };
		for (int32 i = 0; i < 4; ++i) if (MusicStems[i]) MusicStems[i]->SetVolumeMultiplier(FMath::FInterpTo(MusicStems[i]->VolumeMultiplier, V[i], Dt, 2.f));
	}
	else if (MusicStems.Num() == 4)
	{
		for (UAudioComponent* C : MusicStems) if (C) C->SetVolumeMultiplier(FMath::FInterpTo(C->VolumeMultiplier, 0.f, Dt, 1.5f));
	}
	(void)bMenuLike;
}

// ---------------------------------------------------------------------------------------------------- states
void AIVGameFlow::EnterMenu()
{
	State = EIVFlowState::Menu;
	MenuIndex = 0;
	if (AIVPlayerController* P = PC()) P->SetCombatEnabled(false);
	SetCam(5);
	if (Dir)
	{
		Dir->EnableAutoPlayer(iv::Archetype::Counterpuncher, iv::Difficulty::Normal);
		Dir->SetEnemyStyle(iv::Archetype::LimbHunter, iv::Difficulty::Normal);
		Dir->Restart();
		Dir->SetDummy(iv::DummyMode::Off);
	}
	PlaceMechs(60.f);
	SetBanner(TEXT(""), TEXT(""), 0.f);
	EndDelay = -1.f;
	StopBattleMusic();
	StartMenuMusic(0.55f);
}

void AIVGameFlow::EnterTutorial()
{
	State = EIVFlowState::Tutorial;
	if (AIVPlayerController* P = PC()) P->SetCombatEnabled(true);
	SetCam(0);
	if (Dir)
	{
		Dir->ClearPlayerAuto();
		Dir->SetEnemyStyle(iv::Archetype::Counterpuncher, iv::Difficulty::Easy);
		Dir->Restart();
	}
	PlaceMechs(46.f);
	StopBattleMusic();
	StartMenuMusic(0.28f);
	Step = 0;
	EndDelay = -1.f;
	{ int32 S0 = 0; FParse::Value(FCommandLine::Get(), TEXT("-IVStep="), S0); BeginStep(FMath::Clamp(S0, 0, Steps.Num() - 1)); }
}

void AIVGameFlow::EnterDuel()
{
	State = EIVFlowState::Duel;
	if (AIVPlayerController* P = PC()) P->SetCombatEnabled(true);
	SetCam(0);
	if (Dir)
	{
		Dir->ClearPlayerAuto();
		Dir->SetEnemyStyle(kRotation[NextStyle % 6], static_cast<iv::Difficulty>(FMath::Clamp(Difficulty, 0, 2)));
		Dir->Restart();
		Dir->SetDummy(iv::DummyMode::Off);
	}
	PlaceMechs(60.f);
	const TCHAR* StyleNames[6] = { TEXT("Контрбойцовщик"), TEXT("Громила"), TEXT("Охотник на конечности"), TEXT("Обманщик"), TEXT("Стрелок"), TEXT("Борец") };
	SetBanner(TEXT("ДУЭЛЬ"), FString::Printf(TEXT("Противник: %s  ·  %s"), StyleNames[NextStyle % 6], kDifficulty[FMath::Clamp(Difficulty, 0, 2)]), 3.2f);
	++NextStyle;
	DuelClock = 0.f;
	HitsLanded = HitsTaken = Parries = 0;
	EndDelay = -1.f;
	StartBattleMusic();
}

void AIVGameFlow::EnterResult()
{
	State = EIVFlowState::Result;
	StopBattleMusic();
	if (!FParse::Param(FCommandLine::Get(), TEXT("IVNoAudio"))) IVAudio::Play2D(GetWorld(), Dir->GetEndText() == TEXT("VICTORY") ? TEXT("mus_victory") : TEXT("mus_defeat"), 0.9f);
	ResultT = 0.f;
	if (AIVPlayerController* P = PC()) P->SetCombatEnabled(false);
}

// ---------------------------------------------------------------------------------------------------- tutorial
void AIVGameFlow::BeginStep(int32 Index)
{
	Step = Index;
	Progress = 0;
	StepTimer = 0.f;
	bStepDone = false;
	StepDoneFlash = 0.f;
	WalkAcc = LookAcc = 0.f;
	SinceDefence = 99.f;
	if (!Steps.IsValidIndex(Step) || !Dir) return;
	const FIVTutorialStep& S = Steps[Step];
	Dir->HealFighter(iv::Side::A);
	Dir->SetDummy(S.Dummy);
	if (S.Dummy == iv::DummyMode::Scripted) Dir->SetDummyScript(S.Script);
	if (S.bFullUltimate) Dir->FillUltimate(iv::Side::A);
	if (FParse::Param(FCommandLine::Get(), TEXT("IVHurtEnemy")) && Dir->GetMutableDuel())
		for (int32 z = 0; z < iv::kZoneCount; ++z) Dir->GetMutableDuel()->fighter(iv::Side::B).body.ApplyDamage(static_cast<iv::Zone>(z), 150.f, iv::StrikeKind::Quick);
	if (S.Goal != ETutGoal::Walk && Dir->GetDuel() && Dir->GetDuel()->distance() > 40.f) PlaceMechs(26.f);
}

void AIVGameFlow::AdvanceStep()
{
	if (Step + 1 >= Steps.Num()) { EnterDuel(); return; }
	BeginStep(Step + 1);
}

float AIVGameFlow::GetStepProgress01() const
{
	if (!Steps.IsValidIndex(Step)) return 0.f;
	const FIVTutorialStep& S = Steps[Step];
	if (S.Goal == ETutGoal::Timer) return S.Seconds > 0.f ? FMath::Clamp(StepTimer / S.Seconds, 0.f, 1.f) : 0.f;
	if (S.Goal == ETutGoal::Walk && Dir && Dir->GetDuel()) return FMath::Clamp((60.f - Dir->GetDuel()->distance()) / 26.f, 0.f, 1.f);
	if (S.Goal == ETutGoal::Look) return FMath::Clamp(LookAcc / 70.f, 0.f, 1.f);
	return FMath::Clamp(float(Progress) / float(FMath::Max(S.Count, 1)), 0.f, 1.f);
}

void AIVGameFlow::OnCombatEvent(const iv::Event& Ev)
{
	using iv::EventType;
	const bool bMine = (Ev.actor == iv::Side::A);
	if (State == EIVFlowState::Duel)
	{
		if (Ev.type == EventType::StrikeContact && bMine && Ev.b == int32(iv::Outcome::Hit)) ++HitsLanded;
		if (Ev.type == EventType::StrikeContact && !bMine && Ev.b == int32(iv::Outcome::Hit)) ++HitsTaken;
		if (Ev.type == EventType::ParrySuccess && bMine) ++Parries;
		if (Ev.type == EventType::MatchEnd) EndDelay = 4.6f;
		return;
	}
	if (State != EIVFlowState::Tutorial || !Steps.IsValidIndex(Step) || bStepDone) return;
	const FIVTutorialStep& S = Steps[Step];
	if (Ev.type == EventType::ParrySuccess && bMine) SinceDefence = 0.f;
	if (Ev.type == EventType::Evaded && bMine) SinceDefence = 0.f;
	switch (S.Goal)
	{
	case ETutGoal::HeavyHit:
		if (Ev.type == EventType::StrikeContact && bMine && Ev.a == int32(iv::StrikeKind::Heavy) && Ev.b == int32(iv::Outcome::Hit)) ++Progress;
		break;
	case ETutGoal::QuickHit:
		if (Ev.type == EventType::StrikeContact && bMine && Ev.a == int32(iv::StrikeKind::Quick) && Ev.b == int32(iv::Outcome::Hit)) ++Progress;
		break;
	case ETutGoal::Defend:
		if (bMine && (Ev.type == EventType::ParrySuccess || Ev.type == EventType::Blocked)) ++Progress;
		break;
	case ETutGoal::Evade:
		if (bMine && Ev.type == EventType::Evaded) ++Progress;
		break;
	case ETutGoal::Counter:
		if (Ev.type == EventType::StrikeContact && bMine && Ev.b == int32(iv::Outcome::Hit) && SinceDefence < 1.4f) ++Progress;
		break;
	case ETutGoal::Ability:
		if (Ev.type == EventType::WeaponFired && bMine) ++Progress;
		break;
	case ETutGoal::Scoop:
		if (Ev.type == EventType::ExternalHit && !bMine && Ev.a == 0) ++Progress;
		break;
	case ETutGoal::Ultimate:
		if (Ev.type == EventType::UltimateUsed && bMine) ++Progress;
		break;
	default: break;
	}
}

FString AIVGameFlow::GetStatsLine() const
{
	return FString::Printf(TEXT("Время боя %d:%02d   ·   попаданий %d   ·   получено %d   ·   парирований %d"), int32(DuelClock) / 60, int32(DuelClock) % 60, HitsLanded, HitsTaken, Parries);
}

TArray<FString> AIVGameFlow::GetMenuItems() const
{
	TArray<FString> I;
	I.Add(TEXT("ОБУЧЕНИЕ"));
	I.Add(FString::Printf(TEXT("ДУЭЛЬ      <  %s  >"), kDifficulty[FMath::Clamp(Difficulty, 0, 2)]));
	I.Add(TEXT("ВЫХОД"));
	return I;
}

FString AIVGameFlow::GetDifficultyName() const { return kDifficulty[FMath::Clamp(Difficulty, 0, 2)]; }

// ---------------------------------------------------------------------------------------------------- tick
void AIVGameFlow::MenuInput()
{
	APlayerController* P = UGameplayStatics::GetPlayerController(this, 0);
	if (!P) return;
	auto Pressed = [P](std::initializer_list<FKey> Keys) { for (const FKey& K : Keys) if (P->WasInputKeyJustPressed(K)) return true; return false; };
	if (Pressed({ EKeys::Up, EKeys::W, EKeys::Gamepad_DPad_Up })) MenuIndex = (MenuIndex + 2) % 3;
	if (Pressed({ EKeys::Down, EKeys::S, EKeys::Gamepad_DPad_Down })) MenuIndex = (MenuIndex + 1) % 3;
	if (MenuIndex == 1)
	{
		if (Pressed({ EKeys::Left, EKeys::A, EKeys::Gamepad_DPad_Left })) Difficulty = FMath::Max(0, Difficulty - 1);
		if (Pressed({ EKeys::Right, EKeys::D, EKeys::Gamepad_DPad_Right })) Difficulty = FMath::Min(2, Difficulty + 1);
	}
	if (Pressed({ EKeys::Enter, EKeys::SpaceBar, EKeys::Gamepad_FaceButton_Bottom, EKeys::LeftMouseButton }))
	{
		if (MenuIndex == 0) EnterTutorial();
		else if (MenuIndex == 1) EnterDuel();
		else UKismetSystemLibrary::QuitGame(this, nullptr, EQuitPreference::Quit, false);
	}
}

void AIVGameFlow::Tick(float Dt)
{
	Super::Tick(Dt);
	if (BannerLeft > 0.f) BannerLeft = FMath::Max(0.f, BannerLeft - Dt);
	if (StepDoneFlash > 0.f) StepDoneFlash = FMath::Max(0.f, StepDoneFlash - Dt);
	if (SinceDefence < 90.f) SinceDefence += Dt;
	APlayerController* P = UGameplayStatics::GetPlayerController(this, 0);
	if (!P || !Player || !Enemy || !Dir) return;

	UpdateMusic(Dt);
	if (State != EIVFlowState::Menu && P->WasInputKeyJustPressed(EKeys::Escape)) { EnterMenu(); return; }

	switch (State)
	{
	case EIVFlowState::Menu:
		MenuInput();
		if (Dir->IsMatchOver() && Dir->GetSecondsSinceEnd() > 6.f)
		{
			Dir->Restart();
			PlaceMechs(60.f);
		}
		break;
	case EIVFlowState::Tutorial:
	{
		if (!Steps.IsValidIndex(Step)) break;
		const FIVTutorialStep& S = Steps[Step];
		StepTimer += Dt;
		// bookkeeping for the movement goals
		const FVector PNow = Player->GetActorLocation();
		WalkAcc += FVector::Dist2D(PNow, LastPlayerPos);
		LastPlayerPos = PNow;
		const float Yaw = Player->GetAimYaw();
		LookAcc += FMath::Abs(FMath::FindDeltaAngleDegrees(LastYaw, Yaw));
		LastYaw = Yaw;
		if (P->WasInputKeyJustPressed(EKeys::Tab)) LookAcc += 70.f;
		if (P->WasInputKeyJustPressed(EKeys::Enter) && bStepDone) { AdvanceStep(); break; }
		bool bDone = false;
		switch (S.Goal)
		{
		case ETutGoal::Timer: bDone = StepTimer >= S.Seconds; break;
		case ETutGoal::Walk: bDone = Dir->GetDuel() && Dir->GetDuel()->distance() <= 34.f; break;
		case ETutGoal::Look: bDone = LookAcc >= 70.f; break;
		default: bDone = Progress >= S.Count; break;
		}
		if (bDone && !bStepDone)
		{
			bStepDone = true;
			StepDoneFlash = 1.f;
			StepTimer = 0.f;
		}
		if (bStepDone && StepTimer >= (S.Goal == ETutGoal::Timer ? 0.2f : 1.6f)) AdvanceStep();
		// keep the lesson going: the trainee never dies, and the gauge stays usable
		if (Dir->IsMatchOver()) { Dir->Restart(); BeginStep(Step); }
		break;
	}
	case EIVFlowState::Duel:
		DuelClock += Dt;
		if (EndDelay > 0.f)
		{
			EndDelay -= Dt;
			if (EndDelay <= 0.f)
			{
				const bool bWin = Dir->GetEndText() == TEXT("VICTORY");
				SetBanner(bWin ? TEXT("ПОБЕДА") : (Dir->GetEndText() == TEXT("DRAW") ? TEXT("НИЧЬЯ") : TEXT("ПОРАЖЕНИЕ")), GetStatsLine(), 1000.f);
				EnterResult();
			}
		}
		break;
	case EIVFlowState::Result:
		ResultT += Dt;
		if (ResultT > 0.6f && P->WasInputKeyJustPressed(EKeys::Enter)) EnterDuel();
		if (ResultT > 0.6f && P->WasInputKeyJustPressed(EKeys::Gamepad_FaceButton_Bottom)) EnterDuel();
		break;
	}
}
