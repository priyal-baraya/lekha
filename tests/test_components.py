"""Tests for the redesign building blocks in ui/components.py.

Each block is built as an HTML string first (the *_html functions), so
these tests can check the exact markup without running Streamlit.
"""

from services.comparisons import Comparison
from ui.components import (
    Figure,
    card_heading_html,
    cover_letter_html,
    figure_strip_html,
    page_header_html,
    status_html,
    step_html,
    summary_header_html,
    wordmark_html,
)


# ---------- Page headers ----------

def test_page_header_has_one_h1_and_no_label_above():
    html = page_header_html("Books", "Every book in your shop, with your own price and stock.")
    assert html.count("<h1") == 1
    assert '<h1 class="lekha-pagehead__title">Books</h1>' in html
    assert "eyebrow" not in html


def test_summary_header_escapes_names():
    html = summary_header_html("Thursday 12 November · <Kitab & Ghar>", "₹1,250 in sales so far today.")
    assert "&lt;Kitab &amp; Ghar&gt;" in html
    assert '<h1 class="lekha-pagehead__summary">₹1,250 in sales so far today.</h1>' in html


# ---------- Figure strip ----------

def test_figure_with_a_good_change_has_a_drawn_arrow():
    html = figure_strip_html([Figure("Revenue", "₹48,250", Comparison("12% more than ₹43,080", "good"))])
    assert '<p class="lekha-figure__value">₹48,250</p>' in html
    assert 'class="lekha-change lekha-change--good"' in html
    assert 'lekha-change__arrow' in html
    assert "12% more than ₹43,080" in html


def test_neutral_change_has_no_arrow():
    html = figure_strip_html([Figure("Average per sale", "₹292", Comparison("₹308 before", "neutral"))])
    assert "lekha-change--neutral" in html
    assert "lekha-change__arrow" not in html


def test_missing_figure_is_a_dash_that_screen_readers_hear_as_no_data():
    html = figure_strip_html([Figure("Revenue", None)])
    assert '<span aria-hidden="true">—</span>' in html
    assert "No data yet" in html


def test_figure_in_words_uses_the_smaller_style():
    html = figure_strip_html([Figure("Today", "No sales yet", words=True)])
    assert "lekha-figure__value lekha-figure__value--words" in html


def test_figure_text_is_escaped():
    html = figure_strip_html([Figure("<b>Revenue</b>", "₹1", note="2 sales · <script>")])
    assert "<b>" not in html and "<script>" not in html
    assert "&lt;b&gt;Revenue&lt;/b&gt;" in html


def test_unknown_tone_is_refused():
    try:
        figure_strip_html([Figure("Revenue", "₹1", Comparison("up", "great"))])
    except ValueError:
        return
    raise AssertionError("an unknown tone should raise ValueError")


# ---------- Small pieces ----------

def test_status_tag():
    assert status_html("warning", "Low") == '<span class="lekha-status lekha-status--warning">Low</span>'


def test_status_tag_refuses_unknown_kinds():
    try:
        status_html("loud", "Low")
    except ValueError:
        return
    raise AssertionError("an unknown kind should raise ValueError")


def test_waiting_step():
    html = step_html(3, "See your trends", "After two weeks of sales.", waiting=True)
    assert 'class="lekha-step lekha-step--waiting"' in html
    assert '<span class="lekha-step__number" aria-hidden="true">3</span>' in html


def test_cover_letter_uses_the_first_letter_and_names_the_book():
    html = cover_letter_html("ghachar Ghochar")
    assert ">G</span>" in html
    assert 'aria-label="No cover: ghachar Ghochar"' in html


def test_cover_letter_for_a_title_starting_with_a_symbol():
    assert '>"</span>' not in cover_letter_html('"Quoted" title')
    assert ">Q</span>" in cover_letter_html('"Quoted" title')


# ---------- Sign in and Get started ----------

def test_wordmark_is_the_one_h1_with_its_tagline():
    html = wordmark_html("Lekha", "Reading between the numbers.")
    assert html.count("<h1") == 1
    assert '<h1 class="lekha-wordmark__name">Lekha</h1>' in html
    assert '<p class="lekha-wordmark__tagline">Reading between the numbers.</p>' in html


def test_card_heading_is_an_h2_with_a_short_description():
    html = card_heading_html("Start a shop", "You'll own it & can invite staff.")
    assert '<h2 class="lekha-cardhead__title">Start a shop</h2>' in html
    assert "You&#x27;ll own it &amp; can invite staff." in html
    assert "eyebrow" not in html and "<h1" not in html

