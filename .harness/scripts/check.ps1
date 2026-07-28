[CmdletBinding()]
param(
    [ValidateSet("Lint", "Test", "Full")]
    [string]$Mode = "Full"
)

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
    throw "uv is required. Run .harness/scripts/bootstrap.ps1 after installing uv."
}

Push-Location $RepoRoot
try {
    if ($Mode -in @("Lint", "Full")) {
        Invoke-Checked -Label "Ruff format check" -Arguments @("run", "ruff", "format", "--check", ".")
        Invoke-Checked -Label "Ruff lint" -Arguments @("run", "ruff", "check", ".")
    }

    if ($Mode -in @("Test", "Full")) {
        Invoke-Checked -Label "Offline test suite" -Arguments @(
            "run", "pytest", "--basetemp", ".pytest-tmp"
        )
    }
}
finally {
    Pop-Location
}

Write-Host "Harness checks passed ($Mode)."
