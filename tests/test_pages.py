"""Tests that run the pages themselves, without a browser.

Streamlit's AppTest loads a page script, runs it like a real visit, and
lets the test read what was drawn and click widgets.

Two kinds of test:
  * single pages (views/*.py) run on one temporary shop database through
    LEKHA_DB_PATH, with the visitor's role set directly;
  * the whole app (app.py), with sign-in, shops and roles, runs on a
    temporary data folder through LEKHA_DATA_DIR.
The real data/ folder is never touched.
"""

import json
import re
import time
import urllib.parse
from pathlib import Path

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from database import connect, connect_accounts, ensure_shop_database, get_connection, reset_empty, reset_with_sample_data
from services import accounts, limits, openlibrary
from services.books import BookInput, add_book
from ui import session

PROJECT = Path(__file__).parent.parent
TIMEOUT = 30  # seconds per run; the first run imports pandas and Altair
PASSWORD = "correct horse battery"


# ---------------------------------------------------------------- fixtures

@pytest.fixture
def sample_file(tmp_path, monkeypatch):
    """A fresh copy of the fictional test dataset, and Lekha pointed at it."""
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
def data_dir(tmp_path, monkeypatch):
    """An empty data folder for whole-app tests (accounts and shop files)."""
    monkeypatch.setenv("LEKHA_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("LEKHA_DB_PATH", raising=False)
    return tmp_path


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


# ----------------------------------------------------------------- helpers

def run_page(name: str, role: str = "owner", user_id: int | None = None) -> AppTest:
    """Run one page as someone with this role in the shop."""
    app = AppTest.from_file(str(PROJECT / "views" / f"{name}.py"), default_timeout=TIMEOUT)
    app.session_state[session.ROLE] = role
    if user_id is not None:
        app.session_state[session.USER] = user_id
    app.run()
    return app


def run_app(user_id: int | None = None) -> AppTest:
    """Run the whole app, optionally as an already signed-in person."""
    app = AppTest.from_file(str(PROJECT / "app.py"), default_timeout=TIMEOUT)
    if user_id is not None:
        app.session_state[session.USER] = user_id
        app.session_state[session.METHOD] = "password"
        with connect_accounts() as acc:    # what sign_in() remembers about the password
            app.session_state[session.STAMP] = accounts.credential_stamp(acc, user_id)
    app.run()
    return app


def shown(markdown: str) -> str:
    """Markdown as a person reads it: without the backslashes that ui.plain()
    adds so names and titles show exactly as typed."""
    return re.sub(r"\\(.)", r"\1", markdown).replace("⁠", "")


def all_text(app: AppTest) -> str:
    """Everything the page wrote with markdown, html, info, success or error boxes."""
    parts = [element.value for element in app.markdown]
    parts += [str(element.proto.body) for element in app.get("html")]
    parts += [box.value for box in [*app.info, *app.error, *app.success]]
    return shown("\n".join(parts))


def field(app: AppTest, label: str):
    return next(widget for widget in app.text_input if widget.label == label)


def stock(path: Path, book_id: int) -> int:
    conn = get_connection(path)
    try:
        return conn.execute("SELECT stock_quantity FROM books WHERE book_id = ?", (book_id,)).fetchone()[0]
    finally:
        conn.close()


def person_with_shop(username: str, shop_name: str) -> tuple[int, int]:
    with connect_accounts() as acc:
        user_id = accounts.create_user(acc, username, username.title(), PASSWORD)
        shop_id = accounts.create_shop(acc, user_id, shop_name)
    ensure_shop_database(shop_id)
    return user_id, shop_id


# ---------- Every page opens (as an owner) ----------

@pytest.mark.parametrize(
    "page, expected",
    [
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


# ---------- The example from the brief, through the real page ----------

def test_selling_two_copies_through_the_sales_page(sample_file):
    assert stock(sample_file, 1) == 8
    app = run_page("sales", role="staff", user_id=5)            # staff may sell

    app.selectbox(key="sale_book_0").set_value(1).run()        # The Monsoon Ledger
    app.number_input(key="sale_qty_0").set_value(2).run()
    app.button(key="sale_add_0").click().run()
    assert "2 copies × ₹399.00 = **₹798.00**" in all_text(app)

    app.button(key="sale_complete_0").click().run()
    assert not app.exception
    assert any("Sale #16 recorded: 2 copies, ₹798.00" in shown(box.value) for box in app.success)
    assert stock(sample_file, 1) == 6                           # exactly 2 fewer
    assert "The sale is empty" in all_text(app)                 # basket cleared
    conn = get_connection(sample_file)
    try:
        assert conn.execute("SELECT recorded_by FROM sales WHERE sale_id = 16").fetchone()[0] == 5
    finally:
        conn.close()


def test_out_of_stock_book_cannot_be_added(sample_file):
    app = run_page("sales")
    app.selectbox(key="sale_book_0").set_value(5).run()        # 0 in stock
    assert any("out of stock" in shown(box.value) for box in app.warning)
    assert not app.button                                        # no Add button offered


# ---------- Other pages' main actions ----------

def test_search_filters_the_catalogue(sample_file):
    app = run_page("books")
    app.text_input(key="books_search").set_value("menon").run()
    assert "Showing **2** of 12 books" in all_text(app)


def test_stock_correction_through_the_inventory_page(sample_file):
    app = run_page("inventory", user_id=3)
    app.selectbox(key="correct_choice").set_value(1).run()
    # Inside a form, typed values only count when the form is submitted, so
    # type and press Save in the same run, as a person would.
    app.number_input(key="correct_counted_1_0").set_value(5)
    app.button(key="FormSubmitter:correct_form_1_0-Save correction").click().run()
    assert not app.exception
    assert stock(sample_file, 1) == 5
    assert any("changed from 8 to 5" in shown(box.value) for box in app.success)


def test_insights_all_time_figures_match_hand_calculations(sample_file):
    app = run_page("insights")
    app.selectbox(key="insights_period").set_value("all_time").run()
    text = all_text(app)
    for figure in ("₹11,144.00", "₹796.00", "₹3,992.00", "Fiction brought in the most revenue"):
        assert figure in text, figure


# ---------- What staff can and can't see ----------

def test_staff_cannot_edit_books(sample_file):
    app = run_page("books", role="staff")
    assert [tab.label for tab in app.tabs] == ["Browse", "Add a book"]


def test_staff_cannot_correct_stock(sample_file):
    app = run_page("inventory", role="staff")
    text = all_text(app)
    assert "books need attention" in text                      # can see alerts
    assert "Correct stock" not in text


def test_staff_do_not_see_profit(sample_file):
    app = run_page("insights", role="staff")
    app.selectbox(key="insights_period").set_value("all_time").run()
    text = all_text(app)
    assert "₹11,144.00" in text                                # revenue yes
    assert "Estimated gross profit" not in text and "₹3,992.00" not in text


def test_staff_cannot_open_the_team_page(sample_file):
    app = run_page("team", role="staff", user_id=1)
    assert any("Only the shop's owners can invite and manage the team" in shown(box.value) for box in app.error)


# ---------- Signing in, the whole app ----------

def test_signed_out_visitors_only_see_sign_in(data_dir):
    app = run_app()
    assert not app.exception and not app.error
    text = all_text(app)
    assert "Reading between the numbers." in text
    assert [tab.label for tab in app.tabs] == ["Sign in", "Create an account"]
    assert "The daily read" not in text                        # no shop data without signing in


def test_sign_up_create_a_shop_and_land_on_its_overview(data_dir):
    app = run_app()
    field(app, "Your name").set_value("Priya")
    field(app, "Choose a username").set_value("priya")
    field(app, "Choose a password").set_value(PASSWORD)
    field(app, "Type the password again").set_value(PASSWORD)
    app.button(key="FormSubmitter:sign_up-Create account").click().run()
    assert not app.exception
    assert "Start a shop" in all_text(app)                      # signed in, no shop yet

    field(app, "Shop name").set_value("Kitaab Corner")
    app.button(key="FormSubmitter:create_shop-Create shop").click().run()
    assert not app.exception
    text = all_text(app)
    assert "Kitaab Corner" in text and "Your shop is empty" in text
    assert "Your shop is ready" in text                         # shown here, not on the next page

    with connect_accounts() as acc:
        stored = acc.execute("SELECT password_hash FROM users WHERE username = 'priya'").fetchone()[0]
        assert PASSWORD not in stored
        assert [(m.shop_name, m.role) for m in accounts.memberships(acc, 1)] == [("Kitaab Corner", "owner")]
    assert (data_dir / "shops" / "shop_1.db").exists()


def test_wrong_password_is_refused_on_the_page(data_dir):
    person_with_shop("priya", "Kitaab Corner")
    app = run_app()
    field(app, "Username").set_value("priya")
    field(app, "Password").set_value("not my password")
    app.button(key="FormSubmitter:sign_in-Sign in").click().run()
    assert any("The username or password is incorrect." in shown(box.value) for box in app.error)
    assert session.USER not in app.session_state


def test_people_only_see_their_own_shop(data_dir):
    asha, asha_shop = person_with_shop("asha", "Asha's Books")
    ben, _ = person_with_shop("ben", "Ben's Books")
    with connect(ensure_shop_database(asha_shop)) as conn:
        add_book(conn, BookInput(title="Only at Asha's", author="A", genre="Fiction", selling_price=100))

    text = all_text(run_app(asha))
    assert "Asha's Books" in text and "Your shop is empty" not in text
    text = all_text(run_app(ben))
    assert "Ben's Books" in text and "Your shop is empty" in text
    assert "Only at Asha's" not in text


def test_removed_staff_lose_access_on_their_next_click(data_dir):
    owner, shop = person_with_shop("owner", "Kitaab Corner")
    with connect_accounts() as acc:
        staff = accounts.create_user(acc, "assistant", "Assistant", PASSWORD)
        accounts.redeem_invitation(acc, staff, accounts.create_invitation(acc, owner, shop))
    app = run_app(staff)
    assert "Kitaab Corner" in all_text(app)

    with connect_accounts() as acc:
        accounts.remove_member(acc, owner, shop, staff)
    app.run()                                                   # their next click
    text = all_text(app)
    assert "Start a shop" in text and "Kitaab Corner" not in text


# ---------- Security ----------

def test_changing_the_password_signs_out_other_tabs(data_dir):
    priya, _ = person_with_shop("priya", "Kitaab Corner")
    other_tab = run_app(priya)
    assert "Kitaab Corner" in all_text(other_tab)

    with connect_accounts() as acc:                             # changed in another tab
        accounts.change_password(acc, priya, PASSWORD, "a brand new passphrase")
    other_tab.run()
    text = all_text(other_tab)
    assert "Your password was changed, so you were signed out." in text
    assert "Kitaab Corner" not in text and session.USER not in other_tab.session_state


def test_idle_tabs_are_signed_out(data_dir):
    priya, _ = person_with_shop("priya", "Kitaab Corner")
    app = run_app(priya)
    app.session_state[session.LAST_SEEN] = time.monotonic() - (session.IDLE_MINUTES * 60 + 1)
    app.run()
    assert f"signed out after {session.IDLE_MINUTES} minutes without any activity" in all_text(app)
    assert session.USER not in app.session_state


def test_many_failed_sign_ins_from_one_device_are_refused(data_dir, monkeypatch):
    person_with_shop("priya", "Kitaab Corner")
    monkeypatch.setattr(limits, "SIGN_IN_FAILURES", limits.AttemptLimiter(limit=2, window_seconds=900))
    app = run_app()
    for guess in ("guess number one", "guess number two", PASSWORD):    # the last one is right
        field(app, "Username").set_value("priya")
        field(app, "Password").set_value(guess)
        app.button(key="FormSubmitter:sign_in-Sign in").click().run()
    assert any("Too many attempts from this device" in box.value for box in app.error)
    assert session.USER not in app.session_state


def test_names_are_shown_as_typed_not_as_formatting(data_dir):
    with connect_accounts() as acc:
        user = accounts.create_user(acc, "sneaky", "**Owner** ![x](https://example.com/p.png)", PASSWORD)
        accounts.create_shop(acc, user, "$5 Books")
    app = run_app(user)
    bar = [element.value for element in app.markdown if "Signed in as" in element.value][0]
    assert "![x](" not in bar and r"\*\*Owner\*\*" in bar
    assert "$5 Books" in shown("\n".join(element.value for element in app.markdown))
    assert any(r"\$5 Books" in element.value for element in app.markdown)


# ---------- Errors ----------

def test_broken_database_shows_a_friendly_message(data_dir):
    (data_dir / "accounts.db").write_text("this is not a database", encoding="utf-8")
    app = run_app()                     # the sign-in page itself doesn't read the file...
    field(app, "Username").set_value("priya")
    field(app, "Password").set_value(PASSWORD)
    app.button(key="FormSubmitter:sign_in-Sign in").click().run()   # ...signing in does
    assert not app.exception                                    # no traceback shown
    assert any("couldn't read or write its database" in shown(box.value) for box in app.error)


# ---------- A real, empty shop ----------

def test_empty_shop_books_page_offers_ways_to_add(empty_shop):
    app = run_page("books")
    assert "No books yet" in all_text(app)


def test_adding_a_real_book_by_isbn(empty_shop, open_library):
    app = run_page("books", role="staff")                      # staff may add books
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
    assert any("Added “The God of Small Things”" in shown(box.value) for box in app.success)

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
