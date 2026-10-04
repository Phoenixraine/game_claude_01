# Как читать `district.json` v3 в Unreal (TASK-019)

Все числа в файле — **метры**; система координат генератора: X вправо, Y от моря к городу, Z вверх, углы `yaw_deg` — против часовой стрелки от +X.

## Преобразование в Unreal
| Генератор | Unreal (см) |
|---|---|
| позиция `(x, y, z)` м | `X_ue = y·100`, `Y_ue = x·100`, `Z_ue = z·100` |
| вектор `(dx, dy)` (нормали вывесок, `dir` толпы) | `(dy, dx)` |
| `yaw_deg` | `Yaw_ue = 90 − yaw_deg` (оси X и Y поменялись местами, поэтому угол зеркален) |
| размеры `size_m`, `radius` | ×100 |

Рельеф — как в v1/v2 (`heightmap.r16`, 1009×1009, 16 бит, `z = (v − 32768)/128`; при импорте ландшафта проверьте переворот оси Y).

## Что и откуда брать
| Данные | Что сделать в Unreal |
|---|---|
| `arena.plaza` | площадка боя: ничего не спавнить, мехов ставить на `spawn_duel_a/b`; `arena.street` — ось улицы |
| `roads[]` (`pedestrian` 12 м, `alley` 24–36 м) | дорожное полотно/декали; пешеходная улица — плитка + лужи |
| `buildings[]` + `facade` | **стеклянная башня** (`glass_tower`): куб по `footprint`×`height` с материалом `M_GlassTower`; **лавка** (`shopfront_row`): `M_Shopfront`; прочие — `M_Facade` |
| `buildings[].destruction` | при разрушении: `fracture_pattern` → набор из `art/shards/fracture_patterns.json`, смесь осколков по `debris_mix`, цвет пыли `dust_color` |
| `mega_signs[]` | плоскость/объём `size_m` на фасаде здания `host`, нормаль `normal`, смещение `offset_m`; материал `M_MegaSign` |
| `props[]` | `torii_neon`, `banner_flag`, `steam_vent` (Niagara-пар), `puddle` (маска отражения для мокрого асфальта), `water_tank`/`rooftop_antenna` (на крыше, `pos.z` = высота), торговые автоматы, фонари и т.д. |
| `infrastructure.wires[]` | сплайн-кабели (`power`) и гирлянды (`garland`) по `points` |
| `crowd_spawners[]` | силуэты прохожих в тумане: плотность `density_per_100m2`, скорость, направление |
| `lights[]` | точечные/прямоугольные/spot-источники без теней (`shadow:false` — не включать `CastShadows`); бюджет по `priority` (гасить 5 → 1), мерцание — множитель по шуму с частотой `flicker_hz` и амплитудой `flicker` |
| `fog_map` | карты тумана (ниже) |

## Ресурсы материалов (нужно создать на стороне Unreal)
* **`facade_atlas`** — атлас фасадов жилых/офисных/лавочных зданий (столбцы = `facade_style`: `balcony_grid`, `plaster_balcony`, `tile_panel`, `glass_curtain`, `concrete_grid`, `metal_panel`, `signage_strip`, `shutter_front`, `brick`, `open_deck`, `concrete_ribbed`, `shopfront_neon`, `wood_red`, `brick_red`).
* **`emissive_mask`** — маски светящихся окон; узор выбирается `facade.emissive_floors.pattern` (`random | bands | columns | checker | top_heavy`), плотность `density`, зерно `color_seed`.
* **`mega_sign_atlas`** — штрихи глифов: ячейка атласа = числовой суффикс идентификатора (`g_kana_07` → ячейка 7 набора `kana_like`; `seed` в `glyph_sets.json` задаёт форму штриха). Пиктограммы имеют имя (`pictogram`). Ничего не читается как слово.

## Параметры материалов
* `M_GlassTower`: `Tint` (`facade.tint`), `Reflectivity`, `MullionSpacing`, `PanelWidth`, `PanelHeight`, `SpandrelRatio`, `FloorHeight`, `EmissivePattern`, `EmissiveDensity`, `EmissiveSeed`, `CrownType` (для мэша короны), `Wetness` (мокрое стекло). Отражения — «простейшие»: фальшивый кубмап неба с неоном + сдвиг по этажам, без трассировки.
* `M_Shopfront`: `BayWidth`, `GlassRatio`, `Awning`, `Shutter`, `SignageStrip`, `VerticalSigns`.
* `M_MegaSign`: `Palette0`, `Palette1` (`palette`), `EmissiveIntensity`, `AnimKind` (flicker/scroll/pulse/cycle), `AnimSpeed`, `AnimPhase`, `GlyphAtlas`, `GlyphIds[]`, `Layout` (`glyph_layout`: vertical/horizontal/stack/single), `Style`.
* Мокрый асфальт: `puddle` — маска `size`, отражение неона берётся из `lights[]` (рядом лежащие `neon_*`).

## Карты тумана
`fog_density.png` (серый) и `fog_glow.png` (RGB), 512×512, покрывают `x −800…800`, `y 0…1200` (строка 0 = `y_max`). Использование: в материале объёмного тумана (или Exponential Height Fog + Volumetric Fog Material)
`density *= lerp(0.6, 1.4, fog_density)`, `inscatter += fog_glow * density`. Улицы светлее, над водой и у паровых люков гуще, у вывесок — цветной ореол.
