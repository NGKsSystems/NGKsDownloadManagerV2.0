#!/usr/bin/env python3
"""
F16/F17 Forensics metadata helpers + log naming presets.

Separated from batch_run.py to avoid security scan false-positives
(subprocess is forbidden in core download path files).
"""

import hashlib
import json
import os
import platform
import re
import subprocess
from datetime import datetime
from typing import Any, Dict, List, Optional

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CONFIG_PATH = os.path.join(_PROJECT_ROOT, "config.json")

# ---------------------------------------------------------------------------
# Valid naming presets
# ---------------------------------------------------------------------------
VALID_PRESETS = ("shortid", "summary", "host", "firstfile")
DEFAULT_PRESET = "summary"


def git_short_rev() -> str:
    """Return short git revision hash, or 'unknown'."""
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL, cwd=_PROJECT_ROOT
        ).decode().strip()
    except Exception:
        return "unknown"


def app_version() -> str:
    """Read VERSION file from project root."""
    vpath = os.path.join(_PROJECT_ROOT, "VERSION")
    try:
        with open(vpath, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return "unknown"


def policy_version_hash() -> str:
    """SHA-256 of config/policy.json (first 12 hex chars)."""
    ppath = os.path.join(_PROJECT_ROOT, "config", "policy.json")
    try:
        with open(ppath, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()[:12]
    except Exception:
        return "none"


def os_platform() -> str:
    return platform.platform()


def python_version() -> str:
    return platform.python_version()


# ---------------------------------------------------------------------------
# F17: Naming preset config read/write
# ---------------------------------------------------------------------------

def _load_config() -> Dict[str, Any]:
    """Load config.json from project root."""
    try:
        with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_config(cfg: Dict[str, Any]) -> None:
    """Save config.json to project root."""
    with open(_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)


def get_naming_preset() -> str:
    """Return the current log naming preset (default: 'summary')."""
    cfg = _load_config()
    logs_cfg = cfg.get("logs", {})
    preset = logs_cfg.get("naming_preset", DEFAULT_PRESET)
    if preset not in VALID_PRESETS:
        return DEFAULT_PRESET
    return preset


def set_naming_preset(preset: str) -> None:
    """Persist the log naming preset in config.json."""
    if preset not in VALID_PRESETS:
        raise ValueError(f"Invalid preset {preset!r}; valid: {VALID_PRESETS}")
    cfg = _load_config()
    if "logs" not in cfg:
        cfg["logs"] = {}
    cfg["logs"]["naming_preset"] = preset
    _save_config(cfg)


# ---------------------------------------------------------------------------
# F17: Display name builder
# ---------------------------------------------------------------------------

def _sanitize_fragment(text: str, max_len: int = 40) -> str:
    """Sanitize a fragment for use in a display name (safe characters only)."""
    # Keep alphanumeric, dot, dash, underscore
    safe = re.sub(r"[^a-zA-Z0-9._\-]", "_", text)
    return safe[:max_len]


def build_display_name(
    preset: str,
    mode: str,
    short_id: str,
    summary_tag: str = "",
    primary_host: str = "",
    first_filename: str = "",
    time_str: str = "",
) -> str:
    """Build a display name string based on the chosen preset.

    All presets start with ``HHMMSS - <mode>`` and end with ``<shortid>``.
    The middle segment varies by preset.
    """
    ts = time_str or datetime.now().strftime("%H%M%S")
    sid = short_id

    if preset == "shortid":
        return f"{ts} - {mode} - {sid}"
    elif preset == "host":
        frag = _sanitize_fragment(primary_host) if primary_host else "unknown"
        return f"{ts} - {mode} - {frag} - {sid}"
    elif preset == "firstfile":
        frag = _sanitize_fragment(first_filename) if first_filename else "unknown"
        return f"{ts} - {mode} - {frag} - {sid}"
    else:  # "summary" (default)
        return f"{ts} - {mode} - {summary_tag} - {sid}"


# ---------------------------------------------------------------------------
# F17: Alias index (append-only JSONL)
# ---------------------------------------------------------------------------

_ALIAS_INDEX_PATH = os.path.join(_PROJECT_ROOT, "logs", "_index", "aliases.jsonl")


def append_alias_index(
    run_id: str,
    canonical_rel: str,
    display_name: str,
    preset: str,
    ts: str = "",
) -> None:
    """Append one line to logs/_index/aliases.jsonl."""
    os.makedirs(os.path.dirname(_ALIAS_INDEX_PATH), exist_ok=True)
    entry = {
        "run_id": run_id,
        "canonical_rel": canonical_rel,
        "display_name": display_name,
        "preset": preset,
        "ts": ts or datetime.now().isoformat(),
    }
    with open(_ALIAS_INDEX_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
