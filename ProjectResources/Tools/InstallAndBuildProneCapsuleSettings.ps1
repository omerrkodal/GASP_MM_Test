$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$pythonPath = 'C:/Program Files/Epic Games/UE_5.8/Engine/Binaries/ThirdParty/Python3/Win64/python.exe'
$evidenceRoot = Join-Path $projectRoot 'Saved/VibeUE/ProneCapsuleSettings-20261015'
$statusPath = Join-Path $evidenceRoot 'install-build-status.json'
function Write-TaskStatus($state, $message) {
    @{ status=$state; message=$message; updatedUtc=[DateTime]::UtcNow.ToString('o') } |
        ConvertTo-Json | Set-Content -LiteralPath $statusPath -Encoding utf8
}
try {
    Write-TaskStatus 'installing' 'Installing the reviewed incremental patch.'
    & $pythonPath (Join-Path $PSScriptRoot 'StageProneCapsuleSettings.py') --install *> (Join-Path $evidenceRoot 'install.log')
    if ($LASTEXITCODE -ne 0) { throw 'Source installation failed; inspect install.log.' }
    Write-TaskStatus 'waiting_for_editor' 'Waiting for editor shutdown before native build.'
    & $pythonPath (Join-Path $PSScriptRoot 'RebuildGlobalMover.py') --wait-for-close 180 *> (Join-Path $evidenceRoot 'build-launcher.log')
    if ($LASTEXITCODE -ne 0) { throw 'Native rebuild failed; inspect build-launcher.log and last-build.json.' }
    Write-TaskStatus 'succeeded' 'Source installed and native rebuild succeeded.'
} catch {
    Write-TaskStatus 'failed' $_.Exception.Message
    exit 1
}
