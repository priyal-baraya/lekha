"""Settings: the shop's settings (owners) and your own account (everyone)."""

import streamlit as st

from database import connect_accounts
from services import ValidationError, accounts
from ui import components as ui
from ui import session

ui.page_intro(
    eyebrow="Configuration",
    title="Settings",
    description="Your shop's details, and your own account.",
)
ui.show_flash()

me, shop_id = session.user_id(), st.session_state[session.SHOP]
with connect_accounts() as acc:
    shop = accounts.get_shop(acc, shop_id)
    user = accounts.get_user(acc, me)

# ----------------------------------------------------------- the shop
ui.section_header(eyebrow="Shop", title=shop["name"])
if session.can_do("manage_settings"):
    with st.form("shop_settings"):
        name = st.text_input("Shop name", value=shop["name"], max_chars=80)
        reorder = st.number_input(
            "Default reorder level for new books", min_value=0, step=1, value=shop["default_reorder_level"],
            help="Lekha flags a book as low on stock at or below its reorder level. "
                 "New books start with this number; you can change it per book.",
        )
        saved = st.form_submit_button("Save shop settings", type="primary")
    if saved:
        try:
            with connect_accounts() as acc:
                accounts.update_shop_settings(acc, me, shop_id, name, int(reorder))
        except ValidationError as problem:
            ui.show_errors(problem.errors)
        else:
            st.session_state.pop(session.SHOP_NAME, None)
            ui.flash("success", "Shop settings saved.")
            st.rerun()
else:
    st.markdown(f"Default reorder level for new books: **{shop['default_reorder_level']}**. "
                "Only the shop's owners can change shop settings.")

ui.divider()

# ------------------------------------------------------------ your account
ui.section_header(eyebrow="You", title="Your account",
                  description=("You sign in with Google" + (f" ({user['email']})" if user["email"] else "") + "."
                               if user["uses_google"] and not user["has_password"]
                               else f"You sign in with the username {user['username']}."))
with st.form("display_name"):
    display_name = st.text_input("Your name, as the team sees it", value=user["display_name"],
                                 max_chars=accounts.MAX_NAME_LENGTH)
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

if user["has_password"]:
    with st.form("change_password", clear_on_submit=True):
        limit = accounts.MAX_PASSWORD_LENGTH
        current = st.text_input("Current password", type="password", autocomplete="current-password", max_chars=limit)
        new = st.text_input("New password", type="password", autocomplete="new-password", max_chars=limit)
        repeat = st.text_input("New password again", type="password", autocomplete="new-password", max_chars=limit)
        changed = st.form_submit_button("Change password")
    if changed:
        if new != repeat:
            ui.show_errors(["The two new passwords don't match."])
        else:
            try:
                with connect_accounts() as acc:
                    accounts.change_password(acc, me, current, new)
            except ValidationError as problem:
                ui.show_errors(problem.errors)
            else:
                session.remember_new_password()     # this tab stays signed in; others are signed out
                st.success("Password changed. Any other tabs signed in to your account have been signed out.")

ui.divider()
ui.section_header(eyebrow="More shops", title="Start or join another shop",
                  description="One account can belong to several shops; switch between them at the top of each page.")
st.page_link("views/get_started.py", label="Start or join a shop →")
