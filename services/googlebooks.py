"""A selling-price suggestion from Google Books (https://books.google.com).

When a book is looked up by ISBN, Lekha asks Google Books what that exact
edition sells for in India and fills in the selling price with it. The
person adding the book checks it and changes it before saving.

Google's price is what Google Play charges, which is usually the ebook,
so the form says so. Print books often have no price at all; then the
field stays empty, as before.

Google Books needs an API key. Without one, every app in the world shares
one small daily limit, which is usually used up. The key belongs in
.streamlit/secrets.toml (or the host's secret settings):

    [google_books]
    api_key = "AIza..."

With no key, Lekha never asks Google, and nothing else changes.
"""

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from services import ValidationError
from services.books import clean_isbn

API = "https://www.googleapis.com/books/v1/volumes"
TIMEOUT_SECONDS = 10
MAX_RESPONSE_BYTES = 2_000_000
# Google API keys are "AIza" and 35 more letters, digits, - or _. Anything
# else is refused, so a mistyped key can't change the address asked.
KEY_PATTERN = re.compile(r"AIza[0-9A-Za-z_\-]{35}")
MAX_PRICE_RUPEES = 100_000       # far above any book; a bigger number is a mistake


class GoogleBooksError(Exception):
    """Google Books couldn't be reached or sent something unusable.
    The message never includes the address asked, which holds the key."""


@dataclass(frozen=True)
class PriceSuggestion:
    paise: int
    ebook: bool              # Google says this price is for the ebook


def valid_key(key) -> bool:
    return isinstance(key, str) and KEY_PATTERN.fullmatch(key) is not None


def fetch_json(url: str) -> dict:
    """GET a Google Books address and decode its JSON. The tests replace
    this function, so they never need the internet."""
    if not url.startswith(API + "?"):
        raise ValueError(f"Lekha only fetches from {API}")
    try:
        # Reviewed for bandit: the scheme and host are fixed to https://www.googleapis.com above.
        with urllib.request.urlopen(url, timeout=TIMEOUT_SECONDS) as response:  # nosec B310
            body = response.read(MAX_RESPONSE_BYTES + 1)
    except urllib.error.HTTPError as problem:
        raise GoogleBooksError(f"Google Books answered with an error ({problem.code}).") from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise GoogleBooksError("Couldn't reach Google Books.") from None
    if len(body) > MAX_RESPONSE_BYTES:
        raise GoogleBooksError("Google Books sent something Lekha couldn't read.")
    try:
        data = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise GoogleBooksError("Google Books sent something Lekha couldn't read.") from None
    if not isinstance(data, dict):
        raise GoogleBooksError("Google Books sent something Lekha couldn't read.")
    return data


def _isbns(item: dict) -> set[str]:
    info = item.get("volumeInfo")
    identifiers = info.get("industryIdentifiers") if isinstance(info, dict) else None
    if not isinstance(identifiers, list):
        return set()
    return {clean_isbn(entry["identifier"]) for entry in identifiers
            if isinstance(entry, dict) and isinstance(entry.get("identifier"), str)}


def _rupees(price) -> Decimal | None:
    if not isinstance(price, dict) or price.get("currencyCode") != "INR":
        return None
    amount = price.get("amount")
    if isinstance(amount, bool) or not isinstance(amount, (int, float)):
        return None
    amount = Decimal(str(amount))
    return amount if 0 < amount <= MAX_PRICE_RUPEES else None


def _suggestion(item: dict) -> PriceSuggestion | None:
    sale = item.get("saleInfo")
    if not isinstance(sale, dict) or sale.get("saleability") != "FOR_SALE":
        return None
    if sale.get("country", "IN") != "IN":
        return None
    # The list price is the publisher's price (closest to the printed MRP);
    # the retail price is Google's, often discounted.
    rupees = _rupees(sale.get("listPrice")) or _rupees(sale.get("retailPrice"))
    if rupees is None:
        return None
    paise = int((rupees * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    return PriceSuggestion(paise=paise, ebook=sale.get("isEbook") is True)


def price_for_isbn(raw_isbn: str, key: str) -> PriceSuggestion | None:
    """What Google Books sells this exact edition for in India, or None."""
    if not valid_key(key):
        raise ValueError("Not a Google API key.")
    isbn = clean_isbn(raw_isbn)
    valid = isbn is not None and (
        (len(isbn) == 13 and isbn.isdigit())
        or (len(isbn) == 10 and isbn[:9].isdigit() and (isbn[9].isdigit() or isbn[9] == "X"))
    )
    if not valid:
        raise ValidationError(["An ISBN is 10 or 13 digits (an ISBN-10 may end in X)."])
    query = urllib.parse.urlencode({"q": f"isbn:{isbn}", "country": "IN", "key": key})
    items = fetch_json(f"{API}?{query}").get("items")
    for item in items if isinstance(items, list) else []:
        # A search by ISBN can also return other editions: only this one counts.
        if isinstance(item, dict) and isbn in _isbns(item):
            return _suggestion(item)
    return None
