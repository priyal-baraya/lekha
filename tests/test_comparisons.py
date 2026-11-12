"""Tests for services/comparisons.py and the whole-rupee format.

The rules come from the design review (docs/decision-log.md, 2026-11-12):
compare like with like, show no change when there's nothing fair to
compare against, and colour a change only where "up" is good.
"""

import pytest

from services.comparisons import (
    before_money,
    compare_count,
    compare_money,
    same_time_last_week,
)
from services.money import format_rupees_whole


# ---------- Whole rupees ----------

@pytest.mark.parametrize("paise, text", [
    (0, "₹0"),
    (30_800, "₹308"),
    (34_999, "₹350"),            # rounds half up to the nearest rupee
    (34_949, "₹349"),
    (4_308_000, "₹43,080"),
    (11_144_400, "₹1,11,444"),   # Indian grouping, as in format_rupees
    (124_583_050, "₹12,45,831"),
])
def test_format_rupees_whole(paise, text):
    assert format_rupees_whole(paise) == text


# ---------- Money ----------

def test_money_up_is_good():
    change = compare_money(4_825_000, 4_308_000)            # ₹48,250 against ₹43,080
    assert (change.text, change.tone) == ("12% more than ₹43,080", "good")


def test_money_down_is_bad():
    change = compare_money(90_000, 100_000)
    assert (change.text, change.tone) == ("10% less than ₹1,000", "bad")


def test_money_tiny_change_is_about_the_same():
    change = compare_money(100_400, 100_000)                # 0.4%
    assert (change.text, change.tone) == ("About the same as ₹1,000", "neutral")


def test_money_percent_rounds_half_up():
    assert compare_money(102_500, 100_000).text == "3% more than ₹1,000"    # 2.5% -> 3%


@pytest.mark.parametrize("current, previous", [(50_000, 0), (0, 0)])
def test_money_nothing_to_compare_shows_no_change(current, previous):
    assert compare_money(current, previous) is None


def test_money_from_something_to_nothing():
    change = compare_money(0, 50_000)
    assert (change.text, change.tone) == ("100% less than ₹500", "bad")


# ---------- Counts ----------

def test_count_as_percent():
    change = compare_count(186, 172)
    assert (change.text, change.tone) == ("8% more than 172", "good")


def test_count_down_says_fewer():
    change = compare_count(90, 100)
    assert (change.text, change.tone) == ("10% fewer than 100", "bad")


def test_count_as_difference():
    assert compare_count(165, 140, by="difference").text == "25 more than 140"
    assert compare_count(138, 140, by="difference").text == "2 fewer than 140"
    assert compare_count(140, 140, by="difference").text == "The same as before"


def test_count_nothing_to_compare_shows_no_change():
    assert compare_count(5, 0) is None


# ---------- Neutral comparisons ----------

def test_before_money_is_neutral():
    change = before_money(30_800)
    assert (change.text, change.tone) == ("₹308 before", "neutral")


def test_before_money_with_nothing_before():
    assert before_money(0) is None


def test_same_time_last_week():
    change = same_time_last_week(162_000, "Wednesday")
    assert (change.text, change.tone) == ("₹1,620 by this time last Wednesday", "neutral")


def test_same_time_last_week_with_no_sales_then():
    change = same_time_last_week(0, "Wednesday")
    assert (change.text, change.tone) == ("No sales by this time last Wednesday", "neutral")
