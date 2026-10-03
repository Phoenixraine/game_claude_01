#include "IVRigAnim.h"
#include "Engine/SkeletalMesh.h"
#include "ReferenceSkeleton.h"
#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "Misc/FileHelper.h"

namespace
{
	FVector ReadVec3(const TArray<TSharedPtr<FJsonValue>>& A)
	{
		return A.Num() >= 3 ? FVector(A[0]->AsNumber(), A[1]->AsNumber(), A[2]->AsNumber()) : FVector::ZeroVector;
	}
	bool LoadJson(const FString& Path, TSharedPtr<FJsonObject>& Out)
	{
		FString S;
		if (!FFileHelper::LoadFileToString(S, *Path)) return false;
		return FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(S), Out) && Out.IsValid();
	}
}

// ---------------------------------------------------------------------------------------------------------------
FIVPoseAngles FIVPoseAngles::Lerp(const FIVPoseAngles& A, const FIVPoseAngles& B, float T)
{
	FIVPoseAngles R;
	for (const TPair<FName, FVector>& KV : A.Joint)
	{
		const FVector* Vb = B.Joint.Find(KV.Key);
		R.Joint.Add(KV.Key, Vb ? FMath::Lerp(KV.Value, *Vb, T) : KV.Value);
	}
	for (const TPair<FName, FVector>& KV : B.Joint)
	{
		if (!R.Joint.Contains(KV.Key)) R.Joint.Add(KV.Key, KV.Value);
	}
	R.RootPosM = FMath::Lerp(A.RootPosM, B.RootPosM, T);
	R.RootRotDeg = FMath::Lerp(A.RootRotDeg, B.RootRotDeg, T);
	return R;
}

bool FIVRigData::Load(const FString& PosesPath, const FString& LocoPath)
{
	TSharedPtr<FJsonObject> P, L;
	if (!LoadJson(PosesPath, P) || !LoadJson(LocoPath, L)) return false;

	// poses
	const TSharedPtr<FJsonObject> PoseObj = P->GetObjectField(TEXT("poses"));
	for (const TPair<FString, TSharedPtr<FJsonValue>>& KV : PoseObj->Values)
	{
		const TSharedPtr<FJsonObject> O = KV.Value->AsObject();
		FIVPoseAngles Pose;
		const TSharedPtr<FJsonObject> J = O->GetObjectField(TEXT("joints"));
		for (const TPair<FString, TSharedPtr<FJsonValue>>& JJ : J->Values)
		{
			Pose.Joint.Add(FName(*JJ.Key), ReadVec3(JJ.Value->AsArray()));
		}
		if (O->HasTypedField<EJson::Array>(TEXT("root_pos"))) Pose.RootPosM = ReadVec3(O->GetArrayField(TEXT("root_pos")));
		if (O->HasTypedField<EJson::Array>(TEXT("root_rot"))) Pose.RootRotDeg = ReadVec3(O->GetArrayField(TEXT("root_rot")));
		Poses.Add(FName(*KV.Key), MoveTemp(Pose));
	}

	// clips
	for (const TSharedPtr<FJsonValue>& V : L->GetArrayField(TEXT("bone_order"))) BoneOrder.Add(FName(*V->AsString()));
	for (const TSharedPtr<FJsonValue>& CV : L->GetArrayField(TEXT("clips")))
	{
		const TSharedPtr<FJsonObject> C = CV->AsObject();
		FIVClip Clip;
		Clip.Name = FName(*C->GetStringField(TEXT("name")));
		Clip.Fps = C->HasField(TEXT("fps")) ? float(C->GetNumberField(TEXT("fps"))) : 30.f;
		Clip.DurationS = float(C->GetNumberField(TEXT("duration_s")));
		for (const TSharedPtr<FJsonValue>& FV : C->GetArrayField(TEXT("frames")))
		{
			const TSharedPtr<FJsonObject> F = FV->AsObject();
			FIVClipFrame Fr;
			Fr.RootPosM = ReadVec3(F->GetArrayField(TEXT("root")));
			Fr.RootRotDeg = ReadVec3(F->GetArrayField(TEXT("root_rot")));
			for (const TSharedPtr<FJsonValue>& X : F->GetArrayField(TEXT("j"))) Fr.J.Add(float(X->AsNumber()));
			const TArray<TSharedPtr<FJsonValue>>& Ct = F->GetArrayField(TEXT("contact"));
			if (Ct.Num() >= 2) { Fr.bContactL = Ct[0]->AsBool(); Fr.bContactR = Ct[1]->AsBool(); }
			Clip.Frames.Add(MoveTemp(Fr));
		}
		Clips.Add(Clip.Name, MoveTemp(Clip));
	}
	return IsValid();
}

FIVPoseAngles FIVRigData::SampleClip(const FIVClip& Clip, float T, bool bLoop) const
{
	FIVPoseAngles R;
	const int32 N = Clip.Frames.Num();
	if (N == 0) return R;
	float F = T * Clip.Fps;
	int32 A, B;
	float Alpha;
	if (bLoop)
	{
		F = FMath::Fmod(F, float(N));
		if (F < 0.f) F += N;
		A = FMath::FloorToInt(F) % N;
		B = (A + 1) % N;
		Alpha = F - FMath::FloorToInt(F);
	}
	else
	{
		F = FMath::Clamp(F, 0.f, float(N - 1));
		A = FMath::FloorToInt(F);
		B = FMath::Min(A + 1, N - 1);
		Alpha = F - A;
	}
	const FIVClipFrame& Fa = Clip.Frames[A];
	const FIVClipFrame& Fb = Clip.Frames[B];
	for (int32 i = 0; i < BoneOrder.Num(); ++i)
	{
		const int32 k = i * 3;
		if (k + 2 >= Fa.J.Num() || k + 2 >= Fb.J.Num()) break;
		R.Joint.Add(BoneOrder[i], FMath::Lerp(FVector(Fa.J[k], Fa.J[k + 1], Fa.J[k + 2]), FVector(Fb.J[k], Fb.J[k + 1], Fb.J[k + 2]), Alpha));
	}
	R.RootPosM = FMath::Lerp(Fa.RootPosM, Fb.RootPosM, Alpha);
	R.RootRotDeg = FMath::Lerp(Fa.RootRotDeg, Fb.RootRotDeg, Alpha);
	return R;
}

// ---------------------------------------------------------------------------------------------------------------
FQuat FIVRigDriver::DeltaToUE(const FVector& Deg)
{
	// FBX exported by Blender imports into Unreal WITHOUT an axis rotation, only the handedness flip: x_u = x_b, y_u = -y_b, z_u = z_b
	// (the mech then faces +Y_u; the pawn rotates the mesh component by -90 deg yaw to face +X).
	// The flip is a reflection, so a rotation about axis a by t becomes a rotation about M*a by -t:
	//   Rx_b(t) -> about +X_u by -t     Ry_b(t) -> about +Y_u by +t     Rz_b(t) -> about +Z_u by -t
	const float Rx = FMath::DegreesToRadians(Deg.X), Ry = FMath::DegreesToRadians(Deg.Y), Rz = FMath::DegreesToRadians(Deg.Z);
	const FQuat Qx(FVector(1, 0, 0), -Rx);
	const FQuat Qy(FVector(0, 1, 0), Ry);
	const FQuat Qz(FVector(0, 0, 1), -Rz);
	return Qz * Qy * Qx;
}

bool FIVRigDriver::Init(USkeletalMesh* SM)
{
	RestComp.Reset(); Names.Reset(); Parent.Reset(); Index.Reset();
	if (!SM) return false;
	const FReferenceSkeleton& RS = SM->GetRefSkeleton();
	const TArray<FTransform>& Local = RS.GetRefBonePose();
	const int32 N = RS.GetNum();
	RestComp.SetNum(N);
	for (int32 i = 0; i < N; ++i)
	{
		Names.Add(RS.GetBoneName(i));
		Parent.Add(RS.GetParentIndex(i));
		Index.Add(Names[i], i);
		RestComp[i] = (Parent[i] >= 0) ? Local[i] * RestComp[Parent[i]] : Local[i];
	}
	return true;
}

void FIVRigDriver::Compute(const FIVPoseAngles& Pose, TArray<FTransform>& OutLocal) const
{
	const int32 N = Names.Num();
	OutLocal.SetNum(N);
	TArray<FQuat> W;        // world-aligned posed rotation of each bone
	TArray<FTransform> Comp;
	W.SetNum(N); Comp.SetNum(N);

	const FVector RootOffset(Pose.RootPosM.X * 100.0, -Pose.RootPosM.Y * 100.0, Pose.RootPosM.Z * 100.0);
	const FQuat RootRot = DeltaToUE(Pose.RootRotDeg);

	for (int32 i = 0; i < N; ++i)
	{
		const int32 Pi = Parent[i];
		FQuat D = FQuat::Identity;
		if (const FVector* J = Pose.Joint.Find(Names[i])) D = DeltaToUE(*J);
		else if (Pi < 0) D = RootRot;
		FVector P;
		if (Pi < 0)
		{
			W[i] = D;
			P = RestComp[i].GetLocation() + RootOffset;
		}
		else
		{
			W[i] = W[Pi] * D;
			P = Comp[Pi].GetLocation() + W[Pi].RotateVector(RestComp[i].GetLocation() - RestComp[Pi].GetLocation());
		}
		Comp[i] = FTransform(W[i] * RestComp[i].GetRotation(), P, RestComp[i].GetScale3D());   // keep the import unit scale (x100)
		OutLocal[i] = (Pi >= 0) ? Comp[i] * Comp[Pi].Inverse() : Comp[i];
	}
}
