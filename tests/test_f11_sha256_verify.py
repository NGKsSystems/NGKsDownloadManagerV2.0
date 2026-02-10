#!/usr/bin/env python3
"""
F11 Gate Test: Optional SHA256 Verify per Batch Item

Proves:
  A. Valid sha256 in item -> COMPLETED with hash_result=OK
  B. Wrong sha256 in item -> FAILED with HASH_MISMATCH, no final file
  C. No sha256 in item -> COMPLETED (hash_result=UNCHECKED)
  D. Schema validates sha256 format (64 hex chars)
  E. SECURITY.HASH_MISMATCH event emitted on mismatch
  F. No orphan .part/.resume files

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
from tools.batch_schema import validate_batch_dict
from tools.batch_run import run_batch

# Whitelist loopback for policy
_LOOPBACK = {'localhost', '127.0.0.1', '::1'}
try:
    from policy_engine import get_policy_engine as _get_pe
    _pe = _get_pe()
    _orig_denylist = list(_pe.policies.get('per_host', {}).get('denylist', []))
    _pe.policies.setdefault('per_host', {})['denylist'] = [
        h for h in _orig_denylist if h not in _LOOPBACK
    ]
except Exception:
    _pe = None
    _orig_denylist = None


def _restore():
    if _pe is not None and _orig_denylist is not None:
        _pe.policies.setdefault('per_host', {})['denylist'] = _orig_denylist


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

    print("=== F11 Gate Test: Optional SHA256 Verify per Batch Item ===")
    print()

    sec_logger = logging.getLogger("security")
    sec_logger.setLevel(logging.DEBUG)
    capture = SecurityLogCapture()
    capture.setFormatter(logging.Formatter("%(message)s"))
    sec_logger.addHandler(capture)

    tmp = tempfile.mkdtemp(prefix="f11_gate_")

    try:
        # ------------------------------------------------------------------
        # Test A: Schema validation for sha256
        # ------------------------------------------------------------------
        print("--- Test A: Schema sha256 validation ---")

        # Valid sha256
        batch_ok = {
            "items": [
                {"id": "a1", "url": "http://x/f.bin", "sha256": "a" * 64}
            ]
        }
        errs = validate_batch_dict(batch_ok)
        check("A1: valid sha256 passes", len(errs) == 0, f"errors={errs}")

        # Wrong length
        batch_bad_len = {
            "items": [
                {"id": "a2", "url": "http://x/f.bin", "sha256": "abc123"}
            ]
        }
        errs2 = validate_batch_dict(batch_bad_len)
        check("A2: wrong length rejected", any("64-character" in e for e in errs2),
              f"errors={errs2}")

        # Non-hex
        batch_bad_hex = {
            "items": [
                {"id": "a3", "url": "http://x/f.bin", "sha256": "g" * 64}
            ]
        }
        errs3 = validate_batch_dict(batch_bad_hex)
        check("A3: non-hex rejected", any("hex" in e for e in errs3),
              f"errors={errs3}")

        # Uppercase valid (should pass)
        batch_upper = {
            "items": [
                {"id": "a4", "url": "http://x/f.bin", "sha256": "A" * 64}
            ]
        }
        errs4 = validate_batch_dict(batch_upper)
        check("A4: uppercase hex passes", len(errs4) == 0, f"errors={errs4}")

        # ------------------------------------------------------------------
        # Test B: Correct hash -> COMPLETED
        # ------------------------------------------------------------------
        print()
        print("--- Test B: Correct hash -> COMPLETED ---")

        server = LocalRangeServer()
        base_url, serve_dir = server.start()

        file_data = b"deterministic-content-for-f11-test" + bytes(range(200))
        correct_hash = sha256_bytes(file_data)

        with open(os.path.join(serve_dir, "verified.bin"), "wb") as f:
            f.write(file_data)

        dl_dir = os.path.join(tmp, "dl_b")
        os.makedirs(dl_dir)
        report_path = os.path.join(tmp, "report_b.json")

        try:
            batch_b = {
                "items": [
                    {"id": "good_hash", "url": f"{base_url}/range/verified.bin",
                     "filename": "verified.bin", "dest_dir": dl_dir,
                     "sha256": correct_hash},
                ]
            }
            exit_code = run_batch(batch_b, report_path=report_path)
        finally:
            server.stop()

        with open(report_path) as f:
            report = json.load(f)

        good_r = next((r for r in report["results"] if r["task_id"] == "good_hash"), None)
        check("B1: result exists", good_r is not None)
        if good_r:
            check("B2: state=COMPLETED", good_r["state"] == "COMPLETED")
            check("B3: hash_result=OK", good_r.get("hash_result") == "OK")
            check("B4: expected_sha256 in report",
                  good_r.get("expected_sha256") == correct_hash)
            check("B5: file exists", os.path.isfile(good_r["final_path"]))

        # ------------------------------------------------------------------
        # Test C: Wrong hash -> FAILED + no file
        # ------------------------------------------------------------------
        print()
        print("--- Test C: Wrong hash -> FAILED ---")

        server2 = LocalRangeServer()
        base_url2, serve_dir2 = server2.start()

        with open(os.path.join(serve_dir2, "bad.bin"), "wb") as f:
            f.write(file_data)

        dl_dir_c = os.path.join(tmp, "dl_c")
        os.makedirs(dl_dir_c)
        report_c = os.path.join(tmp, "report_c.json")
        capture.events.clear()

        wrong_hash = "0" * 64

        try:
            batch_c = {
                "items": [
                    {"id": "bad_hash", "url": f"{base_url2}/range/bad.bin",
                     "filename": "bad.bin", "dest_dir": dl_dir_c,
                     "sha256": wrong_hash},
                ]
            }
            exit_code_c = run_batch(batch_c, report_path=report_c)
        finally:
            server2.stop()

        with open(report_c) as f:
            report_c_data = json.load(f)

        bad_r = next((r for r in report_c_data["results"] if r["task_id"] == "bad_hash"), None)
        check("C1: result exists", bad_r is not None)
        if bad_r:
            check("C2: state=FAILED", bad_r["state"] == "FAILED")
            check("C3: hash_result=MISMATCH", bad_r.get("hash_result") == "MISMATCH")
            check("C4: error contains HASH_MISMATCH",
                  "HASH_MISMATCH" in (bad_r.get("error") or ""))
            check("C5: no final file left",
                  not os.path.exists(os.path.join(dl_dir_c, "bad.bin")))

        # ------------------------------------------------------------------
        # Test D: No sha256 -> COMPLETED (unchecked)
        # ------------------------------------------------------------------
        print()
        print("--- Test D: No hash -> COMPLETED (unchecked) ---")

        server3 = LocalRangeServer()
        base_url3, serve_dir3 = server3.start()

        with open(os.path.join(serve_dir3, "nocheck.bin"), "wb") as f:
            f.write(file_data)

        dl_dir_d = os.path.join(tmp, "dl_d")
        os.makedirs(dl_dir_d)
        report_d = os.path.join(tmp, "report_d.json")

        try:
            batch_d = {
                "items": [
                    {"id": "no_hash", "url": f"{base_url3}/range/nocheck.bin",
                     "filename": "nocheck.bin", "dest_dir": dl_dir_d},
                ]
            }
            exit_code_d = run_batch(batch_d, report_path=report_d)
        finally:
            server3.stop()

        with open(report_d) as f:
            report_d_data = json.load(f)

        no_r = next((r for r in report_d_data["results"] if r["task_id"] == "no_hash"), None)
        check("D1: result exists", no_r is not None)
        if no_r:
            check("D2: state=COMPLETED", no_r["state"] == "COMPLETED")
            check("D3: hash_result=UNCHECKED", no_r.get("hash_result") == "UNCHECKED")
            check("D4: file exists", os.path.isfile(no_r["final_path"]))

        # ------------------------------------------------------------------
        # Test E: Security event for HASH_MISMATCH
        # ------------------------------------------------------------------
        print()
        print("--- Test E: Security events ---")

        mismatch_events = [e for e in capture.events if "SECURITY.HASH_MISMATCH" in e]
        check("E1: HASH_MISMATCH event emitted", len(mismatch_events) >= 1,
              f"count={len(mismatch_events)}")
        if mismatch_events:
            check("E2: event mentions expected hash",
                  wrong_hash in mismatch_events[0])

        # ------------------------------------------------------------------
        # Test F: No orphans
        # ------------------------------------------------------------------
        print()
        print("--- Test F: No orphans ---")

        orphans = []
        for d in [dl_dir, dl_dir_c, dl_dir_d]:
            for root, dirs, files in os.walk(d):
                for fname in files:
                    if fname.endswith((".part", ".resume")):
                        orphans.append(os.path.join(root, fname))
        check("F1: no .part/.resume orphans", len(orphans) == 0,
              f"orphans={orphans}" if orphans else "clean")

    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        sec_logger.removeHandler(capture)
        _restore()

    # --- Overall ---
    print()
    if overall:
        print("OVERALL: PASS")
    else:
        print("OVERALL: FAIL")
    sys.exit(0 if overall else 1)


if __name__ == "__main__":
    main()
