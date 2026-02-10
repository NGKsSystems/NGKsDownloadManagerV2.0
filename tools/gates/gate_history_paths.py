"""
Gate: History Path Regression Guard
------------------------------------
Ensures the orphan history path never re-appears in tracked source files
and that exactly one download_history_v2.json exists under data/.

Exit 0 = all checks pass.  Exit 1 = at least one check failed.
Prints OVERALL: PASS or OVERALL: FAIL for run_gates.ps1 compatibility.
"""

import os
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

# Split to avoid self-match
FORBIDDEN_STRING = "data/runtime/" + "download_history_v2.json"

# Directories to skip when scanning source files
EXCLUDED_DIRS = {
    ".venv", "__pycache__", ".git", "node_modules",
    "test-results", "artifacts", "_orphan_archive",
}

# Extensions considered "source / config" (not binaries)
SOURCE_EXTENSIONS = {
    ".py", ".ps1", ".bat", ".sh", ".json", ".yaml", ".yml",
    ".toml", ".cfg", ".ini", ".txt", ".md", ".rst",
}


def _should_skip_dir(dirname: str) -> bool:
    return dirname in EXCLUDED_DIRS


def check_forbidden_string() -> bool:
    """Check A: no tracked/source file references the orphan path."""
    hits = []
    for dirpath, dirnames, filenames in os.walk(REPO_ROOT):
        # Prune excluded dirs in-place
        dirnames[:] = [d for d in dirnames if not _should_skip_dir(d)]
        for fname in filenames:
            ext = os.path.splitext(fname)[1].lower()
            if ext not in SOURCE_EXTENSIONS:
                continue
            fpath = os.path.join(dirpath, fname)
            try:
                with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                    for lineno, line in enumerate(f, 1):
                        if FORBIDDEN_STRING in line:
                            rel = os.path.relpath(fpath, REPO_ROOT)
                            hits.append(f"  {rel}:{lineno}")
            except (OSError, PermissionError):
                pass

    if hits:
        print(f"FAIL  [A] Forbidden string '{FORBIDDEN_STRING}' found in:")
        for h in hits:
            print(h)
        return False

    print(f"PASS  [A] No source file references '{FORBIDDEN_STRING}'")
    return True


def check_history_file_count() -> bool:
    """Check B: exactly one download_history_v2.json under data/."""
    data_dir = os.path.join(REPO_ROOT, "data")
    if not os.path.isdir(data_dir):
        print("FAIL  [B] data/ directory does not exist")
        return False

    found = []
    for dirpath, dirnames, filenames in os.walk(data_dir):
        dirnames[:] = [d for d in dirnames if not _should_skip_dir(d)]
        for fname in filenames:
            if fname == "download_history_v2.json":
                found.append(os.path.relpath(os.path.join(dirpath, fname), REPO_ROOT))

    if len(found) == 1:
        print(f"PASS  [B] Exactly 1 history file: {found[0]}")
        return True

    print(f"FAIL  [B] Expected 1 history file under data/, found {len(found)}:")
    for f in found:
        print(f"  {f}")
    return False


def main() -> int:
    print("=" * 60)
    print("Gate: History Path Regression Guard")
    print("=" * 60)

    a = check_forbidden_string()
    b = check_history_file_count()

    ok = a and b
    print()
    print(f"OVERALL: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
