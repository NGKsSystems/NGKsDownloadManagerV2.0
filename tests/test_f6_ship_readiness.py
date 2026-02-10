#!/usr/bin/env python3
"""
F6 Gate Test: Ship Readiness -- Policy Normalization + Batch Hardening

Proves:
  A. Policy hostname normalization (port stripped, denylist matches hostname only)
  B. Batch report correctly distinguishes COMPLETED / FAILED / DENIED
  C. Exit codes align with CLI contract (0 = all ok, 4 = partial)
  D. No orphan .part / .resume files after batch run

Deterministic, headless, fast (<10s).
"""

import hashlib
import json
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from policy_engine import PolicyEngine, get_policy_engine
from queue_manager import QueueManager
from local_range_server import LocalRangeServer
from tools.batch_run import run_batch
from tools.batch_schema import validate_batch_dict


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------

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

    print("=== F6 Gate Test: Ship Readiness ===")
    print()

    pe = get_policy_engine()
    orig_denylist = list(pe.policies.get("per_host", {}).get("denylist", []))

    # ------------------------------------------------------------------
    # Test A: Policy hostname normalization proof
    # ------------------------------------------------------------------
    print("--- Test A: Policy hostname normalization ---")

    # Ensure 'localhost' IS in the denylist for this test
    pe.policies.setdefault("per_host", {})["denylist"] = ["localhost", "127.0.0.1", "example.com"]

    # A1: http://localhost:9999/x  must be DENIED (hostname = localhost)
    qm_a = QueueManager(max_active_downloads=1, retry_enabled=False)
    denied_a1 = False
    try:
        qm_a.enqueue("a1", "http://localhost:9999/x", "/tmp/a1")
    except ValueError:
        denied_a1 = True
    check("A1: localhost:9999 denied by denylist", denied_a1)

    # A2: http://127.0.0.1:9999/x  must be DENIED (hostname = 127.0.0.1)
    denied_a2 = False
    try:
        qm_a.enqueue("a2", "http://127.0.0.1:9999/x", "/tmp/a2")
    except ValueError:
        denied_a2 = True
    check("A2: 127.0.0.1:9999 denied by denylist", denied_a2)

    # A3: http://192.0.2.1:9999/x  must be ALLOWED (not in denylist)
    allowed_a3 = False
    try:
        qm_a.enqueue("a3", "http://192.0.2.1:9999/x", "/tmp/a3")
        allowed_a3 = True
    except ValueError:
        allowed_a3 = False
    check("A3: 192.0.2.1:9999 allowed (not in denylist)", allowed_a3)

    # A4: http://example.com:443/x  must be DENIED (hostname = example.com)
    denied_a4 = False
    try:
        qm_a.enqueue("a4", "http://example.com:443/x", "/tmp/a4")
    except ValueError:
        denied_a4 = True
    check("A4: example.com:443 denied by denylist", denied_a4)

    # ------------------------------------------------------------------
    # Test B: Batch mixed outcomes (COMPLETED + FAILED + DENIED)
    # ------------------------------------------------------------------
    print()
    print("--- Test B: Batch mixed outcomes ---")

    # Whitelist localhost so the local server works, but keep example.com denied
    pe.policies["per_host"]["denylist"] = ["example.com"]

    server = LocalRangeServer()
    base_url, serve_dir = server.start()
    print(f"  [SETUP] Server: {base_url}")

    # Create one real file
    good_data = bytes(range(256)) * 400  # 100KB
    good_hash = sha256_bytes(good_data)
    good_fname = "f6_good.bin"
    with open(os.path.join(serve_dir, good_fname), "wb") as f:
        f.write(good_data)

    work_dir = tempfile.mkdtemp(prefix="f6_gate_")
    dl_dir = os.path.join(work_dir, "downloads")
    os.makedirs(dl_dir)
    report_path = os.path.join(work_dir, "report.json")

    try:
        batch = {
            "batch_id": "f6-mixed-test",
            "defaults": {"dest_dir": dl_dir, "connections": 1, "priority": 5},
            "items": [
                {"id": "good", "url": f"{base_url}/range/{good_fname}", "filename": good_fname},
                {"id": "bad404", "url": f"{base_url}/range/nonexistent_file.bin", "filename": "bad.bin"},
                {"id": "denied", "url": "https://example.com/blocked.zip", "filename": "blocked.zip"},
            ],
        }

        errs = validate_batch_dict(batch)
        check("B0: batch schema valid", len(errs) == 0, f"errors={errs}" if errs else "")

        exit_code = run_batch(batch, report_path=report_path, max_concurrent=2)

        check("B1: exit code is 4 (partial)", exit_code == 4, f"got {exit_code}")

        with open(report_path, "r", encoding="utf-8") as f:
            report = json.load(f)

        summary = report["summary"]
        check("B2: completed == 1", summary["completed"] == 1, f"got {summary['completed']}")
        check("B3: failed == 1", summary["failed"] == 1, f"got {summary['failed']}")
        check("B4: denied == 1", summary["denied"] == 1, f"got {summary['denied']}")

        # Verify completed file integrity
        good_dest = os.path.join(dl_dir, good_fname)
        check("B5: good file exists", os.path.exists(good_dest))
        if os.path.exists(good_dest):
            got_hash = sha256_file(good_dest)
            check("B6: good file SHA-256 match", got_hash == good_hash,
                  f"expected {good_hash[:16]}... got {got_hash[:16]}...")

        # Verify report result states
        states = {r["task_id"]: r["state"] for r in report["results"]}
        check("B7: 'good' state == COMPLETED", states.get("good") == "COMPLETED", f"got {states.get('good')}")
        check("B8: 'bad404' state == FAILED", states.get("bad404") == "FAILED", f"got {states.get('bad404')}")
        check("B9: 'denied' state == DENIED", states.get("denied") == "DENIED", f"got {states.get('denied')}")

        # Verify denied item has error message
        denied_result = next((r for r in report["results"] if r["task_id"] == "denied"), None)
        check("B10: denied item has error", denied_result is not None and bool(denied_result.get("error")),
              f"error={denied_result.get('error', 'MISSING')}" if denied_result else "no result")

    finally:
        server.stop()

    # ------------------------------------------------------------------
    # Test C: All-complete exit code
    # ------------------------------------------------------------------
    print()
    print("--- Test C: All-complete exit code ---")

    server2 = LocalRangeServer()
    base_url2, serve_dir2 = server2.start()

    c_data = b"F6_COMPLETE_TEST" * 1000
    c_fname = "f6_complete.bin"
    with open(os.path.join(serve_dir2, c_fname), "wb") as f:
        f.write(c_data)

    dl_dir_c = os.path.join(work_dir, "downloads_c")
    os.makedirs(dl_dir_c)
    report_path_c = os.path.join(work_dir, "report_c.json")

    try:
        batch_c = {
            "batch_id": "f6-complete-test",
            "defaults": {"dest_dir": dl_dir_c, "connections": 1, "priority": 5},
            "items": [
                {"id": "c1", "url": f"{base_url2}/range/{c_fname}", "filename": c_fname},
            ],
        }
        exit_code_c = run_batch(batch_c, report_path=report_path_c, max_concurrent=1)
        check("C1: exit code is 0 (all complete)", exit_code_c == 0, f"got {exit_code_c}")
    finally:
        server2.stop()

    # ------------------------------------------------------------------
    # Test D: No orphan files
    # ------------------------------------------------------------------
    print()
    print("--- Test D: Orphan check ---")
    for d in [dl_dir, dl_dir_c]:
        if os.path.isdir(d):
            for fname in os.listdir(d):
                if fname.endswith(".part") or fname.endswith(".resume"):
                    check(f"D: orphan found in {d}", False, f"orphan={fname}")
                    break
            else:
                continue
            break
    else:
        check("D1: no orphan .part/.resume", True)

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------
    pe.policies["per_host"]["denylist"] = orig_denylist
    shutil.rmtree(work_dir, ignore_errors=True)

    # --- Overall ---
    print()
    if overall:
        print("OVERALL: PASS")
    else:
        print("OVERALL: FAIL")
    sys.exit(0 if overall else 1)


if __name__ == "__main__":
    main()
