param([int]$W=3440,[int]$H=1440,[string]$Extra="",[int]$Quit=34,[string]$Cvars="")
$ue='E:\epic games\UE_5.8\Engine\Binaries\Win64\UnrealEditor.exe'
Remove-Item 'F:\IVUnreal\Saved\Screenshots' -Recurse -Force -ErrorAction SilentlyContinue
$a=@('F:\IVUnreal\ImpactVector.uproject','-game','-windowed',"-ResX=$W","-ResY=$H",'-log','-nosplash','-unattended','-IVStart=duel',"-IVQuit=$Quit",'-IVNoAudio','-IVAutoFight') + ($Extra -split ' ' | ? { $_ })
if($Cvars){$a += ('-ExecCmds="' + $Cvars + '"')}
$p=Start-Process $ue -ArgumentList $a -PassThru
if(-not $p.WaitForExit(300000)){$p.Kill()}
Select-String -Path 'F:\IVUnreal\Saved\Logs\ImpactVector.log' -Pattern 'IV perf' | Select -Last 8 | % { $_.Line.Substring(22) }
