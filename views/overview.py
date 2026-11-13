"""Overview: Lekha's front page, laid out as on the design canvas
(Main and OverviewEmpty artboards).

At the top, a date line and one sentence about today. Then three figures,
each compared fairly with an earlier one: today so far against the same
time last week, this week so far, and the last 30 days against the 30
days before. Below them: the books to reorder, the latest sales, and
what's selling this week.

A shop with no sales yet sees the steps to get started instead.
Every number comes from the database, through services/analytics.py, the
same code the Insights page uses.
"""

from datetime import datetime, time, timedelta

import streamlit as st

from database import connect
from services import analytics, clock
from services.books import count_books
from services.comparisons import compare_money, same_time_last_week
from services.inventory import low_stock_books
from services.money import format_rupees, format_rupees_whole
from services.openlibrary import cover_url
from services.sales import latest_sales
from services.sentences import overview_sentence, sale_time_label, selling_well_note
from ui import components as ui
from ui import session

REORDER_ROWS = 5        # rows in "Reorder these"; the rest are in Inventory
LATEST_SALES = 5
SHELF_BOOKS = 5

now = clock.now()
today = now.date()

with connect() as conn:
    total_books = count_books(conn)
    has_sales = analytics.earliest_sale_date(conn) is not None
    low_stock = low_stock_books(conn)
    today_totals = analytics.today_so_far(conn, now)
    last_week_totals = analytics.same_time_last_week(conn, now)
    week_totals = analytics.week_so_far(conn, now)
    period = analytics.period_for(conn, "last_30", today)
    period_totals = analytics.summary(conn, period)
    before = analytics.previous_period(period)
    before_totals = analytics.summary(conn, before)
    recent = latest_sales(conn, since=datetime.combine(today - timedelta(days=1), time()), limit=LATEST_SALES)
    selling = analytics.selling_this_week(conn, now, limit=SHELF_BOOKS)

# ---------- The date line and today's sentence ----------
date_line = f"{now:%A} {now.day} {now:%B} · {session.shop_name() or 'Your shop'}"
ui.summary_header(date_line, overview_sentence(total_books, has_sales, today_totals["revenue_paise"], len(low_stock)))
ui.show_flash()     # e.g. "Your shop is ready" after creating or joining a shop


def copies_note(totals: dict) -> str:
    sales = totals["transactions"]
    copies = totals["copies"]
    return f"{sales} {'sale' if sales == 1 else 'sales'} · {copies} {'copy' if copies == 1 else 'copies'}"


def page_link(path: str, label: str, action: str | None) -> None:
    """A link to another page, only if this person's role can open it."""
    if action is None or session.can_do(action):
        st.page_link(path, label=label)


# ---------- A shop that hasn't sold anything yet: the steps ----------
if not has_sales:
    steps = []
    if total_books == 0:
        steps.append(("Add your first book",
                      "Look it up by ISBN or title on Open Library, check the details, then add your own "
                      "price and copies in stock.", ("views/books.py", "Add a book", "add_books")))
    steps.append(("Record your first sale",
                  "Once a book is in, sell it from the Sales page. It takes a few seconds at the till.",
                  ("views/sales.py", "Go to Sales", "sell") if total_books else None))
    steps.append(("See your trends",
                  "Weekly sales, best sellers and genres appear after two weeks of sales. Until then, "
                  "Lekha shows only what you've recorded.", None))
    count_word = {2: "Two", 3: "Three"}[len(steps)]
    with st.container(key="lekha_card_steps"):
        st.html(f'<h2 class="lekha-steps-title">{count_word} steps to get started</h2>')
        for number, (title, text, link) in enumerate(steps, start=1):
            step_col, action_col = st.columns([5, 1], vertical_alignment="center")
            with step_col:
                st.html(ui.step_html(number, title, text, waiting=link is None))
            with action_col:
                if link:
                    page_link(*link)
                else:
                    st.html('<p class="lekha-note">After 2 weeks</p>' if title == "See your trends"
                            else '<p class="lekha-note">After your first book</p>')

    ui.figure_strip([
        ui.Figure("Today", "No sales yet", words=True),
        ui.Figure("Books in the shop", str(total_books) if total_books else "None yet", words=not total_books),
        ui.Figure("Low on stock", str(len(low_stock)) if low_stock else "Nothing to reorder",
                  words=not low_stock),
    ])

# ---------- A trading shop: three fair figures ----------
else:
    with st.container(key="lekha_overview_figures"):     # the phone layout hides "This week so far"
        ui.figure_strip([
            ui.Figure("Today", format_rupees_whole(today_totals["revenue_paise"]),
                      same_time_last_week(last_week_totals["revenue_paise"], f"{now:%A}"),
                      note=copies_note(today_totals)),
            ui.Figure("This week so far", format_rupees_whole(week_totals["revenue_paise"]),
                      note="Monday to today"),
            ui.Figure("Last 30 days", format_rupees_whole(period_totals["revenue_paise"]),
                      compare_money(period_totals["revenue_paise"], before_totals["revenue_paise"]),
                      note=f"Compared with {before.start.day} {before.start:%b} to {before.end.day} {before.end:%b}"),
        ])

# ---------- Books to reorder, and the latest sales ----------
show_reorder = bool(low_stock) and session.can_do("view_stock")
show_recent = has_sales
if show_reorder or show_recent:
    columns = st.columns(2, gap="small") if (show_reorder and show_recent) else [st.container()]
    cards = iter(columns)

    if show_reorder:
        with next(cards), st.container(key="lekha_card_reorder"):
            ui.card_heading("Reorder these", "At or below their reorder level, emptiest first.")
            st.html(ui.data_table_html(
                [("Book", "left"), ("In stock", "right"), ("Reorder at", "right"), ("Status", "left")],
                [[ui.book_cell_html(book["title"], book["author"], cover_url(book["cover_id"], "S")),
                  book["stock_quantity"], book["reorder_level"],
                  ui.Html(ui.stock_status_html(book["stock_quantity"], book["reorder_level"]))]
                 for book in low_stock[:REORDER_ROWS]],
                css_class="lekha-wide-only",
            ))
            st.html('<div class="lekha-narrow-only">' + ui.book_list_html(
                [(book["title"], cover_url(book["cover_id"], "S"), book["stock_quantity"], book["reorder_level"])
                 for book in low_stock[:REORDER_ROWS]]) + "</div>")
            if len(low_stock) > REORDER_ROWS:          # only when the list is cut short
                ui.showing_note(REORDER_ROWS, len(low_stock))
            page_link("views/inventory.py", "See all in Inventory", "view_stock")

    if show_recent:
        with next(cards), st.container(key="lekha_card_latest_sales"):
            ui.card_heading("Latest sales", "Today and yesterday.")
            if recent:
                names = session.names({sale["recorded_by"] for sale in recent if sale["recorded_by"]})
                st.html(ui.data_table_html(
                    [("When", "left"), ("Books", "left"), ("Total", "right"), ("By", "left")],
                    [[sale_time_label(datetime.fromisoformat(sale["sale_datetime"]), today),
                      sale["books"] + (" · cancelled" if sale["status"] == "cancelled" else ""),
                      format_rupees(sale["total_paise"]),
                      names.get(sale["recorded_by"], "")]
                     for sale in recent],
                ))
            else:
                st.html('<p class="lekha-note">No sales today or yesterday.</p>')
            page_link("views/sales.py", "All recent sales", "sell")

# ---------- Selling well this week ----------
if selling:
    with st.container(key="lekha_card_selling"):
        ui.card_heading("Selling well this week", selling_well_note(selling))
        st.html(ui.shelf_html([
            ui.ShelfBook(row["title"], row["copies"], cover_url(row["cover_id"], "M"),
                         sold_out=row["stock_quantity"] == 0)
            for row in selling
        ]))
        page_link("views/insights.py", "See trends in Insights", "view_insights")
