"""Looking up real books on Open Library (https://openlibrary.org).

Open Library is a free, open catalogue of books run by the Internet
Archive. It needs no account or key. Its data is edited by volunteers,
so it is usually right but not always: Lekha only ever PRE-FILLS the add
form with it, and the person adding the book checks it before saving.

Two kinds of request:
  lookup_isbn(isbn)  -> one exact edition (title, author, this edition's
                        publisher and year, its cover)
  search(text)       -> works matching a title or author (a "work" is
                        the book in general, across all its editions)

Prices, stock and sales never come from here: only the shop knows those.
"""

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field

from services import ValidationError
from services.books import clean_isbn

API = "https://openlibrary.org"
COVERS = "https://covers.openlibrary.org/b/id/{cover_id}-{size}.jpg"
# Open Library asks apps to say who they are, so they can get in touch
# if something goes wrong.
USER_AGENT = "Lekha/1.0 (independent bookstore inventory; https://github.com/priyal-baraya/lekha)"
TIMEOUT_SECONDS = 10
# A book's answer is a few kilobytes; anything far bigger is refused
# rather than read into memory.
MAX_RESPONSE_BYTES = 2_000_000
MAX_SEARCH_LENGTH = 200
# What Open Library's record references look like. Anything else is
# ignored, so a strange answer can never become a strange link.
EDITION_KEY = re.compile(r"/books/OL\d+M")
WORK_KEY = re.compile(r"/works/OL\d+W")

# Shop genres suggested from Open Library's subject tags, checked in this
# order, so "Juvenile fiction" suggests Children rather than Fiction, and
# "Detective and mystery stories" suggests Mystery. Only a suggestion:
# the person adding the book chooses the genre.
GENRE_RULES = [
    ("Children", ("juvenile", "children", "picture book")),
    ("Poetry", ("poetry", "poems")),
    ("Mystery", ("mystery", "detective", "crime", "thriller", "suspense")),
    ("Cookery", ("cooking", "cookery", "recipes", "cookbook")),
    ("History", ("history",)),
    ("Fiction", ("fiction", "novel")),
]


class OpenLibraryError(Exception):
    """Open Library couldn't be reached or sent something unusable."""


@dataclass(frozen=True)
class FoundBook:
    """A book as Open Library describes it, before anyone adds it."""

    title: str
    author: str                      # names joined with ", "; may be empty
    openlibrary_key: str             # /books/OL...M (edition) or /works/OL...W (work)
    isbn: str | None = None          # only from an ISBN lookup
    publisher: str | None = None     # only from an ISBN lookup (edition fact)
    published_year: int | None = None    # only from an ISBN lookup (edition fact)
    first_published: int | None = None   # from a search (work fact, shown, not saved)
    cover_id: int | None = None
    subjects: tuple[str, ...] = field(default_factory=tuple)

    def cover_url(self, size: str = "M") -> str | None:
        return cover_url(self.cover_id, size)

    @property
    def page_url(self) -> str:
        return API + self.openlibrary_key


def cover_url(cover_id: int | None, size: str = "M") -> str | None:
    """Address of a cover picture: size S (small), M (medium) or L (large)."""
    return COVERS.format(cover_id=cover_id, size=size) if cover_id else None


def fetch_json(url: str) -> dict:
    """GET a URL and decode its JSON. The tests replace this function with
    one that returns saved real responses, so they never need the internet.

    Only Open Library's own address is ever fetched: the URLs are built in
    this file, and the check below makes sure of it."""
    if not url.startswith(API + "/"):
        raise ValueError(f"Lekha only fetches from {API}")
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        # Reviewed for bandit: the scheme and host are fixed to https://openlibrary.org above.
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:  # nosec B310
            body = response.read(MAX_RESPONSE_BYTES + 1)
        if len(body) > MAX_RESPONSE_BYTES:
            raise OpenLibraryError("Open Library sent something Lekha couldn't read. Try again later.")
        data = json.loads(body)
        if not isinstance(data, dict):
            raise OpenLibraryError("Open Library sent something Lekha couldn't read. Try again later.")
        return data
    except urllib.error.HTTPError as problem:
        if problem.code == 429:
            raise OpenLibraryError("Open Library is busy right now. Wait a minute and try again.") from None
        raise OpenLibraryError(f"Open Library answered with an error ({problem.code}). Try again later.") from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise OpenLibraryError(
            "Couldn't reach Open Library. Check the internet connection, or type the book in by hand."
        ) from None
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise OpenLibraryError("Open Library sent something Lekha couldn't read. Try again later.") from None


def _text(value, limit: int) -> str:
    """A tidy piece of text from Open Library: text only, one line, not too long."""
    if not isinstance(value, str):
        return ""
    return " ".join(value.split())[:limit]


def _positive_int(value) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) and value > 0 else None


def _year(text: str | None) -> int | None:
    """The first plausible four-digit year in text like "May 1998" or "1998"."""
    match = re.search(r"\b(1[4-9]\d\d|20\d\d)\b", text or "")
    return int(match.group(1)) if match else None


def _cover_id_from_url(url: str | None) -> int | None:
    match = re.search(r"/b/id/(\d+)-", url or "")
    return int(match.group(1)) if match else None


def lookup_isbn(raw_isbn: str) -> FoundBook | None:
    """Find one exact edition by ISBN. Returns None if Open Library doesn't know it."""
    isbn = clean_isbn(raw_isbn)
    valid = isbn is not None and (
        (len(isbn) == 13 and isbn.isdigit())
        or (len(isbn) == 10 and isbn[:9].isdigit() and (isbn[9].isdigit() or isbn[9] == "X"))
    )
    if not valid:
        raise ValidationError(["An ISBN is 10 or 13 digits (an ISBN-10 may end in X)."])

    query = urllib.parse.urlencode({"bibkeys": f"ISBN:{isbn}", "format": "json", "jscmd": "data"})
    data = fetch_json(f"{API}/api/books?{query}").get(f"ISBN:{isbn}")
    if not isinstance(data, dict) or not _text(data.get("title"), 300):
        return None

    identifiers = data.get("identifiers") or {}
    edition_ids = identifiers.get("openlibrary") or []
    key = data.get("key") or (f"/books/{edition_ids[0]}" if edition_ids else None)
    if not isinstance(key, str) or not EDITION_KEY.fullmatch(key):
        return None
    isbn_13 = clean_isbn(_text((identifiers.get("isbn_13") or [None])[0], 20)) or None
    if isbn_13 is not None and not (len(isbn_13) == 13 and isbn_13.isdigit()):
        isbn_13 = None
    subtitle = _text(data.get("subtitle"), 200)
    title = _text(data["title"], 300) + (f": {subtitle}" if subtitle else "")
    names = [_text(author.get("name"), 100) for author in data.get("authors", []) if isinstance(author, dict)]
    publishers = [_text(p.get("name"), 200) for p in data.get("publishers", []) if isinstance(p, dict)]
    return FoundBook(
        title=title,
        author=", ".join(name for name in names if name)[:200],
        openlibrary_key=key,
        isbn=isbn_13 or isbn,
        publisher=next((p for p in publishers if p), None),
        published_year=_year(_text(data.get("publish_date"), 50)),
        cover_id=_cover_id_from_url(_text((data.get("cover") or {}).get("medium"), 200)),
        subjects=tuple(name for subject in data.get("subjects", [])[:40] if isinstance(subject, dict)
                       for name in [_text(subject.get("name"), 100)] if name),
    )


def search(text: str, limit: int = 10) -> list[FoundBook]:
    """Works whose title or author matches the text, most relevant first."""
    text = " ".join((text or "").split())
    if len(text) < 2:
        raise ValidationError(["Type at least two letters of a title or author."])
    if len(text) > MAX_SEARCH_LENGTH:
        raise ValidationError([f"Search for at most {MAX_SEARCH_LENGTH} characters."])
    query = urllib.parse.urlencode({
        "q": text, "limit": limit,
        "fields": "key,title,author_name,first_publish_year,cover_i,subject",
    })
    results = []
    docs = fetch_json(f"{API}/search.json?{query}").get("docs")
    for doc in docs if isinstance(docs, list) else []:
        if not isinstance(doc, dict):
            continue
        title, key = _text(doc.get("title"), 300), doc.get("key")
        if not title or not isinstance(key, str) or not WORK_KEY.fullmatch(key):
            continue
        year = _positive_int(doc.get("first_publish_year"))
        authors = doc.get("author_name") if isinstance(doc.get("author_name"), list) else []
        subjects = doc.get("subject") if isinstance(doc.get("subject"), list) else []
        results.append(FoundBook(
            title=title,
            author=", ".join(name for name in (_text(a, 100) for a in authors) if name)[:200],
            openlibrary_key=key,
            first_published=year if year and 1000 <= year <= 2100 else None,
            cover_id=_positive_int(doc.get("cover_i")),
            subjects=tuple(name for name in (_text(s, 100) for s in subjects[:40]) if name),
        ))
    return results


def suggest_genre(subjects: tuple[str, ...] | list[str]) -> str | None:
    """A shop genre suggested by Open Library's subject tags, or None."""
    lowered = [subject.lower() for subject in subjects]
    for genre, keywords in GENRE_RULES:
        if any(keyword in subject for subject in lowered for keyword in keywords):
            return genre
    return None
