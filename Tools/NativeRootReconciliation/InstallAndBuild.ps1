$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$evidenceRoot = Join-Path $projectRoot 'Saved/VibeUE/NativeRootReconciliation'
$statusPath = Join-Path $evidenceRoot 'install-build-status.json'
$pythonPath = 'C:/Program Files/Epic Games/UE_5.8/Engine/Binaries/ThirdParty/Python3/Win64/python.exe'
function Write-TaskStatus($state, $message) {
    @{status=$state; message=$message; updatedUtc=[DateTime]::UtcNow.ToString('o')} |
        ConvertTo-Json | Set-Content -LiteralPath $statusPath -Encoding utf8
}
try {
    Write-TaskStatus 'installing' 'Installing the staged, hash-checked native reconciliation patch.'
    & $pythonPath (Join-Path $PSScriptRoot 'StageAndInstall.py') --install *> (Join-Path $evidenceRoot 'install.log')
    if ($LASTEXITCODE -ne 0) { throw 'Source installation failed; inspect install.log.' }
    Write-TaskStatus 'building' 'Building the global Mover plugin with the editor closed.'
    & $pythonPath (Join-Path $projectRoot 'Tools/RebuildGlobalMover.py') --wait-for-close 180 *> (Join-Path $evidenceRoot 'build-launcher.log')
    if ($LASTEXITCODE -ne 0) { throw 'Build failed; inspect build-launcher.log and Saved/VibeUE/last-build.json.' }
    Write-TaskStatus 'succeeded' 'Native build succeeded. Ready to reopen the editor.'
} catch {
    Write-TaskStatus 'failed' $_.Exception.Message
    exit 1
}
