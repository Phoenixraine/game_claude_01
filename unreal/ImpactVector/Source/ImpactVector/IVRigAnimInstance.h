// Minimal AnimInstance that outputs a pose computed in code (anim library) -- no Animation Blueprint required.
#pragma once

#include "CoreMinimal.h"
#include "Animation/AnimInstance.h"
#include "Animation/AnimInstanceProxy.h"
#include "IVRigAnimInstance.generated.h"

UCLASS()
class IMPACTVECTOR_API UIVRigAnimInstance : public UAnimInstance
{
	GENERATED_BODY()

public:
	/** Local (parent-relative) transforms indexed by reference-skeleton bone index. Written by the pawn each frame. */
	TArray<FTransform> PoseLocal;

protected:
	virtual FAnimInstanceProxy* CreateAnimInstanceProxy() override;
};

struct FIVRigAnimProxy : public FAnimInstanceProxy
{
	FIVRigAnimProxy(UAnimInstance* InInstance) : FAnimInstanceProxy(InInstance) {}
	TArray<FTransform> Pose;

	virtual void PreUpdate(UAnimInstance* InAnimInstance, float DeltaSeconds) override;
	virtual bool Evaluate(FPoseContext& Output) override;
};
