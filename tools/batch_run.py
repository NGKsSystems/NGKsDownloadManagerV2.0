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
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

# Resolve project root
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from tools.batch_schema import validate_batch_dict
from tools.forensics import (
    git_short_rev as _git_short_rev,
    app_version as _app_version,
    policy_version_hash as _policy_version_hash,
    os_platform as _os_platform,
    python_version as _python_version,
    get_naming_preset,
    build_display_name,
    append_alias_index,
)
from queue_manager import QueueManager, TaskState
from download_manager import DownloadManager
from security import safe_join, sanitize_filename, PathTraversalError, choose_final_dir, log_security_event

logger = logging.getLogger("batch_run")


# ---------------------------------------------------------------------------
# F16: Forensics metadata helpers
# ---------------------------------------------------------------------------


def _extract_host(url: str) -> str:
    from urllib.parse import urlparse
    try:
        return (urlparse(url).hostname or "").lower() or "unknown"
    except Exception:
        return "unknown"


def _classify_failure(state: str, error: str | None) -> str:
    """Return a short failure category string."""
    if state == "COMPLETED":
        return "none"
    if state == "DENIED":
        return "policy_denied"
    if not error:
        return "unknown"
    el = error.lower()
    if "hash_mismatch" in el:
        return "hash_mismatch"
    if "timeout" in el:
        return "timeout"
    if "connection" in el or "network" in el:
        return "network_error"
    return "download_error"


def build_log_folder(base: str, mode: str, summary: Dict[str, int],
                     short_id: str = "") -> str:
    """Build the CANONICAL log folder path (never changes with preset):
    YYYY-MM-DD/HHMMSS - <mode> - <summary> - <shortid>/

    The canonical path is always summary-style for traceability.
    Display name / aliases are layered on top via session_meta.json.
    """
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H%M%S")
    c = summary.get("completed", 0)
    f = summary.get("failed", 0) + summary.get("denied", 0)
    if f == 0:
        tag = f"{c}ok"
    else:
        tag = f"{c}ok_{f}fail"
    sid = short_id or uuid.uuid4().hex[:8]
    folder_name = f"{time_str} - {mode} - {tag} - {sid}"
    return os.path.join(base, date_str, folder_name), time_str, tag, sid


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
    _expected_sha256: Dict[str, str] = {}  # task_id -> normalized lowercase hex

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
                "host": _extract_host(item["url"]),
                "final_path": raw_filename,
                "state": "DENIED",
                "bytes_total": 0,
                "bytes_downloaded": 0,
                "started_at": now_utc,
                "ended_at": now_utc,
                "error": f"path traversal blocked: {e}",
                "failure_category": "policy_denied",
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
        # F11: store expected sha256 if provided
        item_sha = item.get("sha256")
        if item_sha:
            _expected_sha256[item["id"]] = item_sha.lower()

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
                "host": _extract_host(item["url"]),
                "final_path": dest,
                "state": "DENIED",
                "bytes_total": 0,
                "bytes_downloaded": 0,
                "started_at": now_utc,
                "ended_at": now_utc,
                "error": str(e),
                "failure_category": "policy_denied",
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
        hash_result = "NONE"
        error = task_dict.get("error")

        if state == "COMPLETED" and os.path.exists(dest):
            sha = _sha256_file(dest)
            file_size = os.path.getsize(dest)

            # F11: sha256 verification if expected hash was provided
            expected = _expected_sha256.get(tid)
            if expected:
                if sha == expected:
                    hash_result = "OK"
                else:
                    hash_result = "MISMATCH"
                    state = "FAILED"
                    error = f"HASH_MISMATCH: expected={expected} actual={sha}"
                    log_security_event("HASH_MISMATCH",
                                       task_id=tid,
                                       final_path=dest,
                                       detail=f"expected={expected} actual={sha}",
                                       decision="DENY")
                    # Remove the file — do not leave mismatched content
                    try:
                        os.unlink(dest)
                    except OSError:
                        pass
                    file_size = 0
            elif sha:
                hash_result = "UNCHECKED"

        qmeta = _quarantine_map.get(tid, {})
        expected_sha = _expected_sha256.get(tid)
        task_url = task_dict["url"]
        results.append({
            "task_id": tid,
            "url": task_url,
            "host": _extract_host(task_url),
            "final_path": dest,
            "state": state,
            "bytes_total": file_size,
            "bytes_downloaded": file_size if state == "COMPLETED" else 0,
            "sha256": sha,
            "expected_sha256": expected_sha,
            "hash_result": hash_result,
            "started_at": task_dict.get("created_at", now_utc),
            "ended_at": task_dict.get("updated_at", now_utc),
            "error": error,
            "failure_category": _classify_failure(state, error),
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
        "app_version": _app_version(),
        "git_rev": _git_short_rev(),
        "policy_version_hash": _policy_version_hash(),
        "os": _os_platform(),
        "python_version": _python_version(),
        "results": results,
        "summary": summary,
    }

    # --- Write report + session log folder ---
    log_dir, log_time_str, summary_tag, log_sid = build_log_folder(
        os.path.join(_PROJECT_ROOT, "logs"),
        "batch", summary,
    )
    os.makedirs(log_dir, exist_ok=True)

    # F17: Compute display name based on user preset
    preset = get_naming_preset()
    # Extract primary_host and first_filename from items for host/firstfile presets
    primary_host = ""
    first_filename = ""
    if items:
        first_url = items[0].get("url", "")
        primary_host = _extract_host(first_url)
        first_filename = (
            items[0].get("filename")
            or first_url.rstrip("/").split("/")[-1]
            or "download"
        )
    display_name = build_display_name(
        preset=preset,
        mode="batch",
        short_id=log_sid,
        summary_tag=summary_tag,
        primary_host=primary_host,
        first_filename=first_filename,
        time_str=log_time_str,
    )

    # Canonical relative path (date/folder_name)
    canonical_rel = os.path.relpath(log_dir, os.path.join(_PROJECT_ROOT, "logs"))

    session_meta = {
        "run_id": report["run_id"],
        "started_at": now_utc,
        "canonical_path": canonical_rel,
        "display_name": display_name,
        "naming_preset": preset,
        "aliases": [display_name],
        "app_version": report["app_version"],
        "git_rev": report["git_rev"],
        "policy_version_hash": report["policy_version_hash"],
        "os": report["os"],
        "python_version": report["python_version"],
        "summary": summary,
    }
    meta_path = os.path.join(log_dir, "session_meta.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(session_meta, f, indent=2)

    # F17: Append to alias index
    try:
        append_alias_index(
            run_id=report["run_id"],
            canonical_rel=canonical_rel,
            display_name=display_name,
            preset=preset,
            ts=now_utc,
        )
    except Exception:
        pass  # alias index is best-effort

    if report_path:
        os.makedirs(os.path.dirname(os.path.abspath(report_path)), exist_ok=True)
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        logger.info(f"BATCH | REPORT | path={report_path}")
    logger.info(f"BATCH | LOG_DIR | path={log_dir}")

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
