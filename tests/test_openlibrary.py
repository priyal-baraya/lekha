"""Tests for services/openlibrary.py and the book-details migration.

The saved files in tests/fixtures/ are REAL Open Library responses,
recorded once on 2026-11-08. The tests replay them instead of calling
the internet, so they are fast and also work on GitHub's test machine.
"""

import json
import sqlite3
import urllib.parse
from pathlib import Path

import pytest

from database import apply_migrations, create_schema, get_connection, schema_version, SCHEMA_PATH
from services import ValidationError
from services import openlibrary
from services.books import BookInput, add_book, get_book, update_book

FIXTURES = Path(__file__).parent / "fixtures"


def load(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.fixture
def replay(monkeypatch):
    """Answer Open Library requests from the saved responses."""
    calls = []

    def fake_fetch(url):
        calls.append(url)
        url = urllib.parse.unquote(url)     # ISBN%3A... -> ISBN:...
        if "ISBN:9780006550686" in url:
            return load("openlibrary_isbn_9780006550686.json")
        if "ISBN:9790000000001" in url:
            return load("openlibrary_isbn_not_found.json")["response"]
        if "search.json" in url:
            return load("openlibrary_search_god_of_small_things.json")
        raise AssertionError(f"Unexpected request: {url}")

    monkeypatch.setattr(openlibrary, "fetch_json", fake_fetch)
    return calls


# ---------- ISBN lookup ----------

def test_isbn_lookup_returns_the_exact_edition(replay):
    book = openlibrary.lookup_isbn("978-0-00-655068-6")      # hyphens are fine
    assert book.title == "The God of Small Things"
    assert book.author == "Arundhati Roy"
    assert book.isbn == "9780006550686"
    assert book.publisher == "Flamingo"
    assert book.published_year == 1998                       # this edition, not the 1997 original
    assert book.cover_id == 10585942
    assert book.cover_url() == "https://covers.openlibrary.org/b/id/10585942-M.jpg"
    assert book.openlibrary_key == "/books/OL31903694M"
    assert "Literary Fiction" in book.subjects


def test_isbn_lookup_asks_for_one_edition_by_isbn(replay):
    openlibrary.lookup_isbn("9780006550686")
    assert replay == ["https://openlibrary.org/api/books?bibkeys=ISBN%3A9780006550686&format=json&jscmd=data"]


def test_unknown_isbn_returns_none(replay):
    assert openlibrary.lookup_isbn("9790000000001") is None


@pytest.mark.parametrize("bad", ["12345", "abc", "", "978000655068X"])
def test_badly_shaped_isbn_is_refused_without_calling_open_library(replay, bad):
    with pytest.raises(ValidationError):
        openlibrary.lookup_isbn(bad)
    assert replay == []


# ---------- Search ----------

def test_search_returns_works_with_author_and_year(replay):
    results = openlibrary.search("the god of small things")
    assert len(results) == 5
    first = results[0]
    assert (first.title, first.author, first.first_published) == ("The God of Small Things", "Arundhati Roy", 1997)
    assert first.openlibrary_key == "/works/OL1052133W"
    assert first.isbn is None and first.publisher is None and first.published_year is None   # work, not edition
    # Real data includes study guides and at least one odd record, which
    # is why results show author and year and the form is checked by a person.
    assert "Julie Mullaney" in [result.author for result in results]


def test_search_needs_two_letters(replay):
    with pytest.raises(ValidationError):
        openlibrary.search(" a ")
    assert replay == []


def test_result_without_cover_has_no_cover_url(replay):
    no_cover = [r for r in openlibrary.search("the god of small things") if r.cover_id is None]
    assert no_cover and no_cover[0].cover_url() is None


# ---------- Errors ----------

def test_network_failure_gives_a_plain_message(monkeypatch):
    import urllib.error

    def unreachable(*args, **kwargs):
        raise urllib.error.URLError("no network")

    monkeypatch.setattr(openlibrary.urllib.request, "urlopen", unreachable)
    with pytest.raises(openlibrary.OpenLibraryError) as caught:
        openlibrary.lookup_isbn("9780006550686")
    assert "Couldn't reach Open Library" in str(caught.value)


def test_busy_server_gives_a_plain_message(monkeypatch):
    import urllib.error

    def busy(*args, **kwargs):
        raise urllib.error.HTTPError("url", 429, "Too Many Requests", {}, None)

    monkeypatch.setattr(openlibrary.urllib.request, "urlopen", busy)
    with pytest.raises(openlibrary.OpenLibraryError) as caught:
        openlibrary.search("anything")
    assert "busy" in str(caught.value)


# ---------- Genre suggestions ----------

@pytest.mark.parametrize(
    "subjects, genre",
    [
        (["Literary Fiction", "Women's Fiction", "dalit"], "Fiction"),
        (["Juvenile fiction", "Animals"], "Children"),          # Children wins over Fiction
        (["Detective and mystery stories", "Fiction"], "Mystery"),
        (["Historical fiction"], "Fiction"),                    # "historical" isn't "history"
        (["India -- History -- 1947-"], "History"),
        (["Indian Cooking", "Recipes"], "Cookery"),
        (["Poetry", "English poetry"], "Poetry"),
        (["award:man_booker_prize=1997", "Twins"], None),
        ([], None),
    ],
)
def test_suggest_genre(subjects, genre):
    assert openlibrary.suggest_genre(subjects) == genre


def test_real_isbn_record_suggests_fiction(replay):
    assert openlibrary.suggest_genre(openlibrary.lookup_isbn("9780006550686").subjects) == "Fiction"


# ---------- Saving a real book ----------

def test_adding_a_found_book_saves_its_details(empty_db, replay):
    found = openlibrary.lookup_isbn("9780006550686")
    book_id = add_book(empty_db, BookInput(
        title=found.title, author=found.author, genre="Fiction", isbn=found.isbn,
        selling_price=399, stock_quantity=3, reorder_level=1,
        publisher=found.publisher, published_year=found.published_year,
        cover_id=found.cover_id, openlibrary_key=found.openlibrary_key,
    ))
    saved = get_book(empty_db, book_id)
    assert (saved["publisher"], saved["published_year"], saved["cover_id"], saved["openlibrary_key"]) == (
        "Flamingo", 1998, 10585942, "/books/OL31903694M")


def test_editing_a_book_keeps_its_details(empty_db, replay):
    found = openlibrary.lookup_isbn("9780006550686")
    book_id = add_book(empty_db, BookInput(
        title=found.title, author=found.author, genre="Fiction", isbn=found.isbn, selling_price=399,
        publisher=found.publisher, published_year=found.published_year,
        cover_id=found.cover_id, openlibrary_key=found.openlibrary_key,
    ))
    update_book(empty_db, book_id, BookInput(title=found.title, author=found.author, genre="Fiction",
                                             isbn=found.isbn, selling_price=425))
    saved = get_book(empty_db, book_id)
    assert saved["selling_price_paise"] == 42500
    assert saved["cover_id"] == 10585942 and saved["publisher"] == "Flamingo"


@pytest.mark.parametrize(
    "details, message",
    [
        ({"published_year": 1200}, "Published year must be a year between 1450 and 2100."),
        ({"cover_id": -4}, "The cover reference from Open Library isn't valid."),
        ({"openlibrary_key": "/authors/OL1A"}, "The Open Library record reference isn't valid."),
    ],
)
def test_bad_details_are_refused(empty_db, details, message):
    with pytest.raises(ValidationError) as caught:
        add_book(empty_db, BookInput(title="A", author="B", genre="Fiction", selling_price=100, **details))
    assert message in caught.value.errors


def test_database_refuses_bad_details_too(empty_db):
    with pytest.raises(sqlite3.IntegrityError):
        empty_db.execute(
            "INSERT INTO books (title, author, genre, selling_price_paise, openlibrary_key) "
            "VALUES ('A', 'B', 'Fiction', 100, 'not a key')"
        )


# ---------- Migration ----------

LATEST_VERSION = 2   # sql/migrations/001 and 002


def test_new_database_is_at_the_latest_version(empty_db):
    assert schema_version(empty_db) == LATEST_VERSION
    columns = [row["name"] for row in empty_db.execute("PRAGMA table_info(books)")]
    assert columns[-4:] == ["publisher", "published_year", "cover_id", "openlibrary_key"]


def test_old_database_is_upgraded_without_losing_books():
    # A database made with the Phase 7 schema (version 0) with one book.
    conn = get_connection(":memory:")
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    conn.execute("INSERT INTO books (title, author, genre, selling_price_paise) VALUES ('Old', 'Book', 'Fiction', 100)")
    conn.commit()
    assert schema_version(conn) == 0
    assert apply_migrations(conn) == [1, 2]
    assert schema_version(conn) == LATEST_VERSION
    row = conn.execute("SELECT title, cover_id FROM books").fetchone()
    assert (row["title"], row["cover_id"]) == ("Old", None)
    assert apply_migrations(conn) == []          # running again changes nothing
    conn.close()


def test_create_schema_is_safe_to_run_again(empty_db):
    create_schema(empty_db)
    assert schema_version(empty_db) == LATEST_VERSION
