"""The one-sentence summaries at the top of Overview and Insights, and
the counts under shortened lists.

Every sentence is built from figures by fixed rules, so each word can be
traced to a number. Nothing is guessed or generated, and nothing claims
a cause: "Revenue rose 12%", never "Revenue rose because…".
"""

from decimal import ROUND_HALF_UP, Decimal

from services.money import format_rupees_whole

# Insights waits for this much sales history before talking about trends.
MIN_HISTORY_DAYS = 14


def _plural(n: int, one: str, many: str) -> str:
    return f"{n} {one if n == 1 else many}"


def overview_sentence(total_books: int, has_sales: bool, today_revenue_paise: int, low_stock: int) -> str:
    """Overview's opening line: today so far, and what needs reordering."""
    if total_books == 0:
        return ("Welcome to Lekha. Add your books and record your sales, "
                "and your shop's numbers will start to appear here.")
    if not has_sales:
        return "Your books are in. Record your first sale on the Sales page, and today's figures will appear here."
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
        return (f"Insights need a little more history. You've recorded {_plural(sales, 'sale', 'sales')} so far; "
                "trends appear after two weeks of sales.")
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


def showing(shown: int, total: int) -> str:
    """The line under a shortened list: "Showing 5 of 137." """
    if total <= 1:
        return ""
    if shown >= total:
        return f"All {total} shown."
    return f"Showing {shown} of {total}."
