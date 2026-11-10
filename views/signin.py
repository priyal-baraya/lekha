"""Sign in, or create an account. The only page people see before signing in."""

import streamlit as st

from database import connect_accounts
from services import ValidationError, accounts, limits
from ui import components as ui
from ui import session

ui.hero(
    eyebrow="Independent bookstore insights",
    title="Lekha",
    tagline="Reading between the numbers.",
    description="Sign in to your shop, or create an account to start one or join one.",
)
ui.divider()

reason = st.session_state.pop(session.SIGNED_OUT_REASON, None)
if reason:
    st.info(reason)

# Limits on repeated failures from one network address (services/limits.py).
address = session.network_address()
TOO_MANY = (f"Too many attempts from this device. Wait {limits.WINDOW_MINUTES} minutes, then try again.")

if session.google_configured():
    if st.button("Sign in with Google", type="primary", key="google_sign_in"):
        st.login("google")      # Google's page; Lekha never sees the password
    st.markdown("Or use a Lekha username and password:")

sign_in_tab, sign_up_tab = st.tabs(["Sign in", "Create an account"])

with sign_in_tab:
    with st.form("sign_in"):
        username = st.text_input("Username", autocomplete="username", max_chars=32)
        password = st.text_input("Password", type="password", autocomplete="current-password",
                                 max_chars=accounts.MAX_PASSWORD_LENGTH)
        submitted = st.form_submit_button("Sign in", type="primary")
    if submitted:
        if limits.SIGN_IN_FAILURES.blocked(address):
            st.error(TOO_MANY)
        else:
            try:
                with connect_accounts() as acc:
                    user_id = accounts.authenticate(acc, username, password)
            except accounts.SignInError as problem:
                limits.SIGN_IN_FAILURES.record(address)
                st.error(str(problem))
            else:
                session.sign_in(user_id, "password")
                st.rerun()

with sign_up_tab:
    st.markdown(
        f"Passwords need at least {accounts.MIN_PASSWORD_LENGTH} characters. A few unrelated words "
        "together make a strong one that's easy to remember. Lekha stores only a scrambled version "
        "(a salted hash), never the password itself."
    )
    with st.form("sign_up"):
        name = st.text_input("Your name", autocomplete="name", max_chars=accounts.MAX_NAME_LENGTH)
        new_username = st.text_input("Choose a username", autocomplete="username", max_chars=32,
                                     help="3 to 32 letters, digits, dots, dashes or underscores.")
        new_password = st.text_input("Choose a password", type="password", autocomplete="new-password",
                                     max_chars=accounts.MAX_PASSWORD_LENGTH)
        repeat = st.text_input("Type the password again", type="password", autocomplete="new-password",
                               max_chars=accounts.MAX_PASSWORD_LENGTH)
        created = st.form_submit_button("Create account", type="primary")
    if created:
        if new_password != repeat:
            ui.show_errors(["The two passwords don't match."])
        elif limits.NEW_ACCOUNTS.blocked(address):
            st.error("Too many new accounts from this device. Try again in an hour.")
        else:
            try:
                with connect_accounts() as acc:
                    user_id = accounts.create_user(acc, new_username, name, new_password)
            except ValidationError as problem:
                ui.show_errors(problem.errors)
            else:
                limits.NEW_ACCOUNTS.record(address)
                session.sign_in(user_id, "password")
                st.rerun()

st.markdown(
    "Signing in with a username and password lasts until you close or refresh this tab. "
    f"After {session.IDLE_MINUTES} minutes without any activity, Lekha signs you out."
    + (" A Google sign-in is remembered after a refresh." if session.google_configured() else "")
)
