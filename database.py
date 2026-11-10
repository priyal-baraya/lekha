"""Database connection and set-up for Lekha.

Everything else in the app talks to SQLite through get_connection(), so
the important settings (foreign keys on, rows readable by column name)
are applied in exactly one place.

Where the database lives: data/lekha.db by default. Setting the
environment variable LEKHA_DB_PATH points Lekha at a different file
instead (the page tests and the demo dataset use this), without
changing any code.

The fictional sample data in data/sample_data.sql is used only by the
automated tests (and by `query.py --sample`); it is never put in the
app's database.

Run this file directly to start again with an EMPTY shop. This DELETES
the database file, and everything in it, first:

    .\\.venv\\Scripts\\python.exe database.py --reset
"""

import os
import sqlite3
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path

PROJECT_DIR = Path(__file__).parent
DEFAULT_DB_PATH = PROJECT_DIR / "data" / "lekha.db"
SCHEMA_PATH = PROJECT_DIR / "sql" / "schema.sql"
ACCOUNTS_SCHEMA_PATH = PROJECT_DIR / "sql" / "accounts_schema.sql"
MIGRATIONS_DIR = PROJECT_DIR / "sql" / "migrations"
SAMPLE_DATA_PATH = PROJECT_DIR / "data" / "sample_data.sql"

# The shop database for the page run happening right now. Streamlit serves
# every visitor from one Python process, so an ordinary global variable
# would be shared by everyone using the app at once. A ContextVar belongs
# to the current run only: app.py sets it to the signed-in person's shop
# before each page runs, and other visitors' runs never see it.
_current_shop_db: ContextVar[Path | None] = ContextVar("lekha_current_shop_db", default=None)


def data_dir() -> Path:
    """Where accounts and shop files live: LEKHA_DATA_DIR, else data/."""
    configured = os.environ.get("LEKHA_DATA_DIR")
    return Path(configured) if configured else PROJECT_DIR / "data"


def accounts_path() -> Path:
    return data_dir() / "accounts.db"


def shop_path(shop_id: int) -> Path:
    """Each shop's books and sales live in their own file."""
    return data_dir() / "shops" / f"shop_{int(shop_id)}.db"


def use_database(path: Path | None) -> None:
    """Point this page run at one shop's database (None clears it)."""
    _current_shop_db.set(Path(path) if path else None)


def database_path() -> Path:
    """The shop database to use, in this order:

    1. the signed-in person's shop, set by app.py with use_database();
    2. LEKHA_DB_PATH, if set (the page tests use this);
    3. data/lekha.db (command-line tools such as query.py).

    Read on every call (not once at start-up).
    """
    current = _current_shop_db.get()
    if current is not None:
        return current
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


@contextmanager
def connect_accounts(path: Path | str | None = None) -> Iterator[sqlite3.Connection]:
    """Open the accounts database (creating its tables if needed) and close it afterwards."""
    path = Path(path) if path else accounts_path()
    if str(path) != ":memory:":
        path.parent.mkdir(parents=True, exist_ok=True)
    conn = get_connection(path)
    try:
        conn.executescript(ACCOUNTS_SCHEMA_PATH.read_text(encoding="utf-8"))
        yield conn
    finally:
        conn.close()


def ensure_shop_database(shop_id: int) -> Path:
    """Create a shop's database file and tables if they don't exist yet."""
    path = shop_path(shop_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    ensure_database(path)
    return path


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
    """Insert the fictional sample dataset from data/sample_data.sql.

    For the automated tests and query.py --sample only, never the app's own
    database: Lekha shows only real books and recorded sales."""
    connection.executescript(SAMPLE_DATA_PATH.read_text(encoding="utf-8"))


def reset_empty(db_path: Path | None = None) -> None:
    """Delete the database file and create an empty one: an empty shop."""
    db_path = Path(db_path or database_path())
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db_path.unlink(missing_ok=True)
    with connect(db_path) as conn:
        create_schema(conn)
    print(f"Created an empty shop in {db_path}.")


def reset_with_sample_data(db_path: Path | None = None) -> None:
    """Delete the database file and rebuild it with the FICTIONAL sample
    data. Used by the page tests on their own temporary files only."""
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
    if sys.argv[1:] == ["--reset"]:
        reset_empty()
    else:
        print("Usage: python database.py --reset")
        print(f"Deletes {database_path()} and everything in it, and starts an empty shop.")
