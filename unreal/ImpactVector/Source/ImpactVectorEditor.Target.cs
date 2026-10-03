using UnrealBuildTool;
using System.Collections.Generic;

public class ImpactVectorEditorTarget : TargetRules
{
	public ImpactVectorEditorTarget(TargetInfo Target) : base(Target)
	{
		Type = TargetType.Editor;
		DefaultBuildSettings = BuildSettingsVersion.Latest;
		IncludeOrderVersion = EngineIncludeOrderVersion.Latest;
		ExtraModuleNames.Add("ImpactVector");
	}
}
