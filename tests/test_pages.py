"""Tests that run the pages themselves, without a browser.

Streamlit's AppTest loads a page script, runs it like a real visit, and
lets the test read what was drawn and click widgets. Each test points
Lekha at its own copy of the sample data through LEKHA_DB_PATH, so the
real data/lekha.db is never touched.
"""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from database import get_connection, reset_with_sample_data

PROJECT = Path(__file__).parent.parent
TIMEOUT = 30  # seconds per run; the first run imports pandas and Altair


@pytest.fixture
def sample_file(tmp_path, monkeypatch):
    """A fresh sample database file, and Lekha pointed at it."""
    path = tmp_path / "lekha.db"
    reset_with_sample_data(path)
    monkeypatch.setenv("LEKHA_DB_PATH", str(path))
    return path


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
    assert "Every book and sale shown here is fictional" in text


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
