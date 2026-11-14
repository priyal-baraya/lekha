"""The one-sentence summaries at the top of Overview and Insights, and
the counts under shortened lists.

Every sentence is built from figures by fixed rules, so each word can be
traced to a number. Nothing is guessed or generated, and nothing claims
a cause: "Revenue rose 12%", never "Revenue rose because…".
"""

from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

from services.money import format_rupees_whole

# Insights waits for this much sales history before talking about trends.
MIN_HISTORY_DAYS = 14


def _plural(n: int, one: str, many: str) -> str:
    return f"{n} {one if n == 1 else many}"


def overview_sentence(total_books: int, has_sales: bool, today_revenue_paise: int, low_stock: int) -> str:
    """Overview's opening line: today so far, and what needs reordering."""
    if total_books == 0:
        return "Welcome to Lekha!"
    if not has_sales:
        return "Your books are in. Record your first sale."
    today = (f"{format_rupees_whole(today_revenue_paise)} in sales so far today" if today_revenue_paise > 0
             else "No sales yet today")
    if low_stock == 0:
        reorder = "nothing needs reordering"
    else:
        reorder = f"{_plural(low_stock, 'book needs', 'books need')} reordering"
    return f"{today}, and {reorder}."


def _whole(share) -> int:
    return int(Decimal(str(share)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def insights_sentence(
    revenue_paise: int,
    previous_revenue_paise: int,
    sales: int,
    genres: list[tuple[str, object]],
    history_days: int,
    before_label: str,
) -> str:
    """Insights' opening line: how revenue moved, and the leading genre.

    genres: (genre, share of revenue in percent), largest first.
    before_label: how to name the earlier period, e.g. "the 30 days before".
    """
    if sales == 0:
        return "No completed sales in this period. Try a longer one."
    if history_days < MIN_HISTORY_DAYS:
        return "Trends appear after two weeks of sales."
    if previous_revenue_paise <= 0:
        movement = f"{format_rupees_whole(revenue_paise)} in revenue"
    else:
        exact = Decimal(revenue_paise - previous_revenue_paise) * 100 / Decimal(previous_revenue_paise)
        pct = _whole(abs(exact))
        if pct == 0:
            movement = f"Revenue was about the same as {before_label}"
        else:
            movement = f"Revenue {'rose' if exact > 0 else 'fell'} {pct}% on {before_label}"
    if len(genres) >= 2:
        top, share = genres[0]
        return f"{movement}, and {top} brought in {_whole(share)}% of it."
    return f"{movement}."


def sale_time_label(when: datetime, today: date) -> str:
    """When a sale happened, as short as it can be: "16:45" today,
    "Yesterday 18:05", otherwise "5 Nov 10:00"."""
    clock = f"{when:%H:%M}"
    if when.date() == today:
        return clock
    if when.date() == today - timedelta(days=1):
        return f"Yesterday {clock}"
    return f"{when.day} {when:%b} {clock}"


def _and(names: list[str]) -> str:
    return names[0] if len(names) == 1 else f"{', '.join(names[:-1])} and {names[-1]}"


def selling_well_note(rows: list[dict]) -> str:
    """The line under "Selling well this week": only when a book sold out ("" otherwise)."""
    sold_out = [row["title"] for row in rows if row["stock_quantity"] == 0]
    if len(sold_out) == 1:
        return f"{sold_out[0]} sold out, so it's on the reorder list."
    if sold_out:
        return f"{_and(sold_out)} sold out, so they're on the reorder list."
    return ""


def catalogue_note(shown: int, matched: int, total: int) -> str:
    """The line under the Books table: how many books, and how many are shown."""
    if matched == 0:
        return "No books match. Try fewer letters, or choose All genres."
    if shown < matched:
        rest = (f"{matched:,} books. Search to find the rest" if matched == total
                else f"{matched:,} matches. Type more to narrow it")
        return f"Showing the first {shown} of {rest}."
    if matched < total:
        return f"Showing {matched} of {total:,} books."
    return f"{_plural(total, 'book', 'books')}."


def low_stock_note(count: int) -> str:
    """The line under Inventory's low-stock list (every low book is shown)."""
    return "1 book." if count == 1 else f"All {count} shown, emptiest first."


def correction_hint(current: int, counted: int) -> str:
    """Lekha's count, and what saving the correction will record, said before it's saved."""
    change = counted - current
    if change == 0:
        return f"Lekha has {current} in stock too, so there's nothing to record."
    sign = "+" if change > 0 else "−"            # a real minus sign, easier to read than "-"
    return f"Lekha has {current} in stock, so it will record a change of {sign}{abs(change)}."


def showing(shown: int, total: int) -> str:
    """The line under a shortened list: "Showing 5 of 137." """
    if total <= 1:
        return ""
    if shown >= total:
        return f"All {total} shown."
    return f"Showing {shown} of {total}."


def profit_note(coverage_percent: Decimal) -> str:
    """The line under estimated gross profit: how much revenue it covers
    (books without a cost are left out) and what it leaves out."""
    if coverage_percent <= 0:
        return "No books have a cost recorded yet."
    covered = "" if coverage_percent >= 100 else (
        f"From the {float(coverage_percent):g}% of revenue with a cost recorded. ")
    return covered + "Rent and wages aren't included."
