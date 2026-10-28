from decimal import Decimal

import pytest

from services.money import format_rupees, paise_to_rupees, rupees_to_paise


@pytest.mark.parametrize(
    "rupees, paise",
    [
        (349.99, 34999),
        (0.1, 10),
        (19.99, 1999),       # plain float maths would give 1998
        (4.35, 435),         # plain float maths would give 434
        (0.57, 57),          # plain float maths would give 56
        (300, 30000),
        ("299.50", 29950),
        (Decimal("0.01"), 1),
        (0, 0),
    ],
)
def test_rupees_to_paise_is_exact(rupees, paise):
    assert rupees_to_paise(rupees) == paise


def test_plain_float_multiplication_would_be_wrong():
    # Shows why Decimal is needed: 19.99 * 100 is 1998.9999999999998 as a
    # float, so int() gives 1998 and a paisa disappears.
    assert int(19.99 * 100) == 1998
    assert int(4.35 * 100) == 434
    assert rupees_to_paise(19.99) == 1999
    assert rupees_to_paise(4.35) == 435


@pytest.mark.parametrize("bad", [-1, "-0.01", 12.345, "abc", "", "nan", "inf"])
def test_rupees_to_paise_rejects_bad_amounts(bad):
    with pytest.raises(ValueError):
        rupees_to_paise(bad)


def test_paise_to_rupees():
    assert paise_to_rupees(34999) == Decimal("349.99")
    assert paise_to_rupees(5) == Decimal("0.05")


@pytest.mark.parametrize(
    "paise, text",
    [
        (0, "₹0.00"),
        (5, "₹0.05"),
        (34999, "₹349.99"),
        (100000, "₹1,000.00"),
        (1114400, "₹11,144.00"),
        (11144400, "₹1,11,444.00"),     # one lakh: Indian grouping
        (1234567800, "₹1,23,45,678.00"),  # one crore
        (-34900, "-₹349.00"),
    ],
)
def test_format_rupees_uses_indian_grouping(paise, text):
    assert format_rupees(paise) == text
