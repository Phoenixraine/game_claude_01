#include "iv/HackBot.h"

#include <algorithm>
#include <cmath>

namespace iv {

HackBot::HackBot(const HackBotProfile& profile, uint64_t seed) : prof_(profile), rng_(seed, 0x424f5448ULL) {}

float HackBot::Gauss() {
  // Irwin-Hall: sum of 4 uniforms, centred and scaled to unit variance.
  float s = 0.f;
  for (int i = 0; i < 4; ++i) s += rng_.Unit();
  return (s - 2.f) * 1.7320508f;
}

void HackBot::Replan(const HackGame& g) {
  stage_ = g.stageIndex();
  rerolls_ = g.rerolls();
  planPos_ = 0;
  plan_.clear();
  havePrev_ = false;
  skipLock_ = false;
  gap_ = 0;
  const int r = prof_.reactionTicks;
  idle_ = r * 2;   // reading the new screen
  if (g.stage() == HackStage::Path) {
    idle_ += r == 0 ? 0 : 3 * static_cast<int>(g.path().solution.size());   // planning the route
  } else if (g.stage() == HackStage::Rhythm) {
    const float sigma = 0.10f * static_cast<float>(r) + 0.3f;
    for (const RhythmImpulse& im : g.rhythm().impulses) {
      Plan p{im.tick, im.lane, false};
      if (r > 0) {
        p.tick = im.tick + static_cast<int>(std::lround(Gauss() * sigma));
        if (rng_.Chance(prof_.errorRate)) {
          if (rng_.Chance(0.5f)) p.skip = true;
          else p.lane = (im.lane + 1 + static_cast<int>(rng_.Below(static_cast<uint32_t>(std::max(1, g.rhythm().lanes - 1))))) % g.rhythm().lanes;
        }
      }
      plan_.push_back(p);
    }
    std::stable_sort(plan_.begin(), plan_.end(), [](const Plan& a, const Plan& b) { return a.tick < b.tick; });
  }
}

HackInput HackBot::Next(const HackGame& g) {
  HackInput in;
  if (!g.running()) return in;
  if (g.stageIndex() != stage_ || g.rerolls() != rerolls_ || g.stageTick() < lastStageTick_) Replan(g);
  lastStageTick_ = g.stageTick();
  const int r = prof_.reactionTicks;

  switch (g.stage()) {
    case HackStage::Path: {
      if (idle_ > 0) {
        --idle_;
        break;
      }
      if (gap_ > 0) {
        --gap_;
        break;
      }
      const HackInput want = g.PerfectInput();
      gap_ = r == 0 ? 0 : std::max(2, r * 7 / 10);
      if (r > 0 && !want.aux && rng_.Chance(prof_.errorRate)) {
        // a slip of the thumb: another direction
        const int d = static_cast<int>(rng_.Below(4));
        in.dx = static_cast<int8_t>(d == 0 ? -1 : d == 1 ? 1 : 0);
        in.dy = static_cast<int8_t>(d == 2 ? -1 : d == 3 ? 1 : 0);
        if (in.dx == want.dx && in.dy == want.dy) in = want;
      } else {
        in = want;
        if (want.aux) gap_ = std::max(gap_, r);   // noticing the mistake takes a moment
      }
      break;
    }
    case HackStage::Rhythm: {
      if (idle_ > 0) {
        // the first impulse is kHackLeadTicks away: reading the screen does not delay the plan, only the very first reaction
        idle_ = std::max(0, idle_ - 1);
      }
      while (planPos_ < plan_.size() && plan_[planPos_].tick < g.stageTick()) ++planPos_;   // too late: forgotten
      while (planPos_ < plan_.size() && plan_[planPos_].tick == g.stageTick()) {
        const Plan& p = plan_[planPos_++];
        if (p.skip) continue;
        switch (p.lane) {
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
      if (idle_ > 0) {
        --idle_;
        break;
      }
      if (r == 0) {
        in.confirm = g.PerfectInput().confirm;
        break;
      }
      const float off = g.freqOffset();
      if (!havePrev_) {
        prevOff_ = off;
        havePrev_ = true;
        const float sigmaDeg = (0.18f * static_cast<float>(r)) * (g.freq().hackerSpeed + g.freq().iceSpeed);
        aim_ = Gauss() * sigmaDeg;
        skipLock_ = rng_.Chance(prof_.errorRate);
      }
      // the offset grows by the relative speed every tick: press when it crosses the aim point
      const bool crossed = (prevOff_ < aim_ && off >= aim_) || (off < prevOff_ && aim_ <= off);   // the second case: the angle wrapped past 180
      if (crossed) {
        if (!skipLock_) in.confirm = true;
        const float sigmaDeg = (0.18f * static_cast<float>(r)) * (g.freq().hackerSpeed + g.freq().iceSpeed);
        aim_ = Gauss() * sigmaDeg;
        skipLock_ = rng_.Chance(prof_.errorRate);
      }
      prevOff_ = off;
      break;
    }
  }
  return in;
}

}  // namespace iv
