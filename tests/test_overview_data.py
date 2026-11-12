"""Tests for the data behind the redesigned Overview: the books to
reorder (with covers), the latest sales (with their books), and what's
selling this week, plus the short sentences written about them.

Each test records its own sales at known times, so the expected numbers
can be worked out by reading the test.
"""

from datetime import date, datetime

import pytest

from services.analytics import selling_this_week
from services.books import BookInput, add_book
from services.inventory import low_stock_books
from services.sales import SaleLine, cancel_sale, latest_sales, record_sale
from services.sentences import sale_time_label, selling_well_note

NOW = datetime(2026, 11, 12, 16, 45)        # Thursday afternoon
YESTERDAY = datetime(2026, 11, 11)


@pytest.fixture
def shop(empty_db):
    """Three books and a few sales this week and last."""
    def book(title, author, price, stock, cover_id=None, reorder=2):
        return add_book(empty_db, BookInput(title=title, author=author, genre="Fiction", selling_price=price,
                                            stock_quantity=stock, reorder_level=reorder, cover_id=cover_id))

    ids = {
        "malgudi": book("Malgudi Days", "R. K. Narayan", "250", 20, cover_id=101),   # any number: never fetched
        "train": book("Train to Pakistan", "Khushwant Singh", "450", 10),
        "gitanjali": book("Gitanjali", "Rabindranath Tagore", "300", 4),
    }

    def sell(when, *lines):
        return record_sale(empty_db, [SaleLine(ids[key], copies, price) for key, copies, price in lines],
                           sale_datetime=when, now=NOW)

    sell(datetime(2026, 11, 5, 12, 0), ("malgudi", 9, 25_000))                      # last week
    sell(datetime(2026, 11, 9, 10, 0), ("gitanjali", 3, 30_000))                     # Monday
    sell(datetime(2026, 11, 10, 18, 5), ("train", 1, 45_000))                        # Tuesday
    late = sell(datetime(2026, 11, 11, 18, 5), ("malgudi", 1, 25_000), ("train", 1, 45_000))   # yesterday
    cancel_sale(empty_db, late, "Rang up twice", now=NOW)
    sell(datetime(2026, 11, 12, 11, 20), ("gitanjali", 1, 30_000))                   # today: sells out
    sell(datetime(2026, 11, 12, 16, 44), ("malgudi", 2, 25_000), ("train", 1, 45_000))
    return empty_db, ids


# ---------- Books to reorder ----------

def test_books_to_reorder_carry_their_cover(shop):
    conn, ids = shop
    rows = {row["book_id"]: row for row in low_stock_books(conn)}
    assert rows[ids["gitanjali"]]["cover_id"] is None          # no cover: the page shows its letter
    assert rows[ids["gitanjali"]]["stock_quantity"] == 0


# ---------- Latest sales ----------

def test_latest_sales_are_newest_first_with_their_books(shop):
    conn, _ = shop
    rows = latest_sales(conn, since=YESTERDAY)
    assert [row["books"] for row in rows] == [
        "Malgudi Days ×2, Train to Pakistan",
        "Gitanjali",
        "Malgudi Days, Train to Pakistan",
    ]
    assert [row["total_paise"] for row in rows] == [95_000, 30_000, 70_000]


def test_latest_sales_show_cancelled_sales_as_cancelled(shop):
    conn, _ = shop
    statuses = [row["status"] for row in latest_sales(conn, since=YESTERDAY)]
    assert statuses == ["completed", "completed", "cancelled"]


def test_latest_sales_leave_out_older_sales_and_stop_at_the_limit(shop):
    conn, _ = shop
    assert len(latest_sales(conn, since=YESTERDAY, limit=2)) == 2
    assert all(row["sale_datetime"] >= "2026-11-11" for row in latest_sales(conn, since=YESTERDAY))


def test_no_latest_sales_is_an_empty_list(empty_db):
    assert latest_sales(empty_db, since=YESTERDAY) == []


# ---------- Selling well this week ----------

def test_selling_this_week_counts_copies_since_monday(shop):
    conn, ids = shop
    rows = selling_this_week(conn, NOW)
    # Malgudi: 2 today (the 9 last week and the cancelled one don't count).
    # Gitanjali: 3 on Monday + 1 today. Train: 1 Tuesday + 1 today.
    # A tie on copies goes to the higher revenue: Train (₹900) before Malgudi (₹500).
    assert [(row["title"], row["copies"]) for row in rows] == [
        ("Gitanjali", 4), ("Train to Pakistan", 2), ("Malgudi Days", 2),
    ]


def test_selling_this_week_knows_covers_and_sold_out_books(shop):
    conn, ids = shop
    rows = {row["title"]: row for row in selling_this_week(conn, NOW)}
    assert rows["Malgudi Days"]["cover_id"] == 101
    assert rows["Gitanjali"]["stock_quantity"] == 0


def test_selling_this_week_stops_at_the_limit(shop):
    conn, _ = shop
    assert len(selling_this_week(conn, NOW, limit=1)) == 1


# ---------- Sentences ----------

@pytest.mark.parametrize(
    "when, expected",
    [
        (datetime(2026, 11, 12, 16, 45), "16:45"),
        (datetime(2026, 11, 12, 9, 5), "09:05"),
        (datetime(2026, 11, 11, 18, 5), "Yesterday 18:05"),
        (datetime(2026, 11, 5, 10, 0), "5 Nov 10:00"),
    ],
)
def test_sale_time_label(when, expected):
    assert sale_time_label(when, date(2026, 11, 12)) == expected


def test_selling_well_note_with_nothing_sold_out():
    rows = [{"title": "Malgudi Days", "stock_quantity": 3}]
    assert selling_well_note(rows) == "Copies sold since Monday."


def test_selling_well_note_names_a_sold_out_book():
    rows = [{"title": "Gitanjali", "stock_quantity": 0}, {"title": "Malgudi Days", "stock_quantity": 3}]
    assert selling_well_note(rows) == "Copies sold since Monday. Gitanjali sold out, so it's on the reorder list."


def test_selling_well_note_names_several_sold_out_books():
    rows = [{"title": "Gitanjali", "stock_quantity": 0}, {"title": "The Guide", "stock_quantity": 0},
            {"title": "Godaan", "stock_quantity": 0}]
    assert selling_well_note(rows) == ("Copies sold since Monday. Gitanjali, The Guide and Godaan sold out, "
                                       "so they're on the reorder list.")
