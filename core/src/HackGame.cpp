#include "iv/HackGame.h"

#include <algorithm>
#include <cmath>

namespace iv {

namespace {

// vector::assign trips a gcc 13 -Wnonnull false positive when inlined; clear+resize is equivalent.
template <class V, class T>
void Fill(V* v, size_t n, T value) {
  v->clear();
  v->resize(n, value);
}

float Clamp(float v, float lo, float hi) { return std::max(lo, std::min(hi, v)); }

float WrapDeg(float a) {
  while (a > 180.f) a -= 360.f;
  while (a < -180.f) a += 360.f;
  return a;
}

const tune::HackLevel& Row(int difficulty) { return tune::kHackLevels[std::max(1, std::min(10, difficulty)) - 1]; }

uint64_t Mix64(uint64_t x) {
  x ^= x >> 33;
  x *= 0xff51afd7ed558ccdULL;
  x ^= x >> 33;
  x *= 0xc4ceb9fe1a85ec53ULL;
  x ^= x >> 33;
  return x;
}

}  // namespace

int HackGame::DefaultTimeLimit(int d) { return Row(d).timeLimitSec * kTickHz; }
int HackGame::DefaultPenalty(int d) { return MsToTicks(Row(d).penaltyMs); }

int HackGame::DifficultyFor(Archetype arch, Difficulty diff, ZoneState shoulder) {
  static const int kByDiff[kDifficultyCount] = {1, 3, 6};
  static const int kByArch[kArchetypeCount] = {1, -1, 0, 0, -1, 1};   // Counterpuncher, Breaker, LimbHunter, Trickster, Gunner, Grappler
  int d = kByDiff[static_cast<int>(diff)] + kByArch[static_cast<int>(arch)];
  switch (shoulder) {
    case ZoneState::Intact:
    case ZoneState::Dented: break;
    case ZoneState::Exposed: d -= 1; break;
    case ZoneState::Damaged: d -= 2; break;
    default: d -= 3; break;   // Critical and worse: the hatch hangs open
  }
  return std::max(1, std::min(10, d));
}

uint64_t HackGame::StageSeed(uint64_t seed, int stage, int reroll) {
  return Mix64(seed ^ Mix64(static_cast<uint64_t>(stage) * 0x9e3779b97f4a7c15ULL + static_cast<uint64_t>(reroll) * 0xbf58476d1ce4e5b9ULL + 0x1234567ULL));
}

std::vector<HackStageSpec> HackGame::StagesFor(int difficulty) {
  const int n = Row(difficulty).stages;
  std::vector<HackStageSpec> s;
  s.push_back({HackStage::Path, false});
  if (n >= 3) s.push_back({HackStage::Rhythm, false});
  s.push_back({HackStage::Frequency, false});
  if (n >= 5) {   // the boss phase: a longer rhythm run and a narrow frequency lock, both under a permanent alarm
    s.push_back({HackStage::Rhythm, true});
    s.push_back({HackStage::Frequency, true});
  }
  return s;
}

// ------------------------------------------------------------------------------------------------ generators

RhythmLayout HackGame::GenerateRhythm(int difficulty, uint64_t seed, bool boss) {
  const tune::HackLevel& L = Row(difficulty);
  Rng rng(seed, 0x52485954ULL);
  RhythmLayout r;
  r.boss = boss;
  r.lanes = boss ? std::min(5, L.lanes + 1) : L.lanes;
  const int n = boss ? L.impulses * 6 / 5 : L.impulses;
  const int gmin = boss ? std::max(10, L.gapMin * 9 / 10) : L.gapMin;
  const int gmax = boss ? std::max(gmin + 2, L.gapMax * 9 / 10) : L.gapMax;
  int t = tune::kHackLeadTicks;
  int lastLane = -1;
  for (int i = 0; i < n; ++i) {
    int lane = static_cast<int>(rng.Below(static_cast<uint32_t>(r.lanes)));
    if (lane == lastLane && rng.Chance(0.6f)) lane = (lane + 1 + static_cast<int>(rng.Below(static_cast<uint32_t>(std::max(1, r.lanes - 1))))) % r.lanes;
    r.impulses.push_back({t, lane});
    lastLane = lane;
    t += gmin + static_cast<int>(rng.Below(static_cast<uint32_t>(gmax - gmin + 1)));
  }
  return r;
}

FreqLayout HackGame::GenerateFreq(int difficulty, uint64_t seed, bool boss) {
  const tune::HackLevel& L = Row(difficulty);
  Rng rng(seed, 0x46524551ULL);
  FreqLayout f;
  f.boss = boss;
  f.locks = L.locks + (boss ? 1 : 0);
  const float rel = L.relSpeed * (boss ? 1.1f : 1.f);
  f.hackerSpeed = rel * (0.4f + 0.2f * rng.Unit());
  f.iceSpeed = rel - f.hackerSpeed;
  f.hackerStart = rng.Unit() * 360.f;
  f.iceStart = rng.Unit() * 360.f;
  const float hw0 = L.lockHalfDeg * (boss ? 0.95f : 1.f);
  for (int k = 0; k < f.locks; ++k) {
    const float travel = rel * (1.f + tune::kHackLockSpeedGain * static_cast<float>(k)) * tune::kHackAlarmSpeedMult;
    f.halfDeg.push_back(std::max(std::max(tune::kHackLockHalfMinDeg, 1.2f * travel), hw0 * std::pow(L.lockShrink, static_cast<float>(k))));
  }
  return f;
}

PathLayout HackGame::GeneratePath(int difficulty, uint64_t seed) {
  const tune::HackLevel& L = Row(difficulty);
  Rng rng(seed, 0x50415448ULL);
  const int W = L.gridW, H = L.gridH;
  auto at = [&](int x, int y) { return y * W + x; };

  for (int attempt = 0; attempt < 60; ++attempt) {
    PathLayout p;
    p.w = W;
    p.h = H;
    Fill(&p.cell, static_cast<size_t>(W * H), static_cast<uint8_t>(0));
    p.sx = 0;
    p.sy = static_cast<int>(rng.Below(static_cast<uint32_t>(H)));
    p.cx = W - 1;
    p.cy = static_cast<int>(rng.Below(static_cast<uint32_t>(H)));
    const int coreCell = at(p.cx, p.cy);

    // 1) a random self-avoiding route entry -> core, as long as the attempt allows
    int minLen = std::max(W + H, W + H + 2 * L.keys + L.ice * 2) - attempt / 6;
    minLen = std::max(minLen, std::abs(p.cx - p.sx) + std::abs(p.cy - p.sy) + 1);
    std::vector<int> route;
    std::vector<uint8_t> seen(static_cast<size_t>(W * H), 0);
    int budget = 6000;
    const int dxs[4] = {1, 0, -1, 0}, dys[4] = {0, 1, 0, -1};
    struct Dfs {
      static bool Go(int cur, int coreCell, int W, int H, int minLen, const int* dxs, const int* dys, std::vector<int>* route, std::vector<uint8_t>* seen, int* budget, Rng* rng) {
        if (--*budget < 0) return false;
        route->push_back(cur);
        (*seen)[static_cast<size_t>(cur)] = 1;
        if (cur == coreCell) {
          if (static_cast<int>(route->size()) >= minLen) return true;
          route->pop_back();
          (*seen)[static_cast<size_t>(cur)] = 0;
          return false;
        }
        int order[4] = {0, 1, 2, 3};
        for (int i = 3; i > 0; --i) std::swap(order[i], order[rng->Below(static_cast<uint32_t>(i + 1))]);
        for (int k = 0; k < 4; ++k) {
          const int nx = cur % W + dxs[order[k]], ny = cur / W + dys[order[k]];
          if (nx < 0 || ny < 0 || nx >= W || ny >= H) continue;
          const int ni = ny * W + nx;
          if ((*seen)[static_cast<size_t>(ni)]) continue;
          if (Go(ni, coreCell, W, H, minLen, dxs, dys, route, seen, budget, rng)) return true;
        }
        route->pop_back();
        (*seen)[static_cast<size_t>(cur)] = 0;
        return false;
      }
    };
    if (!Dfs::Go(at(p.sx, p.sy), coreCell, W, H, minLen, dxs, dys, &route, &seen, &budget, &rng)) continue;
    const int Lr = static_cast<int>(route.size());
    if (Lr < 3) continue;

    // 2) keys evenly along the route, ice only where the route runs straight on
    std::vector<uint8_t> onRoute(static_cast<size_t>(W * H), 0);
    for (int c : route) onRoute[static_cast<size_t>(c)] = 1;
    std::vector<uint8_t> isKey(route.size(), 0);
    for (int k = 0; k < L.keys; ++k) {
      int idx = (k + 1) * (Lr - 1) / (L.keys + 1);
      idx = std::max(1, std::min(Lr - 2, idx));
      while (idx < Lr - 1 && isKey[static_cast<size_t>(idx)]) ++idx;
      if (idx >= Lr - 1) break;
      isKey[static_cast<size_t>(idx)] = 1;
    }
    for (int i = 0; i < Lr; ++i)
      if (isKey[static_cast<size_t>(i)]) p.keys.push_back(route[static_cast<size_t>(i)]);
    if (static_cast<int>(p.keys.size()) != L.keys) continue;
    std::vector<int> cand;
    for (int i = 1; i + 1 < Lr; ++i) {
      if (isKey[static_cast<size_t>(i)]) continue;
      const int a = route[static_cast<size_t>(i - 1)], b = route[static_cast<size_t>(i)], c = route[static_cast<size_t>(i + 1)];
      if (b - a == c - b && (std::abs(b - a) == 1 ? a / W == c / W : true)) cand.push_back(i);   // collinear and not wrapping a row
    }
    for (int k = 0; k < L.ice && !cand.empty(); ++k) {
      const size_t j = rng.Below(static_cast<uint32_t>(cand.size()));
      p.cell[static_cast<size_t>(route[static_cast<size_t>(cand[j])])] = 2;
      cand.erase(cand.begin() + static_cast<long>(j));
    }
    // 3) blockers (and a few decoy ice nodes) off the route
    std::vector<int> freeCells;
    for (int c = 0; c < W * H; ++c)
      if (!onRoute[static_cast<size_t>(c)]) freeCells.push_back(c);
    for (int i = static_cast<int>(freeCells.size()) - 1; i > 0; --i) std::swap(freeCells[static_cast<size_t>(i)], freeCells[rng.Below(static_cast<uint32_t>(i + 1))]);
    size_t used = 0;
    for (int b = 0; b < L.blocks && used < freeCells.size(); ++b) p.cell[static_cast<size_t>(freeCells[used++])] = 1;
    for (int b = 0; b < L.ice / 2 + 1 && used < freeCells.size(); ++b) p.cell[static_cast<size_t>(freeCells[used++])] = 2;
    p.route = route;

    // 4) the reference presses: replay the route through the real rules (an ice node slides on, so it costs no press)
    HackGame g;
    g.path_ = p;
    Fill(&g.pvis_, static_cast<size_t>(W * H), static_cast<uint8_t>(0));
    g.pvis_[static_cast<size_t>(at(p.sx, p.sy))] = 1;
    g.px_ = p.sx;
    g.py_ = p.sy;
    g.pkey_ = 0;
    int pos = 0;
    bool ok = true;
    std::vector<HackStep> sol;
    while (pos < Lr - 1) {
      const int cur = route[static_cast<size_t>(pos)], nxt = route[static_cast<size_t>(pos + 1)];
      const int dx = nxt % W - cur % W, dy = nxt / W - cur / W;
      if (g.PathMove(dx, dy) != 2) {
        ok = false;
        break;
      }
      sol.push_back({static_cast<int8_t>(dx), static_cast<int8_t>(dy)});
      const int here = g.py_ * W + g.px_;
      int q = -1;
      for (int i = pos + 1; i < Lr; ++i)
        if (route[static_cast<size_t>(i)] == here) {
          q = i;
          break;
        }
      if (q < 0) {
        ok = false;
        break;
      }
      pos = q;
    }
    if (!ok || g.px_ != p.cx || g.py_ != p.cy || g.pkey_ != static_cast<int>(p.keys.size())) continue;
    p.solution = sol;
    return p;
  }
  // Fallback (never expected): a straight corridor without keys.
  PathLayout p;
  p.w = W;
  p.h = H;
  Fill(&p.cell, static_cast<size_t>(W * H), static_cast<uint8_t>(0));
  p.sx = 0;
  p.sy = 0;
  p.cx = W - 1;
  p.cy = 0;
  for (int x = 0; x < W; ++x) p.route.push_back(x);
  for (int x = 1; x < W; ++x) p.solution.push_back({1, 0});
  return p;
}

// ------------------------------------------------------------------------------------------------ path rules

int HackGame::PathMove(int dx, int dy) {
  const int W = path_.w, H = path_.h;
  auto isKey = [&](int c) { return std::find(path_.keys.begin(), path_.keys.end(), c) != path_.keys.end(); };
  const int coreCell = path_.cy * W + path_.cx;
  const int nkeys = static_cast<int>(path_.keys.size());
  auto blocked = [&](int c) {
    if (path_.cell[static_cast<size_t>(c)] == 1) return true;
    if (pvis_[static_cast<size_t>(c)]) return true;
    if (isKey(c) && (pkey_ >= nkeys || path_.keys[static_cast<size_t>(pkey_)] != c)) return true;   // keys in order
    if (c == coreCell && pkey_ < nkeys) return true;                                                // the core opens when every key is taken
    return false;
  };
  int x = px_ + dx, y = py_ + dy;
  if (x < 0 || y < 0 || x >= W || y >= H) return 0;
  if (blocked(y * W + x)) return 1;
  Move m;
  m.keyBefore = pkey_;
  m.dx = static_cast<int8_t>(dx);
  m.dy = static_cast<int8_t>(dy);
  for (;;) {
    const int c = y * W + x;
    pvis_[static_cast<size_t>(c)] = 1;
    m.cells.push_back(c);
    if (pkey_ < nkeys && path_.keys[static_cast<size_t>(pkey_)] == c) ++pkey_;
    px_ = x;
    py_ = y;
    if (c == coreCell || path_.cell[static_cast<size_t>(c)] != 2) break;   // ice slides the pilot on in the same direction
    const int nx = x + dx, ny = y + dy;
    if (nx < 0 || ny < 0 || nx >= W || ny >= H || blocked(ny * W + nx)) break;
    x = nx;
    y = ny;
  }
  pmoves_.push_back(m);
  return 2;
}

void HackGame::PathUndo() {
  if (pmoves_.empty()) return;
  const Move m = pmoves_.back();
  pmoves_.pop_back();
  for (int c : m.cells) pvis_[static_cast<size_t>(c)] = 0;
  pkey_ = m.keyBefore;
  if (pmoves_.empty()) {
    px_ = path_.sx;
    py_ = path_.sy;
  } else {
    const int c = pmoves_.back().cells.back();
    px_ = c % path_.w;
    py_ = c / path_.w;
  }
}

bool HackGame::PathSolvable(const PathLayout& p) {
  if (p.w <= 0 || p.h <= 0 || p.cell.size() != static_cast<size_t>(p.w * p.h)) return false;
  HackGame g;
  g.path_ = p;
  Fill(&g.pvis_, p.cell.size(), static_cast<uint8_t>(0));
  g.pvis_[static_cast<size_t>(p.sy * p.w + p.sx)] = 1;
  g.px_ = p.sx;
  g.py_ = p.sy;
  g.pkey_ = 0;
  for (const HackStep& s : p.solution)
    if (g.PathMove(s.dx, s.dy) != 2) return false;
  return g.px_ == p.cx && g.py_ == p.cy && g.pkey_ == static_cast<int>(p.keys.size());
}

// ------------------------------------------------------------------------------------------------ session

void HackGame::Start(const HackConfig& cfg) {
  cfg_ = cfg;
  diff_ = std::max(1, std::min(10, cfg.difficulty));
  cfg_.difficulty = diff_;
  limit_ = cfg.timeLimitTicks > 0 ? cfg.timeLimitTicks : DefaultTimeLimit(diff_);
  penalty_ = cfg.mistakePenaltyTicks > 0 ? cfg.mistakePenaltyTicks : DefaultPenalty(diff_);
  ticksLeft_ = limit_;
  mistakes_ = 0;
  rerolls_ = 0;
  trips_ = 0;
  heat_ = 0.f;
  alarm_ = false;
  sfx_.clear();
  stages_ = StagesFor(diff_);
  stageIdx_ = 0;
  state_ = HackState::Running;
  EnterStage(0, true);
}

void HackGame::EnterStage(int idx, bool regenerate) {
  stageIdx_ = idx;
  stageTick_ = 0;
  const HackStageSpec& sp = stages_[static_cast<size_t>(idx)];
  const uint64_t seed = StageSeed(cfg_.seed, idx, rerolls_);
  switch (sp.kind) {
    case HackStage::Path:
      if (regenerate) path_ = GeneratePath(diff_, seed);
      Fill(&pvis_, path_.cell.size(), static_cast<uint8_t>(0));
      pvis_[static_cast<size_t>(path_.sy * path_.w + path_.sx)] = 1;
      pmoves_.clear();
      px_ = path_.sx;
      py_ = path_.sy;
      pkey_ = 0;
      break;
    case HackStage::Rhythm:
      if (regenerate) rhythm_ = GenerateRhythm(diff_, seed, sp.boss);
      Fill(&rstat_, rhythm_.impulses.size(), static_cast<uint8_t>(0));
      break;
    case HackStage::Frequency:
      if (regenerate) freq_ = GenerateFreq(diff_, seed, sp.boss);
      fk_ = 0;
      fa_ = freq_.hackerStart;
      fc_ = freq_.iceStart;
      break;
  }
}

void HackGame::Reroll(float keep) {
  if (state_ != HackState::Running) return;
  keep = Clamp(keep, 0.f, 1.f);
  int done = static_cast<int>(std::floor(static_cast<float>(stageIdx_) * keep + 0.5f));
  done = std::max(0, std::min(done, stageIdx_));
  ++rerolls_;
  heat_ = 0.f;
  alarm_ = false;
  EnterStage(done, true);
}

bool HackGame::LoadLayout(const PathLayout& p) {
  if (state_ != HackState::Running || stage() != HackStage::Path || p.w <= 0 || p.h <= 0 || p.cell.size() != static_cast<size_t>(p.w * p.h)) return false;
  path_ = p;
  EnterStage(stageIdx_, false);
  return true;
}

bool HackGame::LoadLayout(const RhythmLayout& r) {
  if (state_ != HackState::Running || stage() != HackStage::Rhythm) return false;
  rhythm_ = r;
  EnterStage(stageIdx_, false);
  return true;
}

bool HackGame::LoadLayout(const FreqLayout& f) {
  if (state_ != HackState::Running || stage() != HackStage::Frequency || f.halfDeg.empty()) return false;
  freq_ = f;
  EnterStage(stageIdx_, false);
  return true;
}

void HackGame::AddPenalty(int ticks) {
  if (state_ != HackState::Running || ticks <= 0) return;
  ticksLeft_ -= ticks;
  if (ticksLeft_ <= 0) {
    ticksLeft_ = 0;
    state_ = HackState::Timeout;
    Sfx(HackSfx::Fail);
  }
}

void HackGame::Mistake() {
  ++mistakes_;
  heat_ += static_cast<float>(Row(diff_).heatPerMistake);
  ticksLeft_ -= penalty_;
  Sfx(HackSfx::Err);
}

void HackGame::StageClear() {
  Sfx(HackSfx::StageClear);
  if (stageIdx_ + 1 >= stageCount()) {
    stageIdx_ = stageCount();
    state_ = HackState::Success;
    Sfx(HackSfx::Success);
    return;
  }
  EnterStage(stageIdx_ + 1, true);
}

int HackGame::rhythmWindow() const {
  const int w = Row(diff_).hitWindow;
  return std::max(2, (alarm_ || boss()) ? w - 1 : w);
}

float HackGame::FreqSpeedMult() const {
  return (1.f + tune::kHackLockSpeedGain * static_cast<float>(fk_)) * ((alarm_ || boss()) ? tune::kHackAlarmSpeedMult : 1.f);
}

float HackGame::freqHalfWidth() const {
  if (freq_.halfDeg.empty()) return 0.f;
  return freq_.halfDeg[static_cast<size_t>(std::min(fk_, static_cast<int>(freq_.halfDeg.size()) - 1))];
}

float HackGame::freqOffset() const { return WrapDeg(fa_ - fc_); }

void HackGame::StepPath(const HackInput& in) {
  if (in.aux) {
    if (!pmoves_.empty()) {
      PathUndo();
      ticksLeft_ -= tune::kHackUndoPenaltyTicks;
      Sfx(HackSfx::Tick);
    }
    return;
  }
  if (in.dx == 0 && in.dy == 0) return;
  const int dx = in.dx != 0 ? (in.dx > 0 ? 1 : -1) : 0;
  const int dy = in.dx != 0 ? 0 : (in.dy > 0 ? 1 : -1);   // diagonals are not moves: the horizontal part wins
  const int r = PathMove(dx, dy);
  if (r == 1) {
    Mistake();
  } else if (r == 2) {
    Sfx(HackSfx::Tick);
    if (px_ == path_.cx && py_ == path_.cy && pkey_ == static_cast<int>(path_.keys.size())) StageClear();
  }
}

void HackGame::StepRhythm(const HackInput& in) {
  const int now = stageTick_;
  const int W = rhythmWindow();
  int lanes[3];
  int n = 0;
  if (in.dx < 0) lanes[n++] = 0;
  if (in.dx > 0) lanes[n++] = 3;
  if (in.dy > 0) lanes[n++] = 1;
  if (in.dy < 0) lanes[n++] = 2;
  if (in.confirm && n < 3) lanes[n++] = 4;
  for (int k = 0; k < n; ++k) {
    int hit = -1;
    for (size_t i = 0; i < rhythm_.impulses.size(); ++i) {
      if (rstat_[i] != 0 || rhythm_.impulses[i].lane != lanes[k]) continue;
      if (std::abs(rhythm_.impulses[i].tick - now) <= W) {
        hit = static_cast<int>(i);
        break;
      }
      if (rhythm_.impulses[i].tick - now > W) break;
    }
    if (hit >= 0) {
      rstat_[static_cast<size_t>(hit)] = 1;
      Sfx(HackSfx::Ok);
    } else {
      Mistake();   // a ghost press
    }
  }
  bool open = false;
  for (size_t i = 0; i < rhythm_.impulses.size(); ++i) {
    if (rstat_[i] != 0) continue;
    if (rhythm_.impulses[i].tick + W < now) {
      rstat_[i] = 2;
      Mistake();   // an impulse that ran through the hit line
    } else {
      open = true;
    }
  }
  if (!open && state_ == HackState::Running) {
    bool all = true;
    for (uint8_t s : rstat_) all = all && s != 0;
    if (all) StageClear();
  }
}

void HackGame::StepFreq(const HackInput& in) {
  const float mult = FreqSpeedMult();
  fa_ = WrapDeg(fa_ + freq_.hackerSpeed * mult);
  fc_ = WrapDeg(fc_ - freq_.iceSpeed * mult);
  if (!in.confirm) return;
  if (std::fabs(freqOffset()) <= freqHalfWidth()) {
    ++fk_;
    Sfx(HackSfx::Ok);
    if (fk_ >= freq_.locks) StageClear();
  } else {
    Mistake();
    if (fk_ > 0) --fk_;   // the window widens again
  }
}

void HackGame::Step(const HackInput& in) {
  if (state_ != HackState::Running) return;
  if (in.back) {
    state_ = HackState::Fail;
    Sfx(HackSfx::Fail);
    return;
  }
  switch (stage()) {
    case HackStage::Path: StepPath(in); break;
    case HackStage::Rhythm: StepRhythm(in); break;
    case HackStage::Frequency: StepFreq(in); break;
  }
  if (state_ != HackState::Running) return;
  ++stageTick_;
  heat_ = std::max(0.f, heat_ - tune::kHackHeatDecayPerTick);
  const bool wasAlarm = alarm_;
  alarm_ = heat_ >= static_cast<float>(tune::kHackAlarmHeat);
  if (alarm_ && !wasAlarm) Sfx(HackSfx::Alarm);
  if (heat_ >= static_cast<float>(tune::kHackTripHeat)) {   // the ICE trips: the stage starts over (a time penalty, not a defeat)
    ++trips_;
    heat_ = static_cast<float>(tune::kHackTripHeatAfter);
    ticksLeft_ -= penalty_ * tune::kHackTripPenaltyMult;
    Sfx(HackSfx::IceTrip);
    EnterStage(stageIdx_, false);
  }
  if (--ticksLeft_ <= 0) {
    ticksLeft_ = 0;
    state_ = HackState::Timeout;
    Sfx(HackSfx::Fail);
  }
}

float HackGame::progress() const {
  if (state_ == HackState::Success) return 1.f;
  if (stages_.empty()) return 0.f;
  float frac = 0.f;
  switch (stage()) {
    case HackStage::Path: frac = static_cast<float>(pkey_) / static_cast<float>(path_.keys.size() + 1); break;
    case HackStage::Rhythm: {
      int n = 0;
      for (uint8_t s : rstat_) n += s != 0;
      frac = rstat_.empty() ? 0.f : static_cast<float>(n) / static_cast<float>(rstat_.size());
      break;
    }
    case HackStage::Frequency: frac = freq_.locks > 0 ? static_cast<float>(fk_) / static_cast<float>(freq_.locks) : 0.f; break;
  }
  return Clamp((static_cast<float>(stageIdx_) + frac) / static_cast<float>(stages_.size()), 0.f, 1.f);
}

float HackGame::quality() const {
  if (state_ != HackState::Success) return 0.f;
  const float timeFrac = limit_ > 0 ? Clamp(static_cast<float>(ticksLeft_) / static_cast<float>(limit_), 0.f, 1.f) : 0.f;
  const float clean = 1.f - Clamp(static_cast<float>(mistakes_) / static_cast<float>(8 + 2 * stageCount()), 0.f, 1.f);
  const float noTrips = 1.f - Clamp(static_cast<float>(trips_) / 3.f, 0.f, 1.f);
  return Clamp(0.5f * timeFrac + 0.35f * clean + 0.15f * noTrips, 0.f, 1.f);
}

std::vector<HackSfx> HackGame::DrainSfx() {
  std::vector<HackSfx> out;
  out.swap(sfx_);
  return out;
}

HackInput HackGame::PerfectInput() const {
  HackInput in;
  if (state_ != HackState::Running) return in;
  switch (stage()) {
    case HackStage::Path: {
      size_t common = 0;
      while (common < pmoves_.size() && common < path_.solution.size() && pmoves_[common].dx == path_.solution[common].dx && pmoves_[common].dy == path_.solution[common].dy) ++common;
      if (pmoves_.size() > common) {
        in.aux = true;
      } else if (common < path_.solution.size()) {
        in.dx = path_.solution[common].dx;
        in.dy = path_.solution[common].dy;
      }
      break;
    }
    case HackStage::Rhythm: {
      for (size_t i = 0; i < rhythm_.impulses.size(); ++i) {
        if (rstat_[i] != 0 || rhythm_.impulses[i].tick != stageTick_) continue;
        switch (rhythm_.impulses[i].lane) {
          case 0: in.dx = -1; break;
          case 1: in.dy = 1; break;
          case 2: in.dy = -1; break;
          case 3: in.dx = 1; break;
          default: in.confirm = true; break;
        }
      }
      break;
    }
    case HackStage::Frequency: {
      const float mult = FreqSpeedMult();
      const float na = fa_ + freq_.hackerSpeed * mult, nc = fc_ - freq_.iceSpeed * mult;
      if (std::fabs(WrapDeg(na - nc)) <= freqHalfWidth() * 0.6f) in.confirm = true;
      break;
    }
  }
  return in;
}

uint64_t HackGame::Hash() const {
  uint64_t h = 1469598103934665603ULL;
  auto mix = [&h](uint64_t v) {
    for (int i = 0; i < 8; ++i) {
      h ^= (v >> (i * 8)) & 0xffu;
      h *= 1099511628211ULL;
    }
  };
  auto q = [](float f) { return static_cast<uint64_t>(std::llround(static_cast<double>(f) * 1000.0)); };
  mix(static_cast<uint64_t>(state_));
  mix(static_cast<uint64_t>(static_cast<uint32_t>(ticksLeft_)));
  mix(static_cast<uint64_t>(mistakes_));
  mix(static_cast<uint64_t>(rerolls_));
  mix(static_cast<uint64_t>(trips_));
  mix(static_cast<uint64_t>(stageIdx_));
  mix(static_cast<uint64_t>(stageTick_));
  mix(q(heat_));
  mix(static_cast<uint64_t>(px_ * 100 + py_));
  mix(static_cast<uint64_t>(pkey_));
  mix(static_cast<uint64_t>(pmoves_.size()));
  for (uint8_t s : rstat_) mix(s);
  mix(static_cast<uint64_t>(fk_));
  mix(q(fa_));
  mix(q(fc_));
  return h;
}

}  // namespace iv
