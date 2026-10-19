# Install only. The user owns shutdown/rebuild/relaunch from an external terminal.
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $PSScriptRoot))
$evidence = Join-Path $projectRoot 'Saved/VibeUE/ProneMeshProbeAnchors'
$manifest = Get-Content -LiteralPath (Join-Path $evidence 'manifest.json') -Raw | ConvertFrom-Json
$engineSource = 'C:/Program Files/Epic Games/UE_5.8/Engine/Plugins/Experimental/Mover/Source/Mover'
$allowed = @('Public/DefaultMovementSet/CharacterMoverComponent.h', 'Private/DefaultMovementSet/CharacterMoverComponent.cpp', 'Private/MoveLibrary/ProneFloorTraceUtils.cpp')
# Validate every file before writing any source.
foreach ($entry in $manifest.files) {
    if ($entry.relativePath -notin $allowed) { throw 'Unexpected target in manifest.' }
    $target = Join-Path $engineSource $entry.relativePath
    $source = Join-Path (Join-Path $PSScriptRoot 'Source') $entry.relativePath
    if ((Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash.ToLowerInvariant() -ne $entry.beforeSha256) { throw "Source changed since staging: $target" }
    if ((Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash.ToLowerInvariant() -ne $entry.afterSha256) { throw "Staged file changed: $source" }
}
foreach ($entry in $manifest.files) {
    $target = Join-Path $engineSource $entry.relativePath
    $source = Join-Path (Join-Path $PSScriptRoot 'Source') $entry.relativePath
    Copy-Item -LiteralPath $source -Destination $target -Force
    if ((Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash.ToLowerInvariant() -ne $entry.afterSha256) { throw "Installed hash mismatch: $target" }
    Write-Output "MODIFIED: $target"
}
$manifest.status = 'installed-awaiting-user-build'
$manifest | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $evidence 'manifest.json') -Encoding utf8
Write-Output 'Source installed. Unreal was not closed and no build was started.'
