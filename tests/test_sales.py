"""Tests for services/sales.py, run against the fictional sample data.

Sample data facts used here (see docs/sample-data.md):
book 1 costs 39900 with 8 in stock, book 2 costs 55000 with 2 in stock,
book 5 costs 44900 with 0 in stock, book 9 costs 27500 with 1 in stock.
Completed revenue is 1,114,400 paise from 14 sales and 29 copies.
"""

import sqlite3
from datetime import datetime

import pytest

from services import ValidationError
from services.sales import SaleLine, cancel_sale, get_sale, list_sales, record_sale

NOW = datetime(2026, 11, 8, 15, 30, 0)


def stock(db, book_id):
    return db.execute("SELECT stock_quantity FROM books WHERE book_id = ?", (book_id,)).fetchone()[0]


def count(db, table):
    return db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def completed_revenue(db):
    return db.execute(
        """
        SELECT SUM(si.quantity * si.unit_price_paise)
        FROM sale_items AS si JOIN sales AS s ON s.sale_id = si.sale_id
        WHERE s.status = 'completed'
        """
    ).fetchone()[0]


def snapshot(db):
    """Everything a failed sale must leave untouched."""
    return (
        count(db, "sales"), count(db, "sale_items"), count(db, "sale_cancellations"),
        tuple(row[0] for row in db.execute("SELECT stock_quantity FROM books ORDER BY book_id")),
    )


# ---------- Recording: the happy path ----------

def test_selling_two_copies_saves_the_sale_and_reduces_stock_by_exactly_two(sample_db):
    sale_id = record_sale(sample_db, [SaleLine(1, 2, 39900)], now=NOW)
    assert sale_id == 16
    assert stock(sample_db, 1) == 6
    sale = get_sale(sample_db, sale_id)
    assert sale["status"] == "completed"
    assert sale["sale_datetime"] == "2026-11-08 15:30:00"
    assert sale["lines"] == [
        {"title": "The Monsoon Ledger", "quantity": 2, "unit_price_paise": 39900, "line_total_paise": 79800}
    ]
    assert sale["total_paise"] == 79800
    assert completed_revenue(sample_db) == 1_114_400 + 79_800


def test_multi_book_sale(sample_db):
    sale_id = record_sale(sample_db, [SaleLine(1, 1, 39900), SaleLine(3, 2, 34900)], now=NOW)
    sale = get_sale(sample_db, sale_id)
    assert sale["copies"] == 3
    assert sale["total_paise"] == 39900 + 2 * 34900
    assert (stock(sample_db, 1), stock(sample_db, 3)) == (7, 4)


def test_selling_the_last_copies_is_allowed(sample_db):
    record_sale(sample_db, [SaleLine(2, 2, 55000)], now=NOW)
    assert stock(sample_db, 2) == 0


def test_lines_for_the_same_book_are_combined(sample_db):
    sale_id = record_sale(sample_db, [SaleLine(1, 2, 39900), SaleLine(1, 1, 39900)], now=NOW)
    sale = get_sale(sample_db, sale_id)
    assert [line["quantity"] for line in sale["lines"]] == [3]
    assert stock(sample_db, 1) == 5


def test_sale_can_be_dated_in_the_past(sample_db):
    earlier = datetime(2026, 11, 7, 18, 45, 0)
    sale_id = record_sale(sample_db, [SaleLine(1, 1, 39900)], sale_datetime=earlier, now=NOW)
    assert get_sale(sample_db, sale_id)["sale_datetime"] == "2026-11-07 18:45:00"


# ---------- Recording: refusals change nothing ----------

def test_not_enough_stock_is_refused(sample_db):
    before = snapshot(sample_db)
    with pytest.raises(ValidationError) as caught:
        record_sale(sample_db, [SaleLine(9, 2, 27500)], now=NOW)
    assert caught.value.errors == ["Only 1 copy of “Ten Thousand Mangoes” in stock; the sale asks for 2."]
    assert snapshot(sample_db) == before


def test_out_of_stock_book_is_refused(sample_db):
    with pytest.raises(ValidationError):
        record_sale(sample_db, [SaleLine(5, 1, 44900)], now=NOW)
    assert stock(sample_db, 5) == 0


def test_second_line_failing_rolls_back_the_first(sample_db):
    # Book 1 has enough stock, book 9 doesn't. Book 1's stock update runs
    # first, so the rollback must undo it.
    before = snapshot(sample_db)
    with pytest.raises(ValidationError):
        record_sale(sample_db, [SaleLine(1, 2, 39900), SaleLine(9, 5, 27500)], now=NOW)
    assert snapshot(sample_db) == before
    assert stock(sample_db, 1) == 8


def test_every_problem_is_reported(sample_db):
    with pytest.raises(ValidationError) as caught:
        record_sale(sample_db, [SaleLine(9, 5, 27500), SaleLine(5, 1, 44900)], now=NOW)
    assert len(caught.value.errors) == 2


def test_changed_price_is_refused(sample_db):
    before = snapshot(sample_db)
    with pytest.raises(ValidationError) as caught:
        record_sale(sample_db, [SaleLine(1, 1, 34900)], now=NOW)   # old price
    assert "now ₹399.00, not ₹349.00" in caught.value.errors[0]
    assert snapshot(sample_db) == before


def test_missing_book_is_refused(sample_db):
    before = snapshot(sample_db)
    with pytest.raises(ValidationError):
        record_sale(sample_db, [SaleLine(999, 1, 100)], now=NOW)
    assert snapshot(sample_db) == before


def test_empty_sale_is_refused(sample_db):
    with pytest.raises(ValidationError) as caught:
        record_sale(sample_db, [], now=NOW)
    assert caught.value.errors == ["Add at least one book to the sale."]


@pytest.mark.parametrize("bad_quantity", [0, -1, True, 1.5])
def test_bad_quantity_is_refused(sample_db, bad_quantity):
    before = snapshot(sample_db)
    with pytest.raises(ValidationError):
        record_sale(sample_db, [SaleLine(1, bad_quantity, 39900)], now=NOW)
    assert snapshot(sample_db) == before


def test_future_date_is_refused(sample_db):
    with pytest.raises(ValidationError) as caught:
        record_sale(sample_db, [SaleLine(1, 1, 39900)], sale_datetime=datetime(2026, 11, 9), now=NOW)
    assert caught.value.errors == ["A sale can't be dated in the future."]


def test_same_book_at_two_prices_is_refused(sample_db):
    with pytest.raises(ValidationError):
        record_sale(sample_db, [SaleLine(1, 1, 39900), SaleLine(1, 1, 34900)], now=NOW)


# ---------- Cancelling ----------

def test_cancel_returns_stock_and_records_why(sample_db):
    sale_id = record_sale(sample_db, [SaleLine(1, 2, 39900), SaleLine(3, 1, 34900)], now=NOW)
    cancel_sale(sample_db, sale_id, "  Entered by mistake ", now=NOW)
    assert (stock(sample_db, 1), stock(sample_db, 3)) == (8, 6)   # back where they started
    sale = get_sale(sample_db, sale_id)
    assert sale["status"] == "cancelled"
    assert sale["cancel_reason"] == "Entered by mistake"
    assert sale["cancelled_at"] == "2026-11-08 15:30:00"
    assert completed_revenue(sample_db) == 1_114_400   # cancelled sales don't count


def test_cancelling_twice_returns_stock_once(sample_db):
    sale_id = record_sale(sample_db, [SaleLine(1, 2, 39900)], now=NOW)
    cancel_sale(sample_db, sale_id, "Mistake", now=NOW)
    with pytest.raises(ValidationError) as caught:
        cancel_sale(sample_db, sale_id, "Mistake", now=NOW)
    assert caught.value.errors == ["This sale was already cancelled."]
    assert stock(sample_db, 1) == 8
    assert count(sample_db, "sale_cancellations") == 2   # sale 9 from the sample data + this one


def test_cancel_requires_a_reason(sample_db):
    with pytest.raises(ValidationError) as caught:
        cancel_sale(sample_db, 1, "   ", now=NOW)
    assert caught.value.errors == ["Give a reason for cancelling the sale."]
    assert get_sale(sample_db, 1)["status"] == "completed"


def test_cancel_missing_sale(sample_db):
    with pytest.raises(ValidationError) as caught:
        cancel_sale(sample_db, 999, "Mistake", now=NOW)
    assert caught.value.errors == ["Sale #999 doesn't exist."]


def test_cancel_failure_rolls_back_status_and_stock(sample_db):
    # Make the last step (the cancellation record) fail; the status change
    # and the stock refund before it must be undone.
    sale_id = record_sale(sample_db, [SaleLine(1, 2, 39900)], now=NOW)
    sample_db.execute(
        "CREATE TEMP TRIGGER refuse_cancel BEFORE INSERT ON sale_cancellations "
        "BEGIN SELECT RAISE(ABORT, 'cancellation table unavailable'); END"
    )
    with pytest.raises(sqlite3.IntegrityError):
        cancel_sale(sample_db, sale_id, "Mistake", now=NOW)
    assert get_sale(sample_db, sale_id)["status"] == "completed"
    assert stock(sample_db, 1) == 6


def test_database_refuses_a_second_cancellation_record(sample_db):
    with pytest.raises(sqlite3.IntegrityError):
        sample_db.execute(
            "INSERT INTO sale_cancellations (sale_id, cancelled_at, reason) "
            "VALUES (9, '2026-11-08 10:00:00', 'Again')"
        )


# ---------- Listing ----------

def test_list_sales_newest_first_with_totals(sample_db):
    rows = list_sales(sample_db)
    assert [row["sale_id"] for row in rows][:3] == [15, 14, 13]
    sale_8 = next(row for row in rows if row["sale_id"] == 8)
    assert (sale_8["copies"], sale_8["total_paise"], sale_8["line_count"]) == (3, 129_700, 2)
    sale_9 = next(row for row in rows if row["sale_id"] == 9)
    assert sale_9["status"] == "cancelled"


def test_sample_cancelled_sale_has_its_record(sample_db):
    sale = get_sale(sample_db, 9)
    assert sale["status"] == "cancelled"
    assert sale["cancel_reason"] == "Customer changed their mind before paying"


def test_status_and_cancellation_records_agree(sample_db):
    # Every cancelled sale has exactly one record, and every record
    # belongs to a cancelled sale.
    mismatches = sample_db.execute(
        """
        SELECT COUNT(*) FROM sales AS s
        LEFT JOIN sale_cancellations AS c ON c.sale_id = s.sale_id
        WHERE (s.status = 'cancelled') <> (c.sale_id IS NOT NULL)
        """
    ).fetchone()[0]
    assert mismatches == 0
