// Module 3 and 4 (per-fighter half): Combat Vector strike state machine, arm-pose economy,
// guard / hard stance / dodge, feints, weapon charge (pitch §5, §6, §8, §13).
// A Fighter never looks at its opponent; Duel (Duel.h) resolves contacts between two fighters.
#pragma once

#include "iv/Body.h"
#include "iv/Events.h"
#include "iv/Resources.h"
#include "iv/Tuning.h"
#include "iv/Types.h"

namespace iv {

// One tick of player (or AI) intent. Edge flags are true for exactly one tick when pressed.
struct Input {
  // Strike (RT + right stick + left stick), pitch §5.2.
  bool strikeHeld = false;            // RT held: windup / charge. Releasing it commits the strike.
  SwingSide side = SwingSide::Up;     // right stick direction picked first
  Zone target = Zone::Torso;          // right stick sector picked second
  Footwork footwork = Footwork::Hold; // left stick during the strike
  Arm arm = Arm::R;
  bool quick = false;                 // edge: short RT press, pitch §5.3
  bool cancel = false;                // edge: B, pitch §5.2 (4)
  bool toGrab = false;                // edge: X (feint into a grab while winding up, pitch §8)
  bool switchArm = false;             // edge: RB while winding up: arm-switch feint, pitch §8
  bool reverse = false;               // edge: RB while a reverse chain is open: reply, pitch §7
  // Defence (LT), pitch §6.
  bool guardHeld = false;
  SwingSide guardSide = SwingSide::Up;
  bool hardStance = false;            // Y while LT is held
  // Movement, pitch §11. +1 approach, -1 retreat.
  int8_t move = 0;
  bool dodge = false;                 // edge: A
  int8_t dodgeDir = 1;                // -1 left, +1 right
  // Systems.
  bool weaponHeld = false;            // Y (weapon mode): hold to charge, release to fire, pitch §13
  bool ultimate = false;              // edge: v2 ultimate button (needs a full gauge)
  bool setPriority = false;           // d-pad
  EnergyPriority priority = EnergyPriority::Guard;
};

// What happened when a strike reached its target. Reported in StrikeContact events.
enum class Outcome : uint8_t {
  Hit,
  Blocked,
  Parried,
  Evaded,
  Intercepted,
  Whiff,
  HardStanceBlocked,
  Grabbed,
  GrabParried,
  Clashed,      // v3: two blades met on the same line; both strikes stopped
};

// Per-tick data handed to a Fighter by whoever owns the world (Duel or the game layer).
struct StepContext {
  Tick now = 0;
  float distance = tune::kStartDistance;  // gap to the opponent
  float proximity = 0.f;                  // 0..1, how close an obstacle is behind this fighter (pitch §7)
  float coolingMult = 1.f;                // water / rain bonus (pitch §10)
  EventLog* log = nullptr;
};

struct StrikeState {
  StrikeKind kind = StrikeKind::Heavy;
  SwingSide side = SwingSide::Up;
  Zone target = Zone::Torso;
  Arm arm = Arm::R;
  Footwork foot = Footwork::Hold;
  FootPlant plant = FootPlant::Planted;
  int held = 0;           // ticks RT has been held
  int minHold = 0;        // windup must reach this before a release commits
  int charge = 0;         // ticks held beyond minHold (capped)
  bool released = false;  // RT released (or quick/grab path): the commit delay is running
  int sinceRelease = 0;
  int commitDelay = 0;
  int strikeTick = 0;     // ticks spent in the Strike phase
  int strikeLen = 0;
  bool innerLine = false; // launched as a counter: ordinary blocks and parries fail (pitch §7)
};

struct GuardState {
  bool held = false;
  SwingSide side = SwingSide::Up;
  int age = 0;            // ticks since the guard was raised or its side changed
  Tick pressTick = 0;     // tick of the (re)press: the parry window counts from here
  bool hard = false;      // hard stance requested
  int hardAge = 0;
};

struct HitReport {
  float dealt = 0.f;
  bool severed = false;
  bool staggered = false;
  bool knockedDown = false;
  bool interrupted = false;
  ZoneState before = ZoneState::Intact;
  ZoneState after = ZoneState::Intact;
  Layer layer = Layer::Armor;   // deepest layer reached (v2)
};

class Fighter {
 public:
  explicit Fighter(Side s = Side::A) : side_(s) { Reset(); }
  void Reset();

  // Advances one tick. Sets contactPending when a strike reached its target this tick, and
  // firePending when a charged weapon was released.
  void Step(const Input& in, const StepContext& ctx);

  // Called by Duel after it decided what a pending strike did.
  void FinishStrike(Outcome outcome, const StepContext& ctx);
  void FinishWeapon(const StepContext& ctx);

  // Applies a landed hit. `stabilityHit` is applied after the damage; stagger / knockdown follow.
  HitReport TakeHit(Zone zone, float damage, StrikeKind kind, float stabilityHit, const StepContext& ctx);
  void LoseStability(float amount, const StepContext& ctx);
  // Breaks the current windup / strike (pitch §5.3) and forces a recovery.
  void Interrupt(int recoveryTicks, const StepContext& ctx);
  void EnterClinch();
  void LeaveClinch();
  // v2
  void SetLoadout(WeaponKind k);
  const tune::WeaponProfile& WeaponProf() const { return tune::kWeapons[Index(weapon)]; }
  void GainUltimate(float amount, const StepContext& ctx);
  bool UltimateReady() const { return ultimate >= tune::kUltimateMax - 0.0001f; }
  bool LegsLocked() const { return weaponCharging && WeaponProf().locksLegs; }
  void ForceStagger(const StepContext& ctx) { if (posture == Posture::Standing || posture == Posture::Dodging) EnterStagger(ctx); }
  void ConsumeUltimate() { ultimate = 0.f; ultimatePending = false; }
  // v3
  void ApplyStatus(StatusKind k, int ticks, const StepContext& ctx);
  bool Blind() const { return blindTicks > 0; }
  // Two blades met: the strike (or windup) is dropped into a long recovery.
  void ClashBreak(const StepContext& ctx);

  // ---- queries ---------------------------------------------------------------------------
  Side side() const { return side_; }
  bool CanAct() const { return posture == Posture::Standing; }
  bool HardStanceActive() const { return guard.hard && guard.hardAge >= tune::kHardStanceRaiseTicks; }
  bool Evading() const { return posture == Posture::Dodging && dodgeTicks < tune::kDodgeEvadeTicks; }
  bool GuardReady() const {
    return guard.held && !guard.hard && posture == Posture::Standing && (phase == Phase::Idle || phase == Phase::Recovery);
  }
  int TicksToContact() const;  // only meaningful in the Strike phase
  float StrikeReach() const;
  float StrikeDamage() const;  // raw damage before the defender's mitigation
  bool SwingAllowedByPose(Arm a, SwingSide s) const { return ((tune::kPoseAllowed[static_cast<int>(pose[Index(a)])] >> Index(s)) & 1u) != 0; }

  // ---- public state (read by Duel, the AI observation builder and the game layer) --------
  Body body;
  Resources res;
  Posture posture = Posture::Standing;
  int postureTicks = 0;
  int dodgeTicks = 0;
  int8_t dodgeSide = 1;         // v2: direction of the current/last dodge (-1 left, +1 right)
  int8_t dodgeDirNow = 0;       // set for one tick when a dodge starts; Duel turns the opponent
  Phase phase = Phase::Idle;
  int phaseTicks = 0;
  int recoveryLen = 0;
  StrikeState strike;
  Arm lastArm = Arm::R;
  ArmPose pose[2] = {ArmPose::Neutral, ArmPose::Neutral};
  int poseIdle[2] = {0, 0};
  GuardState guard;
  int counterTicks = 0;         // window after a parry in which a strike becomes an inner-line counter
  int feints = 0;
  int feintDecay = 0;
  int feintSlow = 0;
  float flank = 0.f;            // degrees: how far the opponent is off this mech's front (pitch §9, §11)
  int8_t lastMove = 0;
  float proximity = 0.f;
  float moveDelta = 0.f;        // distance change requested this tick (negative closes the gap)
  bool contactPending = false;
  bool contactResolved = false;  // Duel resolved the strike; phase stays Contact for one more tick
  bool firePending = false;
  bool weaponCharging = false;
  float weaponCharge = 0.f;
  Zone weaponTarget = Zone::Torso;
  WeaponKind weapon = WeaponKind::RailSpear;  // v2 loadout
  int weaponAmmo = -1;          // shots left (-1 = unlimited)
  int weaponCooldown = 0;       // ticks until the next charge may start
  float ultimate = 0.f;         // v2 gauge 0..tune::kUltimateMax
  bool ultimatePending = false; // the ultimate button was accepted this tick; Duel resolves it
  Zone ultimateTarget = Zone::Torso;
  int protectedTicks = 0;       // v2: invulnerable after an external cut
  int stunImmune = 0;           // v3: ticks during which new stability loss cannot stagger again
  int blindTicks = 0;           // v3 status: sensors blinded (rockets, thrown debris)
  int strikeLockTicks = 0;      // v3 status: cannot start strikes (rail spear)
  int burnTicks = 0;            // v3 status: burning (plasma)
  bool ultimateLocked = false;  // v3: the off-hand arm was cut off, the ultimate is gone
  Tick lastHitTick = -100000;
  // Bookkeeping the pilot can feel or see; feeds the AI observation (never the opponent's intent).
  Outcome lastOwnOutcome = Outcome::Whiff;       // result of this fighter's last strike
  Zone lastOwnTarget = Zone::Torso;
  Tick lastOwnTick = -100000;
  Outcome lastIncomingOutcome = Outcome::Whiff;  // what the opponent's last strike did to this fighter
  Zone lastIncomingZone = Zone::Torso;
  Tick lastIncomingTick = -100000;

 private:
  void Emit(const StepContext& ctx, EventType t, Zone z = Zone::Torso, int a = 0, int b = 0, float v = 0.f) const;
  int ComputeRecovery(int baseTicks) const;
  void StartRecovery(int baseTicks, const StepContext& ctx);
  void BeginStrike(const Input& in, StrikeKind kind, const StepContext& ctx);
  void HandleGuard(const Input& in, const StepContext& ctx);
  void HandleStrike(const Input& in, const StepContext& ctx);
  void HandleWindup(const Input& in, const StepContext& ctx);
  void HandleWeapon(const Input& in, const StepContext& ctx);
  void TryDodge(const Input& in, const StepContext& ctx);
  void RegisterFeint(const StepContext& ctx);
  void EnterStagger(const StepContext& ctx);
  void EnterKnockdown(const StepContext& ctx);
  float SwingSpeed(Arm a) const;
  float MoveSpeed() const;
  int ScaledTicks(int base, float speed) const;
  Arm PickArm(Arm wanted, SwingSide side, bool* ok) const;
  int PoseReturnPenalty(Arm a, SwingSide s) const;

  Side side_;
};

// Pose left behind by a heavy strike (pitch §5.4).
ArmPose PoseAfter(StrikeKind kind, SwingSide side);
// Lines a counter may take against a given attack (pitch §7 "Перехват").
bool IsInterceptLine(SwingSide attack, SwingSide counter);
// v3 rule: the torso-turn + half-step dodge gets out of the way of lateral slashes only; a chop from above or a rising cut follows the mech.
inline bool IsLateralSwing(SwingSide s) { return s == SwingSide::Left || s == SwingSide::Right; }
inline bool IsLinearSwing(SwingSide s) { return s == SwingSide::Up || s == SwingSide::Down; }
// v3: two strikes meet if they come along the same line in the world: Up/Up, Down/Down, or opposite screen sides (Left/Right).
inline bool SameLine(SwingSide a, SwingSide b) {
  if (a == SwingSide::Up || a == SwingSide::Down) return a == b;
  return b == SwingSide::Left || b == SwingSide::Right ? a != b : false;
}
// Zone of the blocking arm that takes the load (pitch §6 "нагружает блокирующую руку").
Zone GuardZone(SwingSide s);
// The arm that does the blocking for a given sector.
inline Arm GuardArm(SwingSide s) { return (s == SwingSide::Up || s == SwingSide::Left) ? Arm::L : Arm::R; }

}  // namespace iv
