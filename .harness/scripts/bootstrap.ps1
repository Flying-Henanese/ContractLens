[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path

function Invoke-Checked {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Label,
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    Write-Host "==> $Label"
    & uv @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Label failed with exit code $LASTEXITCODE"
    }
}

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw "uv is required. Install uv and ensure it is available on PATH."
}

Push-Location $RepoRoot
try {
    Invoke-Checked -Label "Sync dependencies" -Arguments @("sync")
    Invoke-Checked -Label "Verify CLI entry point" -Arguments @("run", "pdf-parser", "--help")
}
finally {
    Pop-Location
}

Write-Host "Harness bootstrap completed."
