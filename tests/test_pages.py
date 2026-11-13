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

import html
import json
import re
import time
import urllib.parse
from datetime import datetime
from pathlib import Path

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from database import connect, connect_accounts, ensure_shop_database, get_connection, reset_empty, reset_with_sample_data
from services import accounts, clock, limits, openlibrary
from services.books import BookInput, add_book
from services.sales import SaleLine, record_sale
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
    # HTML pieces escape characters like ' and &; read them as a person would.
    parts += [html.unescape(str(element.proto.body)) for element in app.get("html")]
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
        ("books", "12 books."),
        ("sales", "The basket is empty."),
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

# ---------- The till (Sales) ----------

def till_shop(username: str = "asha") -> tuple[int, Path, dict]:
    """An owner whose shop has four books: Malgudi Days has an ISBN,
    two books are by R. K. Narayan, and Gitanjali is out of stock."""
    owner, shop = person_with_shop(username, "Kitab Ghar")
    shop_file = ensure_shop_database(shop)
    with connect(shop_file) as conn:
        ids = {
            "malgudi": add_book(conn, BookInput(title="Malgudi Days", author="R. K. Narayan", genre="Fiction",
                                                selling_price="300", stock_quantity=5, isbn="9780143039655")),
            "guide": add_book(conn, BookInput(title="The Guide", author="R. K. Narayan", genre="Fiction",
                                              selling_price="299", stock_quantity=2)),
            "train": add_book(conn, BookInput(title="Train to Pakistan", author="Khushwant Singh", genre="Fiction",
                                              selling_price="350", stock_quantity=8)),
            "gitanjali": add_book(conn, BookInput(title="Gitanjali", author="Rabindranath Tagore", genre="Poetry",
                                                  selling_price="300", stock_quantity=0)),
        }
    return owner, shop_file, ids


def open_till(user_id: int) -> AppTest:
    app = run_app(user_id)
    app.switch_page("views/sales.py").run()
    assert not app.exception
    return app


def find(app: AppTest, text: str) -> None:
    """Type in Find a book and press Enter (what a barcode scanner does too)."""
    app.text_input(key="till_query").set_value(text)
    app.button(key="FormSubmitter:till_search-Find").click().run()
    assert not app.exception


def record_label(app: AppTest) -> str:
    return app.button(key="till_record").label


def test_a_sale_at_the_till_from_search_to_undo(data_dir):
    owner, shop_file, ids = till_shop()
    app = open_till(owner)
    assert "The basket is empty." in html_bodies(app)

    find(app, "train")                                   # one match: straight into the sale
    find(app, "978-0-14-303965-5")                       # a scanned ISBN
    app.button(key=f"till_more_{ids['malgudi']}").click().run()
    assert record_label(app) == "Record sale · ₹950.00"   # 1 × ₹350 + 2 × ₹300
    assert "Recorded as now" in html_bodies(app)

    app.button(key="till_record").click().run()
    assert not app.exception
    bodies = html_bodies(app)
    assert "Sale #1 recorded." in bodies and "3 copies, ₹950.00" in bodies
    assert "The basket is empty." in bodies
    assert stock(shop_file, ids["malgudi"]) == 3

    app.button(key="till_undo").click().run()            # a mistake: undo it
    assert "Sale #1 undone. Its copies are back in stock." in html_bodies(app)
    assert stock(shop_file, ids["malgudi"]) == 5
    with connect(shop_file) as conn:
        assert conn.execute("SELECT status FROM sales WHERE sale_id = 1").fetchone()[0] == "cancelled"


def test_several_matches_are_listed_to_choose_from(data_dir):
    owner, _, ids = till_shop()
    app = open_till(owner)
    find(app, "narayan")
    assert "2 matches for “narayan”." in html_bodies(app)
    app.button(key=f"till_add_{ids['guide']}").click().run()
    assert record_label(app) == "Record sale · ₹299.00"


def test_no_match_says_what_to_try(data_dir):
    owner, _, _ = till_shop()
    app = open_till(owner)
    find(app, "kafka on the shore")
    assert "No book matches “kafka on the shore”." in html_bodies(app)


def test_an_out_of_stock_book_is_refused_with_the_reason(data_dir):
    owner, _, _ = till_shop()
    app = open_till(owner)
    find(app, "gitanjali")
    assert "Gitanjali can't be sold until it's restocked." in html_bodies(app)
    assert not any(button.key == "till_record" for button in app.button)     # nothing to record


def test_the_basket_stops_at_the_copies_on_the_shelf(data_dir):
    owner, _, ids = till_shop()
    app = open_till(owner)
    find(app, "the guide")
    app.button(key=f"till_more_{ids['guide']}").click().run()
    app.button(key=f"till_more_{ids['guide']}").click().run()   # a third copy that isn't there
    assert "Only 2 copies of The Guide are in stock, and both are in this sale." in html_bodies(app)
    assert record_label(app) == "Record sale · ₹598.00"


def test_staff_sales_are_recorded_under_their_name(data_dir):
    owner, shop_file, ids = till_shop()
    with connect_accounts() as acc:
        staff = accounts.create_user(acc, "vikram", "Vikram", PASSWORD)
        accounts.redeem_invitation(acc, staff, accounts.create_invitation(acc, owner, 1))
    app = open_till(staff)
    find(app, "train")
    app.button(key="till_record").click().run()
    with connect(shop_file) as conn:
        assert conn.execute("SELECT recorded_by FROM sales WHERE sale_id = 1").fetchone()[0] == staff


def test_recent_sales_list_the_books_and_cancel_with_a_reason(data_dir):
    owner, shop_file, ids = till_shop()
    with connect(shop_file) as conn:
        record_sale(conn, [SaleLine(ids["malgudi"], 2, 30_000)], recorded_by=owner)
    app = open_till(owner)
    app.session_state["sales_view"] = "Recent sales"
    app.run()
    bodies = html_bodies(app)
    assert "Malgudi Days ×2" in bodies and "Showing the last 1 sale." in bodies
    app.text_input(key="cancel_reason").set_value("Customer changed their mind")
    app.button(key="FormSubmitter:cancel_sale-Cancel sale").click().run()
    assert not app.exception
    assert "Sale #1 cancelled. Copies returned to stock: Malgudi Days ×2." in all_text(app) + html_bodies(app)
    assert stock(shop_file, ids["malgudi"]) == 5


# ---------- Other pages' main actions ----------

def test_search_filters_the_catalogue(sample_file):
    app = run_page("books")
    app.text_input(key="books_search").set_value("menon").run()
    assert "Showing 2 of 12 books." in all_text(app)


def test_the_catalogue_can_be_searched_by_isbn(sample_file):
    app = run_page("books")
    app.text_input(key="books_search").set_value("000-000-000-0003").run()
    text = all_text(app)
    assert "Showing 1 of 12 books." in text and "The Lighthouse at Kovalam" in text


def test_the_header_button_opens_add_a_book(sample_file):
    app = run_page("books")
    app.button(key="books_add_header").click().run()
    assert app.session_state["books_tab"] == "Add a book"
    assert app.segmented_control(key="add_method").value == "isbn"


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


def test_sign_in_page_follows_the_design(data_dir):
    app = run_app()
    text = all_text(app)
    assert '<h1 class="lekha-wordmark__name">Lekha</h1>' in str([e.proto.body for e in app.get("html")])
    assert "Independent bookstore insights" not in text            # no label above the heading
    assert "A password sign-in lasts until you close or refresh this tab" in text
    assert "Sign in with Google" not in [button.label for button in app.button]   # Google isn't set up
    assert "A Google sign-in is remembered" not in text


def test_google_sign_in_is_offered_below_the_password_form_when_set_up(data_dir, monkeypatch):
    monkeypatch.setattr(session, "google_configured", lambda: True)
    # The page on its own: the whole app would also ask Google who's signed in.
    app = AppTest.from_file(str(PROJECT / "views" / "signin.py"), default_timeout=TIMEOUT).run()
    assert not app.exception
    google = next(button for button in app.button if button.label == "Sign in with Google")
    assert google.proto.type == "secondary"                       # the password form's button leads
    assert "A Google sign-in is remembered after a refresh." in all_text(app)


def test_get_started_follows_the_design(data_dir):
    with connect_accounts() as acc:
        priya = accounts.create_user(acc, "priya", "Priya", PASSWORD)
    app = run_app(priya)
    assert not app.exception
    bodies = " ".join(str(e.proto.body) for e in app.get("html"))
    assert '<h1 class="lekha-pagehead__title">Get started</h1>' in bodies
    assert '<h2 class="lekha-cardhead__title">Start a shop</h2>' in bodies
    assert '<h2 class="lekha-cardhead__title">Join with a code</h2>' in bodies
    text = all_text(app)
    for old_label in ("Your shops", "New shop", "Existing shop"):  # labels above headings are gone
        assert old_label not in text


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
    assert "Kitaab Corner" in text and "Welcome to Lekha." in text
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
    assert "Asha's Books" in text and "Welcome to Lekha." not in text
    text = all_text(run_app(ben))
    assert "Ben's Books" in text and "Welcome to Lekha." in text
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
    assert not app.exception
    # The account menu's label (Streamlit reads it as Markdown).
    label = session.account_label("**Owner** ![x](https://example.com/p.png)", "$5 Books")
    assert "![x](" not in label and r"\*\*Owner\*\*" in label and r"\$5 Books" in label
    assert shown(label).startswith("**Owner** ![x](https")      # reads exactly as typed (cut short at 24)


def test_long_names_are_cut_short_in_the_account_menu():
    label = session.account_label("Venkatalakshmi Subramanian", "Sri Venkateswara Book Depot & Stationers")
    name, shop = shown(label).split(" · ")
    assert name == "Venkatalakshmi Subraman…" and len(name) == session.ACCOUNT_LABEL_NAME_LIMIT
    assert shop.endswith("…") and len(shop) == session.ACCOUNT_LABEL_NAME_LIMIT


def test_switch_shop_lists_every_shop_and_opens_the_chosen_one(data_dir):
    asha, first = person_with_shop("asha", "Kitaab Corner")
    with connect_accounts() as acc:
        second = accounts.create_shop(acc, asha, "$5 Books")
    app = AppTest.from_file(str(PROJECT / "views" / "switch_shop.py"), default_timeout=TIMEOUT)
    app.session_state[session.USER] = asha
    app.session_state[session.SHOP] = first
    app.run()
    assert not app.exception
    buttons = {button.label: button for button in app.button}
    assert set(buttons) == {"Kitaab Corner · owner · open now", r"\$5 Books · owner"}    # names escaped
    assert buttons["Kitaab Corner · owner · open now"].disabled                   # the shop already open
    buttons[r"\$5 Books · owner"].click().run()
    assert app.session_state[session.SHOP] == second


# ---------- Errors ----------

def test_broken_database_shows_a_friendly_message(data_dir):
    (data_dir / "accounts.db").write_text("this is not a database", encoding="utf-8")
    app = run_app()                     # the sign-in page itself doesn't read the file...
    field(app, "Username").set_value("priya")
    field(app, "Password").set_value(PASSWORD)
    app.button(key="FormSubmitter:sign_in-Sign in").click().run()   # ...signing in does
    assert not app.exception                                    # no traceback shown
    assert any("couldn't read or write its database" in shown(box.value) for box in app.error)


# ---------- Overview ----------

OVERVIEW_NOW = datetime(2026, 11, 12, 16, 45)       # a Thursday afternoon


@pytest.fixture
def fixed_now(monkeypatch):
    monkeypatch.setattr(clock, "now", lambda: OVERVIEW_NOW)


def html_bodies(app: AppTest) -> str:
    """The page's HTML blocks as text, leaving out the stylesheet."""
    bodies = (str(element.proto.body) for element in app.get("html"))
    return " ".join(html.unescape(body) for body in bodies if not body.lstrip().startswith("<style"))


def overview_as_owner() -> tuple[int, Path]:
    """An owner with a new shop, and the path to that shop's database.
    Overview links to other pages, so it runs inside the whole app."""
    owner, shop = person_with_shop("asha", "Kitab Ghar")
    return owner, ensure_shop_database(shop)


def test_overview_of_a_new_shop_shows_the_first_steps(data_dir, fixed_now):
    owner, _ = overview_as_owner()
    app = run_app(owner)
    assert not app.exception and not app.error
    bodies = html_bodies(app)
    assert "Welcome to Lekha." in bodies and "Three steps to get started" in bodies
    assert "None yet" in bodies and "Nothing to reorder" in bodies
    assert "Reorder these" not in bodies and "Latest sales" not in bodies


def test_overview_of_a_trading_shop(data_dir, fixed_now):
    owner, shop_file = overview_as_owner()
    with connect(shop_file) as conn:
        malgudi = add_book(conn, BookInput(title="Malgudi Days", author="R. K. Narayan", genre="Fiction",
                                           selling_price="250", stock_quantity=20))
        gitanjali = add_book(conn, BookInput(title="Gitanjali", author="Rabindranath Tagore", genre="Poetry",
                                             selling_price="300", stock_quantity=1, reorder_level=3))
        record_sale(conn, [SaleLine(malgudi, 1, 25_000)], sale_datetime=datetime(2026, 11, 5, 10, 0),
                    now=OVERVIEW_NOW)                                           # last Thursday morning
        record_sale(conn, [SaleLine(malgudi, 2, 25_000), SaleLine(gitanjali, 1, 30_000)],
                    sale_datetime=datetime(2026, 11, 12, 11, 20), now=OVERVIEW_NOW)
    app = run_app(owner)
    assert not app.exception and not app.error
    bodies = html_bodies(app)
    assert "Thursday 12 November" in bodies
    assert "₹800 in sales so far today, and 1 book needs reordering." in bodies
    assert "₹250 by this time last Thursday" in bodies
    assert "This week so far" in bodies and "Last 30 days" in bodies
    assert "Reorder these" in bodies and "Out of stock" in bodies
    assert "Malgudi Days ×2, Gitanjali" in bodies                       # latest sales, in words
    assert "Gitanjali sold out, so it's on the reorder list." in bodies
    assert "Three steps to get started" not in bodies


def test_overview_shows_book_titles_as_typed(data_dir, fixed_now):
    owner, shop_file = overview_as_owner()
    with connect(shop_file) as conn:
        add_book(conn, BookInput(title="<b>Bold</b> & Co", author="A", genre="Fiction",
                                 selling_price="100", stock_quantity=0))    # out of stock: in Reorder these
    app = run_app(owner)
    assert "<b>Bold</b> & Co" in html_bodies(app)                  # read back as text...
    assert "<b>Bold</b>" not in " ".join(str(e.proto.body) for e in app.get("html"))   # ...never as markup


# ---------- A real, empty shop ----------

def test_empty_shop_books_page_offers_ways_to_add(empty_shop):
    app = run_page("books")
    assert "No books yet" in all_text(app)
    app.button(key="books_add_first").click().run()          # "Add your first book"
    assert app.session_state["books_tab"] == "Add a book"


def test_adding_a_real_book_by_isbn(empty_shop, open_library):
    app = run_page("books", role="staff")                      # staff may add books
    app.session_state["books_tab"] = "Add a book"
    app.run()
    app.segmented_control(key="add_method").set_value("isbn").run()
    app.text_input(key="isbn_lookup_input").set_value("978-0-00-655068-6")
    app.button(key="FormSubmitter:isbn_lookup-Look up").click().run()
    assert not app.exception
    text = all_text(app)
    assert "Found on Open Library." in text
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
    app.segmented_control(key="add_method").set_value("search").run()
    app.text_input(key="ol_search_input").set_value("the god of small things")
    app.button(key="FormSubmitter:openlibrary_search-Search").click().run()
    assert not app.exception
    text = all_text(app)
    assert "5 matches" in text
    assert "Arundhati Roy · first published 1997" in text

    app.button(key="use_result_0").click().run()   # "Use this book"
    text = all_text(app)
    assert "This is the book in general, not a particular edition" in text
    assert app.text_input(key="add_isbn_1").value == ""          # no ISBN guessed for a work
    assert app.text_input(key="add_publisher_1").value == ""     # no edition facts guessed
