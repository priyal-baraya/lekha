"""Tests for services/sentences.py: the one-sentence summaries at the top
of Overview and Insights, and the "Showing 5 of 6" counts under lists.

Every sentence is built from figures by fixed rules, so each case here
names the figures and the exact words they must produce.
"""

from decimal import Decimal

import pytest

from services.sentences import (
    catalogue_note,
    correction_hint,
    insights_sentence,
    low_stock_note,
    overview_sentence,
    profit_note,
    showing,
)


# ---------- Overview ----------

def test_overview_brand_new_shop():
    assert overview_sentence(total_books=0, has_sales=False, today_revenue_paise=0, low_stock=0) == (
        "Welcome to Lekha!"
    )


def test_overview_books_but_no_sales_yet():
    assert overview_sentence(total_books=12, has_sales=False, today_revenue_paise=0, low_stock=0) == (
        "Your books are in. Record your first sale."
    )


@pytest.mark.parametrize("revenue, low, sentence", [
    (125_000, 6, "₹1,250 in sales so far today, and 6 books need reordering."),
    (125_000, 1, "₹1,250 in sales so far today, and 1 book needs reordering."),
    (125_000, 0, "₹1,250 in sales so far today, and nothing needs reordering."),
    (0, 6, "No sales yet today, and 6 books need reordering."),
    (0, 0, "No sales yet today, and nothing needs reordering."),
    (10_456_000, 137, "₹1,04,560 in sales so far today, and 137 books need reordering."),
])
def test_overview_today(revenue, low, sentence):
    assert overview_sentence(total_books=40, has_sales=True, today_revenue_paise=revenue, low_stock=low) == sentence


# ---------- Insights ----------

GENRES = [("Fiction", 46), ("Poetry", 29), ("History", 19)]


def test_insights_no_sales_in_period():
    assert insights_sentence(revenue_paise=0, previous_revenue_paise=0, sales=0, genres=[],
                             history_days=40, before_label="the 30 days before") == (
        "No completed sales in this period. Try a longer one."
    )


def test_insights_too_little_history():
    assert insights_sentence(revenue_paise=184_900, previous_revenue_paise=0, sales=3, genres=GENRES,
                             history_days=3, before_label="the 30 days before") == (
        "Trends appear after two weeks of sales."
    )


def test_insights_one_sale_of_history():
    assert insights_sentence(revenue_paise=30_000, previous_revenue_paise=0, sales=1, genres=[],
                             history_days=1, before_label="the 30 days before") == (
        "Trends appear after two weeks of sales."
    )


def test_insights_rise_with_top_genre():
    assert insights_sentence(revenue_paise=4_825_000, previous_revenue_paise=4_308_000, sales=165,
                             genres=GENRES, history_days=90, before_label="the 30 days before") == (
        "Revenue rose 12% on the 30 days before, and Fiction brought in 46% of it."
    )


def test_insights_fall():
    assert insights_sentence(revenue_paise=90_000, previous_revenue_paise=100_000, sales=20,
                             genres=GENRES, history_days=90, before_label="the 30 days before") == (
        "Revenue fell 10% on the 30 days before, and Fiction brought in 46% of it."
    )


def test_insights_about_the_same_with_one_genre():
    assert insights_sentence(revenue_paise=100_400, previous_revenue_paise=100_000, sales=20,
                             genres=[("Fiction", 100)], history_days=90, before_label="last month") == (
        "Revenue was about the same as last month."
    )


def test_insights_nothing_to_compare_against():
    assert insights_sentence(revenue_paise=4_825_000, previous_revenue_paise=0, sales=165,
                             genres=GENRES, history_days=20, before_label="the 30 days before") == (
        "₹48,250 in revenue, and Fiction brought in 46% of it."
    )


# ---------- "Showing 5 of 6" ----------

@pytest.mark.parametrize("shown, total, text", [
    (5, 6, "Showing 5 of 6."),
    (5, 137, "Showing 5 of 137."),
    (6, 6, "All 6 shown."),
    (4, 4, "All 4 shown."),
    (1, 1, ""),
    (0, 0, ""),
])
def test_showing(shown, total, text):
    assert showing(shown, total) == text


@pytest.mark.parametrize(
    "shown, matched, total, text",
    [
        (12, 12, 12, "12 books."),
        (1, 1, 1, "1 book."),
        (2, 2, 12, "Showing 2 of 12 books."),
        (100, 2000, 2000, "Showing the first 100 of 2,000 books. Search to find the rest."),
        (100, 150, 2000, "Showing the first 100 of 150 matches. Type more to narrow it."),
        (0, 0, 12, "No books match. Try fewer letters, or choose All genres."),
    ],
)
def test_catalogue_note(shown, matched, total, text):
    assert catalogue_note(shown, matched, total) == text


@pytest.mark.parametrize("count, text", [(1, "1 book."), (6, "All 6 shown, emptiest first.")])
def test_low_stock_note(count, text):
    assert low_stock_note(count) == text


@pytest.mark.parametrize(
    "current, counted, text",
    [
        (3, 2, "Lekha has 3 in stock, so it will record a change of −1."),   # a real minus sign
        (3, 9, "Lekha has 3 in stock, so it will record a change of +6."),
        (4, 4, "Lekha has 4 in stock too, so there's nothing to record."),
    ],
)
def test_correction_hint(current, counted, text):
    assert correction_hint(current, counted) == text


# ---------- Insights: the line under estimated gross profit ----------

@pytest.mark.parametrize(("coverage", "expected"), [
    (Decimal("100.0"), "Rent and wages aren't included."),
    (Decimal("92.0"), "From the 92% of revenue with a cost recorded. Rent and wages aren't included."),
    (Decimal("36.3"), "From the 36.3% of revenue with a cost recorded. Rent and wages aren't included."),
    (Decimal("0.0"), "No books have a cost recorded yet."),
])
def test_profit_note(coverage, expected):
    assert profit_note(coverage) == expected
