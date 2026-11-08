"""Insights: what the recorded sales say, for a chosen period and genre.

Every number comes from services/analytics.py, which is tested against
hand calculations. This page only arranges and explains them.
"""

from datetime import date, timedelta

import pandas as pd
import streamlit as st

from database import connect
from services import analytics
from services.books import list_genres
from services.inventory import low_stock_books
from services.money import format_rupees, paise_to_rupees
from ui import charts
from ui import components as ui

ALL_GENRES = "All genres"
GRAIN_LABELS = {"day": "Day", "week": "Week", "month": "Month"}


def copies(n: int) -> str:
    return f"{n} {'copy' if n == 1 else 'copies'}"


def render_filters(conn) -> tuple[analytics.Period, str | None, str]:
    today = date.today()
    period_col, genre_col, grain_col = st.columns([1.4, 1.2, 1])
    choice = period_col.selectbox(
        "Period", list(analytics.PERIOD_LABELS), index=1,     # default: last 30 days
        format_func=analytics.PERIOD_LABELS.get, key="insights_period",
    )
    genre_choice = genre_col.selectbox("Genre", [ALL_GENRES, *list_genres(conn)], key="insights_genre")
    grain = grain_col.selectbox(
        "Group sales by", list(GRAIN_LABELS), index=1, format_func=GRAIN_LABELS.get, key="insights_grain",
    )
    custom = None
    if choice == "custom":
        picked = st.date_input(
            "From and to (both days included)", value=(today - timedelta(days=29), today),
            max_value=today, key="insights_custom",
        )
        if not isinstance(picked, tuple) or len(picked) != 2:
            st.info("Choose both a start date and an end date.")
            st.stop()
        custom = picked
    period = analytics.period_for(conn, choice, today, custom)
    genre = None if genre_choice == ALL_GENRES else genre_choice
    return period, genre, grain


def render_headline(conn, period, genre) -> dict:
    totals = analytics.summary(conn, period, genre)
    average_note = (f"{genre} revenue ÷ sales that included it" if genre else "Revenue ÷ transactions")
    ui.metric_strip([
        ("Revenue", format_rupees(totals["revenue_paise"]), "Completed sales only"),
        ("Copies sold", str(totals["copies"]), "Books, not sales"),
        ("Transactions", str(totals["transactions"]), "Sales recorded"),
        ("Average sale", format_rupees(totals["average_sale_paise"]) if totals["transactions"] else None,
         average_note if totals["transactions"] else "No sales to average"),
    ])
    return totals


def render_trend(conn, period, genre, grain) -> None:
    ui.section_header(
        eyebrow="Over time",
        title="Revenue over time",
        description="Outlined bars are partial periods: they start before the chosen dates, "
                    "end after them, or haven't finished yet, so they can look lower than they are.",
    )
    table = analytics.revenue_over_time(conn, period, grain, genre)
    if table["revenue_paise"].sum() == 0:
        ui.empty_state("No completed sales in this period, so there is nothing to chart.")
        return
    best = table.loc[table["revenue_paise"].idxmax()]
    unit = {"day": "day", "week": "week", "month": "month"}[grain]
    empty = int((table["revenue_paise"] == 0).sum())
    partial = int(table["partial"].sum())
    summary = (
        f"Highest {unit}: {unit_name(best['bucket_start'], grain)}, {format_rupees(int(best['revenue_paise']))}. "
        f"{len(table)} {unit}s shown"
        + (f", {empty} with no sales" if empty else "")
        + (f", {partial} partial" if partial else "")
        + "."
    )
    st.altair_chart(charts.revenue_over_time(table, grain), width="stretch", alt=summary)
    st.markdown(summary)
    with st.expander("Show as a table"):
        shown = table.assign(
            period=table["bucket_start"].map(lambda d: unit_name(d, grain)),
            revenue=table["revenue_paise"].map(format_rupees),
            status=table["partial"].map({True: "Partial", False: "Complete"}),
        )
        st.dataframe(
            shown[["period", "revenue", "copies", "transactions", "status"]], hide_index=True,
            column_config={"period": "Period", "revenue": "Revenue", "copies": "Copies",
                           "transactions": "Sales", "status": "Period status"},
        )


def unit_name(day: date, grain: str) -> str:
    if grain == "month":
        return f"{day:%B %Y}"
    if grain == "week":
        return f"week of {day:%d %b %Y}"
    return f"{day:%d %b %Y}"


def render_genres(conn, period, genre) -> None:
    ui.section_header(
        eyebrow="By genre",
        title="Revenue by genre",
        description="Always shows every genre, so they can be compared"
                    + (f". The genre filter ({genre}) doesn't apply here." if genre else "."),
    )
    rows = analytics.revenue_by_genre(conn, period)
    if not rows:
        ui.empty_state("No completed sales in this period.")
        return
    total = sum(row["revenue_paise"] for row in rows)
    summary = "; ".join(f"{row['genre']} {format_rupees(row['revenue_paise'])} ({row['share_percent']}%)" for row in rows)
    st.altair_chart(charts.revenue_by_genre(rows), width="stretch", alt="Revenue by genre: " + summary)
    shares = sum(row["share_percent"] for row in rows)
    note = f"Total {format_rupees(total)}."
    if shares != 100:
        note += f" Percentages are rounded to one decimal place, so they add up to {shares}%."
    st.markdown(note)
    with st.expander("Show as a table"):
        st.dataframe(
            pd.DataFrame([{"Genre": row["genre"], "Revenue": format_rupees(row["revenue_paise"]),
                           "Share": f"{row['share_percent']}%", "Copies": row["copies"]} for row in rows]),
            hide_index=True,
        )


def render_best_sellers(conn, period, genre) -> None:
    ui.section_header(
        eyebrow="Best sellers",
        title="Most copies sold",
        description="Ranked by copies. Books with the same number of copies share a rank.",
    )
    rows = analytics.best_sellers(conn, period, genre)
    if not rows:
        ui.empty_state("No books sold in this period.")
        return
    table = pd.DataFrame(rows[:10])
    table["revenue"] = table["revenue_paise"].map(lambda paise: float(paise_to_rupees(paise)))
    st.dataframe(
        table[["copies_rank", "title", "author", "genre", "copies", "revenue"]],
        hide_index=True,
        column_config={
            "copies_rank": st.column_config.NumberColumn("Rank", format="%d"),
            "title": "Title", "author": "Author", "genre": "Genre",
            "copies": st.column_config.NumberColumn("Copies"),
            "revenue": st.column_config.NumberColumn("Revenue", format="₹%.2f"),
        },
    )
    if len(rows) > 10:
        st.markdown(f"Showing the top 10 of {len(rows)} books that sold.")


def render_unsold_and_profit(conn, period, genre) -> None:
    unsold_col, profit_col = st.columns(2, gap="large")
    with unsold_col:
        ui.section_header(
            eyebrow="Not moving",
            title="No sales in this period",
            description="Books with no completed sales in these dates. That isn't the same as "
                        "slow-selling: Lekha doesn't record when each book arrived.",
        )
        rows = analytics.unsold_books(conn, period, genre)
        if rows:
            st.dataframe(
                pd.DataFrame(rows)[["title", "genre", "stock_quantity"]], hide_index=True,
                column_config={"title": "Title", "genre": "Genre",
                               "stock_quantity": st.column_config.NumberColumn("In stock")},
            )
        else:
            ui.empty_state(f"Every {genre + ' ' if genre else ''}book had at least one sale in this period.")
    with profit_col:
        ui.section_header(
            eyebrow="Estimate",
            title="Estimated gross profit",
            description="Price paid minus each book's current cost per copy. An estimate, not accounts.",
        )
        profit = analytics.gross_profit(conn, period, genre)
        if profit["revenue_paise"] == 0:
            ui.empty_state("No completed sales in this period.")
            return
        ui.metric_strip([
            ("Estimated gross profit", format_rupees(profit["estimated_gross_profit_paise"]),
             f"Estimated margin {profit['margin_percent']}%"),
        ])
        st.markdown(
            f"Calculated on **{format_rupees(profit['revenue_with_cost_paise'])}** of "
            f"{format_rupees(profit['revenue_paise'])} revenue ({profit['coverage_percent']}%). "
            "Books without a recorded cost are left out rather than counted as free. "
            "It uses today's cost per copy, not what each copy actually cost, and leaves out "
            "rent, wages and other running costs."
        )


def render_observations(conn, period, genre) -> None:
    ui.section_header(
        eyebrow="Observations",
        title="What the numbers suggest",
        description="Plain-language findings from the figures above. Each shows its evidence "
                    "and its limits. They describe recorded sales; they can't prove causes.",
    )
    for item in analytics.observations(conn, period, genre, low_stock=low_stock_books(conn)):
        with st.container(border=True):
            st.markdown(f"**{item.title}**")
            st.markdown(item.evidence)
            if item.action:
                st.markdown(f"*{item.action}*")
            for limit in item.limits:
                # Normal text, not st.caption: caption text is faded and
                # these limits matter as much as the finding.
                st.markdown(f"Limit: {limit}")


# ------------------------------------------------------------------ page

ui.section_header(
    eyebrow="Reading between the numbers",
    title="Insights",
    description="What recorded sales show about revenue, genres and best sellers.",
    page_title=True,
)
ui.sample_data_notice()

with connect() as conn:
    period, genre, grain = render_filters(conn)
    st.markdown(f"Completed sales · **{period.describe()}** · {genre or 'all genres'}")
    render_headline(conn, period, genre)
    ui.divider()
    render_trend(conn, period, genre, grain)
    ui.divider()
    render_genres(conn, period, genre)
    ui.divider()
    render_best_sellers(conn, period, genre)
    ui.divider()
    render_unsold_and_profit(conn, period, genre)
    ui.divider()
    render_observations(conn, period, genre)
