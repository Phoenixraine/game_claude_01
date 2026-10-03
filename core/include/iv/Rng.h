// Seedable PCG32 generator. The core never touches std::random_device or the system clock (determinism rule).
#pragma once

#include <cstdint>

namespace iv {

class Rng {
 public:
  explicit Rng(uint64_t seed = 0x853c49e6748fea9bULL, uint64_t stream = 0xda3e39cb94b95bdbULL) { Seed(seed, stream); }

  void Seed(uint64_t seed, uint64_t stream = 0xda3e39cb94b95bdbULL) {
    state_ = 0;
    inc_ = (stream << 1u) | 1u;
    Next();
    state_ += seed;
    Next();
  }

  uint32_t Next() {
    const uint64_t old = state_;
    state_ = old * 6364136223846793005ULL + inc_;
    const uint32_t xorshifted = static_cast<uint32_t>(((old >> 18u) ^ old) >> 27u);
    const uint32_t rot = static_cast<uint32_t>(old >> 59u);
    return (xorshifted >> rot) | (xorshifted << ((~rot + 1u) & 31u));
  }

  // Uniform in [0, bound). bound == 0 returns 0.
  uint32_t Below(uint32_t bound) {
    if (bound == 0) return 0;
    const uint32_t threshold = (~bound + 1u) % bound;
    for (;;) {
      const uint32_t r = Next();
      if (r >= threshold) return r % bound;
    }
  }

  // Uniform in [0, 1).
  float Unit() { return static_cast<float>(Next() >> 8) * (1.0f / 16777216.0f); }

  bool Chance(float p) { return Unit() < p; }

  uint64_t state() const { return state_; }

 private:
  uint64_t state_ = 0;
  uint64_t inc_ = 1;
};

}  // namespace iv
