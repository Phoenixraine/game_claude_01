# data/hack — данные мини-игры взлома (TASK-018)

| Файл | Что |
|---|---|
| `difficulty.json` | таблица сложностей 1…10 (копия `tune::kHackLevels`), константы тревоги и ЛЬДА |
| `hack_levels.json` | 500 предгенерированных сессий (50 на сложность): раскладки всех этапов точно как их строит `HackGame::Start` |
| `schema.json` | JSON Schema для `hack_levels.json` |
| `palette.json` | палитра экрана |
| `calibration.csv` | вероятность успеха ботов по сложностям (вывод `hack_calib`) |
| `mockups/` | SVG-макеты трёх экранов и PNG-превью; `make_mockups.py` их рисует |
| `previews/hack_calibration.png` | график калибровки |

Перегенерация: `cmake -S core -B build && cmake --build build && ./build/hack_export data/hack` (тест `Hack` сравнивает файлы с генератором побайтно). Подробности — `docs/ux/hack_minigame.md`, `docs/ux/hack_calibration.md`.
