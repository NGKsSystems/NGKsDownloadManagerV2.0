#!/usr/bin/env python3
"""
Batch JSON schema definition and validator.
F5 contract -- canonical batch format for NGKs DL Manager V2.x.
"""

from urllib.parse import urlparse
from typing import Any, Dict, List


# Canonical top-level keys
_BATCH_TOPLEVEL_KEYS = {"batch_id", "defaults", "items"}

# Allowed keys inside "defaults"
_DEFAULTS_KEYS = {"dest_dir", "connections", "priority"}

# Allowed keys inside each item
_ITEM_KEYS = {"id", "url", "filename", "dest_dir", "connections", "priority", "headers", "tags", "sha256"}

# Required keys inside each item
_ITEM_REQUIRED = {"id", "url"}


def validate_batch_dict(batch: Dict[str, Any]) -> List[str]:
    """Validate a canonical batch dict.

    Returns a list of human-readable error strings.
    Empty list means valid.
    """
    errors: List[str] = []

    if not isinstance(batch, dict):
        return ["batch must be a JSON object (dict)"]

    # -- top-level keys --
    extra_top = set(batch.keys()) - _BATCH_TOPLEVEL_KEYS
    if extra_top:
        errors.append(f"unknown top-level keys: {sorted(extra_top)}")

    if "items" not in batch:
        errors.append("missing required key: items")
        return errors  # can't continue without items

    if not isinstance(batch["items"], list):
        errors.append("items must be a list")
        return errors

    if len(batch["items"]) == 0:
        errors.append("items list is empty")

    # -- defaults --
    defaults = batch.get("defaults", {})
    if not isinstance(defaults, dict):
        errors.append("defaults must be a dict")
        defaults = {}
    else:
        extra_def = set(defaults.keys()) - _DEFAULTS_KEYS
        if extra_def:
            errors.append(f"unknown keys in defaults: {sorted(extra_def)}")
        if "connections" in defaults:
            if not isinstance(defaults["connections"], int) or defaults["connections"] < 1:
                errors.append("defaults.connections must be a positive integer")
        if "priority" in defaults:
            if not isinstance(defaults["priority"], int) or not (1 <= defaults["priority"] <= 10):
                errors.append("defaults.priority must be an integer 1-10")

    # -- items --
    seen_ids = set()
    for idx, item in enumerate(batch["items"]):
        prefix = f"items[{idx}]"

        if not isinstance(item, dict):
            errors.append(f"{prefix}: must be a dict")
            continue

        extra_item = set(item.keys()) - _ITEM_KEYS
        if extra_item:
            errors.append(f"{prefix}: unknown keys: {sorted(extra_item)}")

        for req in _ITEM_REQUIRED:
            if req not in item:
                errors.append(f"{prefix}: missing required key: {req}")

        # id uniqueness
        item_id = item.get("id")
        if item_id is not None:
            if item_id in seen_ids:
                errors.append(f"{prefix}: duplicate id: {item_id}")
            seen_ids.add(item_id)

        # url validation
        url = item.get("url")
        if url is not None:
            if not isinstance(url, str) or not url.strip():
                errors.append(f"{prefix}: url must be a non-empty string")
            else:
                parsed = urlparse(url)
                if parsed.scheme.lower() not in ("http", "https"):
                    errors.append(f"{prefix}: url scheme must be http or https, got: {parsed.scheme}")

        # optional typed fields
        if "connections" in item:
            v = item["connections"]
            if not isinstance(v, int) or v < 1:
                errors.append(f"{prefix}: connections must be a positive integer")

        if "priority" in item:
            v = item["priority"]
            if not isinstance(v, int) or not (1 <= v <= 10):
                errors.append(f"{prefix}: priority must be an integer 1-10")

        if "headers" in item:
            v = item["headers"]
            if not isinstance(v, dict):
                errors.append(f"{prefix}: headers must be a dict")
            elif not all(isinstance(k, str) and isinstance(val, str) for k, val in v.items()):
                errors.append(f"{prefix}: headers must be dict[str, str]")

        if "tags" in item:
            v = item["tags"]
            if not isinstance(v, list):
                errors.append(f"{prefix}: tags must be a list")
            elif not all(isinstance(t, str) for t in v):
                errors.append(f"{prefix}: tags must be list[str]")

        if "filename" in item:
            v = item["filename"]
            if not isinstance(v, str) or not v.strip():
                errors.append(f"{prefix}: filename must be a non-empty string")

        if "dest_dir" in item:
            v = item["dest_dir"]
            if not isinstance(v, str) or not v.strip():
                errors.append(f"{prefix}: dest_dir must be a non-empty string")

        if "sha256" in item:
            v = item["sha256"]
            if not isinstance(v, str) or len(v) != 64:
                errors.append(f"{prefix}: sha256 must be a 64-character hex string")
            elif not all(c in '0123456789abcdefABCDEF' for c in v):
                errors.append(f"{prefix}: sha256 must contain only hex characters")

    return errors
