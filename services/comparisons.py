"""How a figure compares with an earlier one, in words a person can check.

The rules (agreed in the 2026-11-12 design review, docs/decision-log.md):

- Compare like with like. Today's sales so far are compared with the
  same time last week, never with a whole day.
- With nothing fair to compare against (nothing before), show no change
  at all: the functions return None, and the page shows only the figure.
- Say the earlier figure, so the change can be checked:
  "12% more than ₹43,080", not just "+12%".
- Tone says how to colour it. "good" and "bad" only where up is good
  (revenue, copies, sales); everything else is "neutral".
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from services.money import format_rupees_whole


@dataclass(frozen=True)
class Comparison:
    text: str
    tone: str           # "good", "bad" or "neutral"


def _whole_percent(current: int, previous: int) -> int:
    """The change as a whole percentage, rounded half up: 186 vs 172 -> 8."""
    exact = Decimal(abs(current - previous)) * 100 / Decimal(previous)
    return int(exact.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def compare_money(current_paise: int, previous_paise: int) -> Comparison | None:
    """Revenue against an earlier period: "12% more than ₹43,080"."""
    if previous_paise <= 0:
        return None
    before = format_rupees_whole(previous_paise)
    pct = _whole_percent(current_paise, previous_paise)
    if pct == 0:
        return Comparison(f"About the same as {before}", "neutral")
    if current_paise > previous_paise:
        return Comparison(f"{pct}% more than {before}", "good")
    return Comparison(f"{pct}% less than {before}", "bad")


def compare_count(current: int, previous: int, by: str = "percent") -> Comparison | None:
    """Copies or sales against an earlier period.

    by="percent":    "8% more than 172"
    by="difference": "25 more than 140" (clearer for small whole numbers)
    """
    if previous <= 0:
        return None
    if by == "difference":
        gap = abs(current - previous)
        if gap == 0:
            return Comparison("The same as before", "neutral")
        word, tone = ("more", "good") if current > previous else ("fewer", "bad")
        return Comparison(f"{gap} {word} than {previous}", tone)
    pct = _whole_percent(current, previous)
    if pct == 0:
        return Comparison(f"About the same as {previous}", "neutral")
    word, tone = ("more", "good") if current > previous else ("fewer", "bad")
    return Comparison(f"{pct}% {word} than {previous}", tone)


def before_money(previous_paise: int) -> Comparison | None:
    """A neutral earlier amount, for figures where up isn't good or bad
    (the average per sale): "₹308 before"."""
    if previous_paise <= 0:
        return None
    return Comparison(f"{format_rupees_whole(previous_paise)} before", "neutral")


def same_time_last_week(previous_paise: int, weekday: str) -> Comparison:
    """Today so far against the same weekday last week, up to the same time.

    Always neutral: a single day goes up and down for many reasons, and
    a part-day is too little to call good or bad."""
    if previous_paise <= 0:
        return Comparison(f"No sales by this time last {weekday}", "neutral")
    return Comparison(f"{format_rupees_whole(previous_paise)} by this time last {weekday}", "neutral")
