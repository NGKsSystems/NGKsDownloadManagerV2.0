#!/usr/bin/env python3
"""
Batch importer: CSV / XLSX -> canonical batch.json
F5 contract -- NGKs DL Manager V2.x
"""

import argparse
import csv
import json
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# Resolve project root so tool can be run from anywhere
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from tools.batch_schema import validate_batch_dict


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_headers(raw: Optional[str]) -> Optional[Dict[str, str]]:
    """Parse a headers value from CSV/XLSX cell.

    Supports two formats:
      1. JSON dict string  ->  parse as JSON
      2. Key:Value;Key2:Value2  ->  split by ; then by first :
    Returns None when *raw* is empty/None.
    """
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return None
    raw = str(raw).strip()
    if raw.startswith("{"):
        return json.loads(raw)
    result = {}
    for pair in raw.split(";"):
        pair = pair.strip()
        if ":" not in pair:
            continue
        key, value = pair.split(":", 1)
        result[key.strip()] = value.strip()
    return result if result else None


def _parse_tags(raw: Optional[str]) -> Optional[List[str]]:
    """Parse comma-separated tags string -> list of trimmed strings."""
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return None
    return [t.strip() for t in str(raw).split(",") if t.strip()]


def _safe_int(value: Any, default: Optional[int] = None) -> Optional[int]:
    """Coerce to int or return default."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return default
    try:
        return int(float(value))  # handles "4.0" from xlsx
    except (ValueError, TypeError):
        return default


def _generate_batch_id(source_path: str) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    base = os.path.splitext(os.path.basename(source_path))[0]
    return f"{ts}_{base}"


# ---------------------------------------------------------------------------
# Importers
# ---------------------------------------------------------------------------

def import_csv(csv_path: str, defaults: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Read a CSV file and return a canonical batch dict."""
    defaults = defaults or {}
    items: List[Dict[str, Any]] = []

    with open(csv_path, "r", newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for idx, row in enumerate(reader):
            item: Dict[str, Any] = {
                "id": f"item-{idx + 1:04d}",
                "url": row.get("url", "").strip(),
            }
            if row.get("filename", "").strip():
                item["filename"] = row["filename"].strip()
            if row.get("dest_dir", "").strip():
                item["dest_dir"] = row["dest_dir"].strip()

            conn = _safe_int(row.get("connections"))
            if conn is not None:
                item["connections"] = conn

            pri = _safe_int(row.get("priority"))
            if pri is not None:
                item["priority"] = pri

            headers = _parse_headers(row.get("headers"))
            if headers:
                item["headers"] = headers

            tags = _parse_tags(row.get("tags"))
            if tags:
                item["tags"] = tags

            items.append(item)

    batch: Dict[str, Any] = {
        "batch_id": _generate_batch_id(csv_path),
        "items": items,
    }
    if defaults:
        batch["defaults"] = defaults
    return batch


def import_xlsx(xlsx_path: str, sheet: Optional[str] = None,
                defaults: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Read an XLSX file and return a canonical batch dict."""
    import openpyxl

    defaults = defaults or {}
    wb = openpyxl.load_workbook(xlsx_path, read_only=True, data_only=True)

    # Select sheet
    if sheet is not None:
        try:
            sheet_idx = int(sheet)
            ws = wb.worksheets[sheet_idx]
        except (ValueError, IndexError):
            ws = wb[sheet]
    else:
        ws = wb.active

    rows = list(ws.iter_rows(values_only=True))
    wb.close()

    if len(rows) < 2:
        return {"batch_id": _generate_batch_id(xlsx_path), "items": []}

    # First row is header
    header = [str(c).strip().lower() if c else "" for c in rows[0]]
    items: List[Dict[str, Any]] = []

    for idx, row in enumerate(rows[1:]):
        cell = {header[i]: row[i] for i in range(min(len(header), len(row)))}

        url_val = cell.get("url")
        if url_val is None or (isinstance(url_val, str) and not url_val.strip()):
            continue  # skip blank rows

        item: Dict[str, Any] = {
            "id": f"item-{idx + 1:04d}",
            "url": str(url_val).strip(),
        }

        fn = cell.get("filename")
        if fn and str(fn).strip():
            item["filename"] = str(fn).strip()

        dd = cell.get("dest_dir")
        if dd and str(dd).strip():
            item["dest_dir"] = str(dd).strip()

        conn = _safe_int(cell.get("connections"))
        if conn is not None:
            item["connections"] = conn

        pri = _safe_int(cell.get("priority"))
        if pri is not None:
            item["priority"] = pri

        headers = _parse_headers(cell.get("headers"))
        if headers:
            item["headers"] = headers

        tags = _parse_tags(cell.get("tags"))
        if tags:
            item["tags"] = tags

        items.append(item)

    batch: Dict[str, Any] = {
        "batch_id": _generate_batch_id(xlsx_path),
        "items": items,
    }
    if defaults:
        batch["defaults"] = defaults
    return batch


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Batch Import: CSV/XLSX -> canonical batch.json")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--csv", metavar="FILE", help="CSV file to import")
    group.add_argument("--xlsx", metavar="FILE", help="XLSX file to import")
    parser.add_argument("--out", required=True, metavar="FILE", help="Output batch.json path")
    parser.add_argument("--sheet", default=None, help="XLSX sheet name or 0-based index")
    parser.add_argument("--dest-dir", default=None, help="Default destination directory")
    parser.add_argument("--connections", type=int, default=None, help="Default connections")
    parser.add_argument("--priority", type=int, default=None, help="Default priority (1-10)")

    args = parser.parse_args()

    # Build defaults from CLI flags
    defaults: Dict[str, Any] = {}
    if args.dest_dir:
        defaults["dest_dir"] = args.dest_dir
    if args.connections is not None:
        defaults["connections"] = args.connections
    if args.priority is not None:
        defaults["priority"] = args.priority

    # Import
    if args.csv:
        batch = import_csv(args.csv, defaults=defaults or None)
    else:
        batch = import_xlsx(args.xlsx, sheet=args.sheet, defaults=defaults or None)

    # Validate
    errors = validate_batch_dict(batch)
    if errors:
        for err in errors:
            print(f"VALIDATION ERROR: {err}", file=sys.stderr)
        sys.exit(2)

    # Write
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(batch, f, indent=2)

    print(f"OK | items={len(batch['items'])} | output={args.out}")
    sys.exit(0)


if __name__ == "__main__":
    main()
