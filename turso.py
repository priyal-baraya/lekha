"""Turso's driver, made to behave like Python's sqlite3 for Lekha.

The hosted Lekha keeps its data in Turso (an online SQLite) instead of
files, because Streamlit Community Cloud can wipe files on any restart.
database.get_connection() uses this module when LEKHA_TURSO_URL is set
(docs/hosting.md); otherwise Lekha uses SQLite files, as always.

Turso's Python driver (libsql) is close to sqlite3 but not the same, so
this wraps it to fill the gaps Lekha relies on:

  * rows that can be read by column name: row["title"] (sqlite3.Row);
  * named parameters, such as :start, which the driver doesn't accept;
  * looping over a cursor's rows;
  * sqlite3's own errors: IntegrityError when the database refuses data,
    OperationalError for other database problems (the driver raises a
    plain ValueError for both).

Each Lekha file becomes one Turso database: accounts.db is "accounts",
shops/shop_3.db is "shop-3". LEKHA_TURSO_URL is the address with {name}
where that goes, for example libsql://lekha-{name}-yourname.turso.io.
"""

import re
import sqlite3
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path

import libsql

SHOP_FILE = re.compile(r"shop_(\d+)\.db")


# ------------------------------------------------------ where the data lives

def database_name(path: Path | str) -> str:
    """The Turso database for one of Lekha's files."""
    name = Path(path).name
    if name == "accounts.db":
        return "accounts"
    shop = SHOP_FILE.fullmatch(name)
    if shop:
        return f"shop-{int(shop.group(1))}"
    raise ValueError(f"{name} isn't one of Lekha's databases.")


def address(template: str, name: str) -> str:
    """The template's address with this database's name in it."""
    if "{name}" not in template:
        raise ValueError("LEKHA_TURSO_URL needs {name} where the database name goes.")
    if not template.startswith(("libsql://", "https://", "wss://")):
        raise ValueError("LEKHA_TURSO_URL must start with libsql:// (an encrypted connection).")
    return template.replace("{name}", name)


# ------------------------------------------------------------------ errors

@contextmanager
def _sqlite3_errors() -> Iterator[None]:
    """Turn the driver's errors into the sqlite3 ones Lekha catches."""
    try:
        yield
    except sqlite3.Error:
        raise
    except TypeError as problem:
        raise sqlite3.ProgrammingError(str(problem)) from None
    except Exception as problem:   # the driver raises ValueError, or its own Error
        message = str(problem)
        # sqlite3 calls these IntegrityError: a broken rule (UNIQUE, CHECK,
        # NOT NULL, FOREIGN KEY) or the wrong kind of value in a STRICT table.
        if any(sign in message.lower() for sign in ("constraint failed", "cannot store", "datatype mismatch")):
            raise sqlite3.IntegrityError(message) from None
        raise sqlite3.OperationalError(message) from None


# --------------------------------------------------------------- parameters

@lru_cache(maxsize=512)
def _named_to_positional(sql: str) -> tuple[str, tuple[str, ...]]:
    """Rewrite :name parameters as ?, returning the SQL and the names in order.

    Colons inside quoted text, quoted names and comments are left alone."""
    out, names = [], []
    i, n = 0, len(sql)
    while i < n:
        ch = sql[i]
        if ch in "'\"`[":
            close = "]" if ch == "[" else ch
            end = sql.find(close, i + 1)
            # A doubled quote inside quotes is an escaped quote: keep going.
            while end != -1 and close != "]" and sql.startswith(close * 2, end):
                end = sql.find(close, end + 2)
            end = n if end == -1 else end + 1
            out.append(sql[i:end])
            i = end
        elif sql.startswith("--", i):
            end = sql.find("\n", i)
            end = n if end == -1 else end
            out.append(sql[i:end])
            i = end
        elif sql.startswith("/*", i):
            end = sql.find("*/", i + 2)
            end = n if end == -1 else end + 2
            out.append(sql[i:end])
            i = end
        elif ch == ":" and i + 1 < n and (sql[i + 1].isalpha() or sql[i + 1] == "_"):
            j = i + 1
            while j < n and (sql[j].isalnum() or sql[j] == "_"):
                j += 1
            names.append(sql[i + 1:j])
            out.append("?")
            i = j
        else:
            out.append(ch)
            i += 1
    return "".join(out), tuple(names)


def _bind(sql: str, parameters) -> tuple[str, tuple]:
    if parameters is None:
        return sql, ()
    if isinstance(parameters, Mapping):
        sql, names = _named_to_positional(sql)
        missing = [name for name in names if name not in parameters]
        if missing:
            raise sqlite3.ProgrammingError(f"You did not supply a value for binding parameter :{missing[0]}.")
        return sql, tuple(parameters[name] for name in names)
    return sql, tuple(parameters)


# --------------------------------------------------------------------- rows

class Row(tuple):
    """A row read by position or by column name, like sqlite3.Row."""

    def __new__(cls, values, names: tuple[str, ...], index: dict[str, int]):
        row = super().__new__(cls, values)
        row._names = names
        row._index = index
        return row

    def __getitem__(self, key):
        if isinstance(key, str):
            try:
                return tuple.__getitem__(self, self._index[key.lower()])
            except KeyError:
                raise IndexError("No item with that key") from None
        return tuple.__getitem__(self, key)

    def keys(self) -> list[str]:
        return list(self._names)


class Cursor:
    def __init__(self, raw):
        self._raw = raw
        self._names: tuple[str, ...] = ()
        self._index: dict[str, int] = {}

    def _remember_columns(self) -> None:
        description = self._raw.description or ()
        self._names = tuple(column[0] for column in description)
        self._index = {}
        for position, name in enumerate(self._names):
            self._index.setdefault(name.lower(), position)   # the first wins, as in sqlite3

    def execute(self, sql: str, parameters=()) -> "Cursor":
        sql, values = _bind(sql, parameters)
        with _sqlite3_errors():
            self._raw.execute(sql, values)
        self._remember_columns()
        return self

    def executemany(self, sql: str, seq_of_parameters) -> "Cursor":
        rows = [_bind(sql, parameters) for parameters in seq_of_parameters]
        if rows:
            with _sqlite3_errors():
                self._raw.executemany(rows[0][0], [values for _, values in rows])
        self._remember_columns()
        return self

    def _row(self, values):
        return None if values is None else Row(values, self._names, self._index)

    def fetchone(self) -> Row | None:
        with _sqlite3_errors():
            return self._row(self._raw.fetchone())

    def fetchmany(self, size: int | None = None) -> list[Row]:
        with _sqlite3_errors():
            values = self._raw.fetchmany(size) if size is not None else self._raw.fetchmany()
        return [self._row(v) for v in values or []]   # Turso gives None for "no rows"

    def fetchall(self) -> list[Row]:
        with _sqlite3_errors():
            values = self._raw.fetchall()
        return [self._row(v) for v in values or []]   # Turso gives None for "no rows"

    def __iter__(self) -> Iterator[Row]:
        while (row := self.fetchone()) is not None:
            yield row

    @property
    def description(self):
        return self._raw.description

    @property
    def lastrowid(self):
        return self._raw.lastrowid

    @property
    def rowcount(self) -> int:
        return self._raw.rowcount

    def close(self) -> None:
        self._raw.close()


class Connection:
    """A sqlite3-style connection to a Turso database (or a local file)."""

    def __init__(self, raw):
        self._raw = raw
        # Accepted so database.get_connection can treat both kinds alike;
        # rows are always Row, which reads like sqlite3.Row.
        self.row_factory = None

    def cursor(self) -> Cursor:
        return Cursor(self._raw.cursor())

    def execute(self, sql: str, parameters=()) -> Cursor:
        return self.cursor().execute(sql, parameters)

    def executemany(self, sql: str, seq_of_parameters) -> Cursor:
        return self.cursor().executemany(sql, seq_of_parameters)

    def executescript(self, script: str) -> Cursor:
        if self.in_transaction:      # sqlite3 commits first, too
            self.commit()
        cursor = self.cursor()
        with _sqlite3_errors():
            cursor._raw.executescript(script)
        return cursor

    @property
    def in_transaction(self) -> bool:
        return bool(self._raw.in_transaction)

    def commit(self) -> None:
        with _sqlite3_errors():
            self._raw.commit()

    def rollback(self) -> None:
        with _sqlite3_errors():
            self._raw.rollback()

    def close(self) -> None:
        with _sqlite3_errors():
            self._raw.close()

    def __enter__(self) -> "Connection":
        return self

    def __exit__(self, exc_type, exc, traceback) -> bool:
        # Like sqlite3: commit if the block finished, roll back if it raised.
        if exc_type is None:
            self.commit()
        else:
            self.rollback()
        return False


def connect(target: str, auth_token: str | None = None) -> Connection:
    """Open a Turso database (an address and token) or a local file."""
    with _sqlite3_errors():
        if auth_token:
            raw = libsql.connect(database=target, auth_token=auth_token)
        else:
            raw = libsql.connect(target)
    return Connection(raw)
