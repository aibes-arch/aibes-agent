#Requires -Version 5.1
<#
.SYNOPSIS
    aibes-agent one-click run script

.DESCRIPTION
    - Activates the .venv virtual environment
    - Calls install.ps1 automatically if .venv is missing
    - Runs examples/readme_demo.py by default
    - Accepts a custom script path and extra arguments

.PARAMETER Script
    Path to the Python script to run. Default: examples/readme_demo.py

.PARAMETER Args
    Extra arguments passed to the script

.PARAMETER YesToAll
    Auto-allow all permission prompts (same as --yes-to-all)

.PARAMETER Config
    Path to aibes-agent.yaml config file

.PARAMETER Install
    Force install/update before running

.EXAMPLE
    .\scripts\run.ps1
    .\scripts\run.ps1 examples/planner_demo.py
    .\scripts\run.ps1 -YesToAll
    .\scripts\run.ps1 -Config aibes-agent.yaml
#>
param(
    [Parameter(Position = 0)]
    [string]$Script = "examples/readme_demo.py",

    [Parameter(Position = 1, ValueFromRemainingArguments = $true)]
    [string[]]$Args,

    [switch]$YesToAll,
    [string]$Config = "",
    [switch]$Install
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

$venvPath = Join-Path $projectRoot ".venv"
$venvActivate = Join-Path $venvPath "Scripts\Activate.ps1"

function Invoke-Install {
    $installScript = Join-Path $PSScriptRoot "install.ps1"
    if (-not (Test-Path $installScript)) {
        Write-Host "[ERROR] install.ps1 not found, cannot auto-install" -ForegroundColor Red
        exit 1
    }
    Write-Host "[INFO] Virtual environment missing, starting install..." -ForegroundColor Cyan
    & $installScript
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}

if ($Install -or -not (Test-Path $venvPath)) {
    Invoke-Install
}

if (-not (Test-Path $venvActivate)) {
    Write-Host "[ERROR] Virtual environment activate script missing: $venvActivate" -ForegroundColor Red
    exit 1
}

Write-Host "[INFO] Activating virtual environment..." -ForegroundColor Cyan
& $venvActivate

$cmdArgs = @("run", $Script)
if ($YesToAll) {
    $cmdArgs += "--yes-to-all"
}
if ($Config) {
    $cmdArgs += @("--config", $Config)
}
if ($Args) {
    $cmdArgs += $Args
}

Write-Host "[INFO] Running: aibes-agent $cmdArgs" -ForegroundColor Cyan
& aibes-agent @cmdArgs

$exitCode = $LASTEXITCODE

if (Get-Command deactivate -ErrorAction SilentlyContinue) {
    deactivate
}

exit $exitCode
