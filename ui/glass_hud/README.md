# Стеклянный HUD — `ui/glass_hud/` (TASK-021)

HUD «на стекле» кабины: тонкие светящиеся линии без плашек и без читаемого текста (только цифры и «%» сегментным начертанием). Источник правды — код (`lib/`), всё остальное генерируется и воспроизводится.
Цветовой код — питч §21: нейтральный = цел, жёлтый = открыта броня, оранжевый = повреждён механизм, красный = критично, серый пунктир (чёрный на бумаге питча) = потеряно. Hex-значения совпадают с `data/damage_fx/warnings.json`.
Игровая часть HUD (`IVHUD.cpp`, Canvas) осталась прежней: здесь — графика AR-стекла и данные раскладки/реакций, интеграция в Unreal — локально.

## Запуск
```
pip install cairosvg pillow numpy matplotlib            # matplotlib нужен только для схемы раскладки
python3 ui/glass_hud/build_hud.py                       # всё: json, svg, png, маски, превью (≈ 25 с)
python3 ui/glass_hud/build_hud.py --out /tmp/hud --no-previews
python3 -m unittest discover -s ui/glass_hud/tests      # 38 тестов
```
Детерминизм: фиксированные сиды, тест пересобирает все SVG и сверяет побайтно; `assets_manifest.json` хранит размеры и хэши всех файлов.

## Раскладка (16:9, нормированные доли кадра; центр свободен)
| Элемент | Привязка | Файл | Прямоугольник x, y, w, h | Постоянный |
|---|---|---|---|---|
| `body_player` | top_left | `svg/silhouette_body_player.svg` | 0.020, 0.030, 0.135, 0.330 | да |
| `layers_player` | top_left | `svg/zone_layers_arcs.svg` | 0.020, 0.030, 0.135, 0.330 | да |
| `body_enemy` | top_right | `svg/silhouette_body_enemy.svg` | 0.845, 0.030, 0.135, 0.330 | да |
| `layers_enemy` | top_right | `svg/zone_layers_arcs_enemy.svg` | 0.845, 0.030, 0.135, 0.330 | да |
| `enemy_status` | top_right | `svg/status_icons_row.svg` | 0.845, 0.375, 0.135, 0.050 | по событию |
| `enemy_stability` | top_right | `svg/stability_bar_h.svg` | 0.845, 0.435, 0.135, 0.028 | по событию |
| `compass` | top_center | `svg/compass_strip.svg` | 0.350, 0.020, 0.300, 0.040 | да |
| `weapons` | bottom_left | `svg/weapon_icons_row.svg` | 0.020, 0.745, 0.150, 0.055 | да |
| `gauge_armor` | bottom_left | `png/bar_armor.png` | 0.020, 0.835, 0.060, 0.107 | да |
| `gauge_stability` | bottom_left | `png/bar_stability.png` | 0.087, 0.835, 0.060, 0.107 | да |
| `gauge_heat` | bottom_left | `png/bar_heat.png` | 0.154, 0.835, 0.060, 0.107 | да |
| `gauge_energy` | bottom_left | `png/bar_energy.png` | 0.221, 0.835, 0.060, 0.107 | да |
| `arm_armor` | bottom_left | `svg/arm_armor_bars.svg` | 0.020, 0.950, 0.261, 0.020 | да |
| `clock` | bottom_right | `svg/clock_digits.svg` | 0.805, 0.700, 0.062, 0.035 | да |
| `distance` | bottom_right | `svg/distance_digits.svg` | 0.875, 0.700, 0.105, 0.035 | да |
| `priority` | bottom_right | `svg/power_priority.svg` | 0.805, 0.748, 0.062, 0.038 | да |
| `radar` | bottom_right | `svg/radar.svg` | 0.875, 0.745, 0.105, 0.187 | да |
| `ultimate` | bottom_right | `png/ultimate_gauge.png` | 0.805, 0.835, 0.062, 0.110 | да |

* **Свободный центр:** прямоугольник 60 % × 60 % по центру (x, y = 0,2…0,8) не содержит ни одного постоянного элемента; в нём живут только мировые элементы (рамка захвата, шестиугольник зоны, линия удара, прицел 24 px). Тест — на 16:9, 21:9 и 16:10.
* **Занято постоянными элементами:** 17,5 % кадра на 16:9, 13,3 % на 21:9, 15,7 % на 16:10 (бюджет ≤ 25 %, тест).
* **Другие пропорции:** масштаб интерфейса одинаковый по обеим осям (по высоте для ≥ 16:9, по ширине для более «квадратных»), углы держат отступ от своего угла, компас остаётся по центру (`lib/scene.py: element_rect_px`). Элементы не пересекаются ни на одной из трёх пропорций (тест).
* Стрелки угрозы стоят на серединах краёв (`scene.threat_rect`), предупреждающие значки — рядом с повреждённым узлом (`warnings` в состоянии: доля экрана).

## Слои и файлы
| Группа | Файлы |
|---|---|
| Силуэты | `svg/silhouette_body_{player,enemy}.svg` (идентификаторы `zone_Head … zone_LegR`, `data-state`), `svg/zone_layers_arcs[_enemy].svg` (`arc_<Зона>_<Armor\|Mechanism\|System>`): 3 дуги на зону, длина дуги = остаток слоя. Враг показан в зеркале: его левая рука на экране справа |
| Захват | `svg/lockon_corners.svg`, `svg/lockon_zone_hexes.svg`, `png/lockon_ring_anim_strip.png` (16 кадров, 4×4 по 128 px), `svg/strike_arc.svg`, `svg/crosshair.svg` |
| Шкалы | `png/bar_{armor,stability,heat,energy}.png` + `png/ultimate_gauge.png` — **маски для материала**: канал R = прогресс вдоль кольца (0 в начале, 255 в конце; порог `R < заполнение`), A = форма, G = внутреннее кольцо; кольцо 270°, старт внизу слева по часовой. `svg/bar_*.svg`, `svg/ultimate_gauge.svg` — их векторный вид |
| Иконки | `svg/weapon_icons_{rockets,rail,plasma}.svg`, `svg/status_icons_{blind,strikelock,burn}.svg`, `svg/icon_warning.svg`, `svg/threat_arrows_{up,left,right,down}.svg` и PNG 256² |
| Приборы | `svg/radar.svg`, `svg/compass_strip.svg`, `svg/power_priority.svg`, `svg/arm_armor_bars.svg`, `svg/stability_bar_h.svg`, `svg/clock_digits.svg`, `svg/distance_digits.svg`, `svg/digits_atlas.svg` (0–9 и %) |
| Стекло | `png/alarm_frame.png` (красная кромка), `png/crack_mask_00..07.png` (8 штук, 1024², серые), `png/soot_mask_00..03.png`, `png/glitch_strip_00..07.png`, `png/rain_drops_atlas.png` (R, G = смещение преломления, B = блик, A = маска) |
| Данные | `palette.json`, `states.json` (стили состояний зон, пороги цветов шкал, тревоги, стеклянные эффекты по тяжести S0–S4), `layout.json` (+ `schema.json`) |
| Превью | `previews/hud_{fight_ok,medium_damage,critical_alarm,lock_on}.jpg` — кадр 1920×1080 поверх процедурного ночного города, `previews/layout_aspects.png` — раскладка на трёх пропорциях |

### Состояния зон (читаются и без цвета)
| Состояние | Цвет | Линия | Прочее |
|---|---|---|---|
| Intact | нейтральный | сплошная | — |
| Dented | бледно-жёлтый | сплошная, чуть толще | — |
| Exposed | жёлтый | сплошная, толще | заливка 15 % |
| Damaged | оранжевый | штрих `9 3` | заливка 18 % |
| Critical | красный | сплошная, самая толстая | мигание 2,5 Гц |
| Destroyed | серый | точки `2 5` | без заливки |
| Severed | серый | точки `2 5` | перечёркнута |

## Элемент → событие ядра → поведение
Имена событий проверяет тест по `core/include/iv/Events.h`. Полный список — в `layout.json → bindings`.

| Событие ядра (`EventType`) | Элементы | Поведение |
|---|---|---|
| `ZoneState` | layers_player / layers_enemy / body_* | Recolour the zone (a = new ZoneState) with the style from states.json; Critical blinks; actor decides the player or the enemy silhouette. |
| `HitEvent` | layers_*, alarm_frame, cracks | Pulse the hit zone outline (0.25 s); layer reached (a) shortens that layer arc; severity b >= Exposed spawns the plate marks; S2+ adds a crack mask, S3+ soot. |
| `ArmorPlateLost` | body_* (shard marks) | Small shard ticks fly off the zone outline; the Armor arc loses 1/b of its length. |
| `ReactorBreach` | body_player zone_Reactor, alarm_frame | Reactor hex turns red and blinks 4 Hz for 8 s, red edge frame on. |
| `SystemFailure` | weapons, gauge_*, priority, radar | The matching widget shows a dead state (dotted outline, no fill); a = SystemId (Sensors -> radar + lock-on quality 0, Power -> gauge_energy, Cooling -> gauge_heat, Weapon -> weapons). |
| `LimbSevered` | body_* zone | Zone drawn as Severed (dotted + slash); an arm hides its weapon-hand icon. |
| `StaggerBegin` | gauge_stability, alarm_frame | Stability ring flashes orange; short horizontal glitch strip. |
| `StaggerEnd` | gauge_stability | Flash stops. |
| `Knockdown` | alarm_frame, glitch_strips | Signal loss 0.6 s (glitch strip alpha 1), red edge frame pulse. |
| `HeatWarning` | gauge_heat | Ring turns orange then red above the hot threshold and blinks 2 Hz. |
| `CoolantLeak` | gauge_heat, body_player | Heat ring drips marks; the torso outline blinks amber. |
| `Shutdown` | all persistent elements | Everything dims to 25 % except alarm_frame and gauge_energy (power loss). |
| `EnergyShift` | priority | The new priority pictogram lights, the old one fades (0.3 s). |
| `StatusApplied` | enemy_status, body_player corner | Show the status icon (a = StatusKind: Blind, StrikeLock, Burn) with a duration ring (b ticks); actor chooses the player or the enemy side. |
| `StatusEnded` | enemy_status | Remove the status icon. |
| `WeaponCharging` | weapons | The weapon icon fills a ring. |
| `WeaponFired` | weapons | Icon flash, cooldown ring starts from full. |
| `WeaponReady` | weapons | Ring completes, icon pulses once (a = WeaponKind). |
| `WeaponEmpty` | weapons | Icon turns red and dotted. |
| `UltimateReady` | ultimate | Ring full: white blink 2 Hz. |
| `UltimateUsed` | ultimate | Ring empties with a sweep. |
| `WindupStarted` | threat_arrows, strike_arc | Threat arrow in the attack direction (b = SwingSide) with a wide sector; narrows after the commit. |
| `Committed` | threat_arrows | The arrow turns solid red and the sector collapses into a line. |
| `StrikeContact` | alarm_frame | Single white-red flash of the edges at the contact moment. |
| `ExternalHit` | alarm_frame, threat_arrows | Arrow from the side of the source (a: 0 debris, 1 building, 2 fall). |
| `BurnTick` | status_icons_burn, soot_masks | Burn icon pulses; soot grows by one step every 5 ticks. |
| `BoardingSwatTelegraph` | threat_arrows, alarm_frame | Corner arrow on the shoulder side (a), the edge frame fills during b ticks until impact. |
| `HackProgress` | distance, lockon_ring | Progress arc around the crosshair (value 0..1). |
| `MatchEnd` | all | Fade everything out over 1 s (a = EndReason). |

## Что проверено
* `python3 -m unittest discover -s ui/glass_hud/tests` — 38 тестов: идентификаторы зон и слоёв (и сверка перечислений `Zone` / `ZoneState` с `core/include/iv/Types.h`), стили состояний различимы без цвета, JSON = вывод генератора, схема, существование всех файлов из `layout.json`, имена событий в `Events.h`, отсутствие `<text>` в SVG, отсутствие пересечений и свободный центр на 16:9 / 21:9 / 16:10, бюджет занятой площади, стрелки угрозы вне HUD, квадратность круглых виджетов, контраст палитры (ядро ≥ 3:1 на тёмном, тёмное гало ≥ 3:1 на светлом, цвета состояний ≥ 2:1 на средне-сером), рендер всех пресетов, пустота центра на растре, монотонность маски шкалы, детерминизм масок и SVG, размеры файлов (каждый ≤ 5 МБ, всего 4,3 МБ), манифест.
* Превью просмотрены глазами и исправлялись: линии были слишком тонкими (утолщены), трещины «забивали» HUD (сетка разрежена, прозрачность снижена), красная кромка и глитч были слишком сильными, стрелка угрозы перекрывала шкалу стабильности врага (позиция вынесена в `threat_rect` и покрыта тестом), нижний правый блок заходил в свободный центр на 1 % (сдвинут и покрыт тестом).

## Что не проверено / слабые места
* Игра и Unreal: интеграция в Canvas/UMG и материал для масок шкал не запускались. Размеры цифр и толщины линий подбирались на кадре 1920×1080; на реальном стекле кокпита (кривизна, блики) нужна визуальная приёмка.
* Фон превью — процедурный стенд (силуэт врага грубый), это не оценка итоговой картинки.
* Контраст — расчёт по формуле WCAG 2.x для палитры и гало; на реальной картинке с яркими окнами города тонкие линии могут теряться: тогда увеличить толщину в `states.json`.
* Свечение сделано наложением полупрозрачных линий (cairosvg не умеет размытие); в Unreal его лучше дать материалом Bloom.
* Таблица реакций — это ТЗ на привязку, а не код: связывание `EventType` → виджет делается в Unreal.
* Значения мигания и длительностей для игры берите из `data/damage_fx/warnings.json`, здесь они продублированы только для превью.
