#!/usr/bin/env python3
"""
F8 Gate Test: yt-dlp Lifecycle Management (Trusted Source + Verify)

Proves:
  A. Version parsing works (import path + binary path simulation)
  B. SHA256SUMS parsing is correct
  C. Hash verify accepts correct hash
  D. Hash verify rejects wrong hash (installer refuses unverified artifact)
  E. Binary update with correct hash succeeds
  F. Binary update with wrong hash fails + no partial install
  G. No rider files created in install dir
  H. Security log events have correct structure (SECURITY.YTDLP.*)
  I. CLI subcommands are registered
  J. Environment detection returns valid values

Deterministic, headless, offline (<10s).
Uses LocalRangeServer to simulate the trusted source.
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
from ytdlp_manager import (
    get_current_ytdlp_version,
    get_latest_release_info,
    parse_sha256sums,
    compute_sha256,
    verify_sha256,
    update_via_binary,
    detect_environment,
    _versions_match,
    _get_binary_asset_name,
)


# ---------------------------------------------------------------------------
# Security log capture (same pattern as F7)
# ---------------------------------------------------------------------------

class SecurityLogCapture(logging.Handler):
    """Capture SECURITY.* log messages for assertion."""

    def __init__(self):
        super().__init__()
        self.events: list[str] = []

    def emit(self, record):
        msg = self.format(record)
        if "SECURITY." in msg:
            self.events.append(msg)


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

    print("=== F8 Gate Test: yt-dlp Lifecycle Management ===")
    print()

    # Attach security log capture
    sec_logger = logging.getLogger("security")
    sec_logger.setLevel(logging.DEBUG)
    capture = SecurityLogCapture()
    capture.setFormatter(logging.Formatter("%(message)s"))
    sec_logger.addHandler(capture)

    tmp = tempfile.mkdtemp(prefix="f8_gate_")

    all_security_events: list[str] = []  # accumulated across all sub-tests

    try:
        # ------------------------------------------------------------------
        # Test A: Version parsing
        # ------------------------------------------------------------------
        print("--- Test A: Version parsing ---")

        # A1: get_current_ytdlp_version returns a string (yt-dlp is installed)
        version = get_current_ytdlp_version()
        check("A1: current version detected",
              version is not None and isinstance(version, str) and len(version) > 0,
              f"version={version!r}")

        # A2: version looks like a date string (YYYY.MM.DD)
        if version:
            parts = version.split(".")
            check("A2: version format YYYY.MM.DD",
                  len(parts) >= 3 and parts[0].isdigit() and len(parts[0]) == 4,
                  f"parts={parts}")
        else:
            check("A2: version format YYYY.MM.DD", False, "no version detected")

        # A3: _versions_match works
        check("A3: versions_match equal", _versions_match("2024.12.06", "2024.12.06"))
        check("A4: versions_match not equal", not _versions_match("2024.12.06", "2025.01.01"))

        # ------------------------------------------------------------------
        # Test B: SHA256SUMS parsing
        # ------------------------------------------------------------------
        print()
        print("--- Test B: SHA256SUMS parsing ---")

        sums_content = (
            "abc123def456  yt-dlp\n"
            "789abc012def  yt-dlp.exe\n"
            "deadbeef0000  yt-dlp_macos\n"
            "# comment line\n"
            "1111222233334444  yt-dlp_linux\n"
        )
        parsed = parse_sha256sums(sums_content)

        check("B1: parsed 4 entries", len(parsed) == 4, f"got {len(parsed)}")
        check("B2: yt-dlp.exe hash correct",
              parsed.get("yt-dlp.exe") == "789abc012def")
        check("B3: yt-dlp_linux hash correct",
              parsed.get("yt-dlp_linux") == "1111222233334444")
        check("B4: comment line skipped", "#" not in str(parsed.keys()))

        # Parse with binary mode indicator (*)
        sums_star = "aabbccdd *yt-dlp.exe\n"
        parsed_star = parse_sha256sums(sums_star)
        check("B5: star filename parsed",
              parsed_star.get("yt-dlp.exe") == "aabbccdd")

        # B-extra: Exercise release info fetch (triggers YTDLP.CHECK event)
        # Use LocalRangeServer to serve a fake release JSON
        srv_check = LocalRangeServer()
        base_url_check, serve_dir_check = srv_check.start()
        fake_release = {
            "tag_name": "2099.01.01",
            "assets": [
                {"name": "SHA2-256SUMS", "browser_download_url": f"{base_url_check}/range/SHA2-256SUMS"},
                {"name": "yt-dlp.exe", "browser_download_url": f"{base_url_check}/range/yt-dlp.exe"},
            ],
        }
        with open(os.path.join(serve_dir_check, "latest"), "w") as f:
            json.dump(fake_release, f)
        try:
            info = get_latest_release_info(api_url=f"{base_url_check}/range/latest")
            check("B6: release info fetched", info is not None and info.get("tag_name") == "2099.01.01")
        finally:
            srv_check.stop()

        # ------------------------------------------------------------------
        # Test C: Hash verification — correct hash accepted
        # ------------------------------------------------------------------
        print()
        print("--- Test C: Hash verification (accept) ---")

        test_data = b"yt-dlp fake binary content for F8 testing"
        test_hash = hashlib.sha256(test_data).hexdigest()

        test_file = os.path.join(tmp, "test_artifact.bin")
        with open(test_file, "wb") as f:
            f.write(test_data)

        # C1: compute_sha256 correct
        computed = compute_sha256(test_file)
        check("C1: compute_sha256 correct", computed == test_hash,
              f"computed={computed[:16]}... expected={test_hash[:16]}...")

        # C2: verify_sha256 accepts correct hash
        all_security_events.extend(capture.events)
        capture.events.clear()
        accepted = verify_sha256(test_file, test_hash)
        check("C2: verify_sha256 accepts correct hash", accepted)

        has_verified = any("SECURITY.YTDLP.HASH_VERIFIED" in e for e in capture.events)
        check("C3: HASH_VERIFIED event logged", has_verified)

        # ------------------------------------------------------------------
        # Test D: Hash verification — wrong hash rejected
        # ------------------------------------------------------------------
        print()
        print("--- Test D: Hash verification (reject) ---")

        all_security_events.extend(capture.events)
        capture.events.clear()
        wrong_hash = "0" * 64
        rejected = verify_sha256(test_file, wrong_hash)
        check("D1: verify_sha256 rejects wrong hash", not rejected)

        has_fail = any("SECURITY.YTDLP.INSTALL_FAIL" in e
                       and "hash_mismatch" in e for e in capture.events)
        check("D2: INSTALL_FAIL/hash_mismatch event logged", has_fail)

        # ------------------------------------------------------------------
        # Test E: Binary update with correct hash (via LocalRangeServer)
        # ------------------------------------------------------------------
        print()
        print("--- Test E: Binary update (correct hash) ---")

        server = LocalRangeServer()
        base_url, serve_dir = server.start()

        fake_binary_data = b"MZfake-ytdlp-binary-" + os.urandom(100)
        fake_hash = hashlib.sha256(fake_binary_data).hexdigest()
        binary_name = _get_binary_asset_name()

        with open(os.path.join(serve_dir, binary_name), "wb") as f:
            f.write(fake_binary_data)

        install_dir = os.path.join(tmp, "install_e")
        os.makedirs(install_dir)

        all_security_events.extend(capture.events)
        capture.events.clear()

        try:
            ok, msg = update_via_binary(
                release_info={},  # not used when url+hash provided
                install_dir=install_dir,
                artifact_url=f"{base_url}/range/{binary_name}",
                expected_hash=fake_hash,
            )
            check("E1: binary update succeeded", ok, msg)

            installed = os.path.join(install_dir, binary_name)
            check("E2: binary file exists", os.path.exists(installed))

            if os.path.exists(installed):
                installed_hash = compute_sha256(installed)
                check("E3: installed hash matches", installed_hash == fake_hash)

            has_ok = any("SECURITY.YTDLP.INSTALL_OK" in e for e in capture.events)
            check("E4: INSTALL_OK event logged", has_ok)

            has_download = any("SECURITY.YTDLP.DOWNLOAD_START" in e for e in capture.events)
            check("E5: DOWNLOAD_START event logged", has_download)

        finally:
            server.stop()

        # ------------------------------------------------------------------
        # Test F: Binary update with wrong hash (must fail)
        # ------------------------------------------------------------------
        print()
        print("--- Test F: Binary update (wrong hash) ---")

        server2 = LocalRangeServer()
        base_url2, serve_dir2 = server2.start()

        tampered_data = b"TAMPERED-binary-not-real"
        with open(os.path.join(serve_dir2, binary_name), "wb") as f:
            f.write(tampered_data)

        install_dir_f = os.path.join(tmp, "install_f")
        os.makedirs(install_dir_f)

        all_security_events.extend(capture.events)
        capture.events.clear()

        try:
            ok_f, msg_f = update_via_binary(
                release_info={},
                install_dir=install_dir_f,
                artifact_url=f"{base_url2}/range/{binary_name}",
                expected_hash="0" * 64,  # wrong hash
            )
            check("F1: binary update with wrong hash fails", not ok_f, msg_f)
            check("F2: 'mismatch' in error message",
                  "mismatch" in msg_f.lower() if msg_f else False)

            # F3: no partial install — binary should NOT exist
            no_install = not os.path.exists(
                os.path.join(install_dir_f, binary_name))
            check("F3: no partial install (binary absent)", no_install)

            has_deny = any("SECURITY.YTDLP.INSTALL_FAIL" in e
                           and "hash_mismatch" in e for e in capture.events)
            check("F4: INSTALL_FAIL/hash_mismatch logged", has_deny)

        finally:
            server2.stop()

        # ------------------------------------------------------------------
        # Test G: No rider files in install directory
        # ------------------------------------------------------------------
        print()
        print("--- Test G: Rider file check ---")

        # Re-check install_dir from Test E — should only have the binary
        files_in_e = os.listdir(install_dir)
        expected_files = {binary_name}
        unexpected = set(files_in_e) - expected_files
        # .bak is acceptable, .download.tmp should be cleaned
        unexpected -= {binary_name + ".bak"}
        check("G1: no rider files in install dir", len(unexpected) == 0,
              f"files={files_in_e}" if unexpected else "clean")

        # install_dir_f should be empty (failed install cleaned up)
        files_in_f = os.listdir(install_dir_f)
        check("G2: failed install left no artifacts", len(files_in_f) == 0,
              f"files={files_in_f}" if files_in_f else "clean")

        # ------------------------------------------------------------------
        # Test H: Security log event structure
        # ------------------------------------------------------------------
        print()
        print("--- Test H: Security log structure ---")

        # Final flush + aggregate all captured events
        all_security_events.extend(capture.events)
        all_events = all_security_events
        has_check = any("SECURITY.YTDLP.CHECK" in e for e in all_events)
        check("H1: YTDLP.CHECK event present", has_check)

        has_hash_v = any("SECURITY.YTDLP.HASH_VERIFIED" in e for e in all_events)
        check("H2: YTDLP.HASH_VERIFIED event present", has_hash_v)

        has_install_ok = any("SECURITY.YTDLP.INSTALL_OK" in e for e in all_events)
        check("H3: YTDLP.INSTALL_OK event present", has_install_ok)

        has_install_fail = any("SECURITY.YTDLP.INSTALL_FAIL" in e for e in all_events)
        check("H4: YTDLP.INSTALL_FAIL event present", has_install_fail)

        has_dl_start = any("SECURITY.YTDLP.DOWNLOAD_START" in e for e in all_events)
        check("H5: YTDLP.DOWNLOAD_START event present", has_dl_start)

        # All events have timestamp
        all_have_ts = all("ts=" in e for e in all_events if "SECURITY.YTDLP." in e)
        check("H6: all YTDLP events have timestamp", all_have_ts)

        # ------------------------------------------------------------------
        # Test I: CLI subcommands registered
        # ------------------------------------------------------------------
        print()
        print("--- Test I: CLI integration ---")

        import importlib
        cli_mod = importlib.import_module("ngks_dl_cli")
        check("I1: cmd_ytdlp_check exists",
              hasattr(cli_mod, "cmd_ytdlp_check") and callable(cli_mod.cmd_ytdlp_check))
        check("I2: cmd_ytdlp_update exists",
              hasattr(cli_mod, "cmd_ytdlp_update") and callable(cli_mod.cmd_ytdlp_update))

        # ------------------------------------------------------------------
        # Test J: Environment detection
        # ------------------------------------------------------------------
        print()
        print("--- Test J: Environment detection ---")

        env = detect_environment()
        check("J1: detect_environment returns valid",
              env in ("pip", "binary"), f"env={env}")

        # We're in a venv during testing
        in_venv = sys.prefix != sys.base_prefix
        if in_venv:
            check("J2: venv detected as pip", env == "pip")
        else:
            check("J2: non-venv detected", env in ("pip", "binary"))

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
