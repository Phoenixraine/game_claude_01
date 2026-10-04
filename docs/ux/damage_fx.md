# Реакции на повреждения — как игра использует таблицы (`data/damage_fx/`)

Источник данных — `data/damage_fx/*.json` (генерируются `build_tables.py`), эталон математики — `data/damage_fx/fxmath.py`. Порт в Unreal должен давать те же числа (сверка: `fxmath.plan_for_event` на тех же событиях).

## 1. Последовательность «событие → эффекты»
```
событие ядра (EventType + поля)
   └─ decode_event            : слой (Armor/Mechanism/System), состояние зоны, блок/парирование, замах, источник ExternalHit
   └─ severity_score → S0…S4  : только для HitEvent / ExternalHit / ReactorBreach / … (см. coverage.json)
        ├─ shake_for_event    → кривые pos_cm[3], rot_deg[3], chroma (120 Гц)  ──► mix_shakes (лимит суммы) ──► камера
        ├─ plan_cockpit_effects → [{t, target, action, duration_s, params}]  ──► Blueprint-команды кабины (имена из TASK-020)
        ├─ plan_chunks        → [{pos, vel, spin, mass, life, fire, smoke, ground_sparks}] ──► AIVDebrisChunk
        └─ warnings_for_event → [id] ──► очередь предупреждений (активно одно: min priority) ──► HUD/сирена/голос
```
Для столкновения с домом: `plan_building_break(kind, energy_kJ, normal, building_params, seed)` → спавны осколков по стадиям + «пуфы» дыма + кривая пыли + звуки.

## 2. Тяжесть S0–S4
`score = (damage / 17.5) × layer × zone × (0.45 блок | 0.1 парирование) × источник(ExternalHit) + bump(состояние зоны) + min(0.3, stability_damage × 0.005)`

| | значения |
|---|---|
| layer | Armor 1.0 · Mechanism 1.35 · System 1.8 |
| zone | Head 1.25 · Torso 1.2 · Reactor 1.5 · Shoulder 1.0 · Arm 0.8 · Leg 0.7 |
| bump | Intact/Dented 0 · Exposed 0.1 · Damaged 0.4 · Critical 0.8 · Destroyed 1.2 · Severed 1.5 |
| пороги S1 / S2 / S3 / S4 | > 0.35 / > 0.9 / > 1.6 / > 2.6 |
| источник ExternalHit | 0 бросок 1.0 · 1 врезание в здание 1.5 · 2 падение 1.3 · 3 граната 1.4 |

`BoardingSwatImpact` всегда S4. Множитель амплитуды тряски по тяжести: S0 0.12 · S1 0.4 · S2 1.0 · S3 1.7 · S4 2.6.

## 3. Тряска
* Компоненты: `damped_sine` (удар), `impulse` (мягкий щелчок), `noise` (сглаженный шум); у каждой — частота, амплитуда (см и градусы), затухание, атака, длительность, оси (вправо/вверх/вперёд), хромата стекла.
* Направление: `impact` = вектор зоны (`zone_direction`) + замах (`swing_direction`); иначе именованное (`forward/back/down/up/lateral/none` → шум по всем осям).
* **Лимиты** (проверены тестом по всем событиям × S0–S4 × 9 зонам): |смещение| ≤ 12 см, |поворот| ≤ 4°, > 3.5 Гц не дольше 0.3 с, к концу кривая = 0. Сумма одновременных тряск тоже ограничивается (`mix_shakes`).
* Доступность «уменьшить тряску»: множитель 0.25 (`shake_reduce_motion` или параметр `reduce_motion`).

## 4. Кабина
Команды берутся из `cockpit_effects.json → severity.Sx` (цель, действие, вероятность, диапазон числа, задержка, длительность, параметры). Выбор экземпляров детерминирован сидом и учитывает `state` (что уже сломано — второй раз не ломается).
Идентификаторы и **минимальное** число экземпляров (контракт для TASK-020 — кабина должна содержать не меньше):

`Pipe_Burst_00..11`, `SteamPort_00..11`, `LeakPoint_00..11`, `Wire_Snapped_00..23`, `SparkPort_00..23`, `Mon_00..11`, `Lamp_Warn_00..19`, `Lamp_Ok_00..19`, `AlarmBeacon_00..03`, `StrobePanel_00..03`, `Fire_Socket_00..07`, `Scorch_Decal_00..05`, `Glass_Crack_Mask_00..03`, `Btn_00..79`, `Dial_00..11`; синглтоны `Glass_Front`, `Cockpit_Root`, `Camera_Rig`.

| S | что происходит (кратко) |
|---|---|
| S0 | возможное мигание лампы / лёгкий выброс пара |
| S1 | 1–2 выброса пара, предупредительная лампа, глитч монитора, пыль с потолка |
| S2 | лопается труба, рвутся 1–2 провода (искры), 3–5 ламп, маяк, глитч, шанс трещины на стекле; сирена + голос |
| S3 | 2–4 трубы, 3–5 проводов, возгорание, подпалина, 1–2 монитора гаснут, много ламп, 2–3 маяка + строб, трещины |
| S4 | 5–8 труб, 6–10 проводов, 2–3 очага огня, 4–6 мониторов, до 20 ламп, мерцание питания, дым |

* **Огонь:** `plan_fire_spread(state, seed, horizon_s, last_severity)` — распространение по графу `Fire_Socket`, не более 4 очагов одновременно, горит 12–25 с, шанс перекинуться на соседний сокет 0.12/с; если последний удар слабее S3 (`extinguish_below`) — огнетушитель гасит очаг через 6–9 с (см. `cockpit_effects.json → fire`).
* **Красный свет:** `red_light_curve(severity)` — пульсация, пик и затухание (S4: пик 1.0, ≈ 10 с; S0 — нет).
* Сирена и голос — по тяжести: S2 `fx_alarm_beep` + `vo_hull_damage` (через 0.6 с), S3 `fx_siren` 6 с + `vo_hull_damage` (0.4 с), S4 `fx_siren` 12 с + `vo_hull_critical` (0.3 с); у S0–S1 их нет.

## 5. Куски меха
Строки `mech_chunks.json → zones[зона][слой]`: тип (`armor_plate`, `armor_plate_burning`, `piston`, `hose`, `cable_bundle`, `reactor_fragment`, `sensor_housing`, `debris_small`), число, масса, скорость, вращение, время жизни, вероятность гореть, огонь/дым (с), искры при ударе о землю. Правила привязки (`event_rules`): `ArmorPlateLost`, `HitEvent` (≥ Mechanism и ≥ S2), `LimbSevered` (+ крупный обломок конечности), `ReactorBreach`, `UltimateFinisher/Sever`, `ExternalHit`, `BoardingBlast`.
Баллистика: g = 9.81, сопротивление 0.04/с, скорость × (0.6…1.3 по S), дальность жёстко ≤ 120 м (`plan_chunks` подрезает скорость), направление — по нормали зоны с конусом 38° и подъёмом ≥ 6 м/с.

## 6. Здания
Сценарии: `sword_hit`, `mech_crash`, `thrown_debris`, `plasma`, `rockets`. Стадии: `contact → facade_crush → floor_collapse → dust_cloud`. Число осколков масштабируется энергией (`e^0.8`, 0.35…2.2×), материалом (`concrete`, `glass_curtain`, `brick`, `steel_frame`), числом этажей и долей стекла, затем **жёстко режется до бюджета**: ≤ 400 крупных, ≤ 6000 мелких, ≤ 80 дымовых пуфов. Классы осколков — контракт для TASK-016 (`Shard_Concrete_S/M/L/XL`, `Slab_Concrete`, `Column_Broken`, `Panel_Facade_Torn`, `Girder_Twisted`, `Steel_Plate_Bent`, `AC_Unit_Broken`, `Sign_Torn`, `Glass_Shard`, `Gravel_Cluster`, `Pebble`, `Rebar_Single/Bundle`, `Pipe_Broken`, `Cable_Dangling`, `Window_Frame_Broken`). Пыль: цвет и кривая плотности по материалу.

## 7. Предупреждения
16 записей `warnings.json` (приоритет 1 — выше всего): `reactor_breach`, `hull_critical`, `power_loss`, `hook_alert` (1) · `arm_lost`, `leg_lost`, `sensors_failed` (2) · `system_failure`, `overheat`, `coolant_leak`, `fire_in_cockpit` (3) · `burning`, `blinded`, `strike_lock` (4) · `ultimate_ready`, `weapon_ready` (5). У каждого: триггер, цвет (`red #ff4a3d`, `orange #ff9a2e`, `amber #ffd24a`, `cyan #7fe4ff`, `white #e8fbff`), ритм `[вкл мс, выкл мс]`, звук, иконка (id для TASK-021), голос. Сирену и голос ведёт одно предупреждение с наивысшим приоритетом (`active_warning`). `fire_in_cockpit` — производный триггер `cockpit_fire`, его выдаёт слой кабины, не ядро.

## 8. «Кнопки сочности» (`global_tuning.json`)
| ключ | по умолч. | диапазон | что |
|---|---|---|---|
| `shake` | 1.0 | 0…2 | амплитуда тряски (лимиты 12 см / 4° остаются) |
| `shake_reduce_motion` | false | — | доступность, ×0.25 |
| `cockpit_effects_count` | 1.0 | 0.25…2 | число ломающихся труб/проводов/мониторов |
| `cockpit_fire` | 1.0 | 0…2 | число и скорость пожаров |
| `chunks_count` / `chunks_speed` | 1.0 | 0.25…2 / 0.5…1.5 | куски меха |
| `building_shards` / `building_dust` | 1.0 | 0.25…1.5 / 0.25…2 | осколки и пыль (бюджеты не превышаются) |
| `red_light` | 1.0 | 0…1.5 | красная подсветка |
| `siren_volume` | 1.0 | 0…1 | громкость сирены |

## 9. Что надо сделать в Unreal (владельцу)
1. Загрузить JSON (либо прочитать их в `UDataAsset`); применить `mix_shakes` — суммарный лимит обязателен.
2. Сверить якоря зон (`ZONE_ANCHOR`) с реальными сокетами меха и высоту (85 м принята оценочно).
3. Убедиться, что в кабине есть не меньше экземпляров каждого класса, чем в `identifiers.json → cockpit`.
4. Подогнать амплитуды и плотности частиц в игре; таблицы подстраиваются через `build_tables.py` + `global_tuning.json`.
