"""Delete GraphMTG's local data. Used by `make reset` / `make reset-cache`.

    python scripts/reset_data.py          # collections + cache (asks first)
    python scripts/reset_data.py --cache  # cache only (re-downloads as needed)
    python scripts/reset_data.py --yes    # skip the confirmation

Folders come from mtgcv itself, so MTGCV_DATA_DIR / MTGCV_CACHE_DIR overrides are honored.
"""

import argparse
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mtgcv.cache import default_cache_dir  # noqa: E402
from mtgcv.store import default_data_dir  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--cache", action="store_true", help="only delete the download cache")
    p.add_argument("--yes", "-y", action="store_true", help="don't ask for confirmation")
    args = p.parse_args()

    targets = [("download cache", default_cache_dir())]
    if not args.cache:
        targets.insert(0, ("collections, boards and graph layouts", default_data_dir()))
    targets = [(label, d) for label, d in targets if d.exists()]
    if not targets:
        print("Nothing to delete: no local data found.")
        return 0

    print("This will delete:")
    for label, d in targets:
        print(f"  {d}  ({label})")
    if not args.yes and not args.cache:
        try:
            answer = input("Type 'yes' to continue: ")
        except EOFError:
            answer = ""
        if answer.strip().lstrip("﻿").lower() != "yes":
            print("Cancelled.")
            return 1

    for _, d in targets:
        try:
            shutil.rmtree(d)
        except PermissionError:
            print(f"Could not delete {d}: a file is in use. Close GraphMTG / `mtgcv serve` and try again.")
            return 1
        print(f"Deleted {d}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
