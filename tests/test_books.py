"""Tests for services/books.py, run against the fictional sample data."""

import pytest

from services import ValidationError
from services.books import (
    BookInput,
    add_book,
    clean_isbn,
    count_books,
    find_same_title_and_author,
    get_book,
    list_genres,
    search_books,
    update_book,
)


def ids(rows):
    return [row["book_id"] for row in rows]


def new_book(**overrides) -> BookInput:
    values = dict(
        title="Paper Boats",
        author="Ira Nair",
        genre="Poetry",
        isbn="0000000000099",
        selling_price=299.0,
        cost_price=180.0,
        stock_quantity=4,
        reorder_level=2,
    )
    values.update(overrides)
    return BookInput(**values)


# ---------- Searching ----------

def test_empty_search_returns_every_book(sample_db):
    assert len(search_books(sample_db)) == 12


def test_search_matches_part_of_a_title_ignoring_case(sample_db):
    assert ids(search_books(sample_db, "MANGOES")) == [9]


def test_search_matches_author(sample_db):
    # Sorted by title: "Murder on the Night Mail" (8) before "The Lighthouse at Kovalam" (3)
    assert ids(search_books(sample_db, "dsouza")) == [8, 3]


def test_search_and_genre_combine(sample_db):
    assert ids(search_books(sample_db, "the", genre="Mystery")) == [8, 3]


def test_genre_filter_alone(sample_db):
    # "Ten Thousand Mangoes" (9) sorts before "The Clockmaker's Cat" (7):
    # the second letters are "e" and "h", and "e" comes first.
    assert ids(search_books(sample_db, genre="Children")) == [9, 7]


def test_search_with_no_match_returns_empty_list(sample_db):
    assert search_books(sample_db, "zzz") == []


def test_wildcard_characters_are_matched_literally(sample_db):
    # Without escaping, "%" would match every title.
    assert search_books(sample_db, "%") == []
    assert search_books(sample_db, "_") == []


def test_sql_in_search_box_is_treated_as_text(sample_db):
    assert search_books(sample_db, "'; DROP TABLE books; --") == []
    assert count_books(sample_db) == 12


def test_sort_by_stock_lowest_first(sample_db):
    assert ids(search_books(sample_db, sort="stock_low"))[:3] == [5, 9, 2]


def test_sort_by_price(sample_db):
    assert ids(search_books(sample_db, sort="price_high"))[0] == 10  # Rs 799
    assert ids(search_books(sample_db, sort="price_low"))[0] == 11   # Rs 225


def test_unknown_sort_is_refused(sample_db):
    with pytest.raises(ValueError):
        search_books(sample_db, sort="title; DROP TABLE books")


def test_stock_status_words(sample_db):
    status = {row["book_id"]: row["stock_status"] for row in search_books(sample_db)}
    assert status[5] == "Out of stock"
    assert status[2] == "Low stock"   # exactly at its reorder level
    assert status[9] == "Low stock"
    assert status[1] == "In stock"


def test_list_genres(sample_db):
    assert list_genres(sample_db) == ["Children", "Cookery", "Fiction", "History", "Mystery", "Poetry"]


# ---------- ISBN tidying ----------

@pytest.mark.parametrize(
    "raw, cleaned",
    [("978-0-00-000000-1", "9780000000001"), (" 0 00 000 000 x ", "000000000X"), ("", None), (None, None)],
)
def test_clean_isbn(raw, cleaned):
    assert clean_isbn(raw) == cleaned


# ---------- Adding ----------

def test_add_valid_book(sample_db):
    book_id = add_book(sample_db, new_book())
    saved = get_book(sample_db, book_id)
    assert saved["title"] == "Paper Boats"
    assert saved["selling_price_paise"] == 29900
    assert saved["cost_price_paise"] == 18000
    assert saved["stock_quantity"] == 4
    assert count_books(sample_db) == 13


def test_add_tidies_spaces_and_reuses_genre_spelling(sample_db):
    book_id = add_book(sample_db, new_book(title="  Paper   Boats ", genre="poetry"))
    saved = get_book(sample_db, book_id)
    assert saved["title"] == "Paper Boats"
    assert saved["genre"] == "Poetry"
    assert list_genres(sample_db).count("Poetry") == 1


def test_add_new_genre(sample_db):
    add_book(sample_db, new_book(genre="Travel"))
    assert "Travel" in list_genres(sample_db)


def test_add_without_isbn_or_cost(sample_db):
    book_id = add_book(sample_db, new_book(isbn="", cost_price=None))
    saved = get_book(sample_db, book_id)
    assert saved["isbn"] is None
    assert saved["cost_price_paise"] is None


def test_add_reports_every_problem_at_once(sample_db):
    with pytest.raises(ValidationError) as caught:
        add_book(sample_db, new_book(title=" ", author="", selling_price=None, stock_quantity=-1))
    errors = caught.value.errors
    assert "Title is required." in errors
    assert "Author is required." in errors
    assert "Selling price is required." in errors
    assert "Opening stock can't be negative." in errors
    assert count_books(sample_db) == 12  # nothing saved


def test_add_duplicate_isbn_gives_friendly_message(sample_db):
    with pytest.raises(ValidationError) as caught:
        add_book(sample_db, new_book(isbn="0000000000001"))
    assert caught.value.errors == ['ISBN 0000000000001 already belongs to "The Monsoon Ledger".']


@pytest.mark.parametrize("bad_isbn", ["12345", "000000000000A", "00000000XX"])
def test_add_rejects_badly_shaped_isbn(sample_db, bad_isbn):
    with pytest.raises(ValidationError):
        add_book(sample_db, new_book(isbn=bad_isbn))


def test_add_rejects_price_with_fractions_of_paise(sample_db):
    with pytest.raises(ValidationError) as caught:
        add_book(sample_db, new_book(selling_price=299.999))
    assert caught.value.errors == ["Selling price: Use at most two decimal places (whole paise)."]


def test_same_title_and_author_is_found_for_warning(sample_db):
    matches = find_same_title_and_author(sample_db, " the monsoon ledger ", "ASHA VARKEY")
    assert ids(matches) == [1]
    assert find_same_title_and_author(sample_db, "The Monsoon Ledger", "Asha Varkey", exclude_book_id=1) == []


# ---------- Editing ----------

def test_edit_changes_details_but_not_stock(sample_db):
    update_book(sample_db, 1, new_book(title="The Monsoon Ledger", author="Asha Varkey",
                                       genre="Fiction", isbn="0000000000001",
                                       selling_price=425, stock_quantity=999))
    saved = get_book(sample_db, 1)
    assert saved["selling_price_paise"] == 42500
    assert saved["stock_quantity"] == 8  # unchanged: stock changes go through inventory


def test_edit_keeps_own_isbn_without_duplicate_error(sample_db):
    update_book(sample_db, 1, new_book(title="The Monsoon Ledger", isbn="0000000000001"))


def test_edit_to_another_books_isbn_is_refused(sample_db):
    with pytest.raises(ValidationError):
        update_book(sample_db, 1, new_book(isbn="0000000000002"))


def test_price_change_leaves_past_sales_alone(sample_db):
    before = sample_db.execute("SELECT SUM(quantity * unit_price_paise) FROM sale_items").fetchone()[0]
    update_book(sample_db, 1, new_book(title="The Monsoon Ledger", isbn="0000000000001", selling_price=999))
    after = sample_db.execute("SELECT SUM(quantity * unit_price_paise) FROM sale_items").fetchone()[0]
    assert before == after


def test_edit_missing_book(sample_db):
    with pytest.raises(ValidationError) as caught:
        update_book(sample_db, 999, new_book(isbn=None))
    assert caught.value.errors == ["This book no longer exists."]


def test_search_matches_an_isbn_with_or_without_dashes(sample_db):
    assert ids(search_books(sample_db, "0000000000003")) == [3]
    assert ids(search_books(sample_db, "000-000-000-0003")) == [3]


def test_a_short_number_is_not_treated_as_an_isbn(sample_db):
    assert search_books(sample_db, "000") == []          # would match every stand-in ISBN
