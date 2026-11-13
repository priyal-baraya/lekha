"""Reusable page pieces for Lekha.

Each function writes one piece of the editorial layout as HTML using
st.html. The matching styles live in ui/styles.css, and the ornament
drawings live in ui/assets/.

Text passed into these functions is escaped with html.escape, so a book
title containing "<" or "&" later on cannot break the page.

Text shown with st.markdown, st.info, st.success and similar is read as
Markdown, so anything a person typed or Open Library sent goes through
plain() first (see below).
"""

import base64
import re
from dataclasses import dataclass
from html import escape
from pathlib import Path

import streamlit as st

from services.comparisons import Comparison
from services.sentences import showing

UI_DIR = Path(__file__).parent
ASSETS_DIR = UI_DIR / "assets"


# Characters Markdown (and Streamlit's extras: $ for maths, :red[...] for
# colours, :emoji:) can treat as instructions rather than text.
_MARKDOWN_SPECIAL = re.compile(r"([\\`*_{}\[\]()#+\-.!|~<>$:&=])")
_BARE_LINK = re.compile(r"(?i)(https?|ftp|mailto|www)(?=\\[:.])")


def plain(text) -> str:
    """Make text safe to put inside Markdown, so it shows exactly as typed.

    Use it for anything a person typed (names, shop names, reasons, notes)
    or Open Library sent (titles, authors). Without it, a title such as
    "$5 *Deals*" would turn into maths and italics, a name could pretend
    to be bold "owner" text, and "![x](https://…)" would load a picture
    from someone else's website. Line breaks become spaces, so text can't
    start a heading or a list either.
    """
    text = " ".join(str(text).split())
    escaped = _MARKDOWN_SPECIAL.sub(r"\\\1", text)
    # Streamlit also turns bare web addresses ("https://…", "www.…") into
    # links. An invisible word joiner (U+2060) breaks the pattern, so an
    # address in a name or title stays plain text.
    return _BARE_LINK.sub("\\1\u2060", escaped)


def _read(path: Path) -> str:
    """Read a text file. Read fresh on every page load so that edits to
    styles.css or the SVG files show up without restarting Streamlit."""
    return path.read_text(encoding="utf-8")


# Ornament name (used in CSS class names) -> SVG file in ui/assets/
ORNAMENTS = {
    "arch": "arch-botanical.svg",
    "rosette": "divider-rosette.svg",
}


def _data_url(filename: str) -> str:
    """Turn an SVG file into a "data URL": the whole image packed into one string."""
    encoded = base64.b64encode(_read(ASSETS_DIR / filename).encode("utf-8")).decode("ascii")
    return f"data:image/svg+xml;base64,{encoded}"


def _ornament(name: str) -> str:
    """An empty <span> that CSS paints with one of the SVG ornaments.

    st.html cleans the HTML it is given and removes <svg> drawings and SVG
    images. Stylesheets are not cleaned, so each ornament is drawn as a CSS
    background image instead (see load_styles). Screen readers skip CSS
    backgrounds, which is right for purely decorative drawings.
    """
    return f'<span class="lekha-ornament lekha-ornament--{name}"></span>'


def load_styles() -> None:
    """Add Lekha's custom CSS to the page. Call once, before any content."""
    ornament_rules = "".join(
        f'.lekha-ornament--{name} {{ background-image: url("{_data_url(filename)}"); }}\n'
        for name, filename in ORNAMENTS.items()
    )
    st.html(f"<style>{_read(UI_DIR / 'styles.css')}\n{ornament_rules}</style>")


def hero(title: str, tagline: str, description: str, eyebrow: str) -> None:
    """The brand introduction: a deep-wine panel with the arch motif."""
    st.html(
        f"""
        <section class="lekha-hero" aria-label="Introduction">
          <div class="lekha-hero__text">
            <p class="lekha-hero__eyebrow">{escape(eyebrow)}</p>
            <h1 class="lekha-hero__title">{escape(title)}</h1>
            <p class="lekha-hero__tagline">{escape(tagline)}</p>
            <p class="lekha-hero__description">{escape(description)}</p>
          </div>
          <div class="lekha-hero__motif" aria-hidden="true">{_ornament("arch")}</div>
        </section>
        """
    )


def divider() -> None:
    """The ornamental divider used between major sections."""
    st.html(
        f"""
        <div class="lekha-divider" aria-hidden="true">
          <span class="lekha-divider__rule"></span>
          {_ornament("rosette")}
          <span class="lekha-divider__rule"></span>
        </div>
        """
    )


def _tag(text: str | None) -> str:
    return f'<span class="lekha-tag">{escape(text)}</span>' if text else ""


def section_header(
    eyebrow: str,
    title: str,
    description: str | None = None,
    tag: str | None = None,
    page_title: bool = False,
) -> None:
    """A section introduction: small practical label, Lora title, short explanation.

    page_title=True makes the title the page's main heading (h1) on pages
    that have no hero. Otherwise it is a section heading (h2).
    """
    st.html(_section_header_html(eyebrow, title, description, tag, page_title))


def _section_header_html(
    eyebrow: str, title: str, description: str | None, tag: str | None, page_title: bool
) -> str:
    level, extra_class = ("h1", " lekha-page-title") if page_title else ("h2", "")
    description_html = (
        f'<p class="lekha-section__description">{escape(description)}</p>' if description else ""
    )
    return f"""
        <header class="lekha-section">
          <p class="lekha-section__eyebrow">{escape(eyebrow)}</p>
          <div class="lekha-section__heading-row">
            <{level} class="lekha-section__title{extra_class}">{escape(title)}</{level}>
            {_tag(tag)}
          </div>
          {description_html}
        </header>
        """


def page_intro(eyebrow: str, title: str, description: str) -> None:
    """The opening of every page except Overview, always the same shape:
    label, main title (h1), description, then a section-sized gap."""
    st.html(
        f'<div class="lekha-page-intro">'
        f"{_section_header_html(eyebrow, title, description, None, page_title=True)}</div>"
    )


def metric_strip(metrics: list[tuple[str, str | None, str]]) -> None:
    """A connected row of figures. Each metric is (label, value, note).

    A value of None shows a dash, plus hidden text "No data yet" for
    screen readers, so a missing figure never looks like a real result.
    """
    def value_html(value: str | None) -> str:
        if value is None:
            return '<span aria-hidden="true">—</span><span class="lekha-sr-only">No data yet</span>'
        return escape(value)

    cells = "".join(
        f"""
        <div class="lekha-metric">
          <p class="lekha-metric__label">{escape(label)}</p>
          <p class="lekha-metric__value">{value_html(value)}</p>
          <p class="lekha-metric__note">{escape(note)}</p>
        </div>
        """
        for label, value, note in metrics
    )
    # The strip is laid out for four figures; a single figure takes the full width.
    style = ' style="grid-template-columns: 1fr"' if len(metrics) == 1 else ""
    st.html(f'<div class="lekha-metrics"{style}>{cells}</div>')


def empty_state(message: str, tag: str | None = None) -> None:
    """A plain panel explaining what will appear here and when."""
    st.html(
        f"""
        <div class="lekha-empty">
          {_ornament("arch")}
          <div>
            <p class="lekha-empty__text">{escape(message)}</p>
            {_tag(tag)}
          </div>
        </div>
        """
    )


# ------------------------------------------------------------ data pages

def flash(kind: str, message: str, details: list[str] | None = None) -> None:
    """Save a message to show after the next page reload.

    Saving a form is followed by st.rerun(), which redraws the page from
    the top and would wipe a message shown before it. st.session_state
    survives reruns, so the message waits there until show_flash().
    """
    st.session_state["lekha_flash"] = (kind, message, details or [])


def show_flash() -> None:
    """Show (once) any message saved with flash()."""
    saved = st.session_state.pop("lekha_flash", None)
    if not saved:
        return
    kind, message, details = saved
    show = {"success": st.success, "warning": st.warning, "error": st.error}[kind]
    show(plain(message))           # messages often quote a title or a name
    for detail in details:
        st.warning(plain(detail))


def show_errors(errors: list[str]) -> None:
    """Show every validation problem in one error box."""
    lines = "\n".join(f"- {plain(error)}" for error in errors)
    st.error(f"Nothing was saved. Please fix the following:\n\n{lines}")


# ================================================================
# Redesign building blocks (Lekha Design System, 12 Nov 2026).
# Each piece is built as an HTML string first (the *_html functions),
# so tests can check the exact markup; the plain-named functions show
# it. All text is escaped with html.escape. Pages move onto these in
# phase 4; the pieces above stay until then.
# ================================================================

TONES = ("good", "bad", "neutral")
STATUS_KINDS = ("success", "warning", "error", "info", "neutral")


def page_header_html(title: str, description: str = "") -> str:
    """A page title (the page's only h1), and one line under it if needed. No label above it."""
    line = f'<p class="lekha-pagehead__description">{escape(description)}</p>' if description else ""
    return f'<header class="lekha-pagehead"><h1 class="lekha-pagehead__title">{escape(title)}</h1>{line}</header>'


def page_header(title: str, description: str = "") -> None:
    st.html(page_header_html(title, description))


def summary_header_html(date_line: str, sentence: str) -> str:
    """Overview and Insights: a plain date line (if any), then the summary sentence as the h1."""
    meta = f'<p class="lekha-pagehead__meta">{escape(date_line)}</p>' if date_line else ""
    return f'<header class="lekha-pagehead">{meta}<h1 class="lekha-pagehead__summary">{escape(sentence)}</h1></header>'


def summary_header(date_line: str, sentence: str) -> None:
    st.html(summary_header_html(date_line, sentence))


def wordmark_html(name: str, tagline: str) -> str:
    """The sign-in page's heading: the name as the page's h1, centred, and its tagline."""
    return (f'<header class="lekha-wordmark"><h1 class="lekha-wordmark__name">{escape(name)}</h1>'
            f'<p class="lekha-wordmark__tagline">{escape(tagline)}</p></header>')


def wordmark(name: str, tagline: str) -> None:
    st.html(wordmark_html(name, tagline))


def card_heading_html(title: str, description: str) -> str:
    """A card's title (h2) and one short line under it. No label above it."""
    return (f'<div class="lekha-cardhead"><h2 class="lekha-cardhead__title">{escape(title)}</h2>'
            f'<p class="lekha-cardhead__description">{escape(description)}</p></div>')


def card_heading(title: str, description: str) -> None:
    st.html(card_heading_html(title, description))


def or_divider() -> None:
    """A thin line with "or" in the middle, between two ways of doing one thing."""
    st.html('<div class="lekha-or"><span aria-hidden="true"></span>or<span aria-hidden="true"></span></div>')


@dataclass(frozen=True)
class Figure:
    """One figure in a strip.

    value None means "no data": it shows a dash that screen readers hear
    as "No data yet". words=True is for a value that is a phrase rather
    than a number ("No sales yet"), shown a little smaller.
    """

    label: str
    value: str | None
    comparison: Comparison | None = None
    note: str | None = None
    words: bool = False


def _comparison_html(comparison: Comparison) -> str:
    if comparison.tone not in TONES:
        raise ValueError(f"Unknown tone: {comparison.tone}")
    arrow = '<span class="lekha-change__arrow" aria-hidden="true"></span>' if comparison.tone != "neutral" else ""
    return (f'<p class="lekha-change lekha-change--{comparison.tone}">'
            f'{arrow}<span>{escape(comparison.text)}</span></p>')


def _figure_html(figure: Figure) -> str:
    if figure.value is None:
        value = '<span aria-hidden="true">—</span><span class="lekha-sr-only">No data yet</span>'
    else:
        value = escape(figure.value)
    value_class = "lekha-figure__value lekha-figure__value--words" if figure.words else "lekha-figure__value"
    comparison = _comparison_html(figure.comparison) if figure.comparison else ""
    note = f'<p class="lekha-figure__note">{escape(figure.note)}</p>' if figure.note else ""
    return (f'<div class="lekha-figure"><p class="lekha-figure__label">{escape(figure.label)}</p>'
            f'<p class="{value_class}">{value}</p>{comparison}{note}</div>')


def figure_strip_html(figures: list[Figure]) -> str:
    """Figures side by side in one connected strip (not separate cards)."""
    return f'<div class="lekha-strip">{"".join(_figure_html(f) for f in figures)}</div>'


def figure_strip(figures: list[Figure]) -> None:
    st.html(figure_strip_html(figures))


def status_html(kind: str, text: str) -> str:
    """A one- or two-word status. The word carries the meaning; colour only reinforces it."""
    if kind not in STATUS_KINDS:
        raise ValueError(f"Unknown status kind: {kind}")
    return f'<span class="lekha-status lekha-status--{kind}">{escape(text)}</span>'


def step_html(number: int, title: str, text: str = "", waiting: bool = False) -> str:
    """One numbered first-run step. waiting=True greys it out until it can be done."""
    state = " lekha-step--waiting" if waiting else ""
    more = f'<p class="lekha-step__text">{escape(text)}</p>' if text else ""
    return (f'<div class="lekha-step{state}"><span class="lekha-step__number" aria-hidden="true">{number}</span>'
            f'<div><p class="lekha-step__title">{escape(title)}</p>{more}</div></div>')


def cover_letter_html(title: str) -> str:
    """Stands in for a missing Open Library cover: the title's first letter on parchment."""
    letter = next((ch.upper() for ch in title if ch.isalnum()), "·")
    return (f'<span class="lekha-cover-letter" role="img" aria-label="No cover: {escape(title)}">'
            f'{escape(letter)}</span>')


def showing_note(shown: int, total: int) -> None:
    """The line under a shortened list ("Showing 5 of 137."), if there is one."""
    text = showing(shown, total)
    if text:
        st.html(f'<p class="lekha-showing">{escape(text)}</p>')


# ---------- Overview: tables, book cells and the shelf ----------

class Html(str):
    """A table cell that is already safe HTML, built by one of the *_html
    functions here. Any other cell value is escaped."""


def _cell(value) -> str:
    return value if isinstance(value, Html) else escape(str(value))


def data_table_html(columns: list[tuple[str, str]], rows: list[list], css_class: str = "") -> str:
    """A plain, readable table. columns are (heading, "left" or "right");
    numbers go right so their digits line up."""
    def cls(align: str) -> str:
        return ' class="lekha-table__num"' if align == "right" else ""

    head = "".join(f'<th scope="col"{cls(align)}>{escape(label)}</th>' for label, align in columns)
    body = "".join(
        "<tr>" + "".join(f"<td{cls(align)}>{_cell(value)}</td>" for value, (_, align) in zip(row, columns)) + "</tr>"
        for row in rows
    )
    wrap = f"lekha-table-wrap {css_class}".strip()
    return f'<div class="{escape(wrap)}"><table class="lekha-table"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def book_cell_html(title: str, author: str | None, cover_url: str | None) -> Html:
    """A small cover (or its letter) beside the title and author."""
    if cover_url:
        cover = f'<img class="lekha-book__cover" src="{escape(cover_url)}" alt="" loading="lazy" width="22" height="33">'
    else:
        cover = cover_letter_html(title)
    author_html = f'<span class="lekha-book__author">{escape(author)}</span>' if author else ""
    return Html(f'<span class="lekha-book">{cover}<span class="lekha-book__text">'
                f'<span class="lekha-book__title">{escape(title)}</span>{author_html}</span></span>')


@dataclass(frozen=True)
class ShelfBook:
    title: str
    copies: int
    cover_url: str | None
    sold_out: bool = False


def shelf_html(books: list[ShelfBook]) -> str:
    """Covers in a row with copies sold under each. "Sold out" is said in words."""
    items = []
    for book in books:
        if book.cover_url:
            cover = f'<img class="lekha-shelf__cover" src="{escape(book.cover_url)}" alt="" loading="lazy">'
        else:
            letter = next((ch.upper() for ch in book.title if ch.isalnum()), "·")
            cover = f'<span class="lekha-shelf__cover lekha-shelf__cover--letter" aria-hidden="true">{escape(letter)}</span>'
        sold_out = status_html("error", "Sold out") if book.sold_out else ""
        items.append(f'<li class="lekha-shelf__item"><span class="lekha-shelf__frame">{cover}{sold_out}</span>'
                     f'<span class="lekha-shelf__title">{escape(book.title)}</span>'
                     f'<span class="lekha-shelf__copies">{book.copies} sold</span></li>')
    return f'<ul class="lekha-shelf">{"".join(items)}</ul>'


def stock_status_html(in_stock: int, reorder_at: int) -> str:
    """A book's stock in words: Out of stock, Low (at or below its reorder level), In stock."""
    if in_stock <= 0:
        return status_html("error", "Out of stock")
    if in_stock <= reorder_at:
        return status_html("warning", "Low")
    return status_html("success", "In stock")


@dataclass(frozen=True)
class BookRow:
    """One book in a phone list: cover, title, one line of detail, a status."""
    title: str
    cover_url: str | None
    detail: str
    status: str = ""            # built HTML from status_html / stock_status_html


def book_rows_html(rows: list[BookRow]) -> str:
    """Books as a list, for phones, where a table with many columns is too tight."""
    items = []
    for row in rows:
        cover = (f'<img class="lekha-book__cover" src="{escape(row.cover_url)}" alt="" loading="lazy" '
                 f'width="22" height="33">' if row.cover_url else cover_letter_html(row.title))
        items.append(f'<li class="lekha-booklist__item">{cover}<span class="lekha-book__text">'
                     f'<span class="lekha-book__title">{escape(row.title)}</span>'
                     f'<span class="lekha-book__author">{escape(row.detail)}</span></span>{row.status}</li>')
    return f'<ul class="lekha-booklist">{"".join(items)}</ul>'


def book_list_html(books: list[tuple[str, str | None, int, int]]) -> str:
    """Books to reorder as a list, for phones. Each item is
    (title, cover_url, in_stock, reorder_at)."""
    return book_rows_html([
        BookRow(title, url, f"{in_stock} left · reorder at {reorder_at}", stock_status_html(in_stock, reorder_at))
        for title, url, in_stock, reorder_at in books
    ])
