"""Run SQL against Lekha's database and print the results as tables.

Usage (from the project folder):
    .\\.venv\\Scripts\\python.exe query.py "SELECT title, genre FROM books"
    .\\.venv\\Scripts\\python.exe query.py sql\\01_first_queries.sql

A .sql file can hold several queries. Each one is printed with the
comment lines written above it. This is a learning tool: it reads the
database but should only be given SELECT queries.
"""

import sqlite3
import sys
from pathlib import Path

import pandas as pd

from database import DB_PATH, get_connection


def split_statements(sql_text: str) -> list[str]:
    """Split text into complete SQL statements.

    sqlite3.complete_statement() knows SQL's rules, so a semicolon inside
    a quoted string or a comment doesn't end a statement by mistake.
    """
    statements, buffer = [], ""
    for line in sql_text.splitlines(keepends=True):
        buffer += line
        if sqlite3.complete_statement(buffer):
            statements.append(buffer.strip())
            buffer = ""
    return statements


def main() -> None:
    if len(sys.argv) != 2:
        print(__doc__)
        return
    if not DB_PATH.exists():
        print("No database yet. Create it first with:")
        print("    .\\.venv\\Scripts\\python.exe database.py --reset-sample")
        return

    argument = sys.argv[1]
    sql_text = Path(argument).read_text(encoding="utf-8") if argument.endswith(".sql") else argument
    statements = split_statements(sql_text) or [sql_text]

    pd.set_option("display.width", 120)
    connection = get_connection()
    try:
        for statement in statements:
            # pandas runs the query and lays the rows out as a table.
            table = pd.read_sql_query(statement, connection)
            print(statement)
            print()
            print(table.to_string(index=False))
            print("\n" + "-" * 72 + "\n")
    finally:
        connection.close()


if __name__ == "__main__":
    main()
