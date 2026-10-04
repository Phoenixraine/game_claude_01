// The living inside of the cockpit: the pilot's drive-suit body, tube pipes that vent steam and can burst, dangling wires that sway and
// snap, monitors drawn from game data, fires, sparks, alarm lights. Everything lives in the cockpit's local space (cm, UE axes:
// X forward, Y right, Z up, the eye at the origin) and is built from cockpit_layout.json written by art/cockpit/v3/build_cockpit_v3.py.
#pragma once

#include "CoreMinimal.h"
#include "Components/SceneComponent.h"
#include "iv/Types.h"
#include "IVCockpit.generated.h"

class UStaticMeshComponent;
class UStaticMesh;
class UProceduralMeshComponent;
class UInstancedStaticMeshComponent;
class UPointLightComponent;
class UMaterialInstanceDynamic;
class UMaterialInterface;
class UTextureRenderTarget2D;
class UCanvas;

/** What the monitors and alarms need to know, pushed by the combat director every frame. All fractions are 0..1. */
struct FIVCockpitFeed
{
	float Armor[iv::kZoneCount] = { 1, 1, 1, 1, 1, 1, 1, 1, 1 };
	float Mech[iv::kZoneCount] = { 1, 1, 1, 1, 1, 1, 1, 1, 1 };
	uint8 State[iv::kZoneCount] = {};
	float EnemyArmor[iv::kZoneCount] = { 1, 1, 1, 1, 1, 1, 1, 1, 1 };
	uint8 EnemyState[iv::kZoneCount] = {};
	float Overall = 1.f, EnemyOverall = 1.f;
	float Stability = 1.f, Heat = 0.f, Energy = 1.f, Ultimate = 0.f, EnemyStability = 1.f, EnemyEnergy = 1.f;
	float DistM = 100.f, BearingDeg = 0.f;
	float WeaponReady[3] = { 1, 1, 1 };
	int32 Weapon = 0;
	float Scoop = 1.f;
	bool bBurn = false, bBlind = false, bStrikeLock = false, bLocked = true, bValid = false;
	int32 Priority = 0;
	float Speed01 = 0.f;
};

/** One pipe: control polyline in cockpit space plus its runtime tube mesh. */
struct FIVCockpitPipe
{
	FString Id;
	TArray<FVector> Ctrl;
	TArray<FVector> Dense;           // smoothed centre line
	float R = 2.f;
	int32 Cls = 0;
	float Steam = 0.f;
	bool bBreakable = true;
	TObjectPtr<UProceduralMeshComponent> Mesh;
	bool bBurst = false;
	int32 BreakIdx = 0;
	FVector JetA = FVector::ZeroVector, DirA = FVector::UpVector, JetB = FVector::ZeroVector, DirB = FVector::DownVector;
	float JetTime = 0.f, JetPower = 0.f;
	TArray<FVector> Ports;           // steam ports (positions)
	TArray<FVector> PortDirs;
};

struct FIVCockpitWire
{
	FVector Anchor = FVector::ZeroVector;
	FVector Dir = FVector::DownVector;
	TArray<FVector> P, Prev;
	float SegLen = 8.f, R = 0.4f;
	FLinearColor Col = FLinearColor::Black;
	bool bSnapped = false, bStick = false;
	float SnapTime = 0.f, SparkAcc = 0.f;
	int32 Base = 0;                   // first ISM instance index
	bool bHidden = false;
};

struct FIVCockpitMonitor
{
	FString Id;
	FVector C = FVector::ZeroVector, Right = FVector::RightVector, Up = FVector::UpVector, N = FVector::ForwardVector;
	float W = 30.f, H = 20.f;
	int32 Feed = 0;
	TObjectPtr<UStaticMeshComponent> Mesh;
	TObjectPtr<UMaterialInstanceDynamic> MID;
};

struct FIVLayoutSocket { int32 Kind = 0; FVector P = FVector::ZeroVector, D = FVector::UpVector; FString Tag; float Burn = 0.f; };

struct FIVCockpitPuff { FVector P, V; float Age = 0, Life = 1, S0 = 4, S1 = 12, Roll = 0, Rise = 0, Drag = 1, Seed = 0, Dark = 0; };
struct FIVCockpitSpark { FVector P, V; float Age = 0, Life = 0.6f, Len = 3.f; };
struct FIVCockpitFlame { FVector P, V; float Age = 0, Life = 1, S0 = 8, S1 = 20, Roll = 0, Rise = 40, Heat = 1, Seed = 0; };

UCLASS()
class UIVCockpitComponent : public USceneComponent
{
	GENERATED_BODY()

public:
	UIVCockpitComponent();
	virtual void TickComponent(float Dt, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction) override;

	/** Builds everything on first use (only the viewer's own cockpit needs it). */
	void EnsureBuilt();
	bool IsBuilt() const { return bBuilt; }
	void SetShown(bool bShow);
	void SetCockpitMaterial(UMaterialInterface* M) { CockpitMat = M; }

	void SetFeed(const FIVCockpitFeed& F) { Feed = F; }
	/** Motion of the whole mech this frame (cm/s local to the cockpit), used for steam, wire sway and the pilot's steps. */
	void SetMotion(const FVector& LocalVel, float Speed01, const FVector& LocalAccel, float Lean, float Twist);

	void Footfall(float Strength);
	/** A hit on the player: severity 0..1, direction in cockpit space (where it came from), blocked/parried. */
	void Hit(float Severity, const FVector& FromDir, bool bBlocked);
	void ZoneChanged(iv::Zone Z, iv::ZoneState S, iv::ZoneState Old);
	void PanelBurst(float Strength);

	/** 0 calm, 1 warning, 2 critical: drives red lights, sirens and monitor flicker. */
	float GetAlert() const { return AlertSmooth; }
	int32 ActiveFailures() const;
	/** Stops leaks and fires (the QTE below decks calls this with 1 for everything). */
	void Repair(float Amount);
	void ForceFailures(int32 Count);
	float GetGlitch() const { return Glitch; }
	float GetShake() const { return ShakeLevel; }
	void SetPower(float P) { PowerLevel = P; }
	float GetBodyLean() const { return BodyLean; }

private:
	bool bBuilt = false, bShown = true;
	FIVCockpitFeed Feed;
	FVector LocalVel = FVector::ZeroVector, LocalAccel = FVector::ZeroVector;
	float Speed01 = 0.f, Lean = 0.f, Twist = 0.f;
	float GaitPhase = 0.f, StepPulse = 0.f, BodyLean = 0.f;
	float AlertTarget = 0.f, AlertSmooth = 0.f, Glitch = 0.f, ShakeLevel = 0.f, PowerLevel = 1.f;
	float Time = 0.f, MonAcc = 0.f;
	int32 MonRound = 0;
	float AmbientSparkAcc = 0.f;
	FRandomStream Rng;

	UPROPERTY() TObjectPtr<UMaterialInterface> CockpitMat;
	UPROPERTY() TObjectPtr<UMaterialInstanceDynamic> PropMID;
	UPROPERTY() TArray<TObjectPtr<UStaticMeshComponent>> BodyParts;
	UPROPERTY() TArray<TObjectPtr<USceneComponent>> BodyPivots;
	enum { B_Pelvis, B_Torso, B_ThighL, B_ThighR, B_ShinL, B_ShinR, B_BootL, B_BootR, B_Count };
	UPROPERTY() TArray<TObjectPtr<USceneComponent>> BodyPivot;      // size B_Count

	TArray<FIVCockpitPipe> Pipes;
	TArray<FIVCockpitWire> Wires;
	TArray<FIVCockpitMonitor> Monitors;
	TArray<FIVLayoutSocket> Sockets;
	UPROPERTY() TArray<TObjectPtr<UPointLightComponent>> Lamps;
	TArray<FString> LampKinds;
	TArray<float> LampBase;
	UPROPERTY() TObjectPtr<UInstancedStaticMeshComponent> WireISM;
	UPROPERTY() TObjectPtr<UInstancedStaticMeshComponent> PuffISM;
	UPROPERTY() TObjectPtr<UInstancedStaticMeshComponent> SparkISM;
	UPROPERTY() TObjectPtr<UInstancedStaticMeshComponent> FlameISM;
	UPROPERTY() TArray<TObjectPtr<UTextureRenderTarget2D>> Targets;
	UPROPERTY() TObjectPtr<UPointLightComponent> FireLight;
	TArray<FIVCockpitPuff> Puffs;
	TArray<FIVCockpitSpark> Sparks;
	TArray<FIVCockpitFlame> Flames;
	TArray<FVector> Scroll;                                          // oscilloscope history
	TArray<FString> LogLines;
	float LogAcc = 0.f;
	float FireIntensity = 0.f;
	float PipeBurstCooldown = 0.f;
	float WireSnapCooldown = 0.f;

	bool LoadLayout();
	void BuildPipes();
	void RebuildPipeMesh(FIVCockpitPipe& P);
	void BuildBody();
	void BuildMonitors();
	void BuildWires();
	void UpdateBody(float Dt);
	void UpdatePipes(float Dt);
	void UpdateWires(float Dt);
	void UpdateParticles(float Dt);
	void UpdateLamps(float Dt);
	void UpdateMonitors(float Dt);
	void EmitSteam(const FVector& P, const FVector& Dir, int32 Count, float Speed, float Size);
	void EmitSparks(const FVector& P, const FVector& Dir, int32 Count, float Speed);
	void BurstPipe(int32 Index);
	void SnapWire(int32 Index);
	void AddFire(int32 SocketIndex);
	void DrawMonitor(int32 Feed, UTextureRenderTarget2D* RT);
	void LogLine(const FString& S);
};
