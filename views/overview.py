"""Overview: Lekha's front page.

No database exists yet, so nothing on this page is calculated. Every
section says on screen what it will show and in which phase it arrives.
"""

import streamlit as st

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

ui.divider()
ui.section_header(
    eyebrow="Summary",
    title="The daily read",
    description=(
        "Four figures worth checking each morning. They will be calculated "
        "from recorded sales and stock once the database is in place."
    ),
    tag="Placeholder · no data yet",
)
ui.metric_placeholders(
    ["Revenue", "Copies sold", "Transactions", "Books low on stock"],
    note="Not connected yet",
)

ui.divider()
ui.section_header(
    eyebrow="Sales",
    title="Sales and trends",
    description="How revenue and copies sold change over time, and which titles and genres lead.",
)
ui.empty_state(
    "Charts of revenue over time, best-selling titles and revenue by genre "
    "will appear here once sales are being recorded.",
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
    ui.empty_state("The searchable catalogue will live here.", tag="Planned · Phase 3")
with inventory_column:
    ui.section_header(
        eyebrow="Inventory",
        title="Shelf check",
        description="Books at or below their reorder level.",
    )
    ui.empty_state("Low-stock alerts will appear here.", tag="Planned · Phase 3")
