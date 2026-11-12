"""Lekha: application entry point.

On every page run, this file:
  1. works out who is signed in (a Lekha password, or Google);
  2. finds the shops they belong to, and their role in the chosen one,
     fresh from the accounts database;
  3. points the page at that shop's own database file;
  4. shows only the pages their role allows, then runs the chosen page;
  5. catches errors and shows a plain message instead of a traceback.
Each page's content lives in views/.

Run with:
    .\\.venv\\Scripts\\python.exe -m streamlit run app.py
"""

import logging
import sqlite3

import streamlit as st

from database import connect_accounts, ensure_shop_database, use_database
from services import accounts
from ui import components as ui
from ui import session

# Messages for whoever runs the app; they appear in the terminal.
logger = logging.getLogger("lekha")

st.set_page_config(
    page_title="Lekha",
    page_icon="📚",
    layout="wide",
)

ui.load_styles()

# The five pages used every day, in the navigation bar itself.
SHOP_PAGES = [
    ("views/overview.py", "Overview", None),
    ("views/books.py", "Books", None),
    ("views/sales.py", "Sales", "sell"),
    ("views/inventory.py", "Inventory", "view_stock"),
    ("views/insights.py", "Insights", "view_insights"),
]
# Everything about the person and the shop, in the account menu just after
# the page links (its label is the person and the shop).
ACCOUNT_PAGES = [
    ("views/team.py", "Team", "manage_team"),
    ("views/settings.py", "Settings", None),
]


def sign_out_page() -> None:
    """"Sign out" in the account menu: opening it signs this tab out."""
    session.sign_out()


def sign_in_from_google() -> None:
    """After Google sends someone back, find or create their Lekha account."""
    if session.user_id() is None and session.google_configured() and st.user.is_logged_in:
        with connect_accounts() as acc:
            user_id = accounts.google_sign_in(acc, st.user.get("sub"), st.user.get("email"), st.user.get("name"))
        session.sign_in(user_id, "google")


def choose_current_shop(memberships: list[accounts.Membership]) -> accounts.Membership:
    """The shop chosen in this tab, or the first one, with role and settings
    read fresh, so a changed role or removal takes effect immediately."""
    chosen = st.session_state.get(session.SHOP)
    current = next((m for m in memberships if m.shop_id == chosen), memberships[0])
    with connect_accounts() as acc:
        shop = accounts.get_shop(acc, current.shop_id)
    st.session_state[session.SHOP] = current.shop_id
    st.session_state[session.ROLE] = current.role
    st.session_state[session.SHOP_NAME] = shop["name"]
    st.session_state[session.DEFAULT_REORDER] = shop["default_reorder_level"]
    return current


def account_pages(memberships: list[accounts.Membership]) -> list:
    """What the account menu holds: Team (owners), Settings, Switch shop
    (only with more than one shop), Start or join a shop, and Sign out."""
    pages = [st.Page(path, title=title) for path, title, action in ACCOUNT_PAGES
             if action is None or session.can_do(action)]
    if len(memberships) > 1:
        pages.append(st.Page("views/switch_shop.py", title="Switch shop"))
    pages.append(st.Page("views/get_started.py", title="Start or join a shop"))
    pages.append(st.Page(sign_out_page, title="Sign out", url_path="sign-out"))
    return pages


try:
    sign_in_from_google()
    session.check_still_valid()      # idle too long, or password changed elsewhere
    user_id = session.user_id()
    user = None
    if user_id is not None:
        with connect_accounts() as acc:
            user = accounts.get_user(acc, user_id)
            memberships = accounts.memberships(acc, user_id)
        if user is None:            # the account no longer exists
            session.sign_out()

    if user is None:
        # Signed out: the sign-in page is the only page that exists.
        use_database(None)
        page = st.navigation([st.Page("views/signin.py", title="Sign in")], position="hidden")
    elif not memberships:
        # Signed in, but not part of any shop yet: Get started, and Sign out
        # in the account menu.
        use_database(None)
        page = st.navigation({
            "": [st.Page("views/get_started.py", title="Get started")],
            session.account_label(user["display_name"]): [st.Page(sign_out_page, title="Sign out", url_path="sign-out")],
        }, position="top")
    else:
        current = choose_current_shop(memberships)
        # Every query on this page run now goes to this shop's own file.
        use_database(ensure_shop_database(current.shop_id))
        daily = [
            st.Page(path, title=title, default=(path == "views/overview.py"))
            for path, title, action in SHOP_PAGES
            if action is None or session.can_do(action)
        ]
        # "" puts the daily pages first; the labelled section becomes the
        # account menu, a dropdown at the end of the bar.
        label = session.account_label(user["display_name"], current.shop_name)
        page = st.navigation({"": daily, label: account_pages(memberships)}, position="top")
        if st.session_state.pop("lekha_go_home", False):   # just created or joined a shop
            st.switch_page("views/overview.py")

    page.run()
except sqlite3.Error:
    logger.exception("Database error")
    st.error(
        "Lekha couldn't read or write its database. If a file is open in another program, "
        "close it, then reload this page. Nothing was saved halfway: sales, stock corrections "
        "and book changes are saved all-or-nothing."
    )
except Exception:
    logger.exception("Unexpected error")
    st.error(
        "Something went wrong on this page. Nothing was saved halfway: sales, stock corrections "
        "and book changes are saved all-or-nothing. Reload the page to try again."
    )
