"""Tests for services/sentences.py: the one-sentence summaries at the top
of Overview and Insights, and the "Showing 5 of 6" counts under lists.

Every sentence is built from figures by fixed rules, so each case here
names the figures and the exact words they must produce.
"""

import pytest

from services.sentences import insights_sentence, overview_sentence, showing


# ---------- Overview ----------

def test_overview_brand_new_shop():
    assert overview_sentence(total_books=0, has_sales=False, today_revenue_paise=0, low_stock=0) == (
        "Welcome to Lekha. Add your books and record your sales, "
        "and your shop's numbers will start to appear here."
    )


def test_overview_books_but_no_sales_yet():
    assert overview_sentence(total_books=12, has_sales=False, today_revenue_paise=0, low_stock=0) == (
        "Your books are in. Record your first sale on the Sales page, and today's figures will appear here."
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
        "Insights need a little more history. You've recorded 3 sales so far; "
        "trends appear after two weeks of sales."
    )


def test_insights_one_sale_of_history():
    assert insights_sentence(revenue_paise=30_000, previous_revenue_paise=0, sales=1, genres=[],
                             history_days=1, before_label="the 30 days before").startswith(
        "Insights need a little more history. You've recorded 1 sale so far;"
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
