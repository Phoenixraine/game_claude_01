param([switch]$Materials)
# Rebuilds the C++ editor target; optionally regenerates procedural materials first.
$ErrorActionPreference = 'Continue'
if ($Materials) {
    $ue = 'E:\epic games\UE_5.8\Engine\Binaries\Win64\UnrealEditor-Cmd.exe'
    $log = 'F:\IVUnreal\Saved\mat_build.log'
    $p = Start-Process -FilePath $ue -ArgumentList @('F:\IVUnreal\ImpactVector.uproject', '-ExecutePythonScript=F:\IVUnreal\Scripts\build_materials.py', '-unattended', '-nosplash', '-stdout', '-FullStdOutLogOutput') -RedirectStandardOutput $log -PassThru -NoNewWindow
    $p.WaitForExit(900000) | Out-Null
    Select-String -Path $log -Pattern 'IV material|Traceback|FAILED' | ForEach-Object { $_.Line }
}
$bl = 'F:\IVUnreal\Saved\build.log'
& 'E:\epic games\UE_5.8\Engine\Build\BatchFiles\Build.bat' ImpactVectorEditor Win64 Development '-Project=F:\IVUnreal\ImpactVector.uproject' -WaitMutex -NoHotReload *> $bl
Select-String -Path $bl -Pattern 'error|Result' | ForEach-Object { $_.Line }
