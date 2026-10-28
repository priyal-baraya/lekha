"""Lekha: application entry point.

This file only sets up the page, loads the shared styles and defines the
navigation. Each page's content lives in its own file in views/.

Run with:
    .\\.venv\\Scripts\\python.exe -m streamlit run app.py
"""

import streamlit as st

from ui import components as ui

st.set_page_config(
    page_title="Lekha",
    page_icon="📚",
    layout="wide",
)

ui.load_styles()

pages = [
    st.Page("views/overview.py", title="Overview", default=True),
    st.Page("views/books.py", title="Books"),
    st.Page("views/sales.py", title="Sales"),
    st.Page("views/inventory.py", title="Inventory"),
    st.Page("views/insights.py", title="Insights"),
]

st.navigation(pages, position="top").run()
