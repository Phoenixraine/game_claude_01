$cfgs = [ordered]@{
 'A_baseline'   = ''
 'B_noLumenGI'  = 'r.DynamicGlobalIlluminationMethod 0;r.ReflectionMethod 2'
 'C_noClouds'   = 'r.VolumetricCloud 0'
 'D_noVolFog'   = 'r.VolumetricFog 0'
 'E_noVSM'      = 'r.Shadow.Virtual.Enable 0'
}
foreach ($k in $cfgs.Keys) {
  $logp = 'F:\IVUnreal\Saved\Logs\ImpactVector.log'
  $t0 = Get-Date
  $out = & powershell -NoProfile -ExecutionPolicy Bypass -File F:\IVUnreal\Scripts\run_game.ps1 -GameArgs "-IVCam=2 -IVAuto -IVQuit=25" -Cvars $cfgs[$k] -TimeoutSec 200
  $secs = [int]((Get-Date) - $t0).TotalSeconds
  $frames = (Select-String -Path $logp -Pattern 'RequestExit\(0, UGameEngine::HandleExitCommand\)' | Select -First 1).Line
  $fr = if ($frames -match '\]\[\s*(\d+)\]') { $matches[1] } else { '?' }
  "{0,-14} wall={1,3}s frame@exit={2,5} {3}" -f $k, $secs, $fr, ($out -join ' ')
}
