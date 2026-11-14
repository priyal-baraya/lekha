"""Sign in, or create an account. The only page people see before signing in.

Laid out as on the design canvas (SignIn artboard): the name and tagline
centred, then one narrow card with the two forms as tabs. Google, when
it's set up, comes after the password form as a second way in.
"""

import streamlit as st

from database import connect_accounts
from services import ValidationError, accounts, limits
from ui import components as ui
from ui import session

# Limits on repeated failures from one network address (services/limits.py).
address = session.network_address()
TOO_MANY = (f"Too many attempts from this device. Wait {limits.WINDOW_MINUTES} minutes, then try again.")

with st.container(key="lekha_narrow"):
    ui.wordmark("Lekha", "Reading between the numbers.")

    reason = st.session_state.pop(session.SIGNED_OUT_REASON, None)
    if reason:
        st.info(reason)

    with st.container(key="lekha_card_sign_in"):
        sign_in_tab, sign_up_tab = st.tabs(["Sign in", "Create an account"])

        with sign_in_tab:
            with st.form("sign_in", border=False):
                username = st.text_input("Username", autocomplete="username", max_chars=32)
                password = st.text_input("Password", type="password", autocomplete="current-password",
                                         max_chars=accounts.MAX_PASSWORD_LENGTH)
                submitted = st.form_submit_button("Sign in", type="primary", width="stretch")
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
            st.html(
                f'<p class="lekha-note">At least {accounts.MIN_PASSWORD_LENGTH} characters. A few unrelated '
                "words make a strong password that's easy to remember. Lekha keeps only a scrambled "
                "version (a salted hash), never the password itself.</p>"
            )
            with st.form("sign_up", border=False):
                name = st.text_input("Your name", autocomplete="name", max_chars=accounts.MAX_NAME_LENGTH)
                new_username = st.text_input("Choose a username", autocomplete="username", max_chars=32,
                                             help="3 to 32 letters, digits, dots, dashes or underscores.")
                new_password = st.text_input("Choose a password", type="password", autocomplete="new-password",
                                             max_chars=accounts.MAX_PASSWORD_LENGTH)
                repeat = st.text_input("Type the password again", type="password", autocomplete="new-password",
                                       max_chars=accounts.MAX_PASSWORD_LENGTH)
                created = st.form_submit_button("Create account", type="primary", width="stretch")
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

        if session.google_configured():
            ui.or_divider()
            if st.button("Sign in with Google", key="google_sign_in", width="stretch"):
                st.login("google")      # Google's page; Lekha never sees the password

        st.html(f'<p class="lekha-note">Signs out after {session.IDLE_MINUTES} minutes without activity.</p>')
