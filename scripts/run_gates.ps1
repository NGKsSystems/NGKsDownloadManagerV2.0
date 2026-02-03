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

exit 0# File: scripts/run_gates.ps1
# NGK's DL Manager - Gate Runner (engine-only / deterministic)
# - Uses CORE deps only (requirements-core.txt)
# - Produces gate_run.txt + per-gate output files in repo root
# - FAILS LOUDLY on any missing files, test failure, or missing "OVERALL: PASS"

param(
    [switch]$CleanVenv,
    [switch]$Verbose
)

$ErrorActionPreference = "Stop"

function Write-Log {
    param(
        [Parameter(Mandatory=$true)][string]$Message,
        [string]$Color = "Gray"
    )
    # Console
    try {
        Write-Host $Message -ForegroundColor $Color
    } catch {
        Write-Host $Message
    }
    # File
    Add-Content -Path $script:GateRunLog -Value $Message -Encoding UTF8
}

function Fail {
    param([string]$Message)
    Write-Log "FAIL: $Message" "Red"
    exit 1
}

function Ensure-File {
    param([string]$Path, [string]$Label)
    if (-not (Test-Path -LiteralPath $Path)) {
        Fail "$Label not found: $Path"
    }
}

function Get-PythonExe {
    param([string]$VenvPath)

    $py = Join-Path $VenvPath "Scripts\python.exe"
    if (Test-Path -LiteralPath $py) { return $py }

    $pyAlt = Join-Path $VenvPath "Scripts\python"
    if (Test-Path -LiteralPath $pyAlt) { return $pyAlt }

    Fail "Python executable not found inside venv: $VenvPath"
}

function Invoke-Gate {
    param(
        [Parameter(Mandatory=$true)][string]$Name,
        [Parameter(Mandatory=$true)][string]$ScriptPath,
        [Parameter(Mandatory=$true)][string]$OutFile
    )

    Write-Log ""
    Write-Log "=== RUN: $Name ===" "Cyan"
    Write-Log "Script: $ScriptPath"
    Write-Log "Output: $OutFile"

    # Run and capture output (stdout+stderr)
    & $script:PythonExe -u $ScriptPath *> $OutFile
    $exit = $LASTEXITCODE

    if ($exit -ne 0) {
        Write-Log "ExitCode: $exit" "Red"
        Write-Log "Tail (last 30 lines) from $OutFile:" "Yellow"
        Get-Content -LiteralPath $OutFile -Tail 30 | ForEach-Object { Write-Log $_ }
        Fail "$Name failed (non-zero exit code)."
    }

    # Verify "OVERALL: PASS"
    $passLine = Select-String -LiteralPath $OutFile -Pattern "OVERALL:\s*PASS" -SimpleMatch -ErrorAction SilentlyContinue
    if (-not $passLine) {
        Write-Log "Missing expected marker: OVERALL: PASS" "Red"
        Write-Log "Tail (last 30 lines) from $OutFile:" "Yellow"
        Get-Content -LiteralPath $OutFile -Tail 30 | ForEach-Object { Write-Log $_ }
        Fail "$Name failed (no OVERALL: PASS in output)."
    }

    Write-Log "PASS: $Name" "Green"
}

# -------------------------
# Resolve project root
# -------------------------
$ProjectRoot = Split-Path $PSScriptRoot -Parent
Set-Location $ProjectRoot

# Log file in root (so you can open it quickly)
$script:GateRunLog = Join-Path $ProjectRoot "gate_run.txt"
Remove-Item -LiteralPath $script:GateRunLog -Force -ErrorAction SilentlyContinue
New-Item -ItemType File -Path $script:GateRunLog -Force | Out-Null

Write-Log "NGK's DL Manager - Gate Runner" "Green"
Write-Log "============================================================" "Green"
Write-Log "Project Root: $ProjectRoot" "Gray"
Write-Log ("PowerShell: " + $PSVersionTable.PSVersion.ToString()) "Gray"

# -------------------------
# Validate required files
# -------------------------
Ensure-File (Join-Path $ProjectRoot "requirements-core.txt") "requirements-core.txt"
Ensure-File (Join-Path $ProjectRoot "config.json") "config.json"

# -------------------------
# Create / clean venv
# -------------------------
$VenvPath = Join-Path $ProjectRoot ".venv"

if ($CleanVenv -and (Test-Path -LiteralPath $VenvPath)) {
    Write-Log "Cleaning virtual environment: $VenvPath" "Yellow"
    Remove-Item -LiteralPath $VenvPath -Recurse -Force
}

if (-not (Test-Path -LiteralPath $VenvPath)) {
    Write-Log "Creating virtual environment (.venv)..." "Yellow"
    python -m venv $VenvPath
    if ($LASTEXITCODE -ne 0) { Fail "Failed to create virtual environment." }
}

$script:PythonExe = Get-PythonExe -VenvPath $VenvPath

Write-Log ("Using Python: " + (& $script:PythonExe --version 2>&1)) "Gray"

# -------------------------
# Install CORE deps only
# -------------------------
Write-Log "Installing CORE dependencies (fast) from requirements-core.txt..." "Yellow"
& $script:PythonExe -m pip install --disable-pip-version-check --no-python-version-warning -r (Join-Path $ProjectRoot "requirements-core.txt") *> (Join-Path $ProjectRoot "pip_core_install.txt")
if ($LASTEXITCODE -ne 0) {
    Write-Log "Tail (last 40 lines) from pip_core_install.txt:" "Yellow"
    Get-Content -LiteralPath (Join-Path $ProjectRoot "pip_core_install.txt") -Tail 40 | ForEach-Object { Write-Log $_ }
    Fail "pip install (core) failed."
}

# Optional: show installed core packages when Verbose
if ($Verbose) {
    Write-Log "pip list (filtered):" "Gray"
    & $script:PythonExe -m pip list --disable-pip-version-check *> (Join-Path $ProjectRoot "pip_list.txt")
    Get-Content -LiteralPath (Join-Path $ProjectRoot "pip_list.txt") -Tail 60 | ForEach-Object { Write-Log $_ }
}

# -------------------------
# Gate script path resolution
# (supports either root scripts or tests/ versions)
# -------------------------
function Resolve-GateScript {
    param(
        [Parameter(Mandatory=$true)][string[]]$Candidates,
        [Parameter(Mandatory=$true)][string]$GateName
    )
    foreach ($c in $Candidates) {
        $p = Join-Path $ProjectRoot $c
        if (Test-Path -LiteralPath $p) { return $p }
    }
    Fail "$GateName script not found. Tried: $($Candidates -join ', ')"
}

$gateV21 = Resolve-GateScript -GateName "V2.1 Acceptance" -Candidates @("test_v21_acceptance.py", "tests\test_v21_acceptance.py")
$gateV24 = Resolve-GateScript -GateName "V2.4 Bandwidth"  -Candidates @("tests\test_v24_bandwidth.py")
$gateV26 = Resolve-GateScript -GateName "V2.6 Queue"      -Candidates @("tests\test_v26_queue.py")
$gateV27 = Resolve-GateScript -GateName "V2.7 Persistence" -Candidates @("tests\test_v27_persistence.py")
$gateV28 = Resolve-GateScript -GateName "V2.8 Exec Policy" -Candidates @("tests\test_v28_execution_policy.py")
$gateV29 = Resolve-GateScript -GateName "V2.9 UI Contract" -Candidates @("tests\test_v29_ui_contract.py")

# -------------------------
# Run gates (outputs in root)
# -------------------------
Invoke-Gate -Name "V2.1 Acceptance"     -ScriptPath $gateV21 -OutFile (Join-Path $ProjectRoot "acceptance_output.txt")
Invoke-Gate -Name "V2.4 Bandwidth"      -ScriptPath $gateV24 -OutFile (Join-Path $ProjectRoot "v24_output.txt")
Invoke-Gate -Name "V2.6 Queue"          -ScriptPath $gateV26 -OutFile (Join-Path $ProjectRoot "v26_output.txt")
Invoke-Gate -Name "V2.7 Persistence"    -ScriptPath $gateV27 -OutFile (Join-Path $ProjectRoot "v27_output.txt")
Invoke-Gate -Name "V2.8 ExecutionPolicy" -ScriptPath $gateV28 -OutFile (Join-Path $ProjectRoot "v28_output.txt")
Invoke-Gate -Name "V2.9 UI Contract"    -ScriptPath $gateV29 -OutFile (Join-Path $ProjectRoot "v29_output.txt")

Write-Log ""
Write-Log "============================================================" "Green"
Write-Log "ALL GATES: PASS" "Green"
Write-Log "Log: gate_run.txt" "Gray"
exit 0
