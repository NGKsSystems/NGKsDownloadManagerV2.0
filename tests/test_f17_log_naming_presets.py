#!/usr/bin/env python3
"""
F17 Gate Test: Log Naming Presets (canonical + aliases)

Proves:
  A. VALID_PRESETS and DEFAULT_PRESET constants exist and are correct
  B. get_naming_preset / set_naming_preset round-trip through config.json
  C. build_display_name produces correct pattern for each preset
  D. Canonical log folder path is stable across preset changes
  E. session_meta.json contains display_name, naming_preset, canonical_path, aliases
  F. append_alias_index writes JSONL entries
  G. CLI logs preset --get / --set round-trip

Deterministic, headless, offline (<15s).
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.forensics import (
    VALID_PRESETS,
    DEFAULT_PRESET,
    get_naming_preset,
    set_naming_preset,
    build_display_name,
    append_alias_index,
    _ALIAS_INDEX_PATH,
    _load_config,
    _save_config,
)
from tools.batch_run import build_log_folder
from local_range_server import LocalRangeServer

# Whitelist loopback for test-local servers
_LOOPBACK = {'localhost', '127.0.0.1', '::1'}
try:
    from policy_engine import get_policy_engine as _get_pe
    _pe = _get_pe()
    _orig_denylist = list(_pe.policies.get('per_host', {}).get('denylist', []))
    _pe.policies.setdefault('per_host', {})['denylist'] = [
        h for h in _orig_denylist if h not in _LOOPBACK
    ]
    _ft = _pe.policies.get('file_type', {})
    _orig_blocked_exts = list(_ft.get('blocked_extensions', []))
    _ft['blocked_extensions'] = []
except Exception:
    _pe = None
    _orig_denylist = None
    _orig_blocked_exts = None


def _restore_policy():
    if _pe is not None and _orig_denylist is not None:
        _pe.policies.setdefault('per_host', {})['denylist'] = _orig_denylist
    if _pe is not None and _orig_blocked_exts is not None:
        _pe.policies.setdefault('file_type', {})['blocked_extensions'] = _orig_blocked_exts


# Preserve original config.json to restore on exit
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CONFIG_PATH = os.path.join(_PROJECT_ROOT, "config.json")
_CONFIG_BACKUP = None


def _backup_config():
    global _CONFIG_BACKUP
    try:
        with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
            _CONFIG_BACKUP = f.read()
    except Exception:
        _CONFIG_BACKUP = None


def _restore_config():
    if _CONFIG_BACKUP is not None:
        with open(_CONFIG_PATH, "w", encoding="utf-8") as f:
            f.write(_CONFIG_BACKUP)


# ---------------------------------------------------------------------------
# Counters
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
# Test A: Constants
# ---------------------------------------------------------------------------

def test_a_constants():
    print("\n[A] VALID_PRESETS and DEFAULT_PRESET constants")
    check("A1: VALID_PRESETS is a tuple", isinstance(VALID_PRESETS, tuple))
    check("A2: 4 presets", len(VALID_PRESETS) == 4,
          f"got {len(VALID_PRESETS)}")
    for p in ("shortid", "summary", "host", "firstfile"):
        check(f"A3: '{p}' in VALID_PRESETS", p in VALID_PRESETS)
    check("A4: DEFAULT_PRESET is 'summary'", DEFAULT_PRESET == "summary",
          f"got {DEFAULT_PRESET!r}")


# ---------------------------------------------------------------------------
# Test B: get/set naming preset round-trip
# ---------------------------------------------------------------------------

def test_b_preset_roundtrip():
    print("\n[B] get_naming_preset / set_naming_preset round-trip")
    original = get_naming_preset()
    check("B1: default preset is valid", original in VALID_PRESETS,
          f"got {original!r}")

    set_naming_preset("host")
    check("B2: set to 'host' reads back", get_naming_preset() == "host",
          f"got {get_naming_preset()!r}")

    set_naming_preset("shortid")
    check("B3: set to 'shortid' reads back", get_naming_preset() == "shortid",
          f"got {get_naming_preset()!r}")

    # config.json actually has the key
    cfg = _load_config()
    check("B4: config.json has logs.naming_preset",
          cfg.get("logs", {}).get("naming_preset") == "shortid",
          f"got {cfg.get('logs', {}).get('naming_preset')!r}")

    # Invalid preset raises
    raised = False
    try:
        set_naming_preset("bogus")
    except ValueError:
        raised = True
    check("B5: invalid preset raises ValueError", raised)

    # Restore original
    set_naming_preset(original if original in VALID_PRESETS else DEFAULT_PRESET)


# ---------------------------------------------------------------------------
# Test C: build_display_name per preset
# ---------------------------------------------------------------------------

def test_c_display_name():
    print("\n[C] build_display_name per preset")
    ts = "143022"
    mode = "batch"
    sid = "abc12345"
    tag = "3ok"
    host = "cdn.example.com"
    fname = "big_model.safetensors"

    dn_shortid = build_display_name("shortid", mode, sid, tag, host, fname, ts)
    check("C1: shortid format", dn_shortid == f"{ts} - {mode} - {sid}",
          f"got {dn_shortid!r}")

    dn_summary = build_display_name("summary", mode, sid, tag, host, fname, ts)
    check("C2: summary format", dn_summary == f"{ts} - {mode} - {tag} - {sid}",
          f"got {dn_summary!r}")

    dn_host = build_display_name("host", mode, sid, tag, host, fname, ts)
    check("C3: host format", dn_host == f"{ts} - {mode} - {host} - {sid}",
          f"got {dn_host!r}")

    dn_firstfile = build_display_name("firstfile", mode, sid, tag, host, fname, ts)
    check("C4: firstfile format", dn_firstfile == f"{ts} - {mode} - {fname} - {sid}",
          f"got {dn_firstfile!r}")

    # Fragments with special chars are sanitized
    dn_dirty = build_display_name("host", mode, sid, tag, "evil host/path?q=1", fname, ts)
    check("C5: host with special chars sanitized",
          "evil_host_path_q_1" in dn_dirty, f"got {dn_dirty!r}")


# ---------------------------------------------------------------------------
# Test D: Canonical log folder stable across preset changes
# ---------------------------------------------------------------------------

def test_d_canonical_stability():
    print("\n[D] Canonical log folder path stable across preset changes")
    summary = {"completed": 3, "failed": 0, "denied": 0}

    set_naming_preset("summary")
    folder1, ts1, tag1, sid1 = build_log_folder("/logs", "batch", summary,
                                                 short_id="test1234")

    set_naming_preset("shortid")
    folder2, ts2, tag2, sid2 = build_log_folder("/logs", "batch", summary,
                                                 short_id="test1234")

    set_naming_preset("host")
    folder3, ts3, tag3, sid3 = build_log_folder("/logs", "batch", summary,
                                                 short_id="test1234")

    # Canonical folder pattern should be the same regardless of preset
    # (build_log_folder is CANONICAL — it always uses summary-style pattern)
    check("D1: folder pattern is consistent with summary style",
          "3ok" in folder1 and "test1234" in folder1,
          f"got {folder1!r}")
    check("D2: folder pattern same for shortid preset",
          "3ok" in folder2 and "test1234" in folder2,
          f"got {folder2!r}")
    check("D3: folder pattern same for host preset",
          "3ok" in folder3 and "test1234" in folder3,
          f"got {folder3!r}")

    # Display name changes with preset
    dn1 = build_display_name("summary", "batch", sid1, tag1, "", "", ts1)
    dn2 = build_display_name("shortid", "batch", sid2, tag2, "", "", ts2)
    check("D4: display_name differs with preset",
          dn1 != dn2, f"summary={dn1!r}, shortid={dn2!r}")

    # Restore
    set_naming_preset(DEFAULT_PRESET)


# ---------------------------------------------------------------------------
# Test E: session_meta.json enriched fields (via batch run)
# ---------------------------------------------------------------------------

def test_e_session_meta_enriched():
    print("\n[E] session_meta.json enriched with F17 fields")
    logs_root = os.path.join(_PROJECT_ROOT, "logs")

    tmp = tempfile.mkdtemp(prefix="f17_e_")
    dl_dir = os.path.join(tmp, "dl")
    os.makedirs(dl_dir)

    srv = LocalRangeServer()
    base_url, serve_dir = srv.start()
    try:
        payload = b"f17-session-meta-test"
        with open(os.path.join(serve_dir, "f17test.bin"), "wb") as f:
            f.write(payload)

        # Set a known preset
        set_naming_preset("host")

        from tools.batch_run import run_batch
        batch = {
            "version": 1,
            "defaults": {"dest_dir": dl_dir, "priority": 5, "connections": 1},
            "items": [{"id": "e1", "url": f"{base_url}/range/f17test.bin"}],
        }
        report_path = os.path.join(tmp, "report.json")
        run_batch(batch, report_path=report_path, max_concurrent=1, until="empty")

        # Find most recent session_meta.json
        meta_data = None
        if os.path.isdir(logs_root):
            for d in sorted(os.listdir(logs_root), reverse=True):
                dd_path = os.path.join(logs_root, d)
                if not os.path.isdir(dd_path) or d.startswith("_"):
                    continue
                for sub in sorted(os.listdir(dd_path), reverse=True):
                    meta_path = os.path.join(dd_path, sub, "session_meta.json")
                    if os.path.exists(meta_path):
                        with open(meta_path, "r", encoding="utf-8") as f:
                            meta_data = json.load(f)
                        break
                if meta_data:
                    break

        check("E1: session_meta.json found", meta_data is not None)
        if meta_data:
            check("E2: has display_name", "display_name" in meta_data,
                  f"keys: {list(meta_data.keys())}")
            check("E3: has naming_preset", "naming_preset" in meta_data)
            check("E4: naming_preset is 'host'",
                  meta_data.get("naming_preset") == "host",
                  f"got {meta_data.get('naming_preset')!r}")
            check("E5: has canonical_path", "canonical_path" in meta_data)
            check("E6: has aliases list", isinstance(meta_data.get("aliases"), list),
                  f"got {type(meta_data.get('aliases'))}")
            check("E7: aliases contains display_name",
                  meta_data.get("display_name") in meta_data.get("aliases", []),
                  f"aliases={meta_data.get('aliases')!r}")
            check("E8: has started_at", "started_at" in meta_data)
            check("E9: canonical_path contains date pattern",
                  re.search(r"\d{4}-\d{2}-\d{2}", meta_data.get("canonical_path", ""))
                  is not None,
                  f"got {meta_data.get('canonical_path')!r}")
    finally:
        srv.stop()
        shutil.rmtree(tmp, ignore_errors=True)
        # Restore preset
        set_naming_preset(DEFAULT_PRESET)


# ---------------------------------------------------------------------------
# Test F: append_alias_index writes JSONL
# ---------------------------------------------------------------------------

def test_f_alias_index():
    print("\n[F] append_alias_index JSONL")
    # Use a temp path to avoid polluting the real index
    tmp = tempfile.mkdtemp(prefix="f17_f_")
    test_index = os.path.join(tmp, "aliases.jsonl")

    import tools.forensics as fmod
    orig_path = fmod._ALIAS_INDEX_PATH
    fmod._ALIAS_INDEX_PATH = test_index

    try:
        append_alias_index("run-001", "2025-01-01/120000 - batch - 3ok - abc",
                           "120000 - batch - abc", "shortid", "2025-01-01T12:00:00")
        append_alias_index("run-002", "2025-01-01/120100 - batch - 2ok - def",
                           "120100 - batch - 2ok - def", "summary", "2025-01-01T12:01:00")

        check("F1: aliases.jsonl created", os.path.exists(test_index))

        with open(test_index, "r", encoding="utf-8") as f:
            lines = [json.loads(line) for line in f if line.strip()]

        check("F2: 2 entries", len(lines) == 2, f"got {len(lines)}")
        check("F3: first run_id", lines[0]["run_id"] == "run-001")
        check("F4: first preset", lines[0]["preset"] == "shortid")
        check("F5: second display_name", "2ok" in lines[1]["display_name"])
        check("F6: canonical_rel present", "canonical_rel" in lines[0])
    finally:
        fmod._ALIAS_INDEX_PATH = orig_path
        shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------
# Test G: CLI logs preset round-trip
# ---------------------------------------------------------------------------

def test_g_cli_preset():
    print("\n[G] CLI logs preset --get / --set")
    cli_path = os.path.join(_PROJECT_ROOT, "ngks_dl_cli.py")

    # Save original preset
    original = get_naming_preset()

    try:
        # --set host
        r_set = subprocess.run(
            [sys.executable, cli_path, "logs", "preset", "--set", "host"],
            capture_output=True, text=True, timeout=10,
        )
        check("G1: --set host exits 0", r_set.returncode == 0,
              f"rc={r_set.returncode} stderr={r_set.stderr.strip()}")

        # --get
        r_get = subprocess.run(
            [sys.executable, cli_path, "logs", "preset", "--get"],
            capture_output=True, text=True, timeout=10,
        )
        check("G2: --get exits 0", r_get.returncode == 0,
              f"rc={r_get.returncode} stderr={r_get.stderr.strip()}")
        check("G3: --get prints 'host'", r_get.stdout.strip() == "host",
              f"got {r_get.stdout.strip()!r}")

        # --set invalid
        r_bad = subprocess.run(
            [sys.executable, cli_path, "logs", "preset", "--set", "bogus"],
            capture_output=True, text=True, timeout=10,
        )
        check("G4: --set bogus exits non-zero", r_bad.returncode != 0,
              f"rc={r_bad.returncode}")
    finally:
        # Restore original
        set_naming_preset(original if original in VALID_PRESETS else DEFAULT_PRESET)


# ===========================================================================

def main():
    _backup_config()

    print("=" * 60)
    print("F17 GATE: Log Naming Presets (canonical + aliases)")
    print("=" * 60)

    try:
        test_a_constants()
        test_b_preset_roundtrip()
        test_c_display_name()
        test_d_canonical_stability()
        test_e_session_meta_enriched()
        test_f_alias_index()
        test_g_cli_preset()
    finally:
        _restore_config()
        _restore_policy()

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
