"""Who is signed in, which shop they're working in, and what they may do.

Streamlit keeps st.session_state per browser tab, on the server. Lekha
stores only the signed-in person's user_id and chosen shop there. Their
role is read fresh from the accounts database on every page run (in
app.py), so if an owner removes someone or changes their role, it takes
effect on that person's next click.
"""

import streamlit as st

from database import connect_accounts
from services import accounts
from services.permissions import ACTIONS, can

USER = "lekha_user_id"
METHOD = "lekha_sign_in_method"     # "password" or "google"
SHOP = "lekha_shop_id"
ROLE = "lekha_role"
SHOP_NAME = "lekha_shop_name"
DEFAULT_REORDER = "lekha_default_reorder"


def user_id() -> int | None:
    return st.session_state.get(USER)


def role() -> str | None:
    return st.session_state.get(ROLE)


def shop_name() -> str | None:
    return st.session_state.get(SHOP_NAME)


def default_reorder_level() -> int:
    return st.session_state.get(DEFAULT_REORDER, 2)


def can_do(action: str) -> bool:
    return can(role(), action)


def require(action: str) -> None:
    """Stop the page unless the current role allows the action."""
    if not can_do(action):
        st.error(f"Only the shop's owners can {ACTIONS[action][0].lower() + ACTIONS[action][1:]}.")
        st.stop()


def sign_in(new_user_id: int, method: str) -> None:
    st.session_state[USER] = new_user_id
    st.session_state[METHOD] = method
    for key in (SHOP, ROLE, SHOP_NAME, DEFAULT_REORDER):
        st.session_state.pop(key, None)


def sign_out() -> None:
    method = st.session_state.get(METHOD)
    # Forget everything this tab knew: the person, the shop, and any
    # half-finished work such as a sale basket.
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    if method == "google" and google_configured():
        st.logout()      # also clears Google's sign-in cookie, then reloads
    st.rerun()


def choose_shop(shop_id: int) -> None:
    st.session_state[SHOP] = shop_id
    for key in (ROLE, SHOP_NAME, DEFAULT_REORDER, "basket"):
        st.session_state.pop(key, None)


def google_configured() -> bool:
    """True when .streamlit/secrets.toml has Google sign-in credentials."""
    try:
        auth = st.secrets.get("auth", {})
    except Exception:          # no secrets file at all
        return False
    return bool(auth.get("redirect_uri") and auth.get("cookie_secret") and auth.get("google"))


def names(user_ids) -> dict[int, str]:
    """Display names for "recorded by" columns."""
    with connect_accounts() as acc:
        return accounts.display_names(acc, user_ids)
