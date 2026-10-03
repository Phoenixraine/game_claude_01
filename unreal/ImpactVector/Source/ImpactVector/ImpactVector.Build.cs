using UnrealBuildTool;

public class ImpactVector : ModuleRules
{
	public ImpactVector(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
		PublicDependencyModuleNames.AddRange(new string[] {
			"Core", "CoreUObject", "Engine", "InputCore", "EnhancedInput", "UMG", "Slate", "SlateCore", "Niagara", "Json", "JsonUtilities", "ProceduralMeshComponent"
		});
	}
}
