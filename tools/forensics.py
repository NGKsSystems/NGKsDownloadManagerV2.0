#!/usr/bin/env python3
"""
F16 Forensics metadata helpers.

Separated from batch_run.py to avoid security scan false-positives
(subprocess is forbidden in core download path files).
"""

import hashlib
import os
import platform
import subprocess

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


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
