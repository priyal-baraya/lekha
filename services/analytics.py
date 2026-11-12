"""Sales analytics: the numbers behind the Insights page.

The SQL lives in sql/analytics/ so it can be read on its own. Every
query starts from the same `period_lines` definition (completed sales in
the period, optionally one genre), so all figures agree with each other.

Division of work:
  SQL     filtering, joining, summing, grouping, ranking
  pandas  filling empty days/weeks/months with zero
  Python  periods, percentages and the wording of observations
"""

import calendar
import sqlite3
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import pandas as pd

from services.money import format_rupees

SQL_DIR = Path(__file__).parent.parent / "sql" / "analytics"

# Below this many sales, findings are labelled as hints, not patterns.
MIN_SALES_FOR_PATTERN = 30

PERIOD_LABELS = {
    "last_7": "Last 7 days",
    "last_30": "Last 30 days",
    "this_month": "This month",
    "last_month": "Last month",
    "all_time": "All time",
    "custom": "Custom dates",
}
GRAINS = ("day", "week", "month")


# ---------------------------------------------------------------- periods

@dataclass(frozen=True)
class Period:
    """A range of whole days, both ends included."""

    start: date
    end: date
    label: str = ""

    @property
    def start_text(self) -> str:
        return f"{self.start.isoformat()} 00:00:00"

    @property
    def end_exclusive_text(self) -> str:
        """Midnight at the start of the day AFTER the last day."""
        return f"{(self.end + timedelta(days=1)).isoformat()} 00:00:00"

    def describe(self) -> str:
        span = f"{self.start:%d %b %Y} to {self.end:%d %b %Y}"
        return f"{self.label} ({span})" if self.label else span


def earliest_sale_date(conn: sqlite3.Connection) -> date | None:
    first = conn.execute(
        "SELECT MIN(sale_datetime) FROM sales WHERE status = 'completed'"
    ).fetchone()[0]
    return date.fromisoformat(first[:10]) if first else None


def period_for(
    conn: sqlite3.Connection,
    choice: str,
    today: date,
    custom: tuple[date, date] | None = None,
) -> Period:
    """Turn a choice like "last_30" into exact dates, ending today."""
    label = PERIOD_LABELS[choice]
    if choice == "last_7":
        return Period(today - timedelta(days=6), today, label)
    if choice == "last_30":
        return Period(today - timedelta(days=29), today, label)
    if choice == "this_month":
        return Period(today.replace(day=1), today, label)
    if choice == "last_month":
        last_day = today.replace(day=1) - timedelta(days=1)
        return Period(last_day.replace(day=1), last_day, label)
    if choice == "all_time":
        return Period(earliest_sale_date(conn) or today, today, label)
    if choice == "custom":
        if not custom or custom[0] > custom[1]:
            raise ValueError("A custom period needs a start date on or before its end date.")
        return Period(custom[0], custom[1], label)
    raise ValueError(f"Unknown period: {choice}")


# ---------------------------------------------------------- running SQL

def _query(conn, name: str, period: Period, genre: str | None, **extra) -> list[dict]:
    """Run sql/analytics/<name>.sql with period_lines placed in front of it."""
    cte = (SQL_DIR / "_period_lines.sql").read_text(encoding="utf-8")
    body = (SQL_DIR / f"{name}.sql").read_text(encoding="utf-8")
    sql = f"WITH period_lines AS (\n{cte}\n)\n{body}"
    params = {"start": period.start_text, "end": period.end_exclusive_text, "genre": genre, **extra}
    return [dict(row) for row in conn.execute(sql, params)]


def previous_period(period: Period) -> Period:
    """The period of the same length that ends the day before this one starts.

    Last 30 days (14 Oct to 12 Nov) -> 14 Sep to 13 Oct, "the 30 days before".
    """
    length = (period.end - period.start).days + 1
    end = period.start - timedelta(days=1)
    label = "the day before" if length == 1 else f"the {length} days before"
    return Period(end - timedelta(days=length - 1), end, label)


def days_of_history(conn: sqlite3.Connection, today: date) -> int:
    """Days from the first completed sale to today, both included (0 with no sales)."""
    first = earliest_sale_date(conn)
    return (today - first).days + 1 if first else 0


# ------------------------------------------------- exact time windows

@dataclass(frozen=True)
class Window:
    """From one moment up to (not including) another, for figures that
    stop part-way through a day: "today so far", "by this time last week".
    Has the same two properties as Period, so the same SQL runs on it."""

    start: datetime
    end: datetime

    @property
    def start_text(self) -> str:
        return self.start.strftime("%Y-%m-%d %H:%M:%S")

    @property
    def end_exclusive_text(self) -> str:
        return self.end.strftime("%Y-%m-%d %H:%M:%S")


def _window_totals(conn, window: Window) -> dict:
    return _query(conn, "summary", window, None)[0]


def today_so_far(conn, now: datetime) -> dict:
    """Completed sales from midnight up to now."""
    return _window_totals(conn, Window(datetime.combine(now.date(), time()), now))


def same_time_last_week(conn, now: datetime) -> dict:
    """Completed sales on the same weekday last week, from midnight up to
    the same time of day. The fair comparison for "today so far"."""
    then = now - timedelta(days=7)
    return _window_totals(conn, Window(datetime.combine(then.date(), time()), then))


def week_so_far(conn, now: datetime) -> dict:
    """Completed sales from Monday midnight up to now."""
    monday = now.date() - timedelta(days=now.weekday())
    return _window_totals(conn, Window(datetime.combine(monday, time()), now))


def percent(part: int, whole: int) -> Decimal:
    """part as a percentage of whole, to one decimal place: 404000 of 1114400 -> 36.3."""
    if whole == 0:
        return Decimal("0.0")
    return (Decimal(part) * 100 / Decimal(whole)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)


# -------------------------------------------------------------- metrics

def summary(conn, period: Period, genre: str | None = None) -> dict:
    """Revenue, copies, transactions and average sale for the period."""
    row = _query(conn, "summary", period, genre)[0]
    transactions = row["transactions"]
    # Whole paise, rounded half up: the average must stay an exact amount.
    row["average_sale_paise"] = (
        int((Decimal(row["revenue_paise"]) / transactions).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        if transactions else 0
    )
    return row


def revenue_by_genre(conn, period: Period) -> list[dict]:
    """Every genre's revenue and share. Always all genres, by design."""
    rows = _query(conn, "revenue_by_genre", period, None)
    total = sum(row["revenue_paise"] for row in rows)
    for row in rows:
        row["share_percent"] = percent(row["revenue_paise"], total)
    return rows


def best_sellers(conn, period: Period, genre: str | None = None) -> list[dict]:
    return _query(conn, "best_sellers", period, genre)


def unsold_books(conn, period: Period, genre: str | None = None) -> list[dict]:
    return _query(conn, "unsold_books", period, genre)


def gross_profit(conn, period: Period, genre: str | None = None) -> dict:
    """Estimated gross profit, with how much revenue it covers."""
    row = _query(conn, "gross_profit", period, genre)[0]
    row["coverage_percent"] = percent(row["revenue_with_cost_paise"], row["revenue_paise"])
    row["margin_percent"] = percent(row["estimated_gross_profit_paise"], row["revenue_with_cost_paise"])
    return row


def _bucket_start(day: date, grain: str) -> date:
    if grain == "day":
        return day
    if grain == "week":
        return day - timedelta(days=day.weekday())   # Monday = 0
    return day.replace(day=1)


def _bucket_end(start: date, grain: str) -> date:
    if grain == "day":
        return start
    if grain == "week":
        return start + timedelta(days=6)
    return start.replace(day=calendar.monthrange(start.year, start.month)[1])


def _next_bucket(start: date, grain: str) -> date:
    return _bucket_end(start, grain) + timedelta(days=1)


def revenue_over_time(
    conn, period: Period, grain: str = "week", genre: str | None = None, today: date | None = None
) -> pd.DataFrame:
    """One row per day/week/month in the period, including empty ones.

    Columns: bucket_start, bucket_end, revenue_paise, copies, transactions,
    partial. A bucket is partial when part of it falls outside the period,
    or when it includes today (the day isn't over yet).
    """
    if grain not in GRAINS:
        raise ValueError(f"Unknown grain: {grain}")
    today = today or date.today()
    found = pd.DataFrame(
        _query(conn, "revenue_over_time", period, genre, grain=grain),
        columns=["bucket_start", "revenue_paise", "copies", "transactions"],
    )
    found["bucket_start"] = pd.to_datetime(found["bucket_start"]).dt.date

    # Every bucket from the one holding the first day to the one holding the last.
    starts, current = [], _bucket_start(period.start, grain)
    while current <= period.end:
        starts.append(current)
        current = _next_bucket(current, grain)

    # reindex: keep the found rows, add the missing buckets, fill them with 0.
    table = (
        found.set_index("bucket_start")
        .reindex(starts, fill_value=0)
        .rename_axis("bucket_start")
        .reset_index()
    )
    # With no sales at all, pandas can't tell these are numbers; make sure.
    for column in ("revenue_paise", "copies", "transactions"):
        table[column] = table[column].astype(int)
    table["bucket_end"] = table["bucket_start"].map(lambda start: _bucket_end(start, grain))
    table["partial"] = [
        start < period.start or end > period.end or end >= today
        for start, end in zip(table["bucket_start"], table["bucket_end"])
    ]
    return table[["bucket_start", "bucket_end", "revenue_paise", "copies", "transactions", "partial"]]


# --------------------------------------------------------- observations

@dataclass
class Observation:
    """A finding in plain language, always with its evidence and limits."""

    title: str
    evidence: str
    action: str = ""
    limits: list[str] = field(default_factory=list)


def _names(rows: list[dict], limit: int = 4) -> str:
    titles = [f"“{row['title']}”" for row in rows[:limit]]
    more = len(rows) - limit
    if more > 0:
        titles.append(f"{more} more")
    return titles[0] if len(titles) == 1 else ", ".join(titles[:-1]) + " and " + titles[-1]


def observations(
    conn, period: Period, genre: str | None = None, low_stock: list[dict] | None = None
) -> list[Observation]:
    """Findings built only from calculated numbers, each with its limits."""
    totals = summary(conn, period, genre)
    sales = totals["transactions"]
    if sales == 0:
        return [Observation(
            "No completed sales in this period",
            f"There are no completed sales for {period.describe()}"
            + (f" in {genre}." if genre else "."),
            limits=["Nothing can be concluded. Try a longer period."],
        )]

    small = []
    if sales < MIN_SALES_FOR_PATTERN:
        small = [f"Only {sales} {'sale' if sales == 1 else 'sales'} in this period, "
                 "so treat this as a hint, not a pattern."]
    found: list[Observation] = []

    if genre is None:
        genres = revenue_by_genre(conn, period)
        if len(genres) >= 2:
            top = genres[0]
            found.append(Observation(
                f"{top['genre']} brought in the most revenue",
                f"{format_rupees(top['revenue_paise'])} of {format_rupees(totals['revenue_paise'])} "
                f"({top['share_percent']}%) across {sales} {'sale' if sales == 1 else 'sales'}.",
                f"Possible action: consider a {top['genre']} display or table.",
                ["Based on recorded sales only. It doesn't show that a display would increase sales.", *small],
            ))

    leaders = [row for row in best_sellers(conn, period, genre) if row["copies_rank"] == 1]
    if leaders:
        copies = leaders[0]["copies"]
        tied = len(leaders) > 1
        found.append(Observation(
            (f"{_names(leaders)} tied as best sellers" if tied
             else f"{_names(leaders)} sold the most copies"),
            f"{copies} {'copy' if copies == 1 else 'copies'} {'each' if tied else ''}".strip()
            + f" out of {totals['copies']} sold.",
            "Possible action: check it stays in stock." if not tied else "Possible action: check they stay in stock.",
            ["Copies sold, not profit: a cheaper book can top this list.", *small],
        ))

    if low_stock is not None:
        sold_ids = {row["book_id"] for row in best_sellers(conn, period, genre)}
        selling_and_low = [book for book in low_stock if book["book_id"] in sold_ids]
        if selling_and_low:
            found.append(Observation(
                "Selling, and low on stock",
                f"{_names(selling_and_low)} sold in this period and "
                f"{'is' if len(selling_and_low) == 1 else 'are'} at or below the reorder level.",
                "Worth checking before the next order.",
                ["This is an alert, not a reorder recommendation: it doesn't account for "
                 "delivery times or whether sales will continue."],
            ))

    unsold_on_shelf = [book for book in unsold_books(conn, period, genre) if book["stock_quantity"] > 0]
    if unsold_on_shelf:
        copies_waiting = sum(book["stock_quantity"] for book in unsold_on_shelf)
        found.append(Observation(
            "On the shelf, no sales this period",
            f"{_names(unsold_on_shelf)}: {copies_waiting} "
            f"{'copy' if copies_waiting == 1 else 'copies'} in stock with no completed sales.",
            "Possible action: consider moving them to a more visible spot.",
            ["“No sales in this period” isn't the same as “slow-selling”. Lekha doesn't record "
             "when each book arrived, so a recently added book may simply be new.", *small],
        ))
    return found
