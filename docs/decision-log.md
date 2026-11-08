# Decision log

Each entry: what was decided, why, and what else was considered. Newest at the bottom.

---

## 2026-10-24: Python, SQLite, Streamlit as the starting stack

**Decision:** Python for logic, SQLite for the database, SQL for analysis, Pandas where it helps, Streamlit for the interface.

**Why:** SQLite needs no server and ships with Python, so time goes into learning database design and SQL rather than setup. Streamlit gives a working interface without a separate frontend and API.

**Considered:** PostgreSQL (more setup, not needed for one local user); React frontend (a second language and architecture before the core works).

---

## 2026-10-24: Project lives in `C:\Users\priya\projects\lekha`

**Decision:** Use a folder inside the user's home directory.

**Why:** `C:\Users\projects` only allows administrators to create files. Using the home folder avoids changing Windows permissions.

---

## 2026-10-24: Virtual environment, run tools with `python -m`

**Decision:** A `.venv` per project; run tools as `.\.venv\Scripts\python.exe -m pip` and `-m streamlit`.

**Why:** Keeps Lekha's packages separate from other projects. Calling the venv's Python directly guarantees the right packages are used and avoids Windows' script-blocking setting for `Activate.ps1`.

---

## 2026-10-24: `requirements.txt` lists direct dependencies only

**Decision:** Pin only `streamlit` and `pandas` by hand, not the full `pip freeze` output.

**Why:** A short file a person can read and explain. pip installs the sub-dependencies automatically.

---

## 2026-10-25: Theme in `.streamlit/config.toml`, CSS only where needed

**Decision:** Every colour, font, corner radius, border and chart colour that Streamlit supports is set in `config.toml`. `ui/styles.css` only styles HTML we write ourselves (classes starting `lekha-`), plus one rule for keyboard focus.

**Why:** Built-in settings survive Streamlit updates. CSS that targets Streamlit's internal class names breaks when those names change. Each option was checked against `streamlit config show` for Streamlit 1.66.1.

---

## 2026-10-25: Added one colour, Border Taupe `#8C7A68`

**Decision:** Use `#8C7A68` for input and panel outlines.

**Why:** WCAG 1.4.11 asks that the outline identifying a control reaches 3:1 against its background. Measured on Manuscript Paper: Antique Gold 2.66, Aged Parchment far lower, Secondary Text 5.99 (passes, but looks heavy on every outline). `#8C7A68` measures 3.49: it passes while staying quiet.

**Considered:** Reusing Secondary Text `#67554A`. Still a valid fallback if the palette must stay closed.

---

## 2026-10-25: Ornaments drawn as CSS background images

**Decision:** SVG files in `ui/assets/` are converted into data URLs by `load_styles()` and used as `background-image` on empty `<span class="lekha-ornament">` elements.

**Why:** `st.html` cleans its HTML and removed both inline `<svg>` drawings and `<img>` tags with SVG data URLs (confirmed by inspecting the rendered page). Stylesheets are not cleaned. Background images are also skipped by screen readers, which is correct for decoration.

**Considered:** Streamlit static file serving (it is not certain that it serves `.svg` with an image content type, which would be needed); `st.markdown(unsafe_allow_html=True)` (also sanitised, and less explicit).

---

## 2026-10-25: Top navigation with honest placeholder pages

**Decision:** `st.navigation(position="top")` with five practical labels. Pages not built yet show "Not built yet" and the phase they are planned for.

**Why:** It fixes the information architecture early and lets the navigation style be checked, without pretending features exist.

---

## 2026-10-25: Overview shows placeholders, never invented numbers

**Decision:** The metric strip shows "—" with "Not connected yet", and screen readers hear "No data yet". Sections carry "Placeholder" or "Planned · Phase N" tags.

**Why:** There is no database yet. Showing plausible fake figures would look like real results in screenshots.

---

## 2026-10-25: Tagline kept as "Reading between the numbers."

**Decision:** Keep the tagline and description from the user's own edit of `app.py`, instead of the alternative wording in the design brief ("Between the covers and the numbers." / "Where bookstore instincts meet meaningful insights.").

**Why:** The user asked for their code changes to be preserved.

---

## 2026-10-25: Work on a branch for the design pass

**Decision:** Design changes go on `design/manuscript-theme` and are merged into `main` once reviewed.

**Why:** The design pass touches many files. Keeping it off `main` means the public `main` branch always runs.

---

## 2026-10-28: Three core tables: books, sales, sale_items

**Decision:** A sale (the transaction) and its sale items (one line per book) are separate tables, linked by foreign keys.

**Why:** One visit can include several books. Splitting stores each fact once and lets transactions and copies sold be counted separately. See `docs/schema.md`.

---

## 2026-10-28: Money stored as whole paise

**Decision:** All prices are INTEGER paise (₹349.00 → `34900`).

**Why:** Binary floating-point numbers can't represent values like 0.1 exactly, so sums of decimal prices drift. Whole numbers are exact.

---

## 2026-10-28: Sale totals are calculated, not stored

**Decision:** No `total_amount` column. Totals come from `SUM(quantity × unit_price_paise)`.

**Why:** A stored total is a second copy of the same fact that could disagree with the lines. Calculating is always consistent, and fast at this data size.

---

## 2026-10-28: Price recorded on every sale line

**Decision:** `sale_items.unit_price_paise` stores the price paid, separate from `books.selling_price_paise`.

**Why:** Prices change. Past revenue must not change with them.

---

## 2026-10-28: Cancel sales with a status, never delete them

**Decision:** `sales.status` is `completed` or `cancelled`. Analytics count only completed sales.

**Why:** Deleting erases evidence. The column is added now so the table doesn't need changing in Phase 4.

---

## 2026-10-28: STRICT tables, rules in the schema

**Decision:** Every table is `STRICT`, with `CHECK`, `NOT NULL`, `UNIQUE` and foreign-key rules. Foreign keys are switched on in `get_connection()`.

**Why:** The database refuses bad data even if application code has a bug. SQLite's defaults (loose typing, foreign keys off) are too forgiving.

**Considered:** Validating only in Python. Rejected: one missed check would let bad rows in permanently.

---

## 2026-10-28: Dates as ISO text in store local time

**Decision:** `sale_datetime` is text like `2026-10-28 14:30:00` in India Standard Time, validated with `strftime()`.

**Why:** SQLite has no date type. ISO text sorts correctly as plain text and works with SQLite's date functions. A single store in one time zone doesn't need UTC conversion yet.

---

## 2026-10-28: Genre as text, not a separate table

**Decision:** `books.genre` is free text, kept consistent by offering a dropdown in the app (Phase 3).

**Why:** Simpler queries for now. Revisit if variant spellings appear.

---

## 2026-10-28: Sample data as SQL, rebuilt by command

**Decision:** The fictional dataset is `data/sample_data.sql`, loaded by `python database.py --reset-sample`. The database file itself is not committed.

**Why:** Plain INSERT statements are readable and reviewable in Git. The database can always be rebuilt identically.

---

## 2026-10-28: pytest for automated tests

**Decision:** Use pytest, with each test getting a fresh in-memory database.

**Why:** It's the most widely used Python test runner, and plain `assert` statements keep tests readable. In-memory databases keep tests fast and isolated from real data.

---

## 2026-11-08: A service layer between pages and the database

**Decision:** Business rules live in `services/` (books, inventory, money). Pages in `views/` call those functions and never write SQL themselves.

**Why:** The rules can be tested with pytest without a browser, reused by several pages (low stock is needed on Overview and Inventory), and kept when the interface is redesigned.

---

## 2026-11-08: Stock changes only through recorded corrections

**Decision:** The Books edit form shows stock as read-only. Stock changes on the Inventory page, where each change needs a reason and is saved together with a history row in `stock_adjustments`, in one transaction.

**Why:** An editable number leaves no trace of why it changed (theft, damage, a counting mistake). The history makes every change explainable.

**Considered:** A plain editable stock field. Simpler, but no audit trail.

---

## 2026-11-08: Corrections are checked against the number the user saw

**Decision:** `UPDATE books SET stock_quantity = <counted> WHERE book_id = ? AND stock_quantity = <number shown on screen>`. If no row matches, nothing is saved and the user is told the stock changed.

**Why:** It stops a correction landing on top of a number the user never saw, for example after someone else's change or a double click on Save. This pattern is called *optimistic concurrency control*.

---

## 2026-11-08: "Delivery received" is a correction reason, not a separate feature

**Decision:** Incoming stock is recorded as a correction with the reason "Delivery received".

**Why:** Enough to keep stock and history correct now. A full deliveries feature (suppliers, invoices, costs per delivery) can come later if needed.

---

## 2026-11-08: Rupees converted to paise with Decimal

**Decision:** `services.money.rupees_to_paise` converts through `Decimal(str(value))` and rejects fractions of a paisa.

**Why:** Float arithmetic loses paise: `int(19.99 * 100)` is 1998. A test checks this.

---

## 2026-11-08: Validation in Python, with the database as a safety net

**Decision:** `validate_book` checks every field and reports all problems at once, in plain language. The schema's rules stay in place behind it.

**Why:** Database errors are accurate but unfriendly, and stop at the first problem. Streamlit's own "required" setting only runs in the browser, and its documentation notes it can be bypassed, so the server must check too.

---

## 2026-11-08: Genres matched ignoring case

**Decision:** A typed genre that matches an existing one apart from upper/lower case uses the existing spelling.

**Why:** It prevents "fiction" and "Fiction" becoming two genres in revenue-by-genre analysis, without a separate genres table.

---

## 2026-11-08: Forms reset by changing their key

**Decision:** The add-book and correct-stock forms include a version number in their widget keys, increased after each successful save.

**Why:** Deleting the old values from `st.session_state` did not empty the add-book form in testing; the browser kept showing what was typed. A new key makes Streamlit draw a new, empty form.

---

## 2026-11-08: "Sample data" notice on every data page

**Decision:** Overview, Books and Inventory always show "Sample data: every book and sale shown here is fictional."

**Why:** Screenshots of the app must never pass for a real store's figures. Assumption: Lekha has only ever held the fictional dataset. Remove the notice if real data is ever loaded.

---

## 2026-11-08: Recording a sale is one transaction

**Decision:** `services.sales.record_sale` inserts the sale, inserts each line and reduces each book's stock inside one transaction. Every problem found raises an error at the end, which rolls back everything, including stock already reduced for earlier lines.

**Why:** A sale must never be half-saved, and stock must never change without a matching sale. A test makes the second of two lines fail and checks that the first line's stock change is undone. A deliberately broken version (no rollback) was shown to fail that test.

---

## 2026-11-08: Check and reduce stock in one statement

**Decision:** `UPDATE books SET stock_quantity = stock_quantity - :n WHERE book_id = :id AND stock_quantity >= :n`. If it changes no rows, there wasn't enough stock.

**Why:** Reading the stock, checking it in Python and then writing it leaves a gap where something else could change the stock ("check, then act"). One statement leaves no gap, and stock can never go negative.

---

## 2026-11-08: The sale uses the price shown on screen, or not at all

**Decision:** Each basket line carries the price shown when the book was added. If the book's current price differs at save time, the sale is refused.

**Why:** The saved sale must match what the customer was told. No discounts yet: the price is the shelf price.

---

## 2026-11-08: The basket lives in session state

**Decision:** The basket is kept in `st.session_state` until "Complete sale". Nothing is written to the database before then.

**Why:** An unfinished sale isn't a fact yet. The cost: refreshing the browser loses an unfinished basket, which is acceptable for a till.

---

## 2026-11-08: Sales are cancelled, never edited or deleted

**Decision:** `cancel_sale` marks a sale `cancelled`, returns its copies to stock and records when and why in `sale_cancellations`, in one transaction. Only a `completed` sale can be cancelled. To fix a mistake: cancel and record again.

**Why:** Editing or deleting would erase evidence and make stock history unreliable.

**Considered:** Partial returns (one book out of three). Left for later.

---

## 2026-11-08: Cancellations in a new table, not new columns

**Decision:** `sale_cancellations` with `sale_id` as its primary key.

**Why:** The primary key lets the database itself refuse a second cancellation of the same sale. A new table is created by `CREATE TABLE IF NOT EXISTS`, so no migration of existing databases is needed.

**Trade-off:** The cancellation is stored in two places (`sales.status` and this table). Both are written in the same transaction, and a test checks they always agree.

---

## 2026-11-08: Sales can be dated in the past, not the future

**Decision:** A sale is dated "now" unless "This sale happened earlier" is ticked. Future dates are refused.

**Why:** Owners often enter paper receipts at the end of the day.

---

## 2026-11-08: Metrics defined and hand-calculated before coding

**Decision:** Every analytics figure was defined and worked out by hand on the sample data (`docs/analytics.md`) before the code existed, and the tests use those numbers.

**Why:** A dashboard number nobody has checked is a guess. When code and hand calculation disagree, one of them is wrong, and the test says so.

---

## 2026-11-08: One shared definition of "a sale in the period"

**Decision:** Every analytics query starts from `sql/analytics/_period_lines.sql` (completed sales, inside the period, optionally one genre), placed in front of the query as a CTE.

**Why:** If each query filtered by itself, one could forget to exclude cancelled sales, and the page's figures would quietly disagree.

---

## 2026-11-08: Analytics SQL in separate .sql files

**Decision:** Each query lives in its own commented file in `sql/analytics/`.

**Why:** The SQL can be read, reviewed and discussed without digging through Python strings.

---

## 2026-11-08: Half-open date ranges

**Decision:** A period of whole days is filtered as `>= start 00:00:00` and `< day-after-end 00:00:00`.

**Why:** `<= end 23:59:59` would miss anything recorded with fractions of a second, and is easy to get wrong. Tests check both edges.

---

## 2026-11-08: Partial periods drawn as outlines; empty periods as zero

**Decision:** A day, week or month that sticks out of the period, or hasn't finished yet, is drawn as an outlined bar and named in the tooltip and summary. Periods with no sales show as 0.

**Why:** A partial week looks like a bad week, which is one of the most common ways charts mislead. Missing periods would hide gaps entirely. Shape, rather than colour, keeps the distinction visible to colour-blind readers.

---

## 2026-11-08: Ties share a rank

**Decision:** Best sellers use SQL's `RANK()`.

**Why:** Five books with 3 copies each are equally "third". Numbering them 3, 4, 5, 6, 7 would invent a difference that isn't in the data.

---

## 2026-11-08: Estimated gross profit, clearly labelled

**Decision:** Show estimated gross profit on the Insights page only, with the revenue it covers and its limits: today's cost per copy, books without cost left out (not treated as free), running costs excluded.

**Why:** The brief asks for profit only if the cost basis is reasonable and clearly defined. It is reasonable as an estimate, not as accounts.

**Considered:** Leaving profit out until cost is recorded per delivery.

---

## 2026-11-08: Observations state evidence and limits, and admit small samples

**Decision:** Observations are generated by simple rules from calculated numbers. Each one shows its evidence and limits, and below 30 sales each says it's a hint, not a pattern.

**Why:** The brief requires suggestions to acknowledge uncertainty. The 30-sale threshold is a plain judgement call, not a statistical test, and is documented as such.

---

## 2026-11-08: Keep the small sample dataset

**Decision:** No larger generated dataset yet.

**Why:** 14 sales make thin charts, but every number can be checked by hand. A larger, clearly fictional demo dataset may come in Phase 7 for screenshots.

---

## 2026-11-08: Default period is the last 30 days

**Why:** It's what an owner would check most often. "All time" shows the whole sample, which mostly falls earlier than 30 days ago.

---

## 2026-11-08: Audit before refining

**Decision:** Phase 6 started with a measurement script (contrast of every piece of text against its real background, heading order, text sizes) and a visual review at desktop and phone width, and fixed only what those found.

**Why:** "Polish" without evidence tends to change taste, not usability. The before and after numbers are in the testing log.

---

## 2026-11-08: A spacing scale

**Decision:** Six spacing tokens (4, 8, 16, 24, 40, 64px) replace one-off values in `ui/styles.css`.

**Why:** Consistent rhythm, and a direct match for Figma's spacing variables in a future redesign.

---

## 2026-11-08: Override Streamlit's faded text where it fails contrast

**Decision:** Chart axis text is set to Secondary Text on each Altair axis; input placeholders get Secondary Text through a CSS rule.

**Why:** Streamlit's defaults measured 3.15:1 (chart text) and 3.89:1 (placeholders), below the 4.5:1 target. The placeholder rule uses plain element selectors, not Streamlit class names, so it should survive updates.

---

## 2026-11-08: Sentences instead of grids on narrow screens

**Decision:** Sales basket lines read "1 copy × ₹399.00 = ₹399.00" with a Remove button, instead of a five-column grid.

**Why:** Streamlit stacks columns on phones, which separated every number from its label. A sentence reads correctly at any width.

---

## 2026-11-08: Decision columns first in tables

**Decision:** Tables show the title, then the columns you act on (status, stock, copies, revenue, change), then details (author, genre, dates).

**Why:** On a phone, a table shows only its first two or three columns without scrolling sideways. The low-stock table used to hide its Status column there.

---

## 2026-11-08: Database location from an environment variable

**Decision:** `LEKHA_DB_PATH` chooses the database file (default `data/lekha.db`). `database.database_path()` reads it on every call.

**Why:** Tests, the demo dataset and any future deployment each need their own database without code changes. Reading it at call time, not import time, lets a test switch files just by setting the variable.

---

## 2026-11-08: One error handler around every page

**Decision:** `app.py` runs each page inside `try/except`: database errors and anything unexpected show a plain message; full details go to the terminal log. `showErrorDetails = "none"` covers anything outside it.

**Why:** A Python traceback means nothing to a shop owner and exposes the code. `st.rerun()` and `st.stop()` are unaffected: Streamlit signals them with a `BaseException`, which `except Exception` lets through (checked before relying on it).

---

## 2026-11-08: Page tests with Streamlit's AppTest

**Decision:** 11 tests run the pages without a browser, including the brief's example (sell 2 copies, stock falls by exactly 2) through the real Sales page.

**Why:** The rules were tested; the wiring between pages and rules wasn't. AppTest is part of Streamlit, so it adds nothing new to install.

---

## 2026-11-08: Tests run on GitHub for every push and pull request

**Decision:** A GitHub Actions workflow installs `requirements.txt` on Linux with Python 3.13 and runs pytest.

**Why:** A broken change can't be merged unnoticed, it proves the project works outside the development machine, and the badge shows it to visitors.

---

## 2026-11-08: A generated demo dataset, separate from the tested one

**Decision:** `demo_data.py` builds `data/demo.db` (30 invented books, about 14 weeks of invented sales) from a fixed random seed and fixed dates, recording everything through Lekha's own service functions. The small hand-checked sample dataset stays the one the tests and hand calculations use.

**Why:** 14 sales make near-empty charts in screenshots. Generating through the services exercises the real rules hundreds of times. Every screenshot and the case study say which dataset is shown.

**Supersedes:** the Phase 5 decision to keep only the small dataset, which deferred this to Phase 7.

---

## 2026-11-08: Screenshots with Playwright, as a development-only tool

**Decision:** `scripts/capture_screenshots.py` uses Playwright to drive the installed Microsoft Edge. Playwright is listed in `requirements-dev.txt`, not `requirements.txt`.

**Why:** Headless Edge alone captured only the loading skeleton, because Streamlit draws after the page loads. Playwright can wait for Streamlit to finish. Running Lekha doesn't need it, so it stays out of the main requirements.

---

## 2026-11-08: Hide Streamlit's developer controls

**Decision:** `toolbarMode = "viewer"`.

**Why:** The Deploy and Rerun buttons are for developers, not shop owners. `docs/setup.md` explains how to switch back while developing.

---

## 2026-11-08: Remove the Overview's placeholder message

**Decision:** Removed "We're building the foundation first. Book data and analytics will come next."

**Why:** It was no longer true, and the hero and sample-data notice already explain the page. Removed with the owner's agreement.

---

## 2026-11-08: Resume bullets stay out of the repository

**Why:** A resume is personal and changes per application. The case study holds the verified facts the bullets are drawn from.
