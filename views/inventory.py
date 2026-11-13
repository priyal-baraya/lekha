"""Inventory: low-stock alerts, stock corrections and their history.

Laid out as on the design canvas (Inventory and InventoryClear
artboards). The rules live in services/inventory.py; this page only
shows them.
"""

from datetime import datetime

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
from services.openlibrary import cover_url
from services.sentences import correction_hint, low_stock_note
from ui import components as ui
from ui import session


def note(text: str) -> None:
    st.html(f'<p class="lekha-note">{ui.escape(text)}</p>')


def signed(change: int) -> str:
    """+6 or −1, with a real minus sign."""
    return f"+{change}" if change > 0 else f"−{abs(change)}" if change < 0 else "0"


def render_alerts(conn) -> None:
    rows = low_stock_books(conn)
    with st.container(key="lekha_card_low_stock"):
        ui.card_heading("Low on stock", "At or below their reorder level.")
        if not rows:
            st.html('<p class="lekha-message lekha-message--success"><strong>Nothing to reorder.</strong> '
                    "Every book is above its reorder level.</p>")
            return
        st.html(ui.data_table_html(
            [("Book", "left"), ("In stock", "right"), ("Reorder at", "right"), ("Status", "left")],
            [[ui.book_cell_html(book["title"], book["author"], cover_url(book["cover_id"], "S")),
              book["stock_quantity"], book["reorder_level"],
              ui.Html(ui.stock_status_html(book["stock_quantity"], book["reorder_level"]))]
             for book in rows],
            css_class="lekha-wide-only",
        ))
        st.html('<div class="lekha-narrow-only">' + ui.book_list_html(
            [(book["title"], cover_url(book["cover_id"], "S"), book["stock_quantity"], book["reorder_level"])
             for book in rows]) + "</div>")
        note(low_stock_note(len(rows)))


def render_correction(conn) -> None:
    with st.container(key="lekha_card_correct"):
        ui.card_heading("Correct stock", "Count the copies on the shelf. Lekha records the difference and why.")
        books = search_books(conn)
        if not books:
            note("There are no books yet.")
            return
        # Title and author only: Streamlit keeps the chosen option's wording
        # after a save, so a stock number here would go stale. The line under
        # the count field says Lekha's current count instead.
        labels = {book["book_id"]: f"{book['title']} · {book['author']}" for book in books}
        book_id = st.selectbox(
            "Book", list(labels), format_func=labels.get, index=None,
            placeholder="Choose a book", key="correct_choice",
        )

        # Remember which stock number the person is looking at. On the run
        # where they press Save, this is read back BEFORE the page stores the
        # new number, so the correction is checked against what they saw.
        shown = st.session_state.get("correct_shown")
        if book_id is None:
            st.session_state["correct_shown"] = None
            return
        book = get_book(conn, book_id)
        current = book["stock_quantity"]
        expected = shown["quantity"] if shown and shown["book_id"] == book_id else current

        # Not a form: the line saying what will be recorded updates as the count changes.
        version = st.session_state.setdefault("correct_form_version", 0)
        counted_col, reason_col = st.columns(2)
        counted = counted_col.number_input(
            "Copies counted on the shelf", min_value=0, step=1, value=current,
            key=f"correct_counted_{book_id}_{version}",
        )
        reason = reason_col.selectbox(
            "Reason", list(REASONS), format_func=REASONS.get, key=f"correct_reason_{book_id}_{version}",
        )
        note(correction_hint(current, int(counted)))
        why = st.text_input(
            "Note (required when the reason is “Other”)", key=f"correct_note_{book_id}_{version}",
            max_chars=200, placeholder="What happened",
        )
        save = st.button("Save correction", type="primary", key=f"correct_save_{book_id}_{version}",
                         disabled=int(counted) == current)

        if save:
            session.require("correct_stock")     # checked again at the moment of saving
            try:
                correct_stock(conn, book_id, expected, int(counted), reason, why, recorded_by=session.user_id())
            except ValidationError as problem:
                ui.show_errors(problem.errors)
            except StockChangedError as problem:
                st.error(str(problem))
            else:
                ui.flash(
                    "success",
                    f"Stock for “{book['title']}” changed from {expected} to {int(counted)} "
                    f"({signed(int(counted) - expected)}). The change is recorded below.",
                )
                st.session_state["correct_form_version"] = version + 1
                st.rerun()

        st.session_state["correct_shown"] = {"book_id": book_id, "quantity": current}


def render_history(conn) -> None:
    rows = recent_adjustments(conn)
    with st.container(key="lekha_card_corrections"):
        st.html('<h2 class="lekha-cardhead__title">Recent corrections</h2>')
        if not rows:
            note("No corrections yet. When a shelf count doesn't match Lekha, correct it above and the "
                 "change is recorded here with its reason.")
            return
        people = session.names({row["recorded_by"] for row in rows if row["recorded_by"]})

        def when(text: str) -> str:
            moment = datetime.fromisoformat(text)
            return f"{moment.day} {moment:%b}, {moment:%H:%M}"

        st.html(ui.data_table_html(
            [("When", "left"), ("Book", "left"), ("Before", "right"), ("After", "right"), ("Change", "right"),
             ("Reason", "left"), ("Note", "left"), ("By", "left")],
            [[when(row["adjusted_at"]), row["title"], row["quantity_before"], row["quantity_after"],
              signed(row["change"]), row["reason_label"], row["note"] or "",
              people.get(row["recorded_by"], "")]
             for row in rows],
            css_class="lekha-nowrap",
        ))
        note("The latest 20 changes, newest first. Corrections are never edited or deleted.")


# ------------------------------------------------------------------ page

ui.page_header(
    "Inventory",
    "What's running low, and corrections when a count doesn't match." if session.can_do("correct_stock")
    else "What's running low. Only the shop's owners can correct stock counts.",
)
ui.show_flash()

with connect() as conn:
    render_alerts(conn)
    if session.can_do("correct_stock"):      # owners only
        render_correction(conn)
        render_history(conn)
