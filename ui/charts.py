"""The Insights chart (Altair, which Streamlit draws).

One series, revenue, so one hue: Manuscript Crimson, with no legend box
(the card's heading names it). How each bar is drawn says what it is:

- the latest finished day, week or month: crimson;
- earlier ones: a lighter crimson, so the latest stands out;
- the one still running: an outline with a dashed edge, because it
  isn't over yet and would otherwise look like a bad week.

Shape and position carry the meaning as well as colour (dashed edge,
last bar), every bar has a tooltip, the best, latest and running bars
are labelled with their amounts, and the page offers the numbers as a
table too.
"""

import altair as alt
import pandas as pd

from services.money import format_rupees, format_rupees_whole

CRIMSON = "#791A24"
PAST = "#C4767E"              # --lekha-chart-past: earlier bars, 3.2:1 on the card
INK_SECONDARY = "#67554A"
GRID = "#E3D1B2"              # Aged Parchment, as the canvas

BUCKET_NAMES = {"day": "Day", "week": "Week starting", "month": "Month"}

# Streamlit's chart theme draws axis text in a faded ink that measured
# 3.15:1 against the paper (below 4.5:1). Secondary Text measures about 6:1.
AXIS_TEXT = {"labelColor": INK_SECONDARY, "titleColor": INK_SECONDARY, "labelFontSize": 12}


def bar_label(start, grain: str) -> str:
    """How a bar is named on the axis: "26 Oct", or "Oct 2026" by month."""
    return f"{start:%b %Y}" if grain == "month" else f"{start.day} {start:%b}"


def revenue_trend(table: pd.DataFrame, grain: str) -> alt.LayerChart:
    """Bars per day, week or month, from analytics.revenue_over_time."""
    data = table.copy()
    data["rupees"] = data["revenue_paise"] / 100            # display only
    data["label"] = data["bucket_start"].map(lambda start: bar_label(start, grain))
    data["revenue_text"] = data["revenue_paise"].map(format_rupees)

    finished = data.index[~data["partial"]]
    latest = finished[-1] if len(finished) else None
    best = data.loc[finished, "revenue_paise"].idxmax() if len(finished) else None
    data["role"] = "earlier"
    if latest is not None:
        data.loc[latest, "role"] = "latest"
    data.loc[data["partial"], "role"] = "running"
    data["period"] = data["role"].map({"earlier": "Finished", "latest": "Finished", "running": "So far"})

    # Amounts written above the bars that matter: the best, the latest
    # finished one, and the one still running ("₹6,200 so far").
    labelled = {i for i in (best, latest) if i is not None} | set(data.index[data["partial"]])
    data["amount"] = ""
    for i in labelled:
        amount = format_rupees_whole(int(data.loc[i, "revenue_paise"]))
        data.loc[i, "amount"] = f"{amount} so far" if data.loc[i, "partial"] else amount

    order = list(data["label"])
    roles = alt.Scale(domain=["earlier", "latest", "running"], range=[PAST, CRIMSON, "transparent"])
    base = alt.Chart(data).encode(
        x=alt.X("label:N", sort=order, title=None,
                axis=alt.Axis(labelAngle=0 if len(order) <= 12 else -45, ticks=False,
                              domainColor="#8C7A68", **AXIS_TEXT)),
        y=alt.Y("rupees:Q", title=None,
                axis=alt.Axis(labelExpr="'₹' + format(datum.value, ',.0f')", tickCount=4, domain=False,
                              ticks=False, gridColor=GRID, **AXIS_TEXT)),
        tooltip=[
            alt.Tooltip("label:N", title=BUCKET_NAMES[grain]),
            alt.Tooltip("revenue_text:N", title="Revenue"),
            alt.Tooltip("copies:Q", title="Copies"),
            alt.Tooltip("transactions:Q", title="Sales"),
            alt.Tooltip("period:N", title="Period"),
        ],
    )
    bars = base.mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3, stroke=CRIMSON).encode(
        fill=alt.Fill("role:N", scale=roles, legend=None),
        strokeWidth=alt.condition(alt.datum.partial, alt.value(1.5), alt.value(0)),
        strokeDash=alt.condition(alt.datum.partial, alt.value([4, 3]), alt.value([1, 0])),
    )
    amounts = base.mark_text(dy=-8, color=INK_SECONDARY, fontSize=12).encode(text="amount:N")
    # Transparent, so the chart sits on its card rather than on a paper-coloured box
    return (bars + amounts).properties(height=220, background="transparent").configure_view(stroke=None)
