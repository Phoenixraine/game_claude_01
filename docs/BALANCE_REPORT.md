# BALANCE_REPORT — headless-баланс ядра `ivcore`

Источник чисел — `ivsim` (ИИ против ИИ, все пары 6×6 архетипов × 3 сложности × сиды). Цифры ниже **получены реальным запуском**
(`python3 core/tools/balance_report.py`, раздел между маркерами `SIM`), не выдуманы. Цели из TASK-001: средняя длительность боя
**8–12 игровых минут**, ни один архетип не выигрывает **> 65 %** у остальных, различные причины конца боя, отрыв рук, доли зон, доля парирований/перехватов.

## Что менялось (история тюнинга)

1. **Базовые правки логики** (до тюнинга чисел): конец боя «реактор» почти не случался и 100 % ничьих между пассивными архетипами →
   гистерезис движения, дистанция предпочтения внутри досягаемости, Gunner не отступает при тесноте; реактор стал уязвим только
   сзади (угол корпуса, обход при уклонении), торс крепче, реактор слабее; ИИ отвечает на замах захвата и защищается от орудия
   (рывок/уклонение), контратака после парирования.
2. **Автотюнер** (`hill-climb` по таблице стилей `kStyles` в `Ai.cpp` и по ключевым константам `Tuning.h`: урон тяжёлого удара, урон орудия,
   стабильность захвата, штраф парирования, урон по руке при перехвате, коэффициент стабильности от попаданий, регенерация стабильности).
   Функция потерь: отклонение винрейта от 50 % за пределами ±7 п.п. (сильнее выше 62 %), длительность вне 9–11 мин, ничьи по времени,
   разнообразие причин конца боя. Этап 1 — 300 итераций, этап 2 — ещё 300 (другая база сидов, чтобы не переобучиться); результат —
   `kHeavyDamage` 10,5 → 13,1; `kGrabStability` 32 → 35,2; `kInterceptArmDamage` 0,35 → 0,44; окна реверса `kReverseWindowTicks` = {6, 5} тиков (100 / 83 мс —
   внутри диапазона питча 70–110 мс; тест `Defense.WindowsStayInsideThePitchRangesInMilliseconds`).
3. **v2** (орудия с большой перезарядкой, шкала ультимейта, внешние вставки) заметно меняют темп боя: первая версия ультимейта
   (урон 68, прирост 14 за парирование) укорачивала бой до 4–6 минут и давала 5 ультимейтов за дуэль. Прирост снижен
   (парирование 6, перехват 8, попадание 0,45, по критической зоне +1,5; получение урона — 0,02/ед. с потолком 0,3), урон ультимейта 42.
   Затем тюнинг продолжен автоматически с этими константами среди параметров (см. текущий статус ниже).

## Текущий статус

Автотюнер v2 запущен; ниже — числа на момент открытия PR (до его завершения). См. обновление в этом разделе после слияния настроек.

## Результаты запуска

<!-- SIM -->
(ivsim --seeds 40 --seed-base 50000: 1440 дуэлей на сложность = 6 × 6 архетипов × 40 сидов)

### Easy (1440 duels)

Match length, game minutes: mean 11.50, median 10.64, p10 7.12, p90 17.64; time-limit draws: 100 (6.9%)

| Archetype | Games | Wins | Losses | Draws | Win rate vs other archetypes |
|---|---|---|---|---|---|
| Counterpuncher | 400 | 94 | 288 | 18 | 23.5% |
| Breaker | 400 | 241 | 159 | 0 | 60.2% |
| LimbHunter | 400 | 235 | 148 | 17 | 58.8% |
| Trickster | 400 | 214 | 176 | 10 | 53.5% |
| Gunner | 400 | 127 | 266 | 7 | 31.8% |
| Grappler | 400 | 263 | 137 | 0 | 65.8% |

End reasons: ReactorDestroyed 3.5%, CockpitCritical 86.9%, TotalImmobility 0.0%, PowerLoss 0.0%, ArmsLostImmobilised 2.6%, TimeLimit 6.9%

Severed limbs: 1379 in 863 duels (59.9% of duels, 0.96 per duel)

Strike contacts by aimed zone: Head 8.0%, Torso 34.7%, Reactor 5.4%, ShoulderL 9.5%, ShoulderR 9.4%, ArmL 10.9%, ArmR 11.1%, LegL 5.5%, LegR 5.5%

Contact outcomes: Hit 49.3%, Blocked 27.6%, Parried 5.1%, Evaded 1.7%, Intercepted 1.3%, Whiff 7.6%, HardStanceBlocked 2.7%, Grabbed 4.8%, GrabParried 0.0%

Defences (block, hard stance, parry, dodge, intercept, grab parry): 229562 of 597749 contacts. Parry share of defences 13.4%, intercept share 3.4%, dodge share 4.5%, plain block share 78.7%.

Per duel: heavy 188.2, quick 204.6, grabs 30.2, feints 8.4, clinches 0.04, reverse replies 0.49, staggers 31.7, knockdowns 0.15; weapon shots 5.93 (9% hit)

v2 per duel: ultimates 2.71, cinematic cuts 8.64, armour plates lost 66.3, HitEvents 494.3

### Normal (1440 duels)

Match length, game minutes: mean 9.88, median 9.40, p10 5.76, p90 14.56; time-limit draws: 23 (1.6%)

| Archetype | Games | Wins | Losses | Draws | Win rate vs other archetypes |
|---|---|---|---|---|---|
| Counterpuncher | 400 | 237 | 163 | 0 | 59.2% |
| Breaker | 400 | 131 | 269 | 0 | 32.8% |
| LimbHunter | 400 | 168 | 227 | 5 | 42.0% |
| Trickster | 400 | 210 | 185 | 5 | 52.5% |
| Gunner | 400 | 301 | 99 | 0 | 75.2% |
| Grappler | 400 | 148 | 252 | 0 | 37.0% |

End reasons: ReactorDestroyed 21.3%, CockpitCritical 76.6%, TotalImmobility 0.0%, PowerLoss 0.0%, ArmsLostImmobilised 0.5%, TimeLimit 1.6%

Severed limbs: 644 in 381 duels (26.5% of duels, 0.45 per duel)

Strike contacts by aimed zone: Head 6.8%, Torso 36.4%, Reactor 10.5%, ShoulderL 8.4%, ShoulderR 8.3%, ArmL 9.8%, ArmR 10.0%, LegL 4.9%, LegR 4.9%

Contact outcomes: Hit 53.4%, Blocked 23.4%, Parried 5.2%, Evaded 2.4%, Intercepted 4.6%, Whiff 3.8%, HardStanceBlocked 3.3%, Grabbed 3.9%, GrabParried 0.0%

Defences (block, hard stance, parry, dodge, intercept, grab parry): 217118 of 557427 contacts. Parry share of defences 13.5%, intercept share 11.8%, dodge share 6.1%, plain block share 68.7%.

Per duel: heavy 158.1, quick 218.4, grabs 24.7, feints 7.3, clinches 1.62, reverse replies 6.25, staggers 29.9, knockdowns 0.30; weapon shots 4.78 (16% hit)

v2 per duel: ultimates 3.58, cinematic cuts 8.36, armour plates lost 61.8, HitEvents 458.0

### Hard (1440 duels)

Match length, game minutes: mean 6.95, median 6.89, p10 3.51, p90 10.32; time-limit draws: 0 (0.0%)

| Archetype | Games | Wins | Losses | Draws | Win rate vs other archetypes |
|---|---|---|---|---|---|
| Counterpuncher | 400 | 297 | 103 | 0 | 74.2% |
| Breaker | 400 | 113 | 287 | 0 | 28.2% |
| LimbHunter | 400 | 62 | 338 | 0 | 15.5% |
| Trickster | 400 | 261 | 139 | 0 | 65.2% |
| Gunner | 400 | 366 | 34 | 0 | 91.5% |
| Grappler | 400 | 101 | 299 | 0 | 25.2% |

End reasons: ReactorDestroyed 39.7%, CockpitCritical 60.3%, TotalImmobility 0.0%, PowerLoss 0.0%, ArmsLostImmobilised 0.1%, TimeLimit 0.0%

Severed limbs: 222 in 133 duels (9.2% of duels, 0.15 per duel)

Strike contacts by aimed zone: Head 5.9%, Torso 37.0%, Reactor 17.3%, ShoulderL 7.2%, ShoulderR 7.2%, ArmL 8.4%, ArmR 8.6%, LegL 4.2%, LegR 4.2%

Contact outcomes: Hit 57.6%, Blocked 19.2%, Parried 6.3%, Evaded 2.4%, Intercepted 6.7%, Whiff 1.2%, HardStanceBlocked 3.1%, Grabbed 3.5%, GrabParried 0.0%

Defences (block, hard stance, parry, dodge, intercept, grab parry): 163614 of 434618 contacts. Parry share of defences 16.6%, intercept share 17.7%, dodge share 6.3%, plain block share 59.4%.

Per duel: heavy 108.2, quick 188.5, grabs 12.3, feints 5.0, clinches 4.01, reverse replies 11.72, staggers 28.2, knockdowns 0.46; weapon shots 3.09 (25% hit)

v2 per duel: ultimates 3.30, cinematic cuts 6.39, armour plates lost 51.1, HitEvents 353.1

<!-- /SIM -->

## Как воспроизвести

```
cmake -S core -B build && cmake --build build
python3 core/tools/balance_report.py --seeds 40 --seed-base 50000   # обновляет раздел «Результаты запуска»
./build/ivsim --seeds 20 --quiet --duels duels.csv --markdown summary.md
```

Симулятор детерминирован: один набор сидов даёт те же числа (`ivsim` дважды + `cmp` в CI).
