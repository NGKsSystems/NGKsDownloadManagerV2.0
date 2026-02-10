#!/usr/bin/env python3
"""
F12 Gate Test: Archive Path Safety Primitives (ZipSlip Guard)

Proves:
  A. safe_extract_path allows valid member paths
  B. safe_extract_path blocks parent traversal (..)
  C. safe_extract_path blocks absolute paths
  D. safe_extract_path blocks UNC paths
  E. safe_extract_path blocks drive letters
  F. safe_extract_path blocks null bytes
  G. SECURITY.ARCHIVE_PATH_BLOCKED events emitted
  H. ArchivePathBlockedError is raised (not generic Exception)

Deterministic, headless, offline (<2s).
"""

import logging
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from security import safe_extract_path, ArchivePathBlockedError


class SecurityLogCapture(logging.Handler):
    def __init__(self):
        super().__init__()
        self.events: list[str] = []

    def emit(self, record):
        msg = self.format(record)
        if "SECURITY." in msg:
            self.events.append(msg)


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

    print("=== F12 Gate Test: Archive Path Safety Primitives ===")
    print()

    sec_logger = logging.getLogger("security")
    sec_logger.setLevel(logging.DEBUG)
    capture = SecurityLogCapture()
    capture.setFormatter(logging.Formatter("%(message)s"))
    sec_logger.addHandler(capture)

    tmp = tempfile.mkdtemp(prefix="f12_gate_")
    base = os.path.join(tmp, "extract_root")
    os.makedirs(base)

    try:
        # ------------------------------------------------------------------
        # Test A: Valid paths
        # ------------------------------------------------------------------
        print("--- Test A: Valid member paths ---")

        r1 = safe_extract_path(base, "file.txt")
        check("A1: simple file resolves", os.path.basename(r1) == "file.txt")
        check("A2: inside base", r1.startswith(os.path.realpath(base)))

        r2 = safe_extract_path(base, "subdir/nested/file.bin")
        check("A3: nested path resolves", r2.endswith("file.bin"))
        check("A4: nested inside base", r2.startswith(os.path.realpath(base)))

        r3 = safe_extract_path(base, "dir/")
        check("A5: trailing slash dir resolves", r3.startswith(os.path.realpath(base)))

        # ------------------------------------------------------------------
        # Test B: Parent traversal (..)
        # ------------------------------------------------------------------
        print()
        print("--- Test B: Parent traversal blocked ---")
        capture.events.clear()

        blocked = False
        correct_error = False
        try:
            safe_extract_path(base, "../etc/passwd")
        except ArchivePathBlockedError:
            blocked = True
            correct_error = True
        except Exception:
            blocked = True
        check("B1: ../etc/passwd blocked", blocked)
        check("B2: ArchivePathBlockedError raised", correct_error)

        blocked2 = False
        try:
            safe_extract_path(base, "sub/../../etc/shadow")
        except ArchivePathBlockedError:
            blocked2 = True
        check("B3: sub/../../etc/shadow blocked", blocked2)

        blocked3 = False
        try:
            safe_extract_path(base, "..\\windows\\system32\\cmd.exe")
        except ArchivePathBlockedError:
            blocked3 = True
        check("B4: ..\\windows backslash traversal blocked", blocked3)

        # ------------------------------------------------------------------
        # Test C: Absolute paths
        # ------------------------------------------------------------------
        print()
        print("--- Test C: Absolute paths blocked ---")

        blocked_abs = False
        try:
            safe_extract_path(base, "/etc/passwd")
        except ArchivePathBlockedError:
            blocked_abs = True
        check("C1: /etc/passwd blocked", blocked_abs)

        # ------------------------------------------------------------------
        # Test D: UNC paths
        # ------------------------------------------------------------------
        print()
        print("--- Test D: UNC paths blocked ---")

        blocked_unc = False
        try:
            safe_extract_path(base, "\\\\server\\share\\file.txt")
        except ArchivePathBlockedError:
            blocked_unc = True
        check("D1: \\\\server\\share blocked", blocked_unc)

        # ------------------------------------------------------------------
        # Test E: Drive letters
        # ------------------------------------------------------------------
        print()
        print("--- Test E: Drive letters blocked ---")

        blocked_drive = False
        try:
            safe_extract_path(base, "C:\\Windows\\System32\\calc.exe")
        except ArchivePathBlockedError:
            blocked_drive = True
        check("E1: C:\\ drive letter blocked", blocked_drive)

        blocked_drive2 = False
        try:
            safe_extract_path(base, "D:autorun.inf")
        except ArchivePathBlockedError:
            blocked_drive2 = True
        check("E2: D: drive letter (no slash) blocked", blocked_drive2)

        # ------------------------------------------------------------------
        # Test F: Null bytes
        # ------------------------------------------------------------------
        print()
        print("--- Test F: Null bytes blocked ---")

        blocked_null = False
        try:
            safe_extract_path(base, "file.txt\x00.exe")
        except ArchivePathBlockedError:
            blocked_null = True
        check("F1: null byte blocked", blocked_null)

        # ------------------------------------------------------------------
        # Test G: Security events
        # ------------------------------------------------------------------
        print()
        print("--- Test G: Security events ---")

        archive_events = [e for e in capture.events
                          if "SECURITY.ARCHIVE_PATH_BLOCKED" in e]
        check("G1: ARCHIVE_PATH_BLOCKED events emitted",
              len(archive_events) >= 5,  # B1,B3,B4,C1,D1,E1,E2,F1
              f"count={len(archive_events)}")

        has_traversal = any("parent_traversal" in e for e in archive_events)
        check("G2: parent_traversal reason present", has_traversal)

        has_absolute = any("absolute_path" in e for e in archive_events)
        check("G3: absolute_path reason present", has_absolute)

        has_unc = any("unc_path" in e for e in archive_events)
        check("G4: unc_path reason present", has_unc)

        has_drive = any("drive_letter" in e for e in archive_events)
        check("G5: drive_letter reason present", has_drive)

        has_null = any("null_byte" in e for e in archive_events)
        check("G6: null_byte reason present", has_null)

    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        sec_logger.removeHandler(capture)

    # --- Overall ---
    print()
    if overall:
        print("OVERALL: PASS")
    else:
        print("OVERALL: FAIL")
    sys.exit(0 if overall else 1)


if __name__ == "__main__":
    main()
