"""Team: the shop's owners invite staff, change roles and remove people."""

import pandas as pd
import streamlit as st

from database import connect_accounts
from services import ValidationError, accounts
from services.permissions import ACTIONS, STAFF_ACTIONS
from ui import components as ui
from ui import session

ui.page_intro(
    eyebrow="The shop's people",
    title="Team",
    description="Invite staff, choose what each person can do, and remove people who have left.",
)
session.require("manage_team")
ui.show_flash()

me, shop_id = session.user_id(), st.session_state[session.SHOP]

# A new code is shown once, right after it's made, then only its hash remains.
new_code = st.session_state.pop("lekha_new_invite", None)
if new_code:
    st.success(
        f"Invite code: **{new_code[0]}** (for {new_code[1]}). Give it to the person you're inviting. "
        "It works once, for 7 days. Lekha won't show it again: if it's lost, make a new one."
    )

with connect_accounts() as acc:
    members = accounts.team(acc, me, shop_id)

ui.section_header(eyebrow="Members", title="Who's in the shop")
table = pd.DataFrame(members["members"])
table["signs in with"] = table.apply(
    lambda row: row["username"] if row["username"] else (row["email"] or "Google"), axis=1)
table["role"] = table["role"].str.capitalize()
st.dataframe(table[["display_name", "role", "signs in with", "joined_at"]], hide_index=True,
             column_config={"display_name": "Name", "role": "Role", "signs in with": "Signs in with",
                            "joined_at": "Joined"})

staff_can = ", ".join(ACTIONS[action].lower() for action in sorted(STAFF_ACTIONS))
st.markdown(f"**Owners** can do everything. **Staff** can {staff_can}.")

others = {m["user_id"]: m for m in members["members"] if m["user_id"] != me}
if others:
    with st.form("change_member"):
        person = st.selectbox("Person", list(others), format_func=lambda uid: others[uid]["display_name"])
        action = st.radio("Change", ["Make staff", "Make owner", "Remove from the shop"], horizontal=True)
        confirmed = st.checkbox("Yes, make this change.")
        changed = st.form_submit_button("Apply")
    if changed:
        if not confirmed:
            ui.show_errors(["Tick the box to confirm."])
        else:
            try:
                with connect_accounts() as acc:
                    if action == "Remove from the shop":
                        accounts.remove_member(acc, me, shop_id, person)
                    else:
                        accounts.change_role(acc, me, shop_id, person, "owner" if action == "Make owner" else "staff")
            except ValidationError as problem:
                ui.show_errors(problem.errors)
            else:
                ui.flash("success", f"{action.replace('Make', 'Made').replace('Remove', 'Removed')}: {others[person]['display_name']}.")
                st.rerun()

ui.divider()
ui.section_header(eyebrow="Invitations", title="Invite someone",
                  description="Make a one-time code and give it to the person. They create an account, then join with it.")
with st.form("invite"):
    invite_role = st.radio("They'll join as", ["staff", "owner"], format_func=str.capitalize, horizontal=True)
    invited = st.form_submit_button("Make an invite code", type="primary")
if invited:
    with connect_accounts() as acc:
        code = accounts.create_invitation(acc, me, shop_id, invite_role)
    st.session_state["lekha_new_invite"] = (code, invite_role)
    st.rerun()

if members["invitations"]:
    st.markdown("**Codes not yet used**")
    for invite in members["invitations"]:
        text_col, button_col = st.columns([5, 1.4], vertical_alignment="center")
        text_col.markdown(f"{invite['role'].capitalize()} invite made {invite['created_at'][:16]}, "
                          f"expires {invite['expires_at'][:16]}")
        if button_col.button("Cancel code", key=f"revoke_{invite['invitation_id']}"):
            with connect_accounts() as acc:
                accounts.revoke_invitation(acc, me, shop_id, invite["invitation_id"])
            ui.flash("success", "That invite code no longer works.")
            st.rerun()
