// Headless duel simulator: AI vs AI over every archetype pair x difficulty x seed.
//
//   ivsim [--seeds N] [--difficulty easy|normal|hard|all] [--seed-base S] [--pair A:B]
//         [--duels duels.csv] [--events events.csv] [--markdown report.md] [--quiet]
//
// --duels   one CSV row per duel (result, length, counts)
// --events  every event of every duel (large; use with a small --seeds)
// --markdown the summary tables used by docs/BALANCE_REPORT.md
#include <algorithm>
#include <cstdarg>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>

#include "iv/Ai.h"
#include "iv/Duel.h"

using namespace iv;

namespace {

struct Totals {
  int duels = 0;
  int draws = 0;
  double ticks = 0;
  std::vector<double> lengths;
  int reasons[7] = {};
  int severed = 0;
  int duelsWithSever = 0;
  int contacts = 0;
  int aimed[kZoneCount] = {};
  int outcomes[9] = {};
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

const char* kOutcomeNames[9] = {"Hit", "Blocked", "Parried", "Evaded", "Intercepted", "Whiff", "HardStanceBlocked", "Grabbed", "GrabParried"};

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
    for (int r = 1; r < 7; ++r) Out("%s %.1f%%%s", Name(static_cast<EndReason>(r)), 100.0 * t.reasons[r] / t.duels, r < 6 ? ", " : "\n");

    Out("\nSevered limbs: %d in %d duels (%.1f%% of duels, %.2f per duel)\n", t.severed, t.duelsWithSever, 100.0 * t.duelsWithSever / t.duels,
        static_cast<double>(t.severed) / t.duels);

    Out("\nStrike contacts by aimed zone: ");
    for (int z = 0; z < kZoneCount; ++z) Out("%s %.1f%%%s", Name(static_cast<Zone>(z)), t.contacts ? 100.0 * t.aimed[z] / t.contacts : 0.0, z < kZoneCount - 1 ? ", " : "\n");

    Out("\nContact outcomes: ");
    for (int o = 0; o < 9; ++o) Out("%s %.1f%%%s", kOutcomeNames[o], t.contacts ? 100.0 * t.outcomes[o] / t.contacts : 0.0, o < 8 ? ", " : "\n");
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
