using UnrealBuildTool;
using System.Collections.Generic;

public class ImpactVectorTarget : TargetRules
{
	public ImpactVectorTarget(TargetInfo Target) : base(Target)
	{
		Type = TargetType.Game;
		DefaultBuildSettings = BuildSettingsVersion.Latest;
		IncludeOrderVersion = EngineIncludeOrderVersion.Latest;
		ExtraModuleNames.Add("ImpactVector");
	}
}
