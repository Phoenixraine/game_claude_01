# Copies the combat core (repo root /core) into the Unreal module so UBT compiles it. Run after merging core changes.
$proj = (Get-Item 'F:\IVUnreal').Target
if ($proj -is [array]) { $proj = $proj[0] }
$repo = Split-Path (Split-Path $proj -Parent) -Parent    # ...\unreal\ImpactVector -> repo root
$dst = 'F:\IVUnreal\Source\ImpactVector\IVCore'
Remove-Item -Recurse -Force $dst -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force "$dst\include\iv" | Out-Null
New-Item -ItemType Directory -Force "$dst\src" | Out-Null
Copy-Item "$repo\core\include\iv\*" "$dst\include\iv\" -Force
Copy-Item "$repo\core\src\*.cpp" "$dst\src\" -Force
"synced core from $repo : " + (Get-ChildItem "$dst\src").Count + " sources"
