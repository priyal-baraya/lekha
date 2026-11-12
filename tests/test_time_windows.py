"""Tests for the exact time windows behind Overview's figures:
today so far, the same time last week, the week so far, the period
before, and how many days of sales history a shop has.

Each test records its own sales at known times, so the expected numbers
can be worked out by reading the test.
"""

from datetime import date, datetime

import pytest

from services.analytics import (
    Period,
    days_of_history,
    previous_period,
    same_time_last_week,
    today_so_far,
    week_so_far,
)
from services.books import BookInput, add_book
from services.sales import SaleLine, cancel_sale, record_sale

NOW = datetime(2026, 11, 12, 16, 45)        # Thursday afternoon
PRICE = 30_000                              # ₹300 a copy


@pytest.fixture
def shop(empty_db):
    book = add_book(empty_db, BookInput(title="Malgudi Days", author="R. K. Narayan", genre="Fiction",
                                        selling_price="300", stock_quantity=100))

    def sell(when: datetime, copies: int = 1) -> int:
        return record_sale(empty_db, [SaleLine(book, copies, PRICE)], sale_datetime=when, now=NOW)

    sell(datetime(2026, 11, 12, 11, 20))            # today, before now
    sell(datetime(2026, 11, 12, 16, 44), copies=3)  # today, just before now
    sell(datetime(2026, 11, 5, 10, 0), copies=2)    # last Thursday, before this time
    sell(datetime(2026, 11, 5, 16, 45))             # last Thursday, exactly this time: excluded
    sell(datetime(2026, 11, 5, 18, 0), copies=4)    # last Thursday, later: excluded
    sell(datetime(2026, 11, 10, 9, 30))             # Tuesday this week
    sell(datetime(2026, 11, 8, 19, 0))              # Sunday: last week
    cancelled = sell(datetime(2026, 11, 12, 9, 0), copies=5)
    cancel_sale(empty_db, cancelled, "Customer changed their mind")
    return empty_db


def test_today_so_far_counts_completed_sales_up_to_now(shop):
    today = today_so_far(shop, NOW)
    assert (today["revenue_paise"], today["copies"], today["transactions"]) == (120_000, 4, 2)


def test_same_time_last_week_stops_at_the_same_minute(shop):
    then = same_time_last_week(shop, NOW)
    # Only the 10:00 sale: 16:45 itself is the end, and is not included.
    assert (then["revenue_paise"], then["copies"], then["transactions"]) == (60_000, 2, 1)


def test_week_so_far_starts_on_monday(shop):
    week = week_so_far(shop, NOW)
    # Tuesday 09:30 (1 copy) + today's two completed sales (4 copies); Sunday 8 Nov is last week.
    assert (week["revenue_paise"], week["copies"], week["transactions"]) == (150_000, 5, 3)


def test_today_so_far_with_no_sales(empty_db):
    assert today_so_far(empty_db, NOW) == {"revenue_paise": 0, "copies": 0, "transactions": 0}


def test_previous_period_is_the_same_length_just_before():
    last_30 = Period(date(2026, 10, 14), date(2026, 11, 12), "Last 30 days")
    before = previous_period(last_30)
    assert (before.start, before.end) == (date(2026, 9, 14), date(2026, 10, 13))
    assert before.label == "the 30 days before"


def test_previous_period_of_one_day():
    before = previous_period(Period(date(2026, 11, 12), date(2026, 11, 12)))
    assert (before.start, before.end, before.label) == (date(2026, 11, 11), date(2026, 11, 11), "the day before")


def test_days_of_history(shop):
    # First completed sale: Thursday 5 Nov. 5 Nov to 12 Nov is 8 days.
    assert days_of_history(shop, NOW.date()) == 8


def test_days_of_history_with_no_sales(empty_db):
    assert days_of_history(empty_db, NOW.date()) == 0
