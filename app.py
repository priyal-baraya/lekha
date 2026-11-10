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

SHOP_PAGES = [
    ("views/overview.py", "Overview", None),
    ("views/books.py", "Books", None),
    ("views/sales.py", "Sales", "sell"),
    ("views/inventory.py", "Inventory", "view_stock"),
    ("views/insights.py", "Insights", "view_insights"),
    ("views/team.py", "Team", "manage_team"),
    ("views/settings.py", "Settings", None),
]


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


def account_bar(user: dict, memberships: list[accounts.Membership], current: accounts.Membership | None) -> None:
    """Shop switcher, who's signed in, and Sign out, above every page."""
    shop_col, who_col, out_col = st.columns([3, 3, 1], vertical_alignment="center")
    if current and len(memberships) > 1:
        by_id = {m.shop_id: m for m in memberships}
        picked = shop_col.selectbox(
            "Shop", list(by_id), index=list(by_id).index(current.shop_id),
            format_func=lambda shop_id: f"{by_id[shop_id].shop_name} ({by_id[shop_id].role})",
            key="account_bar_shop",
        )
        if picked != current.shop_id:
            session.choose_shop(picked)
            st.rerun()
    elif current:
        shop_col.markdown(f"**{current.shop_name}**")
    who_col.markdown(f"Signed in as **{user['display_name']}**" + (f" · {current.role}" if current else ""))
    if out_col.button("Sign out", key="account_bar_sign_out"):
        session.sign_out()


try:
    sign_in_from_google()
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
        # Signed in, but not part of any shop yet.
        use_database(None)
        account_bar(user, memberships, None)
        page = st.navigation([st.Page("views/get_started.py", title="Get started")], position="hidden")
    else:
        current = choose_current_shop(memberships)
        # Every query on this page run now goes to this shop's own file.
        use_database(ensure_shop_database(current.shop_id))
        account_bar(user, memberships, current)
        pages = [
            st.Page(path, title=title, default=(path == "views/overview.py"))
            for path, title, action in SHOP_PAGES
            if action is None or session.can_do(action)
        ]
        pages.append(st.Page("views/get_started.py", title="Start or join a shop", visibility="hidden"))
        page = st.navigation(pages, position="top")
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
