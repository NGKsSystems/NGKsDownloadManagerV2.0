# Release Integrity Metadata

This document describes how to verify the integrity of NGKs Download Manager releases.

## Version Display

The application version is stored in the `VERSION` file at the repo root.

```
cat VERSION
# Output: 2.0
```

The CLI command `python ngks_dl_cli.py version` prints the version and (if in a git repo) the short commit hash:

```
NGKs Download Manager v2.0 (git abc1234)
```

## Where Installer/Release Hashes Are Published

When packaging a release:

1. Compute SHA-256 of every distributable artifact (zip, exe, wheel, etc.)
2. Publish the hashes in a `SHA256SUMS.txt` file alongside the release on GitHub Releases.
3. Format: one line per file — `<sha256hex>  <filename>`

Example:
```
a1b2c3d4...  NGKsDLManager-2.0-win64.zip
e5f6a7b8...  NGKsDLManager-2.0.tar.gz
```

## How to Validate SHA-256

### Windows (PowerShell)

```powershell
Get-FileHash .\NGKsDLManager-2.0-win64.zip -Algorithm SHA256 | Format-List
```

Compare the `Hash` output against the value in `SHA256SUMS.txt`.

### Linux / macOS

```bash
sha256sum NGKsDLManager-2.0.tar.gz
# Compare output against SHA256SUMS.txt
```

### Python

```python
import hashlib
h = hashlib.sha256(open("NGKsDLManager-2.0-win64.zip", "rb").read()).hexdigest()
print(h)
```

## How Version Is Shown in App / CLI

| Context | Command | Output |
|---------|---------|--------|
| CLI | `python ngks_dl_cli.py version` | `NGKs Download Manager v2.0 (git <hash>)` |
| GUI | Help → About (planned) | Version + build date |

## yt-dlp Sub-dependency Verification

yt-dlp updates are verified using the upstream `SHA2-256SUMS` asset from each GitHub release.
See `ytdlp_manager.py` for implementation details (F8).

## Policy File Integrity

The policy engine (`config/policy.json`) is loaded at startup. Its content hash
can be included in forensic run reports (F16) to prove which policy was active
during a given download session.
