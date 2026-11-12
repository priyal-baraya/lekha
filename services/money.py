"""Converting between rupees (what people type and read) and paise
(what the database stores).

Why Decimal? Ordinary Python floats are binary fractions, so most
decimal prices are stored very slightly off. For example `19.99 * 100`
gives 1998.9999999999998, and int() of that is 1998: a paisa lost.
Decimal stores the digits exactly as written, so the conversion is exact.
"""

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

PAISE_PER_RUPEE = 100
TWO_PLACES = Decimal("0.01")


def rupees_to_paise(rupees: float | int | str | Decimal) -> int:
    """Convert a rupee amount to whole paise: 349.99 -> 34999.

    Raises ValueError for anything that isn't a valid, non-negative
    amount with at most two decimal places.
    """
    try:
        # str() first, so a float like 349.99 becomes the text "349.99"
        # before Decimal sees it, rather than its inexact binary value.
        amount = Decimal(str(rupees).strip())
    except InvalidOperation:
        raise ValueError(f"'{rupees}' is not a number.") from None
    if not amount.is_finite():
        raise ValueError(f"'{rupees}' is not a number.")
    if amount < 0:
        raise ValueError("Amounts can't be negative.")
    if amount != amount.quantize(TWO_PLACES):
        raise ValueError("Use at most two decimal places (whole paise).")
    return int(amount * PAISE_PER_RUPEE)


def paise_to_rupees(paise: int) -> Decimal:
    """Convert paise to an exact rupee amount: 34999 -> Decimal('349.99')."""
    return (Decimal(paise) / PAISE_PER_RUPEE).quantize(TWO_PLACES)


def format_rupees(paise: int) -> str:
    """Format paise for display with Indian digit grouping.

    34999 -> "₹349.99",  11144400 -> "₹1,11,444.00"
    (Indian grouping puts the first comma after three digits, then every
    two digits: thousands, lakhs, crores.)
    """
    rupees, paise_part = divmod(abs(paise), PAISE_PER_RUPEE)
    digits = str(rupees)
    if len(digits) > 3:
        head, tail = digits[:-3], digits[-3:]
        pairs = []
        while len(head) > 2:
            pairs.insert(0, head[-2:])
            head = head[:-2]
        digits = ",".join(([head] if head else []) + pairs) + "," + tail
    sign = "-" if paise < 0 else ""
    return f"{sign}₹{digits}.{paise_part:02d}"


def format_rupees_whole(paise: int) -> str:
    """Format paise as whole rupees, rounded half up, with Indian grouping.

    Used for headline figures and comparisons, where paise would only add
    noise: 4308000 -> "₹43,080", 34999 -> "₹350". Amounts the shop
    charges and records (prices, sale totals) keep format_rupees().
    """
    rupees = (Decimal(abs(paise)) / PAISE_PER_RUPEE).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    text = format_rupees(int(rupees) * PAISE_PER_RUPEE)[:-3]      # drop ".00"
    return f"-{text}" if paise < 0 else text
