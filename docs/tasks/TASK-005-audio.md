# TASK-005 — Процедурный звук (`audio/`, Python)

**Ветка:** `claude/task-005-audio` → PR в `main`. **Область:** только `audio/`.
**Источник:** питч §24 «Звук и музыка», §6, §13 (сигнал зарядки), §15.

## Цель
Скрипты синтеза (Python 3.10+, `numpy` + стандартная библиотека; `scipy` можно, если доступен) создают набор звуковых эффектов и
ambient-петель как WAV (48 кБ/с, 16 бит, моно для 3D-источников, стерео для интерьерных/ambient), без внешних сэмплов и лицензий.
Звуки должны быть правдоподобными: металл, гидравлика, масса — а не «писк». Для оценки качества строить спектрограммы и **смотреть** на них,
сверять огибающие, нормировать пик/RMS, проверять отсутствие клиппинга и щелчков на границах петель.

## Список (минимум; имя файла = ID события, контракт для интеграции)
**Мех (внешние):** `mech_step_heavy_01..04`, `mech_step_water_01..02`, `mech_step_rubble_01..02`, `mech_servo_arm_windup`, `mech_servo_arm_strike`,
`mech_hydraulic_release`, `mech_stabilizer_whine`, `mech_power_shift` (поток энергии, §10), `mech_weapon_charge_loop`, `mech_weapon_charge_peak`,
`mech_weapon_fire`, `mech_joint_creak_01..03`, `mech_armor_plate_tear`, `mech_limb_sever`.
**Удары (по §24 «Удары», 6 слоёв):** `hit_metal_contact_light/heavy` (слой 1), `hit_lowfreq_thump_light/heavy` (2), `hit_deform_01..03` (3),
`hit_cockpit_rumble_light/heavy` (4), `hit_compensator_kick` (5), `hit_debris_delay_01..03` (6); плюс `parry_clang`, `intercept_clash`, `block_impact`, `clinch_grind_loop`.
**Кабина (внутренние):** `cockpit_reactor_loop`, `cockpit_breath_loop`, `cockpit_harness_creak`, `cockpit_switch_01..04`, `cockpit_alarm_warning`,
`cockpit_alarm_critical`, `cockpit_coolant_leak_loop`, `cockpit_spark_01..04`, `cockpit_panel_burst`, `cockpit_sensor_fail_static`,
`cockpit_sensor_boot`, `cockpit_hud_lock`, `cockpit_hud_unlock`.
**Окружение:** `env_building_collapse_start/mid/end`, `env_glass_shatter_big`, `env_concrete_crumble`, `env_car_crush`, `env_wave_big`, `env_water_loop_sea`,
`env_rain_loop`, `env_wind_loop_city`, `env_siren_distant_loop`, `env_substation_arc`, `env_missile_incoming`, `env_missile_explosion`, `env_distant_boom_01..03`.
**UI:** `ui_move`, `ui_confirm`, `ui_back`, `ui_deny`, `ui_hangar_ambience_loop`.
**Музыка (минималистично, §24):** `mus_contact_theme_loop` (60 с, холодные синты/низкие струны, без мелодии-«поп»), `mus_tension_pulse_loop`, `mus_commit_hit`.
Диапазон длительностей: удары 0.3–2.5 с, петли 8–60 с бесшовные. Для звуков «масса/размер» — низкие частоты 25–90 Гц, длинные хвосты.

## Выходные файлы
`audio/out/*.wav`, `audio/manifest.json` (для каждого звука: id, файл, длительность, loop, bus: `sfx_ext|sfx_cockpit|ambient|ui|music`,
рекомендуемая громкость dB, 3D (attenuation радиус в метрах), группа вариаций), `audio/gen/` (код синтеза по модулям), `audio/README.md`,
`audio/out/spectrograms/*.png` (по одной на группу), тесты `audio/tests/` (нет клиппинга; петли — разница первого/последнего сэмпла < порога;
длительности в заявленных пределах; манифест соответствует файлам).

## Приёмка
Запуск `python audio/build_all.py` с нуля; тесты зелёные; суммарный размер WAV ≤ 120 МБ; в PR — реальные команды и результаты, оценка слабых
звуков (честно), что не проверено (вы не можете «слышать» — опирайтесь на спектры, огибающие и физическую логику).
