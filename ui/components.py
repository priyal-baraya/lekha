"""Reusable page pieces for Lekha.

Each function writes one piece of the editorial layout as HTML using
st.html. The matching styles live in ui/styles.css, and the ornament
drawings live in ui/assets/.

Text passed into these functions is escaped with html.escape, so a book
title containing "<" or "&" later on cannot break the page.
"""

import base64
from html import escape
from pathlib import Path

import streamlit as st

UI_DIR = Path(__file__).parent
ASSETS_DIR = UI_DIR / "assets"


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
    level, extra_class = ("h1", " lekha-page-title") if page_title else ("h2", "")
    description_html = (
        f'<p class="lekha-section__description">{escape(description)}</p>' if description else ""
    )
    st.html(
        f"""
        <header class="lekha-section">
          <p class="lekha-section__eyebrow">{escape(eyebrow)}</p>
          <div class="lekha-section__heading-row">
            <{level} class="lekha-section__title{extra_class}">{escape(title)}</{level}>
            {_tag(tag)}
          </div>
          {description_html}
        </header>
        """
    )


def metric_placeholders(labels: list[str], note: str) -> None:
    """A connected row of metric slots that clearly hold no data yet.

    Shows a dash, plus hidden text "No data yet" for screen readers,
    instead of a number, so nothing looks like a real result.
    """
    cells = "".join(
        f"""
        <div class="lekha-metric">
          <p class="lekha-metric__label">{escape(label)}</p>
          <p class="lekha-metric__value"><span aria-hidden="true">—</span><span class="lekha-sr-only">No data yet</span></p>
          <p class="lekha-metric__note">{escape(note)}</p>
        </div>
        """
        for label in labels
    )
    st.html(f'<div class="lekha-metrics">{cells}</div>')


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


def planned_page(title: str, purpose: str, plan: str, phase: str) -> None:
    """A page that exists in the navigation but is not built yet, and says so."""
    section_header(eyebrow="Lekha", title=title, description=purpose, page_title=True)
    divider()
    empty_state(f"Not built yet. {plan}", tag=f"Planned · {phase}")
