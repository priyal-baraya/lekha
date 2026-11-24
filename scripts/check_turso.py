"""Check that Lekha can use its Turso databases, before hosting it.

    .\\.venv\\Scripts\\python.exe scripts\\check_turso.py 2

The number is how many shop databases you made (lekha-shop-1, lekha-shop-2,
...). It reads LEKHA_TURSO_URL and LEKHA_TURSO_TOKEN from the environment,
or else from .streamlit/secrets.toml, and never prints the token.

For each database it sets up Lekha's tables (safe to repeat: nothing is
deleted), then checks what Lekha relies on: foreign keys are enforced,
values of every kind come back unchanged, broken rules are refused as
IntegrityError, a transaction that fails leaves nothing behind, and an
unfinished save isn't seen by another connection. It changes no data:
those checks use a small table of their own, removed afterwards.
"""

import os
import sqlite3
import sys
import time
import tomllib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import database  # noqa: E402  (after the path above)
from ui.session import TURSO_SETTINGS, copy_turso_settings  # noqa: E402

SECRETS = Path(__file__).resolve().parent.parent / ".streamlit" / "secrets.toml"


class _Undo(Exception):
    pass


VALUES = (None, 7, -2**62, 1.5, "₹ text", b"\x00\xff")


def check(conn, open_another=None) -> list[str]:
    """What's wrong with this connection for Lekha (an empty list if nothing).

    open_another opens a second connection to the same database, to check
    that an unfinished save isn't seen by anyone else."""
    problems = []
    if conn.execute("PRAGMA foreign_keys").fetchone()[0] != 1:
        problems.append("foreign keys aren't enforced")
    if tuple(conn.execute("SELECT ?, ?, ?, ?, ?, ?", VALUES).fetchone()) != VALUES:
        problems.append("values don't come back as they went")
    # Turso has no temporary tables, so the check uses a small table of its
    # own and removes it afterwards.
    conn.executescript("DROP TABLE IF EXISTS lekha_check;\n"
                       "CREATE TABLE lekha_check (t TEXT NOT NULL UNIQUE, n INTEGER CHECK (n >= 0)) STRICT;")
    try:
        try:
            with conn:
                conn.execute("INSERT INTO lekha_check (t, n) VALUES (:t, :n)", {"t": "a", "n": 1})
                raise _Undo
        except _Undo:
            pass
        if conn.execute("SELECT COUNT(*) FROM lekha_check").fetchone()[0] != 0:
            problems.append("a failed transaction wasn't undone")
        with conn:
            conn.execute("INSERT INTO lekha_check (t, n) VALUES ('a', 1)")
        for refused in ("INSERT INTO lekha_check (t, n) VALUES ('a', 2)",      # UNIQUE
                        "INSERT INTO lekha_check (t, n) VALUES ('b', -1)",     # CHECK
                        "INSERT INTO lekha_check (t, n) VALUES ('c', 'x')"):   # wrong type
            try:
                with conn:
                    conn.execute(refused)
                problems.append(f"wasn't refused: {refused}")
            except sqlite3.IntegrityError:
                pass
        if open_another is not None:
            other = open_another()
            try:
                conn.execute("UPDATE lekha_check SET n = 9")
                if other.execute("SELECT n FROM lekha_check").fetchone()[0] != 1:
                    problems.append("an unfinished save was seen by another connection")
                conn.rollback()
            finally:
                other.close()
    finally:
        conn.executescript("DROP TABLE IF EXISTS lekha_check;")
    return problems


def milliseconds_per_query(conn, tries: int = 5) -> float:
    start = time.perf_counter()
    for _ in range(tries):
        conn.execute("SELECT 1").fetchone()
    return (time.perf_counter() - start) * 1000 / tries


def main(argv: list[str]) -> int:
    if len(argv) != 1 or not argv[0].isdigit() or int(argv[0]) < 1:
        print("Usage: python scripts/check_turso.py <number of shop databases>")
        return 2
    if SECRETS.is_file():
        copy_turso_settings(tomllib.loads(SECRETS.read_text(encoding="utf-8")), os.environ)
    missing = [name for name in TURSO_SETTINGS if not os.environ.get(name)]
    if missing:
        print(f"Set {' and '.join(missing)} first (docs/hosting.md).")
        return 2

    folder = database.data_dir()   # only used for the names; nothing is written there
    files = [folder / "accounts.db"] + [folder / "shops" / f"shop_{n}.db" for n in range(1, int(argv[0]) + 1)]
    failed = False
    for path in files:
        name = f"lekha-{database.turso.database_name(path)}"
        try:
            if path.name == "accounts.db":
                with database.connect_accounts(path):
                    pass
            else:
                database.ensure_database(path)
            with database.connect(path) as conn:
                problems = check(conn, lambda path=path: database.get_connection(path))
                speed = milliseconds_per_query(conn)
        except (sqlite3.Error, ValueError, RuntimeError) as problem:
            print(f"{name}: couldn't use it: {problem}")
            failed = True
            continue
        if problems:
            print(f"{name}: " + "; ".join(problems))
            failed = True
        else:
            print(f"{name}: ready ({speed:.0f} ms a query)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
