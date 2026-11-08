"""Database connection and set-up for Lekha.

Everything else in the app talks to SQLite through get_connection(), so
the important settings (foreign keys on, rows readable by column name)
are applied in exactly one place.

Where the database lives: data/lekha.db by default. Setting the
environment variable LEKHA_DB_PATH points Lekha at a different file
instead (the page tests and the demo dataset use this), without
changing any code.

Run this file directly to rebuild the database with the fictional
sample data. This DELETES the database file first:

    .\\.venv\\Scripts\\python.exe database.py --reset-sample
"""

import os
import sqlite3
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

PROJECT_DIR = Path(__file__).parent
DEFAULT_DB_PATH = PROJECT_DIR / "data" / "lekha.db"
SCHEMA_PATH = PROJECT_DIR / "sql" / "schema.sql"
MIGRATIONS_DIR = PROJECT_DIR / "sql" / "migrations"
SAMPLE_DATA_PATH = PROJECT_DIR / "data" / "sample_data.sql"


def database_path() -> Path:
    """The database file to use: LEKHA_DB_PATH if it is set, else data/lekha.db.

    Read on every call (not once at start-up), so a test can point Lekha
    at a temporary file just by setting the variable.
    """
    configured = os.environ.get("LEKHA_DB_PATH")
    return Path(configured) if configured else DEFAULT_DB_PATH


def get_connection(db_path: Path | str | None = None) -> sqlite3.Connection:
    """Open a connection to the database with Lekha's settings applied.

    db_path defaults to database_path(). It can be ":memory:" for a
    temporary database that lives only in memory, which the rule tests
    use so they never touch a real file.
    """
    connection = sqlite3.connect(db_path or database_path())
    # Rows behave like dictionaries: row["title"] instead of row[2].
    connection.row_factory = sqlite3.Row
    # SQLite ignores foreign keys unless this is switched on for every
    # new connection. Without it, a sale could point at a book that
    # does not exist.
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


@contextmanager
def connect(db_path: Path | str | None = None) -> Iterator[sqlite3.Connection]:
    """Open a connection for a block of code and always close it afterwards.

        with connect() as conn:
            ...use conn...

    (sqlite3's own `with conn:` only commits or rolls back; it does not
    close the connection. This one closes it.)
    """
    conn = get_connection(db_path)
    try:
        yield conn
    finally:
        conn.close()


def create_schema(connection: sqlite3.Connection) -> None:
    """Create the tables and indexes if they do not exist yet, then bring
    the database up to date with any migrations it hasn't had."""
    connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    apply_migrations(connection)


def schema_version(connection: sqlite3.Connection) -> int:
    """How many migrations this database has had.

    SQLite keeps a spare whole number in every database file's header,
    `PRAGMA user_version` (0 in a new file). Lekha uses it to remember
    which numbered migration ran last.
    """
    return connection.execute("PRAGMA user_version").fetchone()[0]


def apply_migrations(connection: sqlite3.Connection) -> list[int]:
    """Run, in order, every sql/migrations/NNN_*.sql newer than the database.

    Each migration and its version number are saved in one transaction,
    so a failure leaves the database exactly as it was. Returns the
    numbers of the migrations applied (usually none).
    """
    applied = []
    for path in sorted(MIGRATIONS_DIR.glob("[0-9][0-9][0-9]_*.sql")):
        number = int(path.name[:3])
        if number <= schema_version(connection):
            continue
        connection.executescript(
            "BEGIN;\n"
            + path.read_text(encoding="utf-8")
            + f"\nPRAGMA user_version = {number};\nCOMMIT;"
        )
        applied.append(number)
    return applied


def ensure_database(db_path: Path | str | None = None) -> None:
    """Make sure the database file and all its tables exist.

    Safe to call on every page load: every CREATE uses IF NOT EXISTS, so
    existing data is untouched and new tables (like stock_adjustments)
    are added to older databases.
    """
    with connect(db_path) as conn:
        create_schema(conn)


def load_sample_data(connection: sqlite3.Connection) -> None:
    """Insert the fictional sample dataset from data/sample_data.sql."""
    connection.executescript(SAMPLE_DATA_PATH.read_text(encoding="utf-8"))


def reset_with_sample_data(db_path: Path | None = None) -> None:
    """Delete the database file and rebuild it with the sample data."""
    db_path = Path(db_path or database_path())
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db_path.unlink(missing_ok=True)
    connection = get_connection(db_path)
    try:
        create_schema(connection)
        load_sample_data(connection)
        counts = {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("books", "sales", "sale_items")
        }
    finally:
        connection.close()
    print(f"Rebuilt {db_path} with fictional sample data:")
    for table, count in counts.items():
        print(f"  {table}: {count} rows")


if __name__ == "__main__":
    if sys.argv[1:] == ["--reset-sample"]:
        reset_with_sample_data()
    else:
        print("Usage: python database.py --reset-sample")
        print(f"Deletes {database_path()} and rebuilds it with the fictional sample data.")
