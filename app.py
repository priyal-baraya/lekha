"""Lekha: application entry point.

This file only sets up the page, loads the shared styles, defines the
navigation and catches errors. Each page's content lives in views/.

Run with:
    .\\.venv\\Scripts\\python.exe -m streamlit run app.py
"""

import logging
import sqlite3

import streamlit as st

from database import ensure_database
from ui import components as ui

# Messages for whoever runs the app; they appear in the terminal.
logger = logging.getLogger("lekha")

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
page = st.navigation(pages, position="top")

# One safety net for every page. Without it, an unexpected error shows the
# owner a Python traceback. The full details still go to the terminal.
# st.rerun() and st.stop() are not caught here: Streamlit signals them with
# a BaseException that `except Exception` deliberately lets through.
try:
    # Creates the database file and any missing tables. Existing data is kept.
    ensure_database()
    page.run()
except sqlite3.Error:
    logger.exception("Database error on page %s", page.title)
    st.error(
        "Lekha couldn't read or write its database. If the file is open in another "
        "program, close it, then reload this page. Nothing was saved halfway: sales, "
        "stock corrections and book changes are saved all-or-nothing."
    )
except Exception:
    logger.exception("Unexpected error on page %s", page.title)
    st.error(
        "Something went wrong on this page. Nothing was saved halfway: sales, stock "
        "corrections and book changes are saved all-or-nothing. Reload the page to try again."
    )
