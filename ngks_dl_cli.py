#!/usr/bin/env python3
"""
ngks-dl CLI entrypoint -- NGKs Download Manager V2.x
F4/F5 contract: headless commands using the same engine as the UI.

Usage:
  python ngks_dl_cli.py batch import  --csv <file> --out <batch.json>
  python ngks_dl_cli.py batch import  --xlsx <file> --out <batch.json>
  python ngks_dl_cli.py batch validate --file <batch.json>
  python ngks_dl_cli.py batch run     --file <batch.json> [--report <path>]
  python ngks_dl_cli.py ytdlp check
  python ngks_dl_cli.py ytdlp update [--yes]
  python ngks_dl_cli.py version
"""

import argparse
import json
import os
import sys

# Ensure project root is on sys.path
_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)


def cmd_batch_import(args):
    """batch import: CSV/XLSX -> canonical batch.json"""
    from tools.batch_import import import_csv, import_xlsx
    from tools.batch_schema import validate_batch_dict

    defaults = {}
    if args.dest_dir:
        defaults["dest_dir"] = args.dest_dir
    if args.connections is not None:
        defaults["connections"] = args.connections
    if args.priority is not None:
        defaults["priority"] = args.priority

    if args.csv:
        batch = import_csv(args.csv, defaults=defaults or None)
    elif args.xlsx:
        batch = import_xlsx(args.xlsx, sheet=args.sheet, defaults=defaults or None)
    else:
        print("ERROR: provide --csv or --xlsx", file=sys.stderr)
        sys.exit(2)

    errors = validate_batch_dict(batch)
    if errors:
        for e in errors:
            print(f"VALIDATION ERROR: {e}", file=sys.stderr)
        sys.exit(2)

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(batch, f, indent=2)

    print(f"OK | items={len(batch['items'])} | output={args.out}")


def cmd_batch_validate(args):
    """batch validate: schema check only"""
    from tools.batch_schema import validate_batch_dict

    try:
        with open(args.file, "r", encoding="utf-8") as f:
            batch = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(2)

    errors = validate_batch_dict(batch)
    if errors:
        for e in errors:
            print(f"VALIDATION ERROR: {e}", file=sys.stderr)
        sys.exit(2)
    else:
        print(f"VALID | items={len(batch.get('items', []))}")


def cmd_batch_run(args):
    """batch run: execute batch.json via QueueManager"""
    # Delegate to batch_run module (handles logging, SIGINT, exit codes)
    sys.argv = ["batch_run", "--file", args.file]
    if args.report:
        sys.argv += ["--report", args.report]
    if args.max_concurrent:
        sys.argv += ["--max-concurrent", str(args.max_concurrent)]
    if args.until:
        sys.argv += ["--until", args.until]
    if args.stop_on_fail:
        sys.argv += ["--stop-on-fail"]
    if args.verbose:
        sys.argv += ["--verbose"]

    from tools.batch_run import main as batch_run_main
    batch_run_main()


def cmd_version(args):
    """Print version + git short hash (if available)."""
    version_file = os.path.join(_PROJECT_ROOT, "VERSION")
    if os.path.exists(version_file):
        with open(version_file) as f:
            ver = f.read().strip()
    else:
        ver = "unknown"

    # Try to get git short hash
    git_rev = ""
    try:
        import subprocess
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=5,
            cwd=_PROJECT_ROOT,
        )
        if result.returncode == 0:
            git_rev = f" (git {result.stdout.strip()})"
    except Exception:
        pass

    print(f"NGKsAcquisitionCore v{ver}{git_rev}")
    print("Powered by: NGKsSystems")


def cmd_ytdlp_check(args):
    """ytdlp check: show current + latest yt-dlp version"""
    from ytdlp_manager import get_current_ytdlp_version, get_latest_ytdlp_version

    current = get_current_ytdlp_version()
    print(f"Current yt-dlp version: {current or 'not installed'}")

    latest = get_latest_ytdlp_version()
    if latest:
        print(f"Latest yt-dlp version:  {latest}")
        if current and current.strip().lower() == latest.strip().lower():
            print("yt-dlp is up to date.")
        elif current:
            print(f"Update available: {current} -> {latest}")
    else:
        print("Could not fetch latest version (network error).")


def cmd_ytdlp_update(args):
    """ytdlp update: check + prompt + update"""
    from ytdlp_manager import check_and_prompt_cli
    exit_code = check_and_prompt_cli(auto_yes=args.yes)
    sys.exit(exit_code)


def cmd_logs_preset(args):
    """logs preset --get or --set <value>"""
    from tools.forensics import get_naming_preset, set_naming_preset, VALID_PRESETS

    if args.get_preset:
        print(get_naming_preset())
    elif args.set_preset:
        value = args.set_preset
        if value not in VALID_PRESETS:
            print(f"ERROR: invalid preset {value!r}; valid: {', '.join(VALID_PRESETS)}",
                  file=sys.stderr)
            sys.exit(2)
        set_naming_preset(value)
        print(f"Naming preset set to: {value}")
    else:
        print(f"Current preset: {get_naming_preset()}")
        print(f"Valid presets: {', '.join(VALID_PRESETS)}")


def main():
    parser = argparse.ArgumentParser(
        prog="ngks-dl",
        description="NGKsAcquisitionCore CLI (headless) — Powered by NGKsSystems",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # --- batch ---
    batch_parser = subparsers.add_parser("batch", help="Batch operations")
    batch_sub = batch_parser.add_subparsers(dest="batch_command", help="Batch sub-commands")

    # batch import
    imp = batch_sub.add_parser("import", help="Import CSV/XLSX to batch.json")
    imp_src = imp.add_mutually_exclusive_group(required=True)
    imp_src.add_argument("--csv", metavar="FILE")
    imp_src.add_argument("--xlsx", metavar="FILE")
    imp.add_argument("--out", required=True, metavar="FILE")
    imp.add_argument("--sheet", default=None)
    imp.add_argument("--dest-dir", default=None)
    imp.add_argument("--connections", type=int, default=None)
    imp.add_argument("--priority", type=int, default=None)
    imp.set_defaults(func=cmd_batch_import)

    # batch validate
    val = batch_sub.add_parser("validate", help="Validate batch.json schema")
    val.add_argument("--file", required=True, metavar="FILE")
    val.set_defaults(func=cmd_batch_validate)

    # batch run
    run = batch_sub.add_parser("run", help="Execute batch.json")
    run.add_argument("--file", required=True, metavar="FILE")
    run.add_argument("--report", default=None, metavar="FILE")
    run.add_argument("--max-concurrent", type=int, default=2)
    run.add_argument("--until", default="empty")
    run.add_argument("--stop-on-fail", action="store_true")
    run.add_argument("--verbose", action="store_true")
    run.set_defaults(func=cmd_batch_run)

    # --- version ---
    ver = subparsers.add_parser("version", help="Print version")
    ver.set_defaults(func=cmd_version)

    # --- ytdlp ---
    ytdlp_parser = subparsers.add_parser("ytdlp", help="yt-dlp lifecycle management")
    ytdlp_sub = ytdlp_parser.add_subparsers(dest="ytdlp_command",
                                             help="yt-dlp sub-commands")

    # ytdlp check
    yt_check = ytdlp_sub.add_parser("check", help="Show current + latest yt-dlp version")
    yt_check.set_defaults(func=cmd_ytdlp_check)

    # ytdlp update
    yt_update = ytdlp_sub.add_parser("update", help="Check for update and install")
    yt_update.add_argument("--yes", "-y", action="store_true",
                           help="Auto-accept update without prompting")
    yt_update.set_defaults(func=cmd_ytdlp_update)

    # --- logs ---
    logs_parser = subparsers.add_parser("logs", help="Forensic-log settings")
    logs_sub = logs_parser.add_subparsers(dest="logs_command",
                                          help="Log sub-commands")

    # logs preset
    preset_parser = logs_sub.add_parser("preset", help="Get or set the naming preset")
    preset_grp = preset_parser.add_mutually_exclusive_group()
    preset_grp.add_argument("--get", dest="get_preset", action="store_true",
                            help="Print current naming preset")
    preset_grp.add_argument("--set", dest="set_preset", metavar="PRESET",
                            help="Set naming preset (shortid|summary|host|firstfile)")
    preset_parser.set_defaults(func=cmd_logs_preset)

    args = parser.parse_args()

    if not hasattr(args, "func"):
        parser.print_help()
        sys.exit(2)

    args.func(args)


if __name__ == "__main__":
    main()
