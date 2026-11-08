"""Tests that run the pages themselves, without a browser.

Streamlit's AppTest loads a page script, runs it like a real visit, and
lets the test read what was drawn and click widgets. Each test points
Lekha at its own temporary database through LEKHA_DB_PATH (an empty shop,
or a copy of the fictional sample data the tests' expected numbers refer
to), so the real data/lekha.db is never touched.
"""

import json
import urllib.parse
from pathlib import Path

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from database import get_connection, reset_empty, reset_with_sample_data
from services import openlibrary

PROJECT = Path(__file__).parent.parent
TIMEOUT = 30  # seconds per run; the first run imports pandas and Altair


@pytest.fixture
def sample_file(tmp_path, monkeypatch):
    """A fresh sample database file, and Lekha pointed at it."""
    path = tmp_path / "lekha.db"
    reset_with_sample_data(path)
    monkeypatch.setenv("LEKHA_DB_PATH", str(path))
    return path


@pytest.fixture
def empty_shop(tmp_path, monkeypatch):
    """A new, empty shop, and Lekha pointed at it."""
    path = tmp_path / "shop.db"
    reset_empty(path)
    monkeypatch.setenv("LEKHA_DB_PATH", str(path))
    return path


@pytest.fixture
def open_library(monkeypatch):
    """Answer Open Library requests with the real responses saved in
    tests/fixtures, and start with an empty cache of lookups."""
    fixtures = Path(__file__).parent / "fixtures"

    def fake_fetch(url):
        url = urllib.parse.unquote(url)
        if "ISBN:9780006550686" in url:
            name = "openlibrary_isbn_9780006550686.json"
        elif "search.json" in url:
            name = "openlibrary_search_god_of_small_things.json"
        else:
            return {}
        return json.loads((fixtures / name).read_text(encoding="utf-8"))

    monkeypatch.setattr(openlibrary, "fetch_json", fake_fetch)
    st.cache_data.clear()
    yield
    st.cache_data.clear()


def run_page(name: str) -> AppTest:
    app = AppTest.from_file(str(PROJECT / "views" / f"{name}.py"), default_timeout=TIMEOUT)
    app.run()
    return app


def all_text(app: AppTest) -> str:
    """Everything the page wrote with markdown, html, info or error boxes."""
    parts = [element.value for element in app.markdown]
    parts += [str(element.proto.body) for element in app.get("html")]
    parts += [element.value for element in app.info] + [element.value for element in app.error]
    return "\n".join(parts)


def stock(path: Path, book_id: int) -> int:
    conn = get_connection(path)
    try:
        return conn.execute("SELECT stock_quantity FROM books WHERE book_id = ?", (book_id,)).fetchone()[0]
    finally:
        conn.close()


# ---------- Every page opens ----------

@pytest.mark.parametrize(
    "page, expected",
    [
        # Overview links to other pages, which only works inside app.py's
        # navigation, so it is tested through app.py below.
        ("books", "Showing <strong>12</strong> of 12 books"),
        ("sales", "The sale is empty"),
        ("inventory", "books need attention"),
        ("insights", "What the numbers suggest"),
    ],
)
def test_page_opens_without_errors(sample_file, page, expected):
    app = run_page(page)
    assert not app.exception, app.exception
    assert not app.error
    text = all_text(app)
    assert expected.replace("<strong>", "**").replace("</strong>", "**") in text or expected in text
    assert "fictional" not in text.lower()          # the app never labels itself as fake data


def test_whole_app_opens_on_overview(sample_file):
    app = AppTest.from_file(str(PROJECT / "app.py"), default_timeout=TIMEOUT)
    app.run()
    assert not app.exception
    assert not app.error
    text = all_text(app)
    assert "Reading between the numbers." in text
    assert "The daily read" in text
    assert "Book data and analytics will come next" not in text   # old message removed


# ---------- The example from the brief, through the real page ----------

def test_selling_two_copies_through_the_sales_page(sample_file):
    assert stock(sample_file, 1) == 8
    app = run_page("sales")

    app.selectbox(key="sale_book_0").set_value(1).run()        # The Monsoon Ledger
    app.number_input(key="sale_qty_0").set_value(2).run()
    app.button(key="sale_add_0").click().run()
    assert "2 copies × ₹399.00 = **₹798.00**" in all_text(app)

    app.button(key="sale_complete_0").click().run()
    assert not app.exception
    assert any("Sale #16 recorded: 2 copies, ₹798.00" in box.value for box in app.success)
    assert stock(sample_file, 1) == 6                           # exactly 2 fewer
    assert "The sale is empty" in all_text(app)                 # basket cleared


def test_out_of_stock_book_cannot_be_added(sample_file):
    app = run_page("sales")
    app.selectbox(key="sale_book_0").set_value(5).run()        # 0 in stock
    assert any("out of stock" in box.value for box in app.warning)
    assert not app.button                                        # no Add button offered


# ---------- Other pages' main actions ----------

def test_search_filters_the_catalogue(sample_file):
    app = run_page("books")
    app.text_input(key="books_search").set_value("menon").run()
    assert "Showing **2** of 12 books" in all_text(app)


def test_stock_correction_through_the_inventory_page(sample_file):
    app = run_page("inventory")
    app.selectbox(key="correct_choice").set_value(1).run()
    # Inside a form, typed values only count when the form is submitted, so
    # type and press Save in the same run, as a person would.
    app.number_input(key="correct_counted_1_0").set_value(5)
    app.button(key="FormSubmitter:correct_form_1_0-Save correction").click().run()
    assert not app.exception
    assert stock(sample_file, 1) == 5
    assert any("changed from 8 to 5" in box.value for box in app.success)


def test_insights_all_time_figures_match_hand_calculations(sample_file):
    app = run_page("insights")
    app.selectbox(key="insights_period").set_value("all_time").run()
    text = all_text(app)
    for figure in ("₹11,144.00", "₹796.00", "₹3,992.00", "Fiction brought in the most revenue"):
        assert figure in text, figure


# ---------- Errors ----------

def test_broken_database_shows_a_friendly_message(tmp_path, monkeypatch):
    broken = tmp_path / "broken.db"
    broken.write_text("this is not a database", encoding="utf-8")
    monkeypatch.setenv("LEKHA_DB_PATH", str(broken))
    app = AppTest.from_file(str(PROJECT / "app.py"), default_timeout=TIMEOUT)
    app.run()
    assert not app.exception                                    # no traceback shown
    assert any("couldn't read or write its database" in box.value for box in app.error)


# ---------- A real, empty shop ----------

def test_empty_shop_overview_explains_where_to_start(empty_shop):
    app = AppTest.from_file(str(PROJECT / "app.py"), default_timeout=TIMEOUT)
    app.run()
    assert not app.exception and not app.error
    text = all_text(app)
    assert "Your shop is empty" in text
    assert "₹0.00" in text                         # real zero, not a made-up figure


def test_empty_shop_books_page_offers_ways_to_add(empty_shop):
    app = run_page("books")
    assert "No books yet" in all_text(app)


def test_adding_a_real_book_by_isbn(empty_shop, open_library):
    app = run_page("books")
    app.session_state["books_tab"] = "Add a book"
    app.run()
    app.radio(key="add_method").set_value("isbn").run()
    app.text_input[0].set_value("978-0-00-655068-6")
    app.button[0].click().run()                    # "Look up"
    assert not app.exception
    text = all_text(app)
    assert "Details from Open Library" in text
    assert "This is the exact edition with this ISBN." in text

    # The form is pre-filled from Open Library; price and stock are ours.
    assert app.text_input(key="add_title_1").value == "The God of Small Things"
    assert app.text_input(key="add_author_1").value == "Arundhati Roy"
    assert app.text_input(key="add_publisher_1").value == "Flamingo"
    assert app.number_input(key="add_year_1").value == 1998
    assert app.selectbox(key="add_genre_1").value == "Fiction"      # suggested from subjects
    assert app.number_input(key="add_price_1").value is None       # never guessed

    app.number_input(key="add_price_1").set_value(399.0)
    app.number_input(key="add_stock_1").set_value(3)
    app.button(key="FormSubmitter:add_book_form_1-Add book").click().run()
    assert not app.exception
    assert any("Added “The God of Small Things”" in box.value for box in app.success)

    conn = get_connection(empty_shop)
    try:
        row = conn.execute("SELECT * FROM books").fetchone()
    finally:
        conn.close()
    assert (row["isbn"], row["publisher"], row["published_year"], row["cover_id"], row["openlibrary_key"]) == (
        "9780006550686", "Flamingo", 1998, 10585942, "/books/OL31903694M")
    assert (row["selling_price_paise"], row["stock_quantity"]) == (39900, 3)


def test_searching_open_library_lists_real_matches(empty_shop, open_library):
    app = run_page("books")
    app.session_state["books_tab"] = "Add a book"
    app.run()
    app.radio(key="add_method").set_value("search").run()
    app.text_input[0].set_value("the god of small things")
    app.button[0].click().run()                    # "Search"
    assert not app.exception
    text = all_text(app)
    assert "5 matches" in text
    assert "Arundhati Roy · first published 1997" in text

    app.button(key="use_result_0").click().run()   # "Use this book"
    text = all_text(app)
    assert "This is the book in general, not a particular edition" in text
    assert app.text_input(key="add_isbn_1").value == ""          # no ISBN guessed for a work
    assert app.text_input(key="add_publisher_1").value == ""     # no edition facts guessed
