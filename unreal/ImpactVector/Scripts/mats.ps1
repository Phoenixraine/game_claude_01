param([string]$Only = '')
# Rebuilds the procedural materials (optionally only the named builders, comma separated) with the headless editor.
if ($Only) { $env:IV_ONLY = $Only } else { Remove-Item Env:IV_ONLY -ErrorAction SilentlyContinue }
$ue = 'E:\epic games\UE_5.8\Engine\Binaries\Win64\UnrealEditor-Cmd.exe'
$log = 'F:\IVUnreal\Saved\mat_build.log'
$p = Start-Process -FilePath $ue -ArgumentList @('F:\IVUnreal\ImpactVector.uproject', '-ExecutePythonScript=F:\IVUnreal\Scripts\build_materials.py', '-unattended', '-nosplash', '-stdout', '-FullStdOutLogOutput') -RedirectStandardOutput $log -PassThru -NoNewWindow
$p.WaitForExit(900000) | Out-Null
Select-String -Path $log -Pattern 'IV material|Traceback|LogPython: Error|HLSL|error X|\(\d+,\d+\)' | ForEach-Object { $_.Line.Substring([Math]::Min(30, $_.Line.Length)) } | Select-Object -First 40
