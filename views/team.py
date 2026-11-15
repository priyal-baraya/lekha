"""Team: the shop's owners see who's in the shop, change roles, remove
people and make invite codes.

Laid out as on the design canvas (Team artboard): who's in the shop,
then changing someone's role beside inviting someone. Removing a person
asks first, because it can't be undone from here (they'd need a new
invite). An invite code is shown once, right after it's made; codes
not yet used can be cancelled.
"""

from datetime import datetime

import streamlit as st

from database import connect_accounts
from services import ValidationError, accounts
from ui import components as ui
from ui import session

CHANGES = ["Make staff", "Make owner", "Remove from shop"]
ROLES = {"Staff": "staff", "Owner": "owner"}
REMOVING = "team_removing"          # the person waiting for "Yes, remove"
NEW_CODE = "lekha_new_invite"       # a code just made, shown once

ui.page_header("Team")
session.require("manage_team")
ui.show_flash()

me, shop_id = session.user_id(), st.session_state[session.SHOP]
with connect_accounts() as acc:
    members = accounts.team(acc, me, shop_id)
    shop_name = accounts.get_shop(acc, shop_id)["name"]


def joined(when: str) -> str:
    day = datetime.fromisoformat(when).date()
    return f"{day.day} {day:%b %Y}"


def signs_in_with(member: dict) -> str:
    ways = [way for way, used in (("Password", member["has_password"]), ("Google", member["uses_google"])) if used]
    return " and ".join(ways) or "—"


# ---------------------------------------------------------- who's in the shop
with st.container(key="lekha_card_members"):
    ui.card_heading("Who's in the shop")
    st.html(ui.data_table_html(
        [("Name", "left"), ("Role", "left"), ("Signs in with", "left"), ("Joined", "left")],
        [[member["display_name"] + (" (you)" if member["user_id"] == me else ""),
          ui.Html(ui.status_html("info" if member["role"] == "owner" else "neutral", member["role"].capitalize())),
          signs_in_with(member), joined(member["joined_at"])]
         for member in members["members"]],
    ))


# ------------------------------------------------------------ change a role
def render_change(others: dict) -> None:
    with st.container(key="lekha_card_change"):
        ui.card_heading("Change someone's role")
        person = st.selectbox("Person", list(others), format_func=lambda uid: others[uid]["display_name"],
                              key="team_person")
        change = st.segmented_control("Change", CHANGES, key="team_change", label_visibility="collapsed")
        name = others[person]["display_name"]

        if st.session_state.get(REMOVING) == person:
            st.html(f'<p class="lekha-message lekha-message--warning">Remove {ui.escape(name)} from '
                    f'{ui.escape(shop_name)}?</p>')
            with st.container(horizontal=True):
                if st.button("Yes, remove", key="team_remove_yes", type="primary"):
                    st.session_state.pop(REMOVING, None)
                    apply(person, "remove", f"Removed {name}.")
                if st.button("Keep", key="team_remove_no"):
                    st.session_state.pop(REMOVING, None)
                    st.rerun()
            return

        if st.button("Apply", key="team_apply", disabled=change is None):
            if change == "Remove from shop":
                st.session_state[REMOVING] = person      # ask first
                st.rerun()
            role = "owner" if change == "Make owner" else "staff"
            apply(person, role, f"Made {name} {'an owner' if role == 'owner' else 'staff'}.")


def apply(person: int, change: str, done: str) -> None:
    try:
        with connect_accounts() as acc:
            if change == "remove":
                accounts.remove_member(acc, me, shop_id, person)
            else:
                accounts.change_role(acc, me, shop_id, person, change)
    except ValidationError as problem:
        ui.show_errors(problem.errors)
    else:
        ui.flash("success", done)
        st.rerun()


# ----------------------------------------------------------- invite someone
def render_invite() -> None:
    with st.container(key="lekha_card_invite"):
        ui.card_heading("Invite someone")
        chosen = st.segmented_control("They'll join as", list(ROLES), default="Staff", key="team_invite_role",
                                      label_visibility="collapsed")
        if st.button("Make an invite code", key="team_invite", type="primary", disabled=chosen is None):
            with connect_accounts() as acc:
                st.session_state[NEW_CODE] = accounts.create_invitation(acc, me, shop_id, ROLES[chosen])
            st.rerun()
        code = st.session_state.pop(NEW_CODE, None)       # shown once, then only its hash remains
        if code:
            st.html(f'<p class="lekha-code">{ui.escape(code)}</p>'
                    '<p class="lekha-note">Shown once. Works once, for 7 days.</p>')
        for invite in members["invitations"]:
            with st.container(horizontal=True, vertical_alignment="center", key=f"team_code_{invite['invitation_id']}"):
                st.html(f'<p class="lekha-note">{invite["role"].capitalize()} code, made '
                        f'{joined(invite["created_at"])}, not used yet</p>', width="stretch")
                if st.button("Cancel code", key=f"revoke_{invite['invitation_id']}", type="tertiary"):
                    with connect_accounts() as acc:
                        accounts.revoke_invitation(acc, me, shop_id, invite["invitation_id"])
                    ui.flash("success", "That invite code no longer works.")
                    st.rerun()


others = {m["user_id"]: m for m in members["members"] if m["user_id"] != me}
if others:
    change_col, invite_col = st.columns(2)
    with change_col:
        render_change(others)
    with invite_col:
        render_invite()
else:
    render_invite()
