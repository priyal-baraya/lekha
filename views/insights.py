"""Insights: how sales are trending, for a chosen period and genre.

Laid out as on the design canvas (Insights and InsightsEmpty artboards):
a date line and one sentence that sums up the figures, the genre and
period filters beside them, four figures compared with the period
before, revenue by day, week or month, revenue by genre next to the
estimated gross profit (owners only), the best sellers, and findings in
plain language.

Until the shop has two weeks of sales, the page says so instead, with
what it has so far: a trend from a few days would mean nothing.

Every number comes from services/analytics.py, tested against hand
calculations; every sentence from services/sentences.py. This page only
arranges them.
"""

from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal

import streamlit as st

from database import connect
from services import analytics, clock
from services.books import list_genres
from services.comparisons import before_money, compare_count, compare_money
from services.inventory import low_stock_books
from services.money import format_rupees, format_rupees_whole
from services.openlibrary import cover_url
from services.sentences import (
    MIN_HISTORY_DAYS,
    first_days_text,
    insights_sentence,
    profit_note,
    small_sample_note,
    span_text,
    trend_note,
)
from ui import charts
from ui import components as ui
from ui import session

ALL_GENRES = "All genres"
TOP_BOOKS = 5
PERIODS = ["last_7", "last_30", "this_month", "last_month", "all_time", "custom"]

now = clock.now()
today = now.date()


def whole(share) -> int:
    """A share as a whole percentage, half up (90.5 -> 91), like every other figure."""
    return int(Decimal(str(share)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


# ---------------------------------------------------------------- header

def render_header(conn):
    """The date line and sentence on the left, the filters on the right.
    The sentence depends on the filters, so its place is kept and filled
    in once the figures are known."""
    with st.container(horizontal=True, vertical_alignment="bottom", key="insights_header"):
        heading = st.container(key="insights_heading")
        with st.container(horizontal=True, width="content", key="insights_filters"):
            genre_choice = st.selectbox("Genre", [ALL_GENRES, *list_genres(conn)], key="insights_genre",
                                        label_visibility="collapsed", width=190)
            choice = st.selectbox("Period", PERIODS, index=PERIODS.index("last_30"),
                                  format_func=analytics.PERIOD_LABELS.get, key="insights_period",
                                  label_visibility="collapsed", width=170)
    custom = None
    if choice == "custom":
        picked = st.date_input("From and to", value=(today - timedelta(days=29), today), max_value=today,
                               key="insights_custom", format="DD/MM/YYYY", width=260)
        if not isinstance(picked, tuple) or len(picked) != 2:
            st.html('<p class="lekha-note">Choose a start and an end date.</p>')
            st.stop()
        custom = picked
    period = analytics.period_for(conn, choice, today, custom)
    return period, None if genre_choice == ALL_GENRES else genre_choice, heading


# --------------------------------------------------------------- figures

def render_figures(totals: dict, before: dict) -> None:
    sold = totals["transactions"]
    ui.figure_strip([
        ui.Figure("Revenue", format_rupees_whole(totals["revenue_paise"]),
                  compare_money(totals["revenue_paise"], before["revenue_paise"])),
        ui.Figure("Copies sold", str(totals["copies"]), compare_count(totals["copies"], before["copies"])),
        ui.Figure("Sales", str(sold), compare_count(sold, before["transactions"], by="difference")),
        ui.Figure("Average per sale", format_rupees_whole(totals["average_sale_paise"]) if sold else None,
                  before_money(before["average_sale_paise"]) if sold else None),
    ])


# ----------------------------------------------------------------- chart

def render_trend(conn, period, genre) -> None:
    grain = analytics.chart_grain(period)
    table = analytics.revenue_over_time(conn, analytics.chart_period(period, grain, today), grain, genre, today)
    note = trend_note(list(zip(table["bucket_start"], table["revenue_paise"], table["partial"])), grain, today)
    with st.container(key="lekha_card_trend"):
        ui.card_heading(f"Revenue by {grain}", note)
        st.altair_chart(charts.revenue_trend(table, grain), width="stretch", alt=note or f"Revenue by {grain}")
        with st.expander("Show as a table"):
            st.html(ui.data_table_html(
                [(charts.BUCKET_NAMES[grain], "left"), ("Revenue", "right"), ("Copies", "right"),
                 ("Sales", "right"), ("", "left")],
                [[charts.bar_label(row.bucket_start, grain), format_rupees(int(row.revenue_paise)),
                  int(row.copies), int(row.transactions), "So far" if row.partial else ""]
                 for row in table.itertuples()],
            ))


# ------------------------------------------------- genres, and profit

def render_genres(conn, period, genre) -> None:
    rows = analytics.revenue_by_genre(conn, period)       # always every genre, to compare
    with st.container(key="lekha_card_genres"):
        if not rows:
            ui.card_heading("Revenue by genre", "No completed sales in this period.")
            return
        ui.card_heading("Revenue by genre")
        st.html(ui.genre_bars_html([(row["genre"], row["revenue_paise"], row["share_percent"]) for row in rows],
                                   highlight=genre))


def render_profit(conn, period, genre) -> None:
    profit = analytics.gross_profit(conn, period, genre)
    with st.container(key="lekha_card_profit"):
        ui.card_heading("Estimated gross profit")
        if profit["revenue_with_cost_paise"] > 0:
            share = whole(profit["estimated_gross_profit_paise"] * 100 / profit["revenue_with_cost_paise"])
            st.html(f'<p class="lekha-figure__value">{format_rupees_whole(profit["estimated_gross_profit_paise"])}</p>'
                    f'<p class="lekha-profit__share">About {share}% of revenue</p>')
        st.html(f'<p class="lekha-card-note">{ui.escape(profit_note(profit["coverage_percent"]))}</p>')


# ------------------------------------------------------------ best sellers

def render_best_sellers(conn, period, genre) -> None:
    rows = analytics.best_sellers(conn, period, genre)
    top = analytics.add_covers(conn, rows[:TOP_BOOKS])
    with st.container(key="lekha_card_best"):
        ui.card_heading("Most copies sold")
        st.html(ui.data_table_html(
            [("#", "left"), ("Book", "left"), ("Genre", "left"), ("Copies", "right"), ("Revenue", "right")],
            [[row["copies_rank"], ui.book_cell_html(row["title"], row["author"], cover_url(row["cover_id"], "S")),
              row["genre"], row["copies"], format_rupees(row["revenue_paise"])] for row in top],
            css_class="lekha-wide-only",
        ))
        st.html('<div class="lekha-narrow-only">' + ui.book_rows_html([
            ui.BookRow(row["title"], cover_url(row["cover_id"], "S"),
                       f"{row['copies']} {'copy' if row['copies'] == 1 else 'copies'} · "
                       f"{format_rupees(row['revenue_paise'])}")
            for row in top]) + "</div>")
        ui.showing_note(len(top), len(rows))


# --------------------------------------------------------------- findings

def render_findings(conn, period, genre, sales: int) -> None:
    intro = "Patterns in your sales, not proof of why."
    small = small_sample_note(sales, analytics.MIN_SALES_FOR_PATTERN)
    st.html(f'<h2 class="lekha-section-title">What the numbers suggest</h2>'
            f'<p class="lekha-section-text">{intro}{" " + ui.escape(small) if small else ""}</p>')
    for item in analytics.observations(conn, period, genre, low_stock=low_stock_books(conn)):
        side = ("Worth trying", item.action) if item.action else ("What this can't tell you", item.limits[0])
        st.html(ui.observation_html(item.tone, item.title, item.evidence, *side))


# ------------------------------------------- before two weeks of sales

def render_waiting(conn, history: int) -> None:
    first = analytics.earliest_sale_date(conn)
    date_line = f"{span_text(first, today)} · {first_days_text(history)}" if first else ""
    ui.summary_header(date_line, "Trends appear after two weeks of sales.")
    with st.container(key="lekha_card_waiting"):
        ui.card_heading("Two weeks of sales")
        st.html(ui.progress_html(history, MIN_HISTORY_DAYS, "Days of sales recorded"))
    if first:
        so_far = analytics.summary(conn, analytics.Period(first, today))
        ui.figure_strip([
            ui.Figure("Revenue so far", format_rupees_whole(so_far["revenue_paise"])),
            ui.Figure("Copies sold", str(so_far["copies"])),
            ui.Figure("Sales", str(so_far["transactions"])),
        ])


# ------------------------------------------------------------------ page

with connect() as conn:
    history = analytics.days_of_history(conn, today)
    if history < MIN_HISTORY_DAYS:
        render_waiting(conn, history)
    else:
        period, genre, heading = render_header(conn)
        previous = analytics.previous_period(period)
        totals = analytics.summary(conn, period, genre)
        before = analytics.summary(conn, previous, genre)
        genres = [] if genre else [(row["genre"], row["share_percent"])
                                   for row in analytics.revenue_by_genre(conn, period)]
        span = span_text(period.start, period.end)
        with heading:
            ui.summary_header(
                f"{span} · compared with {previous.label}" if before["transactions"] else span,
                insights_sentence(totals["revenue_paise"], before["revenue_paise"], totals["transactions"],
                                  genres, history, previous.label),
            )
        render_figures(totals, before)
        if totals["transactions"]:
            render_trend(conn, period, genre)
            if session.can_do("view_profit"):                  # owners only
                genre_col, profit_col = st.columns(2)
                with genre_col:
                    render_genres(conn, period, genre)
                with profit_col:
                    render_profit(conn, period, genre)
            else:
                render_genres(conn, period, genre)
            render_best_sellers(conn, period, genre)
            render_findings(conn, period, genre, totals["transactions"])
