"""Overview: Lekha's front page.

The stock figures here come from the database. Sales figures arrive in
Phase 5, and until then their slots say so on screen.
"""

import pandas as pd
import streamlit as st

from database import connect
from services.books import count_books, list_genres
from services.inventory import count_low_stock, low_stock_books
from ui import components as ui

ui.hero(
    eyebrow="Independent bookstore insights",
    title="Lekha",
    tagline="Reading between the numbers.",
    description="An inventory and sales insights tool for independent bookstores.",
)

st.info(
    "We're building the foundation first. "
    "Book data and analytics will come next."
)

with connect() as conn:
    total_books = count_books(conn)
    genre_count = len(list_genres(conn))
    low_stock_count = count_low_stock(conn)
    low_stock = low_stock_books(conn)

ui.divider()
ui.section_header(
    eyebrow="Summary",
    title="The daily read",
    description=(
        "Four figures worth checking each morning. The stock figure is live; "
        "the sales figures arrive with sales analysis in Phase 5."
    ),
    tag="Partly connected",
)
ui.sample_data_notice()
ui.metric_strip([
    ("Revenue", None, "Arrives in Phase 5"),
    ("Copies sold", None, "Arrives in Phase 5"),
    ("Transactions", None, "Arrives in Phase 5"),
    ("Books low on stock", str(low_stock_count), "At or below their reorder level"),
])

ui.divider()
ui.section_header(
    eyebrow="Sales",
    title="Sales and trends",
    description="How revenue and copies sold change over time, and which titles and genres lead.",
)
ui.empty_state(
    "Charts of revenue over time, best-selling titles and revenue by genre "
    "will appear here once sales analysis is built.",
    tag="Planned · Phase 5",
)

ui.divider()
books_column, inventory_column = st.columns(2, gap="large")
with books_column:
    ui.section_header(
        eyebrow="Books",
        title="The bookshelf",
        description="Browse, search and edit the catalogue.",
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
