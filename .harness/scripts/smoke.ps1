[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$InputPdf,

    [string]$OutputJson,

    [ValidateRange(1, 3600)]
    [int]$TimeoutSeconds = 180,

    [ValidateRange(1, 8)]
    [int]$Concurrency = 1
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$SmokeRoot = [System.IO.Path]::GetFullPath((Join-Path $RepoRoot "output\smoke"))
$ResolvedInput = (Resolve-Path $InputPdf).Path

if ([System.IO.Path]::GetExtension($ResolvedInput) -ne ".pdf") {
    throw "InputPdf must point to a PDF file."
}

if (-not $OutputJson) {
    $Stem = [System.IO.Path]::GetFileNameWithoutExtension($ResolvedInput)
    $OutputJson = Join-Path $SmokeRoot "${Stem}_harness_result.json"
}
elseif (-not [System.IO.Path]::IsPathRooted($OutputJson)) {
    $OutputJson = Join-Path $RepoRoot $OutputJson
}

$ResolvedOutput = [System.IO.Path]::GetFullPath($OutputJson)
$SmokePrefix = $SmokeRoot.TrimEnd("\") + "\"
if (-not $ResolvedOutput.StartsWith($SmokePrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Smoke output must stay under $SmokeRoot to protect user samples."
}

New-Item -ItemType Directory -Force $SmokeRoot | Out-Null

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

Push-Location $RepoRoot
try {
    Invoke-Checked -Label "PaddleX health check" -Arguments @("run", "pdf-parser", "health")
    Invoke-Checked -Label "Parse smoke PDF" -Arguments @(
        "run", "pdf-parser", "parse", $ResolvedInput,
        "-o", $ResolvedOutput,
        "--timeout", $TimeoutSeconds,
        "--concurrency", $Concurrency
    )
    Invoke-Checked -Label "Validate output contract" -Arguments @(
        "run", "python", ".harness\scripts\validate_result.py", $ResolvedOutput
    )
}
finally {
    Pop-Location
}

Write-Host "Smoke test passed: $ResolvedOutput"
