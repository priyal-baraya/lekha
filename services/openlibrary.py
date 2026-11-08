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
    one that returns saved real responses, so they never need the internet."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            return json.load(response)
    except urllib.error.HTTPError as problem:
        if problem.code == 429:
            raise OpenLibraryError("Open Library is busy right now. Wait a minute and try again.") from None
        raise OpenLibraryError(f"Open Library answered with an error ({problem.code}). Try again later.") from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise OpenLibraryError(
            "Couldn't reach Open Library. Check the internet connection, or type the book in by hand."
        ) from None
    except json.JSONDecodeError:
        raise OpenLibraryError("Open Library sent something Lekha couldn't read. Try again later.") from None


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
    if not data or not data.get("title"):
        return None

    identifiers = data.get("identifiers", {})
    edition_ids = identifiers.get("openlibrary") or []
    key = data.get("key") or (f"/books/{edition_ids[0]}" if edition_ids else None)
    if not key:
        return None
    isbn_13 = (identifiers.get("isbn_13") or [None])[0]
    title = data["title"] + (f": {data['subtitle']}" if data.get("subtitle") else "")
    return FoundBook(
        title=title,
        author=", ".join(author["name"] for author in data.get("authors", []) if author.get("name")),
        openlibrary_key=key,
        isbn=isbn_13 or isbn,
        publisher=next((p["name"] for p in data.get("publishers", []) if p.get("name")), None),
        published_year=_year(data.get("publish_date")),
        cover_id=_cover_id_from_url((data.get("cover") or {}).get("medium")),
        subjects=tuple(subject["name"] for subject in data.get("subjects", []) if subject.get("name")),
    )


def search(text: str, limit: int = 10) -> list[FoundBook]:
    """Works whose title or author matches the text, most relevant first."""
    text = " ".join((text or "").split())
    if len(text) < 2:
        raise ValidationError(["Type at least two letters of a title or author."])
    query = urllib.parse.urlencode({
        "q": text, "limit": limit,
        "fields": "key,title,author_name,first_publish_year,cover_i,subject",
    })
    results = []
    for doc in fetch_json(f"{API}/search.json?{query}").get("docs", []):
        if not doc.get("title") or not doc.get("key"):
            continue
        results.append(FoundBook(
            title=doc["title"],
            author=", ".join(doc.get("author_name", [])),
            openlibrary_key=doc["key"],
            first_published=doc.get("first_publish_year"),
            cover_id=doc.get("cover_i"),
            subjects=tuple(doc.get("subject", [])[:40]),
        ))
    return results


def suggest_genre(subjects: tuple[str, ...] | list[str]) -> str | None:
    """A shop genre suggested by Open Library's subject tags, or None."""
    lowered = [subject.lower() for subject in subjects]
    for genre, keywords in GENRE_RULES:
        if any(keyword in subject for subject in lowered for keyword in keywords):
            return genre
    return None
