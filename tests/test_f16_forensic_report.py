#!/usr/bin/env python3
"""
F16 Gate Test: Forensics-Grade Run Report + Human-Readable Log Folder Naming

Proves:
  A. Report contains forensics envelope: app_version, git_rev, policy_version_hash, os, python_version
  B. Per-item results include: host, failure_category
  C. build_log_folder() produces YYYY-MM-DD/HHMMSS - batch - <tag> - <id> pattern
  D. session_meta.json is written to log folder
  E. _classify_failure returns correct categories
  F. Batch run with real server produces expanded report
  G. Log folder created during batch run

Deterministic, headless, offline (<15s).
"""

import hashlib
import json
import os
import re
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.batch_run import (
    build_log_folder,
    _classify_failure,
    _extract_host,
    run_batch,
)
from tools.forensics import (
    app_version as _app_version,
    git_short_rev as _git_short_rev,
    policy_version_hash as _policy_version_hash,
)
from local_range_server import LocalRangeServer

# Whitelist loopback for test-local servers
_LOOPBACK = {'localhost', '127.0.0.1', '::1'}
try:
    from policy_engine import get_policy_engine as _get_pe
    _pe = _get_pe()
    _orig_denylist = list(_pe.policies.get('per_host', {}).get('denylist', []))
    _pe.policies.setdefault('per_host', {})['denylist'] = [
        h for h in _orig_denylist if h not in _LOOPBACK
    ]
    _ft = _pe.policies.get('file_type', {})
    _orig_blocked_exts = list(_ft.get('blocked_extensions', []))
    _ft['blocked_extensions'] = []
except Exception:
    _pe = None
    _orig_denylist = None
    _orig_blocked_exts = None


def _restore_policy():
    if _pe is not None and _orig_denylist is not None:
        _pe.policies.setdefault('per_host', {})['denylist'] = _orig_denylist
    if _pe is not None and _orig_blocked_exts is not None:
        _pe.policies.setdefault('file_type', {})['blocked_extensions'] = _orig_blocked_exts


# ---------------------------------------------------------------------------
# Counters
# ---------------------------------------------------------------------------

pass_count = 0
fail_count = 0


def check(label, condition, detail=""):
    global pass_count, fail_count
    if condition:
        pass_count += 1
        print(f"  PASS: {label}")
    else:
        fail_count += 1
        print(f"  FAIL: {label}  {detail}")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# ---------------------------------------------------------------------------
# Test A: Forensics helpers exist and return strings
# ---------------------------------------------------------------------------

def test_a_forensics_helpers():
    print("\n[A] Forensics metadata helpers")
    ver = _app_version()
    check("A1: app_version returns string", isinstance(ver, str) and len(ver) > 0,
          f"got {ver!r}")
    rev = _git_short_rev()
    check("A2: git_short_rev returns string", isinstance(rev, str) and len(rev) > 0,
          f"got {rev!r}")
    pvh = _policy_version_hash()
    check("A3: policy_version_hash returns string <=12 hex",
          isinstance(pvh, str) and len(pvh) <= 12, f"got {pvh!r}")


# ---------------------------------------------------------------------------
# Test B: _extract_host
# ---------------------------------------------------------------------------

def test_b_extract_host():
    print("\n[B] _extract_host")
    check("B1: normal URL", _extract_host("http://example.com/file.bin") == "example.com")
    check("B2: https with port", _extract_host("https://cdn.io:8080/f") == "cdn.io")
    check("B3: garbage", _extract_host("not_a_url") == "unknown")


# ---------------------------------------------------------------------------
# Test C: _classify_failure
# ---------------------------------------------------------------------------

def test_c_classify_failure():
    print("\n[C] _classify_failure")
    check("C1: COMPLETED -> none", _classify_failure("COMPLETED", None) == "none")
    check("C2: DENIED -> policy_denied", _classify_failure("DENIED", "whatever") == "policy_denied")
    check("C3: FAILED hash_mismatch", _classify_failure("FAILED", "HASH_MISMATCH: x") == "hash_mismatch")
    check("C4: FAILED timeout", _classify_failure("FAILED", "Connection timeout") == "timeout")
    check("C5: FAILED network", _classify_failure("FAILED", "network error") == "network_error")
    check("C6: FAILED unknown", _classify_failure("FAILED", "some random error") == "download_error")
    check("C7: FAILED no error", _classify_failure("FAILED", None) == "unknown")


# ---------------------------------------------------------------------------
# Test D: build_log_folder pattern
# ---------------------------------------------------------------------------

def test_d_log_folder_pattern():
    print("\n[D] build_log_folder pattern")
    summary = {"completed": 3, "failed": 0, "denied": 0}
    folder, _ts, _tag, _sid = build_log_folder("/logs", "batch", summary, short_id="abc12345")
    # Expected: /logs/YYYY-MM-DD/HHMMSS - batch - 3ok - abc12345
    check("D1: contains YYYY-MM-DD subfolder",
          re.search(r"\d{4}-\d{2}-\d{2}", folder) is not None, f"got {folder}")
    check("D2: contains HHMMSS", re.search(r"\d{6} - batch", folder) is not None,
          f"got {folder}")
    check("D3: contains 3ok tag", "3ok" in folder, f"got {folder}")
    check("D4: contains short_id", "abc12345" in folder, f"got {folder}")

    # With failures
    summary2 = {"completed": 2, "failed": 1, "denied": 1}
    folder2, _ts2, _tag2, _sid2 = build_log_folder("/logs", "batch", summary2, short_id="x1234567")
    check("D5: contains 2ok_2fail tag", "2ok_2fail" in folder2, f"got {folder2}")


# ---------------------------------------------------------------------------
# Test E: Batch run produces expanded report
# ---------------------------------------------------------------------------

def test_e_batch_report():
    print("\n[E] Batch run expanded report")
    tmp = tempfile.mkdtemp(prefix="f16_e_")
    dl_dir = os.path.join(tmp, "dl")
    os.makedirs(dl_dir)

    srv = LocalRangeServer()
    base_url, serve_dir = srv.start()
    try:
        payload = b"forensics-test-content-1234"
        fname = "forensic.bin"
        with open(os.path.join(serve_dir, fname), "wb") as f:
            f.write(payload)

        url = f"{base_url}/range/{fname}"

        batch = {
            "version": 1,
            "defaults": {"dest_dir": dl_dir, "priority": 5, "connections": 1},
            "items": [{"id": "forensic-1", "url": url}],
        }

        report_path = os.path.join(tmp, "report.json")
        run_batch(batch, report_path=report_path, max_concurrent=1, until="empty")

        with open(report_path, "r", encoding="utf-8") as f:
            report = json.load(f)

        # Envelope fields
        check("E1: app_version in report", "app_version" in report,
              f"keys: {list(report.keys())}")
        check("E2: git_rev in report", "git_rev" in report)
        check("E3: policy_version_hash in report", "policy_version_hash" in report)
        check("E4: os in report", "os" in report)
        check("E5: python_version in report", "python_version" in report)

        # Per-item fields
        r0 = report["results"][0]
        check("E6: host field in result", "host" in r0, f"keys: {list(r0.keys())}")
        check("E7: host is loopback",
              r0.get("host") in ("127.0.0.1", "localhost"),
              f"got {r0.get('host')!r}")
        check("E8: failure_category in result", "failure_category" in r0)
        check("E9: failure_category is none for completed",
              r0.get("failure_category") == "none",
              f"got {r0.get('failure_category')!r}")
    finally:
        srv.stop()
        shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------
# Test F: Log folder created with session_meta.json
# ---------------------------------------------------------------------------

def test_f_log_folder_created():
    print("\n[F] Log folder + session_meta.json")
    logs_root = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")

    tmp = tempfile.mkdtemp(prefix="f16_f_")
    dl_dir = os.path.join(tmp, "dl")
    os.makedirs(dl_dir)

    srv = LocalRangeServer()
    base_url, serve_dir = srv.start()
    try:
        payload = b"log-folder-test"
        with open(os.path.join(serve_dir, "lf.bin"), "wb") as f:
            f.write(payload)

        batch = {
            "version": 1,
            "defaults": {"dest_dir": dl_dir},
            "items": [{"id": "lf-1", "url": f"{base_url}/range/lf.bin"}],
        }
        run_batch(batch, max_concurrent=1, until="empty")

        # Find today's date folder
        found_date_dirs = []
        if os.path.isdir(logs_root):
            for d in os.listdir(logs_root):
                if re.match(r"\d{4}-\d{2}-\d{2}$", d):
                    found_date_dirs.append(d)

        check("F1: at least one YYYY-MM-DD folder in logs/",
              len(found_date_dirs) > 0, f"found {found_date_dirs}")

        # Find session_meta.json in one of them
        found_meta = False
        for dd in found_date_dirs:
            dd_path = os.path.join(logs_root, dd)
            for sub in os.listdir(dd_path):
                meta = os.path.join(dd_path, sub, "session_meta.json")
                if os.path.exists(meta):
                    found_meta = True
                    with open(meta, "r", encoding="utf-8") as f:
                        meta_data = json.load(f)
                    check("F2: session_meta has run_id", "run_id" in meta_data)
                    check("F3: session_meta has app_version", "app_version" in meta_data)
                    check("F4: session_meta has git_rev", "git_rev" in meta_data)
                    check("F5: session_meta has summary", "summary" in meta_data)
                    break
            if found_meta:
                break

        if not found_meta:
            check("F2: session_meta.json found", False, "no session_meta.json in any log folder")
    finally:
        srv.stop()
        shutil.rmtree(tmp, ignore_errors=True)


# ===========================================================================

def main():
    print("=" * 60)
    print("F16 GATE: Forensics Report + Log Folder Naming")
    print("=" * 60)

    try:
        test_a_forensics_helpers()
        test_b_extract_host()
        test_c_classify_failure()
        test_d_log_folder_pattern()
        test_e_batch_report()
        test_f_log_folder_created()
    finally:
        _restore_policy()

    print("\n" + "=" * 60)
    total = pass_count + fail_count
    print(f"RESULTS: {pass_count}/{total} passed, {fail_count} failed")
    if fail_count == 0:
        print("OVERALL: PASS")
    else:
        print("OVERALL: FAIL")
    print("=" * 60)

    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
