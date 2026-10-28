"""Tests for services/inventory.py, run against the fictional sample data."""

import sqlite3
from datetime import datetime

import pytest

from services import ValidationError
from services.books import get_book
from services.inventory import (
    StockChangedError,
    correct_stock,
    count_low_stock,
    low_stock_books,
    recent_adjustments,
)

NOW = datetime(2026, 10, 28, 9, 30, 0)


def stock(db, book_id):
    return get_book(db, book_id)["stock_quantity"]


def adjustment_count(db):
    return db.execute("SELECT COUNT(*) FROM stock_adjustments").fetchone()[0]


# ---------- Low-stock alerts ----------

def test_low_stock_books_emptiest_first(sample_db):
    rows = low_stock_books(sample_db)
    assert [row["book_id"] for row in rows] == [5, 9, 2]
    assert [row["stock_status"] for row in rows] == ["Out of stock", "Low stock", "Low stock"]


def test_count_low_stock(sample_db):
    assert count_low_stock(sample_db) == 3


# ---------- Stock corrections: the happy path ----------

def test_correction_updates_stock_and_records_history(sample_db):
    correct_stock(sample_db, book_id=1, expected_quantity=8, counted_quantity=5,
                  reason="shelf_count", now=NOW)
    assert stock(sample_db, 1) == 5
    [entry] = recent_adjustments(sample_db)
    assert entry["title"] == "The Monsoon Ledger"
    assert (entry["quantity_before"], entry["quantity_after"], entry["change"]) == (8, 5, -3)
    assert entry["reason_label"] == "Shelf count"
    assert entry["adjusted_at"] == "2026-10-28 09:30:00"


def test_delivery_raises_stock(sample_db):
    correct_stock(sample_db, 5, expected_quantity=0, counted_quantity=6,
                  reason="delivery_received", now=NOW)
    assert stock(sample_db, 5) == 6
    assert count_low_stock(sample_db) == 2  # book 5 is no longer low


def test_other_reason_with_note(sample_db):
    correct_stock(sample_db, 1, 8, 7, reason="other", note="  Signed copy given to author  ", now=NOW)
    assert recent_adjustments(sample_db)[0]["note"] == "Signed copy given to author"


# ---------- Stock corrections: refusals leave everything unchanged ----------

@pytest.mark.parametrize(
    "counted, reason, note, message",
    [
        (-1, "shelf_count", "", "The counted quantity can't be negative."),
        (8, "shelf_count", "", "The count matches the current stock, so there is nothing to correct."),
        (5, "stolen", "", "Choose a reason for the correction."),
        (5, "other", "   ", 'Add a note explaining the correction when the reason is "Other".'),
    ],
)
def test_invalid_corrections_are_refused(sample_db, counted, reason, note, message):
    with pytest.raises(ValidationError) as caught:
        correct_stock(sample_db, 1, 8, counted, reason, note, now=NOW)
    assert message in caught.value.errors
    assert stock(sample_db, 1) == 8
    assert adjustment_count(sample_db) == 0


def test_stale_count_is_refused(sample_db):
    # The page showed 7, but the database says 8: someone else changed it.
    with pytest.raises(StockChangedError):
        correct_stock(sample_db, 1, expected_quantity=7, counted_quantity=5,
                      reason="shelf_count", now=NOW)
    assert stock(sample_db, 1) == 8
    assert adjustment_count(sample_db) == 0


def test_same_correction_submitted_twice_applies_once(sample_db):
    # A double click on Save sends the same form twice.
    correct_stock(sample_db, 3, 6, 4, "damaged_or_lost", now=NOW)
    with pytest.raises(StockChangedError):
        correct_stock(sample_db, 3, 6, 4, "damaged_or_lost", now=NOW)
    assert stock(sample_db, 3) == 4
    assert adjustment_count(sample_db) == 1


def test_missing_book_is_refused(sample_db):
    with pytest.raises(ValidationError) as caught:
        correct_stock(sample_db, 999, 1, 2, "shelf_count", now=NOW)
    assert caught.value.errors == ["This book no longer exists."]


def test_failure_inside_transaction_rolls_back_stock(sample_db):
    # Force the second statement (the history insert) to fail after the
    # stock UPDATE has already run, by making the history table refuse
    # every insert. The rollback must undo the UPDATE too.
    sample_db.execute(
        """
        CREATE TEMP TRIGGER refuse_history BEFORE INSERT ON stock_adjustments
        BEGIN SELECT RAISE(ABORT, 'history table unavailable'); END
        """
    )
    with pytest.raises(sqlite3.IntegrityError):
        correct_stock(sample_db, 1, 8, 5, "shelf_count", now=NOW)
    assert stock(sample_db, 1) == 8
    assert adjustment_count(sample_db) == 0


# ---------- The table's own rules ----------

def test_history_table_rejects_a_non_change(sample_db):
    with pytest.raises(sqlite3.IntegrityError):
        sample_db.execute(
            "INSERT INTO stock_adjustments (book_id, adjusted_at, quantity_before, quantity_after, reason)"
            " VALUES (1, '2026-10-28 09:30:00', 8, 8, 'shelf_count')"
        )


def test_history_table_requires_note_for_other(sample_db):
    with pytest.raises(sqlite3.IntegrityError):
        sample_db.execute(
            "INSERT INTO stock_adjustments (book_id, adjusted_at, quantity_before, quantity_after, reason)"
            " VALUES (1, '2026-10-28 09:30:00', 8, 7, 'other')"
        )
