#!/usr/bin/env python3
"""
F7: Desktop Security Hardening Module
--------------------------------------
Structural safety guarantees for file downloads.

NOT antivirus. NOT heuristics. NOT sandboxing.
This module enforces:
  - Path containment (no traversal, no escape)
  - Filename normalization (no deception, no control chars)
  - Executable classification (warning, not blocking)
  - Rider file detection (one URL -> one file)
  - Audit-grade security logging
"""

import logging
import os
import re
import unicodedata
from datetime import datetime, timezone
from typing import List, Optional, Set, Tuple

logger = logging.getLogger("security")


# ---------------------------------------------------------------------------
# Dangerous extension set (Step 2)
# ---------------------------------------------------------------------------

DANGEROUS_EXTENSIONS: Set[str] = frozenset({
    ".exe", ".msi", ".bat", ".cmd", ".ps1", ".vbs", ".js",
    ".jar", ".scr", ".com", ".dll", ".wsf", ".wsh", ".pif",
    ".hta", ".cpl", ".inf", ".reg",
})

# Unicode bidi overrides and control chars to strip
_BIDI_OVERRIDES = set(range(0x202A, 0x202F)) | set(range(0x2066, 0x206A))
_CONTROL_CHARS = set(range(0x00, 0x20)) | {0x7F} | set(range(0x80, 0xA0))
_STRIP_CODEPOINTS = _BIDI_OVERRIDES | _CONTROL_CHARS


# ---------------------------------------------------------------------------
# 1.1 Path Containment
# ---------------------------------------------------------------------------

class PathTraversalError(Exception):
    """Raised when a path escapes the designated root."""
    pass


def safe_join(base: str, target: str) -> str:
    """Join base + target and assert the result is inside base.

    Rejects:
      - ``..`` components
      - Absolute paths in target
      - UNC paths (``\\\\server``)
      - Drive-letter injection (``C:``)
      - Symlinks that escape base

    Returns the resolved absolute path.
    Raises PathTraversalError on violation.
    """
    if not base:
        raise PathTraversalError("base path is empty")
    if not target:
        raise PathTraversalError("target path is empty")

    # Reject absolute targets
    if os.path.isabs(target):
        _log_security_event("PATH_TRAVERSAL_BLOCKED", reason="absolute target",
                            detail=f"target={target}")
        raise PathTraversalError(f"absolute target path rejected: {target!r}")

    # Reject UNC paths
    if target.startswith("\\\\") or target.startswith("//"):
        _log_security_event("PATH_TRAVERSAL_BLOCKED", reason="UNC path",
                            detail=f"target={target}")
        raise PathTraversalError(f"UNC path rejected: {target!r}")

    # Reject drive letter injection (e.g. "C:" or "D:\")
    if len(target) >= 2 and target[1] == ":":
        _log_security_event("PATH_TRAVERSAL_BLOCKED", reason="drive letter injection",
                            detail=f"target={target}")
        raise PathTraversalError(f"drive letter injection rejected: {target!r}")

    # Reject explicit ".." components
    parts = target.replace("\\", "/").split("/")
    if ".." in parts:
        _log_security_event("PATH_TRAVERSAL_BLOCKED", reason="parent traversal",
                            detail=f"target={target}")
        raise PathTraversalError(f"path traversal rejected: {target!r}")

    # Resolve and containment check
    resolved_base = os.path.realpath(os.path.abspath(base))
    joined = os.path.join(resolved_base, target)
    resolved = os.path.realpath(os.path.abspath(joined))

    # Prefix check -- resolved must start with resolved_base
    if not resolved.startswith(resolved_base + os.sep) and resolved != resolved_base:
        _log_security_event("PATH_TRAVERSAL_BLOCKED", reason="resolved path escapes root",
                            detail=f"base={resolved_base} resolved={resolved}")
        raise PathTraversalError(
            f"path escapes root: base={resolved_base!r} resolved={resolved!r}")

    return resolved


# ---------------------------------------------------------------------------
# 1.2 Filename Normalization
# ---------------------------------------------------------------------------

def sanitize_filename(name: str, max_length: int = 200) -> str:
    """Normalize a filename for safe filesystem use.

    - NFKC Unicode normalization
    - Strip Unicode bidi overrides
    - Strip control characters
    - Collapse whitespace
    - Replace path separators
    - Truncate to max_length (preserving extension)
    - Fallback to 'download' if nothing remains
    """
    if not name:
        return "download"

    original = name

    # NFKC normalization
    name = unicodedata.normalize("NFKC", name)

    # Strip dangerous codepoints
    name = "".join(ch for ch in name if ord(ch) not in _STRIP_CODEPOINTS)

    # Replace path separators with underscore
    name = name.replace("/", "_").replace("\\", "_")

    # Collapse whitespace
    name = re.sub(r"\s+", " ", name).strip()

    # Remove leading/trailing dots (Windows hidden file / extension confusion)
    name = name.strip(".")

    if not name:
        name = "download"

    # Truncate preserving extension
    if len(name) > max_length:
        stem, ext = os.path.splitext(name)
        if ext:
            stem = stem[:max_length - len(ext)]
            name = stem + ext
        else:
            name = name[:max_length]

    if name != original:
        _log_security_event("FILENAME_NORMALIZED",
                            detail=f"original={original!r} normalized={name!r}")

    return name


# ---------------------------------------------------------------------------
# 2. Executable Classification
# ---------------------------------------------------------------------------

def classify_executable_risk(filepath: str) -> Optional[str]:
    """Check if a file has a dangerous extension.

    Returns risk label string if dangerous, None if safe.
    Does NOT block the download -- warning only.
    """
    _, ext = os.path.splitext(filepath.lower())
    if ext in DANGEROUS_EXTENSIONS:
        return "EXECUTABLE_PAYLOAD"
    # Double extension detection (e.g. .pdf.exe)
    stem_no_ext = os.path.splitext(os.path.splitext(filepath)[0])[1]
    if stem_no_ext and ext in DANGEROUS_EXTENSIONS:
        return "EXECUTABLE_PAYLOAD"
    return None


def warn_if_executable(filepath: str, task_id: str = "unknown",
                       url: str = "") -> Optional[str]:
    """Emit warning if file is an executable type.

    Returns the risk label if applicable, None otherwise.
    """
    risk = classify_executable_risk(filepath)
    if risk:
        _log_security_event("EXECUTABLE_WARNING",
                            task_id=task_id, url=url,
                            final_path=filepath,
                            detail=f"risk={risk} ext={os.path.splitext(filepath)[1]}")
    return risk


# ---------------------------------------------------------------------------
# 3. Rider File Detection
# ---------------------------------------------------------------------------

def check_rider_files(expected_path: str, directory: str,
                      task_id: str = "unknown",
                      url: str = "") -> List[str]:
    """Detect unexpected files in the download directory.

    One URL must produce exactly one file.
    Returns list of rider file paths (empty = clean).
    """
    if not os.path.isdir(directory):
        return []

    expected_base = os.path.basename(expected_path)
    expected_part = expected_base + ".part"
    expected_resume = expected_base + ".resume"

    riders = []
    for fname in os.listdir(directory):
        full = os.path.join(directory, fname)
        if not os.path.isfile(full):
            continue
        # Expected: the final file, its .part temp, or its .resume state
        if fname in (expected_base, expected_part, expected_resume):
            continue
        # Everything else in a per-task directory is a rider
        riders.append(full)

    if riders:
        _log_security_event("RIDER_FILE_DETECTED",
                            task_id=task_id, url=url,
                            final_path=expected_path,
                            detail=f"riders={[os.path.basename(r) for r in riders]}")

    return riders


# ---------------------------------------------------------------------------
# 4. Auto-Execution Prevention (audit helper)
# ---------------------------------------------------------------------------

# Forbidden APIs in download codepath -- checked by gate test, not at runtime.
AUTO_EXEC_FORBIDDEN = frozenset({
    "os.startfile",
    "os.system",
    "subprocess.call",
    "subprocess.check_call",
    "subprocess.check_output",
    "subprocess.run",
    "subprocess.Popen",
})


# ---------------------------------------------------------------------------
# 5. Audit-Grade Security Logging
# ---------------------------------------------------------------------------

def _log_security_event(event_type: str, task_id: str = "",
                        url: str = "", final_path: str = "",
                        reason: str = "", detail: str = "",
                        decision: str = "") -> None:
    """Emit a structured security log event.

    Format: SECURITY.<EVENT> | key=value | ...
    All values are sanitized to prevent log injection.
    """
    # Sanitize all values -- replace pipe and newline to prevent forgery
    def _safe(val: str) -> str:
        return val.replace("|", "_").replace("\n", "_").replace("\r", "_")

    parts = [f"SECURITY.{event_type}"]
    if task_id:
        parts.append(f"task_id={_safe(task_id)}")
    if url:
        parts.append(f"url={_safe(url[:120])}")
    if final_path:
        parts.append(f"final_path={_safe(final_path)}")
    if reason:
        parts.append(f"reason={_safe(reason)}")
    if decision:
        parts.append(f"decision={_safe(decision)}")
    if detail:
        parts.append(f"detail={_safe(detail)}")
    parts.append(f"ts={datetime.now(timezone.utc).isoformat()}")

    msg = " | ".join(parts)

    if event_type in ("PATH_TRAVERSAL_BLOCKED", "RIDER_FILE_DETECTED"):
        logger.warning(msg)
    elif event_type == "EXECUTABLE_WARNING":
        logger.warning(msg)
    else:
        logger.info(msg)
