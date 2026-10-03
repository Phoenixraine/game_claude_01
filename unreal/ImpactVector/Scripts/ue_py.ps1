param([Parameter(Mandatory=$true)][string]$Script, [string]$ScriptArgs = "", [string]$Pattern = 'IV |Traceback|Error: .*Python')
# Runs an editor Python script headless:  ue_py.ps1 -Script F:\IVUnreal\Scripts\import_static.py -ScriptArgs "Cockpit a.fbx b.fbx"
$ue = 'E:\epic games\UE_5.8\Engine\Binaries\Win64\UnrealEditor-Cmd.exe'
$log = 'F:\IVUnreal\Saved\ue_py.log'
$cmd = if ($ScriptArgs) { "$Script $ScriptArgs" } else { $Script }
$p = Start-Process -FilePath $ue -ArgumentList @('F:\IVUnreal\ImpactVector.uproject', "-ExecutePythonScript=`"$cmd`"", '-unattended', '-nosplash', '-stdout', '-FullStdOutLogOutput') -RedirectStandardOutput $log -PassThru -NoNewWindow
$p.WaitForExit(900000) | Out-Null
Select-String -Path $log -Pattern $Pattern | ForEach-Object { $_.Line }
