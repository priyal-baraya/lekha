"""Switch shop: for people who belong to more than one shop.

Opened from the account menu. Each shop is a button; choosing one opens
its Overview. The person's role in each shop is read fresh, like
everywhere else, so a removed shop disappears from this list at once.
"""

import streamlit as st

from database import connect_accounts
from services import accounts
from ui import components as ui
from ui import session

ui.page_header("Switch shop", "Choose the shop to work in. Each shop keeps its own books, sales and team.")

with connect_accounts() as acc:
    memberships = accounts.memberships(acc, session.user_id())

current = st.session_state.get(session.SHOP)
for membership in memberships:
    here = membership.shop_id == current
    # Button labels are read as Markdown, and shop names are typed by people.
    label = f"{ui.plain(membership.shop_name)} · {membership.role}" + (" · open now" if here else "")
    if st.button(label, key=f"switch_shop_{membership.shop_id}", disabled=here, width="stretch"):
        session.choose_shop(membership.shop_id)
        st.switch_page("views/overview.py")
