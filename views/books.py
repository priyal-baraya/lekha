"""Books: browse, find real books, add and edit the catalogue.

This page only handles what the user sees. Looking books up happens in
services/openlibrary.py; checking and saving in services/books.py. Both
have their own tests.
"""

from dataclasses import asdict

import pandas as pd
import streamlit as st

from database import connect
from services import ValidationError, openlibrary
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
from ui import session

ALL_GENRES = "All genres"
SORT_LABELS = {
    "title": "Title (A–Z)",
    "price_low": "Price (low to high)",
    "price_high": "Price (high to low)",
    "stock_low": "Stock (lowest first)",
}
# Common bookshop sections, offered so an empty shop has genres to choose
# from. They are labels, not data; any other genre can be typed in.
STARTER_GENRES = ["Biography", "Children", "Cookery", "Fiction", "History", "Mystery", "Non-fiction", "Poetry"]
ADD_METHODS = {
    "isbn": "Look up by ISBN",
    "search": "Search by title or author",
    "manual": "Type it in myself",
}
CREDIT = ("Book details and covers come from [Open Library](https://openlibrary.org), a free "
          "catalogue edited by volunteers. Check them against the book in your hand.")
ONE_DAY = 24 * 60 * 60


def price_field(paise: int | None) -> float | None:
    """Paise -> rupees for a number field (display only; saving uses Decimal)."""
    return None if paise is None else float(paise_to_rupees(paise))


def genre_options(conn, suggested: str | None = None) -> list[str]:
    options = sorted({*STARTER_GENRES, *list_genres(conn)}, key=str.lower)
    if suggested and suggested not in options:
        options.append(suggested)
    return options


# Open Library answers are cached for a day, so looking the same book up
# twice doesn't ask Open Library twice. Errors are never cached.
@st.cache_data(ttl=ONE_DAY, show_spinner="Looking it up on Open Library…")
def lookup_isbn_cached(isbn: str) -> dict | None:
    found = openlibrary.lookup_isbn(isbn)
    return asdict(found) if found else None


@st.cache_data(ttl=ONE_DAY, show_spinner="Searching Open Library…")
def search_cached(text: str) -> list[dict]:
    return [asdict(found) for found in openlibrary.search(text)]


# ---------------------------------------------------------------- browse

def render_browse(conn) -> None:
    total = count_books(conn)
    if total == 0:
        ui.empty_state(
            "No books yet. Add your first one in the “Add a book” tab: look it up by its "
            "ISBN, search Open Library by title or author, or type it in yourself."
        )
        return

    search_col, genre_col, sort_col = st.columns([2, 1, 1])
    text = search_col.text_input(
        "Search by title or author", key="books_search", live=True,
        placeholder="Part of a title or an author's name",
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
    table["cover"] = table["cover_id"].map(lambda cover_id: openlibrary.cover_url(cover_id, "S"))
    st.dataframe(
        # Decision columns first, so they stay visible on a phone; details after.
        table[["cover", "title", "stock_status", "stock_quantity", "price", "author", "genre", "reorder_level"]],
        hide_index=True,
        column_config={
            "cover": st.column_config.ImageColumn("Cover", width="small"),
            "title": st.column_config.TextColumn("Title"),
            "author": st.column_config.TextColumn("Author"),
            "genre": st.column_config.TextColumn("Genre"),
            "price": st.column_config.NumberColumn("Price", format="₹%.2f"),
            "stock_quantity": st.column_config.NumberColumn("In stock"),
            "reorder_level": st.column_config.NumberColumn("Reorder level"),
            "stock_status": st.column_config.TextColumn("Status"),
        },
    )
    if table["cover_id"].notna().any():
        st.markdown(CREDIT)


# ------------------------------------------------------------- find a book

def use_found(found: dict) -> None:
    """Pre-fill the add form with a book from Open Library."""
    st.session_state["add_found"] = found
    st.session_state["add_form_version"] = st.session_state.get("add_form_version", 0) + 1
    st.rerun()


def render_isbn_lookup() -> None:
    with st.form("isbn_lookup"):
        isbn = st.text_input(
            "ISBN", placeholder="The 10 or 13 digits by the barcode on the back cover",
            help="Hyphens and spaces are fine.",
        )
        submitted = st.form_submit_button("Look up")
    if not submitted:
        return
    try:
        found = lookup_isbn_cached((isbn or "").strip())
    except ValidationError as problem:
        ui.show_errors(problem.errors)
        return
    except openlibrary.OpenLibraryError as problem:
        st.error(str(problem))
        return
    if found is None:
        st.info(
            f"Open Library has no record for ISBN {isbn.strip()}. Check the number, "
            "search by title instead, or type the book in yourself."
        )
        return
    use_found(found)


def render_search() -> None:
    with st.form("openlibrary_search"):
        text = st.text_input("Title or author", placeholder="For example: The God of Small Things")
        submitted = st.form_submit_button("Search")
    if submitted:
        try:
            st.session_state["add_results"] = search_cached(" ".join((text or "").split()))
        except ValidationError as problem:
            ui.show_errors(problem.errors)
            return
        except openlibrary.OpenLibraryError as problem:
            st.error(str(problem))
            return

    results = st.session_state.get("add_results")
    if results is None:
        return
    if not results:
        st.info("No matches on Open Library. Try fewer words, or just the author's surname.")
        return
    st.markdown(f"**{len(results)} matches.** Check the author and year to find the right book.")
    for index, found in enumerate(results):
        cover_col, text_col, button_col = st.columns([0.8, 5, 1.6], vertical_alignment="center")
        url = openlibrary.cover_url(found["cover_id"], "S")
        if url:
            cover_col.image(url, width=48)
        else:
            cover_col.markdown("No cover")
        year = found["first_published"]
        text_col.markdown(
            f"**{found['title']}**  \n{found['author'] or 'Author not listed'} · "
            f"{'first published ' + str(year) if year else 'year not listed'}"
        )
        if button_col.button("Use this book", key=f"use_result_{index}"):
            use_found(found)
    st.markdown(CREDIT)


# -------------------------------------------------------------- add form

def render_found_summary(found: dict) -> None:
    cover_col, text_col = st.columns([1, 5])
    url = openlibrary.cover_url(found["cover_id"], "M")
    if url:
        cover_col.image(url, width=110)
    edition = found.get("isbn") is not None
    text_col.markdown(
        "**Details from Open Library.** Check them against the book in your hand and correct "
        "anything that's wrong, then add your own price and stock.  \n"
        + ("This is the exact edition with this ISBN."
           if edition else
           "This is the book in general, not a particular edition: type the ISBN from your copy "
           "if it has one.")
        + f"  \n[See the Open Library record]({openlibrary.API + found['openlibrary_key']})"
    )
    if text_col.button("Start again", key="add_start_again"):
        st.session_state.pop("add_found", None)
        st.session_state["add_form_version"] = st.session_state.get("add_form_version", 0) + 1
        st.rerun()


def render_add_form(conn, found: dict | None) -> None:
    found = found or {}
    suggested = openlibrary.suggest_genre(found.get("subjects", ())) if found else None
    options = genre_options(conn, suggested)

    # Every widget key ends in this version number. After a save, or when
    # a different book is chosen, the number goes up, so Streamlit draws a
    # new form with the new starting values.
    version = st.session_state.setdefault("add_form_version", 0)
    with st.form(f"add_book_form_{version}"):
        title = st.text_input("Title", value=found.get("title", ""), key=f"add_title_{version}")
        author = st.text_input("Author", value=found.get("author", ""), key=f"add_author_{version}")
        genre_col, isbn_col = st.columns(2)
        genre = genre_col.selectbox(
            "Genre", options, index=options.index(suggested) if suggested else None,
            accept_new_options=True, key=f"add_genre_{version}",
            placeholder="Choose a genre or type a new one",
            help=("Suggested from Open Library's subject tags. Change it if it's wrong."
                  if suggested else None),
        )
        isbn = isbn_col.text_input(
            "ISBN (optional)", value=found.get("isbn") or "", key=f"add_isbn_{version}",
            help="10 or 13 digits. Hyphens and spaces are removed automatically.",
        )
        publisher_col, year_col = st.columns(2)
        publisher = publisher_col.text_input(
            "Publisher (optional)", value=found.get("publisher") or "", key=f"add_publisher_{version}",
            help="The publisher of your edition, as printed on the book.",
        )
        published_year = year_col.number_input(
            "Year this edition was published (optional)", min_value=1450, max_value=2100, step=1,
            value=found.get("published_year"), key=f"add_year_{version}",
        )
        price_col, cost_col = st.columns(2)
        price = price_col.number_input(
            "Selling price (₹)", min_value=0.0, step=1.0, format="%.2f", value=None, key=f"add_price_{version}",
            help="What you charge, for example the MRP printed on the book.",
        )
        cost = cost_col.number_input(
            "Cost price (₹, optional)", min_value=0.0, step=1.0, format="%.2f", value=None,
            key=f"add_cost_{version}", help="What the shop pays per copy. Leave empty if unknown.",
        )
        stock_col, reorder_col = st.columns(2)
        stock = stock_col.number_input("Copies in stock", min_value=0, step=1, value=0, key=f"add_stock_{version}")
        reorder = reorder_col.number_input(
            "Reorder level", min_value=0, step=1, value=session.default_reorder_level(),
            key=f"add_reorder_{version}",
            help="Lekha flags the book as low on stock at or below this number.",
        )
        submitted = st.form_submit_button("Add book", type="primary")

    if not submitted:
        return
    data = BookInput(
        title=title, author=author, genre=genre or "", isbn=isbn,
        selling_price=price, cost_price=cost,
        stock_quantity=int(stock), reorder_level=int(reorder),
        publisher=publisher or None,
        published_year=int(published_year) if published_year is not None else None,
        cover_id=found.get("cover_id"),
        openlibrary_key=found.get("openlibrary_key"),
    )
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
    st.session_state.pop("add_found", None)
    st.session_state.pop("add_results", None)
    st.session_state["add_form_version"] = version + 1   # empty form next time
    ui.flash("success", f"Added “{saved['title']}” to the catalogue.", warnings)
    st.rerun()


def render_add(conn) -> None:
    found = st.session_state.get("add_found")
    if found:
        render_found_summary(found)
        render_add_form(conn, found)
        return
    method = st.radio(
        "How would you like to add the book?", list(ADD_METHODS), format_func=ADD_METHODS.get,
        horizontal=True, key="add_method",
    )
    if method == "isbn":
        render_isbn_lookup()
    elif method == "search":
        render_search()
    else:
        st.markdown("Fields marked optional can be left empty. Everything else is required.")
        render_add_form(conn, None)


# ------------------------------------------------------------------ edit

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
    genres = genre_options(conn)

    details = [part for part in (
        book["publisher"],
        f"published {book['published_year']}" if book["published_year"] else None,
    ) if part]
    if book["cover_id"] or details or book["openlibrary_key"]:
        cover_col, text_col = st.columns([1, 5])
        if book["cover_id"]:
            cover_col.image(openlibrary.cover_url(book["cover_id"], "M"), width=90)
        lines = [" · ".join(details)] if details else []
        if book["openlibrary_key"]:
            lines.append(f"[Open Library record]({openlibrary.API + book['openlibrary_key']})")
        text_col.markdown("  \n".join(lines))

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
    description="Find real books, add them to your catalogue, and keep their details up to date.",
)
ui.show_flash()

with connect() as conn:
    # on_change="rerun" makes the tabs remember which one is open, so the
    # page stays on "Add a book" after saving, and only the open tab runs.
    # Editing prices and details is for owners; staff can browse and add.
    names = ["Browse", "Add a book"] + (["Edit a book"] if session.can_do("edit_books") else [])
    tabs = st.tabs(names, key="books_tab", on_change="rerun")
    if tabs[0].open:
        with tabs[0]:
            render_browse(conn)
    if tabs[1].open:
        with tabs[1]:
            render_add(conn)
    if len(tabs) > 2 and tabs[2].open:
        with tabs[2]:
            render_edit(conn)
