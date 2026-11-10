"""Run SQL against Lekha's database and print the results as tables.

Usage (from the project folder):
    .\\.venv\\Scripts\\python.exe query.py "SELECT title, genre FROM books"
    .\\.venv\\Scripts\\python.exe query.py --sample sql\\01_first_queries.sql

Without --sample it reads your real shop's database. With --sample it
builds the FICTIONAL sample data in memory for this run only (the data
the practice queries' expected answers refer to); nothing is saved.

A .sql file can hold several queries. Each one is printed with the
comment lines written above it. This is a learning tool: it reads the
database but should only be given SELECT queries.
"""

import sqlite3
import sys
from pathlib import Path

import pandas as pd

from database import create_schema, database_path, get_connection, load_sample_data


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
    arguments = sys.argv[1:]
    sample = "--sample" in arguments
    arguments = [argument for argument in arguments if argument != "--sample"]
    if len(arguments) != 1:
        print(__doc__)
        return
    if not sample and not database_path().exists():
        print("No database yet. Start Lekha once, or create an empty shop with:")
        print("    .\\.venv\\Scripts\\python.exe database.py --reset")
        return

    argument = arguments[0]
    sql_text = Path(argument).read_text(encoding="utf-8") if argument.endswith(".sql") else argument
    statements = split_statements(sql_text) or [sql_text]

    pd.set_option("display.width", 120)
    if sample:
        connection = get_connection(":memory:")   # lives only for this run
        create_schema(connection)
        load_sample_data(connection)
    else:
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
