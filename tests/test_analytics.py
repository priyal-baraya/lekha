"""Tests for services/analytics.py.

Every expected number here was worked out by hand from the fictional
sample data BEFORE the code was written; docs/analytics.md shows the
working. OCT is 1–26 October 2026, the span of the sample sales.
"""

from datetime import date, datetime
from decimal import Decimal

import pytest

from services.analytics import (
    Period,
    best_sellers,
    gross_profit,
    observations,
    percent,
    period_for,
    revenue_by_genre,
    revenue_over_time,
    summary,
    unsold_books,
)
from services.inventory import low_stock_books
from services.sales import SaleLine, cancel_sale, record_sale

OCT = Period(date(2026, 10, 1), date(2026, 10, 26), "Sample span")
TODAY = date(2026, 11, 8)


# ---------- Headline figures ----------

def test_summary_all_genres(sample_db):
    totals = summary(sample_db, OCT)
    assert totals["revenue_paise"] == 1_114_400
    assert totals["copies"] == 29
    assert totals["transactions"] == 14
    assert totals["average_sale_paise"] == 79_600      # 1,114,400 / 14 exactly


def test_summary_one_genre(sample_db):
    # Mystery: book 3 in sales 1, 6, 15 and book 8 in sales 6, 12 -> 4 sales.
    totals = summary(sample_db, OCT, genre="Mystery")
    assert (totals["revenue_paise"], totals["copies"], totals["transactions"]) == (203_400, 6, 4)


def test_summary_empty_period_is_zero(sample_db):
    totals = summary(sample_db, Period(date(2026, 9, 1), date(2026, 9, 30)))
    assert totals == {"revenue_paise": 0, "copies": 0, "transactions": 0, "average_sale_paise": 0}


def test_cancelled_sale_never_counts(sample_db):
    # Sale 9 (cancelled, 79,900) falls on 14 Oct.
    week = Period(date(2026, 10, 12), date(2026, 10, 18))
    assert summary(sample_db, week)["revenue_paise"] == 324_600   # sales 8, 10, 11 only


# ---------- Date boundaries ----------

def test_sale_at_last_second_is_in_and_next_midnight_is_out(sample_db):
    now = datetime(2026, 11, 8, 12, 0, 0)
    record_sale(sample_db, [SaleLine(1, 1, 39900)], sale_datetime=datetime(2026, 10, 26, 23, 59, 59), now=now)
    record_sale(sample_db, [SaleLine(1, 1, 39900)], sale_datetime=datetime(2026, 10, 27, 0, 0, 0), now=now)
    assert summary(sample_db, OCT)["revenue_paise"] == 1_114_400 + 39_900


def test_new_sale_and_its_cancellation_move_the_figures(sample_db):
    now = datetime(2026, 10, 20, 9, 0, 0)
    sale_id = record_sale(sample_db, [SaleLine(2, 1, 55000)], sale_datetime=now, now=now)
    assert summary(sample_db, OCT)["revenue_paise"] == 1_114_400 + 55_000
    cancel_sale(sample_db, sale_id, "Test", now=now)
    assert summary(sample_db, OCT)["revenue_paise"] == 1_114_400


# ---------- Genres ----------

def test_revenue_by_genre(sample_db):
    rows = revenue_by_genre(sample_db, OCT)
    assert [(row["genre"], row["revenue_paise"], row["share_percent"]) for row in rows] == [
        ("Fiction", 404_000, Decimal("36.3")),
        ("Mystery", 203_400, Decimal("18.3")),
        ("Children", 172_200, Decimal("15.5")),
        ("Cookery", 165_000, Decimal("14.8")),
        ("History", 119_800, Decimal("10.8")),
        ("Poetry", 50_000, Decimal("4.5")),
    ]
    assert sum(row["revenue_paise"] for row in rows) == 1_114_400
    # Rounded shares add up to 100.2, not 100: rounding, not an error.
    assert sum(row["share_percent"] for row in rows) == Decimal("100.2")


@pytest.mark.parametrize(
    "part, whole, expected",
    [(404_000, 1_114_400, "36.3"), (1, 3, "33.3"), (1, 8, "12.5"), (0, 0, "0.0"), (5, 5, "100.0")],
)
def test_percent(part, whole, expected):
    assert percent(part, whole) == Decimal(expected)


# ---------- Best sellers ----------

def test_best_sellers_share_ranks_on_ties(sample_db):
    rows = best_sellers(sample_db, OCT)
    assert [(row["book_id"], row["copies"], row["copies_rank"]) for row in rows] == [
        (1, 6, 1),
        (5, 4, 2),
        (2, 3, 3), (3, 3, 3), (8, 3, 3), (7, 3, 3), (9, 3, 3),   # tied; then by revenue
        (6, 2, 8), (4, 2, 8),                                   # rank 8, not 4
    ]
    revenue = {row["book_id"]: row["revenue_paise"] for row in rows}
    assert revenue == {1: 224_400, 2: 165_000, 3: 104_700, 4: 50_000, 5: 179_600,
                       6: 119_800, 7: 89_700, 8: 98_700, 9: 82_500}
    assert sum(revenue.values()) == 1_114_400


def test_best_sellers_respect_genre(sample_db):
    rows = best_sellers(sample_db, OCT, genre="Children")
    assert [(row["book_id"], row["copies"], row["copies_rank"]) for row in rows] == [(7, 3, 1), (9, 3, 1)]


# ---------- Unsold ----------

def test_unsold_books_all_time(sample_db):
    assert [row["book_id"] for row in unsold_books(sample_db, OCT)] == [12, 11, 10]


def test_unsold_books_short_period(sample_db):
    first_days = Period(date(2026, 10, 1), date(2026, 10, 4))   # sales 1–3: books 1, 2, 3, 7, 9
    assert sorted(row["book_id"] for row in unsold_books(sample_db, first_days)) == [4, 5, 6, 8, 10, 11, 12]


def test_unsold_books_respect_genre(sample_db):
    assert [row["book_id"] for row in unsold_books(sample_db, OCT, genre="Poetry")] == [11]


# ---------- Profit ----------

def test_estimated_gross_profit(sample_db):
    profit = gross_profit(sample_db, OCT)
    assert profit["revenue_paise"] == 1_114_400
    assert profit["revenue_with_cost_paise"] == 1_024_700        # book 7 has no cost
    assert profit["estimated_gross_profit_paise"] == 399_200
    assert profit["coverage_percent"] == Decimal("92.0")
    assert profit["margin_percent"] == Decimal("39.0")


# ---------- Over time ----------

def test_weekly_revenue_with_partial_weeks(sample_db):
    table = revenue_over_time(sample_db, OCT, "week", today=TODAY)
    assert [str(start) for start in table["bucket_start"]] == [
        "2026-09-28", "2026-10-05", "2026-10-12", "2026-10-19", "2026-10-26"]
    assert list(table["revenue_paise"]) == [247_000, 232_500, 324_600, 275_400, 34_900]
    # First week starts before 1 Oct; last week runs past 26 Oct.
    assert list(table["partial"]) == [True, False, False, False, True]
    assert table["revenue_paise"].sum() == 1_114_400


def test_daily_revenue_fills_empty_days_with_zero(sample_db):
    week = Period(date(2026, 10, 1), date(2026, 10, 7))
    table = revenue_over_time(sample_db, week, "day", today=TODAY)
    assert len(table) == 7
    assert list(table["revenue_paise"]) == [104_700, 55_000, 0, 87_300, 34_900, 0, 69_900]
    assert not table["partial"].any()


def test_monthly_revenue(sample_db):
    table = revenue_over_time(sample_db, OCT, "month", today=TODAY)
    assert list(table["revenue_paise"]) == [1_114_400]
    assert list(table["partial"]) == [True]          # 26 Oct isn't the end of October


def test_bucket_including_today_is_marked_partial(sample_db):
    period = Period(date(2026, 10, 1), TODAY)        # "all time" on 8 Nov
    table = revenue_over_time(sample_db, period, "week", today=TODAY)
    assert str(table["bucket_start"].iloc[-1]) == "2026-11-02"
    assert table["revenue_paise"].iloc[-1] == 0
    assert bool(table["partial"].iloc[-1]) is True   # this week isn't over
    assert bool(table["partial"].iloc[-2]) is False  # week of 26 Oct is complete


def test_period_with_no_sales_gives_zero_buckets(sample_db):
    table = revenue_over_time(sample_db, Period(date(2026, 9, 1), date(2026, 9, 30)), "week", today=TODAY)
    assert table["revenue_paise"].sum() == 0
    assert len(table) == 5   # weeks starting 31 Aug, 7, 14, 21, 28 Sep


# ---------- Periods ----------

@pytest.mark.parametrize(
    "choice, start, end",
    [
        ("last_7", date(2026, 11, 2), date(2026, 11, 8)),
        ("last_30", date(2026, 10, 10), date(2026, 11, 8)),
        ("this_month", date(2026, 11, 1), date(2026, 11, 8)),
        ("last_month", date(2026, 10, 1), date(2026, 10, 31)),
        ("all_time", date(2026, 10, 1), date(2026, 11, 8)),
    ],
)
def test_period_for(sample_db, choice, start, end):
    period = period_for(sample_db, choice, TODAY)
    assert (period.start, period.end) == (start, end)


def test_last_month_in_january(sample_db):
    period = period_for(sample_db, "last_month", date(2027, 1, 15))
    assert (period.start, period.end) == (date(2026, 12, 1), date(2026, 12, 31))


def test_custom_period_must_be_in_order(sample_db):
    with pytest.raises(ValueError):
        period_for(sample_db, "custom", TODAY, (date(2026, 10, 5), date(2026, 10, 1)))


def test_period_bounds_text():
    assert OCT.start_text == "2026-10-01 00:00:00"
    assert OCT.end_exclusive_text == "2026-10-27 00:00:00"


# ---------- Observations ----------

def test_observations_on_sample_data(sample_db):
    found = observations(sample_db, OCT, low_stock=low_stock_books(sample_db))
    titles = [item.title for item in found]
    assert titles == [
        "Fiction brought in the most revenue",
        "“The Monsoon Ledger” sold the most copies",
        "Selling, and low on stock",
        "On the shelf, no sales this period",
    ]
    genre = found[0]
    assert genre.evidence == "₹4,040.00 of ₹11,144.00 (36.3%) across 14 sales."
    assert "doesn't show that a display would increase sales" in genre.limits[0]
    assert "Only 14 sales in this period" in genre.limits[1]
    assert "“Salt and Saffron”" in found[2].evidence      # books 2, 5 and 9 sold and are low
    assert "13 copies in stock" in found[3].evidence     # books 12 (6), 11 (4), 10 (3)


def test_tied_best_sellers_are_reported_as_a_tie(sample_db):
    # Both sold 3 copies; tied books are listed by revenue, and
    # The Clockmaker's Cat (89,700) out-earned Ten Thousand Mangoes (82,500).
    found = observations(sample_db, OCT, genre="Children")
    assert found[0].title == "“The Clockmaker's Cat” and “Ten Thousand Mangoes” tied as best sellers"


def test_no_sales_gives_one_honest_observation(sample_db):
    found = observations(sample_db, Period(date(2026, 9, 1), date(2026, 9, 30)))
    assert [item.title for item in found] == ["No completed sales in this period"]
