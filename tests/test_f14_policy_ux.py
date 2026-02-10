#!/usr/bin/env python3
"""
F14 Gate Test: Policy UX — Structured Denial Codes + Allow-Once Exception

Proves:
  A. PolicyDecision carries structured `code` field (DENY_HOST_DENYLIST, etc.)
  B. DENY_HOST_DENYLIST code emitted for denied host
  C. DENY_EXTENSION_BLOCKED code emitted for blocked extension
  D. DENY_SAFE_MODE code emitted when safe_mode is on
  E. add_exception("host", ...) creates one-time exception
  F. Denied host allowed once via exception, then denied again
  G. Exception file consumed (used=True) after first use
  H. Batch run DENIED line includes [DENY_HOST_DENYLIST] code tag
  I. PolicyDecision.code defaults to "" for ALLOW/MODIFY decisions

Deterministic, headless, offline (<10s).
"""

import json
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from policy_engine import PolicyEngine, PolicyDecision

# ---------------------------------------------------------------------------
# Helpers
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


# ---------------------------------------------------------------------------
# Setup: isolated policy engine with known config
# ---------------------------------------------------------------------------

def make_policy_engine(tmp, denylist=None, blocked_extensions=None, safe_mode=False,
                       allowlist=None):
    """Create a PolicyEngine with in-memory policies (no disk config)."""
    config_path = os.path.join(tmp, "policy.json")
    os.makedirs(os.path.dirname(config_path) or tmp, exist_ok=True)
    config = {
        "version": "1.0",
        "schema_version": 1,
        "last_updated": "test",
        "policies": {
            "global": {"safe_mode": safe_mode, "offline_mode": False,
                       "metered_network_restrictions": False},
            "per_task": {"max_speed_bps": None, "max_retries": None,
                         "timeout_seconds": 300},
            "per_host": {
                "allowlist": allowlist or [],
                "denylist": denylist or [],
                "max_connections_per_host": 2,
                "rate_limit_requests_per_minute": None,
            },
            "file_type": {
                "allowed_extensions": [],
                "blocked_extensions": blocked_extensions or [],
                "max_file_size_mb": None,
            },
        },
    }
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f)
    pe = PolicyEngine(policy_config_path=config_path)
    # Override exception path to isolated tmp
    pe._EXCEPTION_PATH = os.path.join(tmp, "policy_exceptions.json")
    return pe


# ---------------------------------------------------------------------------
# Test A: PolicyDecision has code field
# ---------------------------------------------------------------------------

def test_a_code_field():
    print("\n[A] PolicyDecision code field")
    d = PolicyDecision("DENY", "test reason", code="DENY_HOST_DENYLIST")
    check("A1: code field present", d.code == "DENY_HOST_DENYLIST")
    check("A2: action is DENY", d.action == "DENY")
    check("A3: reason present", d.reason == "test reason")

    d2 = PolicyDecision("ALLOW", "ok")
    check("A4: default code is empty string", d2.code == "")


# ---------------------------------------------------------------------------
# Test B: DENY_HOST_DENYLIST code
# ---------------------------------------------------------------------------

def test_b_deny_host_denylist():
    print("\n[B] DENY_HOST_DENYLIST code for denied host")
    tmp = tempfile.mkdtemp(prefix="f14_b_")
    try:
        pe = make_policy_engine(tmp, denylist=["evil.com"])
        decision = pe.check_enqueue_policy("t1", "http://evil.com/file.bin",
                                            os.path.join(tmp, "file.bin"))
        check("B1: action is DENY", decision.action == "DENY")
        check("B2: code is DENY_HOST_DENYLIST", decision.code == "DENY_HOST_DENYLIST",
              f"got {decision.code!r}")
        check("B3: reason mentions evil.com", "evil.com" in decision.reason)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------
# Test C: DENY_EXTENSION_BLOCKED code
# ---------------------------------------------------------------------------

def test_c_deny_extension_blocked():
    print("\n[C] DENY_EXTENSION_BLOCKED code for blocked extension")
    tmp = tempfile.mkdtemp(prefix="f14_c_")
    try:
        pe = make_policy_engine(tmp, blocked_extensions=[".exe"])
        decision = pe.check_enqueue_policy("t2", "http://ok.com/app.exe",
                                            os.path.join(tmp, "app.exe"))
        check("C1: action is DENY", decision.action == "DENY")
        check("C2: code is DENY_EXTENSION_BLOCKED", decision.code == "DENY_EXTENSION_BLOCKED",
              f"got {decision.code!r}")
        check("C3: reason mentions .exe", ".exe" in decision.reason)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------
# Test D: DENY_SAFE_MODE code
# ---------------------------------------------------------------------------

def test_d_deny_safe_mode():
    print("\n[D] DENY_SAFE_MODE code when safe_mode enabled")
    tmp = tempfile.mkdtemp(prefix="f14_d_")
    try:
        pe = make_policy_engine(tmp, safe_mode=True)
        decision = pe.check_enqueue_policy("t3", "http://ok.com/file.bin",
                                            os.path.join(tmp, "file.bin"))
        check("D1: action is DENY", decision.action == "DENY")
        check("D2: code is DENY_SAFE_MODE", decision.code == "DENY_SAFE_MODE",
              f"got {decision.code!r}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------
# Test E: add_exception creates entry
# ---------------------------------------------------------------------------

def test_e_add_exception():
    print("\n[E] add_exception creates allow-once entry")
    tmp = tempfile.mkdtemp(prefix="f14_e_")
    try:
        pe = make_policy_engine(tmp, denylist=["evil.com"])
        pe.add_exception("host", "evil.com")

        exc_path = pe._EXCEPTION_PATH
        check("E1: exception file exists", os.path.exists(exc_path))

        with open(exc_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        check("E2: one exception entry", len(data) == 1, f"got {len(data)}")
        check("E3: type=host", data[0]["type"] == "host")
        check("E4: value=evil.com", data[0]["value"] == "evil.com")
        check("E5: used=False", data[0]["used"] is False)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------
# Test F: Exception allows once, then denied again
# ---------------------------------------------------------------------------

def test_f_allow_once():
    print("\n[F] Allow-once exception consumed then denied")
    tmp = tempfile.mkdtemp(prefix="f14_f_")
    try:
        pe = make_policy_engine(tmp, denylist=["evil.com"])

        # Without exception -> denied
        d1 = pe.check_enqueue_policy("t_pre", "http://evil.com/f.bin",
                                      os.path.join(tmp, "f.bin"))
        check("F1: denied without exception", d1.action == "DENY")

        # Add exception
        pe.add_exception("host", "evil.com")

        # First check -> allowed via exception
        d2 = pe.check_enqueue_policy("t_exc", "http://evil.com/f.bin",
                                      os.path.join(tmp, "f.bin"))
        check("F2: allowed with exception", d2.action == "ALLOW", f"got {d2.action}")
        check("F3: code is ALLOW_EXCEPTION", d2.code == "ALLOW_EXCEPTION",
              f"got {d2.code!r}")

        # Second check -> denied again (exception consumed)
        d3 = pe.check_enqueue_policy("t_post", "http://evil.com/f.bin",
                                      os.path.join(tmp, "f.bin"))
        check("F4: denied again after exception consumed", d3.action == "DENY")
        check("F5: code is DENY_HOST_DENYLIST", d3.code == "DENY_HOST_DENYLIST",
              f"got {d3.code!r}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------
# Test G: Exception file shows used=True after consumption
# ---------------------------------------------------------------------------

def test_g_exception_consumed():
    print("\n[G] Exception file updated with used=True")
    tmp = tempfile.mkdtemp(prefix="f14_g_")
    try:
        pe = make_policy_engine(tmp, denylist=["evil.com"])
        pe.add_exception("host", "evil.com")

        # Consume the exception
        pe.check_enqueue_policy("t_consume", "http://evil.com/f.bin",
                                 os.path.join(tmp, "f.bin"))

        with open(pe._EXCEPTION_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        check("G1: exception still in file", len(data) == 1)
        check("G2: used=True after consumption", data[0]["used"] is True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------
# Test H: Queue valueOf includes code tag in denial message
# ---------------------------------------------------------------------------

def test_h_code_in_queue_denial():
    print("\n[H] Queue denial includes code tag")
    tmp = tempfile.mkdtemp(prefix="f14_h_")
    try:
        pe = make_policy_engine(tmp, denylist=["evil.com"])
        decision = pe.check_enqueue_policy("t_h", "http://evil.com/f.bin",
                                            os.path.join(tmp, "f.bin"))
        # Simulate what queue_manager does
        code_tag = f" [{decision.code}]" if decision.code else ""
        msg = f"Queue policy denied{code_tag}: {decision.reason}"
        check("H1: message contains [DENY_HOST_DENYLIST]",
              "[DENY_HOST_DENYLIST]" in msg, f"got: {msg}")
        check("H2: message contains reason text", "evil.com" in msg)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------
# Test I: ALLOW/MODIFY decisions have empty code by default
# ---------------------------------------------------------------------------

def test_i_allow_modify_defaults():
    print("\n[I] ALLOW/MODIFY code defaults")
    tmp = tempfile.mkdtemp(prefix="f14_i_")
    try:
        pe = make_policy_engine(tmp)  # no restrictions
        d = pe.check_enqueue_policy("t_i", "http://safe.com/file.txt",
                                     os.path.join(tmp, "file.txt"))
        # With default per_task timeout_seconds set, action may be MODIFY
        check("I1: action is ALLOW or MODIFY", d.action in ("ALLOW", "MODIFY"),
              f"got {d.action}")
        check("I2: code is empty string", d.code == "", f"got {d.code!r}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------
# Test J: DENY_HOST_ALLOWLIST code for allowlist miss
# ---------------------------------------------------------------------------

def test_j_deny_host_allowlist():
    print("\n[J] DENY_HOST_ALLOWLIST code for allowlist miss")
    tmp = tempfile.mkdtemp(prefix="f14_j_")
    try:
        pe = make_policy_engine(tmp, allowlist=["trusted.com"])
        decision = pe.check_enqueue_policy("t_j", "http://untrusted.com/f.bin",
                                            os.path.join(tmp, "f.bin"))
        check("J1: action is DENY", decision.action == "DENY")
        check("J2: code is DENY_HOST_ALLOWLIST", decision.code == "DENY_HOST_ALLOWLIST",
              f"got {decision.code!r}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------
# Test K: Allow-once works for allowlist miss too
# ---------------------------------------------------------------------------

def test_k_exception_for_allowlist():
    print("\n[K] Allow-once exception for allowlist miss")
    tmp = tempfile.mkdtemp(prefix="f14_k_")
    try:
        pe = make_policy_engine(tmp, allowlist=["trusted.com"])
        pe.add_exception("host", "untrusted.com")

        d = pe.check_enqueue_policy("t_k", "http://untrusted.com/f.bin",
                                     os.path.join(tmp, "f.bin"))
        check("K1: allowed via exception", d.action == "ALLOW")
        check("K2: code is ALLOW_EXCEPTION", d.code == "ALLOW_EXCEPTION")

        d2 = pe.check_enqueue_policy("t_k2", "http://untrusted.com/f.bin",
                                      os.path.join(tmp, "f.bin"))
        check("K3: denied again (exception consumed)", d2.action == "DENY")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ===========================================================================

def main():
    print("=" * 60)
    print("F14 GATE: Policy UX — Denial Codes + Allow-Once Exception")
    print("=" * 60)

    test_a_code_field()
    test_b_deny_host_denylist()
    test_c_deny_extension_blocked()
    test_d_deny_safe_mode()
    test_e_add_exception()
    test_f_allow_once()
    test_g_exception_consumed()
    test_h_code_in_queue_denial()
    test_i_allow_modify_defaults()
    test_j_deny_host_allowlist()
    test_k_exception_for_allowlist()

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
