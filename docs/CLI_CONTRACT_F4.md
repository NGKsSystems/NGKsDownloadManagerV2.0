# F4 -- CLI / Headless Contract Spec (Frozen)

**Status:** FROZEN -- no implementation in this phase; spec only.
**Date:** 2026-02-10
**Applies to:** NGKs Download Manager V2.x
**Baseline commit:** b060826

---

## Scope

Define a stable CLI interface for NGKs Download Manager V2.x that:

1. Runs downloads headlessly using the **same engine** as the UI.
2. Enforces the **same policy** (denylist, resume rules, etc.).
3. Produces **deterministic machine-readable outputs**.
4. Supports **Option A batch** later (CSV/XLSX -> JSON -> enqueue).

No implementation in this phase; spec only.

---

## 1  Executables and Entrypoints

### Primary executable

`ngks-dl` (Windows: `ngks-dl.exe` or `ngks-dl.py`)

### Invocation contract

- All commands must be runnable from repo root **and** from installed location.
- Always return exit codes defined in section 4.
- Never require UI components (PySide6 etc. must not be imported).

---

## 2  Commands

### 2.1  `ngks-dl download`

Single direct download (still uses policy + engine).

```
ngks-dl download --url <URL> --out <PATH> [options]
```

| Option | Required | Default | Description |
|--------|----------|---------|-------------|
| `--url <URL>` | yes | -- | HTTP/HTTPS only |
| `--out <PATH>` | yes | -- | Final file path |
| `--connections <N>` | no | engine default | If policy restricts, policy wins |
| `--resume` | no | `true` | Attempt resume if state exists and policy allows |
| `--overwrite` | no | `false` | If true, deletes existing target and state |
| `--headers <JSON>` | no | -- | JSON object string: `{"Authorization":"Bearer ..."}` |
| `--timeout <seconds>` | no | -- | Per-download timeout |
| `--tag <value>` | no | -- | Repeatable |
| `--priority <int>` | no | -- | Used when routed through queue |

**Behavior:**
- Must enforce policy before starting.
- Must write temp as `.part` and commit atomically.

### 2.2  `ngks-dl enqueue`

Add one item to queue (Option A path).

```
ngks-dl enqueue --url <URL> --dest-dir <DIR> [options]
```

| Option | Required | Default | Description |
|--------|----------|---------|-------------|
| `--url <URL>` | yes | -- | |
| `--dest-dir <DIR>` | yes | -- | |
| `--filename <NAME>` | no | -- | |
| `--connections <N>` | no | -- | |
| `--priority <int>` | no | -- | |
| `--headers <JSON>` | no | -- | |
| `--resume` | no | `true` | |

**Behavior:**
- Enqueue only (no download execution).
- Policy is checked at enqueue time.

### 2.3  `ngks-dl run-queue`

Run queue until completion, or until criteria met.

```
ngks-dl run-queue [--max-concurrent <N>] [--until empty|time:<sec>|count:<n>]
```

| Option | Required | Default | Description |
|--------|----------|---------|-------------|
| `--max-concurrent <N>` | no | config / queue default | |
| `--until` | no | `empty` | `empty`, `time:<sec>`, `count:<n>` |
| `--stop-on-fail` | no | `false` | Abort on first FAILED |
| `--report <PATH>` | no | -- | Output JSON report (see section 3.2) |

**Behavior:**
- Uses same executor as UI queue path.
- Respects policy for each task and for resume.

### 2.4  `ngks-dl batch run`

Run a canonical batch JSON (future-ready for CSV/XLSX import).

```
ngks-dl batch run --file <batch.json> [--report <PATH>]
```

**Behavior:**
- Validates schema.
- Enqueues all items (policy enforced).
- Executes via queue.
- Produces a report.

*(Import from CSV/XLSX is F5; this command is frozen now.)*

### 2.5  `ngks-dl batch validate`

Validate only.

```
ngks-dl batch validate --file <batch.json>
```

### 2.6  `ngks-dl policy check`

Policy dry-run for a URL.

```
ngks-dl policy check --url <URL>
```

**Output:** Allow/deny + reason (machine-readable).

### 2.7  `ngks-dl version`

Print version and build info.

```
ngks-dl version
```

---

## 3  Canonical Outputs

### 3.1  Standard output rule

- Default is **human-readable summary**.
- `--json` flag switches to **machine-readable JSON only** (no extra lines).

### 3.2  Report JSON schema (`--report`)

```json
{
  "run_id": "2026-02-10T16:05:00Z",
  "mode": "queue|batch|download",
  "results": [
    {
      "task_id": "abc",
      "url": "https://...",
      "final_path": "C:\\...",
      "state": "COMPLETED|FAILED|CANCELLED|DENIED",
      "bytes_total": 123,
      "bytes_downloaded": 123,
      "sha256": "optional",
      "started_at": "ISO-8601",
      "ended_at": "ISO-8601",
      "error": "optional string"
    }
  ],
  "summary": {
    "completed": 1,
    "failed": 0,
    "cancelled": 0,
    "denied": 0
  }
}
```

**Constraints:**
- All string values are UTF-8; file paths use OS-native separators.
- `state` values are the exact strings listed (no other values allowed).
- `sha256` is lowercase hex, present only on COMPLETED.
- `started_at` / `ended_at` are ISO-8601 with timezone.

---

## 4  Exit Codes (Frozen)

| Code | Meaning |
|------|---------|
| **0** | Success -- all requested work completed successfully |
| **1** | General failure -- unexpected error |
| **2** | Validation error -- bad arguments / batch schema invalid |
| **3** | Policy denied -- single command denied; batch/queue use report + exit 4 |
| **4** | Partial failure -- batch/queue: some items failed/denied/cancelled |
| **130** | Interrupted by user (Ctrl+C / SIGINT) |

---

## 5  State and File Conventions

| Artifact | Path |
|----------|------|
| Temp download | `<final>.part` |
| Resume state | `<final>.resume` |
| Queue state | `data/queue_state.json` |
| Batch reports | `data/runtime/batch_reports/<run_id>.json` |

- All created paths must be inside `data/runtime/` unless user explicitly chooses `--report <path>`.

---

## 6  Non-Goals (Explicit)

- No torrents / magnet links / P2P
- No FTP / SFTP / Usenet
- No DRM bypass
- No background services in F4 (CLI is foreground process only)

---

## 7  Policy Host Normalization (Improvement -- Not Implemented in F4)

### 7.1  Problem (current behavior)

Policy checks use `parsed_url.netloc` which includes port. This allows
bypass behavior:

1. `denylist` contains `127.0.0.1`
2. URL `http://127.0.0.1:57802/file` yields `netloc = "127.0.0.1:57802"`
3. Naive string compare fails to match denylist entry -> **allowed**

This is why synthetic `127.0.0.1:19999` worked for V2.9 test fixes
(commits f78d069, b060826).

**Affected code:** `policy_engine.py` line 149:
```python
host = parsed_url.netloc.lower()   # <-- includes port
```

### 7.2  Required behavior (frozen for future patch)

Normalize host for policy comparisons:

```python
host = parsed_url.hostname.lower() if parsed_url.hostname else None
if host is None:
    return PolicyDecision('DENY', 'invalid host')
```

- Apply deny/allow lists against this **normalized hostname** (no port).
- If port-level blocking is needed, add a separate optional mechanism:
  `denylist_netloc` for `host:port` matches.
- Default `denylist` must be **hostname-based** (no port).

### 7.3  Test impact

Tests that relied on the port trick to bypass denylist must be updated:

| Test file | Current workaround | Required fix |
|-----------|--------------------|--------------|
| `tests/test_v29_ui_contract.py` | `127.0.0.1:19999` | Use test-only policy fixture or `test.invalid` domain |
| `tests/test_v27_persistence.py` | `127.0.0.1:{port}` | Use test-only policy fixture or `test.invalid` domain |

### 7.4  Compatibility note

- Closes accidental bypass.
- Makes policy intent clearer and more secure.
- **Not implemented in F4** -- this section records the contract for
  the future patch.

---

## Appendix A: Batch JSON Schema (for 2.4 / 2.5)

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "required": ["version", "items"],
  "properties": {
    "version": { "const": "1.0" },
    "items": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["url"],
        "properties": {
          "url":         { "type": "string", "format": "uri" },
          "dest_dir":    { "type": "string" },
          "filename":    { "type": "string" },
          "connections": { "type": "integer", "minimum": 1, "maximum": 16 },
          "priority":    { "type": "integer", "minimum": 1, "maximum": 10 },
          "headers":     { "type": "object" },
          "tags":        { "type": "array", "items": { "type": "string" } },
          "resume":      { "type": "boolean", "default": true }
        }
      }
    }
  }
}
```

---

*End of F4 Contract Spec.*
