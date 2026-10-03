param([string]$GameArgs = "", [int]$TimeoutSec = 400, [string]$Cvars = "")
$ue='E:\epic games\UE_5.8\Engine\Binaries\Win64\UnrealEditor.exe'
Remove-Item 'F:\IVUnreal\Saved\Screenshots' -Recurse -Force -ErrorAction SilentlyContinue
$a = @('F:\IVUnreal\ImpactVector.uproject','-game','-windowed','-ResX=1600','-ResY=900','-log','-nosplash','-unattended') + ($GameArgs -split ' ' | ? { $_ })
if ($Cvars) { $a += "-ExecCmds=$Cvars" }
$p = Start-Process -FilePath $ue -ArgumentList $a -PassThru
if (-not $p.WaitForExit($TimeoutSec * 1000)) { $p.Kill(); "killed (timeout)" }
$crash = Select-String -Path 'F:\IVUnreal\Saved\Logs\ImpactVector.log' -Pattern 'TerminateOnGPUCrash' -Quiet
"gpu_crash=$crash"
Get-ChildItem 'F:\IVUnreal\Saved\Screenshots\WindowsEditor' -ErrorAction SilentlyContinue | % { $_.Name }
