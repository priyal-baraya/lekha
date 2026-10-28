"""Database connection and set-up for Lekha.

Everything else in the app talks to SQLite through get_connection(), so
the important settings (foreign keys on, rows readable by column name)
are applied in exactly one place.

Run this file directly to rebuild the local database with the fictional
sample data. This DELETES data/lekha.db first:

    .\\.venv\\Scripts\\python.exe database.py --reset-sample
"""

import sqlite3
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).parent
DB_PATH = PROJECT_DIR / "data" / "lekha.db"
SCHEMA_PATH = PROJECT_DIR / "sql" / "schema.sql"
SAMPLE_DATA_PATH = PROJECT_DIR / "data" / "sample_data.sql"


def get_connection(db_path: Path | str = DB_PATH) -> sqlite3.Connection:
    """Open a connection to the database with Lekha's settings applied.

    db_path can be ":memory:" for a temporary database that lives only in
    memory, which the tests use so they never touch the real file.
    """
    connection = sqlite3.connect(db_path)
    # Rows behave like dictionaries: row["title"] instead of row[2].
    connection.row_factory = sqlite3.Row
    # SQLite ignores foreign keys unless this is switched on for every
    # new connection. Without it, a sale could point at a book that
    # does not exist.
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def create_schema(connection: sqlite3.Connection) -> None:
    """Create the tables and indexes if they do not exist yet."""
    connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))


def load_sample_data(connection: sqlite3.Connection) -> None:
    """Insert the fictional sample dataset from data/sample_data.sql."""
    connection.executescript(SAMPLE_DATA_PATH.read_text(encoding="utf-8"))


def reset_with_sample_data(db_path: Path = DB_PATH) -> None:
    """Delete the database file and rebuild it with the sample data."""
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
        print("Deletes data/lekha.db and rebuilds it with the fictional sample data.")
