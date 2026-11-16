"""Tests for services/googlebooks.py: the price suggestion when adding a book.

tests/fixtures/googlebooks_isbn_9780006550686.json is shaped like Google
Books' documented answer, but its prices are made up for the tests: on
2026-11-16 Google refused keyless requests (the shared daily limit was
used up), so no real answer could be recorded. The tests replay it
instead of calling the internet.
"""

import json
from pathlib import Path

import pytest

from services import ValidationError, googlebooks

FIXTURES = Path(__file__).parent / "fixtures"
KEY = "AIza" + "x" * 35                       # the shape of a Google API key; not a real one


def answer():
    return json.loads((FIXTURES / "googlebooks_isbn_9780006550686.json").read_text(encoding="utf-8"))


@pytest.fixture
def replay(monkeypatch):
    calls = []

    def fake_fetch(url):
        calls.append(url)
        return answer()

    monkeypatch.setattr(googlebooks, "fetch_json", fake_fetch)
    return calls


def with_sale(**sale_info):
    """The saved answer with only this edition, and its saleInfo replaced."""
    data = answer()
    item = data["items"][1]
    item["saleInfo"] = sale_info
    data["items"] = [item]
    return data


def test_price_comes_from_the_edition_with_this_isbn(replay):
    found = googlebooks.price_for_isbn("978-0-00-655068-6", KEY)
    # The other edition (₹999) is ignored; the list price is used, not the discounted one.
    assert found == googlebooks.PriceSuggestion(paise=39900, ebook=True)
    url = replay[0]
    assert url.startswith(googlebooks.API + "?")
    assert "q=isbn%3A9780006550686" in url and "country=IN" in url and f"key={KEY}" in url


def test_an_isbn_10_matches_too(replay):
    assert googlebooks.price_for_isbn("0006550681", KEY).paise == 39900


def test_no_matching_edition_means_no_suggestion(replay):
    assert googlebooks.price_for_isbn("9780143028574", KEY) is None


def test_bad_isbn_is_refused_before_asking(replay):
    with pytest.raises(ValidationError):
        googlebooks.price_for_isbn("12345", KEY)
    assert replay == []


@pytest.mark.parametrize("sale_info", [
    {"saleability": "NOT_FOR_SALE", "isEbook": False},                                  # print books, usually
    {"saleability": "FREE", "isEbook": True},
    {"saleability": "FOR_SALE", "listPrice": {"amount": 9.99, "currencyCode": "USD"}},  # not rupees
    {"saleability": "FOR_SALE", "listPrice": {"amount": 0, "currencyCode": "INR"}},
    {"saleability": "FOR_SALE", "listPrice": {"amount": -5, "currencyCode": "INR"}},
    {"saleability": "FOR_SALE", "listPrice": {"amount": True, "currencyCode": "INR"}},
    {"saleability": "FOR_SALE", "listPrice": {"amount": "399", "currencyCode": "INR"}},
    {"saleability": "FOR_SALE", "listPrice": {"amount": 10_000_000, "currencyCode": "INR"}},
    {"saleability": "FOR_SALE", "country": "US", "listPrice": {"amount": 399, "currencyCode": "INR"}},
    {"saleability": "FOR_SALE"},
])
def test_unusable_prices_give_no_suggestion(monkeypatch, sale_info):
    monkeypatch.setattr(googlebooks, "fetch_json", lambda url: with_sale(**sale_info))
    assert googlebooks.price_for_isbn("9780006550686", KEY) is None


def test_retail_price_is_used_when_there_is_no_list_price(monkeypatch):
    monkeypatch.setattr(googlebooks, "fetch_json", lambda url: with_sale(
        saleability="FOR_SALE", isEbook=False, retailPrice={"amount": 279.995, "currencyCode": "INR"}))
    assert googlebooks.price_for_isbn("9780006550686", KEY) == googlebooks.PriceSuggestion(28000, ebook=False)


@pytest.mark.parametrize("data", [{}, {"items": "x"}, {"items": [None, 3, {"saleInfo": []}]},
                                  {"items": [{"volumeInfo": {"industryIdentifiers": "x"}}]}])
def test_strange_answers_give_no_suggestion(monkeypatch, data):
    monkeypatch.setattr(googlebooks, "fetch_json", lambda url: data)
    assert googlebooks.price_for_isbn("9780006550686", KEY) is None


@pytest.mark.parametrize("key", [None, "", "abc", "AIza" + "x" * 34, "AIza" + "x" * 34 + "&", KEY + "x"])
def test_only_a_key_shaped_like_a_google_key_is_used(replay, key):
    assert not googlebooks.valid_key(key)
    with pytest.raises(ValueError):
        googlebooks.price_for_isbn("9780006550686", key)
    assert replay == []


def test_only_google_books_is_fetched():
    for url in ("https://example.com/x", "http://www.googleapis.com/books/v1/volumes?q=x",
                "https://www.googleapis.com.evil.example/books/v1/volumes?q=x",
                "https://www.googleapis.com/drive/v3/files"):
        with pytest.raises(ValueError):
            googlebooks.fetch_json(url)


def test_errors_never_show_the_key(monkeypatch):
    def refuse(request, timeout):
        raise googlebooks.urllib.error.HTTPError(str(request), 403, "Forbidden", {}, None)

    monkeypatch.setattr(googlebooks.urllib.request, "urlopen", refuse)
    with pytest.raises(googlebooks.GoogleBooksError) as problem:
        googlebooks.price_for_isbn("9780006550686", KEY)
    assert KEY not in str(problem.value) and "googleapis" not in str(problem.value)
    assert problem.value.__cause__ is None and problem.value.__suppress_context__


def test_oversized_answers_are_refused(monkeypatch):
    class Huge:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self, limit):
            return b'{"x": "' + b"a" * (googlebooks.MAX_RESPONSE_BYTES + 10) + b'"}'

    monkeypatch.setattr(googlebooks.urllib.request, "urlopen", lambda request, timeout: Huge())
    with pytest.raises(googlebooks.GoogleBooksError):
        googlebooks.fetch_json(googlebooks.API + "?q=isbn:9780006550686")


def test_the_key_is_read_from_secrets_only_when_it_looks_right(monkeypatch):
    import streamlit as st
    from ui import session

    for secrets, expected in (
        ({}, None),
        ({"google_books": {}}, None),
        ({"google_books": {"api_key": "not a key"}}, None),
        ({"google_books": {"api_key": f"  {KEY}\n"}}, KEY),
    ):
        monkeypatch.setattr(st, "secrets", secrets)
        assert session.google_books_key() == expected
