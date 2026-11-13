"""Sales: the till, and the record of recent sales.

Laid out as on the design canvas (Sales, SalesRecorded, SalesNoMatch,
SalesOutOfStock, SalesRecent and SalesPhone artboards).

New sale: type a title, author or ISBN in Find a book and press Enter (a
barcode scanner does both). One match goes straight into the sale;
several are listed to choose from. The basket lives in this browser
session until Record sale, which saves it in one transaction
(services/sales.py). Undo straight afterwards cancels the sale, with a
reason, so nothing is ever deleted.

Recent sales: the latest sales with their books, and a small form to
cancel one with a reason.
"""

from datetime import datetime

import streamlit as st

from database import connect
from services import ValidationError, clock
from services.money import format_rupees
from services.openlibrary import cover_url
from services.sales import cancel_sale, latest_sales, record_sale
from services.till import UNDO_REASON, Basket, recorded_as, till_search
from ui import components as ui
from ui import session

RECENT_SALES = 20

basket = st.session_state.get("basket")
if not isinstance(basket, Basket):           # first visit, or left over from an older version
    basket = st.session_state["basket"] = Basket()

now = clock.now()


def copies(n: int) -> str:
    return f"{n} {'copy' if n == 1 else 'copies'}"


def page_link(path: str, label: str, action: str | None) -> None:
    if action is None or session.can_do(action):
        st.page_link(path, label=label)


def note(text: str) -> None:
    st.html(f'<p class="lekha-note">{ui.escape(text)}</p>')


def say(kind: str, text: str) -> None:
    """Leave a message for the next run: a problem, or what just happened."""
    st.session_state["till_message"] = (kind, text)


# ------------------------------------------------------------ find a book

def render_find(conn) -> None:
    with st.form("till_search", clear_on_submit=True, border=False):
        query = st.text_input("Find a book", key="till_query", max_chars=100,
                              placeholder="Title, author or ISBN. Scan a barcode to add it.")
        submitted = st.form_submit_button("Find")
    if submitted:
        st.session_state.pop("till_message", None)
        result = till_search(conn, query)
        if result.total == 1:                                   # one match: add it
            problem = basket.add(result.books[0])
            st.session_state.pop("till_results_for", None)
            st.session_state.pop("till_last_sale", None)
            if problem:
                say("restock" if result.books[0]["stock_quantity"] <= 0 else "warning", problem)
        else:
            st.session_state["till_results_for"] = query.strip()
        st.rerun()

    render_last_sale(conn)

    message = st.session_state.get("till_message")
    if message:
        kind, text = message
        st.html(f'<p class="lekha-message lekha-message--{"error" if kind == "restock" else kind}">'
                f"{ui.escape(text)}</p>")
        if kind == "restock":
            note("If there are copies on the shelf, correct the stock in Inventory.")
            page_link("views/inventory.py", "Correct the stock", "correct_stock")

    looked_for = st.session_state.get("till_results_for")
    if looked_for is None:
        return
    result = till_search(conn, looked_for)
    if result.total == 0:
        st.html(f'<p class="lekha-message lekha-message--info">No book matches “{ui.escape(looked_for)}”.</p>')
        note("Check the spelling, try the author, or scan the barcode. If it's a new book, add it in Books first.")
        page_link("views/books.py", "Add it in Books", "add_books")
        return
    shown = f" The first {len(result.books)} are shown; type more to narrow it." if result.total > len(result.books) else ""
    note(f"{result.total} matches for “{looked_for}”.{shown}")
    for book in result.books:
        with st.container(horizontal=True, vertical_alignment="center", key=f"till_match_{book['book_id']}"):
            st.html(ui.book_cell_html(book["title"], book["author"], cover_url(book["cover_id"], "S")))
            st.html(f'<span class="lekha-till__price">{format_rupees(book["selling_price_paise"])}'
                    f'<br>{book["stock_quantity"]} in stock</span>', width="content")
            out = book["stock_quantity"] <= 0
            if st.button("Add", key=f"till_add_{book['book_id']}", disabled=out,
                         help="Out of stock" if out else f"Add one copy of {book['title']}"):
                st.session_state.pop("till_last_sale", None)
                problem = basket.add(book)
                if problem:
                    say("warning", problem)
                else:
                    st.session_state.pop("till_message", None)
                    st.session_state.pop("till_results_for", None)
                st.rerun()


def render_last_sale(conn) -> None:
    """After Record sale: what was saved, and Undo in case it was a mistake."""
    last = st.session_state.get("till_last_sale")
    if not last:
        return
    if last["undone"]:
        st.html(f'<p class="lekha-message lekha-message--info">Sale #{last["sale_id"]} undone. '
                "Its copies are back in stock.</p>")
        return
    with st.container(horizontal=True, vertical_alignment="center", key="till_recorded"):
        st.html(f'<p class="lekha-message lekha-message--success"><strong>Sale #{last["sale_id"]} recorded.</strong> '
                f'{copies(last["copies"])}, {format_rupees(last["total_paise"])}. Ready for the next customer.</p>')
        if st.button("Undo", key="till_undo", help="Cancel this sale and put its copies back in stock"):
            try:
                cancel_sale(conn, last["sale_id"], UNDO_REASON, cancelled_by=session.user_id())
            except ValidationError as problem:
                say("warning", " ".join(problem.errors))
            else:
                last["undone"] = True
            st.rerun()


# --------------------------------------------------------------- the sale

def render_basket(conn) -> None:
    with st.container(key="lekha_card_basket"):
        st.html('<h2 class="lekha-cardhead__title">This sale</h2>')
        if not basket:
            note("The basket is empty. Find a book to start a sale.")
            return
        for line in list(basket.lines.values()):
            with st.container(horizontal=True, vertical_alignment="center", key=f"till_line_{line.book_id}"):
                st.html(ui.book_cell_html(line.title, f"{format_rupees(line.unit_price_paise)} each",
                                          cover_url(line.cover_id, "S")))
                if st.button("−", key=f"till_fewer_{line.book_id}", help="One fewer",
                             disabled=line.quantity == 1):
                    basket.fewer(line.book_id)
                    st.rerun()
                st.html(f'<span class="lekha-qty" aria-label="{line.quantity} copies">{line.quantity}</span>',
                        width="content")
                if st.button("+", key=f"till_more_{line.book_id}", help="One more"):
                    problem = basket.more(line.book_id)
                    if problem:
                        say("warning", problem)
                    st.rerun()
                st.html(f'<span class="lekha-till__line-total">{format_rupees(line.total_paise)}</span>',
                        width="content")
                if st.button("Remove", key=f"till_remove_{line.book_id}", type="tertiary",
                             help=f"Remove {line.title} from this sale"):
                    basket.remove(line.book_id)
                    st.session_state.pop("till_message", None)
                    st.rerun()

        st.html(f'<div class="lekha-till__total"><span>{copies(basket.copies)}</span>'
                f'<span>{format_rupees(basket.total_paise)}</span></div>')
        render_when()
        if st.button(f"Record sale · {format_rupees(basket.total_paise)}", key="till_record", type="primary",
                     width="stretch", shortcut="ctrl+enter"):
            record(conn)          # the button itself shows "Ctrl + Enter"


def render_when() -> None:
    """When the sale will be saved as happening: now, or a time chosen for
    entering receipts afterwards."""
    when = st.session_state.get("till_when")
    with st.container(horizontal=True, vertical_alignment="center"):
        note(recorded_as(when, now))
        with st.popover("Change date or time", type="tertiary"):
            day = st.date_input("Date", value=(when or now).date(), max_value=now.date(), key="till_day",
                                format="DD/MM/YYYY")
            moment = st.time_input("Time", value=(when or now).time(), step=60, key="till_time")
            if st.button("Use this date and time", key="till_when_set"):
                st.session_state["till_when"] = datetime.combine(day, moment)
                st.rerun()
            if when and st.button("Back to now", key="till_when_now"):
                st.session_state["till_when"] = None
                st.rerun()


def record(conn) -> None:
    try:
        sale_id = record_sale(conn, basket.sale_lines(), sale_datetime=st.session_state.get("till_when"),
                              recorded_by=session.user_id())
    except ValidationError as problem:
        say("warning", " ".join(problem.errors))
        st.rerun()
    st.session_state["till_last_sale"] = {"sale_id": sale_id, "copies": basket.copies,
                                          "total_paise": basket.total_paise, "undone": False}
    basket.clear()
    for key in ("till_when", "till_message", "till_results_for", "till_day", "till_time"):
        st.session_state.pop(key, None)
    st.rerun()


# ----------------------------------------------------------- recent sales

def render_recent(conn) -> None:
    rows = latest_sales(conn, limit=RECENT_SALES)
    if not rows:
        note("No sales have been recorded yet.")
        return
    names = session.names({row["recorded_by"] for row in rows if row["recorded_by"]})

    def when(row) -> str:
        moment = datetime.fromisoformat(row["sale_datetime"])
        return f"{moment.day} {moment:%b}, {moment:%H:%M}"

    with st.container(key="lekha_card_recent"):
        st.html(ui.data_table_html(
            [("Sale", "left"), ("When", "left"), ("Books", "left"), ("Copies", "right"), ("Total", "right"),
             ("Status", "left"), ("Recorded by", "left")],
            [[f"#{row['sale_id']}", when(row), row["books"], row["copies"], format_rupees(row["total_paise"]),
              ui.Html(ui.status_html("success", "Completed") if row["status"] == "completed"
                      else ui.status_html("neutral", "Cancelled")),
              names.get(row["recorded_by"], "Not recorded")]
             for row in rows],
            css_class="lekha-nowrap",
        ))
        note(f"Showing the last {len(rows)} {'sale' if len(rows) == 1 else 'sales'}.")

    completed = {row["sale_id"]: row for row in rows if row["status"] == "completed"}
    with st.container(key="lekha_card_cancel"):
        ui.card_heading("Cancel a sale",
                        "The copies go back into stock and the sale stays in the record, marked as cancelled.")
        if not completed:
            note("There are no completed sales here to cancel.")
            return
        with st.form("cancel_sale", border=False):
            sale_id = st.selectbox("Sale", list(completed), key="cancel_sale_id", format_func=lambda sid: (
                f"#{sid} · {when(completed[sid])} · {format_rupees(completed[sid]['total_paise'])}"))
            reason = st.text_input("Reason (required)", key="cancel_reason", max_chars=200,
                                   placeholder="For example: customer returned the book")
            submitted = st.form_submit_button("Cancel sale")
        if submitted:
            try:
                cancel_sale(conn, sale_id, reason, cancelled_by=session.user_id())
            except ValidationError as problem:
                ui.show_errors(problem.errors)
                return
            ui.flash("success", f"Sale #{sale_id} cancelled. Copies returned to stock: {completed[sale_id]['books']}.")
            st.rerun()


# ------------------------------------------------------------------ page

ui.page_header("Sales", "Find a book, add it, record the sale. A barcode scanner types the ISBN for you.")
ui.show_flash()

with connect() as conn:
    has_books = conn.execute("SELECT EXISTS (SELECT 1 FROM books)").fetchone()[0]
    new_tab, recent_tab = st.tabs(["New sale", "Recent sales"], key="sales_view", on_change="rerun")
    if new_tab.open:
        with new_tab:
            if not has_books:
                note("There are no books to sell yet. Add your first book, then come back to the till.")
                page_link("views/books.py", "Add a book", "add_books")
            else:
                find_col, sale_col = st.columns([1, 1], gap="medium")
                with find_col:
                    render_find(conn)
                with sale_col:
                    render_basket(conn)
    if recent_tab.open:
        with recent_tab:
            render_recent(conn)
