"""Security checks that don't need a browser: escaping, limits on repeated
attempts, password changes, Open Library answers, input sizes and the
server settings."""

import io
import re
import tomllib
from datetime import datetime
from pathlib import Path

import pytest

from database import connect_accounts
from services import ValidationError, accounts, openlibrary
from services.books import BookInput, add_book
from services.inventory import correct_stock
from services.limits import AttemptLimiter
from services.sales import cancel_sale
from ui.components import plain

PROJECT = Path(__file__).parent.parent
NOW = datetime(2026, 11, 10, 10, 0, 0)
PASSWORD = "correct horse battery"


@pytest.fixture
def acc(tmp_path):
    with connect_accounts(tmp_path / "accounts.db") as conn:
        yield conn


def unescaped(markdown: str) -> str:
    """What a person reads: no backslashes, no invisible word joiners."""
    return re.sub(r"\\(.)", r"\1", markdown).replace("⁠", "")


# ---------- Text shown as Markdown ----------

@pytest.mark.parametrize("text", [
    "$5 *Deals* for __everyone__",                     # maths and emphasis
    "![tracker](https://example.com/pixel.png)",       # a picture from another website
    "[click me](javascript:alert(1))",                 # a link
    ":red[owner] :material/lock:",                     # Streamlit colours and icons
    "# Heading <b>bold</b> | table | `code` ~strike~",
    "1. not a list",
])
def test_plain_shows_text_exactly_and_hides_markdown(text):
    escaped = plain(text)
    assert unescaped(escaped) == text                  # reads exactly as typed
    # Every character Markdown could act on has a backslash before it.
    assert not re.search(r"(?<!\\)[*_\[\]()!$:#<>|`~]", escaped)


def test_plain_stops_bare_web_addresses_becoming_links():
    escaped = plain("Visit https://example.com or www.example.com")
    assert "https⁠\\://" in escaped and "www⁠\\." in escaped
    assert unescaped(escaped) == "Visit https://example.com or www.example.com"


def test_plain_turns_line_breaks_into_spaces():
    assert plain("Title\n# not a heading\n- not a list") == r"Title \# not a heading \- not a list"


# ---------- Limits on repeated attempts ----------

def test_limiter_blocks_after_the_limit_and_forgets_after_the_window():
    limiter = AttemptLimiter(limit=3, window_seconds=60)
    for second in (0, 1, 2):
        assert not limiter.blocked("address", now=second)
        limiter.record("address", now=second)
    assert limiter.blocked("address", now=3)
    assert not limiter.blocked("another address", now=3)   # each address counted separately
    assert not limiter.blocked("address", now=61)           # the first attempt has expired


def test_limiter_clear():
    limiter = AttemptLimiter(limit=1, window_seconds=60)
    limiter.record("x", now=0)
    limiter.clear("x")
    assert not limiter.blocked("x", now=1)


# ---------- Passwords ----------

def test_wrong_current_password_counts_towards_the_lockout(acc):
    user = accounts.create_user(acc, "priya", "Priya", PASSWORD, now=NOW)
    for _ in range(accounts.MAX_FAILED_LOGINS - 1):
        with pytest.raises(ValidationError) as refused:
            accounts.change_password(acc, user, "a wrong guess", "a brand new passphrase", now=NOW)
        assert refused.value.errors == ["Your current password is incorrect."]
    with pytest.raises(ValidationError) as refused:
        accounts.change_password(acc, user, "a wrong guess", "a brand new passphrase", now=NOW)
    assert refused.value.errors == ["Too many wrong passwords. Try again after 10:15."]
    # Locked: now even the right password can't sign in or change it.
    with pytest.raises(accounts.SignInError):
        accounts.authenticate(acc, "priya", PASSWORD, now=NOW)
    with pytest.raises(ValidationError):
        accounts.change_password(acc, user, PASSWORD, "a brand new passphrase", now=NOW)


def test_new_password_must_differ_from_the_current_one(acc):
    user = accounts.create_user(acc, "priya", "Priya", PASSWORD, now=NOW)
    with pytest.raises(ValidationError) as refused:
        accounts.change_password(acc, user, PASSWORD, PASSWORD, now=NOW)
    assert refused.value.errors == ["Choose a new password, different from the current one."]


def test_changing_the_password_changes_the_credential_stamp(acc):
    user = accounts.create_user(acc, "priya", "Priya", PASSWORD, now=NOW)
    before = accounts.credential_stamp(acc, user)
    assert before and PASSWORD not in before
    accounts.change_password(acc, user, PASSWORD, "a brand new passphrase", now=NOW)
    assert accounts.credential_stamp(acc, user) != before


def test_google_accounts_have_no_credential_stamp(acc):
    user = accounts.google_sign_in(acc, "google-subject-1", "p@example.com", "Priya", now=NOW)
    assert accounts.credential_stamp(acc, user) is None


def test_enormous_passwords_are_never_hashed(acc, monkeypatch):
    accounts.create_user(acc, "priya", "Priya", PASSWORD, now=NOW)
    seen = []
    real_verify = accounts.verify_password
    monkeypatch.setattr(accounts, "verify_password", lambda pw, stored: seen.append(len(pw)) or real_verify(pw, stored))
    with pytest.raises(accounts.SignInError):
        accounts.authenticate(acc, "priya", "x" * 1_000_000, now=NOW)
    assert seen == [accounts.MAX_PASSWORD_LENGTH + 1]


def test_long_google_names_are_shortened(acc):
    user = accounts.google_sign_in(acc, "google-subject-2", None, "N" * 500, now=NOW)
    assert len(accounts.get_user(acc, user)["display_name"]) == accounts.MAX_NAME_LENGTH


def test_short_cookie_secret_keeps_google_sign_in_off(monkeypatch):
    import streamlit as st
    from ui import session
    google = {"client_id": "x", "client_secret": "y", "server_metadata_url": "z"}
    monkeypatch.setattr(st, "secrets", {"auth": {"redirect_uri": "r", "cookie_secret": "short", "google": google}})
    assert not session.google_configured()
    monkeypatch.setattr(st, "secrets", {"auth": {"redirect_uri": "r", "cookie_secret": "s" * 32, "google": google}})
    assert session.google_configured()


# ---------- Input sizes ----------

def test_overlong_book_details_are_refused(empty_db):
    with pytest.raises(ValidationError) as refused:
        add_book(empty_db, BookInput(title="T" * 301, author="A" * 201, genre="G" * 61, selling_price=100))
    assert refused.value.errors == [
        "Title is at most 300 characters.",
        "Author is at most 200 characters.",
        "Genre is at most 60 characters.",
    ]


def test_overlong_cancellation_reason_is_refused(sample_db):
    with pytest.raises(ValidationError) as refused:
        cancel_sale(sample_db, 1, "r" * 301)
    assert refused.value.errors == ["Keep the reason to 300 characters or fewer."]


def test_overlong_stock_note_is_refused(sample_db):
    stock = sample_db.execute("SELECT stock_quantity FROM books WHERE book_id = 1").fetchone()[0]
    with pytest.raises(ValidationError) as refused:
        correct_stock(sample_db, 1, stock, stock + 1, "other", "n" * 301)
    assert refused.value.errors == ["Keep the note to 300 characters or fewer."]


# ---------- Open Library answers ----------

def test_only_open_library_is_ever_fetched():
    for url in ("https://example.com/x", "file:///etc/passwd", "http://openlibrary.org/x",
                "https://openlibrary.org.evil.example/x"):
        with pytest.raises(ValueError):
            openlibrary.fetch_json(url)


def test_oversized_answers_are_refused(monkeypatch):
    class Huge(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *problem):
            return False

    big = b'{"x": "' + b"a" * (openlibrary.MAX_RESPONSE_BYTES + 10) + b'"}'
    monkeypatch.setattr(openlibrary.urllib.request, "urlopen", lambda request, timeout: Huge(big))
    with pytest.raises(openlibrary.OpenLibraryError):
        openlibrary.fetch_json(openlibrary.API + "/search.json?q=x")


def test_strange_search_results_are_ignored(monkeypatch):
    answer = {"docs": [
        {"title": "Good", "key": "/works/OL1W", "cover_i": 7, "author_name": ["A"]},
        {"title": "Bad key", "key": "javascript:alert(1)"},
        {"title": "Bad key 2", "key": "/works/OL1W) [x](https://evil.example"},
        {"title": ["not", "text"], "key": "/works/OL2W"},
        {"title": "Odd cover", "key": "/works/OL3W", "cover_i": "12", "first_publish_year": True},
        "not even a record",
    ]}
    monkeypatch.setattr(openlibrary, "fetch_json", lambda url: answer)
    found = openlibrary.search("anything")
    assert [(book.title, book.openlibrary_key, book.cover_id, book.first_published) for book in found] == [
        ("Good", "/works/OL1W", 7, None),
        ("Odd cover", "/works/OL3W", None, None),
    ]


def test_overlong_searches_are_refused():
    with pytest.raises(ValidationError):
        openlibrary.search("x" * (openlibrary.MAX_SEARCH_LENGTH + 1))


# ---------- Server settings ----------

def test_server_settings_stay_safe():
    config = tomllib.loads((PROJECT / ".streamlit" / "config.toml").read_text(encoding="utf-8"))
    server = config["server"]
    assert server["address"] == "localhost"
    assert server["enableXsrfProtection"] is True and server["enableCORS"] is True
    assert server["enableStaticServing"] is False
    assert config["client"]["showErrorDetails"] == "none"     # no tracebacks in the browser


def test_secrets_file_is_never_committed():
    ignored = (PROJECT / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert ".streamlit/secrets.toml" in ignored
