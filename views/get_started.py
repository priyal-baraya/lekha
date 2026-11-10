"""Create a shop or join one: for people signed in but not part of any shop yet,
and from Settings for anyone who wants another shop."""

import streamlit as st

from database import connect_accounts, ensure_shop_database
from services import ValidationError, accounts
from ui import components as ui
from ui import session

ui.page_intro(
    eyebrow="Get started",
    title="Your shops",
    description="Start a new shop as its owner, or join an existing shop with an invite code from its owner.",
)
ui.show_flash()

create_col, join_col = st.columns(2, gap="large")

with create_col:
    ui.section_header(eyebrow="New shop", title="Start a shop",
                      description="You'll be its owner, and can invite staff afterwards.")
    with st.form("create_shop"):
        name = st.text_input("Shop name", placeholder="As it appears on your sign")
        created = st.form_submit_button("Create shop", type="primary")
    if created:
        try:
            with connect_accounts() as acc:
                shop_id = accounts.create_shop(acc, session.user_id(), name)
        except ValidationError as problem:
            ui.show_errors(problem.errors)
        else:
            ensure_shop_database(shop_id)
            session.choose_shop(shop_id)
            st.session_state["lekha_go_home"] = True      # app.py opens the Overview
            ui.flash("success", "Your shop is ready. Add your first book on the Books page.")
            st.rerun()

with join_col:
    ui.section_header(eyebrow="Existing shop", title="Join with a code",
                      description="Ask the shop's owner for an invite code. Each code works once, for 7 days.")
    with st.form("join_shop"):
        code = st.text_input("Invite code", placeholder="For example ABCDE-FGHJK")
        joined = st.form_submit_button("Join shop", type="primary")
    if joined:
        try:
            with connect_accounts() as acc:
                shop_id = accounts.redeem_invitation(acc, session.user_id(), code)
        except ValidationError as problem:
            ui.show_errors(problem.errors)
        else:
            session.choose_shop(shop_id)
            st.session_state["lekha_go_home"] = True
            ui.flash("success", "You've joined the shop.")
            st.rerun()
