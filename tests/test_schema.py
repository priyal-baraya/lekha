"""Tests that try to break the database rules.

Each test inserts something the schema should refuse and checks that
SQLite raises sqlite3.IntegrityError (a rule was broken). A few tests
first insert valid data, to prove the rules don't block normal use.
"""

import sqlite3

import pytest


def add_book(db, book_id=1, isbn="0000000000001", title="Test Book", **overrides):
    """Insert one valid book. Pass keyword arguments to change any column."""
    values = {
        "book_id": book_id,
        "isbn": isbn,
        "title": title,
        "author": "Test Author",
        "genre": "Fiction",
        "selling_price_paise": 30000,
        "cost_price_paise": 18000,
        "stock_quantity": 5,
        "reorder_level": 2,
    }
    values.update(overrides)
    columns = ", ".join(values)
    placeholders = ", ".join("?" for _ in values)
    db.execute(f"INSERT INTO books ({columns}) VALUES ({placeholders})", list(values.values()))


def add_sale(db, sale_id=1, sale_datetime="2026-10-28 10:00:00", status="completed"):
    db.execute(
        "INSERT INTO sales (sale_id, sale_datetime, status) VALUES (?, ?, ?)",
        (sale_id, sale_datetime, status),
    )


def add_sale_item(db, sale_id=1, book_id=1, quantity=1, unit_price_paise=30000):
    db.execute(
        "INSERT INTO sale_items (sale_id, book_id, quantity, unit_price_paise) VALUES (?, ?, ?, ?)",
        (sale_id, book_id, quantity, unit_price_paise),
    )


# ---------- Set-up checks ----------

def test_tables_exist(empty_db):
    names = {
        row["name"]
        for row in empty_db.execute("SELECT name FROM sqlite_schema WHERE type = 'table'")
    }
    assert {"books", "sales", "sale_items"} <= names


def test_foreign_keys_are_switched_on(empty_db):
    assert empty_db.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_schema_can_run_twice(empty_db):
    from database import create_schema

    create_schema(empty_db)  # must not fail: every statement uses IF NOT EXISTS


def test_valid_sale_is_accepted(empty_db):
    add_book(empty_db)
    add_sale(empty_db)
    add_sale_item(empty_db, quantity=2)
    count = empty_db.execute("SELECT COUNT(*) FROM sale_items").fetchone()[0]
    assert count == 1


# ---------- Books ----------

def test_duplicate_isbn_is_rejected(empty_db):
    add_book(empty_db, book_id=1, isbn="0000000000001")
    with pytest.raises(sqlite3.IntegrityError):
        add_book(empty_db, book_id=2, isbn="0000000000001")


def test_books_without_isbn_are_allowed(empty_db):
    # NULL means "unknown", and two unknowns are not duplicates.
    add_book(empty_db, book_id=1, isbn=None)
    add_book(empty_db, book_id=2, isbn=None)


@pytest.mark.parametrize("bad_isbn", ["12345", "00000000000A1", "000-000-0000"])
def test_badly_formed_isbn_is_rejected(empty_db, bad_isbn):
    with pytest.raises(sqlite3.IntegrityError):
        add_book(empty_db, isbn=bad_isbn)


@pytest.mark.parametrize("bad_title", ["", "   ", None])
def test_blank_title_is_rejected(empty_db, bad_title):
    with pytest.raises(sqlite3.IntegrityError):
        add_book(empty_db, title=bad_title)


@pytest.mark.parametrize(
    "column", ["selling_price_paise", "cost_price_paise", "stock_quantity", "reorder_level"]
)
def test_negative_numbers_are_rejected(empty_db, column):
    with pytest.raises(sqlite3.IntegrityError):
        add_book(empty_db, **{column: -1})


def test_unknown_cost_price_is_allowed(empty_db):
    add_book(empty_db, cost_price_paise=None)


def test_text_in_number_column_is_rejected(empty_db):
    # STRICT tables refuse values of the wrong type.
    with pytest.raises(sqlite3.IntegrityError):
        add_book(empty_db, stock_quantity="twelve")


def test_decimal_price_is_rejected(empty_db):
    # Prices are whole paise. 299.5 is a sign someone passed rupees by mistake.
    with pytest.raises(sqlite3.IntegrityError):
        add_book(empty_db, selling_price_paise=299.5)


# ---------- Sales ----------

@pytest.mark.parametrize(
    "bad_datetime",
    [
        "28/10/2026 10:00:00",   # wrong order
        "2026-10-28",            # no time
        "2026-13-01 10:00:00",   # month 13
        "2026-02-30 10:00:00",   # 30 February
        "2026-10-28 25:00:00",   # hour 25
        "yesterday",
    ],
)
def test_bad_sale_datetime_is_rejected(empty_db, bad_datetime):
    with pytest.raises(sqlite3.IntegrityError):
        add_sale(empty_db, sale_datetime=bad_datetime)


def test_unknown_status_is_rejected(empty_db):
    with pytest.raises(sqlite3.IntegrityError):
        add_sale(empty_db, status="refunded")


# ---------- Sale items ----------

def test_sale_item_for_missing_book_is_rejected(empty_db):
    add_sale(empty_db)
    with pytest.raises(sqlite3.IntegrityError):
        add_sale_item(empty_db, book_id=999)


def test_sale_item_for_missing_sale_is_rejected(empty_db):
    add_book(empty_db)
    with pytest.raises(sqlite3.IntegrityError):
        add_sale_item(empty_db, sale_id=999)


@pytest.mark.parametrize("bad_quantity", [0, -1])
def test_zero_or_negative_quantity_is_rejected(empty_db, bad_quantity):
    add_book(empty_db)
    add_sale(empty_db)
    with pytest.raises(sqlite3.IntegrityError):
        add_sale_item(empty_db, quantity=bad_quantity)


def test_negative_unit_price_is_rejected(empty_db):
    add_book(empty_db)
    add_sale(empty_db)
    with pytest.raises(sqlite3.IntegrityError):
        add_sale_item(empty_db, unit_price_paise=-100)


def test_same_book_twice_in_one_sale_is_rejected(empty_db):
    add_book(empty_db)
    add_sale(empty_db)
    add_sale_item(empty_db, quantity=1)
    with pytest.raises(sqlite3.IntegrityError):
        add_sale_item(empty_db, quantity=1)


def test_book_with_sales_history_cannot_be_deleted(empty_db):
    add_book(empty_db)
    add_sale(empty_db)
    add_sale_item(empty_db)
    with pytest.raises(sqlite3.IntegrityError):
        empty_db.execute("DELETE FROM books WHERE book_id = 1")


def test_book_without_sales_can_be_deleted(empty_db):
    add_book(empty_db)
    empty_db.execute("DELETE FROM books WHERE book_id = 1")
    assert empty_db.execute("SELECT COUNT(*) FROM books").fetchone()[0] == 0
