"""Tests for turso.py: Lekha's connection to Turso, made to behave like
Python's sqlite3.

These talk to a stand-in Turso server (tests/fake_turso.py) that answers
the same JSON as the real one, with sqlite3 on a local file. The whole
suite can also run through it (LEKHA_TEST_THROUGH_TURSO=1, conftest.py).
scripts/check_turso.py checks the same things against the real Turso.
"""

import http.server
import json
import sqlite3
import threading

import pytest

import database
import turso
from tests.fake_turso import FakeTurso


@pytest.fixture
def fake(tmp_path):
    server = FakeTurso(str(tmp_path / "shop.db"))
    yield server
    server.close_all()


@pytest.fixture
def conn(fake):
    connection = turso.Connection(fake)
    connection.executescript("""
        CREATE TABLE books (
            book_id INTEGER PRIMARY KEY,
            title TEXT NOT NULL UNIQUE,
            stock INTEGER NOT NULL CHECK (stock >= 0)
        ) STRICT;
        CREATE TABLE sales (
            sale_id INTEGER PRIMARY KEY,
            book_id INTEGER NOT NULL REFERENCES books (book_id)
        ) STRICT;
    """)
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("INSERT INTO books (title, stock) VALUES ('Gitanjali', 3)")
    connection.commit()
    yield connection
    connection.close()


# ------------------------------------------------------------------ rows

def test_rows_work_like_sqlite3_rows(conn):
    row = conn.execute("SELECT book_id, title, stock FROM books").fetchone()

    assert row["title"] == "Gitanjali"
    assert row[1] == "Gitanjali"
    assert row[-1] == 3
    assert row.keys() == ["book_id", "title", "stock"]
    assert dict(row) == {"book_id": 1, "title": "Gitanjali", "stock": 3}
    assert tuple(row) == (1, "Gitanjali", 3)
    book_id, title, stock = row
    assert (book_id, title, stock) == (1, "Gitanjali", 3)


def test_row_names_ignore_case_like_sqlite3(conn):
    row = conn.execute("SELECT title AS Name FROM books").fetchone()

    assert row["name"] == row["NAME"] == "Gitanjali"
    with pytest.raises(IndexError):
        row["missing"]


def test_fetching(conn):
    conn.execute("INSERT INTO books (title, stock) VALUES ('Godan', 1)")

    assert conn.execute("SELECT 1 WHERE 0").fetchone() is None
    assert [r["title"] for r in conn.execute("SELECT title FROM books ORDER BY title")] == ["Gitanjali", "Godan"]
    assert len(conn.execute("SELECT * FROM books").fetchall()) == 2
    assert len(conn.execute("SELECT * FROM books").fetchmany(1)) == 1


def test_cursor_details(conn):
    cursor = conn.execute("INSERT INTO books (title, stock) VALUES ('Godan', 1)")
    assert cursor.lastrowid == 2
    assert cursor.rowcount == 1
    assert conn.execute("SELECT title FROM books").description[0][0] == "title"
    assert conn.cursor().execute("SELECT count(*) FROM books").fetchone()[0] == 2


# ------------------------------------------------------------ parameters

def test_named_parameters(conn):
    row = conn.execute("SELECT title FROM books WHERE stock >= :least AND title = :title",
                       {"title": "Gitanjali", "least": 1}).fetchone()

    assert row["title"] == "Gitanjali"


def test_named_parameters_can_repeat(conn):
    assert conn.execute("SELECT :n + :n", {"n": 2}).fetchone()[0] == 4


def test_colons_in_text_and_comments_are_not_parameters(conn):
    row = conn.execute("""
        SELECT ':not' AS "b:c", :real AS [d:e]  -- a :comment
        /* and :another */
    """, {"real": 5}).fetchone()

    assert tuple(row) == (":not", 5)
    assert row.keys() == ["b:c", "d:e"]


def test_a_missing_named_parameter_is_an_error(conn):
    with pytest.raises(sqlite3.ProgrammingError):
        conn.execute("SELECT :absent", {"other": 1})


def test_positional_parameters_from_any_sequence(conn):
    assert conn.execute("SELECT ? + ?", [1, 2]).fetchone()[0] == 3
    assert conn.execute("SELECT ?", (x for x in [7])).fetchone()[0] == 7


def test_executemany_with_named_parameters(conn):
    conn.executemany("INSERT INTO books (title, stock) VALUES (:title, :stock)",
                     [{"title": "Godan", "stock": 1}, {"title": "Nirmala", "stock": 2}])

    assert conn.execute("SELECT count(*) FROM books").fetchone()[0] == 3


# ---------------------------------------------------------------- errors

@pytest.mark.parametrize("sql", [
    "INSERT INTO books (title, stock) VALUES ('Gitanjali', 1)",   # UNIQUE
    "INSERT INTO books (title, stock) VALUES ('Godan', -1)",      # CHECK
    "INSERT INTO books (title, stock) VALUES (NULL, 1)",          # NOT NULL
    "INSERT INTO sales (book_id) VALUES (99)",                    # FOREIGN KEY
])
def test_broken_rules_raise_integrity_error(conn, sql):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(sql)


def test_other_database_problems_raise_operational_error(conn):
    with pytest.raises(sqlite3.OperationalError):
        conn.execute("SELECT * FROM no_such_table")
    with pytest.raises(sqlite3.OperationalError):
        conn.execute("SELEC nonsense")


def test_every_error_is_a_sqlite3_error(conn):
    """app.py shows its friendly database message for sqlite3.Error."""
    with pytest.raises(sqlite3.Error):
        conn.execute("SELECT * FROM no_such_table")


# ---------------------------------------------------------- transactions

def test_with_block_commits(conn):
    with conn:
        conn.execute("INSERT INTO books (title, stock) VALUES ('Godan', 1)")
    conn.rollback()

    assert conn.execute("SELECT count(*) FROM books").fetchone()[0] == 2


def test_with_block_rolls_back_on_error(conn):
    with pytest.raises(RuntimeError):
        with conn:
            conn.execute("UPDATE books SET stock = 0")
            raise RuntimeError

    assert conn.execute("SELECT stock FROM books").fetchone()[0] == 3


def test_a_failed_rule_inside_a_with_block_leaves_nothing_half_saved(conn):
    with pytest.raises(sqlite3.IntegrityError):
        with conn:
            conn.execute("UPDATE books SET stock = 2")
            conn.execute("INSERT INTO sales (book_id) VALUES (99)")

    assert conn.execute("SELECT stock FROM books").fetchone()[0] == 3
    assert not conn.in_transaction


def test_executescript_with_its_own_transaction(conn):
    conn.executescript("BEGIN;\nCREATE TABLE extra (n INTEGER) STRICT;\nINSERT INTO extra VALUES (4);\nCOMMIT;")

    assert conn.execute("SELECT n FROM extra").fetchone()[0] == 4


def test_values_of_every_kind_come_back_as_they_went(conn):
    row = conn.execute("SELECT ?, ?, ?, ?, ?, ?", (None, 7, -2**62, 1.5, "₹ text", b"\x00\xff")).fetchone()

    assert tuple(row) == (None, 7, -2**62, 1.5, "₹ text", b"\x00\xff")
    assert conn.execute("SELECT ?", (True,)).fetchone()[0] == 1


def test_a_value_sqlite3_cant_store_is_refused(conn):
    from decimal import Decimal
    with pytest.raises(sqlite3.ProgrammingError):
        conn.execute("SELECT ?", (Decimal("1.5"),))


def test_no_rows_is_an_empty_list(conn):
    cursor = conn.execute("SELECT title FROM books WHERE 0")
    assert cursor.fetchall() == [] and cursor.fetchone() is None and cursor.fetchmany(5) == []


# --------------------------------------------------------- round trips

def test_each_query_is_one_request(conn, fake):
    before = fake.requests
    conn.execute("SELECT COUNT(*) FROM books").fetchone()
    conn.execute("SELECT title FROM books").fetchall()

    assert fake.requests - before == 2


def test_a_save_sends_begin_with_its_first_statement(conn, fake):
    """sqlite3 starts a transaction before an INSERT, UPDATE or DELETE;
    here the BEGIN travels in the same request, so it costs nothing."""
    before = fake.requests
    with conn:
        conn.execute("UPDATE books SET stock = stock - 1")      # BEGIN + UPDATE: one request
        conn.execute("INSERT INTO sales (book_id) VALUES (1)")  # one request
    # COMMIT: one request

    assert fake.requests - before == 3
    assert conn.execute("SELECT stock FROM books").fetchone()[0] == 2


def test_nothing_is_left_open_between_requests(conn, fake):
    conn.execute("SELECT 1").fetchone()
    with conn:
        conn.execute("UPDATE books SET stock = 4")
    assert fake.streams == {}


def test_a_transaction_isnt_seen_by_others_until_it_commits(conn, fake, tmp_path):
    other = turso.Connection(FakeTurso(str(tmp_path / "shop.db")))
    conn.execute("UPDATE books SET stock = 9")
    assert conn.in_transaction
    assert other.execute("SELECT stock FROM books").fetchone()[0] == 3
    conn.commit()
    assert not conn.in_transaction
    assert other.execute("SELECT stock FROM books").fetchone()[0] == 9


def test_closing_in_the_middle_of_a_transaction_discards_it(conn, fake, tmp_path):
    conn.execute("UPDATE books SET stock = 0")
    conn.close()

    assert fake.streams == {}
    again = turso.Connection(FakeTurso(str(tmp_path / "shop.db")))
    assert again.execute("SELECT stock FROM books").fetchone()[0] == 3


def test_an_explicit_begin_keeps_the_transaction_open(conn):
    conn.execute("BEGIN")
    conn.execute("UPDATE books SET stock = 5")
    conn.rollback()

    assert conn.execute("SELECT stock FROM books").fetchone()[0] == 3


def test_executemany_is_one_request(conn, fake):
    before = fake.requests
    with conn:
        conn.executemany("INSERT INTO books (title, stock) VALUES (?, ?)", [("A", 1), ("B", 2), ("C", 3)])

    assert fake.requests - before == 2          # BEGIN + three INSERTs, then COMMIT
    assert conn.execute("SELECT COUNT(*) FROM books").fetchone()[0] == 4


def test_refused_like_real_turso(conn):
    """The stand-in refuses what real Turso refused (found on 18 Nov)."""
    with pytest.raises(sqlite3.OperationalError):
        conn.executescript("PRAGMA user_version = 3;")
    with pytest.raises(sqlite3.OperationalError):
        conn.execute("CREATE TEMP TABLE t (n INTEGER)")


# ------------------------------------------------------------- network

class _Server(http.server.ThreadingHTTPServer):
    daemon_threads = True


@pytest.fixture
def http_turso(tmp_path):
    """A local HTTP server answering like Turso, counting connections."""
    backend = FakeTurso(str(tmp_path / "net.db"))
    seen = {"connections": set(), "authorization": [], "fail_with": None, "hang_up": False}

    class Handler(http.server.BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"          # keep-alive, like Turso

        def do_POST(self):
            seen["connections"].add(self.client_address)
            seen["authorization"].append(self.headers.get("Authorization"))
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            if seen["fail_with"]:
                status, answer = seen["fail_with"]
            else:
                status, answer = 200, backend.pipeline(body)
            data = json.dumps(answer).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            if seen["hang_up"]:            # close the kept-alive connection without saying so
                self.close_connection = True

        def log_message(self, *args):
            pass

    server = _Server(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()

    class PlainPool(turso._Pool):           # plain HTTP to the local server
        def new(self, host):
            return turso.http.client.HTTPConnection("127.0.0.1", server.server_address[1], timeout=5)

    pool = PlainPool()
    transport = turso.HttpTransport("libsql://lekha-shop-1.local.test", "secret-token", pool=pool)
    yield turso.Connection(transport), seen, pool
    pool.clear()
    server.shutdown()
    backend.close_all()


def test_one_secure_connection_is_kept_and_reused(http_turso):
    conn, seen, _ = http_turso
    for _ in range(5):
        conn.execute("SELECT 1").fetchone()

    assert len(seen["connections"]) == 1
    assert seen["authorization"] == ["Bearer secret-token"] * 5


def test_a_refused_request_never_shows_the_token(http_turso):
    conn, seen, _ = http_turso
    seen["fail_with"] = (400, {"error": "JWT error: InvalidToken"})

    with pytest.raises(sqlite3.OperationalError) as problem:
        conn.execute("SELECT 1")
    assert "HTTP 400" in str(problem.value) and "InvalidToken" in str(problem.value)
    assert "secret-token" not in str(problem.value)


def test_turso_out_of_reach_is_a_database_error(tmp_path):
    class Nowhere(turso._Pool):
        def new(self, host):
            return turso.http.client.HTTPConnection("127.0.0.1", 9, timeout=1)   # nothing listens there

    conn = turso.Connection(turso.HttpTransport("libsql://x.local.test", "t", pool=Nowhere()))
    with pytest.raises(sqlite3.OperationalError, match="Couldn't reach Turso"):
        conn.execute("SELECT 1")


def test_a_stale_connection_is_retried_only_for_reads(http_turso):
    conn, seen, pool = http_turso
    seen["hang_up"] = True                              # Turso closes each connection after answering
    conn.execute("SELECT 1").fetchone()                 # the pooled connection is now dead
    assert conn.execute("SELECT 2").fetchone()[0] == 2  # a read: retried on a new connection
    with pytest.raises(sqlite3.OperationalError):
        conn.execute("CREATE TABLE IF NOT EXISTS t (n INTEGER)")   # a change: never sent twice
    assert len(seen["connections"]) == 2


def test_requests_are_counted_for_the_log(conn, fake):
    turso.reset_stats()
    conn.execute("SELECT 1").fetchone()
    conn.execute("SELECT 2").fetchone()
    assert turso.stats.requests == 0          # the stand-in isn't the network; counted only over HTTP


def test_requests_over_http_are_counted(http_turso):
    conn, _, _ = http_turso
    turso.reset_stats()
    conn.execute("SELECT 1").fetchone()
    conn.execute("SELECT 2").fetchone()
    assert turso.stats.requests == 2 and turso.stats.seconds > 0


def test_row_factory_can_be_set_like_sqlite3(conn):
    conn.row_factory = sqlite3.Row     # database.get_connection does this
    assert conn.execute("SELECT title FROM books").fetchone()["title"] == "Gitanjali"


# -------------------------------------------------- where the data lives

def test_turso_names_for_lekha_files(tmp_path):
    assert turso.database_name(tmp_path / "accounts.db") == "accounts"
    assert turso.database_name(tmp_path / "shops" / "shop_12.db") == "shop-12"
    for other in ("lekha.db", "shop_x.db", "notes.txt"):
        with pytest.raises(ValueError):
            turso.database_name(tmp_path / other)


def test_turso_address_from_the_template():
    template = "libsql://lekha-{name}-someone.aws-ap-south-1.turso.io"

    assert turso.address(template, "shop-3") == "libsql://lekha-shop-3-someone.aws-ap-south-1.turso.io"
    with pytest.raises(ValueError):
        turso.address("libsql://lekha.turso.io", "shop-3")      # no {name}
    with pytest.raises(ValueError):
        turso.address("http://lekha-{name}.turso.io", "shop-3")  # not encrypted
    with pytest.raises(ValueError):
        turso.HttpTransport("libsql://lekha-x.turso.io@evil.example", "token")   # odd characters
    with pytest.raises(ValueError):
        turso.HttpTransport("libsql://lekha-x.turso.io", "")                 # no token


def test_lekha_uses_turso_only_when_configured(tmp_path, monkeypatch):
    calls = []

    def fake_connect(target, auth_token=None):
        calls.append((target, auth_token))
        return turso.Connection(FakeTurso(str(tmp_path / "stand-in.db")))

    monkeypatch.setattr(turso, "connect", fake_connect)
    monkeypatch.setattr(database, "_turso_connection", database._turso_connection.__wrapped__
                        if hasattr(database._turso_connection, "__wrapped__") else database._turso_connection)
    monkeypatch.delenv("LEKHA_TURSO_URL", raising=False)
    local = database.get_connection(tmp_path / "accounts.db")
    assert isinstance(local, sqlite3.Connection)
    local.close()

    monkeypatch.setenv("LEKHA_TURSO_URL", "libsql://lekha-{name}-someone.turso.io")
    monkeypatch.setenv("LEKHA_TURSO_TOKEN", "token-for-test")

    remote = database.get_connection(tmp_path / "shops" / "shop_2.db")
    assert isinstance(remote, turso.Connection)
    assert remote.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    remote.close()
    assert calls == [("libsql://lekha-shop-2-someone.turso.io", "token-for-test")]
    # In-memory databases (the rule tests) never go to Turso.
    memory = database.get_connection(":memory:")
    assert isinstance(memory, sqlite3.Connection)
    memory.close()


def test_turso_needs_a_token(tmp_path, monkeypatch):
    monkeypatch.setenv("LEKHA_TURSO_URL", "libsql://lekha-{name}-someone.turso.io")
    monkeypatch.delenv("LEKHA_TURSO_TOKEN", raising=False)

    with pytest.raises(RuntimeError, match="LEKHA_TURSO_TOKEN"):
        database.get_connection(tmp_path / "accounts.db")


def test_wrong_kind_of_value_in_a_strict_table_is_an_integrity_error(conn):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO books (title, stock) VALUES ('Godan', 'many')")


def test_on_turso_each_database_is_set_up_once(tmp_path, monkeypatch):
    """Every statement to Turso crosses the internet, so the tables are
    checked once per run of Lekha, not on every page."""
    scripts = []

    def stand_in(target, auth_token=None):        # a local file per Turso database
        name = target.split("//")[1].split(".")[0]
        connection = turso.Connection(FakeTurso(str(tmp_path / f"{name}.db")))
        real_script = connection.executescript
        connection.executescript = lambda script: scripts.append(target) or real_script(script)
        return connection

    monkeypatch.setattr(turso, "connect", stand_in)
    monkeypatch.setattr(database, "_set_up", set())
    monkeypatch.setenv("LEKHA_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("LEKHA_TURSO_URL", "libsql://lekha-{name}.turso.io")
    monkeypatch.setenv("LEKHA_TURSO_TOKEN", "token-for-test")

    def open_a_page():
        database.ensure_shop_database(1)
        with database.connect_accounts() as acc:
            acc.execute("SELECT COUNT(*) FROM users").fetchone()

    open_a_page()
    first_time = len(scripts)
    open_a_page()
    open_a_page()

    assert sorted(set(scripts)) == ["libsql://lekha-accounts.turso.io", "libsql://lekha-shop-1.turso.io"]
    assert len(scripts) == first_time


def test_files_are_still_checked_every_time(tmp_path, monkeypatch):
    """Without Turso nothing is remembered: a deleted file is made again."""
    monkeypatch.delenv("LEKHA_TURSO_URL", raising=False)
    path = tmp_path / "shop_1.db"
    database.ensure_database(path)
    path.unlink()
    database.ensure_database(path)

    with database.connect(path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM books").fetchone()[0] == 0


def test_turso_settings_come_from_secrets_when_hosted():
    from ui.session import copy_turso_settings
    environ = {}
    copy_turso_settings({"LEKHA_TURSO_URL": "libsql://lekha-{name}.turso.io",
                         "LEKHA_TURSO_TOKEN": " token ", "other": "ignored"}, environ)

    assert environ == {"LEKHA_TURSO_URL": "libsql://lekha-{name}.turso.io", "LEKHA_TURSO_TOKEN": "token"}


def test_settings_already_in_the_environment_win():
    from ui.session import copy_turso_settings
    environ = {"LEKHA_TURSO_URL": "libsql://chosen-{name}.turso.io"}
    copy_turso_settings({"LEKHA_TURSO_URL": "libsql://other-{name}.turso.io"}, environ)

    assert environ == {"LEKHA_TURSO_URL": "libsql://chosen-{name}.turso.io"}


def test_no_secrets_no_turso():
    from ui.session import copy_turso_settings
    environ = {}
    copy_turso_settings({}, environ)
    copy_turso_settings({"LEKHA_TURSO_URL": "  "}, environ)

    assert environ == {}


def test_the_turso_check_passes_on_a_good_connection(tmp_path):
    import importlib.util
    spec = importlib.util.spec_from_file_location("check_turso", database.PROJECT_DIR / "scripts" / "check_turso.py")
    check_turso = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(check_turso)

    with database.connect(tmp_path / "shop_1.db") as conn:
        assert check_turso.check(conn, lambda: database.get_connection(tmp_path / "shop_1.db")) == []
    through = turso.Connection(FakeTurso(str(tmp_path / "shop_2.db")))      # and through turso.py
    assert check_turso.check(through, lambda: turso.Connection(FakeTurso(str(tmp_path / "shop_2.db")))) == []
    raw = sqlite3.connect(tmp_path / "no_rules.db")     # foreign keys left off
    assert check_turso.check(raw) == ["foreign keys aren't enforced"]
    raw.close()


def test_where_the_data_lives_is_told_plainly(tmp_path, monkeypatch):
    monkeypatch.delenv("LEKHA_TURSO_URL", raising=False)
    monkeypatch.setenv("LEKHA_DATA_DIR", str(tmp_path))
    assert database.where_data_lives() == f"Lekha keeps its data in files in {tmp_path}."

    monkeypatch.setenv("LEKHA_TURSO_URL", "libsql://lekha-{name}-someone.turso.io")
    monkeypatch.setenv("LEKHA_TURSO_TOKEN", "secret-token-value")
    told = database.where_data_lives()
    assert told == "Lekha keeps its data in Turso (libsql://lekha-{name}-someone.turso.io)."
    assert "secret-token-value" not in told


def test_where_the_data_lives_is_printed_once(monkeypatch, capsys):
    from ui import session
    monkeypatch.delenv("LEKHA_TURSO_URL", raising=False)
    monkeypatch.setattr(session, "_told_where_data_lives", False)
    session.use_turso_settings_from_secrets()
    session.use_turso_settings_from_secrets()

    assert capsys.readouterr().out.count("Lekha keeps its data in") == 1


def test_the_log_line_for_a_page():
    turso.reset_stats()
    turso.stats.requests, turso.stats.seconds = 16, 1.234

    assert turso.page_summary("Overview", 1.5) == "Overview: 16 requests to Turso, 1.23 s of 1.50 s"
    turso.reset_stats()
    assert turso.stats.requests == 0 and turso.stats.seconds == 0
