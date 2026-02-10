#!/usr/bin/env python3
"""
F5 Gate Test: Batch Import + Batch Run  (deterministic, offline)

Test flow:
  1. Start LocalRangeServer with 3 deterministic files (100KB, 256KB, 512KB)
  2. Write a CSV with those URLs
  3. Import CSV -> batch.json  via batch_import
  4. Validate via batch_schema
  5. Run via batch_run (Option A: QueueManager.enqueue -> execute)
  6. Assert:
       - report summary completed == 3
       - all downloaded files exist with correct SHA-256
       - no orphan .part / .resume files
  7. Cleanup

OVERALL: PASS / FAIL printed last line.
"""

import csv
import hashlib
import json
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from local_range_server import LocalRangeServer
from tools.batch_schema import validate_batch_dict
from tools.batch_import import import_csv
from tools.batch_run import run_batch


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

    print("=== F5 Gate Test: Batch Import + Batch Run ===")
    print()

    # --- Setup ---
    server = LocalRangeServer()
    base_url, serve_dir = server.start()
    print(f"[SETUP] Server: {base_url}")

    test_files = {}
    sizes = [100 * 1024, 256 * 1024, 512 * 1024]
    for idx, size in enumerate(sizes):
        data = bytes(range(256)) * (size // 256)
        fname = f"batch_test_{idx}.bin"
        path = os.path.join(serve_dir, fname)
        with open(path, "wb") as f:
            f.write(data)
        test_files[fname] = {
            "size": len(data),
            "hash": sha256_bytes(data),
            "url": f"{base_url}/range/{fname}",
        }
    print(f"[SETUP] Created {len(test_files)} test files")

    work_dir = tempfile.mkdtemp(prefix="f5_gate_")
    dl_dir = os.path.join(work_dir, "downloads")
    os.makedirs(dl_dir)

    try:
        # --- Test A: CSV import ---
        print()
        print("--- Test A: CSV import ---")
        csv_path = os.path.join(work_dir, "input.csv")
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["url", "filename", "dest_dir", "priority", "tags"])
            for fname, info in test_files.items():
                writer.writerow([info["url"], fname, dl_dir, 5, "test,batch"])

        batch = import_csv(csv_path, defaults={"connections": 1})
        check("A1: import produced dict", isinstance(batch, dict))
        check("A2: items count == 3", len(batch.get("items", [])) == 3,
              f"got {len(batch.get('items', []))}")

        # --- Test B: Validation ---
        print()
        print("--- Test B: Schema validation ---")
        errors = validate_batch_dict(batch)
        check("B1: validation passes", len(errors) == 0,
              "; ".join(errors) if errors else "no errors")

        # Write batch.json for runner
        batch_json_path = os.path.join(work_dir, "batch.json")
        with open(batch_json_path, "w") as f:
            json.dump(batch, f, indent=2)

        # --- Test C: Batch run ---
        print()
        print("--- Test C: Batch run (Option A) ---")
        report_path = os.path.join(work_dir, "report.json")

        exit_code = run_batch(
            batch,
            report_path=report_path,
            max_concurrent=2,
            until="empty",
        )
        check("C1: exit code == 0", exit_code == 0, f"got {exit_code}")

        # Load report
        with open(report_path, "r") as f:
            report = json.load(f)

        summary = report.get("summary", {})
        check("C2: report.summary.completed == 3", summary.get("completed") == 3,
              f"got {summary}")
        check("C3: report.summary.failed == 0", summary.get("failed", 0) == 0)
        check("C4: report.summary.denied == 0", summary.get("denied", 0) == 0)

        # --- Test D: File integrity ---
        print()
        print("--- Test D: File integrity ---")
        for fname, info in test_files.items():
            dest = os.path.join(dl_dir, fname)
            exists = os.path.exists(dest)
            check(f"D-{fname}: exists", exists)
            if exists:
                got_hash = sha256_file(dest)
                check(f"D-{fname}: sha256 match", got_hash == info["hash"],
                      f"expected {info['hash'][:16]}... got {got_hash[:16]}...")

        # --- Test E: No orphan .part / .resume ---
        print()
        print("--- Test E: Orphan check ---")
        orphans = []
        for f in os.listdir(dl_dir):
            if f.endswith(".part") or f.endswith(".resume"):
                orphans.append(f)
        check("E1: no orphan .part/.resume", len(orphans) == 0,
              f"found: {orphans}" if orphans else "clean")

    finally:
        server.stop()
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
