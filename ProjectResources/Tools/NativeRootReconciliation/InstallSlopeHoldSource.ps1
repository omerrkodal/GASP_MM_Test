# Install reviewed source only. The user owns editor shutdown, rebuild and restart.
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $PSScriptRoot))
$evidenceRoot = Join-Path $projectRoot 'Saved/VibeUE/NativeRootReconciliation/slope-hold-v2'
$pythonPath = 'C:/Program Files/Epic Games/UE_5.8/Engine/Binaries/ThirdParty/Python3/Win64/python.exe'
$state = 'failed'
$message = 'Source installation failed; inspect install.log.'
try {
    & $pythonPath (Join-Path $PSScriptRoot 'StageAndInstall.py') --revision slope-hold-v2 --install *> (Join-Path $evidenceRoot 'install.log')
    if ($LASTEXITCODE -ne 0) { throw $message }
    $state = 'installed-awaiting-user-build'
    $message = 'Slope-hold source installed. No editor shutdown, rebuild, restart or Blueprint mutation was performed.'
} catch {
    $message = $_.Exception.Message
} finally {
    @{status=$state; message=$message; updatedUtc=[DateTime]::UtcNow.ToString('o')} |
        ConvertTo-Json | Set-Content -LiteralPath (Join-Path $evidenceRoot 'source-install-status.json') -Encoding utf8
}
if ($state -eq 'failed') { exit 1 }
