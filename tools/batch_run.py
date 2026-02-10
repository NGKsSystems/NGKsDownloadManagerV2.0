#!/usr/bin/env python3
"""
Batch runner: load batch.json -> enqueue into QueueManager -> execute -> report.
F5 contract -- NGKs DL Manager V2.x (Option A path).
"""

import argparse
import hashlib
import json
import logging
import os
import signal
import sys
import threading
import time
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

# Resolve project root
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from tools.batch_schema import validate_batch_dict
from queue_manager import QueueManager, TaskState
from download_manager import DownloadManager
from security import safe_join, sanitize_filename, PathTraversalError, choose_final_dir

logger = logging.getLogger("batch_run")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sha256_file(path: str) -> Optional[str]:
    """Compute SHA-256 hex digest of a file. Returns None on error."""
    try:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return None


def _make_downloader_func(dm: DownloadManager) -> Callable:
    """Build a downloader function compatible with QueueManager._worker_thread."""

    def _download(url: str, destination: str, task_id: str = "unknown",
                  progress_callback: Optional[Callable] = None, **kwargs) -> bool:
        cancel_event = kwargs.get("cancel_event", threading.Event())
        success = dm._basic_download(url, destination, progress_callback=progress_callback,
                                     resume=True, task_id=task_id)
        return success

    return _download


# ---------------------------------------------------------------------------
# Core batch execution
# ---------------------------------------------------------------------------

def run_batch(batch: Dict[str, Any], report_path: Optional[str] = None,
              max_concurrent: int = 2, until: str = "empty",
              stop_on_fail: bool = False) -> int:
    """Execute a validated batch dict.

    Returns F4 exit code:
      0 = all completed
      4 = partial failure
      1 = unexpected error
    """
    now_utc = datetime.now(timezone.utc).isoformat()

    defaults = batch.get("defaults", {})
    items = batch["items"]

    # --- Build QueueManager ---
    qm = QueueManager(max_active_downloads=max_concurrent, retry_enabled=False)
    dm = DownloadManager(enable_multi_connection=False)
    qm.set_downloader(_make_downloader_func(dm))

    # --- Merge defaults + enqueue ---
    denied_items: List[Dict[str, Any]] = []
    _quarantine_map: Dict[str, Dict[str, Any]] = {}

    for item in items:
        dest_dir = item.get("dest_dir") or defaults.get("dest_dir") or "downloads"
        raw_filename = item.get("filename") or item["url"].rstrip("/").split("/")[-1] or "download"
        # F7: sanitize filename + path containment
        filename = sanitize_filename(raw_filename)
        # F10: quarantine risky extensions
        final_dir, quarantined = choose_final_dir(dest_dir, filename)
        try:
            dest = safe_join(final_dir, filename)
        except PathTraversalError as e:
            logger.warning(f"BATCH | DENIED | id={item['id']} | reason=path_traversal: {e}")
            print(f"DENIED: {item['id']} -- path traversal blocked: {e}", file=sys.stderr)
            denied_items.append({
                "task_id": item["id"],
                "url": item["url"],
                "final_path": raw_filename,
                "state": "DENIED",
                "bytes_total": 0,
                "bytes_downloaded": 0,
                "started_at": now_utc,
                "ended_at": now_utc,
                "error": f"path traversal blocked: {e}",
                "quarantined": quarantined,
                "quarantine_reason": "dangerous_extension" if quarantined else None,
            })
            continue
        os.makedirs(final_dir, exist_ok=True)

        priority = item.get("priority") or defaults.get("priority") or 5
        connections = item.get("connections") or defaults.get("connections") or 1

        # Track quarantine metadata per item
        _quarantine_meta = {
            "quarantined": quarantined,
            "quarantine_reason": "dangerous_extension" if quarantined else None,
        }

        try:
            qm.enqueue(
                task_id=item["id"],
                url=item["url"],
                destination=dest,
                priority=priority,
                mode="auto",
                connections=connections,
            )
            # Stash quarantine metadata to inject into report later
            if quarantined:
                _quarantine_map[item["id"]] = _quarantine_meta
            logger.info(f"BATCH | ENQUEUED | id={item['id']} | url={item['url'][:60]}"
                        + (f" | quarantined=true" if quarantined else ""))
        except ValueError as e:
            # Policy denied or duplicate -- clear message to stderr
            reason = str(e)
            logger.warning(f"BATCH | DENIED | id={item['id']} | reason={reason}")
            print(f"DENIED: {item['id']} -- {reason}", file=sys.stderr)
            denied_items.append({
                "task_id": item["id"],
                "url": item["url"],
                "final_path": dest,
                "state": "DENIED",
                "bytes_total": 0,
                "bytes_downloaded": 0,
                "started_at": now_utc,
                "ended_at": now_utc,
                "error": str(e),
                "quarantined": quarantined,
                "quarantine_reason": "dangerous_extension" if quarantined else None,
            })

    # --- Start scheduler ---
    qm.start_scheduler()

    # --- Wait for completion ---
    until_mode = until.split(":")[0]
    until_value = until.split(":")[1] if ":" in until else None

    deadline = None
    count_target = None

    if until_mode == "time" and until_value:
        deadline = time.time() + float(until_value)
    elif until_mode == "count" and until_value:
        count_target = int(until_value)

    # Hard timeout: 10 minutes max for safety
    hard_deadline = time.time() + 600

    while time.time() < hard_deadline:
        status = qm.get_status()
        states = status["state_counts"]
        completed = states.get("COMPLETED", 0)
        failed = states.get("FAILED", 0)
        cancelled = states.get("CANCELLED", 0)
        terminal = completed + failed + cancelled + len(denied_items)

        # until=empty: all items terminal
        if until_mode == "empty" and terminal >= len(items):
            break

        # until=time:N
        if deadline is not None and time.time() >= deadline:
            break

        # until=count:N
        if count_target is not None and completed >= count_target:
            break

        # --stop-on-fail
        if stop_on_fail and failed > 0:
            break

        time.sleep(0.3)

    qm.stop_scheduler()

    # --- Build report ---
    results: List[Dict[str, Any]] = []

    for task_dict in qm.list_tasks():
        tid = task_dict["task_id"]
        state = task_dict["state"]
        dest = task_dict["destination"]
        sha = None
        file_size = 0

        if state == "COMPLETED" and os.path.exists(dest):
            sha = _sha256_file(dest)
            file_size = os.path.getsize(dest)

        qmeta = _quarantine_map.get(tid, {})
        results.append({
            "task_id": tid,
            "url": task_dict["url"],
            "final_path": dest,
            "state": state,
            "bytes_total": file_size,
            "bytes_downloaded": file_size if state == "COMPLETED" else 0,
            "sha256": sha,
            "started_at": task_dict.get("created_at", now_utc),
            "ended_at": task_dict.get("updated_at", now_utc),
            "error": task_dict.get("error"),
            "quarantined": qmeta.get("quarantined", False),
            "quarantine_reason": qmeta.get("quarantine_reason"),
        })

    # Add denied items
    results.extend(denied_items)

    summary = {
        "completed": sum(1 for r in results if r["state"] == "COMPLETED"),
        "failed": sum(1 for r in results if r["state"] == "FAILED"),
        "cancelled": sum(1 for r in results if r["state"] == "CANCELLED"),
        "denied": sum(1 for r in results if r["state"] == "DENIED"),
    }

    report = {
        "run_id": now_utc,
        "mode": "batch",
        "results": results,
        "summary": summary,
    }

    # --- Write report ---
    if report_path:
        os.makedirs(os.path.dirname(os.path.abspath(report_path)), exist_ok=True)
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        logger.info(f"BATCH | REPORT | path={report_path}")

    # Print summary
    print(f"BATCH COMPLETE | completed={summary['completed']} failed={summary['failed']} "
          f"cancelled={summary['cancelled']} denied={summary['denied']}")

    # --- Exit code ---
    total = len(results)
    if summary["completed"] == total and total > 0:
        return 0
    elif summary["failed"] > 0 or summary["denied"] > 0 or summary["cancelled"] > 0:
        return 4
    else:
        return 1


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Batch Run: execute batch.json via QueueManager")
    parser.add_argument("--file", required=True, metavar="FILE", help="Canonical batch.json to execute")
    parser.add_argument("--report", default=None, metavar="FILE", help="Output JSON report path")
    parser.add_argument("--max-concurrent", type=int, default=2, help="Max concurrent downloads")
    parser.add_argument("--until", default="empty", help="empty | time:<sec> | count:<n>")
    parser.add_argument("--stop-on-fail", action="store_true", help="Abort on first failure")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")

    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.INFO, format="%(name)s: %(message)s")
    else:
        logging.basicConfig(level=logging.WARNING, format="%(name)s: %(message)s")

    # Load + validate
    if not os.path.exists(args.file):
        print(f"ERROR: batch file not found: {args.file}", file=sys.stderr)
        sys.exit(2)

    try:
        with open(args.file, "r", encoding="utf-8") as f:
            batch = json.load(f)
    except json.JSONDecodeError as e:
        print(f"ERROR: batch file is not valid JSON: {e}", file=sys.stderr)
        sys.exit(2)
    except OSError as e:
        print(f"ERROR: cannot read batch file: {e}", file=sys.stderr)
        sys.exit(2)

    errors = validate_batch_dict(batch)
    if errors:
        for err in errors:
            print(f"VALIDATION ERROR: {err}", file=sys.stderr)
        sys.exit(2)

    # SIGINT handler
    interrupted = False

    def _sigint_handler(sig, frame):
        nonlocal interrupted
        interrupted = True
        print("\nInterrupted by user.", file=sys.stderr)
        sys.exit(130)

    signal.signal(signal.SIGINT, _sigint_handler)

    try:
        exit_code = run_batch(
            batch,
            report_path=args.report,
            max_concurrent=args.max_concurrent,
            until=args.until,
            stop_on_fail=args.stop_on_fail,
        )
        sys.exit(exit_code)
    except Exception as e:
        print(f"UNEXPECTED ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
