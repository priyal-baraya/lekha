"""Tests for the redesign building blocks in ui/components.py.

Each block is built as an HTML string first (the *_html functions), so
these tests can check the exact markup without running Streamlit.
"""

import pytest

from services.comparisons import Comparison
from ui.components import (
    Figure,
    Html,
    ShelfBook,
    book_cell_html,
    BookRow,
    book_list_html,
    book_rows_html,
    card_heading_html,
    cover_letter_html,
    figure_strip_html,
    data_table_html,
    page_header_html,
    shelf_html,
    status_html,
    stock_status_html,
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


def test_page_header_without_a_description():
    html = page_header_html("Books")
    assert "lekha-pagehead__description" not in html


def test_summary_header_without_a_date_line():
    html = summary_header_html("", "Welcome to Lekha!")
    assert "lekha-pagehead__meta" not in html and ">Welcome to Lekha!</h1>" in html


def test_card_heading_without_a_description():
    html = card_heading_html("Latest sales")
    assert "lekha-cardhead__description" not in html and ">Latest sales</h2>" in html


def test_step_without_an_explanation():
    html = step_html(1, "Add your first book")
    assert "lekha-step__text" not in html and "Add your first book" in html


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


# ---------- Overview: tables, book cells and the shelf ----------

def test_table_escapes_plain_values_and_keeps_built_html():
    html = data_table_html(
        [("Book", "left"), ("In stock", "right")],
        [["<script>x</script>", 0], [Html('<span class="lekha-status">Low</span>'), 2]],
    )
    assert "&lt;script&gt;x&lt;/script&gt;" in html and "<script>" not in html
    assert '<span class="lekha-status">Low</span>' in html
    assert '<th scope="col" class="lekha-table__num">In stock</th>' in html
    assert '<td class="lekha-table__num">0</td>' in html


def test_book_cell_with_a_cover_has_an_empty_alt():
    html = book_cell_html("Malgudi Days", "R. K. Narayan", "https://covers.openlibrary.org/b/id/1-S.jpg")
    assert 'alt=""' in html and 'loading="lazy"' in html      # the title is right beside it
    assert "lekha-cover-letter" not in html


def test_book_cell_without_a_cover_shows_its_letter_and_escapes():
    html = book_cell_html("<Godaan>", "Premchand", None)
    assert "lekha-cover-letter" in html and "&lt;Godaan&gt;" in html and "<img" not in html


def test_shelf_marks_sold_out_books_in_words():
    html = shelf_html([ShelfBook("Gitanjali", 4, None, sold_out=True), ShelfBook("Godaan", 1, None)])
    assert html.count("Sold out") == 1
    assert "4 sold" in html and "1 sold" in html


def test_book_list_for_phones_says_stock_in_words():
    html = book_list_html([("Gitanjali", None, 0, 3), ("The <Guide>", "https://covers.openlibrary.org/b/id/1-S.jpg", 1, 4)])
    assert "0 left · reorder at 3" in html and "1 left · reorder at 4" in html
    assert html.count("Out of stock") == 1 and html.count(">Low<") == 1
    assert "The &lt;Guide&gt;" in html


@pytest.mark.parametrize(
    "stock, reorder, kind, words",
    [(0, 3, "error", "Out of stock"), (2, 3, "warning", "Low"), (3, 3, "warning", "Low"), (5, 3, "success", "In stock")],
)
def test_stock_status_in_words(stock, reorder, kind, words):
    assert stock_status_html(stock, reorder) == f'<span class="lekha-status lekha-status--{kind}">{words}</span>'


def test_book_rows_for_phones_escape_their_details():
    html = book_rows_html([BookRow("Godaan", None, "Premchand · ₹250 · <3> in stock", stock_status_html(3, 3))])
    assert "Premchand · ₹250 · &lt;3&gt; in stock" in html and ">Low<" in html

