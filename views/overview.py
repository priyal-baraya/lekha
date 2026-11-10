"""Overview: Lekha's front page.

Every figure here comes from the database. Sales figures cover the last
30 days and come from services/analytics.py, the same code the Insights
page uses, so the two pages always agree.
"""

from datetime import date

import pandas as pd
import streamlit as st

from database import connect
from services import analytics
from services.books import count_books, list_genres
from services.inventory import count_low_stock, low_stock_books
from services.money import format_rupees
from ui import charts
from ui import components as ui
from ui import session

ui.hero(
    eyebrow=session.shop_name() or "Independent bookstore insights",
    title="Lekha",
    tagline="Reading between the numbers.",
    description="An inventory and sales insights tool for independent bookstores.",
)
ui.show_flash()     # e.g. "Your shop is ready" after creating or joining a shop

with connect() as conn:
    total_books = count_books(conn)
    genre_count = len(list_genres(conn))
    low_stock_count = count_low_stock(conn)
    low_stock = low_stock_books(conn)
    period = analytics.period_for(conn, "last_30", date.today())
    totals = analytics.summary(conn, period)
    weekly = analytics.revenue_over_time(conn, period, "week")

ui.divider()
ui.section_header(
    eyebrow="Summary",
    title="The daily read",
    description=(f"Four figures worth checking each morning. Sales figures cover the last 30 days "
                 f"({period.start:%d %b} to {period.end:%d %b %Y})."),
)
if total_books == 0:
    ui.empty_state(
        "Your shop is empty. Start on the Books page: look a book up by its ISBN or search "
        "Open Library, then add your own price and stock. Figures here come only from the "
        "books you add and the sales you record."
    )
ui.metric_strip([
    ("Revenue", format_rupees(totals["revenue_paise"]), "Last 30 days, completed sales"),
    ("Copies sold", str(totals["copies"]), "Last 30 days"),
    ("Transactions", str(totals["transactions"]), "Last 30 days"),
    ("Books low on stock", str(low_stock_count), "At or below their reorder level, today"),
])

ui.divider()
ui.section_header(
    eyebrow="Sales",
    title="Sales and trends",
    description="Revenue per week over the last 30 days. Outlined bars are partial weeks.",
)
if weekly["revenue_paise"].sum() == 0:
    ui.empty_state("No completed sales in the last 30 days.")
else:
    best = weekly.loc[weekly["revenue_paise"].idxmax()]
    trend_summary = (f"Highest week: week of {best['bucket_start']:%d %b %Y}, "
                     f"{format_rupees(int(best['revenue_paise']))}.")
    st.altair_chart(charts.revenue_over_time(weekly, "week"), width="stretch", alt=trend_summary)
    st.markdown(trend_summary)
st.page_link("views/insights.py", label="Open Insights for genres, best sellers and more →")

ui.divider()
books_column, inventory_column = st.columns(2, gap="large")
with books_column:
    ui.section_header(
        eyebrow="Books",
        title="The bookshelf",
        description=("Browse, search and edit the catalogue." if session.can_do("edit_books")
                     else "Browse, search and add to the catalogue."),
    )
    genre_word = "genre" if genre_count == 1 else "genres"
    st.markdown(f"**{total_books}** {'book' if total_books == 1 else 'books'} across {genre_count} {genre_word}.")
    st.page_link("views/books.py", label="Open Books →")
with inventory_column:
    ui.section_header(
        eyebrow="Inventory",
        title="Shelf check",
        description="Books at or below their reorder level.",
    )
    if low_stock:
        st.dataframe(
            pd.DataFrame(low_stock[:5])[["title", "stock_quantity", "stock_status"]],
            hide_index=True,
            column_config={
                "title": st.column_config.TextColumn("Title"),
                "stock_quantity": st.column_config.NumberColumn("In stock"),
                "stock_status": st.column_config.TextColumn("Status"),
            },
        )
        if len(low_stock) > 5:
            st.markdown(f"Showing the 5 emptiest of {len(low_stock)}.")
    else:
        ui.empty_state("No books are at or below their reorder level.")
    st.page_link("views/inventory.py", label="Open Inventory →")
