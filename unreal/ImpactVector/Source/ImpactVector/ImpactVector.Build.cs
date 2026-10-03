using UnrealBuildTool;

public class ImpactVector : ModuleRules
{
	public ImpactVector(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
		PublicIncludePaths.Add(System.IO.Path.Combine(ModuleDirectory, "IVCore", "include"));   // combat core (core/, synced by Scripts/sync_core.ps1)
		PublicDependencyModuleNames.AddRange(new string[] {
			"Core", "CoreUObject", "Engine", "InputCore", "EnhancedInput", "UMG", "Slate", "SlateCore", "Niagara", "Json", "JsonUtilities", "ProceduralMeshComponent"
		});
	}
}
