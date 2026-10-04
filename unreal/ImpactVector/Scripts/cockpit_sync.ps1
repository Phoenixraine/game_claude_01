# Copies the cockpit v3 export from the repo (through the F:\IVRepo junction) into the Unreal project and imports the meshes.
$o = 'F:\IVRepo\art\cockpit\v3\out'
New-Item -ItemType Directory -Force F:\IVUnreal\Content\Source\CockpitV3 | Out-Null
Get-ChildItem $o -Filter *.fbx | ForEach-Object { Copy-Item $_.FullName F:\IVUnreal\Content\Source\CockpitV3\ -Force }
Copy-Item "$o\cockpit_layout.json" F:\IVUnreal\Content\Data\cockpit_layout.json -Force
$f = (Get-ChildItem F:\IVUnreal\Content\Source\CockpitV3 -Filter *.fbx | ForEach-Object { $_.FullName }) -join ' '
& F:\IVUnreal\Scripts\ue_py.ps1 -Script F:\IVUnreal\Scripts\import_static.py -ScriptArgs "Cockpit/V3 $f" -Pattern 'Traceback'
"imported"
