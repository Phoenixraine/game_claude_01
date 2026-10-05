import io
SRC = r"F:\IVRepo\core"


def rd(n):
    s = io.open(SRC + "\\" + n, encoding="utf-8").read()
    return s.replace("\r\n", "\n"), ("\r\n" in s)


def wr(n, s, crlf):
    io.open(SRC + "\\" + n, "w", encoding="utf-8", newline="\r\n" if crlf else "\n").write(s)


def rep(t, old, new):
    assert old in t, old[:80]
    return t.replace(old, new, 1)


t, c = rd("include/iv/Tuning.h")
if "kStrikeEnergyCost" not in t:
    t = rep(t, "// v6 (owner's rules, 2026-10-05): the ultimate starts", """// v6 (owner, 2026-10-05): three strike-energy pools — quick strikes, long (sword) strikes, ranged (weapon) strikes. A strike spends its pool and is
// weaker the emptier the pool was when it was thrown (full pool = full damage), so one strike cannot be spammed: mix the types.
constexpr float kStrikeEnergyMax = 100.f;
constexpr float kStrikeEnergyCost[3] = {16.f, 34.f, 55.f};       // quick, long, ranged
constexpr float kStrikeEnergyRegenPerSec[3] = {13.f, 9.f, 6.f};
constexpr float kStrikeEnergyMinMult = 0.3f;                      // damage multiplier of an empty pool
// v6 (owner's rules, 2026-10-05): the ultimate starts""")
    wr("include/iv/Tuning.h", t, c)

h, c = rd("include/iv/Fighter.h")
if "strikeEnergy" not in h:
    h = rep(h, "  bool innerLine = false; // launched as a counter: ordinary blocks and parries fail (pitch §7)\n};", "  bool innerLine = false; // launched as a counter: ordinary blocks and parries fail (pitch §7)\n  float energyMult = 1.f; // v6: damage multiplier from the strike-energy pool at the moment it was thrown\n};")
    h = rep(h, "  float strikeMove = 0.f;", "  float strikeEnergy[3] = {100.f, 100.f, 100.f};   // v6: quick / long / ranged strike pools (0..kStrikeEnergyMax)\n  float strikeMove = 0.f;")
    h = rep(h, "  void GainUltimate(float amount, const StepContext& ctx);", "  void GainUltimate(float amount, const StepContext& ctx);\n  /** Spends pool `pool` (0 quick, 1 long, 2 ranged) and returns the damage multiplier its level gave (1.0 when full, kStrikeEnergyMinMult when empty). */\n  float SpendStrikeEnergy(int pool);\n  float StrikeEnergyMult(int pool) const;\n  static int EnergyPoolOf(StrikeKind k) { return k == StrikeKind::Quick ? 0 : 1; }")
    wr("include/iv/Fighter.h", h, c)

f, c = rd("src/Fighter.cpp")
if "SpendStrikeEnergy" not in f:
    f = rep(f, "  ultimate = 0.f;\n  ultimatePending = false;\n  ultWind = ultWindLen = 0;", "  ultimate = 0.f;\n  ultimatePending = false;\n  ultWind = ultWindLen = 0;\n  for (float& e : strikeEnergy) e = tune::kStrikeEnergyMax;")
    f = rep(f, "void Fighter::GainUltimate(float amount, const StepContext& ctx) {", """float Fighter::StrikeEnergyMult(int pool) const {
  const float u = std::max(0.f, std::min(1.f, strikeEnergy[pool] / tune::kStrikeEnergyMax));
  return tune::kStrikeEnergyMinMult + (1.f - tune::kStrikeEnergyMinMult) * u;
}

float Fighter::SpendStrikeEnergy(int pool) {
  const float m = StrikeEnergyMult(pool);
  strikeEnergy[pool] = std::max(0.f, strikeEnergy[pool] - tune::kStrikeEnergyCost[pool]);
  return m;
}

void Fighter::GainUltimate(float amount, const StepContext& ctx) {""")
    # regen every tick
    f = rep(f, "void Fighter::Step(const Input& in, const StepContext& ctx) {\n  contactPending = false;", "void Fighter::Step(const Input& in, const StepContext& ctx) {\n  for (int i = 0; i < 3; ++i) strikeEnergy[i] = std::min(tune::kStrikeEnergyMax, strikeEnergy[i] + tune::kStrikeEnergyRegenPerSec[i] / static_cast<float>(kTickHz));\n  contactPending = false;")
    # spend when a strike commits
    f = rep(f, "  s.strikeLen = ScaledTicks(len, SwingSpeed(s.arm));\n  s.strikeTick = 0;\n  phase = Phase::Strike;", "  s.strikeLen = ScaledTicks(len, SwingSpeed(s.arm));\n  s.strikeTick = 0;\n  s.energyMult = SpendStrikeEnergy(EnergyPoolOf(s.kind));   // v6: weaker when the pool is low\n  phase = Phase::Strike;")
    f = rep(f, "    strike.released = true;\n    phase = Phase::Strike;\n    phaseTicks = 0;\n    Emit(ctx, EventType::AirChopStarted);", "    strike.released = true;\n    strike.energyMult = SpendStrikeEnergy(1);\n    phase = Phase::Strike;\n    phaseTicks = 0;\n    Emit(ctx, EventType::AirChopStarted);")
    f = rep(f, "  if (s.innerLine) d *= tune::kInnerLineDamageMult;\n  return d;", "  if (s.innerLine) d *= tune::kInnerLineDamageMult;\n  return d * s.energyMult;")
    wr("src/Fighter.cpp", f, c)

a, c = rd("include/iv/Anim.h")
if "energyQuick01" not in a:
    a = rep(a, "  float ultimate01 = 0.f;\n", "  float ultimate01 = 0.f;\n  float energyQuick01 = 1.f, energyLong01 = 1.f, energyRanged01 = 1.f;   // v6 strike-energy pools\n")
    wr("include/iv/Anim.h", a, c)
ac, c = rd("src/Anim.cpp")
if "energyQuick01" not in ac:
    ac = rep(ac, "  a.ultimate01 = Unit(f.ultimate / tune::kUltimateMax);", "  a.ultimate01 = Unit(f.ultimate / tune::kUltimateMax);\n  a.energyQuick01 = Unit(f.strikeEnergy[0] / tune::kStrikeEnergyMax);\n  a.energyLong01 = Unit(f.strikeEnergy[1] / tune::kStrikeEnergyMax);\n  a.energyRanged01 = Unit(f.strikeEnergy[2] / tune::kStrikeEnergyMax);")
    wr("src/Anim.cpp", ac, c)

d, c = rd("src/Duel.cpp")
if "SpendStrikeEnergy(2)" not in d:
    NL = chr(10)
    d = rep(d, "  int hits = 0;" + NL + "  for (int k = 0; k < wp.salvo; ++k) {", "  int hits = 0;" + NL + "  const float energyMult = atk.SpendStrikeEnergy(2);   // v6: one shot spends the ranged pool once; the emptier it was, the weaker every hit" + NL + "  for (int k = 0; k < wp.salvo; ++k) {")
    d = rep(d, "    float dmg = wp.damage;", "    float dmg = wp.damage * energyMult;")
    wr("src/Duel.cpp", d, c)
print("energy patched")
