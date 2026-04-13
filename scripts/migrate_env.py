#!/usr/bin/env python3
"""
migrate_env — Append missing keys from .env.example to .env.

Compares .env against .env.example and appends any missing keys
with their default values and surrounding comments.

Usage:
    python scripts/migrate_env.py          # preview (dry run)
    python scripts/migrate_env.py --apply  # write changes to .env
"""

import sys
from pathlib import Path

from dotenv import dotenv_values

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = PROJECT_ROOT / ".env"
ENV_EXAMPLE = PROJECT_ROOT / ".env.example"


def extract_missing_blocks(existing_keys: set[str]) -> str:
    """Return lines from .env.example for keys not in existing_keys.

    Preserves section headers and comments that precede missing keys.
    Uses raw line parsing here because we need to preserve comments and
    formatting that dotenv_values intentionally strips.
    """
    lines = ENV_EXAMPLE.read_text().splitlines()
    pending_comments: list[str] = []
    missing_lines: list[str] = []

    for line in lines:
        stripped = line.strip()

        if not stripped or stripped.startswith("#"):
            pending_comments.append(line)
            continue

        if "=" in stripped:
            key, _, _ = stripped.partition("=")
            if key.strip() not in existing_keys:
                missing_lines.extend(pending_comments)
                missing_lines.append(line)

        pending_comments = []

    return "\n".join(missing_lines)


def main() -> int:
    if not ENV_EXAMPLE.exists():
        print("ERROR: .env.example not found")
        return 1

    if not ENV_FILE.exists():
        print(".env does not exist — copying .env.example as .env")
        if "--apply" in sys.argv:
            ENV_FILE.write_text(ENV_EXAMPLE.read_text())
            print("Done.")
        else:
            print("(dry run — use --apply to create .env)")
        return 0

    existing_keys = set(dotenv_values(ENV_FILE).keys())
    example_keys = set(dotenv_values(ENV_EXAMPLE).keys())
    missing_keys = example_keys - existing_keys

    if not missing_keys:
        print("No missing keys — .env is up to date.")
        return 0

    print(f"Found {len(missing_keys)} missing key(s): {', '.join(sorted(missing_keys))}")

    block = extract_missing_blocks(existing_keys)
    print()
    print("Will append to .env:")
    print("─" * 60)
    print(block)
    print("─" * 60)

    if "--apply" in sys.argv:
        current = ENV_FILE.read_text()
        separator = "\n" if current.endswith("\n") else "\n\n"
        ENV_FILE.write_text(current + separator + block + "\n")
        print("\nApplied. Review your .env and update values as needed.")
    else:
        print("\n(dry run — use --apply to write changes)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
