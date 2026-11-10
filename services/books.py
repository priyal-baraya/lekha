"""The book catalogue: searching, validating, adding and editing books.

Every query passes user input through "?" placeholders. SQLite treats
whatever fills a placeholder strictly as data, never as SQL, which
blocks SQL injection (typing SQL into a search box to make it run).
"""

import re
import sqlite3
from dataclasses import dataclass
from decimal import Decimal

from services import ValidationError
from services.money import rupees_to_paise

# The only ORDER BY clauses allowed. Placeholders can't be used for
# column names or sort directions, so instead of inserting user input
# into the SQL, the page picks one of these fixed keys.
# Longest text accepted for each field. Real titles fit easily; the limits
# stop someone pasting a whole book into a form and filling the database.
MAX_LENGTHS = {"title": 300, "author": 200, "genre": 60, "publisher": 200}
MAX_SEARCH_LENGTH = 200

SORT_OPTIONS = {
    "title": "title COLLATE NOCASE ASC",
    "price_low": "selling_price_paise ASC, title COLLATE NOCASE ASC",
    "price_high": "selling_price_paise DESC, title COLLATE NOCASE ASC",
    "stock_low": "stock_quantity ASC, title COLLATE NOCASE ASC",
}

# Shared by every query that shows a stock status. Written in words so
# meaning never depends on colour alone.
STOCK_STATUS_SQL = """
    CASE
        WHEN stock_quantity = 0 THEN 'Out of stock'
        WHEN stock_quantity <= reorder_level THEN 'Low stock'
        ELSE 'In stock'
    END
"""


@dataclass
class BookInput:
    """What the add and edit forms collect, before any checking.

    Prices are in rupees, as typed. stock_quantity is only used when
    adding a book; afterwards stock changes through services.inventory.

    The last four fields come from Open Library (services/openlibrary.py)
    and are only saved when a book is added, so editing a book's price can
    never wipe its cover or publisher.
    """

    title: str
    author: str
    genre: str
    isbn: str | None = None
    selling_price: float | Decimal | str | None = None
    cost_price: float | Decimal | str | None = None
    stock_quantity: int | None = 0
    reorder_level: int | None = 0
    publisher: str | None = None
    published_year: int | None = None
    cover_id: int | None = None
    openlibrary_key: str | None = None


# ---------------------------------------------------------------- reading

def count_books(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT COUNT(*) FROM books").fetchone()[0]


def list_genres(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute("SELECT DISTINCT genre FROM books ORDER BY genre COLLATE NOCASE")
    return [row["genre"] for row in rows]


def _escape_like(text: str) -> str:
    """Make % and _ match literally. In LIKE patterns they are wildcards
    (% = any text, _ = any one character), so a search for "50%" would
    otherwise match everything starting with "50"."""
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def search_books(
    conn: sqlite3.Connection,
    text: str = "",
    genre: str | None = None,
    sort: str = "title",
) -> list[dict]:
    """Books whose title or author contains `text`, optionally in one genre.

    Matching ignores upper/lower case for English letters (SQLite's LIKE
    default). An empty `text` matches every book.
    """
    if sort not in SORT_OPTIONS:
        raise ValueError(f"Unknown sort option: {sort}")
    pattern = f"%{_escape_like(text.strip()[:MAX_SEARCH_LENGTH])}%"
    rows = conn.execute(
        f"""
        SELECT book_id, isbn, title, author, genre,
               selling_price_paise, cost_price_paise,
               stock_quantity, reorder_level,
               publisher, published_year, cover_id, openlibrary_key,
               {STOCK_STATUS_SQL} AS stock_status
        FROM books
        WHERE (title LIKE :pattern ESCAPE '\\' OR author LIKE :pattern ESCAPE '\\')
          AND (:genre IS NULL OR genre = :genre)
        ORDER BY {SORT_OPTIONS[sort]}
        """,  # nosec B608
        {"pattern": pattern, "genre": genre},
    )
    return [dict(row) for row in rows]


def get_book(conn: sqlite3.Connection, book_id: int) -> dict | None:
    row = conn.execute(
        f"SELECT *, {STOCK_STATUS_SQL} AS stock_status FROM books WHERE book_id = ?",  # nosec B608
        (book_id,),
    ).fetchone()
    return dict(row) if row else None


def find_same_title_and_author(
    conn: sqlite3.Connection, title: str, author: str, exclude_book_id: int | None = None
) -> list[dict]:
    """Books with the same title and author, ignoring case and extra spaces.

    Used for a warning, not a block: a store may stock two editions.
    """
    rows = conn.execute(
        """
        SELECT book_id, title, author, isbn FROM books
        WHERE lower(trim(title)) = lower(trim(?))
          AND lower(trim(author)) = lower(trim(?))
          AND (? IS NULL OR book_id <> ?)
        """,
        (title, author, exclude_book_id, exclude_book_id),
    )
    return [dict(row) for row in rows]


# ------------------------------------------------------------- validation

def clean_isbn(raw: str | None) -> str | None:
    """Remove spaces and hyphens and upper-case a final x. Blank -> None."""
    if raw is None:
        return None
    cleaned = raw.replace("-", "").replace(" ", "").strip().upper()
    return cleaned or None


def _whole_number(value, label: str, errors: list[str]) -> int | None:
    # bool is a kind of int in Python (True == 1), so it is ruled out explicitly.
    if value is None or isinstance(value, bool) or not isinstance(value, int):
        errors.append(f"{label} must be a whole number.")
        return None
    if value < 0:
        errors.append(f"{label} can't be negative.")
        return None
    return value


def _price(value, label: str, errors: list[str], required: bool) -> int | None:
    if value is None or (isinstance(value, str) and not value.strip()):
        if required:
            errors.append(f"{label} is required.")
        return None
    try:
        return rupees_to_paise(value)
    except ValueError as problem:
        errors.append(f"{label}: {problem}")
        return None


def _book_details(data: BookInput, errors: list[str]) -> dict:
    """Check the optional Open Library details: publisher, year, cover, record."""
    publisher = " ".join((data.publisher or "").split()) or None
    if publisher and len(publisher) > MAX_LENGTHS["publisher"]:
        errors.append(f"Publisher is at most {MAX_LENGTHS['publisher']} characters.")
    year = data.published_year
    if year is not None and (isinstance(year, bool) or not isinstance(year, int) or not 1450 <= year <= 2100):
        errors.append("Published year must be a year between 1450 and 2100.")
    cover_id = data.cover_id
    if cover_id is not None and (isinstance(cover_id, bool) or not isinstance(cover_id, int) or cover_id <= 0):
        errors.append("The cover reference from Open Library isn't valid.")
    key = data.openlibrary_key
    if key is not None and not re.fullmatch(r"/(books/OL\d+M|works/OL\d+W)", key):
        errors.append("The Open Library record reference isn't valid.")
    return {"publisher": publisher, "published_year": year, "cover_id": cover_id, "openlibrary_key": key}


def validate_book(
    conn: sqlite3.Connection,
    data: BookInput,
    book_id: int | None = None,
    include_stock: bool = True,
) -> dict:
    """Check and tidy a book's details. Returns columns ready to save.

    book_id is the book being edited (None when adding), so its own ISBN
    isn't reported as a duplicate. Raises ValidationError listing every
    problem found.
    """
    errors: list[str] = []
    clean: dict = {}

    for field, label in (("title", "Title"), ("author", "Author"), ("genre", "Genre")):
        value = (getattr(data, field) or "").strip()
        # Collapse runs of spaces: "The  Monsoon   Ledger" -> "The Monsoon Ledger"
        value = " ".join(value.split())
        if not value:
            errors.append(f"{label} is required.")
        elif len(value) > MAX_LENGTHS[field]:
            errors.append(f"{label} is at most {MAX_LENGTHS[field]} characters.")
        clean[field] = value

    # Reuse an existing genre's spelling, so "fiction" joins "Fiction"
    # instead of starting a new genre.
    if clean["genre"]:
        for existing in list_genres(conn):
            if existing.lower() == clean["genre"].lower():
                clean["genre"] = existing
                break

    isbn = clean_isbn(data.isbn)
    if isbn is not None:
        valid_shape = (
            (len(isbn) == 13 and isbn.isdigit())
            or (len(isbn) == 10 and isbn[:9].isdigit() and (isbn[9].isdigit() or isbn[9] == "X"))
        )
        if not valid_shape:
            errors.append("ISBN must be 10 or 13 digits (an ISBN-10 may end in X).")
        else:
            duplicate = conn.execute(
                "SELECT title FROM books WHERE isbn = ? AND (? IS NULL OR book_id <> ?)",
                (isbn, book_id, book_id),
            ).fetchone()
            if duplicate:
                errors.append(f"ISBN {isbn} already belongs to \"{duplicate['title']}\".")
    clean["isbn"] = isbn

    clean["selling_price_paise"] = _price(data.selling_price, "Selling price", errors, required=True)
    clean["cost_price_paise"] = _price(data.cost_price, "Cost price", errors, required=False)
    clean["reorder_level"] = _whole_number(data.reorder_level, "Reorder level", errors)
    if include_stock:   # adding a new book
        clean["stock_quantity"] = _whole_number(data.stock_quantity, "Opening stock", errors)
        clean.update(_book_details(data, errors))

    if errors:
        raise ValidationError(errors)
    return clean


# ---------------------------------------------------------------- writing

def add_book(conn: sqlite3.Connection, data: BookInput) -> int:
    """Validate and insert a new book. Returns its new book_id."""
    clean = validate_book(conn, data)
    columns = ", ".join(clean)
    placeholders = ", ".join(f":{name}" for name in clean)
    try:
        # `with conn:` is a transaction: commit if the block succeeds,
        # roll back if anything inside it raises an error.
        with conn:
            # Column names come from validate_book(), never from a person.
            cursor = conn.execute(f"INSERT INTO books ({columns}) VALUES ({placeholders})", clean)  # nosec B608
    except sqlite3.IntegrityError as problem:
        # The database's own rules are the last line of defence, for
        # anything the checks above missed.
        raise ValidationError([f"The database refused this book: {problem}"]) from None
    return cursor.lastrowid


def update_book(conn: sqlite3.Connection, book_id: int, data: BookInput) -> None:
    """Validate and save changes to a book's details. Stock is not changed here."""
    clean = validate_book(conn, data, book_id=book_id, include_stock=False)
    assignments = ", ".join(f"{name} = :{name}" for name in clean)
    try:
        with conn:
            cursor = conn.execute(
                f"UPDATE books SET {assignments} WHERE book_id = :book_id",  # nosec B608
                {**clean, "book_id": book_id},
            )
    except sqlite3.IntegrityError as problem:
        raise ValidationError([f"The database refused this change: {problem}"]) from None
    if cursor.rowcount == 0:
        raise ValidationError(["This book no longer exists."])
