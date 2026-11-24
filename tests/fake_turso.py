"""A stand-in for Turso's HTTP API, for the tests.

turso.py talks to Turso by sending JSON "pipelines" over HTTPS
(Hrana over HTTP, version 2). This answers the same JSON, with Python's
sqlite3 on a local file or in memory, so the whole suite can run through
turso.py without the internet (LEKHA_TEST_THROUGH_TURSO=1, see conftest.py).

It copies what was seen on real Turso (scripts/check_turso.py checks the
real thing):
  * every broken rule, including a wrong type in a STRICT table, is an
    error with the code SQLITE_CONSTRAINT;
  * PRAGMA user_version = N and temporary tables are refused;
  * foreign keys are always on;
  * a stream (a run of requests sharing one connection) is kept open by
    sending back its "baton"; closing it rolls back an open transaction.

Every request is passed through json.dumps/json.loads first, so values
must be encoded exactly as Turso expects.
"""

import base64
import itertools
import json
import re
import sqlite3

REFUSED = re.compile(r"^\s*(PRAGMA\s+user_version\s*=|CREATE\s+TEMP)", re.IGNORECASE)
_batons = itertools.count(1)


def _decode(value: dict):
    kind = value["type"]
    if kind == "null":
        return None
    if kind == "integer":
        assert isinstance(value["value"], str), "integers travel as text"
        return int(value["value"])
    if kind == "float":
        return float(value["value"])
    if kind == "text":
        return value["value"]
    if kind == "blob":
        return base64.b64decode(value["base64"])
    raise AssertionError(f"unknown value type {kind}")


def _encode(value) -> dict:
    if value is None:
        return {"type": "null"}
    if isinstance(value, int):
        return {"type": "integer", "value": str(value)}
    if isinstance(value, float):
        return {"type": "float", "value": value}
    if isinstance(value, str):
        return {"type": "text", "value": value}
    # Real Turso leaves out base64's "=" padding (found on 24 Nov).
    return {"type": "blob", "base64": base64.b64encode(value).decode("ascii").rstrip("=")}


def _error(problem: Exception) -> dict:
    # Real Turso answers SQLITE_CONSTRAINT for every refused value, including
    # the wrong type in a STRICT table (Python names that one "unknown").
    if isinstance(problem, sqlite3.IntegrityError):
        code = "SQLITE_CONSTRAINT"
    else:
        name = getattr(problem, "sqlite_errorname", "") or ""
        code = name if name.startswith("SQLITE_") else "SQLITE_ERROR"
    return {"type": "error", "error": {"message": f"SQLite error: {problem}", "code": code}}


class FakeTurso:
    """One Turso database. Like the real one, each stream gets its own
    connection, so a transaction on one stream isn't seen by another."""

    def __init__(self, path: str):
        self.path = str(path)
        self.streams: dict[str, sqlite3.Connection] = {}
        self.memory: sqlite3.Connection | None = None   # ":memory:" is one connection, shared
        self.requests = 0                               # pipelines received (one round trip each)

    def _open(self) -> sqlite3.Connection:
        if self.path == ":memory:":
            if self.memory is None:
                self.memory = sqlite3.connect(":memory:", isolation_level=None, check_same_thread=False)
                self.memory.execute("PRAGMA foreign_keys = ON")
            return self.memory
        conn = sqlite3.connect(self.path, isolation_level=None, check_same_thread=False)
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def pipeline(self, body: dict) -> dict:
        body = json.loads(json.dumps(body))         # exactly what would cross the network
        self.requests += 1
        baton = body.get("baton")
        if baton is not None and baton not in self.streams:
            raise AssertionError(f"unknown or closed baton {baton!r}")
        conn = self.streams.pop(baton) if baton else self._open()
        results, closed = [], False
        for request in body["requests"]:
            assert not closed, "nothing may follow close"
            kind = request["type"]
            try:
                if kind == "execute":
                    results.append({"type": "ok", "response": {"type": "execute",
                                                               "result": self._execute(conn, request["stmt"])}})
                elif kind == "sequence":
                    for statement in _statements(request["sql"]):
                        self._refuse(statement)
                    conn.executescript(request["sql"])
                    results.append({"type": "ok", "response": {"type": "sequence"}})
                elif kind == "get_autocommit":
                    results.append({"type": "ok", "response": {"type": "get_autocommit",
                                                               "is_autocommit": not conn.in_transaction}})
                elif kind == "close":
                    if conn.in_transaction:
                        conn.execute("ROLLBACK")          # closing a stream ends its transaction
                    if conn is not self.memory:
                        conn.close()
                    closed = True
                    results.append({"type": "ok", "response": {"type": "close"}})
                else:
                    raise AssertionError(f"unexpected request {kind}")
            except sqlite3.Error as problem:
                results.append(_error(problem))
        new_baton = None
        if not closed:
            new_baton = f"baton-{next(_batons)}"
            self.streams[new_baton] = conn
        return json.loads(json.dumps({"baton": new_baton, "base_url": None, "results": results}))

    def _refuse(self, sql: str) -> None:
        if REFUSED.match(sql):
            raise sqlite3.OperationalError(f"SQL not allowed statement: {sql.strip()}")

    def _execute(self, conn: sqlite3.Connection, stmt: dict) -> dict:
        self._refuse(stmt["sql"])
        args = [_decode(value) for value in stmt.get("args", [])]
        assert not stmt.get("named_args"), "turso.py sends positional arguments only"
        cursor = conn.execute(stmt["sql"], args)
        rows = cursor.fetchall()
        cols = [{"name": column[0], "decltype": None} for column in cursor.description or ()]
        return {
            "cols": cols,
            "rows": [[_encode(value) for value in row] for row in rows],
            "affected_row_count": max(cursor.rowcount, 0),
            "last_insert_rowid": None if cursor.lastrowid is None else str(cursor.lastrowid),
        }

    def close_all(self) -> None:
        for conn in self.streams.values():
            if conn is not self.memory:
                conn.close()
        self.streams.clear()
        if self.memory is not None:
            self.memory.close()
            self.memory = None


def _statements(script: str):
    buffer = ""
    for line in script.splitlines(keepends=True):
        buffer += line
        if sqlite3.complete_statement(buffer):
            yield buffer
            buffer = ""
    if buffer.strip():
        yield buffer
