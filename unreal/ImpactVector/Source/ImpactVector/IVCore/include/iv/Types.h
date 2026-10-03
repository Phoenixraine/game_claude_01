// Shared enums and small helpers for the IMPACT VECTOR combat core (ivcore).
// Plain data only: every type here maps 1:1 onto a UENUM/USTRUCT on the Unreal side.
#pragma once

#include <cstdint>

namespace iv {

using Tick = int32_t;
constexpr int kTickHz = 60;  // pitch §25: fixed 60 Hz simulation step

// Milliseconds -> ticks (rounded to nearest). Used by Tuning.h for all pitch timings.
constexpr int MsToTicks(int ms) { return (ms * kTickHz + 500) / 1000; }

enum class Side : uint8_t { A, B };
constexpr Side Other(Side s) { return s == Side::A ? Side::B : Side::A; }
constexpr int Index(Side s) { return s == Side::A ? 0 : 1; }

// pitch §9, §14: nine damage zones.
enum class Zone : uint8_t { Head, Torso, Reactor, ShoulderL, ShoulderR, ArmL, ArmR, LegL, LegR, Count };
constexpr int kZoneCount = static_cast<int>(Zone::Count);
constexpr int Index(Zone z) { return static_cast<int>(z); }

// pitch §14: three layers per zone, consumed in this order.
enum class Layer : uint8_t { Armor, Mechanism, System, Count };
constexpr int kLayerCount = static_cast<int>(Layer::Count);

// pitch §14. Ordered from healthy to worst; Severed is only reachable for arms and legs.
enum class ZoneState : uint8_t { Intact, Dented, Exposed, Damaged, Critical, Destroyed, Severed };
constexpr int kZoneStateCount = 7;

// pitch §5.2: which of the four swing families an attack belongs to.
enum class SwingSide : uint8_t { Up, Left, Right, Down };
constexpr int Index(SwingSide s) { return static_cast<int>(s); }

// pitch §5.2 (3): lower-body contribution to a strike (left stick).
enum class Footwork : uint8_t { StepIn, Hold, Turn, StepBack };

enum class Arm : uint8_t { L, R };
constexpr int Index(Arm a) { return a == Arm::L ? 0 : 1; }
constexpr Arm Other(Arm a) { return a == Arm::L ? Arm::R : Arm::L; }

// pitch §5.2 (3), §11: result of the foot placement under a strike.
enum class FootPlant : uint8_t { Planted, Stepped, Overextended, Turned, Retreated };

enum class StrikeKind : uint8_t { Heavy, Quick, Grab };

// pitch §5: Idle -> Windup -> (commit point) -> Strike -> Contact -> Recovery.
enum class Phase : uint8_t { Idle, Windup, Strike, Contact, Recovery };

// Whole-body states that override the strike state machine.
enum class Posture : uint8_t { Standing, Staggered, KnockedDown, Dodging, Clinched, ShutDown };

// pitch §5.4: where an arm is left after a strike; decides which swings may follow.
enum class ArmPose : uint8_t { Neutral, Raised, CrossedLeft, CrossedRight, Low };
constexpr int kArmPoseCount = 5;

// pitch §10: power distribution priority.
enum class EnergyPriority : uint8_t { Arms, Legs, Guard, Weapon };

// pitch §14: ways a match can end (no health bar).
enum class EndReason : uint8_t {
  None,
  ReactorDestroyed,
  CockpitCritical,
  TotalImmobility,
  PowerLoss,
  ArmsLostImmobilised,
  TimeLimit,
};

// v2: heavy weapons with a long cooldown (each one triggers an external cinematic cut when fired).
enum class WeaponKind : uint8_t { RailSpear, SuppressionRockets, PlasmaCannon, Count };
constexpr int kWeaponKindCount = static_cast<int>(WeaponKind::Count);
constexpr int Index(WeaponKind k) { return static_cast<int>(k); }

// v2: subsystems reported by SystemFailure events.
enum class SystemId : uint8_t { Sensors, Power, Cooling, ArmL, ArmR, LegL, LegR, Weapon, Count };

// v2: kind of the scripted external cut (CinematicBegin / CinematicEnd).
enum class CinematicKind : uint8_t { None, Ultimate, RailSpear, SuppressionRockets, PlasmaCannon, UltimateBisect, UltimateSever };
constexpr CinematicKind CinematicOf(WeaponKind k) {
  return k == WeaponKind::RailSpear ? CinematicKind::RailSpear : k == WeaponKind::SuppressionRockets ? CinematicKind::SuppressionRockets : CinematicKind::PlasmaCannon;
}

// v3: timed conditions laid on a fighter by weapons, debris and the ultimate.
enum class StatusKind : uint8_t { Blind, StrikeLock, Burn, Count };

// v2: training dummy behaviour (pitch tutorial, TASK-006 update).
enum class DummyMode : uint8_t { Off, Passive, Scripted, BlockOnly };

// pitch §20.
enum class Archetype : uint8_t { Counterpuncher, Breaker, LimbHunter, Trickster, Gunner, Grappler };
constexpr int kArchetypeCount = 6;
enum class Difficulty : uint8_t { Easy, Normal, Hard };
constexpr int kDifficultyCount = 3;

inline const char* Name(Zone z) {
  static const char* const kNames[] = {"Head",      "Torso",    "Reactor", "ShoulderL", "ShoulderR",
                                       "ArmL",      "ArmR",     "LegL",    "LegR"};
  return kNames[Index(z)];
}
inline const char* Name(ZoneState s) {
  static const char* const kNames[] = {"Intact", "Dented", "Exposed", "Damaged", "Critical", "Destroyed", "Severed"};
  return kNames[static_cast<int>(s)];
}
inline const char* Name(EndReason r) {
  static const char* const kNames[] = {"None",         "ReactorDestroyed",    "CockpitCritical", "TotalImmobility",
                                       "PowerLoss",    "ArmsLostImmobilised", "TimeLimit"};
  return kNames[static_cast<int>(r)];
}
inline const char* Name(WeaponKind k) {
  static const char* const kNames[] = {"RailSpear", "SuppressionRockets", "PlasmaCannon"};
  return kNames[Index(k)];
}
inline const char* Name(Archetype a) {
  static const char* const kNames[] = {"Counterpuncher", "Breaker", "LimbHunter", "Trickster", "Gunner", "Grappler"};
  return kNames[static_cast<int>(a)];
}
inline const char* Name(Difficulty d) {
  static const char* const kNames[] = {"Easy", "Normal", "Hard"};
  return kNames[static_cast<int>(d)];
}
inline const char* Name(SwingSide s) {
  static const char* const kNames[] = {"Up", "Left", "Right", "Down"};
  return kNames[Index(s)];
}

constexpr bool IsArmZone(Zone z) { return z == Zone::ArmL || z == Zone::ArmR; }
constexpr bool IsLegZone(Zone z) { return z == Zone::LegL || z == Zone::LegR; }
constexpr bool IsLimbZone(Zone z) { return IsArmZone(z) || IsLegZone(z); }
constexpr Zone ArmZone(Arm a) { return a == Arm::L ? Zone::ArmL : Zone::ArmR; }
constexpr Zone ShoulderZone(Arm a) { return a == Arm::L ? Zone::ShoulderL : Zone::ShoulderR; }

}  // namespace iv
