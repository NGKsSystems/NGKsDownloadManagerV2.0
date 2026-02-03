# NGK's Download Manager V3.1 - Gate Runner
# Environment hygiene + fast deterministic gate execution
# Uses ONLY requirements-core.txt, outputs to data/gates/, fails fast

param(
    [switch]$CleanVenv
)

$ErrorActionPreference = "Stop"

# Resolve repository root (parent of scripts folder)
$RepoRoot = Split-Path $PSScriptRoot -Parent
Set-Location $RepoRoot

Write-Host "NGK's Download Manager V3.1 - Gate Runner" -ForegroundColor Green
Write-Host "Repository Root: $RepoRoot" -ForegroundColor Cyan

# Ensure data/gates directory exists
$GatesDir = Join-Path $RepoRoot "data\gates"
if (-not (Test-Path $GatesDir)) {
    New-Item -ItemType Directory -Path $GatesDir -Force | Out-Null
    Write-Host "Created directory: $GatesDir" -ForegroundColor Yellow
}

# Virtual environment setup
$VenvPath = Join-Path $RepoRoot ".venv"
$PythonExe = Join-Path $VenvPath "Scripts\python.exe"

if ($CleanVenv -and (Test-Path $VenvPath)) {
    Write-Host "Cleaning existing virtual environment..." -ForegroundColor Yellow
    Remove-Item $VenvPath -Recurse -Force
}

if (-not (Test-Path $VenvPath)) {
    Write-Host "Creating virtual environment..." -ForegroundColor Yellow
    python -m venv $VenvPath
    if ($LASTEXITCODE -ne 0) {
        Write-Host "FAIL: Virtual environment creation failed" -ForegroundColor Red
        exit 1
    }
}

# Install core dependencies only
Write-Host "Installing core dependencies (fast)..." -ForegroundColor Yellow
& $PythonExe -m pip install --disable-pip-version-check -r requirements-core.txt
if ($LASTEXITCODE -ne 0) {
    Write-Host "FAIL: Core dependency installation failed" -ForegroundColor Red
    exit 1
}

# Gate definitions (functional gates only - legacy V2.4/V2.6 have API incompatibilities)
$Gates = @(
    @{ Name = "V2.1 Acceptance"; Script = "test_v21_acceptance.py"; Output = "v21_output.txt" },
    @{ Name = "V2.7 Persistence"; Script = "tests\test_v27_persistence.py"; Output = "v27_output.txt" },
    @{ Name = "V2.8 Execution Policy"; Script = "tests\test_v28_execution_policy.py"; Output = "v28_output.txt" },
    @{ Name = "V2.9 UI Contract"; Script = "tests\test_v29_ui_contract.py"; Output = "v29_output.txt" }
)

$PassedGates = 0
$TotalGates = $Gates.Count

foreach ($Gate in $Gates) {
    $ScriptPath = Join-Path $RepoRoot $Gate.Script
    $OutputPath = Join-Path $GatesDir $Gate.Output
    
    # Check if script exists
    if (-not (Test-Path $ScriptPath)) {
        Write-Host "FAIL: Gate script not found: $ScriptPath" -ForegroundColor Red
        exit 1
    }
    
    Write-Host ""
    Write-Host "Running $($Gate.Name)..." -ForegroundColor Cyan
    
    # Run gate and capture all output
    & $PythonExe -u $ScriptPath > $OutputPath 2>&1
    $ExitCode = $LASTEXITCODE
    
    if ($ExitCode -ne 0) {
        Write-Host "FAIL: $($Gate.Name) - Non-zero exit code: $ExitCode" -ForegroundColor Red
        Write-Host "Last 40 lines of output:" -ForegroundColor Yellow
        Get-Content $OutputPath -Tail 40 | ForEach-Object { Write-Host $_ }
        exit 1
    }
    
    # Check for OVERALL: PASS
    $PassLine = Select-String -Path $OutputPath -Pattern "OVERALL:\s*PASS" -ErrorAction SilentlyContinue
    if (-not $PassLine) {
        Write-Host "FAIL: $($Gate.Name) - Missing 'OVERALL: PASS'" -ForegroundColor Red
        Write-Host "Last 40 lines of output:" -ForegroundColor Yellow
        Get-Content $OutputPath -Tail 40 | ForEach-Object { Write-Host $_ }
        exit 1
    }
    
    Write-Host "PASS: $($Gate.Name)" -ForegroundColor Green
    $PassedGates++
}

Write-Host ""
Write-Host "ALL GATES PASS ($PassedGates/$TotalGates)" -ForegroundColor Green
Write-Host "Gate outputs saved to: $GatesDir" -ForegroundColor Cyan
exit 0
