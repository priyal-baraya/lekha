"""Stock: low-stock alerts and recorded stock corrections.

A low-stock ALERT is a fact: a book's stock is at or below the reorder
level the owner chose. It is not a RECOMMENDATION to reorder. That would
also need sales speed and delivery times, which belong to later analysis.
"""

import sqlite3
from datetime import datetime

from services import ValidationError
from services.books import STOCK_STATUS_SQL

MAX_NOTE_LENGTH = 300     # a sentence or two; stops a whole page being pasted in

# Stored value -> label shown on screen
REASONS = {
    "shelf_count": "Shelf count",
    "damaged_or_lost": "Damaged or lost",
    "delivery_received": "Delivery received",
    "other": "Other",
}


class StockChangedError(Exception):
    """The stock changed between showing the form and saving it.

    Raised instead of overwriting, so a correction is never applied on
    top of a number the user didn't see (for example after a double
    click on Save).
    """


def low_stock_books(conn: sqlite3.Connection) -> list[dict]:
    """Books at or below their reorder level, emptiest shelves first."""
    rows = conn.execute(
        f"""
        SELECT book_id, title, author, genre, stock_quantity, reorder_level, cover_id,
               {STOCK_STATUS_SQL} AS stock_status
        FROM books
        WHERE stock_quantity <= reorder_level
        ORDER BY stock_quantity ASC, title COLLATE NOCASE ASC
        """  # nosec B608
    )
    return [dict(row) for row in rows]


def count_low_stock(conn: sqlite3.Connection) -> int:
    return conn.execute(
        "SELECT COUNT(*) FROM books WHERE stock_quantity <= reorder_level"
    ).fetchone()[0]


def correct_stock(
    conn: sqlite3.Connection,
    book_id: int,
    expected_quantity: int,
    counted_quantity: int,
    reason: str,
    note: str = "",
    now: datetime | None = None,
    recorded_by: int | None = None,
) -> int:
    """Set a book's stock to a counted number and record why, in one step.

    expected_quantity is the stock the user saw on screen. The update only
    happens if the stock is still that number; otherwise StockChangedError
    is raised and nothing changes.

    Returns the new adjustment_id.
    """
    errors = []
    if isinstance(counted_quantity, bool) or not isinstance(counted_quantity, int):
        errors.append("The counted quantity must be a whole number.")
    elif counted_quantity < 0:
        errors.append("The counted quantity can't be negative.")
    elif counted_quantity == expected_quantity:
        errors.append("The count matches the current stock, so there is nothing to correct.")
    if reason not in REASONS:
        errors.append("Choose a reason for the correction.")
    note = " ".join((note or "").split())
    if reason == "other" and not note:
        errors.append("Add a note explaining the correction when the reason is \"Other\".")
    if len(note) > MAX_NOTE_LENGTH:
        errors.append(f"Keep the note to {MAX_NOTE_LENGTH} characters or fewer.")
    if errors:
        raise ValidationError(errors)

    adjusted_at = (now or datetime.now()).strftime("%Y-%m-%d %H:%M:%S")

    # One transaction: both statements succeed together or neither does.
    with conn:
        cursor = conn.execute(
            # "AND stock_quantity = ?" is the safety check: if the stock is
            # no longer what the user saw, this matches no rows.
            "UPDATE books SET stock_quantity = ? WHERE book_id = ? AND stock_quantity = ?",
            (counted_quantity, book_id, expected_quantity),
        )
        if cursor.rowcount == 0:
            exists = conn.execute("SELECT 1 FROM books WHERE book_id = ?", (book_id,)).fetchone()
            if not exists:
                raise ValidationError(["This book no longer exists."])
            raise StockChangedError(
                "The stock for this book changed since the page was loaded. "
                "Nothing was saved. Check the current number and try again."
            )
        cursor = conn.execute(
            """
            INSERT INTO stock_adjustments
                (book_id, adjusted_at, quantity_before, quantity_after, reason, note, recorded_by)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (book_id, adjusted_at, expected_quantity, counted_quantity, reason, note or None, recorded_by),
        )
    return cursor.lastrowid


def recent_adjustments(conn: sqlite3.Connection, limit: int = 20) -> list[dict]:
    """The latest stock corrections, newest first, with book titles."""
    rows = conn.execute(
        """
        SELECT a.adjustment_id, a.adjusted_at, a.recorded_by, b.title,
               a.quantity_before, a.quantity_after,
               a.quantity_after - a.quantity_before AS change,
               a.reason, a.note
        FROM stock_adjustments AS a
        JOIN books AS b ON b.book_id = a.book_id
        ORDER BY a.adjusted_at DESC, a.adjustment_id DESC
        LIMIT ?
        """,
        (limit,),
    )
    return [{**dict(row), "reason_label": REASONS[row["reason"]]} for row in rows]
