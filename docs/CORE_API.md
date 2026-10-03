# CORE_API — как подключить ядро боя `ivcore`

Ядро — чистая симуляция боевой системы IMPACT VECTOR на C++17: данные на входе (намерения игрока или ИИ),
данные на выходе (состояние тел, события). Без графики, звука, физики мира и зависимостей от Unreal.
Номера разделов `§N` — из питча `docs/pitch/02_pitch/IMPACT_VECTOR_FULL_PITCH_RU.md`.

## 1. Состав

| Заголовок | Что внутри |
|---|---|
| `iv/Types.h` | все `enum` (зоны, состояния, фазы, стороны замаха…) и `MsToTicks` |
| `iv/Tuning.h` | **все** числа баланса в одном месте, у каждого комментарий `pitch §N` |
| `iv/Body.h` | 9 зон × 3 слоя, `Modifiers` (функциональные эффекты повреждений), условия конца боя |
| `iv/Resources.h` | Стабильность, Тепло, Энергия и приоритет питания |
| `iv/Fighter.h` | боец: конечный автомат удара, поза рук, защита, финты, уклонение, орудие. `Input` |
| `iv/Duel.h` | два бойца, контакты, перехват, цепочка реверсов, клинч, конец матча. `World`, `MatchResult` |
| `iv/Ai.h` | `Observation`, `MakeObservation`, `Ai` (6 архетипов × 3 сложности), память привычек |
| `iv/Events.h` | `Event`, `EventLog` (список событий + хэш истории), `HitInfo`/`DecodeHit` |
| `iv/Anim.h` | **v2** `AnimState`, `MakeAnimState(fighter)` — состояние для процедурной анимации |
| `iv/Dummy.h` | **v2** тренировочный манекен (`DummyMode`) |
| `iv/Rng.h` | PCG32 с сидом |
| `iv/Boarding.h` | **v4** абордаж: `Boarding`, `BoardPhase`, `BoardingInput` (см. §7a) |
| `iv/HackGame.h`, `iv/HackBot.h`, `iv/HackExport.h` | **v4** логика мини-игры взлома люка (три слоя), боты для калибровки, экспорт JSON |

Сборка и проверка с нуля:

```
cmake -S core -B build && cmake --build build && ctest --test-dir build --output-on-failure
./build/ivsim --seeds 20          # баланс-симуляция, см. docs/BALANCE_REPORT.md
```

Флаги: `-Wall -Wextra -Werror -fno-exceptions -fno-rtti`, только стандартная библиотека. CI: g++, clang++ (`-std=c++17 -fno-exceptions -fno-rtti -Wall -Wextra -Werror`), ASan+UBSan и MSVC (`/W4 /WX /GR-`) — см. `.github/workflows/core.yml`.

## 2. Модель времени

- Шаг фиксированный: `kTickHz = 60`. Один вызов `Duel::Step` — ровно 1/60 с игрового времени.
- Время — целые тики (`iv::Tick`). Миллисекунды питча переведены в тики в `Tuning.h` через `MsToTicks`.
- В Unreal вызывать из аккумулятора фиксированного шага (не из `DeltaTime`): накопить `DeltaTime`, пока `acc >= 1/60`, сделать
  `Step` и вычесть `1/60`. Кадры рендера интерполируют между последним и предыдущим состоянием.
- Никаких часов, `std::random_device` и глобального изменяемого состояния. Один сид + один и тот же ввод = одна и та же
  история событий (проверено тестами `Determinism.*`, сравнивается хэш потока событий).

## 3. Что подаётся на вход: `Input`

Один `Input` на бойца за тик. Поля-«рёбра» (`quick`, `cancel`, `toGrab`, `switchArm`, `reverse`, `dodge`, `setPriority`)
должны быть `true` ровно один тик — в тик нажатия. Остальные — состояние кнопки/стика в этот тик.

| Поле | Раскладка (pitch §4) | Смысл |
|---|---|---|
| `strikeHeld` | RT удерживается | замах и заряд; отпускание запускает фиксацию (§5.2) |
| `side` | правый стик: вверх/влево/вправо/вниз | `SwingSide::{Up,Left,Right,Down}` — семейство замаха |
| `target` | правый стик: сектор тела | `Zone` цели; пока RT удерживается, смена цели — финт |
| `footwork` | левый стик во время удара | `StepIn / Hold / Turn / StepBack` — вклад ног (§5.2 п.3, §11) |
| `arm` | — | `Arm::L` / `Arm::R` |
| `quick` | короткое нажатие RT | быстрый удар по стороне `side` (§5.3) |
| `cancel` | B | до точки фиксации — бесплатно/дёшево, после — аварийное торможение (§5.2 п.4) |
| `toGrab` | X | в замахе: финт в захват; без замаха: захват (§8, §12) |
| `switchArm` | RB в замахе | финт: переключить руку (§8) |
| `reverse` | RB, пока открыто окно реверса | ответ на перехват/реверс второй рукой (§7) |
| `guardHeld`, `guardSide` | LT + правый стик | блок по сектору; новое нажатие или смена сектора — «нажатие» для парирования (§6) |
| `hardStance` | Y при LT | усиленная стойка (§6) |
| `move` | левый стик вперёд/назад | `+1` сближение, `-1` отход (§11) |
| `dodge`, `dodgeDir` | A + стик | один тяжёлый шаг, `-1` влево / `+1` вправо (§6) |
| `weaponHeld` | Y в оружейном режиме | зажать — заряд, отпустить — выстрел (§13) |
| `ultimate` | кнопка ультимейта (ребро) | v2: срабатывает при полной шкале (`Fighter::UltimateReady()`), цель — `target` |
| `setPriority`, `priority` | крестовина | запрос приоритета питания; применяется с задержкой (§10) |

Смена `target`/`side` считается финтом **только пока `strikeHeld == true`**: возврат стика в центр при отпускании RT финтом не
является.

Дополнительно, раз в тик, через `World`:

```cpp
struct World {
  float proximity[2];   // 0..1: насколько близко стена/здание позади бойца (§7 «близость стены»)
  float coolingMult[2]; // 1 = сухой воздух; вода/дождь поднимают охлаждение (§10)
};
```

## 4. Что читается на выходе

### Состояние (опрашивается каждый кадр)

`duel.fighter(Side::A)` даёт `Fighter` с публичным состоянием — для анимации, камеры и HUD:

- `phase` (`Idle / Windup / Strike / Contact / Recovery`), `phaseTicks`, `strike` (сторона, цель, рука, постановка стопы,
  `TicksToContact()`), `posture` (`Standing / Staggered / KnockedDown / Dodging / Clinched / ShutDown`).
- `pose[2]` — поза каждой руки после удара (§5.4); `guard` (поднят ли блок, сектор, `age`); `HardStanceActive()`.
- `res.stability`, `res.heat`, `res.energy`, `res.priority` (+ `res.pending`, `res.switchTicksLeft` для видимого потока энергии).
- `body.state(Zone)` (`Intact … Destroyed / Severed`), `body.layer(Zone, Layer)` (остаток брони/механизма/системы),
  `body.modifiers()` — готовые множители: скорость замаха, дальность, блок, шаг, поворот, уклонения, захват, таран,
  задержка захвата цели, слепые сектора, точность орудия (§9).
- `flank` — на сколько градусов противник сместился от «носа» бойца (для поворота корпуса и доступности реактора).
- `duel.distance()`, `duel.chain()` (открыто ли окно реверса и чьё), `duel.clinch()`, `duel.result()`.

### События (`EventLog`)

Каждое событие — простая структура `{tick, type, actor, zone, a, b, value}`. Это то, что Unreal превращает в звук, VFX,
тряску кабины и предупреждения. `actor` — боец, с которым это произошло (получил урон, поставил блок, был сбит) или кто
совершил действие (`WindupStarted`, `Whiff`, `StrikeContact`, `GrabHit`).

| Событие | Поля | Куда в Unreal |
|---|---|---|
| `WindupStarted` | `a` = `StrikeKind`, `b` = `SwingSide` | анимация замаха, звук привода |
| `Committed` | `a` = `StrikeKind`, `b` = `FootPlant` | точка невозврата (§5.2 п.4) |
| `CancelCheap` | `a`: 0 — отмена при удержании RT, 1 — слишком короткий замах, 2 — отмена после отпускания до фиксации | сброс анимации |
| `EmergencyBrake` | — | аварийное торможение: пар, скрежет |
| `Feint` | `a` = число финтов | отвод руки, нагрев |
| `Interrupted` | `a` = `Phase` | замах/удар сбит попаданием (§5.3) |
| `StrikeContact` | `a` = `StrikeKind`, `b` = `Outcome`, `zone`, `value` = сырой урон | точка удара |
| `Hit` | `zone`, `value` = нанесено | искры, вмятина, тряска кабины на стороне зоны |
| `Blocked` / `ParrySuccess` / `Evaded` / `InterceptSuccess` | `actor` = защитник; `Blocked.a == 1` — усиленная стойка | звук/VFX защиты |
| `Whiff` | `actor` = атакующий | промах, удар по зданию |
| `Dodge` | `a` = направление | гидравлический шаг |
| `ZoneState` | `zone`, `a` = новое, `b` = прежнее состояние | замена панелей, дым, искры, предупреждение HUD |
| `LimbSevered` | `zone` | отрыв конечности |
| `StaggerBegin` / `StaggerEnd` / `Knockdown` / `GotUp` | — | позы падения |
| `HeatWarning` / `CoolantLeak` / `Shutdown` | — | HUD, пар, отключение питания |
| `EnergyFlow` / `EnergyShift` | `EnergyFlow.a` = целевой `EnergyPriority`; `EnergyShift.a` = новый, `.b` = прежний | видимый поток энергии по меху (§10) |
| `ReverseChain` / `ReverseFailed` | `a` = шаг (1 или 2) | цепочка реверсов (§7) |
| `Clinch` / `ClinchResolved` / `WallSlam` | `value` = перевес / урон | клинч, прижатие к зданию |
| `HardStanceOn` / `HardStanceOff` | — | усиленная стойка |
| `GrabHit` | — | захват |
| `WeaponCharging` / `WeaponFired` / `WeaponInterrupted` | `WeaponCharging.a` = `WeaponKind`; `WeaponFired.a` = число попаданий (0 — промах; у ракет до 6), `.b` = `WeaponKind` | орудие (§13) |
| `PoseReturn` | `a` = `ArmPose` | рука возвращается в нейтральную позу (§5.4) |
| `MatchEnd` | `a` = `EndReason`, `actor` = проигравший, `b == 1` — ничья | конец боя |

После обработки списка событий: `duel.log().Clear()` (это же обнуляет хэш — для игры он не нужен).

## 5. Пример игрового цикла

Полный запускаемый вариант: `core/examples/game_loop.cpp` (собирается и запускается в `ctest`, поэтому не расходится с API).

```cpp
#include "iv/Ai.h"
using namespace iv;

Duel duel(/*seed*/ 42);                          // игрок = Side::A, бот = Side::B
Ai bot(Archetype::Counterpuncher, Difficulty::Normal, /*seed*/ 7);

void FixedTick60Hz(const Input& playerInput, const World& world) {   // вызывать ровно 60 раз в секунду
  const Input botInput = bot.Decide(MakeObservation(duel, Side::B)); // бот видит только Observation
  duel.Step(playerInput, botInput, world);
  for (const Event& e : duel.log().events()) Dispatch(e);            // звук / VFX / тряска / HUD
  duel.log().Clear();
  if (duel.result().over) ShowResult(duel.result().reason, duel.result().loser, duel.result().draw);
}
// Рендер: читает duel.fighter(Side::A/B) (phase, strike, pose, body.state(...), res.*) и рисует интерполированную позу.
```

Локальная дуэль в split-screen: оба `Input` приходят от игроков, `Ai` не создаётся.

## 6. ИИ и честность

`Ai::Decide(const Observation&)` — единственный вход ИИ. `Observation` (см. `iv/Ai.h`) содержит только то, что видит и слышит
человек: позу, фазу, видимый сектор замаха, звук заряда, направление и признаки перераспределения энергии, дистанцию,
видимые повреждения противника, свои приборы. В нём **нет** `Input` противника, цели удара до контакта, длительности
замаха, чисел стабильности/тепла/энергии противника (только видимые признаки: «шатается», «парит»).

- Задержка реакции: `max(12 тиков ≈ 200 мс, значение сложности)` — `Easy 20`, `Normal 15`, `Hard 12`.
  Информация о противнике берётся из наблюдения `reactionDelay()` тиков назад.
- Сложность меняет задержку реакции, глубину чтения привычек (`kAnalysisDepth`), качество позиционирования
  (`kPositionQuality`), точность тайминга парирования и частоту ответов на контратаки. Урон и параметры тела не меняются.
- Память привычек: счётчики «после блока / промаха / удара по ноге / при нестабильности противник делает X» и
  «после замаха стороной S он продолжает стороной T». Используются для выбора сектора блока и преследования.
- Тесты `Ai.*` доказывают: сигнатура `Decide` принимает только `Observation`; два мира, различающиеся только скрытой целью
  замаха, дают побитово одинаковые решения; первое действие в ответ на атаку не раньше задержки.

## 7. v2: орудия, ультимейт, внешние ракурсы, события презентации, AnimState, манекен

Игра — **только от первого лица**; внешний ракурс показывается как короткая вставка (`Cinematic`).

### Орудия и перезарядка

`Duel::SetLoadout(Side, WeaponKind)` (по умолчанию `RailSpear`). Профили — `tune::kWeapons[]` в `Tuning.h`:

| Орудие | Заряд | Урон | Перезарядка | Особенности |
|---|---|---|---|---|
| `RailSpear` | 1,8 с | 40 | 9 с | фиксация ног на время заряда (`Fighter::LegsLocked()`: нет шагов и уклонений), без боезапаса |
| `SuppressionRockets` | 0,7 с | 6 × 6 ракет | 7 с | боезапас 3 залпа (`WeaponEmpty`), каждая ракета попадает независимо, цели разбросаны по телу |
| `PlasmaCannon` | 1,3 с | 34 | 6 с | +38 тепла за выстрел — второй выстрел подряд грозит отключением |

Перезарядка (`Fighter::weaponCooldown`) идёт только в боевое время (не во время вставки); конец — событие `WeaponReady`.

### Ультимейт

Шкала `Fighter::ultimate` (0…`kUltimateMax`). Растёт: успешное парирование/перехват, попадание по зоне в состоянии `Critical` и хуже,
любое попадание, **в меньшей степени** — за полученный урон (потолок за удар `kUltGainTakenCap`). Событие `UltimateReady`, когда шкала полна.
Кнопка `Input::ultimate` при полной шкале: неблокируемый удар по `target` (`kUltimateDamage`), событие `UltimateUsed` + `CinematicBegin`.

### `Cinematic`

`Duel::cinematic()` (`active`, `kind`, `who`, `ticks`, `length`). События:
`CinematicBegin{actor, a = CinematicKind, b = длительность в тиках}` и `CinematicEnd`. Пока вставка идёт, **бой заморожен**: вводы игнорируются,
таймеры бойцов стоят (время матча идёт). Урон выстрела/ультимейта применяется в начале вставки. По `CinematicEnd`: цель оглушена (`kCinematicStunTicks`),
стрелок неуязвим `kCinematicProtectTicks`; проверка конца матча откладывается до `CinematicEnd`. Длительности — 1,75–3,5 с (`WeaponProfile::cinematicTicks`,
`kUltimateCinematicTicks`). Unreal на `CinematicBegin` включает внешнюю камеру/анимацию, на `CinematicEnd` возвращает кабину.

### События для презентации

| Событие | Поля |
|---|---|
| `HitEvent` | `actor` = атакующий, `zone`; `DecodeHit(event, &HitInfo)` даёт `layer` (глубина слоя), `severity` (`ZoneState` после), `direction` (`SwingSide`), `damage`, `stabilityDamage`, `wasBlocked`, `wasParried` (при парировании — `damage = 0`) |
| `ArmorPlateLost` | `zone`, `a` = индекс пластины (с 0), `b` = число пластин зоны (`kArmorPlates`) |
| `ReactorBreach` | реактор впервые `Damaged` — синее свечение, охлаждающая жидкость в кабине |
| `SystemFailure` | `a` = `SystemId` (`Sensors, Power, Cooling, ArmL/R, LegL/R, Weapon`): зона стала `Critical`, течь охлаждения, отключение питания |
| `StaggerBegin` / `StaggerEnd` / `Knockdown` / `Clinch` / `ParrySuccess` / `InterceptSuccess` / `ReverseChain{step}` / `EnergyShift{from,to}` / `HeatWarning` / `LimbSevered{zone}` | см. таблицу выше |
| `UltimateReady` / `UltimateUsed` / `CinematicBegin` / `CinematicEnd` / `WeaponReady` / `WeaponEmpty` | см. выше |

`Event` теперь имеет ещё `c` (int) и `value2` (float); оба входят в хэш детерминизма.

### `AnimState`

`AnimState a = MakeAnimState(duel.fighter(Side::A));` каждый кадр: `phase`, `progress` 0–1 внутри фазы (замах — до точки фиксации, затем задержка фиксации; удар — путь руки;
восстановление — возврат), `committed`, `kind/side/arm/target`, `charge`, `pose[2]` (`ArmPose`), `footPlant`, `weightShift` (−1 назад … +1 вперёд),
`lateralShift` (уклонение/поворот), `legsLocked`, `posture` и `postureProgress`, поднятый блок, усиленная стойка, заряд/перезарядка орудия, нормированные стабильность/тепло/шкала ультимейта.

### `DummyMode` (обучение)

`Duel::SetDummy(Side, DummyMode)`: `Passive` — не действует; `Scripted` — повторяет сценарий атак (`Dummy::SetScript`; по умолчанию 5 ударов: вверх, вправо, быстрый, влево, вниз);
`BlockOnly` — только поднимает блок на видимый сектор замаха игрока после человеческой задержки (`kDummyReactionTicks`) и сам не атакует.
Манекен не проигрывает: при условии конца боя он «чинится» и урок продолжается. Ввод, поданный в `Step` за сторону манекена, игнорируется.

## 7a. v4: абордаж (TASK-017, STATUS §6B)

Одна кнопка: пилот вылезает из кабины, стреляет крюком в плечо врага, садится у люка рядом со стыком плеча и руки, взламывает люк мини-игрой на время
(`HackGame`), бросает гранату и улетает; граната взрывает эту часть меха. Враг может «прихлопнуть» пилота рукой по плечу — надо вовремя перелететь на другое плечо.
Всё — правила и тайминги: Unreal проигрывает анимации по событиям. Сторона симметрична (`Side::A`/`Side::B`); ИИ абордаж пока **запрещён** (`tune::kAiBoardingEnabled = false`,
`BoardingConfig::ownerIsAi` → отказ `AiDisabled`).

### Подключение (3 строки в игровой цикл)

```cpp
iv::Boarding boarding(cfg);                        // BoardingConfig{owner, enemyArchetype, enemyDifficulty, seed, swatChanceMult}
// каждый тик 1/60 с:
Input a = boarding.Filter(duel, playerInput);      // ДО Duel::Step: пока пилот снаружи, вместо ввода игрока — защитный автопилот
duel.Step(a, b, world);
boarding.Step(duel, boardingInput);                // ПОСЛЕ Duel::Step: BoardingInput{start, swing, shoulder, hack}
```

`BoardingInput`: `start` (ребро, кнопка абордажа), `swing` (ребро, «перелететь на другое плечо»), `shoulder` (желаемый бок люка), `hack` (`HackInput`, пробрасывается в мини-игру).
Пока `Boarding::Active()`, у `Fighter` игрока включён `autopilot`: `Duel::Step` отбрасывает **любые** атакующие вводы (`strikeHeld, quick, toGrab, switchArm, reverse, weaponHeld, ultimate`),
`Boarding::Filter` подставляет блок/уклонение от оборонительного `Ai` (Counterpuncher/Easy: слабее живого игрока), а мех получает больше урона (`kAutopilotDamageMult`).
Во время внешней вставки (`Duel::cinematic().active`) абордаж **заморожен** вместе с боем.

### Состояния (`BoardPhase`) и переходы

```
Idle ──start──▶ ClimbOut ▶ OnShoulder ▶ HookLaunch ▶ HookFlight ▶ Landing ▶ Hacking ──Success──▶ GrenadeThrow ▶ Escape ▶ WatchBlast ▶ ClimbIn ▶ Done
                                                          │  ▲          │  ▲       │                                          (взрыв в WatchBlast)
                                          swat (посл. 30 %) │  │          │  │       ├──Fail / Timeout / «назад» ──▶ ReturnHook ▶ ClimbIn ▶ Done
                                                          ▼  │          ▼  │       │
                                                          HookSwing ◀────┴──┴───────┘ (swing в окне, прогресс × kSwingKeepProgress)
 swat без нажатия в окне ──▶ Smashed ──▶ MatchEnd{PilotLost}
```

| Фаза | Длительность (`Tuning.h`) | Что играть |
|---|---|---|
| `ClimbOut` | `kBoardClimbOutTicks` 2,2 с | пилот вылезает из люка сбоку, камера внешняя |
| `OnShoulder` | `kBoardOnShoulderTicks` 0,7 с | встаёт на плечо своего меха |
| `HookLaunch` | `kBoardHookLaunchTicks` 0,6 с | выстрел крюка-кошки из наручного гарпуна (`HookFired`) |
| `HookFlight` | `kBoardHookFlightTicks` 1,4 с | полёт к плечу врага; **последние 30 %** — враг уже может замахнуться |
| `Landing` | `kBoardLandingTicks` 0,8 с | посадка у люка (`HookLanded`); `kSwatGraceTicks` 1,5 с после посадки замахов нет |
| `Hacking` | открытая (лимит у `HackGame`, 25–60 с) | мини-игра на весь экран (`HackStarted`, `HackProgress`, `HackResultEvt`) |
| `GrenadeThrow` | 1,1 с | бросок гранаты в люк (`GrenadeThrown`) |
| `Escape` | 1,5 с | пилот взлетает на крюке прочь |
| `WatchBlast` | 2,2 с, взрыв через `kBoardBlastDelayTicks` 0,9 с | камера смотрит на врага; в момент взрыва `Duel::ExternalHit(source = 3)` + `BoardingBlast` |
| `ReturnHook` | 1,5 с | провал/таймаут/отступление: назад по крюку |
| `ClimbIn` | 1,8 с | посадка в свой мех, управление возвращается |
| `HookSwing` | `kBoardHookSwingTicks` 0,9 с | перелёт на другое плечо (значение добавлено в конец enum) |
| `Smashed` | — | пилот раздавлен: `BoardingSmashed`, `MatchEnd{PilotLost}`; конец матча |
| `Done` | — | заход завершён (`BoardingEnded.a = BoardingOutcome`), кулдаун `kBoardCooldownTicks` 60 с (75 с после неудачи) |

Старт отказывается кодом `BoardingDenied` (событие `BoardingDenied.a`, поле `Boarding::lastDenied()`): `AlreadyActive, MatchOver, Clinch, Busy` (идёт замах/удар/заряд орудия/ультимейт), `Stunned`, `Cinematic`,
`Cooldown`, `NoEnergy` (< `kBoardEnergyCost` 25), `NoStability` (< `kBoardMinStability` 35), `NoTarget` (оба плеча врага `Destroyed`), `AiDisabled`.
Если выбранное плечо уничтожено — люк на противоположном; если плечо уничтожают во время захода, пилот перелетает на другое (при потере обоих — `ReturnHook`).

### Помеха: «замах по плечу» (swat)

Враг (ИИ) в `HookFlight` (последние 30 %), `Landing` (после `kSwatGraceTicks`) и `Hacking` раз в `kSwatCheckTicks` (0,5 с) решает замахнуться: шанс `kSwatChance[сложность] × kSwatArchetypeMult[архетип] × swatChanceMult`,
не чаще `kSwatCooldownTicks`, не более `kMaxSwatsPerBoarding` (2) за заход; бьёт **противоположной** рукой — нет руки (`Destroyed/Severed`), нет замаха по этому плечу.
Телеграф: `BoardingSwatTelegraph{a = плечо (0 L / 1 R), b = тиков до удара}` — на экране «камера врага» в углу. Телеграф `kSwatWindupTicks`: Easy 1,2 с, Normal 0,9 с, Hard 0,65 с.

| Момент нажатия `swing` (до удара) | Результат |
|---|---|
| первые `kSwatReadyTicks` (0,2 с) после телеграфа | игнорируется (замах ещё не виден) |
| дальше окна: больше `kSwingWindowTicks` (0,7 с) | **рано**: пилот перелетает, но враг «подстраивается» один раз (`BoardingSwatAdjusted`, новый телеграф на новом плече); повторное раннее нажатие игнорируется |
| `[kSwingMinTicks … kSwingWindowTicks]` (0,15…0,7 с) | **успех**: `BoardingSwingOk`, `HookSwing` 0,9 с, прогресс взлома `× kSwingKeepProgress` (0,5), `HackGame::Reroll`; удар приходит на пустое плечо (`BoardingSwatImpact.a = 0`) |
| позже `kSwingMinTicks` | **поздно**: игнорируется → `BoardingSwatImpact.a = 1` → `Smashed` |
| успех, но второго плеча нет | та же кнопка = **отступление** по крюку (`ReturnHook`, взлом провален, пилот жив) |

Смерть при нажатии внутри окна невозможна (проверяет тест и `ivsim --boarding`).

### События (добавлены в конец `EventType`, порядок прежних — контракт)

| Событие | Поля |
|---|---|
| `BoardingStarted` | `a` = плечо (0 L / 1 R) |
| `BoardingPhase` | `a` = `BoardPhase`, `b` = длительность в тиках (0 — открытая) |
| `BoardingDenied` | `a` = `BoardingDenied` |
| `HookFired` / `HookLanded` | `a` = плечо |
| `HackStarted` | `a` = сложность 1..10, `b` = лимит в тиках |
| `HackProgress` | `value` = прогресс 0..1 (при изменении ≥ 5 %) |
| `HackResultEvt` | `a` = `HackState` (Success/Fail/Timeout), `value` = quality 0..1 |
| `BoardingSwatTelegraph` | `a` = плечо, `b` = тиков до удара, `value` = номер замаха |
| `BoardingSwingOk` | `a` = новое плечо, `value` = сохранённый прогресс |
| `BoardingSwatAdjusted` | `a` = новое плечо, `b` = тиков до удара |
| `BoardingSwatImpact` | `a` = 1 пилот на плече (раздавлен) / 0 промах, `b` = плечо |
| `BoardingShock` | удар по пустому меху: `value` = потерянное время взлома (`kBoardShockSeconds` 0,8 с, не более `kBoardMaxShocks` раз) |
| `BoardingSmashed` | пилот раздавлен (затем `MatchEnd` с `EndReason::PilotLost`) |
| `GrenadeThrown` | — |
| `BoardingBlast` | `zone` = поражённая зона (плечо; если оно уничтожено — рука), `value` = нанесено |
| `BoardingEnded` | `a` = `BoardingOutcome` (`Success, HackFailed, HackTimeout, Smashed, Aborted`) |

Граната: `Duel::ExternalHit(..., source = kGrenadeSource = 3, StatusKind::Burn, kGrenadeBurnTicks)`; урон `kGrenadeDamageMin…kGrenadeDamageMax` (27…38 ≈ 1,5…2,2 тяжёлых удара) по `quality` взлома.
`ExternalHit.a`: 0 обломок, 1 удар о здание, 2 падение, **3 граната**.

### Изменения в остальном ядре (контракт)
- `EndReason::PilotLost` добавлен в конец; `Name(EndReason)` знает его.
- `Duel::ForceEnd(loser, reason)` — завершить матч снаружи (используется абордажем).
- `Fighter::autopilot` / `set_autopilot()`; `Fighter::TakeHit` умножает урон на `kAutopilotDamageMult` (1,4) только при `autopilot`.
- `HackGame` (`iv/HackGame.h`) — мини-игра взлома из трёх слоёв (TASK-018): путь по сетке, ритм, подбор частоты; интерфейс `Start, Step, Reroll, AddPenalty, state, progress, mistakes, ticksLeft, quality, PerfectInput, DifficultyFor` + доступ к раскладкам для экрана; данные — `data/hack/`, спецификация экрана — `docs/ux/hack_minigame.md`, калибровка — `docs/ux/hack_calibration.md`.
- `Boarding::Hash()` — хэш состояния для теста детерминизма (равный сид и ввод → равные хэш истории событий и хэш абордажа).
- Баланс — `docs/BOARDING_BALANCE.md` (`ivsim --boarding`).

## 8. Подключение в Unreal (план для локальной стороны)

1. Положить `core/include/iv` и `core/src` в модуль проекта (ядро не использует исключения и RTTI — как и UE по умолчанию).
2. Обернуть `Duel` в `UActorComponent` с аккумулятором фиксированного шага; `Input` собирать из Enhanced Input.
3. `Event` → `UFUNCTION(BlueprintImplementableEvent)` или делегаты. Перечисления зеркалятся в `UENUM` один к одному (задача G-2
   плана): порядок значений — контракт, менять только с записью в PR.
4. Данные (таблицы атак, зоны, ИИ) на стороне Unreal брать из `data/` (TASK-006); числа боя живут в `Tuning.h` и при необходимости
   выносятся в `UDataAsset` без изменения логики.

## 9. Контракты и ограничения

- Порядок значений в `Types.h` и `EventType` — часть контракта с Unreal-стороной.
- Арифметика `float`. Побитовая воспроизводимость гарантируется на одной сборке (один компилятор и флаги); между разными
  компиляторами/платформами итоговые числа могут отличаться в последних разрядах. Для кросс-платформенных реплеев нужен
  fixed-point — вне объёма этой задачи.
- Дистанция одномерная (`Duel::distance`), «угол корпуса» — число `flank`. Ядро не знает геометрии города: близость стены
  приходит снаружи через `World::proximity`.
- Захват, клинч и орудие — упрощённые модели (см. §5.4, §7, §12, §13 питча): без отдельной анимации борьбы и без баллистики снаряда.
- Числа баланса — стартовые, подобраны headless-симуляцией (`docs/BALANCE_REPORT.md`), а не игровыми тестами. Финальную
  настройку делать в Combat Lab, меняя только `Tuning.h` и таблицу стилей в `Ai.cpp`.
