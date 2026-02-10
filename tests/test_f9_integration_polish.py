#!/usr/bin/env python3
"""
F9 Gate Test: yt-dlp + Security Integration Polish

Proves:
  A. resolve_install_dir returns a valid, writable path
  B. resolve_install_dir differs between venv and non-venv (logic branch)
  C. check_ytdlp_freshness returns correct status strings
  D. check_ytdlp_freshness offline returns error:offline
  E. check_ytdlp_freshness up-to-date path works
  F. check_ytdlp_freshness update-available prompts correctly
  G. CLI error messages go to stderr with structured exit codes
  H. Binary update into resolve_install_dir produces no rider files
  I. Security events emitted for full update cycle
  J. UI hook is importable and callable (no GUI deadlock)

Deterministic, headless, offline (<10s).
Uses LocalRangeServer to simulate trusted source.
"""

import hashlib
import io
import json
import logging
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from local_range_server import LocalRangeServer
from ytdlp_manager import (
    resolve_install_dir,
    get_current_ytdlp_version,
    get_latest_ytdlp_version,
    check_ytdlp_freshness,
    check_and_prompt_cli,
    update_via_binary,
    detect_environment,
    compute_sha256,
    _get_binary_asset_name,
    _versions_match,
)


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


# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------

def main():
    results = []
    overall = True
    all_security_events: list[str] = []

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

    print("=== F9 Gate Test: yt-dlp + Security Integration Polish ===")
    print()

    sec_logger = logging.getLogger("security")
    sec_logger.setLevel(logging.DEBUG)
    capture = SecurityLogCapture()
    capture.setFormatter(logging.Formatter("%(message)s"))
    sec_logger.addHandler(capture)

    tmp = tempfile.mkdtemp(prefix="f9_gate_")

    try:
        # ------------------------------------------------------------------
        # Test A: resolve_install_dir
        # ------------------------------------------------------------------
        print("--- Test A: resolve_install_dir ---")

        install_dir = resolve_install_dir()
        check("A1: returns a string", isinstance(install_dir, str) and len(install_dir) > 0,
              f"dir={install_dir}")
        check("A2: directory exists", os.path.isdir(install_dir))

        # Try writing a file to prove it's writable
        probe = os.path.join(install_dir, ".f9_probe")
        try:
            with open(probe, "w") as f:
                f.write("probe")
            os.unlink(probe)
            writable = True
        except OSError:
            writable = False
        check("A3: directory is writable", writable)

        # ------------------------------------------------------------------
        # Test B: resolve_install_dir logic branches
        # ------------------------------------------------------------------
        print()
        print("--- Test B: Install dir branch logic ---")

        in_venv = sys.prefix != sys.base_prefix
        if in_venv:
            # Dev mode: should be in <repo>/bin/
            repo_bin = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bin")
            check("B1: venv -> repo/bin/",
                  os.path.realpath(install_dir) == os.path.realpath(repo_bin),
                  f"install={install_dir} expected={repo_bin}")
        else:
            check("B1: non-venv -> app data dir",
                  "NGKsDL" in install_dir or "ngksdl" in install_dir,
                  f"dir={install_dir}")

        check("B2: detect_environment coherent",
              detect_environment() in ("pip", "binary"))

        # ------------------------------------------------------------------
        # Test C: check_ytdlp_freshness — no prompt (info only)
        # ------------------------------------------------------------------
        print()
        print("--- Test C: check_ytdlp_freshness (no prompt) ---")

        # Simulate a server with a different version (update available)
        srv = LocalRangeServer()
        base_url, serve_dir = srv.start()
        fake_release = {
            "tag_name": "2099.12.31",
            "assets": [],
        }
        with open(os.path.join(serve_dir, "latest"), "w") as f:
            json.dump(fake_release, f)

        try:
            result = check_ytdlp_freshness(prompt_fn=None, api_url=f"{base_url}/range/latest")
            check("C1: returns update_available string",
                  result is not None and result.startswith("update_available:"),
                  f"result={result}")
        finally:
            srv.stop()

        # ------------------------------------------------------------------
        # Test D: check_ytdlp_freshness — offline
        # ------------------------------------------------------------------
        print()
        print("--- Test D: Offline handling ---")

        result_offline = check_ytdlp_freshness(
            prompt_fn=None,
            api_url="http://127.0.0.1:1/nonexistent")
        check("D1: offline returns error:offline",
              result_offline == "error:offline",
              f"result={result_offline}")

        # ------------------------------------------------------------------
        # Test E: check_ytdlp_freshness — up to date
        # ------------------------------------------------------------------
        print()
        print("--- Test E: Up-to-date detection ---")

        current_version = get_current_ytdlp_version()
        srv2 = LocalRangeServer()
        base_url2, serve_dir2 = srv2.start()
        same_release = {"tag_name": current_version, "assets": []}
        with open(os.path.join(serve_dir2, "latest"), "w") as f:
            json.dump(same_release, f)

        try:
            result_utd = check_ytdlp_freshness(
                prompt_fn=None, api_url=f"{base_url2}/range/latest")
            check("E1: up_to_date detected",
                  result_utd == "up_to_date",
                  f"result={result_utd}")
        finally:
            srv2.stop()

        # ------------------------------------------------------------------
        # Test F: check_ytdlp_freshness — prompt function
        # ------------------------------------------------------------------
        print()
        print("--- Test F: Prompt function ---")

        srv3 = LocalRangeServer()
        base_url3, serve_dir3 = srv3.start()
        new_release = {"tag_name": "2099.12.31", "assets": []}
        with open(os.path.join(serve_dir3, "latest"), "w") as f:
            json.dump(new_release, f)

        try:
            # Prompt returns False (declined)
            result_declined = check_ytdlp_freshness(
                prompt_fn=lambda c, l: False,
                api_url=f"{base_url3}/range/latest")
            check("F1: declined by prompt",
                  result_declined == "declined",
                  f"result={result_declined}")
        finally:
            srv3.stop()

        # ------------------------------------------------------------------
        # Test G: CLI error messages (stderr + exit codes)
        # ------------------------------------------------------------------
        print()
        print("--- Test G: CLI error clarity ---")

        # Capture stderr for offline scenario
        old_stderr = sys.stderr
        old_stdin = sys.stdin
        captured_err = io.StringIO()
        sys.stderr = captured_err
        sys.stdin = io.StringIO("")  # EOF on input

        try:
            exit_code = check_and_prompt_cli(
                api_url="http://127.0.0.1:1/nonexistent",
                auto_yes=False)
        finally:
            sys.stderr = old_stderr
            sys.stdin = old_stdin

        err_text = captured_err.getvalue()
        check("G1: offline -> exit code 1", exit_code == 1)
        check("G2: offline -> stderr mentions offline/unreachable",
              "offline" in err_text.lower() or "unreachable" in err_text.lower(),
              f"stderr={err_text.strip()[:80]}")

        # ------------------------------------------------------------------
        # Test H: Binary update into resolve_install_dir — no riders
        # ------------------------------------------------------------------
        print()
        print("--- Test H: Binary update + rider check ---")

        srv4 = LocalRangeServer()
        base_url4, serve_dir4 = srv4.start()

        fake_binary = b"MZf9-test-binary-" + os.urandom(100)
        fake_hash = hashlib.sha256(fake_binary).hexdigest()
        binary_name = _get_binary_asset_name()

        with open(os.path.join(serve_dir4, binary_name), "wb") as f:
            f.write(fake_binary)

        h_install_dir = os.path.join(tmp, "install_h")
        os.makedirs(h_install_dir)

        all_security_events.extend(capture.events)
        capture.events.clear()

        try:
            ok, msg = update_via_binary(
                release_info={},
                install_dir=h_install_dir,
                artifact_url=f"{base_url4}/range/{binary_name}",
                expected_hash=fake_hash,
            )
            check("H1: binary update succeeded", ok, msg)

            # Rider file check
            files = os.listdir(h_install_dir)
            unexpected = [f for f in files
                          if f != binary_name and f != binary_name + ".bak"]
            check("H2: no rider files", len(unexpected) == 0,
                  f"files={files}" if unexpected else "clean")

            # Verify installed content
            installed = os.path.join(h_install_dir, binary_name)
            check("H3: installed content matches hash",
                  compute_sha256(installed) == fake_hash)

        finally:
            srv4.stop()

        # ------------------------------------------------------------------
        # Test I: Security events for full cycle
        # ------------------------------------------------------------------
        print()
        print("--- Test I: Security event coverage ---")

        all_security_events.extend(capture.events)
        capture.events.clear()

        has_check = any("SECURITY.YTDLP.CHECK" in e for e in all_security_events)
        check("I1: YTDLP.CHECK emitted", has_check)

        has_update_avail = any("SECURITY.YTDLP.UPDATE_AVAILABLE" in e
                               for e in all_security_events)
        check("I2: YTDLP.UPDATE_AVAILABLE emitted", has_update_avail)

        has_dl_start = any("SECURITY.YTDLP.DOWNLOAD_START" in e
                           for e in all_security_events)
        check("I3: YTDLP.DOWNLOAD_START emitted", has_dl_start)

        has_hash_ok = any("SECURITY.YTDLP.HASH_VERIFIED" in e
                          for e in all_security_events)
        check("I4: YTDLP.HASH_VERIFIED emitted", has_hash_ok)

        has_install_ok = any("SECURITY.YTDLP.INSTALL_OK" in e
                             for e in all_security_events)
        check("I5: YTDLP.INSTALL_OK emitted", has_install_ok)

        all_have_ts = all("ts=" in e for e in all_security_events
                          if "SECURITY.YTDLP." in e)
        check("I6: all YTDLP events have timestamp", all_have_ts)

        # ------------------------------------------------------------------
        # Test J: UI hook importable (no GUI deadlock test)
        # ------------------------------------------------------------------
        print()
        print("--- Test J: UI hook ---")

        # check_ytdlp_freshness is the public API used by UI
        import inspect
        sig = inspect.signature(check_ytdlp_freshness)
        check("J1: check_ytdlp_freshness has prompt_fn param",
              "prompt_fn" in sig.parameters)
        check("J2: check_ytdlp_freshness has api_url param",
              "api_url" in sig.parameters)

        # Verify resolve_install_dir is importable
        from ytdlp_manager import resolve_install_dir as ri
        check("J3: resolve_install_dir importable", callable(ri))

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
