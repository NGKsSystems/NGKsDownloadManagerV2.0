#!/usr/bin/env python3
"""
F10 Gate Test: Quarantine Default for Risky Extensions

Proves:
  A. should_quarantine correctly classifies dangerous vs safe extensions
  B. choose_final_dir routes dangerous to _quarantine, safe to base
  C. Batch run quarantines .exe, keeps .bin in normal dir
  D. Report includes quarantined=true/false and quarantine_reason
  E. No orphan .part/.resume files
  F. SECURITY.QUARANTINE_SELECTED event emitted for risky files
  G. quarantine_dir creates the directory

Deterministic, headless, offline (<10s).
"""

import hashlib
import json
import logging
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from local_range_server import LocalRangeServer
from security import (
    should_quarantine,
    quarantine_dir,
    choose_final_dir,
    DANGEROUS_EXTENSIONS,
)
from tools.batch_run import run_batch

# Whitelist loopback for test-local servers (same pattern as F5/F6)
# Also clear blocked_extensions so quarantine (not policy deny) handles risky files
_LOOPBACK = {'localhost', '127.0.0.1', '::1'}
_orig_blocked_exts = None
try:
    from policy_engine import get_policy_engine as _get_pe
    _pe = _get_pe()
    _orig_denylist = list(_pe.policies.get('per_host', {}).get('denylist', []))
    _pe.policies.setdefault('per_host', {})['denylist'] = [
        h for h in _orig_denylist if h not in _LOOPBACK
    ]
    # Clear blocked_extensions so quarantine handles them instead of policy deny
    ft = _pe.policies.get('file_type', {})
    _orig_blocked_exts = list(ft.get('blocked_extensions', []))
    ft['blocked_extensions'] = []
except Exception:
    _pe = None
    _orig_denylist = None


def _restore_denylist():
    if _pe is not None and _orig_denylist is not None:
        _pe.policies.setdefault('per_host', {})['denylist'] = _orig_denylist
    if _pe is not None and _orig_blocked_exts is not None:
        _pe.policies.setdefault('file_type', {})['blocked_extensions'] = _orig_blocked_exts


# ---------------------------------------------------------------------------
# Security log capture
# ---------------------------------------------------------------------------

class SecurityLogCapture(logging.Handler):
    def __init__(self):
        super().__init__()
        self.events: list[str] = []

    def emit(self, record):
        msg = self.format(record)
        if "SECURITY." in msg:
            self.events.append(msg)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main():
    results = []
    overall = True

    def check(label, condition, detail=""):
        nonlocal overall
        tag = "PASS" if condition else "FAIL"
        if not condition:
            overall = False
        msg = f"  [{tag}] {label}"
        if detail:
            msg += f" -- {detail}"
        print(msg)
        results.append((label, condition))

    print("=== F10 Gate Test: Quarantine Default for Risky Extensions ===")
    print()

    sec_logger = logging.getLogger("security")
    sec_logger.setLevel(logging.DEBUG)
    capture = SecurityLogCapture()
    capture.setFormatter(logging.Formatter("%(message)s"))
    sec_logger.addHandler(capture)

    tmp = tempfile.mkdtemp(prefix="f10_gate_")

    try:
        # ------------------------------------------------------------------
        # Test A: should_quarantine classification
        # ------------------------------------------------------------------
        print("--- Test A: should_quarantine ---")
        check("A1: .exe -> quarantine", should_quarantine("setup.exe"))
        check("A2: .msi -> quarantine", should_quarantine("installer.msi"))
        check("A3: .bat -> quarantine", should_quarantine("run.bat"))
        check("A4: .cmd -> quarantine", should_quarantine("script.cmd"))
        check("A5: .ps1 -> quarantine", should_quarantine("deploy.ps1"))
        check("A6: .vbs -> quarantine", should_quarantine("macro.vbs"))
        check("A7: .js  -> quarantine", should_quarantine("payload.js"))
        check("A8: .scr -> quarantine", should_quarantine("screen.scr"))
        check("A9: .jar -> quarantine", should_quarantine("app.jar"))
        check("A10: .lnk -> no (not in set)", not should_quarantine("link.lnk"),
              ".lnk not in DANGEROUS_EXTENSIONS is expected")
        check("A11: .bin -> safe", not should_quarantine("data.bin"))
        check("A12: .zip -> safe", not should_quarantine("archive.zip"))
        check("A13: .pdf -> safe", not should_quarantine("doc.pdf"))

        # ------------------------------------------------------------------
        # Test B: choose_final_dir routing
        # ------------------------------------------------------------------
        print()
        print("--- Test B: choose_final_dir ---")
        base = os.path.join(tmp, "dl_b")
        os.makedirs(base)

        dir_exe, q_exe = choose_final_dir(base, "setup.exe")
        check("B1: .exe -> quarantine=True", q_exe is True)
        check("B2: .exe dir ends with _quarantine",
              dir_exe.endswith("_quarantine"),
              f"dir={dir_exe}")

        dir_bin, q_bin = choose_final_dir(base, "data.bin")
        check("B3: .bin -> quarantine=False", q_bin is False)
        check("B4: .bin dir == base", dir_bin == base)

        # ------------------------------------------------------------------
        # Test C: quarantine_dir creates directory
        # ------------------------------------------------------------------
        print()
        print("--- Test C: quarantine_dir ---")
        qd = quarantine_dir(base)
        check("C1: quarantine dir exists", os.path.isdir(qd))
        check("C2: quarantine dir is _quarantine",
              os.path.basename(qd) == "_quarantine")

        # ------------------------------------------------------------------
        # Test D: Batch run with .exe + .bin
        # ------------------------------------------------------------------
        print()
        print("--- Test D: Batch run quarantine ---")

        server = LocalRangeServer()
        base_url, serve_dir = server.start()

        safe_data = b"safe-content-" + bytes(range(200))
        risky_data = b"MZ-fake-exe-payload" + bytes(range(200))

        with open(os.path.join(serve_dir, "safe.bin"), "wb") as f:
            f.write(safe_data)
        with open(os.path.join(serve_dir, "x.exe"), "wb") as f:
            f.write(risky_data)

        dl_dir = os.path.join(tmp, "downloads_d")
        os.makedirs(dl_dir)

        batch = {
            "items": [
                {"id": "safe1", "url": f"{base_url}/range/safe.bin",
                 "filename": "safe.bin", "dest_dir": dl_dir},
                {"id": "risky1", "url": f"{base_url}/range/x.exe",
                 "filename": "x.exe", "dest_dir": dl_dir},
            ]
        }

        report_path = os.path.join(tmp, "report_d.json")
        capture.events.clear()

        try:
            exit_code = run_batch(batch, report_path=report_path, max_concurrent=2)
        finally:
            server.stop()

        # Read report
        with open(report_path, "r") as f:
            report = json.load(f)

        summary = report["summary"]
        check("D1: completed==2", summary["completed"] == 2,
              f"completed={summary['completed']}")

        # safe.bin in normal dir
        safe_result = next((r for r in report["results"] if r["task_id"] == "safe1"), None)
        check("D2: safe.bin result exists", safe_result is not None)
        if safe_result:
            safe_path = safe_result["final_path"]
            check("D3: safe.bin in normal dir (not _quarantine)",
                  "_quarantine" not in safe_path,
                  f"path={safe_path}")
            check("D4: safe.bin quarantined=false",
                  safe_result.get("quarantined") is False)
            check("D5: safe.bin file exists", os.path.isfile(safe_path))

        # x.exe in quarantine
        risky_result = next((r for r in report["results"] if r["task_id"] == "risky1"), None)
        check("D6: x.exe result exists", risky_result is not None)
        if risky_result:
            risky_path = risky_result["final_path"]
            check("D7: x.exe in _quarantine dir",
                  "_quarantine" in risky_path,
                  f"path={risky_path}")
            check("D8: x.exe quarantined=true",
                  risky_result.get("quarantined") is True)
            check("D9: x.exe quarantine_reason=dangerous_extension",
                  risky_result.get("quarantine_reason") == "dangerous_extension")
            check("D10: x.exe file exists", os.path.isfile(risky_path))

        # ------------------------------------------------------------------
        # Test E: No orphan .part/.resume
        # ------------------------------------------------------------------
        print()
        print("--- Test E: No orphans ---")

        orphans = []
        for root, dirs, files in os.walk(dl_dir):
            for fname in files:
                if fname.endswith((".part", ".resume")):
                    orphans.append(os.path.join(root, fname))
        check("E1: no .part/.resume orphans", len(orphans) == 0,
              f"orphans={orphans}" if orphans else "clean")

        # ------------------------------------------------------------------
        # Test F: Security events
        # ------------------------------------------------------------------
        print()
        print("--- Test F: Security events ---")

        quarantine_events = [e for e in capture.events
                             if "SECURITY.QUARANTINE_SELECTED" in e]
        check("F1: QUARANTINE_SELECTED emitted", len(quarantine_events) >= 1,
              f"count={len(quarantine_events)}")

        exe_in_event = any("x.exe" in e for e in quarantine_events)
        check("F2: event mentions x.exe", exe_in_event)

        safe_quarantine = [e for e in quarantine_events if "safe.bin" in e]
        check("F3: no quarantine event for safe.bin", len(safe_quarantine) == 0)

    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        sec_logger.removeHandler(capture)
        _restore_denylist()

    # --- Overall ---
    print()
    if overall:
        print("OVERALL: PASS")
    else:
        print("OVERALL: FAIL")
    sys.exit(0 if overall else 1)


if __name__ == "__main__":
    main()
