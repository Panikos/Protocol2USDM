#!/usr/bin/env python3
"""Propagate VERSION from core/constants.py to all documentation files.

Single source of truth: core.constants.VERSION (e.g. "8.0.0")
Docs use shortened MAJOR.MINOR (e.g. "8.0").
CHANGELOG uses full semver "[8.0.0]".

Usage:
    python scripts/propagate_version.py          # dry-run (show changes)
    python scripts/propagate_version.py --apply   # write changes to disk
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Resolve project root (parent of scripts/)
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.constants import VERSION  # noqa: E402

MAJOR_MINOR = ".".join(VERSION.split(".")[:2])  # e.g. "8.0"

# ---------------------------------------------------------------------------
# Replacement rules: (file, pattern, replacement)
# Each pattern uses a regex with a capture group for the surrounding text.
# ---------------------------------------------------------------------------
RULES: list[tuple[str, str, str]] = [
    # USER_GUIDE.md — header version
    (
        "USER_GUIDE.md",
        r"(\*\*Version:\*\*\s*)\d+\.\d+",
        rf"\g<1>{MAJOR_MINOR}",
    ),
    # USER_GUIDE.md — What's New banner
    (
        "USER_GUIDE.md",
        r"(What's New in v)\d+\.\d+",
        rf"\g<1>{MAJOR_MINOR}",
    ),
    # QUICK_REFERENCE.md — header version badge
    (
        "QUICK_REFERENCE.md",
        r"(\*\*v)\d+\.\d+(\*\*)",
        rf"\g<1>{MAJOR_MINOR}\g<2>",
    ),
    # QUICK_REFERENCE.md — footer version
    (
        "QUICK_REFERENCE.md",
        r"(\*\*Version:\*\*\s*)\d+\.\d+",
        rf"\g<1>{MAJOR_MINOR}",
    ),
    # README.md — What's New heading
    (
        "README.md",
        r"(## What's New in v)\d+\.\d+",
        rf"\g<1>{MAJOR_MINOR}",
    ),
]


def propagate(apply: bool = False) -> int:
    """Run all replacement rules. Returns number of files changed."""
    changed = 0
    for rel_path, pattern, replacement in RULES:
        filepath = ROOT / rel_path
        if not filepath.exists():
            print(f"  SKIP {rel_path} (not found)")
            continue

        original = filepath.read_text(encoding="utf-8")
        updated = re.sub(pattern, replacement, original)

        if original == updated:
            print(f"  OK   {rel_path} (already up to date)")
            continue

        # Show what changed
        changed += 1
        # Find the lines that differ
        orig_lines = original.splitlines()
        upd_lines = updated.splitlines()
        for i, (o, u) in enumerate(zip(orig_lines, upd_lines)):
            if o != u:
                print(f"  PATCH {rel_path}:{i+1}")
                print(f"    - {o.strip()}")
                print(f"    + {u.strip()}")

        if apply:
            filepath.write_text(updated, encoding="utf-8")
            print(f"  WROTE {rel_path}")

    return changed


def main() -> None:
    parser = argparse.ArgumentParser(description="Propagate VERSION to docs")
    parser.add_argument(
        "--apply", action="store_true", help="Write changes (default: dry-run)"
    )
    args = parser.parse_args()

    print(f"VERSION = {VERSION} (MAJOR.MINOR = {MAJOR_MINOR})")
    print(f"Mode: {'APPLY' if args.apply else 'DRY-RUN'}\n")

    changed = propagate(apply=args.apply)

    print(f"\n{'Applied' if args.apply else 'Would change'} {changed} file(s).")
    if not args.apply and changed > 0:
        print("Run with --apply to write changes.")


if __name__ == "__main__":
    main()
