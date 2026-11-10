"""Recording, listing and cancelling sales.

The two functions that change data, record_sale() and cancel_sale(),
each do all of their work inside ONE transaction. If any step fails,
every step is undone, so a sale is never half-saved and stock is never
changed without a matching sale record.
"""

import sqlite3
from dataclasses import dataclass
from datetime import datetime

from services import ValidationError
from services.money import format_rupees

TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"


@dataclass
class SaleLine:
    """One book in a sale, as it was shown on screen.

    unit_price_paise is the price the user saw. record_sale() checks it
    against the book's current price, so the saved sale always matches
    what was on screen.
    """

    book_id: int
    quantity: int
    unit_price_paise: int


def _copies(n: int) -> str:
    return f"{n} {'copy' if n == 1 else 'copies'}"


def _combine_lines(lines: list[SaleLine]) -> list[SaleLine]:
    """Merge lines for the same book: 2 + 1 copies -> 3 copies.

    The database allows each book only once per sale. Two lines for one
    book at different prices can't be merged honestly, so that is refused.
    """
    combined: dict[int, SaleLine] = {}
    for line in lines:
        if line.book_id not in combined:
            combined[line.book_id] = SaleLine(line.book_id, line.quantity, line.unit_price_paise)
            continue
        existing = combined[line.book_id]
        if existing.unit_price_paise != line.unit_price_paise:
            raise ValidationError(["The same book appears twice at different prices."])
        existing.quantity += line.quantity
    return list(combined.values())


def record_sale(
    conn: sqlite3.Connection,
    lines: list[SaleLine],
    sale_datetime: datetime | None = None,
    now: datetime | None = None,
    recorded_by: int | None = None,
) -> int:
    """Save a completed sale and reduce stock, all or nothing.

    sale_datetime is when the sale happened (default: now). It may be in
    the past, for entering receipts later, but not in the future.
    recorded_by is the user_id of the person recording it.
    Returns the new sale_id. Raises ValidationError, with every problem
    found, if anything is wrong; in that case nothing is saved.
    """
    now = now or datetime.now()
    when = sale_datetime or now
    errors = []
    if not lines:
        errors.append("Add at least one book to the sale.")
    for line in lines:
        if isinstance(line.quantity, bool) or not isinstance(line.quantity, int) or line.quantity < 1:
            errors.append("Each quantity must be a whole number of at least 1.")
            break
    if when > now:
        errors.append("A sale can't be dated in the future.")
    if errors:
        raise ValidationError(errors)
    lines = _combine_lines(lines)

    # `with conn:` = one transaction. Raising an error anywhere inside it
    # rolls back everything done so far, including earlier stock updates.
    with conn:
        sale_id = conn.execute(
            "INSERT INTO sales (sale_datetime, status, recorded_by) VALUES (?, 'completed', ?)",
            (when.strftime(TIMESTAMP_FORMAT), recorded_by),
        ).lastrowid
        problems = []
        for line in lines:
            book = conn.execute(
                "SELECT title, selling_price_paise, stock_quantity FROM books WHERE book_id = ?",
                (line.book_id,),
            ).fetchone()
            if book is None:
                problems.append("A book in this sale is no longer in the catalogue.")
                continue
            if book["selling_price_paise"] != line.unit_price_paise:
                problems.append(
                    f"The price of “{book['title']}” is now {format_rupees(book['selling_price_paise'])}, "
                    f"not {format_rupees(line.unit_price_paise)}. Remove it and add it again."
                )
                continue
            # Check and change in ONE statement: the stock only goes down if
            # enough copies exist at this very moment. Nothing can slip in
            # between a separate "check" and "change".
            reduced = conn.execute(
                """
                UPDATE books SET stock_quantity = stock_quantity - :quantity
                WHERE book_id = :book_id AND stock_quantity >= :quantity
                """,
                {"quantity": line.quantity, "book_id": line.book_id},
            ).rowcount
            if reduced == 0:
                problems.append(
                    f"Only {_copies(book['stock_quantity'])} of “{book['title']}” in stock; "
                    f"the sale asks for {line.quantity}."
                )
                continue
            conn.execute(
                "INSERT INTO sale_items (sale_id, book_id, quantity, unit_price_paise) VALUES (?, ?, ?, ?)",
                (sale_id, line.book_id, line.quantity, line.unit_price_paise),
            )
        if problems:
            raise ValidationError(problems)   # rolls back the sale and every stock change
    return sale_id


def cancel_sale(
    conn: sqlite3.Connection, sale_id: int, reason: str, now: datetime | None = None,
    cancelled_by: int | None = None,
) -> None:
    """Cancel a completed sale and return its copies to stock, exactly once."""
    reason = " ".join((reason or "").split())
    if not reason:
        raise ValidationError(["Give a reason for cancelling the sale."])
    cancelled_at = (now or datetime.now()).strftime(TIMESTAMP_FORMAT)

    with conn:
        # Only a sale that is still 'completed' changes. A second attempt
        # matches no rows, so copies are never returned twice.
        changed = conn.execute(
            "UPDATE sales SET status = 'cancelled' WHERE sale_id = ? AND status = 'completed'",
            (sale_id,),
        ).rowcount
        if changed == 0:
            exists = conn.execute("SELECT 1 FROM sales WHERE sale_id = ?", (sale_id,)).fetchone()
            raise ValidationError(
                ["This sale was already cancelled."] if exists else [f"Sale #{sale_id} doesn't exist."]
            )
        # Put each book's copies back on the shelf.
        lines = conn.execute(
            "SELECT book_id, quantity FROM sale_items WHERE sale_id = ?", (sale_id,)
        ).fetchall()
        for line in lines:
            conn.execute(
                "UPDATE books SET stock_quantity = stock_quantity + ? WHERE book_id = ?",
                (line["quantity"], line["book_id"]),
            )
        conn.execute(
            "INSERT INTO sale_cancellations (sale_id, cancelled_at, reason, cancelled_by) VALUES (?, ?, ?, ?)",
            (sale_id, cancelled_at, reason, cancelled_by),
        )


def list_sales(conn: sqlite3.Connection, limit: int = 50) -> list[dict]:
    """Recent sales, newest first, with their copies and totals."""
    rows = conn.execute(
        """
        SELECT s.sale_id, s.sale_datetime, s.status, s.recorded_by,
               COUNT(si.sale_item_id)                  AS line_count,
               SUM(si.quantity)                        AS copies,
               SUM(si.quantity * si.unit_price_paise)  AS total_paise
        FROM sales AS s
        JOIN sale_items AS si ON si.sale_id = s.sale_id
        GROUP BY s.sale_id
        ORDER BY s.sale_datetime DESC, s.sale_id DESC
        LIMIT ?
        """,
        (limit,),
    )
    return [dict(row) for row in rows]


def get_sale(conn: sqlite3.Connection, sale_id: int) -> dict | None:
    """One sale with its lines and, if cancelled, when and why."""
    sale = conn.execute(
        """
        SELECT s.sale_id, s.sale_datetime, s.status, s.recorded_by,
               c.cancelled_at, c.reason AS cancel_reason, c.cancelled_by
        FROM sales AS s
        LEFT JOIN sale_cancellations AS c ON c.sale_id = s.sale_id
        WHERE s.sale_id = ?
        """,
        (sale_id,),
    ).fetchone()
    if sale is None:
        return None
    lines = conn.execute(
        """
        SELECT b.title, si.quantity, si.unit_price_paise,
               si.quantity * si.unit_price_paise AS line_total_paise
        FROM sale_items AS si
        JOIN books AS b ON b.book_id = si.book_id
        WHERE si.sale_id = ?
        ORDER BY si.sale_item_id
        """,
        (sale_id,),
    ).fetchall()
    result = dict(sale)
    result["lines"] = [dict(line) for line in lines]
    result["total_paise"] = sum(line["line_total_paise"] for line in lines)
    result["copies"] = sum(line["quantity"] for line in lines)
    return result
