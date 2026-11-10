"""Inventory: low-stock alerts, stock corrections and their history.

The rules live in services/inventory.py. This page only shows them.
"""

import pandas as pd
import streamlit as st

from database import connect
from services import ValidationError
from services.books import get_book, search_books
from services.inventory import (
    REASONS,
    StockChangedError,
    correct_stock,
    low_stock_books,
    recent_adjustments,
)
from ui import components as ui
from ui import session


def render_alerts(conn) -> None:
    ui.section_header(
        eyebrow="Alerts",
        title="Low on stock",
        description=(
            "Books at or below the reorder level you set. This is an alert, not a "
            "recommendation to reorder: that decision also depends on how fast a "
            "book sells and how long a delivery takes."
        ),
    )
    rows = low_stock_books(conn)
    if not rows:
        ui.empty_state("No books are at or below their reorder level.")
        return
    st.markdown(f"**{len(rows)}** {'book needs' if len(rows) == 1 else 'books need'} attention.")
    st.dataframe(
        pd.DataFrame(rows)[["title", "stock_status", "stock_quantity", "reorder_level", "author"]],
        hide_index=True,
        column_config={
            "title": st.column_config.TextColumn("Title"),
            "author": st.column_config.TextColumn("Author"),
            "stock_quantity": st.column_config.NumberColumn("In stock"),
            "reorder_level": st.column_config.NumberColumn("Reorder level"),
            "stock_status": st.column_config.TextColumn("Status"),
        },
    )


def render_correction(conn) -> None:
    ui.section_header(
        eyebrow="Corrections",
        title="Correct stock",
        description=(
            "After counting a shelf, receiving a delivery or finding damaged copies, "
            "enter the number of copies actually there. Lekha records the change and why."
        ),
    )
    books = search_books(conn)
    if not books:
        st.info("There are no books yet.")
        return
    labels = {book["book_id"]: f"{book['title']} — {book['author']}" for book in books}
    book_id = st.selectbox(
        "Book", list(labels), format_func=labels.get, index=None,
        placeholder="Choose a book", key="correct_choice",
    )

    # Remember which stock number the user is looking at. On the run where
    # they press Save, this is read back BEFORE the page stores the new
    # number, so the correction is checked against what they actually saw.
    shown = st.session_state.get("correct_shown")
    if book_id is None:
        st.session_state["correct_shown"] = None
        return
    book = get_book(conn, book_id)
    current = book["stock_quantity"]
    expected = shown["quantity"] if shown and shown["book_id"] == book_id else current

    st.markdown(f"Lekha's current count: **{current}** · reorder level {book['reorder_level']}")
    version = st.session_state.setdefault("correct_form_version", 0)
    with st.form(f"correct_form_{book_id}_{version}"):
        counted_col, reason_col = st.columns(2)
        counted = counted_col.number_input(
            "Copies actually there", min_value=0, step=1, value=current,
            key=f"correct_counted_{book_id}_{version}",
        )
        reason = reason_col.selectbox(
            "Reason", list(REASONS), format_func=REASONS.get, key=f"correct_reason_{book_id}_{version}",
        )
        note = st.text_input(
            "Note (required when the reason is “Other”)", key=f"correct_note_{book_id}_{version}",
        )
        submitted = st.form_submit_button("Save correction", type="primary")

    if submitted:
        try:
            correct_stock(conn, book_id, expected, int(counted), reason, note, recorded_by=session.user_id())
        except ValidationError as problem:
            ui.show_errors(problem.errors)
        except StockChangedError as problem:
            st.error(str(problem))
        else:
            change = int(counted) - expected
            ui.flash(
                "success",
                f"Stock for “{book['title']}” changed from {expected} to {int(counted)} "
                f"({change:+d}). The change is recorded below.",
            )
            st.session_state["correct_form_version"] = version + 1
            st.rerun()

    st.session_state["correct_shown"] = {"book_id": book_id, "quantity": current}


def render_history(conn) -> None:
    ui.section_header(
        eyebrow="History",
        title="Recent corrections",
        description="The latest 20 changes, newest first. Corrections are never edited or deleted.",
    )
    rows = recent_adjustments(conn)
    if not rows:
        ui.empty_state("No stock corrections have been recorded yet.")
        return
    table = pd.DataFrame(rows)
    table["change"] = table["change"].map(lambda value: f"{value:+d}")   # -3, +6
    table["note"] = table["note"].fillna("")   # show blank, not "None", when there's no note
    people = session.names(table["recorded_by"].dropna())
    table["by"] = table["recorded_by"].map(lambda uid: people.get(uid, "") if pd.notna(uid) else "")
    st.dataframe(
        table[["title", "change", "reason_label", "adjusted_at", "by", "quantity_before", "quantity_after", "note"]],
        hide_index=True,
        column_config={
            "adjusted_at": st.column_config.TextColumn("When"),
            "title": st.column_config.TextColumn("Book"),
            "quantity_before": st.column_config.NumberColumn("Before"),
            "quantity_after": st.column_config.NumberColumn("After"),
            "change": st.column_config.TextColumn("Change"),
            "reason_label": st.column_config.TextColumn("Reason"),
            "note": st.column_config.TextColumn("Note"),
            "by": st.column_config.TextColumn("By"),
        },
    )


# ------------------------------------------------------------------ page

ui.page_intro(
    eyebrow="Shelf check",
    title="Inventory",
    description=("What's running low, and a recorded way to correct stock counts."
                 if session.can_do("correct_stock")
                 else "What's running low. Only the shop's owners can correct stock counts."),
)
ui.show_flash()

with connect() as conn:
    render_alerts(conn)
    if session.can_do("correct_stock"):      # owners only
        ui.divider()
        render_correction(conn)
        ui.divider()
        render_history(conn)
