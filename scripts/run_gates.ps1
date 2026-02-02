# NGK's Download Manager V3.1 Gate Runner
# Fast gate execution with core dependencies only
# Universal Agent Ruleset: ASCII output only, no placeholders, docs in /docs

param(
    [switch]$CleanVenv = $false,
    [switch]$Verbose = $false
)

$ErrorActionPreference = "Stop"

Write-Host "NGK's DL Manager V3.1 - Fast Gate Execution (Core Dependencies)" -ForegroundColor Green
Write-Host "================================================================" -ForegroundColor Green

# Project root detection
$ProjectRoot = Split-Path $PSScriptRoot -Parent
if (-not (Test-Path "$ProjectRoot\requirements-core.txt")) {
    Write-Host "ERROR: requirements-core.txt not found in project root: $ProjectRoot" -ForegroundColor Red
    exit 1
}

Write-Host "Project Root: $ProjectRoot" -ForegroundColor Cyan
Set-Location $ProjectRoot

# Virtual environment path
$VenvPath = ".\.venv"

# Clean venv if requested
if ($CleanVenv -and (Test-Path $VenvPath)) {
    Write-Host "Cleaning existing virtual environment..." -ForegroundColor Yellow
    Remove-Item $VenvPath -Recurse -Force
    Write-Host "Virtual environment cleaned." -ForegroundColor Green
}

# Create/activate virtual environment
if (-not (Test-Path $VenvPath)) {
    Write-Host "Creating new virtual environment..." -ForegroundColor Yellow
    python -m venv $VenvPath
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Failed to create virtual environment" -ForegroundColor Red
        exit 1
    }
    Write-Host "Virtual environment created." -ForegroundColor Green
} else {
    Write-Host "Using existing virtual environment." -ForegroundColor Cyan
}

# Activate virtual environment
Write-Host "Activating virtual environment..." -ForegroundColor Yellow
& "$VenvPath\Scripts\Activate.ps1"

# Verify Python environment
$PythonVersion = python --version 2>&1
Write-Host "Python Version: $PythonVersion" -ForegroundColor Cyan

# Install core dependencies only
Write-Host "Installing core gate dependencies (fast)..." -ForegroundColor Yellow
pip install -r requirements-core.txt
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to install core dependencies" -ForegroundColor Red
    exit 1
}
Write-Host "Core dependencies installed successfully." -ForegroundColor Green

# Verify core dependencies only
Write-Host "Verifying core dependency installation..." -ForegroundColor Yellow
$InstalledPackages = pip list --format=freeze
if ($Verbose) {
    Write-Host "Installed packages:" -ForegroundColor Cyan
    $InstalledPackages | ForEach-Object { Write-Host "  $_" -ForegroundColor Gray }
}

# Verify requests dependency specifically
python -c "import requests; print(f'requests version: {requests.__version__}')"
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: requests import failed" -ForegroundColor Red
    exit 1
}
Write-Host "Core dependency verification passed." -ForegroundColor Green

# Gate 1: V2.1 Acceptance Tests
Write-Host ""
Write-Host "GATE 1: V2.1 Acceptance Tests (Regression Prevention)" -ForegroundColor Yellow
Write-Host "----------------------------------------------------" -ForegroundColor Yellow
python -u test_v21_acceptance.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "GATE 1 FAILED: V2.1 acceptance tests failed" -ForegroundColor Red
    exit 1
}
Write-Host "GATE 1 PASSED: V2.1 acceptance tests successful" -ForegroundColor Green

# Gate 2: V2.4 Bandwidth Limiting Tests
Write-Host ""
Write-Host "GATE 2: V2.4 Bandwidth Limiting Tests (Feature Validation)" -ForegroundColor Yellow
Write-Host "----------------------------------------------------------" -ForegroundColor Yellow
python -u tests\test_v24_bandwidth.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "GATE 2 FAILED: V2.4 bandwidth limiting tests failed" -ForegroundColor Red
    exit 1
}
Write-Host "GATE 2 PASSED: V2.4 bandwidth limiting tests successful" -ForegroundColor Green

# Gate 3: V2.6 Queue Management Tests
Write-Host ""
Write-Host "GATE 3: V2.6 Queue Management Tests (Queue Functionality)" -ForegroundColor Yellow
Write-Host "--------------------------------------------------------" -ForegroundColor Yellow
python -u tests\test_v26_queue.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "GATE 3 FAILED: V2.6 queue management tests failed" -ForegroundColor Red
    exit 1
}
Write-Host "GATE 3 PASSED: V2.6 queue management tests successful" -ForegroundColor Green

# Gate 4: V2.7 Persistence Tests
Write-Host ""
Write-Host "GATE 4: V2.7 Persistence Tests (State Persistence)" -ForegroundColor Yellow
Write-Host "-------------------------------------------------" -ForegroundColor Yellow
python -u tests\test_v27_persistence.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "GATE 4 FAILED: V2.7 persistence tests failed" -ForegroundColor Red
    exit 1
}
Write-Host "GATE 4 PASSED: V2.7 persistence tests successful" -ForegroundColor Green

# Gate 5: V2.8 Execution Policy Tests
Write-Host ""
Write-Host "GATE 5: V2.8 Execution Policy Tests (Retry/Fairness/Per-host)" -ForegroundColor Yellow
Write-Host "------------------------------------------------------------" -ForegroundColor Yellow
python -u tests\test_v28_execution_policy.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "GATE 5 FAILED: V2.8 execution policy tests failed" -ForegroundColor Red
    exit 1
}
Write-Host "GATE 5 PASSED: V2.8 execution policy tests successful" -ForegroundColor Green

# Gate 6: V2.9 UI Contract Tests
Write-Host ""
Write-Host "GATE 6: V2.9 UI Contract Tests (Event Bus/Snapshots)" -ForegroundColor Yellow
Write-Host "---------------------------------------------------" -ForegroundColor Yellow
python -u tests\test_v29_ui_contract.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "GATE 6 FAILED: V2.9 UI contract tests failed" -ForegroundColor Red
    exit 1
}
Write-Host "GATE 6 PASSED: V2.9 UI contract tests successful" -ForegroundColor Green

# Final Success Report
Write-Host ""
Write-Host "================================================================" -ForegroundColor Green
Write-Host "ALL GATES PASSED: V3.1 Fast Gate Execution Complete" -ForegroundColor Green
Write-Host "================================================================" -ForegroundColor Green
Write-Host "Environment Summary:" -ForegroundColor Cyan
Write-Host "- Python Version: $PythonVersion" -ForegroundColor Gray
Write-Host "- Virtual Environment: $VenvPath" -ForegroundColor Gray
Write-Host "- Core Dependencies: requests>=2.31.0 only" -ForegroundColor Gray
Write-Host "- Test Gates: 6/6 passed (V2.1, V2.4, V2.6, V2.7, V2.8, V2.9)" -ForegroundColor Gray
Write-Host ""
Write-Host "V3.1 Environment Hygiene: COMPLETE" -ForegroundColor Green
Write-Host "Install full dependencies with: pip install -r requirements-full.txt" -ForegroundColor Cyan

exit 0