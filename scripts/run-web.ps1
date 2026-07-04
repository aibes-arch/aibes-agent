#Requires -Version 5.1
<#
.SYNOPSIS
    aibes-agent one-click Web UI startup script

.DESCRIPTION
    - Activates the .venv virtual environment
    - Calls install.ps1 automatically if .venv is missing
    - Starts the FastAPI + SSE Web UI

.PARAMETER Config
    Path to aibes-agent.yaml config file

.PARAMETER Host
    Bind host. Defaults to config value.

.PARAMETER Port
    Bind port. Defaults to config value.

.PARAMETER Install
    Force install/update before starting

.EXAMPLE
    .\scripts\run-web.ps1
    .\scripts\run-web.ps1 -Host 0.0.0.0 -Port 8080
    .\scripts\run-web.ps1 -Config aibes-agent.yaml
#>
param(
    [string]$Config = "",
    [string]$Host = "",
    [int]$Port = 0,
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

$cmdArgs = @("web")
if ($Config) {
    $cmdArgs += @("--config", $Config)
}
if ($Host) {
    $cmdArgs += @("--host", $Host)
}
if ($Port -gt 0) {
    $cmdArgs += @("--port", $Port)
}

Write-Host "[INFO] Starting Web UI: aibes-agent $cmdArgs" -ForegroundColor Cyan
& aibes-agent @cmdArgs

$exitCode = $LASTEXITCODE

if (Get-Command deactivate -ErrorAction SilentlyContinue) {
    deactivate
}

exit $exitCode
