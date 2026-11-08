"""Capture the README and case-study screenshots from the running demo app.

A development tool, not part of Lekha itself. It needs Playwright
(see requirements-dev.txt) and Microsoft Edge, and the app running on
the FICTIONAL demo data at port 8502:

    .\\.venv\\Scripts\\python.exe demo_data.py
    $env:LEKHA_DB_PATH = "data\\demo.db"
    .\\.venv\\Scripts\\python.exe -m streamlit run app.py --server.port 8502
    # in a second terminal:
    .\\.venv\\Scripts\\python.exe scripts\\capture_screenshots.py

Streamlit draws pages after they load, over a live connection, so each
shot waits until Streamlit reports it has finished running the page.
"""

from pathlib import Path

from playwright.sync_api import Page, sync_playwright

BASE = "http://localhost:8502"
OUT = Path(__file__).parent.parent / "docs" / "screenshots"


def settle(page: Page) -> None:
    """Wait until Streamlit has finished running the page and drawing it."""
    page.wait_for_selector("h1", timeout=30_000)
    # The "Running…" indicator shows while the page script runs.
    page.wait_for_selector('[data-testid="stStatusWidget"]', state="detached", timeout=30_000)
    page.wait_for_timeout(1_500)      # charts and tables finish drawing


def choose(page: Page, label: str, text: str) -> None:
    """Pick an option in a Streamlit dropdown by typing it."""
    page.get_by_role("combobox", name=label).click()
    page.keyboard.type(text)
    page.keyboard.press("Enter")
    settle(page)


def add_to_basket(page: Page, title: str) -> None:
    choose(page, "Book", title)
    page.get_by_role("button", name="Add to sale").click()
    settle(page)


def insights_all_time(page: Page) -> None:
    choose(page, "Period", "All time")


def sales_basket(page: Page) -> None:
    add_to_basket(page, "The Tamarind Letters")
    add_to_basket(page, "Pip and the Paper Boat")


# (file name, page path, width, height, pixel density, action before the shot)
SHOTS = [
    ("overview-desktop", "/", 1280, 1450, 1, None),
    ("insights-desktop", "/insights", 1280, 2300, 1, insights_all_time),
    ("books-desktop", "/books", 1280, 980, 1, None),
    ("sales-desktop", "/sales", 1280, 900, 1, sales_basket),
    ("inventory-desktop", "/inventory", 1280, 1250, 1, None),
    ("overview-phone", "/", 390, 1500, 2, None),
    ("sales-phone", "/sales", 390, 1150, 2, sales_basket),
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
