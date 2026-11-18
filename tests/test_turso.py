"""Tests for turso.py: Turso's driver made to behave like Python's sqlite3.

These use the same driver (libsql) on local files, the way the hosted
Lekha uses it on Turso's servers. tests/conftest.py can also run the
whole suite through it (LEKHA_TEST_DRIVER=libsql).
"""

import sqlite3

import pytest

import database
import turso


@pytest.fixture
def conn(tmp_path):
    connection = turso.connect(str(tmp_path / "shop.db"))
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
    conn.executescript("BEGIN;\nCREATE TABLE extra (n INTEGER) STRICT;\nPRAGMA user_version = 4;\nCOMMIT;")

    assert conn.execute("PRAGMA user_version").fetchone()[0] == 4


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


def test_lekha_uses_turso_only_when_configured(tmp_path, monkeypatch):
    calls = []
    real_connect = turso.connect

    def fake_connect(target, auth_token=None):
        calls.append((target, auth_token))
        return real_connect(str(tmp_path / "stand-in.db"))

    monkeypatch.setattr(turso, "connect", fake_connect)
    monkeypatch.delenv("LEKHA_TURSO_URL", raising=False)
    monkeypatch.delenv("LEKHA_SQLITE_DRIVER", raising=False)
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
    real_connect = turso.connect
    scripts = []

    def stand_in(target, auth_token=None):        # a local file per Turso database
        connection = real_connect(str(tmp_path / (target.split("//")[1].split(".")[0] + ".db")))
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
