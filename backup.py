"""Back up every Lekha account and shop file, and keep the newest copies.

    LEKHA_BACKUP_DIR=/var/lib/lekha/backups python backup.py
    LEKHA_BACKUP_DIR=/var/lib/lekha/backups python backup.py --keep 14

Each run makes a new dated folder in LEKHA_BACKUP_DIR (for example
2026-11-18_021500) holding accounts.db and shops/shop_<id>.db, then
deletes all but the newest --keep folders (30 by default). The data
comes from LEKHA_DATA_DIR, the same folder Lekha uses.

It's safe to run while Lekha is open: SQLite's own backup copies each
file as it stood at one moment, with no half-saved sale in it. A plain
file copy could catch a file mid-write. Each copy is then checked with
SQLite's integrity check.

On the hosted Lekha a timer runs this every night (deploy/lekha-backup.timer).
To restore, stop Lekha, copy a backup folder's files over the data folder,
and start Lekha again (docs/hosting.md).
"""

import argparse
import os
import re
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

import database

FOLDER_NAME = re.compile(r"\d{4}-\d{2}-\d{2}_\d{6}")
SHOP_FILE = re.compile(r"shop_\d+\.db")
DEFAULT_KEEP = 30


def _files_to_copy(data: Path) -> list[Path]:
    """accounts.db and each shop file, as paths relative to the data folder."""
    files = [Path("accounts.db")]
    shops = data / "shops"
    if shops.is_dir():
        files += sorted(Path("shops") / p.name for p in shops.iterdir()
                        if p.is_file() and SHOP_FILE.fullmatch(p.name))
    return files


def _copy(source: Path, target: Path) -> None:
    """Copy one SQLite file with SQLite's backup, then check the copy."""
    # Read-only, so a file that vanished is an error instead of a new empty file.
    src = sqlite3.connect(source.resolve().as_uri() + "?mode=ro", uri=True)
    dest = sqlite3.connect(target)
    try:
        src.backup(dest)
        result = dest.execute("PRAGMA integrity_check").fetchone()[0]
        if result != "ok":
            raise sqlite3.DatabaseError(f"{target.name} failed its integrity check: {result}")
    finally:
        dest.close()
        src.close()


def back_up(data: Path, backup_root: Path, now: datetime) -> Path | None:
    """Copy the data folder's databases into a new dated folder in backup_root.

    Returns the new folder, or None when there's nothing to back up yet
    (no accounts.db). Refuses to write inside the data folder, and never
    overwrites an earlier backup.
    """
    data, backup_root = Path(data), Path(backup_root)
    if backup_root.resolve().is_relative_to(data.resolve()):
        raise ValueError("Keep backups outside the data folder.")
    if not (data / "accounts.db").is_file():
        return None

    backup_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    folder = backup_root / now.strftime("%Y-%m-%d_%H%M%S")
    folder.mkdir(mode=0o700)   # FileExistsError if this second's backup exists
    try:
        for relative in _files_to_copy(data):
            (folder / relative).parent.mkdir(exist_ok=True, mode=0o700)
            _copy(data / relative, folder / relative)
    except BaseException:
        shutil.rmtree(folder)   # no half-made backup left behind
        raise
    return folder


def prune(backup_root: Path, keep: int) -> list[Path]:
    """Delete all but the newest `keep` backup folders. Returns those deleted.

    Only folders named like a backup are touched."""
    if keep < 1:
        raise ValueError("Keep at least one backup.")
    backups = sorted(p for p in Path(backup_root).iterdir()
                     if p.is_dir() and FOLDER_NAME.fullmatch(p.name))
    old = backups[:-keep]
    for folder in old:
        shutil.rmtree(folder)
    return old


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Back up Lekha's accounts and shops.")
    parser.add_argument("--keep", type=int, default=DEFAULT_KEEP,
                        help=f"how many backups to keep (default {DEFAULT_KEEP})")
    args = parser.parse_args(argv)
    if args.keep < 1:
        parser.error("--keep must be at least 1")

    target = os.environ.get("LEKHA_BACKUP_DIR")
    if not target:
        print("Set LEKHA_BACKUP_DIR to the folder for backups.", file=sys.stderr)
        return 2
    data = database.data_dir()
    folder = back_up(data, Path(target), datetime.now())
    if folder is None:
        print(f"Nothing to back up yet: there's no accounts.db in {data}.")
        return 0
    removed = prune(Path(target), args.keep)
    print(f"Backed up to {folder}" + (f"; removed {len(removed)} older" if removed else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
