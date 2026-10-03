# Copies generated data (worldgen) into the Unreal project's Content/Data. Run after regenerating the district.
$repo = 'F:\Проекты\IMPACT_VECTOR'
New-Item -ItemType Directory -Force 'F:\IVUnreal\Content\Data' | Out-Null
Copy-Item "$repo\worldgen\out\district.json" 'F:\IVUnreal\Content\Data\' -Force
Copy-Item "$repo\worldgen\out\heightmap.r16" 'F:\IVUnreal\Content\Data\' -Force
"synced"
