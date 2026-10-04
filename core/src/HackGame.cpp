#include "iv/HackGame.h"

#include <algorithm>
#include <cmath>

namespace iv {

namespace {
float Clamp(float v, float lo, float hi) { return std::max(lo, std::min(hi, v)); }
}  // namespace

int HackGame::DefaultTimeLimit(int d) {
  d = std::max(1, std::min(10, d));
  const float s = 60.f - 35.f * static_cast<float>(d - 1) / 9.f;   // STATUS §6B: a hard, timed game: 60 s .. 25 s
  return static_cast<int>(s * static_cast<float>(kTickHz));
}

int HackGame::DefaultPenalty(int d) {
  d = std::max(1, std::min(10, d));
  return MsToTicks(1500 + 150 * d);
}

int HackGame::DifficultyFor(Archetype arch, Difficulty diff, ZoneState shoulder) {
  static const int kByDiff[kDifficultyCount] = {3, 5, 7};
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

void HackGame::Start(const HackConfig& cfg) {
  diff_ = std::max(1, std::min(10, cfg.difficulty));
  limit_ = cfg.timeLimitTicks > 0 ? cfg.timeLimitTicks : DefaultTimeLimit(diff_);
  penalty_ = cfg.mistakePenaltyTicks > 0 ? cfg.mistakePenaltyTicks : DefaultPenalty(diff_);
  ticksLeft_ = limit_;
  N_ = 4 + diff_;
  hits_ = 0;
  mistakes_ = 0;
  rerolls_ = 0;
  rng_.Seed(cfg.seed, 0x4841434bULL);
  pos_ = 0.f;
  vel_ = 0.010f + 0.0015f * static_cast<float>(diff_);
  ww_ = 0.088f - 0.0042f * static_cast<float>(diff_);
  NewWindow();
  state_ = HackState::Running;
}

void HackGame::NewWindow() { wc_ = ww_ + 0.1f + rng_.Unit() * (0.8f - 2.f * ww_); }

void HackGame::Step(const HackInput& in) {
  if (state_ != HackState::Running) return;
  pos_ += vel_;
  if (pos_ >= 1.f) {
    pos_ = 2.f - pos_;
    vel_ = -std::fabs(vel_);
  } else if (pos_ <= 0.f) {
    pos_ = -pos_;
    vel_ = std::fabs(vel_);
  }
  if (in.back) {
    state_ = HackState::Fail;
    return;
  }
  if (in.confirm) {
    if (std::fabs(pos_ - wc_) <= ww_) {
      ++hits_;
      if (hits_ >= N_) {
        state_ = HackState::Success;
        return;
      }
      NewWindow();
    } else {
      ++mistakes_;
      ticksLeft_ -= penalty_;
    }
  }
  if (--ticksLeft_ <= 0) {
    ticksLeft_ = 0;
    state_ = HackState::Timeout;
  }
}

void HackGame::Reroll(float keep) {
  if (state_ != HackState::Running) return;
  keep = Clamp(keep, 0.f, 1.f);
  hits_ = static_cast<int>(std::floor(static_cast<float>(hits_) * keep + 0.5f));
  hits_ = std::min(hits_, N_ - 1);
  ++rerolls_;
  pos_ = 0.f;
  vel_ = std::fabs(vel_);
  NewWindow();
}

void HackGame::AddPenalty(int ticks) {
  if (state_ != HackState::Running || ticks <= 0) return;
  ticksLeft_ -= ticks;
  if (ticksLeft_ <= 0) {
    ticksLeft_ = 0;
    state_ = HackState::Timeout;
  }
}

float HackGame::quality() const {
  if (state_ != HackState::Success) return 0.f;
  const float timeFrac = limit_ > 0 ? Clamp(static_cast<float>(ticksLeft_) / static_cast<float>(limit_), 0.f, 1.f) : 0.f;
  const float clean = 1.f - Clamp(static_cast<float>(mistakes_) / static_cast<float>(N_), 0.f, 1.f);
  return Clamp(0.55f * timeFrac + 0.45f * clean, 0.f, 1.f);
}

bool HackGame::WantsConfirm() const {
  if (state_ != HackState::Running) return false;
  return std::fabs(pos_ - wc_) <= ww_ * 0.8f;
}

uint64_t HackGame::Hash() const {
  uint64_t h = 1469598103934665603ULL;
  auto mix = [&h](uint64_t v) {
    for (int i = 0; i < 8; ++i) {
      h ^= (v >> (i * 8)) & 0xffu;
      h *= 1099511628211ULL;
    }
  };
  mix(static_cast<uint64_t>(state_));
  mix(static_cast<uint64_t>(ticksLeft_));
  mix(static_cast<uint64_t>(hits_));
  mix(static_cast<uint64_t>(mistakes_));
  mix(static_cast<uint64_t>(rerolls_));
  mix(static_cast<uint64_t>(std::llround(static_cast<double>(pos_) * 100000.0)));
  mix(static_cast<uint64_t>(std::llround(static_cast<double>(wc_) * 100000.0)));
  mix(rng_.state());
  return h;
}

}  // namespace iv
