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
