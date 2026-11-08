"""Chart builders for the Insights page (Altair, which Streamlit draws).

Each chart shows ONE series (revenue), so it uses one colour, Manuscript
Crimson, and needs no colour legend. Fonts, background and grid come
from the Streamlit theme in .streamlit/config.toml.

Accessibility: partial periods are told apart by shape (an outlined bar
instead of a filled one), not by colour alone; every bar has a tooltip;
and the page also shows each chart's numbers as text and as a table.
"""

import altair as alt
import pandas as pd

from services.money import format_rupees

CRIMSON = "#791A24"
INK_SECONDARY = "#67554A"

BUCKET_NAMES = {"day": "Day", "week": "Week starting", "month": "Month"}

# Streamlit's chart theme draws axis text in a faded ink that measured
# 3.15:1 against the paper (below 4.5:1). Secondary Text measures about 6:1.
# Set on each axis, because settings on the axis win over the theme.
AXIS_TEXT = {"labelColor": INK_SECONDARY, "titleColor": INK_SECONDARY}


def _rupee_axis(title: str) -> alt.Axis:
    # Axis labels like ₹2,000. (Vega's number format has no Indian
    # grouping; it matches below one lakh, which covers this data.)
    return alt.Axis(title=title, labelExpr="'₹' + format(datum.value, ',.0f')", tickCount=5, **AXIS_TEXT)


def revenue_over_time(table: pd.DataFrame, grain: str) -> alt.Chart:
    """Bars per day/week/month. Partial periods are outlined, not filled."""
    data = table.copy()
    data["rupees"] = data["revenue_paise"] / 100       # display only
    data["label"] = data["bucket_start"].map(
        lambda d: d.strftime("%b %Y") if grain == "month" else d.strftime("%d %b")
    )
    data["revenue_text"] = data["revenue_paise"].map(format_rupees)
    data["completeness"] = data["partial"].map({True: "Partial or in progress", False: "Complete"})
    order = list(data["label"])

    return (
        alt.Chart(data)
        .mark_bar(stroke=CRIMSON, strokeWidth=1.5)
        .encode(
            x=alt.X("label:N", sort=order, title=BUCKET_NAMES[grain],
                    axis=alt.Axis(labelAngle=0 if len(order) <= 12 else -45, **AXIS_TEXT)),
            y=alt.Y("rupees:Q", axis=_rupee_axis("Revenue")),
            # Shape, not colour, marks a partial period: filled = complete,
            # outline only = partial or in progress.
            fill=alt.condition(alt.datum.partial, alt.value("transparent"), alt.value(CRIMSON)),
            tooltip=[
                alt.Tooltip("label:N", title=BUCKET_NAMES[grain]),
                alt.Tooltip("revenue_text:N", title="Revenue"),
                alt.Tooltip("copies:Q", title="Copies"),
                alt.Tooltip("transactions:Q", title="Sales"),
                alt.Tooltip("completeness:N", title="Period"),
            ],
        )
        .properties(height=280)
    )


def revenue_by_genre(rows: list[dict]) -> alt.Chart:
    """Horizontal bars, largest first, each labelled with ₹ and %."""
    data = pd.DataFrame(rows)
    data["rupees"] = data["revenue_paise"] / 100
    data["value_label"] = [
        f"{format_rupees(paise)} · {share}%"
        for paise, share in zip(data["revenue_paise"], data["share_percent"])
    ]
    order = list(data["genre"])
    base = alt.Chart(data).encode(
        y=alt.Y("genre:N", sort=order, title=None, axis=alt.Axis(labelLimit=160, **AXIS_TEXT)),
        x=alt.X("rupees:Q", axis=_rupee_axis("Revenue"),
                # Leave room on the right for the "₹4,040.00 · 36.3%" labels.
                # They need a fixed ~115px, so on a phone (about 270px of
                # plot) the scale must reach 1.8 × the largest value.
                scale=alt.Scale(domainMax=float(data["rupees"].max()) * 1.8)),
        tooltip=[
            alt.Tooltip("genre:N", title="Genre"),
            alt.Tooltip("value_label:N", title="Revenue · share"),
            alt.Tooltip("copies:Q", title="Copies"),
        ],
    )
    bars = base.mark_bar(color=CRIMSON, height=18)
    labels = base.mark_text(align="left", dx=6, color=INK_SECONDARY, fontSize=13).encode(text="value_label:N")
    return (bars + labels).properties(height=max(120, 34 * len(data)))
