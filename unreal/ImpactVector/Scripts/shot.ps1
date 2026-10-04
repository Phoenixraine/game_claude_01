param([string]$Name = 'x', [string]$GameArgs = '', [string]$Cvars = '', [int]$Timeout = 150)
# Runs the game with the given args and copies the screenshots to Saved\shots\<Name>_N.png
& 'F:\IVUnreal\Scripts\run_game.ps1' -GameArgs $GameArgs -Cvars $Cvars -TimeoutSec $Timeout | Out-Null
New-Item -ItemType Directory -Force 'F:\IVUnreal\Saved\shots' | Out-Null
$i = 0
Get-ChildItem 'F:\IVUnreal\Saved\Screenshots\WindowsEditor' -Filter *.png -ErrorAction SilentlyContinue | Sort-Object Name | ForEach-Object {
    $dst = "F:\IVUnreal\Saved\shots\${Name}_$i.png"; Copy-Item $_.FullName $dst -Force; $dst; $i++ }
