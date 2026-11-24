"""Lekha's connection to Turso, made to behave like Python's sqlite3.

The hosted Lekha keeps its data in Turso (an online SQLite) instead of
files, because Streamlit Community Cloud can wipe files on any restart.
database.get_connection() uses this module when LEKHA_TURSO_URL is set
(docs/hosting.md); otherwise Lekha uses SQLite files, as always.

It talks to Turso's HTTP API directly (Hrana over HTTP, version 2): each
request is a "pipeline" of statements, sent as JSON. That's faster than
Turso's own Python driver, which was measured taking two round trips a
query and setting up a new secure connection every time:

  * one round trip per query, and a transaction's BEGIN travels with its
    first statement;
  * one secure connection per Turso database, kept open and shared by
    every page (a pool), instead of a new one each time.

It fills the gaps between Turso and sqlite3 that Lekha relies on: rows
read by column name (row["title"]), :named parameters, sqlite3's own
errors (IntegrityError when the database refuses data), and sqlite3's
transactions (an INSERT, UPDATE or DELETE starts one; commit() or a
`with conn:` block ends it).

Each Lekha file becomes one Turso database: accounts.db is "accounts",
shops/shop_3.db is "shop-3". LEKHA_TURSO_URL is the address with {name}
where that goes, for example libsql://lekha-{name}-yourname.turso.io.
"""

import base64
import http.client
import json
import logging
import re
import sqlite3
import ssl
import threading
import time
from collections.abc import Iterator, Mapping
from functools import lru_cache
from pathlib import Path

SHOP_FILE = re.compile(r"shop_(\d+)\.db")
TIMEOUT_SECONDS = 15
IDLE_SECONDS = 20              # an unused connection older than this is replaced
MAX_RESPONSE_BYTES = 32_000_000
STARTS_TRANSACTION = {"INSERT", "UPDATE", "DELETE", "REPLACE"}   # as sqlite3 does
READ_ONLY = {"SELECT", "PRAGMA", "EXPLAIN", "VALUES"}

log = logging.getLogger(__name__)


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
    if not template.startswith(("libsql://", "https://")):
        raise ValueError("LEKHA_TURSO_URL must start with libsql:// (an encrypted connection).")
    return template.replace("{name}", name)


def _host(url: str) -> str:
    host = url.split("://", 1)[1].split("/", 1)[0]
    if not re.fullmatch(r"[A-Za-z0-9.-]+", host):
        raise ValueError("LEKHA_TURSO_URL has an unexpected address in it.")
    return host


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


@lru_cache(maxsize=512)
def _first_word(sql: str) -> str:
    """The statement's first keyword, after any comments: sqlite3 decides
    from it whether a transaction starts."""
    text = re.sub(r"^(\s+|--[^\n]*\n?|/\*.*?\*/)+", "", sql, flags=re.DOTALL)
    match = re.match(r"[A-Za-z]+", text)
    return match.group(0).upper() if match else ""


# ------------------------------------------------------------------ values

def _encode(value) -> dict:
    if value is None:
        return {"type": "null"}
    if isinstance(value, bool | int):
        return {"type": "integer", "value": str(int(value))}
    if isinstance(value, float):
        return {"type": "float", "value": value}
    if isinstance(value, str):
        return {"type": "text", "value": value}
    if isinstance(value, bytes | bytearray | memoryview):
        return {"type": "blob", "base64": base64.b64encode(bytes(value)).decode("ascii")}
    raise sqlite3.ProgrammingError(f"Error binding parameter: type {type(value).__name__!r} is not supported")


def _decode(value: dict):
    kind = value.get("type")
    if kind == "null":
        return None
    if kind == "integer":
        return int(value["value"])
    if kind == "float":
        return float(value["value"])
    if kind == "text":
        return value["value"]
    if kind == "blob":
        text = value["base64"]
        return base64.b64decode(text + "=" * (-len(text) % 4))   # Turso leaves out the padding
    raise sqlite3.OperationalError(f"Turso sent a value of an unknown type: {kind!r}")


def _statement(sql: str, values: tuple) -> dict:
    return {"type": "execute", "stmt": {"sql": sql, "args": [_encode(v) for v in values]}}


def _raise_for(result: dict) -> None:
    """Raise sqlite3's error for a failed statement, as sqlite3 would."""
    if result.get("type") == "ok":
        return
    error = result.get("error") or {}
    message = str(error.get("message", "Turso refused the statement")).removeprefix("SQLite error: ")
    if str(error.get("code", "")).startswith("SQLITE_CONSTRAINT"):
        # A broken rule (UNIQUE, CHECK, NOT NULL, FOREIGN KEY) or the wrong
        # kind of value in a STRICT table.
        raise sqlite3.IntegrityError(message)
    raise sqlite3.OperationalError(message)


# ----------------------------------------------------------------- network

class _Stats(threading.local):
    """Requests to Turso made by this page run (each page runs in its own thread)."""
    requests = 0
    seconds = 0.0


stats = _Stats()


def reset_stats() -> None:
    stats.requests = 0
    stats.seconds = 0.0


def page_summary(page: str, total_seconds: float) -> str:
    """One line for the log: how much of a page's time was spent waiting for Turso."""
    return f"{page}: {stats.requests} requests to Turso, {stats.seconds:.2f} s of {total_seconds:.2f} s"


class _Pool:
    """Open HTTPS connections to Turso, kept for the next request.

    Setting up a secure connection takes several round trips, so one is
    reused for as long as it stays open. A connection is used by one
    request at a time; requests at the same moment get one each."""

    def __init__(self):
        self._idle: dict[str, list[tuple[http.client.HTTPSConnection, float]]] = {}
        self._lock = threading.Lock()
        self._tls = ssl.create_default_context()        # checks Turso's certificate

    def take(self, host: str) -> tuple[http.client.HTTPConnection, bool]:
        with self._lock:
            idle = self._idle.setdefault(host, [])
            while idle:
                conn, last_used = idle.pop()
                if time.monotonic() - last_used < IDLE_SECONDS:
                    return conn, True
                conn.close()
        return self.new(host), False

    def new(self, host: str) -> http.client.HTTPConnection:
        return http.client.HTTPSConnection(host, timeout=TIMEOUT_SECONDS, context=self._tls)

    def give_back(self, host: str, conn: http.client.HTTPConnection) -> None:
        with self._lock:
            self._idle.setdefault(host, []).append((conn, time.monotonic()))

    def clear(self) -> None:
        with self._lock:
            for idle in self._idle.values():
                for conn, _ in idle:
                    conn.close()
            self._idle.clear()


_pool = _Pool()
_STALE = (http.client.RemoteDisconnected, http.client.CannotSendRequest, ConnectionResetError,
          ConnectionAbortedError, BrokenPipeError)


class HttpTransport:
    """Sends pipelines to one Turso database over HTTPS."""

    def __init__(self, url: str, token: str, pool: _Pool = _pool):
        if not token:
            raise ValueError("A Turso token is needed.")
        self.host = _host(url)
        self._headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        self._pool = pool

    def pipeline(self, body: dict) -> dict:
        data = json.dumps(body).encode("utf-8")
        # A stale reused connection fails before Turso sees the request; that
        # is only retried when the request can't have changed anything.
        retry_ok = body.get("baton") is None and all(
            r["type"] != "execute" or _first_word(r["stmt"]["sql"]) in READ_ONLY
            for r in body["requests"] if r["type"] in ("execute", "sequence"))
        if any(r["type"] == "sequence" for r in body["requests"]):
            retry_ok = False
        started = time.perf_counter()
        try:
            conn, reused = self._pool.take(self.host)
            try:
                status, raw = self._send(conn, data)
            except _STALE:
                conn.close()
                if not (reused and retry_ok):
                    raise
                conn = self._pool.new(self.host)
                status, raw = self._send(conn, data)
            except BaseException:
                conn.close()
                raise
        except (OSError, http.client.HTTPException) as problem:
            raise sqlite3.OperationalError(f"Couldn't reach Turso ({type(problem).__name__}).") from None
        finally:
            stats.requests += 1
            stats.seconds += time.perf_counter() - started
        if status != 200:
            conn.close()
            raise sqlite3.OperationalError(f"Turso refused the request (HTTP {status}): {_error_text(raw)}")
        self._pool.give_back(self.host, conn)
        try:
            return json.loads(raw)
        except ValueError:
            raise sqlite3.OperationalError("Turso sent an answer that isn't JSON.") from None

    def _send(self, conn: http.client.HTTPConnection, data: bytes) -> tuple[int, bytes]:
        conn.request("POST", "/v2/pipeline", body=data, headers=self._headers)
        response = conn.getresponse()
        raw = response.read(MAX_RESPONSE_BYTES + 1)
        if len(raw) > MAX_RESPONSE_BYTES:
            conn.close()
            raise sqlite3.OperationalError("Turso's answer was too large.")
        return response.status, raw


def _error_text(raw: bytes) -> str:
    """Turso's own short explanation, never anything we sent (so never the token)."""
    try:
        text = str(json.loads(raw).get("error", ""))
    except (ValueError, AttributeError):
        text = ""
    return text[:200] or "no details"


# -------------------------------------------------------------------- rows

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
    def __init__(self, connection: "Connection"):
        self._connection = connection
        self._rows: list[Row] = []
        self._position = 0
        self.description = None
        self.lastrowid = None
        self.rowcount = -1
        self.arraysize = 1

    def _take(self, result: dict) -> None:
        cols = result.get("cols") or []
        names = tuple(str(col.get("name")) for col in cols)
        index: dict[str, int] = {}
        for position, name in enumerate(names):
            index.setdefault(name.lower(), position)      # the first wins, as in sqlite3
        self._rows = [Row([_decode(v) for v in row], names, index) for row in result.get("rows") or []]
        self._position = 0
        self.description = tuple((name, None, None, None, None, None, None) for name in names) or None
        rowid = result.get("last_insert_rowid")
        self.lastrowid = int(rowid) if rowid is not None else None
        self.rowcount = -1 if names else int(result.get("affected_row_count") or 0)

    def execute(self, sql: str, parameters=()) -> "Cursor":
        sql, values = _bind(sql, parameters)
        self._take(self._connection._run([(sql, values)])[-1])
        return self

    def executemany(self, sql: str, seq_of_parameters) -> "Cursor":
        statements = [_bind(sql, parameters) for parameters in seq_of_parameters]
        if statements:
            results = self._connection._run(statements)
            self._take(results[-1])
            self.rowcount = sum(int(r.get("affected_row_count") or 0) for r in results)
        return self

    def fetchone(self) -> Row | None:
        if self._position >= len(self._rows):
            return None
        self._position += 1
        return self._rows[self._position - 1]

    def fetchmany(self, size: int | None = None) -> list[Row]:
        size = self.arraysize if size is None else size
        rows = self._rows[self._position:self._position + size]
        self._position += len(rows)
        return rows

    def fetchall(self) -> list[Row]:
        rows = self._rows[self._position:]
        self._position = len(self._rows)
        return rows

    def __iter__(self) -> Iterator[Row]:
        while (row := self.fetchone()) is not None:
            yield row

    def close(self) -> None:
        self._rows = []


class Connection:
    """A sqlite3-style connection to one Turso database.

    A "stream" on Turso is a run of requests sharing one server-side
    connection, kept open by sending back its baton. Outside a transaction
    each request closes its stream (nothing is left open); inside one, the
    stream stays open until COMMIT or ROLLBACK."""

    def __init__(self, transport):
        self._transport = transport
        self._baton: str | None = None
        self._in_transaction = False
        # Accepted so database.get_connection can treat both kinds alike;
        # rows are always Row, which reads like sqlite3.Row.
        self.row_factory = None

    @property
    def in_transaction(self) -> bool:
        return self._in_transaction

    def _send(self, requests: list[dict], keep_open: bool) -> list[dict]:
        body = {"baton": self._baton,
                "requests": requests + [{"type": "get_autocommit"}] + ([] if keep_open else [{"type": "close"}])}
        response = self._transport.pipeline(body)
        results = response.get("results") or []
        if len(results) < len(requests) + 1:
            raise sqlite3.OperationalError("Turso's answer was incomplete.")
        self._baton = response.get("baton") if keep_open else None
        state = results[len(requests)]
        if state.get("type") == "ok":
            self._in_transaction = not state["response"].get("is_autocommit", True)
        if not keep_open:
            self._in_transaction = False
        return results[:len(requests)]

    def _run(self, statements: list[tuple[str, tuple]]) -> list[dict]:
        """Send statements in one request, starting a transaction first when
        sqlite3 would (before INSERT, UPDATE, DELETE or REPLACE)."""
        first = _first_word(statements[0][0])
        begins = not self._in_transaction and first in STARTS_TRANSACTION
        ends = first in {"COMMIT", "END"} or (first == "ROLLBACK" and " TO " not in statements[0][0].upper())
        keep_open = (self._in_transaction or begins or first in {"BEGIN", "SAVEPOINT"}) and not ends
        requests = ([_statement("BEGIN", ())] if begins else []) + [_statement(s, v) for s, v in statements]
        results = self._send(requests, keep_open)
        for result in results:
            _raise_for(result)
        return [r["response"]["result"] for r in results[1 if begins else 0:]]

    def cursor(self) -> Cursor:
        return Cursor(self)

    def execute(self, sql: str, parameters=()) -> Cursor:
        return self.cursor().execute(sql, parameters)

    def executemany(self, sql: str, seq_of_parameters) -> Cursor:
        return self.cursor().executemany(sql, seq_of_parameters)

    def executescript(self, script: str) -> Cursor:
        """Run several statements in one request. Like sqlite3, it commits
        a pending transaction first. A script that begins a transaction
        must also end it (Lekha's migrations do)."""
        if self._in_transaction:
            self.commit()
        _raise_for(self._send([{"type": "sequence", "sql": script}], keep_open=False)[0])
        return self.cursor()

    def commit(self) -> None:
        if self._in_transaction:
            _raise_for(self._send([_statement("COMMIT", ())], keep_open=False)[0])

    def rollback(self) -> None:
        if self._in_transaction:
            _raise_for(self._send([_statement("ROLLBACK", ())], keep_open=False)[0])

    def close(self) -> None:
        """Close the stream if one is open; like sqlite3, an uncommitted
        transaction is discarded."""
        if self._baton is not None:
            try:
                self._send([], keep_open=False)
            except sqlite3.Error:
                log.info("Couldn't close a Turso stream; Turso ends it by itself")
            self._baton = None
            self._in_transaction = False

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
    """Open a Turso database: its address and a token."""
    return Connection(HttpTransport(target, auth_token or ""))
