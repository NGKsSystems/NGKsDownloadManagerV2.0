s DL Manager V2.5 Gate Runner
# Reproducible environment testing with automated venv management
# Universal Agent Ruleset: ASCII output only, no placeholders, docs in /docs

param(
    [switch]$CleanVenv = $false,
    [switch]$Verbose = $false
)

$ErrorActionPreference = "Stop"

Write-Host "NGK's DL Manager V2.5 - Reproducible Environment Test Gates" -ForegroundColor Green
Write-Host "================================================================" -ForegroundColor Green

# Project root detection
$ProjectRoot = Split-Path $PSScriptRoot -Parent
if (-not (Test-Path "$ProjectRoot\requirements.txt")) {
    Write-Host "ERROR: requirements.txt not found in project root: $ProjectRoot" -ForegroundColor Red
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

# Install/upgrade dependencies
Write-Host "Installing dependencies from requirements.txt..." -ForegroundColor Yellow
pip install --upgrade pip
pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to install dependencies" -ForegroundColor Red
    exit 1
}
Write-Host "Dependencies installed successfully." -ForegroundColor Green

# Verify minimal dependencies
Write-Host "Verifying minimal dependency installation..." -ForegroundColor Yellow
$InstalledPackages = pip list --format=freeze
Write-Host "Installed packages:" -ForegroundColor Cyan
$InstalledPackages | ForEach-Object { Write-Host "  $_" -ForegroundColor Gray }

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
python -m pytest tests\test_v21_acceptance.py -v
if ($LASTEXITCODE -ne 0) {
    Write-Host "GATE 1 FAILED: V2.1 acceptance tests failed" -ForegroundColor Red
    exit 1
}
Write-Host "GATE 1 PASSED: V2.1 acceptance tests successful" -ForegroundColor Green

# Gate 2: V2.4 Bandwidth Limiting Tests
Write-Host ""
Write-Host "GATE 2: V2.4 Bandwidth Limiting Tests (Feature Validation)" -ForegroundColor Yellow
Write-Host "----------------------------------------------------------" -ForegroundColor Yellow
python -m pytest tests\test_v24_bandwidth.py -v
if ($LASTEXITCODE -ne 0) {
    Write-Host "GATE 2 FAILED: V2.4 bandwidth limiting tests failed" -ForegroundColor Red
    exit 1
}
Write-Host "GATE 2 PASSED: V2.4 bandwidth limiting tests successful" -ForegroundColor Green

# Gate 3: Import and Module Structure Validation
Write-Host ""
Write-Host "GATE 3: Module Structure Validation (Dependency Health)" -ForegroundColor Yellow
Write-Host "-------------------------------------------------------" -ForegroundColor Yellow

# Test core module imports
$ModuleTests = @(
    "integrated_multi_downloader",
    "local_range_server",
    "http_range_detector"
)

foreach ($Module in $ModuleTests) {
    python -c "import $Module; print('$Module imported successfully')"
    if ($LASTEXITCODE -ne 0) {
        Write-Host "GATE 3 FAILED: $Module import failed" -ForegroundColor Red
        exit 1
    }
}
Write-Host "GATE 3 PASSED: All core modules import successfully" -ForegroundColor Green

# Gate 4: Configuration Validation
Write-Host ""
Write-Host "GATE 4: Configuration Validation (Settings Integrity)" -ForegroundColor Yellow
Write-Host "-----------------------------------------------------" -ForegroundColor Yellow
python -c "
import json
with open('config.json', 'r') as f:
    config = json.load(f)
required_keys = ['enable_bandwidth_limiting', 'global_bandwidth_limit_mbps']
for key in required_keys:
    assert key in config, f'Missing config key: {key}'
assert isinstance(config['enable_bandwidth_limiting'], bool), 'enable_bandwidth_limiting must be boolean'
assert isinstance(config['global_bandwidth_limit_mbps'], (int, float)), 'global_bandwidth_limit_mbps must be numeric'
print('Configuration validation passed')
"
if ($LASTEXITCODE -ne 0) {
    Write-Host "GATE 4 FAILED: Configuration validation failed" -ForegroundColor Red
    exit 1
}
Write-Host "GATE 4 PASSED: Configuration validation successful" -ForegroundColor Green

# Final Success Report
Write-Host ""
Write-Host "================================================================" -ForegroundColor Green
Write-Host "ALL GATES PASSED: V2.5 Reproducible Environment Validation" -ForegroundColor Green
Write-Host "================================================================" -ForegroundColor Green
Write-Host "Environment Summary:" -ForegroundColor Cyan
Write-Host "- Python Version: $PythonVersion" -ForegroundColor Gray
Write-Host "- Virtual Environment: $VenvPath" -ForegroundColor Gray
Write-Host "- Minimal Dependencies: requests>=2.25.0" -ForegroundColor Gray
Write-Host "- Test Gates: 4/4 passed" -ForegroundColor Gray
Write-Host ""
Write-Host "V2.5 Release Status: READY FOR PRODUCTION" -ForegroundColor Green

exit 0