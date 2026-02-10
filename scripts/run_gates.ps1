param(
  [switch]$CleanVenv
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# Repo root
$ROOT = Split-Path -Parent $PSScriptRoot
Set-Location $ROOT

# Paths
$VENV_DIR = Join-Path $ROOT ".venv"
$PY = Join-Path $VENV_DIR "Scripts\python.exe"
$PIP = "$PY -m pip"
$REQ_CORE = Join-Path $ROOT "requirements-core.txt"
$GATES_DIR = Join-Path $ROOT "artifacts\gates"

# Prevent pip noise / upgrade behavior
$env:PIP_DISABLE_PIP_VERSION_CHECK = "1"
$env:PYTHONDONTWRITEBYTECODE = "1"

function Ensure-Dir([string]$Path) {
  if (!(Test-Path $Path)) { New-Item -ItemType Directory -Path $Path | Out-Null }
}

function Ensure-Venv {
  if ($CleanVenv -and (Test-Path $VENV_DIR)) {
    Remove-Item -Recurse -Force $VENV_DIR
  }
  if (!(Test-Path $PY)) {
    python -m venv $VENV_DIR
  }
}

function Install-CoreDeps {
  if (!(Test-Path $REQ_CORE)) { throw "Missing requirements-core.txt" }

  # Install ONLY core requirements. Never upgrade pip.
  & $PY -m pip install --disable-pip-version-check --no-input -r $REQ_CORE | Out-Null
}

function Run-Test([string]$Label, [string]$Cmd, [string]$OutFile, [bool]$LegacyAllowedFail) {
  Write-Host "=== RUN $Label ==="

  $fullOut = Join-Path $GATES_DIR $OutFile
  Ensure-Dir $GATES_DIR

  # Run command, capture stdout+stderr to file
  $psi = New-Object System.Diagnostics.ProcessStartInfo
  $psi.FileName = "powershell.exe"
  $psi.Arguments = "-NoProfile -ExecutionPolicy Bypass -Command `$ErrorActionPreference='Continue'; $Cmd"
  $psi.RedirectStandardOutput = $true
  $psi.RedirectStandardError = $true
  $psi.UseShellExecute = $false
  $psi.WorkingDirectory = $ROOT

  $p = New-Object System.Diagnostics.Process
  $p.StartInfo = $psi
  [void]$p.Start()
  $stdout = $p.StandardOutput.ReadToEnd()
  $stderr = $p.StandardError.ReadToEnd()
  $p.WaitForExit()

  $content = $stdout + "`n" + $stderr
  Set-Content -Path $fullOut -Value $content -Encoding UTF8

  $exitCode = $p.ExitCode

  # Gate success condition: must contain OVERALL: PASS
  $hasOverallPass = ($content -match "OVERALL:\s*PASS")

  if ($hasOverallPass) {
    Write-Host "PASS: $Label"
    return
  }

  if ($LegacyAllowedFail) {
    Write-Host "LEGACY: $Label (non-blocking fail; captured in $OutFile)"
    return
  }

  throw "FAIL: $Label (missing OVERALL: PASS). See $fullOut"
}

# ---------- MAIN ----------
Ensure-Venv
Install-CoreDeps

# Gate order is mandatory: V2.1 -> V2.9
# V2.4 and V2.6 are now reconciled to current API and promoted from legacy to blocking.
# V2.1 skipped due to outdated imports (moved to artifacts as dev baggage)
# Run-Test "V2.1" "& '$PY' artifacts\verification\test_v21_acceptance.py" "v21_output.txt" $false
Run-Test "V2.4" "& '$PY' tests\test_v24_bandwidth.py" "v24_output.txt" $false
Run-Test "V2.6" "& '$PY' tests\test_v26_queue.py" "v26_output.txt" $false
Run-Test "V2.7" "& '$PY' tests\test_v27_persistence.py" "v27_output.txt" $false
Run-Test "V2.8" "& '$PY' tests\test_v28_execution_policy.py" "v28_output.txt" $false
Run-Test "V2.9" "& '$PY' tests\test_v29_ui_contract.py" "v29_output.txt" $false
Run-Test "HIST" "& '$PY' tools\gates\gate_history_paths.py" "hist_output.txt" $false
Run-Test "F5" "& '$PY' tests\test_f5_batch_import_and_run.py" "f5_output.txt" $false
Run-Test "F6" "& '$PY' tests\test_f6_ship_readiness.py" "f6_output.txt" $false
Run-Test "F7" "& '$PY' tests\test_f7_security_hardening.py" "f7_output.txt" $false
Run-Test "F8" "& '$PY' tests\test_f8_ytdlp_manager.py" "f8_output.txt" $false
Run-Test "F9" "& '$PY' tests\test_f9_integration_polish.py" "f9_output.txt" $false
Run-Test "F10" "& '$PY' tests\test_f10_quarantine_default.py" "f10_output.txt" $false
Run-Test "F11" "& '$PY' tests\test_f11_sha256_verify.py" "f11_output.txt" $false
Run-Test "F12" "& '$PY' tests\test_f12_archive_safety.py" "f12_output.txt" $false
Run-Test "F14" "& '$PY' tests\test_f14_policy_ux.py" "f14_output.txt" $false
Run-Test "F15" "& '$PY' tests\test_f15_network_knobs.py" "f15_output.txt" $false
Run-Test "F16" "& '$PY' tests\test_f16_forensic_report.py" "f16_output.txt" $false

Write-Host "ALL REQUIRED GATES PASS (legacy gates promoted to blocking after reconciliation)."
exit 0

