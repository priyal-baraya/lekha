"""Settings: the shop (owners), your own account, your password and more
shops (everyone).

Laid out as on the design canvas (Settings artboard): four cards, two
by two. Staff have no Shop card: only owners can change it. Someone who
signs in only with Google has no password to change, so no Password card.
"""

import streamlit as st

from database import connect_accounts
from services import ValidationError, accounts
from ui import components as ui
from ui import session

ui.page_header("Settings")
ui.show_flash()

me, shop_id = session.user_id(), st.session_state[session.SHOP]
with connect_accounts() as acc:
    shop = accounts.get_shop(acc, shop_id)
    user = accounts.get_user(acc, me)


def render_shop() -> None:
    with st.container(key="lekha_card_shop"):
        ui.card_heading("Shop")
        with st.form("shop_settings", border=False):
            name = st.text_input("Shop name", value=shop["name"], max_chars=80, key="settings_shop_name")
            reorder = st.number_input("Default reorder level", min_value=0, step=1,
                                      value=shop["default_reorder_level"], key="settings_reorder", width=200)
            st.html('<p class="lekha-note lekha-field-note">Used for new books</p>')
            saved = st.form_submit_button("Save shop settings", type="primary")
        if saved:
            try:
                with connect_accounts() as acc:
                    accounts.update_shop_settings(acc, me, shop_id, name, int(reorder))
            except ValidationError as problem:
                ui.show_errors(problem.errors)
            else:
                st.session_state.pop(session.SHOP_NAME, None)      # the account menu shows the new name
                ui.flash("success", "Shop settings saved.")
                st.rerun()


def render_account() -> None:
    with st.container(key="lekha_card_account"):
        ui.card_heading("Your account")
        with st.form("display_name", border=False):
            display_name = st.text_input("Your name, as the team sees it", value=user["display_name"],
                                         max_chars=accounts.MAX_NAME_LENGTH, key="settings_display_name")
            renamed = st.form_submit_button("Save name")
        if renamed:
            try:
                with connect_accounts() as acc:
                    accounts.change_display_name(acc, me, display_name)
            except ValidationError as problem:
                ui.show_errors(problem.errors)
            else:
                ui.flash("success", "Name saved.")
                st.rerun()


def render_password() -> None:
    with st.container(key="lekha_card_password"):
        ui.card_heading("Change password", "Other tabs signed in with the old password will be signed out.")
        limit = accounts.MAX_PASSWORD_LENGTH
        with st.form("change_password", border=False, clear_on_submit=True):
            current = st.text_input("Current password", type="password", autocomplete="current-password",
                                    max_chars=limit, key="settings_current")
            new = st.text_input("New password", type="password", autocomplete="new-password", max_chars=limit,
                                placeholder=f"{accounts.MIN_PASSWORD_LENGTH} to {limit} characters",
                                key="settings_new")
            repeat = st.text_input("New password again", type="password", autocomplete="new-password",
                                   max_chars=limit, key="settings_repeat")
            changed = st.form_submit_button("Change password")
        if changed:
            if new != repeat:
                ui.show_errors(["The two new passwords don't match."])
                return
            try:
                with connect_accounts() as acc:
                    accounts.change_password(acc, me, current, new)
            except ValidationError as problem:
                ui.show_errors(problem.errors)
            else:
                session.remember_new_password()     # this tab stays signed in; others are signed out
                st.html('<p class="lekha-message lekha-message--success">Password changed.</p>')


def render_more_shops() -> None:
    with st.container(key="lekha_card_more_shops"):
        ui.card_heading("More shops", "Run another bookshop, or help at a friend's?")
        st.page_link("views/get_started.py", label="Start or join a shop")


# Two by two, as the canvas: what each person can change comes first.
cards = ([render_shop] if session.can_do("manage_settings") else []) + [render_account]
cards += ([render_password] if user["has_password"] else []) + [render_more_shops]
for row in range(0, len(cards), 2):
    columns = st.columns(2)
    for column, card in zip(columns, cards[row:row + 2]):
        with column:
            card()
