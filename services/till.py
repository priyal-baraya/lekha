"""The till: finding a book to sell, and the basket a sale is built in.

Kept apart from the Sales page so the rules can be tested without
Streamlit:
  * a scanned or typed ISBN finds exactly that book;
  * otherwise title and author are searched, a few results shown;
  * the basket never holds more copies than are on the shelf, and keeps
    the price that was on screen, which record_sale() checks again.
"""

import sqlite3
from dataclasses import dataclass, field
from datetime import datetime

from services.books import clean_isbn, search_books
from services.sales import SaleLine

TILL_RESULTS = 6                     # matches shown at once; the rest are counted
UNDO_REASON = "Undone at the till straight after recording"


@dataclass(frozen=True)
class TillSearch:
    books: list[dict]
    total: int
    by_isbn: bool = False


def till_search(conn: sqlite3.Connection, text: str, limit: int = TILL_RESULTS) -> TillSearch:
    """Books for what was typed or scanned at the till.

    An empty search finds nothing (the till isn't a catalogue). Something
    that looks like an ISBN is matched exactly, the way a barcode scanner
    types it; anything else searches titles and authors."""
    text = (text or "").strip()
    if not text:
        return TillSearch([], 0)
    isbn = clean_isbn(text)
    if isbn and isbn[:-1].isdigit() and len(isbn) in (10, 13):
        row = conn.execute("SELECT book_id FROM books WHERE isbn = ?", (isbn,)).fetchone()
        if row is None:
            return TillSearch([], 0, by_isbn=True)
        book = next(b for b in search_books(conn) if b["book_id"] == row["book_id"])
        return TillSearch([book], 1, by_isbn=True)
    matches = search_books(conn, text)
    return TillSearch(matches[:limit], len(matches))


@dataclass
class BasketLine:
    book_id: int
    title: str
    author: str | None
    cover_id: int | None
    unit_price_paise: int
    quantity: int
    in_stock: int            # copies on the shelf when the book was added

    @property
    def total_paise(self) -> int:
        return self.quantity * self.unit_price_paise


def _copies(n: int) -> str:
    return f"{n} {'copy' if n == 1 else 'copies'}"


@dataclass
class Basket:
    """The sale being built, kept in the browser session until it's recorded."""

    lines: dict[int, BasketLine] = field(default_factory=dict)

    def __bool__(self) -> bool:
        return bool(self.lines)

    @property
    def copies(self) -> int:
        return sum(line.quantity for line in self.lines.values())

    @property
    def total_paise(self) -> int:
        return sum(line.total_paise for line in self.lines.values())

    def _full(self, line: BasketLine) -> str:
        n = line.in_stock
        if n == 1:
            return f"Only 1 copy of {line.title} is in stock, and it's in this sale."
        both = "both are" if n == 2 else f"all {n} are"
        return f"Only {n} copies of {line.title} are in stock, and {both} in this sale."

    def add(self, book: dict) -> str | None:
        """Add one copy. Returns why not, if it can't be added."""
        if book["stock_quantity"] <= 0:
            return f"{book['title']} can't be sold until it's restocked."
        line = self.lines.get(book["book_id"])
        if line is None:
            self.lines[book["book_id"]] = BasketLine(
                book["book_id"], book["title"], book.get("author"), book.get("cover_id"),
                book["selling_price_paise"], 1, book["stock_quantity"])
            return None
        return self.more(book["book_id"])

    def more(self, book_id: int) -> str | None:
        line = self.lines[book_id]
        if line.quantity >= line.in_stock:
            return self._full(line)
        line.quantity += 1
        return None

    def fewer(self, book_id: int) -> None:
        """One copy fewer, down to one. Remove takes a book out."""
        line = self.lines[book_id]
        line.quantity = max(1, line.quantity - 1)

    def remove(self, book_id: int) -> None:
        self.lines.pop(book_id, None)

    def clear(self) -> None:
        self.lines.clear()

    def sale_lines(self) -> list[SaleLine]:
        return [SaleLine(line.book_id, line.quantity, line.unit_price_paise) for line in self.lines.values()]

    def summary(self) -> str:
        return _copies(self.copies)


def recorded_as(when: datetime | None, now: datetime) -> str:
    """The line above Record sale: when the sale will be saved as happening."""
    if when is None:
        return f"Recorded as now, {now.day} {now:%b}, {now:%H:%M}."
    return f"Recorded as {when:%A} {when.day} {when:%b}, {when:%H:%M}."
