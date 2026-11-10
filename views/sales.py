"""Sales: build a sale in a basket, complete it, and cancel past sales.

The basket lives in st.session_state (this browser session's memory)
until "Complete sale". Nothing reaches the database before then, and
saving happens in one transaction inside services/sales.py.
"""

from datetime import date, datetime

import pandas as pd
import streamlit as st

from database import connect
from services import ValidationError
from services.books import search_books
from services.money import format_rupees, paise_to_rupees
from services.sales import SaleLine, cancel_sale, get_sale, list_sales, record_sale
from ui import components as ui
from ui import session

# basket = {book_id: {"quantity": int, "unit_price_paise": int}}
basket: dict[int, dict] = st.session_state.setdefault("basket", {})


def copies(n: int) -> str:
    return f"{n} {'copy' if n == 1 else 'copies'}"


# ------------------------------------------------------------- new sale

def render_add_to_basket(books_by_id: dict[int, dict]) -> None:
    pick_version = st.session_state.setdefault("sale_pick_version", 0)

    def label(book_id: int) -> str:
        book = books_by_id[book_id]
        return (f"{book['title']} — {format_rupees(book['selling_price_paise'])} · "
                f"{book['stock_quantity']} in stock")

    book_col, qty_col = st.columns([3, 1])
    book_id = book_col.selectbox(
        "Book", list(books_by_id), format_func=label, index=None,
        placeholder="Choose a book", key=f"sale_book_{pick_version}",
    )
    if book_id is None:
        return
    book = books_by_id[book_id]
    already = basket.get(book_id, {}).get("quantity", 0)
    available = book["stock_quantity"] - already
    if available <= 0:
        qty_col.empty()
        st.warning(
            f"No copies of “{book['title']}” left to add"
            + (f" ({copies(already)} already in this sale)." if already else ": it's out of stock.")
        )
        return
    quantity = qty_col.number_input(
        "Quantity", min_value=1, max_value=available, value=1, step=1, key=f"sale_qty_{pick_version}",
    )
    if st.button("Add to sale", key=f"sale_add_{pick_version}"):
        line = basket.setdefault(book_id, {"quantity": 0, "unit_price_paise": book["selling_price_paise"]})
        line["quantity"] += int(quantity)
        st.session_state["sale_pick_version"] = pick_version + 1   # empty the picker
        st.rerun()


def render_basket(books_by_id: dict[int, dict]) -> int:
    """Show the basket's lines with remove buttons. Returns the total in paise."""
    if not basket:
        st.markdown("The sale is empty. Choose a book above and click **Add to sale**.")
        return 0
    # Each line is one sentence ("2 × ₹399.00 = ₹798.00") next to its Remove
    # button. A five-column grid looked tidy on desktop, but on a phone
    # Streamlit stacks columns, which separated every number from its label.
    st.markdown("**This sale**")
    total = 0
    for book_id, line in list(basket.items()):
        title = books_by_id.get(book_id, {}).get("title", f"Book #{book_id} (no longer in the catalogue)")
        line_total = line["quantity"] * line["unit_price_paise"]
        total += line_total
        text_col, button_col = st.columns([5, 1.2], vertical_alignment="center")
        text_col.markdown(
            f"{title}  \n{copies(line['quantity'])} × {format_rupees(line['unit_price_paise'])} "
            f"= **{format_rupees(line_total)}**"
        )
        if button_col.button("Remove", key=f"sale_remove_{book_id}", help=f"Remove “{title}” from this sale"):
            del basket[book_id]
            st.rerun()
    copies_total = sum(line["quantity"] for line in basket.values())
    st.markdown(f"**Total: {format_rupees(total)}** · {copies(copies_total)}")
    return total


def render_new_sale(conn) -> None:
    books_by_id = {book["book_id"]: book for book in search_books(conn)}
    if not books_by_id:
        st.info("There are no books in the catalogue yet. Add some on the Books page first.")
        return
    render_add_to_basket(books_by_id)
    st.divider()
    total = render_basket(books_by_id)
    if not basket:
        return

    sale_version = st.session_state.setdefault("sale_version", 0)
    earlier = st.checkbox(
        "This sale happened earlier (for entering receipts later)", key=f"sale_earlier_{sale_version}",
    )
    sale_datetime = None
    if earlier:
        default_time = st.session_state.setdefault("sale_default_time", datetime.now().time().replace(second=0, microsecond=0))
        date_col, time_col = st.columns(2)
        day = date_col.date_input("Date", value=date.today(), max_value=date.today(), key=f"sale_date_{sale_version}")
        moment = time_col.time_input("Time", value=default_time, step=60, key=f"sale_time_{sale_version}")
        sale_datetime = datetime.combine(day, moment)

    complete_col, clear_col, _ = st.columns([1.3, 1, 3])
    if clear_col.button("Clear sale", key=f"sale_clear_{sale_version}"):
        basket.clear()
        st.rerun()
    if complete_col.button("Complete sale", type="primary", key=f"sale_complete_{sale_version}"):
        lines = [SaleLine(book_id, line["quantity"], line["unit_price_paise"]) for book_id, line in basket.items()]
        try:
            sale_id = record_sale(conn, lines, sale_datetime=sale_datetime, recorded_by=session.user_id())
        except ValidationError as problem:
            ui.show_errors(problem.errors)
            return
        copies_total = sum(line.quantity for line in lines)
        ui.flash("success", f"Sale #{sale_id} recorded: {copies(copies_total)}, {format_rupees(total)}. Stock has been updated.")
        basket.clear()
        st.session_state["sale_version"] = sale_version + 1
        st.session_state.pop("sale_default_time", None)
        st.rerun()


# --------------------------------------------------------- recent sales

def render_recent_sales(conn) -> None:
    rows = list_sales(conn)
    if not rows:
        ui.empty_state("No sales have been recorded yet.")
        return
    table = pd.DataFrame(rows)
    table["total"] = table["total_paise"].map(lambda paise: float(paise_to_rupees(paise)))
    table["status"] = table["status"].str.capitalize()
    people = session.names(table["recorded_by"].dropna())
    table["recorded_by"] = table["recorded_by"].map(
        lambda uid: people.get(uid, "Not recorded") if pd.notna(uid) else "Not recorded")
    st.markdown(f"The latest {len(rows)} sales, newest first. Cancelled sales stay listed but don't count as revenue.")
    st.dataframe(
        table[["sale_id", "sale_datetime", "total", "status", "copies", "recorded_by"]],
        hide_index=True,
        column_config={
            "sale_id": st.column_config.NumberColumn("Sale #", format="%d"),
            "sale_datetime": st.column_config.TextColumn("When"),
            "copies": st.column_config.NumberColumn("Copies"),
            "total": st.column_config.NumberColumn("Total", format="₹%.2f"),
            "status": st.column_config.TextColumn("Status"),
            "recorded_by": st.column_config.TextColumn("Recorded by"),
        },
    )

    labels = {
        row["sale_id"]: f"#{row['sale_id']} · {row['sale_datetime'][:16]} · "
                        f"{format_rupees(row['total_paise'])} · {row['status'].capitalize()}"
        for row in rows
    }
    sale_id = st.selectbox(
        "Open a sale", list(labels), format_func=labels.get, index=None,
        placeholder="Choose a sale to see its books or cancel it", key="sale_open",
    )
    if sale_id is None:
        return
    sale = get_sale(conn, sale_id)
    lines = pd.DataFrame(sale["lines"])
    lines["unit_price"] = lines["unit_price_paise"].map(lambda paise: float(paise_to_rupees(paise)))
    lines["line_total"] = lines["line_total_paise"].map(lambda paise: float(paise_to_rupees(paise)))
    st.dataframe(
        lines[["title", "quantity", "unit_price", "line_total"]],
        hide_index=True,
        column_config={
            "title": st.column_config.TextColumn("Book"),
            "quantity": st.column_config.NumberColumn("Copies"),
            "unit_price": st.column_config.NumberColumn("Unit price", format="₹%.2f"),
            "line_total": st.column_config.NumberColumn("Line total", format="₹%.2f"),
        },
    )
    people = session.names([sale["recorded_by"], sale["cancelled_by"]])
    recorder = people.get(sale["recorded_by"], "not recorded")
    st.markdown(f"**Total: {format_rupees(sale['total_paise'])}** · {copies(sale['copies'])} · "
                f"recorded for {sale['sale_datetime']} by {recorder}")

    if sale["status"] == "cancelled":
        canceller = people.get(sale["cancelled_by"], "not recorded")
        st.info(f"Cancelled on {sale['cancelled_at']} by {canceller}. Reason: {sale['cancel_reason']}")
        return

    with st.form(f"cancel_form_{sale_id}"):
        st.markdown(
            "**Cancel this sale.** Use this for a sale entered by mistake. Its copies go back into "
            "stock and it stops counting as revenue. Sales are never edited or deleted, so to fix "
            "a mistake, cancel the sale and record it again."
        )
        reason = st.text_input("Reason (required)", key=f"cancel_reason_{sale_id}")
        confirmed = st.checkbox(
            f"Yes, cancel sale #{sale_id} and return its copies to stock.", key=f"cancel_confirm_{sale_id}",
        )
        submitted = st.form_submit_button("Cancel sale")
    if not submitted:
        return
    if not confirmed:
        ui.show_errors(["Tick the box to confirm the cancellation."])
        return
    try:
        cancel_sale(conn, sale_id, reason, cancelled_by=session.user_id())
    except ValidationError as problem:
        ui.show_errors(problem.errors)
        return
    returned = ", ".join(f"{line['title']} ({line['quantity']})" for line in sale["lines"])
    ui.flash("success", f"Sale #{sale_id} cancelled. Copies returned to stock: {returned}.")
    st.rerun()


# ------------------------------------------------------------------ page

ui.page_intro(
    eyebrow="At the till",
    title="Sales",
    description="Record what was sold, and cancel a sale entered by mistake.",
)
ui.show_flash()

with connect() as conn:
    new_tab, recent_tab = st.tabs(["New sale", "Recent sales"], key="sales_tab", on_change="rerun")
    if new_tab.open:
        with new_tab:
            render_new_sale(conn)
    if recent_tab.open:
        with recent_tab:
            render_recent_sales(conn)
