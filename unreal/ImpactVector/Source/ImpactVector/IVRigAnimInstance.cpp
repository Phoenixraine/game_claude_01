#include "IVRigAnimInstance.h"
#include "BoneContainer.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"

FAnimInstanceProxy* UIVRigAnimInstance::CreateAnimInstanceProxy()
{
	return new FIVRigAnimProxy(this);
}

void FIVRigAnimProxy::PreUpdate(UAnimInstance* InAnimInstance, float DeltaSeconds)
{
	if (const UIVRigAnimInstance* I = Cast<UIVRigAnimInstance>(InAnimInstance))
	{
		Pose = I->PoseLocal;
	}
}

bool FIVRigAnimProxy::Evaluate(FPoseContext& Output)
{
	Output.ResetToRefPose();
	static const bool bRefOnly = FParse::Param(FCommandLine::Get(), TEXT("IVRefOnly"));
	if (bRefOnly || Pose.Num() == 0) return true;
	const FBoneContainer& BC = Output.Pose.GetBoneContainer();
	for (FCompactPoseBoneIndex CI : Output.Pose.ForEachBoneIndex())
	{
		const int32 MeshIdx = BC.GetSkeletonIndex(CI);          // skeleton == reference skeleton order for imported meshes
		if (Pose.IsValidIndex(MeshIdx)) Output.Pose[CI] = Pose[MeshIdx];
	}
	return true;
}
