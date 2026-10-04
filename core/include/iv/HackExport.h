// JSON export of the hack mini-game data for the Unreal side (data/hack/*.json). The text is produced here, by the same generators the
// game uses, so a test can prove that the committed files equal the generator output byte for byte.
#pragma once

#include <string>

namespace iv {

// Difficulty table (tune::kHackLevels) + the shared constants.
std::string HackDifficultyJson();
// `perLevel` pre-generated sessions for each difficulty 1..10 (seed = level * 1000 + index): every stage layout exactly as HackGame::Start builds it.
std::string HackLevelsJson(int perLevel);

}  // namespace iv
