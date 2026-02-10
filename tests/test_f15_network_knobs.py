#!/usr/bin/env python3
"""
F15 Gate Test: Network Hardening Knobs

Proves:
  A. tls_only=true denies http:// URLs with DENY_SCHEME_NOT_TLS
  B. tls_only=true allows https:// URLs
  C. tls_only=false allows http:// URLs
  D. retries / backoff_ms / honor_proxy_env propagated as annotations
  E. Default network section present in permissive defaults
  F. check_network_policy returns MODIFY with annotations when knobs set
  G. Missing network section falls back to permissive defaults

Deterministic, headless, offline (<5s).
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


def make_policy_engine(tmp, network=None, denylist=None):
    """Create a PolicyEngine with isolated config."""
    config_path = os.path.join(tmp, "policy.json")
    policies = {
        "global": {"safe_mode": False, "offline_mode": False,
                    "metered_network_restrictions": False},
        "per_task": {"max_speed_bps": None, "max_retries": None,
                     "timeout_seconds": 300},
        "per_host": {
            "allowlist": [],
            "denylist": denylist or [],
            "max_connections_per_host": 2,
            "rate_limit_requests_per_minute": None,
        },
        "file_type": {
            "allowed_extensions": [],
            "blocked_extensions": [],
            "max_file_size_mb": None,
        },
    }
    if network is not None:
        policies["network"] = network

    config = {
        "version": "1.0", "schema_version": 1, "last_updated": "test",
        "policies": policies,
    }
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f)
    return PolicyEngine(policy_config_path=config_path)


# ---------------------------------------------------------------------------
# Test A: tls_only blocks http
# ---------------------------------------------------------------------------

def test_a_tls_only_blocks_http():
    print("\n[A] tls_only=true denies http://")
    tmp = tempfile.mkdtemp(prefix="f15_a_")
    try:
        pe = make_policy_engine(tmp, network={"tls_only": True, "retries": 3,
                                               "backoff_ms": 1000,
                                               "honor_proxy_env": True})
        d = pe.check_network_policy("http://example.com/file.bin", "t_a")
        check("A1: action is DENY", d.action == "DENY", f"got {d.action}")
        check("A2: code is DENY_SCHEME_NOT_TLS", d.code == "DENY_SCHEME_NOT_TLS",
              f"got {d.code!r}")
        check("A3: reason mentions http", "http" in d.reason.lower())
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------
# Test B: tls_only allows https
# ---------------------------------------------------------------------------

def test_b_tls_only_allows_https():
    print("\n[B] tls_only=true allows https://")
    tmp = tempfile.mkdtemp(prefix="f15_b_")
    try:
        pe = make_policy_engine(tmp, network={"tls_only": True, "retries": 3,
                                               "backoff_ms": 1000,
                                               "honor_proxy_env": True})
        d = pe.check_network_policy("https://example.com/file.bin", "t_b")
        check("B1: action is not DENY", d.action != "DENY", f"got {d.action}")
        check("B2: code is not DENY_SCHEME_NOT_TLS",
              d.code != "DENY_SCHEME_NOT_TLS", f"got {d.code!r}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------
# Test C: tls_only=false allows http
# ---------------------------------------------------------------------------

def test_c_tls_off_allows_http():
    print("\n[C] tls_only=false allows http://")
    tmp = tempfile.mkdtemp(prefix="f15_c_")
    try:
        pe = make_policy_engine(tmp, network={"tls_only": False, "retries": 3,
                                               "backoff_ms": 1000,
                                               "honor_proxy_env": True})
        d = pe.check_network_policy("http://example.com/file.bin", "t_c")
        check("C1: action is not DENY", d.action != "DENY", f"got {d.action}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------
# Test D: Annotations carry retry/backoff/proxy settings
# ---------------------------------------------------------------------------

def test_d_annotations():
    print("\n[D] Network annotations carry knobs")
    tmp = tempfile.mkdtemp(prefix="f15_d_")
    try:
        pe = make_policy_engine(tmp, network={"tls_only": False, "retries": 5,
                                               "backoff_ms": 2000,
                                               "honor_proxy_env": False})
        d = pe.check_network_policy("http://example.com/file.bin", "t_d")
        check("D1: action is MODIFY", d.action == "MODIFY", f"got {d.action}")
        check("D2: retries=5 in annotations",
              d.annotations.get("retries") == 5,
              f"got {d.annotations}")
        check("D3: backoff_ms=2000", d.annotations.get("backoff_ms") == 2000,
              f"got {d.annotations}")
        check("D4: honor_proxy_env=False",
              d.annotations.get("honor_proxy_env") is False,
              f"got {d.annotations}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------
# Test E: Permissive defaults include network section
# ---------------------------------------------------------------------------

def test_e_permissive_defaults():
    print("\n[E] Permissive defaults include network")
    tmp = tempfile.mkdtemp(prefix="f15_e_")
    try:
        pe = PolicyEngine(policy_config_path=os.path.join(tmp, "nonexist", "x.json"))
        # Force fallback
        pe.policies = pe._get_permissive_defaults()
        net = pe.policies.get("network")
        check("E1: network section present", net is not None)
        check("E2: tls_only default is False", net.get("tls_only") is False)
        check("E3: retries default is 3", net.get("retries") == 3)
        check("E4: backoff_ms default is 1000", net.get("backoff_ms") == 1000)
        check("E5: honor_proxy_env default is True", net.get("honor_proxy_env") is True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------
# Test F: check_network_policy MODIFY with all knobs
# ---------------------------------------------------------------------------

def test_f_modify_with_knobs():
    print("\n[F] MODIFY returned with all knobs")
    tmp = tempfile.mkdtemp(prefix="f15_f_")
    try:
        pe = make_policy_engine(tmp, network={"tls_only": False, "retries": 10,
                                               "backoff_ms": 500,
                                               "honor_proxy_env": True})
        d = pe.check_network_policy("https://example.com/file.bin", "t_f")
        check("F1: action is MODIFY", d.action == "MODIFY")
        check("F2: retries in annotations", "retries" in d.annotations)
        check("F3: backoff_ms in annotations", "backoff_ms" in d.annotations)
        check("F4: honor_proxy_env in annotations", "honor_proxy_env" in d.annotations)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------
# Test G: Missing network section -> quiet pass (no crash)
# ---------------------------------------------------------------------------

def test_g_missing_network_section():
    print("\n[G] Missing network section -> no crash")
    tmp = tempfile.mkdtemp(prefix="f15_g_")
    try:
        pe = make_policy_engine(tmp)  # no network key
        d = pe.check_network_policy("http://example.com/file.bin", "t_g")
        check("G1: no crash", True)
        check("G2: action is not DENY (tls_only defaults false)",
              d.action != "DENY", f"got {d.action}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------
# Test H: ftp scheme blocked by tls_only
# ---------------------------------------------------------------------------

def test_h_ftp_blocked_by_tls():
    print("\n[H] tls_only blocks ftp://")
    tmp = tempfile.mkdtemp(prefix="f15_h_")
    try:
        pe = make_policy_engine(tmp, network={"tls_only": True, "retries": 3,
                                               "backoff_ms": 1000,
                                               "honor_proxy_env": True})
        d = pe.check_network_policy("ftp://example.com/file.bin", "t_h")
        check("H1: action is DENY", d.action == "DENY")
        check("H2: code is DENY_SCHEME_NOT_TLS", d.code == "DENY_SCHEME_NOT_TLS")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ===========================================================================

def main():
    print("=" * 60)
    print("F15 GATE: Network Hardening Knobs")
    print("=" * 60)

    test_a_tls_only_blocks_http()
    test_b_tls_only_allows_https()
    test_c_tls_off_allows_http()
    test_d_annotations()
    test_e_permissive_defaults()
    test_f_modify_with_knobs()
    test_g_missing_network_section()
    test_h_ftp_blocked_by_tls()

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
