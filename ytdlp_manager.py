#!/usr/bin/env python3
"""
F8: yt-dlp Lifecycle Management — Version Health Check & Verified Updater

Trusted source: GitHub official yt-dlp releases
    https://api.github.com/repos/yt-dlp/yt-dlp/releases/latest
Verification:   SHA2-256SUMS asset from release (sha256sum-format hash file)

Two update strategies (selected by environment detection):
  A) ``pip upgrade``: for venv/dev environments (sys.prefix != sys.base_prefix)
  B) ``binary replacement``: for shipped/packaged builds (download + sha256 + atomic swap)

Security events logged via security.py ``SECURITY.<EVENT>`` format.
"""

import hashlib
import json
import logging
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

from security import log_security_event

logger = logging.getLogger("ytdlp_manager")

# ---------------------------------------------------------------------------
# Trusted Source Configuration
# ---------------------------------------------------------------------------

GITHUB_RELEASE_URL = "https://api.github.com/repos/yt-dlp/yt-dlp/releases/latest"
SHA256SUMS_ASSET_NAME = "SHA2-256SUMS"


def _get_binary_asset_name() -> str:
    """Return the expected yt-dlp binary asset name for this platform."""
    if platform.system() == "Windows":
        return "yt-dlp.exe"
    elif platform.system() == "Darwin":
        return "yt-dlp_macos"
    return "yt-dlp_linux"


# ---------------------------------------------------------------------------
# Step 3: Runtime Version Detection
# ---------------------------------------------------------------------------

def get_current_ytdlp_version() -> Optional[str]:
    """Detect the currently installed yt-dlp version.

    Strategy A (pip/import): ``yt_dlp.version.__version__``
    Strategy B (binary):     controlled binary ``--version``

    Returns version string or None if not installed.
    """
    # Try import first (works for pip installs)
    try:
        import yt_dlp.version as _ytv         # noqa: F811
        v = getattr(_ytv, "__version__", None)
        if v:
            return str(v)
    except (ImportError, AttributeError):
        pass

    # Try controlled binary path
    binary = _find_controlled_binary()
    if binary:
        try:
            result = subprocess.run(
                [binary, "--version"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except (subprocess.TimeoutExpired, OSError):
            pass

    return None


def _find_controlled_binary() -> Optional[str]:
    """Find yt-dlp binary in controlled install directories only.

    Does NOT search PATH — only looks in ``<project_root>/bin/``.
    """
    project_root = os.path.dirname(os.path.abspath(__file__))
    bin_dir = os.path.join(project_root, "bin")

    if platform.system() == "Windows":
        candidate = os.path.join(bin_dir, "yt-dlp.exe")
    else:
        candidate = os.path.join(bin_dir, "yt-dlp")

    if os.path.isfile(candidate):
        return candidate
    return None


# ---------------------------------------------------------------------------
# Step 2: Trusted Source — Fetch Latest Release Info
# ---------------------------------------------------------------------------

def get_latest_release_info(api_url: str = None) -> Optional[Dict[str, Any]]:
    """Fetch latest yt-dlp release metadata from the trusted source (GitHub).

    Returns parsed JSON dict or None on failure.
    """
    url = api_url or GITHUB_RELEASE_URL
    log_security_event("YTDLP.CHECK", url=url, detail="fetching latest release info")

    try:
        req = urllib.request.Request(
            url,
            headers={"Accept": "application/json",
                     "User-Agent": "NGKs-DL-Manager"},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data
    except (urllib.error.URLError, json.JSONDecodeError, OSError) as e:
        logger.warning(f"Failed to fetch release info from {url}: {e}")
        return None


def get_latest_ytdlp_version(api_url: str = None) -> Optional[str]:
    """Get the latest yt-dlp version string from the trusted source."""
    info = get_latest_release_info(api_url)
    if info and "tag_name" in info:
        version = info["tag_name"]
        log_security_event("YTDLP.CHECK", detail=f"latest_version={version}")
        return version
    return None


def fetch_sha256sums(release_info: Dict[str, Any],
                     sums_url_override: str = None) -> Optional[Dict[str, str]]:
    """Download and parse the SHA2-256SUMS asset from a release.

    Returns dict of ``{filename: sha256_hex}`` or None on failure.
    """
    if sums_url_override:
        sums_url = sums_url_override
    else:
        assets = release_info.get("assets", [])
        sums_url = None
        for asset in assets:
            if asset.get("name") == SHA256SUMS_ASSET_NAME:
                sums_url = asset.get("browser_download_url")
                break

    if not sums_url:
        logger.warning("SHA256SUMS asset not found in release")
        return None

    try:
        req = urllib.request.Request(
            sums_url, headers={"User-Agent": "NGKs-DL-Manager"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            content = resp.read().decode("utf-8")
    except (urllib.error.URLError, OSError) as e:
        logger.warning(f"Failed to download SHA256SUMS: {e}")
        return None

    return parse_sha256sums(content)


def parse_sha256sums(content: str) -> Dict[str, str]:
    """Parse sha256sum-format content into ``{filename: hash}`` dict."""
    result: Dict[str, str] = {}
    for line in content.strip().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # Format: <hash>  <filename>  OR  <hash> *<filename>
        parts = line.split(None, 1)
        if len(parts) == 2:
            sha_hash, fname = parts
            fname = fname.lstrip("* ")
            result[fname] = sha_hash.lower()
    return result


# ---------------------------------------------------------------------------
# Hash Verification
# ---------------------------------------------------------------------------

def compute_sha256(filepath: str) -> str:
    """Compute SHA-256 hash of a file."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_sha256(filepath: str, expected_hash: str) -> bool:
    """Verify that a file matches the expected SHA-256 hash.

    Returns True if match, False if mismatch.
    Logs a security event in both cases.
    """
    actual = compute_sha256(filepath)
    match = actual == expected_hash.lower()

    if match:
        log_security_event("YTDLP.HASH_VERIFIED",
                           final_path=filepath,
                           detail=f"sha256={actual}",
                           decision="ALLOW")
    else:
        log_security_event("YTDLP.INSTALL_FAIL",
                           final_path=filepath,
                           reason="hash_mismatch",
                           detail=f"expected={expected_hash.lower()} actual={actual}",
                           decision="DENY")
    return match


# ---------------------------------------------------------------------------
# Step 4: Environment Detection
# ---------------------------------------------------------------------------

def detect_environment() -> str:
    """Detect whether we're in a pip-managed (venv/dev) or binary (shipped) env.

    Returns ``"pip"`` or ``"binary"``.
    """
    # Virtual environment => pip path
    if sys.prefix != sys.base_prefix:
        return "pip"

    # Controlled binary exists => binary path
    if _find_controlled_binary():
        return "binary"

    # Default: try pip
    try:
        import pip      # noqa: F401
        return "pip"
    except ImportError:
        pass

    return "binary"


# ---------------------------------------------------------------------------
# Step 4A: pip Upgrade Path
# ---------------------------------------------------------------------------

def update_via_pip() -> Tuple[bool, str]:
    """Update yt-dlp via pip (dev/venv environments).

    Returns ``(success, message)``.
    """
    log_security_event("YTDLP.DOWNLOAD_START", detail="method=pip")

    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--upgrade", "yt-dlp",
             "--disable-pip-version-check", "--no-input"],
            capture_output=True, text=True, timeout=120,
        )

        if result.returncode == 0:
            new_version = get_current_ytdlp_version()
            log_security_event("YTDLP.INSTALL_OK",
                               detail=f"method=pip new_version={new_version}")
            return True, f"Updated to {new_version}"
        else:
            error = result.stderr.strip()[:200]
            log_security_event("YTDLP.INSTALL_FAIL",
                               reason="pip_error", detail=error)
            return False, f"pip error: {error}"
    except subprocess.TimeoutExpired:
        log_security_event("YTDLP.INSTALL_FAIL", reason="timeout")
        return False, "pip upgrade timed out"
    except OSError as e:
        log_security_event("YTDLP.INSTALL_FAIL", reason=str(e))
        return False, str(e)


# ---------------------------------------------------------------------------
# Step 4B: Binary Replacement Path
# ---------------------------------------------------------------------------

def update_via_binary(release_info: Dict[str, Any],
                      install_dir: str = None,
                      artifact_url: str = None,
                      expected_hash: str = None) -> Tuple[bool, str]:
    """Update yt-dlp via trusted binary download + sha256 verification.

    If *artifact_url* and *expected_hash* are provided, uses those directly
    (for testing with LocalRangeServer).  Otherwise fetches from *release_info*.

    Returns ``(success, message)``.
    """
    if install_dir is None:
        project_root = os.path.dirname(os.path.abspath(__file__))
        install_dir = os.path.join(project_root, "bin")

    os.makedirs(install_dir, exist_ok=True)

    binary_name = _get_binary_asset_name()
    final_path = os.path.join(install_dir, binary_name)

    # ---- Resolve download URL and expected hash ----
    if artifact_url and expected_hash:
        dl_url = artifact_url
        sha_expected = expected_hash
    else:
        sums = fetch_sha256sums(release_info)
        if not sums:
            log_security_event("YTDLP.INSTALL_FAIL",
                               reason="sha256sums_unavailable")
            return False, "Could not fetch SHA256SUMS from release"

        sha_expected = sums.get(binary_name)
        if not sha_expected:
            log_security_event("YTDLP.INSTALL_FAIL",
                               reason=f"no hash for {binary_name} in SHA256SUMS")
            return False, f"No hash found for {binary_name} in SHA256SUMS"

        dl_url = None
        for asset in release_info.get("assets", []):
            if asset.get("name") == binary_name:
                dl_url = asset.get("browser_download_url")
                break
        if not dl_url:
            log_security_event("YTDLP.INSTALL_FAIL",
                               reason=f"binary {binary_name} not in release assets")
            return False, f"Binary {binary_name} not found in release assets"

    log_security_event("YTDLP.DOWNLOAD_START",
                       url=dl_url, detail=f"method=binary target={binary_name}")

    # ---- Download to temp file in install_dir ----
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".download.tmp", dir=install_dir)
    os.close(tmp_fd)

    try:
        req = urllib.request.Request(dl_url,
                                     headers={"User-Agent": "NGKs-DL-Manager"})
        with urllib.request.urlopen(req, timeout=120) as resp:
            with open(tmp_path, "wb") as f:
                shutil.copyfileobj(resp, f)

        # ---- Verify hash BEFORE replacing ----
        if not verify_sha256(tmp_path, sha_expected):
            os.unlink(tmp_path)
            return False, "SHA-256 hash mismatch — artifact rejected"

        # ---- Atomic-ish replace ----
        if os.path.exists(final_path):
            backup = final_path + ".bak"
            if os.path.exists(backup):
                os.unlink(backup)
            os.rename(final_path, backup)

        os.rename(tmp_path, final_path)

        # ---- Rider file check ----
        expected_names = {binary_name, binary_name + ".bak"}
        riders: List[str] = []
        for fname in os.listdir(install_dir):
            if fname in expected_names:
                continue
            if fname.endswith(".download.tmp"):
                continue  # our own temp suffix, should be cleaned on error
            riders.append(fname)

        if riders:
            log_security_event("YTDLP.INSTALL_FAIL",
                               reason="rider_file",
                               detail=f"unexpected files: {riders}",
                               final_path=install_dir)

        log_security_event("YTDLP.INSTALL_OK",
                           final_path=final_path,
                           detail=f"method=binary sha256={sha_expected}")
        return True, f"Updated binary: {final_path}"

    except Exception as e:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        log_security_event("YTDLP.INSTALL_FAIL", reason=str(e))
        return False, str(e)


# ---------------------------------------------------------------------------
# Step 5: User Prompt (CLI)
# ---------------------------------------------------------------------------

def check_and_prompt_cli(api_url: str = None,
                         auto_yes: bool = False) -> int:
    """CLI flow: check version, prompt user, update if approved.

    Returns exit code:
      0 = up to date or updated successfully
      1 = error
      2 = user declined
    """
    current = get_current_ytdlp_version()
    if current is None:
        print("yt-dlp is not installed.")
        return 1

    print(f"Current yt-dlp version: {current}")

    latest = get_latest_ytdlp_version(api_url)
    if latest is None:
        print("Could not check latest version (network error).")
        return 1

    print(f"Latest yt-dlp version:  {latest}")

    if _versions_match(current, latest):
        print("yt-dlp is up to date.")
        return 0

    log_security_event("YTDLP.UPDATE_AVAILABLE",
                       detail=f"current={current} latest={latest}")

    print(f"\nUpdate available: {current} -> {latest}")

    if auto_yes:
        answer = "y"
    else:
        try:
            answer = input("Update now? [y/N] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            answer = "n"

    if answer != "y":
        print("Update declined.")
        return 2

    env = detect_environment()
    print(f"Update method: {env}")

    if env == "pip":
        ok, msg = update_via_pip()
    else:
        release_info = get_latest_release_info(api_url)
        if not release_info:
            print("Failed to fetch release info.")
            return 1
        ok, msg = update_via_binary(release_info)

    if ok:
        print(f"SUCCESS: {msg}")
        return 0
    else:
        print(f"FAILED: {msg}")
        return 1


def _versions_match(current: str, latest: str) -> bool:
    """Compare version strings, normalized."""
    return current.strip().lower() == latest.strip().lower()


# TODO(F8-UI): On MainWindow startup, call a UI-aware version of this flow:
#   from ytdlp_manager import get_current_ytdlp_version, get_latest_ytdlp_version
#   if current != latest:
#       reply = QMessageBox.question(self, "yt-dlp Update",
#           f"Update available: {current} -> {latest}\nUpdate now?")
#       if reply == QMessageBox.Yes: ...
