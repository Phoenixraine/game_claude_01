// Headless duel simulator: AI vs AI over every archetype pair x difficulty x seed.
//
//   ivsim [--seeds N] [--difficulty easy|normal|hard|all] [--seed-base S] [--pair A:B] [--boarding]
//         [--duels duels.csv] [--events events.csv] [--markdown report.md] [--quiet]
//
// --duels   one CSV row per duel (result, length, counts)
// --events  every event of every duel (large; use with a small --seeds)
// --markdown the summary tables used by docs/BALANCE_REPORT.md
// --boarding boarding balance (TASK-017): player bots with different hacking / swing skill against every archetype x difficulty (docs/BOARDING_BALANCE.md)
#include <algorithm>
#include <cstdarg>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>

#include "iv/Ai.h"
#include "iv/Boarding.h"
#include "iv/Duel.h"

using namespace iv;

namespace {

struct Totals {
  int duels = 0;
  int draws = 0;
  double ticks = 0;
  std::vector<double> lengths;
  int reasons[8] = {};
  int severed = 0;
  int duelsWithSever = 0;
  int contacts = 0;
  int aimed[kZoneCount] = {};
  int outcomes[10] = {};
  int wins[kArchetypeCount] = {};
  int losses[kArchetypeCount] = {};
  int drawsBy[kArchetypeCount] = {};
  int matches[kArchetypeCount] = {};
  int pairWins[kArchetypeCount][kArchetypeCount] = {};
  int pairGames[kArchetypeCount][kArchetypeCount] = {};
  int clinches = 0;
  int intercepts = 0;
  int replies = 0;
  int feints = 0;
  int heavy = 0;
  int quick = 0;
  int grabs = 0;
  int weaponShots = 0;
  int weaponHits = 0;
  int staggers = 0;
  int knockdowns = 0;
  int ultimates = 0;
  int cinematics = 0;
  int plates = 0;
  int hitEvents = 0;
};

const char* kOutcomeNames[10] = {"Hit", "Blocked", "Parried", "Evaded", "Intercepted", "Whiff", "HardStanceBlocked", "Grabbed", "GrabParried", "Clashed"};

bool ParseArchetype(const char* s, Archetype* out) {
  for (int i = 0; i < kArchetypeCount; ++i) {
    if (std::strcmp(s, Name(static_cast<Archetype>(i))) == 0) {
      *out = static_cast<Archetype>(i);
      return true;
    }
  }
  return false;
}

double Percentile(std::vector<double> v, double p) {
  if (v.empty()) return 0.0;
  std::sort(v.begin(), v.end());
  const size_t i = static_cast<size_t>(p * static_cast<double>(v.size() - 1) + 0.5);
  return v[i];
}

FILE* g_md = nullptr;
bool g_quiet = false;

#if defined(__GNUC__)
__attribute__((format(printf, 1, 2)))
#endif
void Out(const char* fmt, ...) {
  va_list ap;
  va_start(ap, fmt);
  if (!g_quiet) {
    va_list cp;
    va_copy(cp, ap);
    std::vfprintf(stdout, fmt, cp);
    va_end(cp);
  }
  if (g_md) std::vfprintf(g_md, fmt, ap);
  va_end(ap);
}


// ------------------------------------------------------------------------------------------------ boarding mode (TASK-017)

// A player bot: how well it plays the hack and how fast it answers the enemy hand.
struct SkillBot {
  const char* name;
  int hackDelay;        // ticks between the window opening and the press (reaction + hand)
  float stray;          // chance per tick of a stray press (nerves)
  int swingReaction;    // ticks from the telegraph to the swing attempt
  float swingMiss;      // chance that the bot never answers a given swat
};
const SkillBot kBots[] = {{"perfect", 0, 0.f, 20, 0.f}, {"good", 4, 0.0015f, 24, 0.03f}, {"average", 7, 0.004f, 36, 0.12f}, {"poor", 10, 0.010f, 52, 0.30f}};

enum class Policy { Never, Spam, Periodic };

struct BoardStats {
  int duels = 0, aWins = 0, bWins = 0, draws = 0;
  double ticks = 0;
  int boardings = 0, success = 0, hackFail = 0, timeout = 0, smashed = 0, aborted = 0, swats = 0, swatsAnswered = 0, smashedAfterPress = 0;
  double blastDamage = 0, hackDifficulty = 0, quality = 0;
  int hacks = 0, denied = 0;
};

struct BotDriver {
  const SkillBot* bot;
  Rng rng;
  int pending = -1;
  bool wantsPrev = false;
  bool answered = false;
  bool willAnswer = true;
  bool pressedInWindow = false;
  int swatSeen = -1;
  explicit BotDriver(const SkillBot* b, uint64_t seed) : bot(b), rng(seed, 0x424f54ULL) {}

  void Decide(const Boarding& bd, BoardingInput* bi) {
    if (bd.phase() == BoardPhase::Hacking) {
      const bool w = bd.hack().WantsConfirm();
      if (w && !wantsPrev) pending = bot->hackDelay > 0 ? std::max(1, bot->hackDelay + static_cast<int>(rng.Below(5)) - 2) : 0;   // human jitter: +-2 ticks
      wantsPrev = w;
      if (pending > 0) --pending;
      else if (pending == 0) {
        bi->hack.confirm = true;
        pending = -1;
      }
      if (rng.Chance(bot->stray)) bi->hack.confirm = true;
    } else {
      wantsPrev = false;
      pending = -1;
    }
    if (bd.swatActive()) {
      const int total = tune::kSwatWindupTicks[0];   // only used to detect a fresh swat below
      (void)total;
      if (swatSeen != bd.swatsThisBoarding() * 1000 + static_cast<int>(bd.swatShoulder())) {
        swatSeen = bd.swatsThisBoarding() * 1000 + static_cast<int>(bd.swatShoulder());
        willAnswer = !rng.Chance(bot->swingMiss);
        answered = false;
        reactionLeft = bot->swingReaction;
      }
      if (reactionLeft > 0) --reactionLeft;
      if (willAnswer && !answered && reactionLeft == 0 && bd.phase() != BoardPhase::HookSwing && bd.swatTicksToImpact() <= tune::kSwingWindowTicks - 3 &&
          bd.swatTicksToImpact() >= tune::kSwingMinTicks + 3) {
        bi->swing = true;
        answered = true;
        pressedInWindow = true;
      }
    } else {
      swatSeen = -1;
      pressedInWindow = false;
    }
  }
  int reactionLeft = 0;
};

void RunBoardingMode(int seeds, uint64_t seedBase, int diffMask) {
  Out("# Boarding balance (`ivsim --boarding`)\n\n");
  Out("Player (side A): fencing AI Counterpuncher/Normal + a boarding bot; enemy (side B): every archetype x difficulty. %d seeds per cell.\n", seeds);
  Out("The hack is the stub rule set of TASK-017 (TASK-018 replaces it), so the success numbers must be re-measured after that task.\n\n");

  struct Cell { BoardStats s[4][3]; };           // [bot][difficulty]
  static Cell byArch[kArchetypeCount];
  BoardStats policyStats[3][4];                   // [policy][bot]: aggregated over everything

  auto runOne = [&](Policy pol, const SkillBot& bot, Archetype arch, Difficulty diff, uint64_t seed, BoardStats* out, BoardStats* out2) {
    Duel duel(seed, true);
    duel.set_time_limit(tune::kMatchTimeLimitTicks);
    Ai fence(Archetype::Counterpuncher, Difficulty::Normal, seed * 2 + 1);
    Ai foe(arch, diff, seed * 2 + 2);
    BoardingConfig cfg;
    cfg.owner = Side::A;
    cfg.enemyArchetype = arch;
    cfg.enemyDifficulty = diff;
    cfg.seed = seed ^ 0x55aa;
    Boarding bd(cfg);
    BotDriver drv(&bot, seed ^ 0x77);
    int sinceLast = 1 << 20;
    int anomaly = 0;
    bool lastPressedInWindow = false;
    while (!duel.result().over) {
      Input ia = fence.Decide(MakeObservation(duel, Side::A));
      ia = bd.Filter(duel, ia);
      const Input ib = foe.Decide(MakeObservation(duel, Side::B));
      duel.Step(ia, ib);
      BoardingInput bi;
      bi.shoulder = (seed & 1) ? Arm::L : Arm::R;
      if (pol == Policy::Spam) bi.start = !bd.Active() && bd.cooldownLeft() == 0;
      else if (pol == Policy::Periodic) bi.start = !bd.Active() && bd.cooldownLeft() == 0 && sinceLast >= 90 * kTickHz;
      if (!duel.cinematic().active) drv.Decide(bd, &bi);   // inputs during an external cut are lost (the boarding is frozen too)
      lastPressedInWindow = drv.pressedInWindow;
      const bool wasActive = bd.Active();
      bd.Step(duel, bi);
      if (bd.phase() == BoardPhase::Smashed && drv.answered) ++anomaly;
      if (!wasActive && bd.Active()) sinceLast = 0;
      else ++sinceLast;
      (void)lastPressedInWindow;
    }
    BoardStats* both[2] = {out, out2};
    for (BoardStats* t : both) {
      if (!t) continue;
      ++t->duels;
      t->ticks += duel.tick();
      t->smashedAfterPress += anomaly;
      const MatchResult& r = duel.result();
      if (r.draw) ++t->draws;
      else if (r.loser == Side::A) ++t->bWins;
      else ++t->aWins;
      for (const Event& e : duel.log().events()) {
        switch (e.type) {
          case EventType::BoardingEnded:
            ++t->boardings;
            if (e.a == static_cast<int>(BoardingOutcome::Success)) ++t->success;
            else if (e.a == static_cast<int>(BoardingOutcome::HackFailed)) ++t->hackFail;
            else if (e.a == static_cast<int>(BoardingOutcome::HackTimeout)) ++t->timeout;
            else if (e.a == static_cast<int>(BoardingOutcome::Smashed)) ++t->smashed;
            else if (e.a == static_cast<int>(BoardingOutcome::Aborted)) ++t->aborted;
            break;
          case EventType::BoardingSwatTelegraph: ++t->swats; break;
          case EventType::BoardingSwingOk: ++t->swatsAnswered; break;
          case EventType::BoardingBlast: t->blastDamage += static_cast<double>(e.value); break;
          case EventType::HackStarted: t->hackDifficulty += e.a; ++t->hacks; break;
          case EventType::BoardingDenied: ++t->denied; break;
          case EventType::HackResultEvt: t->quality += static_cast<double>(e.value); break;
          default: break;
        }
      }
    }
  };

  // 1) success by skill and difficulty, boarding every time it is allowed (Spam) - the pure mini-game numbers
  for (int b = 0; b < 4; ++b)
    for (int a = 0; a < kArchetypeCount; ++a)
      for (int d = 0; d < kDifficultyCount; ++d) {
        if (!((diffMask >> d) & 1)) continue;
        for (int s = 0; s < seeds; ++s) {
          const uint64_t seed = seedBase + static_cast<uint64_t>(s) * 7919u + static_cast<uint64_t>(a * 131 + d * 17 + b);
          runOne(Policy::Spam, kBots[b], static_cast<Archetype>(a), static_cast<Difficulty>(d), seed, &byArch[a].s[b][d], &policyStats[1][b]);
        }
      }
  // 2) the same fights with the policies Never / Periodic (the strategy comparison uses the good bot)
  for (int pol = 0; pol < 3; ++pol) {
    if (pol == 1) continue;
    for (int b = 0; b < 4; ++b) {
      if (pol == 0 && b > 0) continue;
      for (int a = 0; a < kArchetypeCount; ++a)
        for (int d = 0; d < kDifficultyCount; ++d) {
          if (!((diffMask >> d) & 1)) continue;
          for (int s = 0; s < seeds; ++s) {
            const uint64_t seed = seedBase + static_cast<uint64_t>(s) * 7919u + static_cast<uint64_t>(a * 131 + d * 17 + b);
            runOne(static_cast<Policy>(pol), kBots[b], static_cast<Archetype>(a), static_cast<Difficulty>(d), seed, nullptr, &policyStats[pol][b]);
          }
        }
    }
  }

  auto pct = [](int a, int b) { return b ? 100.0 * a / b : 0.0; };
  Out("## Boarding outcomes by bot skill (boarding whenever allowed)\n\n");
  Out("| Bot | Boardings | Success | Hack failed | Timeout | Smashed (died) | Swats answered | Avg grenade dmg | Avg hack difficulty | Avg quality of wins |\n|---|---|---|---|---|---|---|---|---|---|\n");
  for (int b = 0; b < 4; ++b) {
    const BoardStats& t = policyStats[1][b];
    Out("| %s | %d | %.1f%% | %.1f%% | %.1f%% | %.1f%% | %.0f%% of %d | %.1f | %.2f | %.2f |\n", kBots[b].name, t.boardings, pct(t.success, t.boardings),
        pct(t.hackFail, t.boardings), pct(t.timeout, t.boardings), pct(t.smashed, t.boardings), pct(t.swatsAnswered, t.swats), t.swats,
        t.success ? t.blastDamage / t.success : 0.0, t.hacks ? t.hackDifficulty / t.hacks : 0.0, t.success ? t.quality / t.success : 0.0);
  }
  Out("\n## Success rate of the good bot by enemy archetype and difficulty\n\n| Enemy | Easy | Normal | Hard |\n|---|---|---|---|\n");
  for (int a = 0; a < kArchetypeCount; ++a) {
    Out("| %s |", Name(static_cast<Archetype>(a)));
    for (int d = 0; d < kDifficultyCount; ++d) {
      const BoardStats& t = byArch[a].s[1][d];
      Out(" %.0f%% (smashed %.0f%%, n=%d) |", pct(t.success, t.boardings), pct(t.smashed, t.boardings), t.boardings);
    }
    Out("\n");
  }
  Out("\n## Success rate by bot and enemy difficulty\n\n| Bot | Easy | Normal | Hard |\n|---|---|---|---|\n");
  for (int b = 0; b < 4; ++b) {
    Out("| %s |", kBots[b].name);
    for (int d = 0; d < kDifficultyCount; ++d) {
      BoardStats t;
      for (int a = 0; a < kArchetypeCount; ++a) {
        const BoardStats& u = byArch[a].s[b][d];
        t.boardings += u.boardings;
        t.success += u.success;
      }
      Out(" %.1f%% (n=%d) |", pct(t.success, t.boardings), t.boardings);
    }
    Out("\n");
  }
  Out("\n## Strategies: win rate of the player (side A) over all archetype x difficulty cells\n\n");
  Out("| Strategy | Duels | Player wins | Enemy wins | Draws | Mean minutes | Boardings per duel |\n|---|---|---|---|---|---|---|\n");
  const char* kPolNames[3] = {"fencer only (never boards)", "boards whenever allowed", "boards every 90 s"};
  for (int pol = 0; pol < 3; ++pol) {
    for (int b = 0; b < 4; ++b) {
      if (pol == 0 && b > 0) continue;
      const BoardStats& t = policyStats[pol][b];
      if (t.duels == 0) continue;
      Out("| %s%s%s | %d | %.1f%% | %.1f%% | %.1f%% | %.2f | %.2f |\n", kPolNames[pol], pol == 0 ? "" : ", bot ", pol == 0 ? "" : kBots[b].name, t.duels,
          pct(t.aWins, t.duels), pct(t.bWins, t.duels), pct(t.draws, t.duels), t.ticks / t.duels / (kTickHz * 60.0), static_cast<double>(t.boardings) / t.duels);
    }
  }
  int anomalies = 0;
  for (int b = 0; b < 4; ++b) anomalies += policyStats[1][b].smashedAfterPress;
  Out("\nSmashed although the swing was pressed inside the window: %d (must be 0).\n", anomalies);
}

}  // namespace

int main(int argc, char** argv) {
  int seeds = 10;
  uint64_t seedBase = 1000;
  int diffMask = 0b111;
  const char* duelsPath = nullptr;
  const char* eventsPath = nullptr;
  const char* mdPath = nullptr;
  bool quiet = false;
  bool hasPair = false;
  bool boardingMode = false;
  Archetype pairA = Archetype::Counterpuncher, pairB = Archetype::Counterpuncher;

  for (int i = 1; i < argc; ++i) {
    const char* a = argv[i];
    auto next = [&]() -> const char* { return i + 1 < argc ? argv[++i] : ""; };
    if (!std::strcmp(a, "--seeds")) seeds = std::atoi(next());
    else if (!std::strcmp(a, "--seed-base")) seedBase = static_cast<uint64_t>(std::atoll(next()));
    else if (!std::strcmp(a, "--difficulty")) {
      const char* d = next();
      if (!std::strcmp(d, "easy")) diffMask = 1;
      else if (!std::strcmp(d, "normal")) diffMask = 2;
      else if (!std::strcmp(d, "hard")) diffMask = 4;
      else diffMask = 7;
    } else if (!std::strcmp(a, "--duels")) duelsPath = next();
    else if (!std::strcmp(a, "--events")) eventsPath = next();
    else if (!std::strcmp(a, "--markdown")) mdPath = next();
    else if (!std::strcmp(a, "--quiet")) quiet = true;
    else if (!std::strcmp(a, "--boarding")) boardingMode = true;
    else if (!std::strcmp(a, "--pair")) {
      std::string p = next();
      const size_t c = p.find(':');
      if (c == std::string::npos || !ParseArchetype(p.substr(0, c).c_str(), &pairA) || !ParseArchetype(p.substr(c + 1).c_str(), &pairB)) {
        std::fprintf(stderr, "bad --pair, expected Archetype:Archetype\n");
        return 2;
      }
      hasPair = true;
    } else {
      std::fprintf(stderr, "unknown argument %s\n", a);
      return 2;
    }
  }

  if (boardingMode) {
    g_md = mdPath ? std::fopen(mdPath, "w") : nullptr;
    g_quiet = quiet;
    RunBoardingMode(seeds, seedBase, diffMask);
    if (g_md) std::fclose(g_md);
    return 0;
  }

  FILE* duelsFile = duelsPath ? std::fopen(duelsPath, "w") : nullptr;
  FILE* eventsFile = eventsPath ? std::fopen(eventsPath, "w") : nullptr;
  if (duelsFile) std::fprintf(duelsFile, "duel,a,b,difficulty,seed,ticks,minutes,result,reason,severed,contacts,clinches,feints\n");
  if (eventsFile) std::fprintf(eventsFile, "duel,tick,type,actor,zone,a,b,value\n");

  Totals per[kDifficultyCount];
  int duelId = 0;
  for (int d = 0; d < kDifficultyCount; ++d) {
    if (!((diffMask >> d) & 1)) continue;
    const Difficulty diff = static_cast<Difficulty>(d);
    for (int a = 0; a < kArchetypeCount; ++a) {
      for (int b = 0; b < kArchetypeCount; ++b) {
        if (hasPair && !(static_cast<int>(pairA) == a && static_cast<int>(pairB) == b)) continue;
        for (int s = 0; s < seeds; ++s) {
          const uint64_t seed = seedBase + static_cast<uint64_t>(s) * 1000003u + static_cast<uint64_t>(a * 31 + b * 7 + d);
          Duel duel(seed, true);
          duel.set_time_limit(tune::kMatchTimeLimitTicks);
          Ai aiA(static_cast<Archetype>(a), diff, seed * 2 + 1);
          Ai aiB(static_cast<Archetype>(b), diff, seed * 2 + 2);
          while (!duel.result().over) {
            const Input ia = aiA.Decide(MakeObservation(duel, Side::A));
            const Input ib = aiB.Decide(MakeObservation(duel, Side::B));
            duel.Step(ia, ib);
          }
          Totals& t = per[d];
          const MatchResult& r = duel.result();
          ++t.duels;
          t.ticks += duel.tick();
          t.lengths.push_back(static_cast<double>(duel.tick()) / (kTickHz * 60.0));
          ++t.reasons[static_cast<int>(r.reason)];
          ++t.matches[a];
          ++t.matches[b];
          if (a != b) {
            ++t.pairGames[a][b];
            if (r.draw) {
              ++t.drawsBy[a];
              ++t.drawsBy[b];
            } else {
              const int winner = r.loser == Side::A ? b : a;
              const int loser = r.loser == Side::A ? a : b;
              ++t.wins[winner];
              ++t.losses[loser];
              ++t.pairWins[winner][winner == a ? b : a];
            }
          }
          if (r.draw) ++t.draws;
          int sever = 0, contacts = 0, clinches = 0, feints = 0;
          for (const Event& e : duel.log().events()) {
            switch (e.type) {
              case EventType::LimbSevered: ++sever; ++t.severed; break;
              case EventType::StrikeContact:
                ++contacts;
                ++t.contacts;
                ++t.aimed[Index(e.zone)];
                ++t.outcomes[e.b];
                break;
              case EventType::Clinch: ++clinches; ++t.clinches; break;
              case EventType::InterceptSuccess: ++t.intercepts; break;
              case EventType::ReverseChain: ++t.replies; break;
              case EventType::Feint: ++feints; ++t.feints; break;
              case EventType::Committed:
                if (e.a == static_cast<int>(StrikeKind::Heavy)) ++t.heavy;
                else if (e.a == static_cast<int>(StrikeKind::Quick)) ++t.quick;
                else ++t.grabs;
                break;
              case EventType::WeaponFired: ++t.weaponShots; t.weaponHits += e.a; break;
              case EventType::StaggerBegin: ++t.staggers; break;
              case EventType::Knockdown: ++t.knockdowns; break;
              case EventType::UltimateUsed: ++t.ultimates; break;
              case EventType::CinematicBegin: ++t.cinematics; break;
              case EventType::ArmorPlateLost: ++t.plates; break;
              case EventType::HitEvent: ++t.hitEvents; break;
              default: break;
            }
            if (eventsFile)
              std::fprintf(eventsFile, "%d,%d,%d,%d,%s,%d,%d,%.3f\n", duelId, e.tick, static_cast<int>(e.type), static_cast<int>(e.actor),
                           Name(e.zone), e.a, e.b, static_cast<double>(e.value));
          }
          if (sever > 0) ++t.duelsWithSever;
          if (duelsFile)
            std::fprintf(duelsFile, "%d,%s,%s,%s,%llu,%d,%.2f,%s,%s,%d,%d,%d,%d\n", duelId, Name(static_cast<Archetype>(a)), Name(static_cast<Archetype>(b)),
                         Name(diff), static_cast<unsigned long long>(seed), duel.tick(), duel.tick() / (kTickHz * 60.0),
                         r.draw ? "draw" : (r.loser == Side::A ? "B" : "A"), Name(r.reason), sever, contacts, clinches, feints);
          ++duelId;
        }
      }
    }
  }
  if (duelsFile) std::fclose(duelsFile);
  if (eventsFile) std::fclose(eventsFile);

  g_md = mdPath ? std::fopen(mdPath, "w") : nullptr;
  g_quiet = quiet;

  for (int d = 0; d < kDifficultyCount; ++d) {
    const Totals& t = per[d];
    if (t.duels == 0) continue;
    Out("\n### %s (%d duels)\n\n", Name(static_cast<Difficulty>(d)), t.duels);
    const double mean = t.ticks / t.duels / (kTickHz * 60.0);
    Out("Match length, game minutes: mean %.2f, median %.2f, p10 %.2f, p90 %.2f; time-limit draws: %d (%.1f%%)\n\n", mean, Percentile(t.lengths, 0.5),
        Percentile(t.lengths, 0.1), Percentile(t.lengths, 0.9), t.draws, 100.0 * t.draws / t.duels);

    Out("| Archetype | Games | Wins | Losses | Draws | Win rate vs other archetypes |\n|---|---|---|---|---|---|\n");
    for (int a = 0; a < kArchetypeCount; ++a) {
      int games = 0;
      for (int b = 0; b < kArchetypeCount; ++b)
        if (a != b) games += t.pairGames[a][b] + t.pairGames[b][a];
      const double wr = games ? 100.0 * t.wins[a] / games : 0.0;
      Out("| %s | %d | %d | %d | %d | %.1f%% |\n", Name(static_cast<Archetype>(a)), games, t.wins[a], t.losses[a], t.drawsBy[a], wr);
    }

    Out("\nEnd reasons: ");
    for (int r = 1; r < 8; ++r) Out("%s %.1f%%%s", Name(static_cast<EndReason>(r)), 100.0 * t.reasons[r] / t.duels, r < 7 ? ", " : "\n");

    Out("\nSevered limbs: %d in %d duels (%.1f%% of duels, %.2f per duel)\n", t.severed, t.duelsWithSever, 100.0 * t.duelsWithSever / t.duels,
        static_cast<double>(t.severed) / t.duels);

    Out("\nStrike contacts by aimed zone: ");
    for (int z = 0; z < kZoneCount; ++z) Out("%s %.1f%%%s", Name(static_cast<Zone>(z)), t.contacts ? 100.0 * t.aimed[z] / t.contacts : 0.0, z < kZoneCount - 1 ? ", " : "\n");

    Out("\nContact outcomes: ");
    for (int o = 0; o < 10; ++o) Out("%s %.1f%%%s", kOutcomeNames[o], t.contacts ? 100.0 * t.outcomes[o] / t.contacts : 0.0, o < 9 ? ", " : "\n");
    const int defended = t.outcomes[1] + t.outcomes[2] + t.outcomes[3] + t.outcomes[4] + t.outcomes[6] + t.outcomes[8];
    Out("\nDefences (block, hard stance, parry, dodge, intercept, grab parry): %d of %d contacts. Parry share of defences %.1f%%, intercept share %.1f%%, "
        "dodge share %.1f%%, plain block share %.1f%%.\n",
        defended, t.contacts, defended ? 100.0 * (t.outcomes[2] + t.outcomes[8]) / defended : 0.0, defended ? 100.0 * t.outcomes[4] / defended : 0.0,
        defended ? 100.0 * t.outcomes[3] / defended : 0.0, defended ? 100.0 * (t.outcomes[1] + t.outcomes[6]) / defended : 0.0);
    Out("\nPer duel: heavy %.1f, quick %.1f, grabs %.1f, feints %.1f, clinches %.2f, reverse replies %.2f, staggers %.1f, knockdowns %.2f; weapon shots %.2f (%.0f%% hit)\n",
        static_cast<double>(t.heavy) / t.duels, static_cast<double>(t.quick) / t.duels, static_cast<double>(t.grabs) / t.duels,
        static_cast<double>(t.feints) / t.duels, static_cast<double>(t.clinches) / t.duels, static_cast<double>(t.replies) / t.duels,
        static_cast<double>(t.staggers) / t.duels, static_cast<double>(t.knockdowns) / t.duels, static_cast<double>(t.weaponShots) / t.duels,
        t.weaponShots ? 100.0 * t.weaponHits / t.weaponShots : 0.0);
    Out("\nv2 per duel: ultimates %.2f, cinematic cuts %.2f, armour plates lost %.1f, HitEvents %.1f\n", static_cast<double>(t.ultimates) / t.duels,
        static_cast<double>(t.cinematics) / t.duels, static_cast<double>(t.plates) / t.duels, static_cast<double>(t.hitEvents) / t.duels);
  }
  if (g_md) std::fclose(g_md);
  return 0;
}
