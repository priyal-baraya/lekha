"""Tests for services/till.py: finding a book at the till, the basket's
rules, and the line that says when the sale will be recorded.

The basket is plain Python, so these tests run without Streamlit or a
browser. Each test builds its own small shop.
"""

from datetime import datetime

import pytest

from services.books import BookInput, add_book
from services.sales import SaleLine, cancel_sale, latest_sales, record_sale
from services.till import Basket, recorded_as, till_search

NOW = datetime(2026, 11, 12, 16, 45)        # Thursday afternoon


@pytest.fixture
def shop(empty_db):
    def book(title, author, price, stock, isbn=None):
        book_id = add_book(empty_db, BookInput(title=title, author=author, genre="Fiction", selling_price=price,
                                               stock_quantity=stock, isbn=isbn))
        return next(b for b in till_search(empty_db, title).books if b["book_id"] == book_id)

    books = {
        "malgudi": book("Malgudi Days", "R. K. Narayan", "300", 5, isbn="9780143039655"),
        "guide": book("The Guide", "R. K. Narayan", "299", 2),
        "train": book("Train to Pakistan", "Khushwant Singh", "350", 8),
        "gitanjali": book("Gitanjali", "Rabindranath Tagore", "300", 0),
    }
    return empty_db, books


# ---------- Finding a book ----------

def test_one_title_match(shop):
    conn, _ = shop
    found = till_search(conn, "train")
    assert [b["title"] for b in found.books] == ["Train to Pakistan"] and found.total == 1


def test_author_matches_every_book_by_them(shop):
    conn, _ = shop
    assert {b["title"] for b in till_search(conn, "narayan").books} == {"Malgudi Days", "The Guide"}


def test_a_scanned_isbn_finds_exactly_that_book(shop):
    conn, _ = shop
    found = till_search(conn, "978-0-14-303965-5")              # typed with dashes
    assert [b["title"] for b in found.books] == ["Malgudi Days"] and found.by_isbn


def test_an_unknown_isbn_finds_nothing(shop):
    conn, _ = shop
    found = till_search(conn, "9780000000002")
    assert found.books == [] and found.total == 0


def test_an_empty_search_finds_nothing_rather_than_everything(shop):
    conn, _ = shop
    assert till_search(conn, "   ").books == []


def test_search_shows_a_few_and_counts_the_rest(shop):
    conn, _ = shop
    found = till_search(conn, "a", limit=2)
    assert len(found.books) == 2 and found.total == 4


# ---------- The basket ----------

def test_adding_a_book_twice_makes_two_copies(shop):
    _, books = shop
    basket = Basket()
    assert basket.add(books["malgudi"]) is None
    assert basket.add(books["malgudi"]) is None
    assert basket.copies == 2 and basket.total_paise == 60_000


def test_an_out_of_stock_book_cant_be_added(shop):
    _, books = shop
    basket = Basket()
    assert basket.add(books["gitanjali"]) == "Gitanjali can't be sold until it's restocked."
    assert basket.copies == 0


def test_the_basket_never_holds_more_than_the_shelf(shop):
    _, books = shop
    basket = Basket()
    basket.add(books["guide"])
    basket.add(books["guide"])
    assert basket.add(books["guide"]) == "Only 2 copies of The Guide are in stock, and both are in this sale."
    assert basket.more(books["guide"]["book_id"]) is not None
    assert basket.copies == 2


def test_one_more_and_one_fewer(shop):
    _, books = shop
    basket = Basket()
    book_id = books["train"]["book_id"]
    basket.add(books["train"])
    basket.more(book_id)
    basket.more(book_id)
    basket.fewer(book_id)
    assert basket.lines[book_id].quantity == 2


def test_one_fewer_stops_at_one_copy(shop):
    _, books = shop
    basket = Basket()
    book_id = books["train"]["book_id"]
    basket.add(books["train"])
    basket.fewer(book_id)
    assert basket.lines[book_id].quantity == 1               # Remove takes it out, not "one fewer"


def test_remove_and_clear(shop):
    _, books = shop
    basket = Basket()
    basket.add(books["train"])
    basket.add(books["malgudi"])
    basket.remove(books["train"]["book_id"])
    assert list(basket.lines) == [books["malgudi"]["book_id"]]
    basket.clear()
    assert basket.copies == 0 and not basket


def test_the_basket_becomes_sale_lines_at_the_price_shown(shop):
    _, books = shop
    basket = Basket()
    basket.add(books["malgudi"])
    basket.add(books["train"])
    basket.more(books["malgudi"]["book_id"])
    assert basket.sale_lines() == [
        SaleLine(books["malgudi"]["book_id"], 2, 30_000),
        SaleLine(books["train"]["book_id"], 1, 35_000),
    ]


# ---------- When the sale is recorded ----------

def test_recorded_as_now_says_nothing():
    assert recorded_as(None, NOW) == ""            # a sale for now needs no line


def test_recorded_as_an_earlier_time():
    assert recorded_as(datetime(2026, 11, 10, 9, 5), NOW) == "Recorded as Tuesday 10 Nov, 09:05."


# ---------- Recent sales ----------

def test_recent_sales_list_every_sale_with_copies(shop):
    conn, books = shop
    first = record_sale(conn, [SaleLine(books["malgudi"]["book_id"], 2, 30_000)],
                        sale_datetime=datetime(2026, 10, 1, 10, 0), now=NOW)
    second = record_sale(conn, [SaleLine(books["train"]["book_id"], 1, 35_000)], now=NOW)
    cancel_sale(conn, second, "Rang up twice", now=NOW)
    rows = latest_sales(conn, limit=10)                       # no start date: all of them
    assert [(row["sale_id"], row["copies"], row["status"]) for row in rows] == [
        (second, 1, "cancelled"), (first, 2, "completed"),
    ]
