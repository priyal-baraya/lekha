"""Capture the README and case-study screenshots from the running app.

A development tool, not part of Lekha itself. It needs Playwright
(see requirements-dev.txt), Microsoft Edge, an internet connection for
Open Library, and Lekha running on port 8501:

    .\\.venv\\Scripts\\python.exe -m streamlit run app.py
    # in a second terminal:
    .\\.venv\\Scripts\\python.exe scripts\\capture_screenshots.py

Only real data appears: whatever is in the shop's database, and real
Open Library records. The script looks books up but never adds them,
so it never types a price or a stock count.

Streamlit draws pages after they load, over a live connection, so each
shot waits until Streamlit reports it has finished running the page.
"""

from pathlib import Path

from playwright.sync_api import Page, sync_playwright

BASE = "http://localhost:8501"
OUT = Path(__file__).parent.parent / "docs" / "screenshots"
EXAMPLE_ISBN = "9780006550686"            # The God of Small Things (Flamingo, 1998)
EXAMPLE_SEARCH = "the god of small things"


def settle(page: Page) -> None:
    """Wait until Streamlit has finished running the page and drawing it."""
    page.wait_for_selector("h1", timeout=30_000)
    # The "Running…" indicator shows while the page script runs.
    page.wait_for_selector('[data-testid="stStatusWidget"]', state="detached", timeout=30_000)
    page.wait_for_timeout(1_500)      # charts and tables finish drawing
    # Cover pictures come from Open Library's image server, which can be
    # slow: wait until every image has finished loading (or failed).
    page.wait_for_function("[...document.images].every(image => image.complete)", timeout=45_000)
    page.wait_for_timeout(500)


def open_add_tab(page: Page) -> None:
    page.get_by_role("tab", name="Add a book").click()
    settle(page)


def isbn_lookup(page: Page) -> None:
    open_add_tab(page)
    page.get_by_label("ISBN", exact=True).fill(EXAMPLE_ISBN)
    page.get_by_role("button", name="Look up").click()
    settle(page)


def title_search(page: Page) -> None:
    open_add_tab(page)
    page.get_by_text("Search by title or author", exact=True).click()
    settle(page)
    page.get_by_label("Title or author", exact=True).fill(EXAMPLE_SEARCH)
    page.get_by_role("button", name="Search").click()
    settle(page)


# (file name, page path, width, height, pixel density, action before the shot)
SHOTS = [
    ("overview-desktop", "/", 1280, 1150, 1, None),
    ("books-isbn-desktop", "/books", 1280, 1150, 1, isbn_lookup),
    ("books-search-desktop", "/books", 1280, 1150, 1, title_search),
    ("books-search-phone", "/books", 390, 1300, 2, title_search),
]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="msedge")
        for name, path, width, height, density, action in SHOTS:
            page = browser.new_page(viewport={"width": width, "height": height}, device_scale_factor=density)
            page.goto(BASE + path)
            settle(page)
            if action:
                action(page)
            page.screenshot(path=OUT / f"{name}.png")
            print(f"saved {name}.png ({width}x{height} at {density}x)")
            page.close()
        browser.close()


if __name__ == "__main__":
    main()
