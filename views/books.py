"""Books: browse, search, add and edit the catalogue.

This page only handles what the user sees. Searching, checking and
saving happen in services/books.py, which has its own tests.
"""

import pandas as pd
import streamlit as st

from database import connect
from services import ValidationError
from services.books import (
    BookInput,
    add_book,
    count_books,
    find_same_title_and_author,
    get_book,
    list_genres,
    search_books,
    update_book,
)
from services.money import paise_to_rupees
from ui import components as ui

ALL_GENRES = "All genres"
SORT_LABELS = {
    "title": "Title (A–Z)",
    "price_low": "Price (low to high)",
    "price_high": "Price (high to low)",
    "stock_low": "Stock (lowest first)",
}


def price_field(paise: int | None) -> float | None:
    """Paise -> rupees for a number field (display only; saving uses Decimal)."""
    return None if paise is None else float(paise_to_rupees(paise))


def render_browse(conn) -> None:
    total = count_books(conn)
    if total == 0:
        ui.empty_state(
            "No books yet. Add one in the “Add a book” tab, or load the fictional "
            "sample data by running:  python database.py --reset-sample"
        )
        return

    search_col, genre_col, sort_col = st.columns([2, 1, 1])
    text = search_col.text_input(
        "Search by title or author", key="books_search", live=True,
        placeholder="For example: monsoon, or Tara Menon",
    )
    genre = genre_col.selectbox("Genre", [ALL_GENRES, *list_genres(conn)], key="books_genre")
    sort = sort_col.selectbox("Sort by", list(SORT_LABELS), format_func=SORT_LABELS.get, key="books_sort")

    rows = search_books(conn, text, None if genre == ALL_GENRES else genre, sort)
    st.markdown(f"Showing **{len(rows)}** of {total} books")
    if not rows:
        st.info("No books match this search. Try fewer letters, or choose “All genres”.")
        return

    table = pd.DataFrame(rows)
    table["price"] = table["selling_price_paise"].map(price_field)
    st.dataframe(
        # Decision columns first, so they stay visible on a phone; details after.
        table[["title", "stock_status", "stock_quantity", "price", "author", "genre", "reorder_level"]],
        hide_index=True,
        column_config={
            "title": st.column_config.TextColumn("Title"),
            "author": st.column_config.TextColumn("Author"),
            "genre": st.column_config.TextColumn("Genre"),
            "price": st.column_config.NumberColumn("Price", format="₹%.2f"),
            "stock_quantity": st.column_config.NumberColumn("In stock"),
            "reorder_level": st.column_config.NumberColumn("Reorder level"),
            "stock_status": st.column_config.TextColumn("Status"),
        },
    )


def render_add(conn) -> None:
    st.markdown("Fields marked optional can be left empty. Everything else is required.")
    # Every widget key ends in this version number. After a successful save
    # the number goes up, so Streamlit sees a brand-new, empty form.
    # (Deleting the old values from session_state does not reset widgets
    # inside a form: the browser keeps showing what was typed.)
    version = st.session_state.setdefault("add_form_version", 0)
    with st.form(f"add_book_form_{version}"):
        title = st.text_input("Title", key=f"add_title_{version}")
        author = st.text_input("Author", key=f"add_author_{version}")
        genre_col, isbn_col = st.columns(2)
        genre = genre_col.selectbox(
            "Genre", list_genres(conn), index=None, accept_new_options=True, key=f"add_genre_{version}",
            placeholder="Choose a genre or type a new one",
        )
        isbn = isbn_col.text_input(
            "ISBN (optional)", key=f"add_isbn_{version}",
            help="10 or 13 digits. Hyphens and spaces are removed automatically.",
        )
        price_col, cost_col = st.columns(2)
        price = price_col.number_input(
            "Selling price (₹)", min_value=0.0, step=1.0, format="%.2f", value=None, key=f"add_price_{version}",
        )
        cost = cost_col.number_input(
            "Cost price (₹, optional)", min_value=0.0, step=1.0, format="%.2f", value=None,
            key=f"add_cost_{version}", help="What the store pays per copy. Leave empty if unknown.",
        )
        stock_col, reorder_col = st.columns(2)
        stock = stock_col.number_input("Opening stock", min_value=0, step=1, value=0, key=f"add_stock_{version}")
        reorder = reorder_col.number_input(
            "Reorder level", min_value=0, step=1, value=2, key=f"add_reorder_{version}",
            help="Lekha flags the book as low on stock at or below this number.",
        )
        submitted = st.form_submit_button("Add book", type="primary")

    if not submitted:
        return
    data = BookInput(title=title, author=author, genre=genre or "", isbn=isbn,
                     selling_price=price, cost_price=cost,
                     stock_quantity=int(stock), reorder_level=int(reorder))
    try:
        book_id = add_book(conn, data)
    except ValidationError as problem:
        ui.show_errors(problem.errors)  # the typed values stay in the form
        return

    saved = get_book(conn, book_id)
    warnings = [
        f"Note: “{match['title']}” by {match['author']} was already in the catalogue "
        f"(book #{match['book_id']}). If this is a different edition, that's fine."
        for match in find_same_title_and_author(conn, saved["title"], saved["author"], book_id)
    ]
    st.session_state["add_form_version"] = version + 1   # empty form next time
    ui.flash("success", f"Added “{saved['title']}” to the catalogue.", warnings)
    st.rerun()


def render_edit(conn) -> None:
    books = search_books(conn)
    if not books:
        st.info("There are no books to edit yet.")
        return
    labels = {book["book_id"]: f"{book['title']} — {book['author']}" for book in books}
    book_id = st.selectbox(
        "Book to edit", list(labels), format_func=labels.get, index=None,
        placeholder="Choose a book", key="edit_choice",
    )
    if book_id is None:
        return
    book = get_book(conn, book_id)
    genres = list_genres(conn)

    # Keys include the book_id so choosing another book refills the form.
    with st.form(f"edit_book_form_{book_id}"):
        title = st.text_input("Title", value=book["title"], key=f"edit_title_{book_id}")
        author = st.text_input("Author", value=book["author"], key=f"edit_author_{book_id}")
        genre_col, isbn_col = st.columns(2)
        genre = genre_col.selectbox(
            "Genre", genres, index=genres.index(book["genre"]), accept_new_options=True,
            key=f"edit_genre_{book_id}",
        )
        isbn = isbn_col.text_input("ISBN (optional)", value=book["isbn"] or "", key=f"edit_isbn_{book_id}")
        price_col, cost_col = st.columns(2)
        price = price_col.number_input(
            "Selling price (₹)", min_value=0.0, step=1.0, format="%.2f",
            value=price_field(book["selling_price_paise"]), key=f"edit_price_{book_id}",
            help="Changing the price affects future sales only. Past sales keep the price actually paid.",
        )
        cost = cost_col.number_input(
            "Cost price (₹, optional)", min_value=0.0, step=1.0, format="%.2f",
            value=price_field(book["cost_price_paise"]), key=f"edit_cost_{book_id}",
        )
        reorder = st.number_input(
            "Reorder level", min_value=0, step=1, value=book["reorder_level"],
            key=f"edit_reorder_{book_id}",
        )
        st.markdown(
            f"**In stock: {book['stock_quantity']}.** Stock isn't edited here. Use "
            "**Inventory → Correct stock**, so every change is recorded with a reason."
        )
        submitted = st.form_submit_button("Save changes", type="primary")

    if not submitted:
        return
    data = BookInput(title=title, author=author, genre=genre or "", isbn=isbn,
                     selling_price=price, cost_price=cost, reorder_level=int(reorder))
    try:
        update_book(conn, book_id, data)
    except ValidationError as problem:
        ui.show_errors(problem.errors)
        return
    ui.flash("success", f"Saved changes to “{get_book(conn, book_id)['title']}”.")
    st.rerun()


# ------------------------------------------------------------------ page

ui.page_intro(
    eyebrow="The bookshelf",
    title="Books",
    description="Browse, search and maintain the catalogue.",
)
ui.show_flash()

with connect() as conn:
    # on_change="rerun" makes the tabs remember which one is open, so the
    # page stays on "Add a book" after saving, and only the open tab runs.
    browse_tab, add_tab, edit_tab = st.tabs(
        ["Browse", "Add a book", "Edit a book"], key="books_tab", on_change="rerun",
    )
    if browse_tab.open:
        with browse_tab:
            render_browse(conn)
    if add_tab.open:
        with add_tab:
            render_add(conn)
    if edit_tab.open:
        with edit_tab:
            render_edit(conn)
