"""Who is signed in, which shop they're working in, and what they may do.

Streamlit keeps st.session_state per browser tab, on the server. Lekha
stores only the signed-in person's user_id and chosen shop there. Their
role is read fresh from the accounts database on every page run (in
app.py), so if an owner removes someone or changes their role, it takes
effect on that person's next click.

A signed-in tab is also signed out when:
  * nobody has clicked anything for IDLE_MINUTES (a till left open);
  * the account's password was changed somewhere else.
"""

import logging
import time

import streamlit as st

from database import connect_accounts
from services import accounts
from services.permissions import ACTIONS, can

log = logging.getLogger("lekha.security")

USER = "lekha_user_id"
METHOD = "lekha_sign_in_method"     # "password" or "google"
STAMP = "lekha_credential_stamp"    # see accounts.credential_stamp
LAST_SEEN = "lekha_last_seen"       # time of the last click, for the idle limit
SHOP = "lekha_shop_id"
ROLE = "lekha_role"
SHOP_NAME = "lekha_shop_name"
DEFAULT_REORDER = "lekha_default_reorder"
SIGNED_OUT_REASON = "lekha_signed_out_reason"

IDLE_MINUTES = 60
MIN_COOKIE_SECRET_LENGTH = 32


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
    # Start from a clean slate, so nothing from before signing in carries over.
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.session_state[USER] = new_user_id
    st.session_state[METHOD] = method
    st.session_state[LAST_SEEN] = time.monotonic()
    with connect_accounts() as acc:
        st.session_state[STAMP] = accounts.credential_stamp(acc, new_user_id)


def remember_new_password() -> None:
    """After this tab changed the password, keep this tab signed in
    (other tabs that knew the old password are signed out)."""
    with connect_accounts() as acc:
        st.session_state[STAMP] = accounts.credential_stamp(acc, user_id())


def check_still_valid() -> None:
    """Sign this tab out if it has been idle too long or the password
    changed elsewhere. Called by app.py at the start of every page run."""
    if user_id() is None:
        return
    now = time.monotonic()
    last_seen = st.session_state.get(LAST_SEEN, now)
    if now - last_seen > IDLE_MINUTES * 60:
        log.info("Account %s signed out after %s idle minutes", user_id(), IDLE_MINUTES)
        sign_out(f"You were signed out after {IDLE_MINUTES} minutes without any activity. Sign in again.")
    with connect_accounts() as acc:
        current = accounts.credential_stamp(acc, user_id())
    if st.session_state.get(METHOD) == "password" and current != st.session_state.get(STAMP):
        log.info("Account %s signed out: its password changed", user_id())
        sign_out("Your password was changed, so you were signed out. Sign in with the new password.")
    st.session_state[LAST_SEEN] = now


def sign_out(reason: str | None = None) -> None:
    method = st.session_state.get(METHOD)
    # Forget everything this tab knew: the person, the shop, and any
    # half-finished work such as a sale basket.
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    if reason:
        st.session_state[SIGNED_OUT_REASON] = reason    # shown on the sign-in page
    if method == "google" and google_configured():
        st.logout()      # also clears Google's sign-in cookie, then reloads
    st.rerun()


def network_address() -> str:
    """The visitor's network address, for limits on repeated failures."""
    try:
        address = st.context.ip_address
    except Exception:            # no browser connection
        return "unknown"
    return address if isinstance(address, str) and address else "unknown"


def choose_shop(shop_id: int) -> None:
    st.session_state[SHOP] = shop_id
    for key in (ROLE, SHOP_NAME, DEFAULT_REORDER, "basket"):
        st.session_state.pop(key, None)


def google_configured() -> bool:
    """True when .streamlit/secrets.toml has Google sign-in credentials.

    The cookie secret signs the cookie that keeps a Google sign-in, so a
    short, guessable one would let someone forge it: Google sign-in stays
    off until it is at least 32 characters."""
    try:
        auth = st.secrets.get("auth", {})
    except Exception:          # no secrets file at all
        return False
    if not (auth.get("redirect_uri") and auth.get("cookie_secret") and auth.get("google")):
        return False
    if len(str(auth.get("cookie_secret"))) < MIN_COOKIE_SECRET_LENGTH:
        log.warning("Google sign-in is off: cookie_secret in secrets.toml must be at least %s characters",
                    MIN_COOKIE_SECRET_LENGTH)
        return False
    return True


def names(user_ids) -> dict[int, str]:
    """Display names for "recorded by" columns."""
    with connect_accounts() as acc:
        return accounts.display_names(acc, user_ids)
