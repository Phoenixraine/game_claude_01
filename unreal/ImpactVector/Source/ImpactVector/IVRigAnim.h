// Runtime for the procedural animation library (`anim/`, TASK-007): poses + locomotion clips -> bone transforms of the rigged mech.
// Conventions (see anim/README.md): joint angles are local Euler (rx, ry, rz) in degrees, R = Rz(rz) Ry(ry) Rx(rx), expressed in a
// world-aligned frame at rest, in the Blender axes (+Z up, mech faces -Y, mech's left = +X). We convert them to Unreal axes here.
#pragma once

#include "CoreMinimal.h"

class USkeletalMesh;

/** Joint angles of every animated bone. */
struct FIVPoseAngles
{
	TMap<FName, FVector> Joint;      // bone -> (rx, ry, rz) degrees
	FVector RootPosM = FVector::ZeroVector;   // blender metres, offset from rest
	FVector RootRotDeg = FVector::ZeroVector; // (rx, ry, rz) of the root

	static FIVPoseAngles Lerp(const FIVPoseAngles& A, const FIVPoseAngles& B, float T);
};

struct FIVClipFrame
{
	FVector RootPosM;
	FVector RootRotDeg;
	TArray<float> J;        // 3 per bone in BoneOrder
	bool bContactL = true, bContactR = true;
};

struct FIVClip
{
	FName Name;
	float Fps = 30.f;
	float DurationS = 1.f;
	TArray<FIVClipFrame> Frames;
};

class FIVRigData
{
public:
	/** Loads poses.json and locomotion.json (both from `Content/Data`). */
	bool Load(const FString& PosesPath, const FString& LocoPath);
	bool IsValid() const { return Poses.Num() > 0 && Clips.Num() > 0; }

	const FIVPoseAngles* FindPose(FName Name) const { return Poses.Find(Name); }
	const FIVClip* FindClip(FName Name) const { return Clips.Find(Name); }

	/** Samples a looping clip at time T (seconds). Cycles wrap, one-shot clips clamp. */
	FIVPoseAngles SampleClip(const FIVClip& Clip, float T, bool bLoop) const;

	TArray<FName> BoneOrder;
	TMap<FName, FIVPoseAngles> Poses;
	TMap<FName, FIVClip> Clips;
};

/** Maps anim-library angles onto the imported skeleton: computes parent-relative bone transforms (reference-skeleton order). */
class FIVRigDriver
{
public:
	bool Init(USkeletalMesh* InMesh);
	bool IsReady() const { return RestComp.Num() > 0; }
	void Compute(const FIVPoseAngles& Pose, TArray<FTransform>& OutLocal) const;
	int32 NumBones() const { return Names.Num(); }

private:
	TArray<FName> Names;
	TArray<int32> Parent;
	TArray<FTransform> RestComp;      // rest component-space transforms (UE axes, cm)
	TMap<FName, int32> Index;

	static FQuat DeltaToUE(const FVector& RxRyRzDeg);
};
