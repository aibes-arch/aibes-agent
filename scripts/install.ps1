#Requires -Version 5.1
<#
.SYNOPSIS
    aibes-agent one-click install / update script

.DESCRIPTION
    - Checks Python >= 3.11
    - Optionally runs git pull to update source
    - Creates/updates .venv virtual environment
    - Installs/updates aibes-agent with optional extras

.PARAMETER NoGitPull
    Skip the git pull step

.PARAMETER Extras
    Optional extras to install. Default: dev,cli,web,mcp,drilling,code_review,documents

.EXAMPLE
    .\scripts\install.ps1
    .\scripts\install.ps1 -NoGitPull
    .\scripts\install.ps1 -Extras "dev,web,mcp"
#>
param(
    [switch]$NoGitPull,
    [string]$Extras = "dev,cli,web,mcp,drilling,code_review,documents"
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

function Test-PythonVersion {
    $python = Get-Command python -ErrorAction SilentlyContinue
    if (-not $python) {
        $python = Get-Command python3 -ErrorAction SilentlyContinue
    }
    if (-not $python) {
        Write-Host "[ERROR] python or python3 not found. Please install Python 3.11+." -ForegroundColor Red
        exit 1
    }

    $versionString = & $python.Source --version 2>&1
    if ($versionString -is [System.Management.Automation.ErrorRecord]) {
        $versionString = $versionString.TargetObject
    }
    $versionString = $versionString.ToString().Trim()
    Write-Host "[INFO] Found: $versionString" -ForegroundColor Cyan

    if ($versionString -notmatch "Python\s+(\d+)\.(\d+)") {
        Write-Host "[ERROR] Cannot parse Python version: $versionString" -ForegroundColor Red
        exit 1
    }

    $major = [int]$matches[1]
    $minor = [int]$matches[2]

    if ($major -lt 3 -or ($major -eq 3 -and $minor -lt 11)) {
        Write-Host "[ERROR] Python >= 3.11 required, found $major.$minor" -ForegroundColor Red
        exit 1
    }

    return $python.Source
}

function Update-SourceCode {
    if ($NoGitPull) {
        Write-Host "[INFO] Skipping git pull (-NoGitPull)" -ForegroundColor Cyan
        return
    }

    if (-not (Test-Path .git)) {
        Write-Host "[INFO] Not a git repository, skipping git pull" -ForegroundColor Cyan
        return
    }

    $git = Get-Command git -ErrorAction SilentlyContinue
    if (-not $git) {
        Write-Host "[WARN] git not found, skipping source update" -ForegroundColor Yellow
        return
    }

    Write-Host "[INFO] Pulling latest source..." -ForegroundColor Cyan
    & $git.Source pull
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[WARN] git pull failed, continuing with current source" -ForegroundColor Yellow
    }
}

function Install-Project {
    param([string]$PythonExe)

    $venvPath = Join-Path $projectRoot ".venv"
    $venvPython = Join-Path $venvPath "Scripts\python.exe"

    if (-not (Test-Path $venvPath)) {
        Write-Host "[INFO] Creating virtual environment .venv..." -ForegroundColor Cyan
        & $PythonExe -m venv $venvPath
        if ($LASTEXITCODE -ne 0) {
            Write-Host "[ERROR] Failed to create virtual environment" -ForegroundColor Red
            exit 1
        }
    }
    else {
        Write-Host "[INFO] Virtual environment .venv already exists" -ForegroundColor Cyan
    }

    Write-Host "[INFO] Upgrading pip..." -ForegroundColor Cyan
    & $venvPython -m pip install --upgrade pip | Out-Host
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[WARN] pip upgrade failed, continuing anyway" -ForegroundColor Yellow
    }

    $installSpec = ".[$Extras]"
    Write-Host "[INFO] Installing/updating: $installSpec" -ForegroundColor Cyan
    & $venvPython -m pip install -e $installSpec | Out-Host
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] Installation failed" -ForegroundColor Red
        exit 1
    }

    return $venvPath
}

function Show-Success {
    param([string]$VenvPath)

    Write-Host "`n[SUCCESS] aibes-agent installed/updated!" -ForegroundColor Green
    Write-Host "  Virtual env: $VenvPath" -ForegroundColor Green
    Write-Host "  Next steps:" -ForegroundColor Green
    Write-Host "    .\scripts\run.ps1              # Run default demo" -ForegroundColor Green
    Write-Host "    .\scripts\run.ps1 <script.py>  # Run a custom script" -ForegroundColor Green
    Write-Host "    .\scripts\run-web.ps1          # Start Web UI" -ForegroundColor Green
    Write-Host "    aibes-agent --help              # Show CLI help" -ForegroundColor Green
}

Write-Host "===================================" -ForegroundColor Blue
Write-Host "  aibes-agent install / update" -ForegroundColor Blue
Write-Host "===================================" -ForegroundColor Blue

$pythonExe = Test-PythonVersion
Update-SourceCode
$venvPath = Install-Project -PythonExe $pythonExe
Show-Success -VenvPath $venvPath
