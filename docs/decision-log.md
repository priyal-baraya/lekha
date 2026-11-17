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

---

## 2026-11-10: Real data only in the app

**Decision:** The app no longer contains or shows any fictional data. It starts as an empty shop (`database.py --reset`). The fictional sample dataset is used only inside the tests and by `query.py --sample` (in memory). The generated demo dataset and its screenshots were deleted.

**Why:** The owner asked that nothing on the site be fake. Book details can be real (from Open Library); prices, stock and sales can only be real if the owner enters or records them, so Lekha never pre-fills them.

**Supersedes:** the "Sample data" notice (Phase 3) and the generated demo dataset (Phase 7).

---

## 2026-11-10: Open Library for book details

**Decision:** Look books up on Open Library: `/api/books?jscmd=data` for an exact edition by ISBN, `/search.json` for titles and authors. Python's built-in `urllib`, with a short timeout and a User-Agent naming the app.

**Why:** Free, open, no key or account, and it worked from this machine. Google Books refused requests without a registered key ("Too Many Requests"). No new package was needed.

**Considered:** Google Books (better search, sometimes prices, but needs a key and has a shared quota).

---

## 2026-11-10: Pre-fill, never save straight from the API

**Decision:** A found book fills in the add form, under a "check these details" note, with a link to the Open Library record. The owner corrects anything and adds their own price and stock before saving.

**Why:** Open Library is edited by volunteers. A real search returned study guides, translations and one record crediting the wrong author.

---

## 2026-11-10: Edition facts only from an exact ISBN match

**Decision:** Publisher and year are saved only from an ISBN lookup (or typed by the owner). A title search fills in title, author, cover and suggested genre, and leaves the ISBN for the owner to type.

**Why:** A search result is a *work* (the book in general, across editions). Its publisher and year would describe some other copy, and saving them would quietly put wrong facts in the catalogue.

---

## 2026-11-10: Suggested genre, confirmed by the owner

**Decision:** Simple keyword rules map Open Library's subject tags to shop genres, in a fixed order (Children, Poetry, Mystery, Cookery, History, Fiction). The suggestion is pre-selected; the owner can change it.

**Why:** Subject tags are messy ("fraternal twins", "award:man_booker_prize=1997"). A shop needs a few broad sections.

---

## 2026-11-10: Numbered migrations with PRAGMA user_version

**Decision:** Schema changes after release go in `sql/migrations/NNN_*.sql`. `apply_migrations()` runs those newer than the database's `user_version`, each with its version number in one transaction, on every start. New databases go through the same files.

**Why:** `CREATE TABLE IF NOT EXISTS` can't add columns to an existing table. Phase 4 avoided this by adding a new table; adding book details to `books` needed a real migration.

---

## 2026-11-10: Tests replay real saved Open Library responses

**Decision:** Real responses were recorded once into `tests/fixtures/`; the tests replace the network call with one that returns them.

**Why:** Tests that call the internet are slow, can fail for reasons unrelated to the code, and would call Open Library on every GitHub push. Recording *real* responses keeps the tests honest about Open Library's actual format.

---

## 2026-11-10: Cache Open Library answers for a day

**Decision:** `st.cache_data(ttl=1 day)` on the lookup and search functions in the Books page. Errors aren't cached.

**Why:** Faster repeat lookups, and fewer requests to a free service. Book details rarely change within a day.

---

## 2026-11-10: Sign in with a username and password, or with Google

**Decision:** Both. Lekha stores its own accounts (username and password), and Google sign-in uses Streamlit's built-in `st.login` (OpenID Connect, through Authlib). Google is switched on only when its credentials are in `.streamlit/secrets.toml`, which is never committed.

**Why:** The owner asked for both. A Lekha password works with no setup at all; Google suits people who don't want another password. Using Streamlit's own sign-in, rather than writing the Google exchange myself, leaves the security-sensitive part to tested code.

---

## 2026-11-10: Shared shops with owners and staff

**Decision:** A shop has members, each an **owner** or **staff**. Owners can do everything. Staff can look up and add books, record and cancel sales, see stock and alerts, and see Insights without profit. One person can belong to several shops and switch between them.

**Why:** A real bookshop has a few people at the till. Staff need to sell; they don't need to change prices, correct stock counts, see the shop's margins or manage the team. Owners can invite a second owner when they want one.

---

## 2026-11-10: One database file per shop, plus an accounts file

**Decision:** `data/accounts.db` holds people, shops, roles and invite codes. Each shop's books and sales live in their own file, `data/shops/shop_<id>.db`, with exactly the schema they had before. On each page run, `app.py` points every query at the chosen shop's file.

**Why:** The alternative, a `shop_id` column on every table, means every query in the app, including the analytics SQL, must remember `WHERE shop_id = ?`. One forgotten filter would show one shop another shop's sales. With separate files there is nothing to forget, the existing tested SQL didn't change, and a shop can be backed up by copying one file.

**Trade-off:** "Who did it" columns can't be foreign keys into another file, so they hold a plain user number; the pages look up names in `accounts.db`.

---

## 2026-11-10: The current shop is held per page run, not in a global

**Decision:** `database.use_database()` stores the chosen shop's file in a `ContextVar`.

**Why:** Streamlit serves every visitor from one Python process, at the same time. A normal global variable would be shared, so one visitor's choice of shop could briefly send another visitor's query to the wrong shop. A `ContextVar` belongs to one page run. A test runs two visits at once on two threads and checks each sees only its own shop.

---

## 2026-11-10: Passwords: scrypt, lockout, and one message for every failure

**Decision:** Passwords are stored as salted **scrypt** hashes from Python's standard library (`hashlib.scrypt`, n=2¹⁴, r=8, p=1, 16-byte random salt), and checked with `hmac.compare_digest`. At least 10 characters. Five wrong passwords lock the account for 15 minutes. A wrong password and an unknown username give the same message, and an unknown username still runs a hash, so the time taken gives nothing away.

**Why:** scrypt is deliberately slow and memory-hungry, which makes guessing stolen hashes expensive, and it needs no extra package. Separate "no such user" and "wrong password" messages would let anyone find out who has an account.

---

## 2026-11-10: Invite codes, shown once and stored hashed

**Decision:** Owners make a 10-character code (`XXXXX-XXXXX`, without look-alike characters such as 0/O and 1/I) for a chosen role. Only its SHA-256 hash is stored. It works once, for 7 days, and can be cancelled. Typing it in lowercase or without the dash works.

**Why:** No email server is needed, and a code is easy to read out loud at the shop. Hashing means a copy of the database doesn't reveal working codes. A fast hash (SHA-256) is fine here, unlike for passwords, because the codes are random and long rather than chosen by people.

---

## 2026-11-10: Permissions checked in the services, not only in the menu

**Decision:** Pages hide what a role can't use, and the service functions also refuse it (`PermissionError`). Roles are read fresh from `accounts.db` on every page run.

**Why:** Hiding a button is a convenience, not security. Reading the role fresh means removing someone, or changing their role, takes effect on their next click, not when they next sign in. A page test checks exactly that.

---

## 2026-11-10: Record who made each sale, cancellation and correction

**Decision:** Migration `002_recorded_by.sql` adds `recorded_by` / `cancelled_by` columns. Older rows stay empty and show "Not recorded".

**Why:** With several people at the till, "who cancelled this sale?" becomes a real question. Leaving older rows empty, rather than guessing a person, keeps the history true.

---

## 2026-11-10: `database.py --reset` deletes accounts and shops, after asking

**Decision:** `--reset` now deletes `accounts.db` and the shop files, and only after the person types `DELETE`.

**Why:** It used to empty the old single-shop file, `data/lekha.db`, which the app no longer reads: it would have looked like it worked while changing nothing. Deleting every account is serious, so it asks first.

---

## 2026-11-10: Slightly rounded corners

**Decision:** Corners go from square to a small 6px radius everywhere (4px on tags, 3px on the outer end of chart bars), set once in `config.toml` and once as `--lekha-radius` in `ui/styles.css`.

**Why:** The owner wanted the app to feel a little softer. A small radius does that while keeping the calm, editorial manuscript look; a large one would start to look like a generic app. Bars stay square on the baseline so their lengths are still easy to compare.

---

## 2026-11-10: Security hardening

**Decision:** A pass over every way in: sign-in, sessions, permissions, displayed text, Open Library, inputs, server settings and dependencies. Each check is listed, with its limits, in [docs/security.md](security.md). The main choices:

- **Escape all displayed text from people and Open Library** (`ui.plain()`). Streamlit reads `st.markdown`, `st.info` and similar as Markdown, with extras for maths (`$`), colours and icons. Without escaping, a title like *The $100 Startup* breaks, a display name can fake bold "owner" text, and `![x](https://…)` loads a picture from another website (which tells that website who opened the page).
- **Count wrong current passwords towards the lockout.** Otherwise someone at an unlocked till could guess the owner's password on the Settings page without limit.
- **Sign out after 60 idle minutes, and when the password changes elsewhere.** A till is a shared computer. Sixty minutes is long enough not to interrupt a quiet afternoon, short enough to end a session left open overnight. Each tab remembers a fingerprint of the password hash (a hash of a hash), never the password.
- **Limits per device on failed sign-ins, sign-ups and invite codes**, kept in memory. They complement the per-account lockout (stored in the database), which stops guessing at one account but not a common password tried against many.
- **Only this computer can open Lekha by default** (`address = "localhost"`). Streamlit's default is every network the computer is on, and Lekha has no HTTPS, so on a shop's Wi-Fi passwords would travel unencrypted.
- **pip-audit and bandit in GitHub Actions, plus Dependabot.** New vulnerabilities are published even when the code doesn't change, so the security workflow also runs weekly.

**Why not more (HTTPS, two-step sign-in, encrypted database files)?** They depend on how Lekha is hosted, which isn't decided yet. They're listed under "Not covered yet" in docs/security.md rather than half-built.

---

## 2026-11-10: Reviewed SQL marked for the code scanner, not the scanner switched off

**Decision:** bandit flagged 7 SQL strings built with f-strings. Each was read: they only join fixed text from the code (column names, a fixed sort order, a fixed status expression), and every value is a placeholder. Each line is marked `# nosec B608` with the reason beside it, instead of turning that check off for the whole project.

**Why:** A new f-string SQL query added later will still be flagged and need its own review.

---

## 2026-11-12: Redesign: a calm, analytics-first dashboard

**Decision:** Replace the manuscript-panel look (Deep Wine hero, ornamental dividers, uppercase labels above every heading) with a calm, light dashboard. The palette, Lora and Lato stay. The plan, phases and approved designs are in [docs/redesign-plan.md](redesign-plan.md).

The main choices, agreed on the canvas and signed off by the owner:

- **Each page has one job.** Overview is today and what to do (today's sales, what to reorder, the latest sales, what's selling); Insights is trends; Sales is the till. Overview and Insights no longer repeat each other's figures.
- **Say it in words.** Overview and Insights open with one sentence that sums up the figures, built from them by fixed rules, never invented.
- **Fair comparisons.** Today's sales so far are compared with the same time last week, not with a whole day. With nothing fair to compare against, no change is shown. Green and red only where "up" is good; a change in average sale stays neutral.
- **The first day is designed.** A new shop sees three steps instead of a page of dashes and ₹0.00.
- **A faster till:** search by title, author or ISBN (a barcode scanner types the ISBN), quantity buttons, and Undo after recording a sale.
- **The account menu moves into the navigation bar,** with Team, Settings, switching shops and Sign out inside it.
- **Palette refined:** a new error red kept well apart from Manuscript Crimson (they were nearly identical), a colour-blind-safe chart set (madder, peacock, turmeric, indigo), and Terracotta, Botanical Olive and Faded Rose retired.

**Why:** A design review (Nielsen's heuristics, Impeccable's craft rules and Emil Kowalski's interface principles) scored the old design 25/40: no first-run states, a slow till, a generic metric-card template and charts that couldn't be read precisely. The revised canvas scored 33/40 with no serious issues left. The decorative look also competed with the data; the owner asked for something that reads first as an analytics tool.

**What it costs:** Streamlit draws its own navigation dropdown, tables and inputs, so some details (the account menu's exact position, the till's result list) will look slightly different from the canvas. Each difference is reported as it's built.

## 2026-11-12: Sign in and Get started, as designed

**Decision:** Both pages now follow the canvas. Sign in shows the name and tagline centred, then one narrow card with the two forms as tabs; Google, when set up, sits below an "or" line as a second, plain button. Get started has the new page header and two cards, which stack on a phone. Three small departures from the canvas:
- The sign-in note says a password sign-in lasts "until you close or refresh this tab", not "for this tab": refreshing really does sign people out, so the note says so.
- The Create an account tab keeps a short password hint (at least 10 characters, a few unrelated words, stored only as a hash). The canvas only showed the Sign in tab.
- The Join card drops "Each code works once, for 7 days". The owner is told this when they make the code, and an expired code says so when it's typed.

**Why:** The old Sign in page had a label above its heading and put Google first, as the main button, even though most people sign in with a password. Get started had labels ("New shop", "Existing shop") above every heading, which the redesign removes everywhere.

**What it costs:** Streamlit's own top bar still shows above the sign-in page (the canvas has a plain bar with the logo). That bar belongs to every page, so it's handled with the navigation, not here.

## 2026-11-12: Overview, as designed

**Decision:** Overview now follows the canvas (Main, OverviewEmpty and OverviewPhone artboards):
- A date line, then one sentence about today as the page's heading ("₹1,850 in sales so far today, and 2 books need reordering.").
- Three figures, each compared fairly: today so far against the same time last week, this week so far (Monday to today), and the last 30 days against the 30 days before, with the dates of that earlier period written out.
- "Reorder these" (with covers, stock, reorder level and a worded status), "Latest sales" for today and yesterday (with the books written out, cancelled sales marked), and "Selling well this week" as a shelf of covers with "Sold out" said in words.
- A shop with no sales sees the steps to get started instead of the figures it doesn't have yet. Once it has books, the first step drops off.
- On a phone (under 640px), Overview shows today, the last 30 days and the reorder list, as on the phone artboard. This week so far, Latest sales and the shelf stay on bigger screens; the till and Insights have them in full.

**Why:** The old Overview was a hero banner, four 30-day figures with no comparison, a weekly chart that repeated Insights, and labels above every heading. The design review asked for a front page that answers "how's today going, and what needs doing?" in one look.

**Details worth knowing:**
- Pages now ask `services/clock.py` for the time, so tests can fix it to a Thursday at 16:45 and check "today so far" exactly.
- The weekly chart moved off Overview: Insights is the place for trends, and the shelf links there.
- Ties in "Selling well" go to the book that brought in more money, the same rule as Insights' best sellers.
- The "Showing N of M" line appears only when the reorder list is actually cut short.

**What it costs:** Streamlit stacks the two cards on a phone in its own way, and its phone menu opens by itself after signing in; both are Streamlit's, not Lekha's.

## 2026-11-13: Sales, as a till

**Decision:** The Sales page now follows the canvas (Sales, SalesRecorded, SalesNoMatch, SalesOutOfStock, SalesRecent and SalesPhone artboards):
- **Find a book** takes a title, author or ISBN. Pressing Enter (which a barcode scanner does after typing the ISBN) adds the book straight away when there's exactly one match; several matches are listed with an Add button each; no match says what to try and links to Books; an out-of-stock book says why it can't be sold and links to Inventory.
- **This sale** has − and + for copies, Remove, the total, when the sale will be recorded ("Recorded as now, 13 Nov, 09:40", or a chosen earlier time for receipts), and one button, "Record sale · ₹950.00", which Ctrl + Enter also presses.
- **After recording**, a line says what was saved, with **Undo**. Undo cancels the sale with the reason "Undone at the till straight after recording", so nothing is ever deleted and the record stays honest.
- **Recent sales** lists the last 20 sales with their books, and a small "Cancel a sale" form with a required reason.

**Why:** The old page made a sale in four steps per book (choose from a long dropdown, set a quantity, Add, then Complete), couldn't use a barcode scanner, and needed a sale's number to see what was in it.

**Departures from the canvas:**
- The canvas shows matches while typing. Streamlit only hears a text box when Enter is pressed, so the till searches on Enter. For a scanner that's the same thing, and one match still goes straight in.
- Recent sales has a **Books** column (the canvas didn't), so a sale can be recognised without opening it.
- Cancelling no longer needs a tick box as well as a reason; the required reason is the confirmation, as on the canvas.
- On a phone, a long table scrolls sideways inside its card rather than squashing every column.

**What it costs:** The basket lives in the browser tab, as before. When Lekha's code changes while it's running (only during development), Streamlit reloads it and an unsaved basket starts empty.

## 2026-11-13: Books, as designed

**Decision:** Books now follows the canvas (Books, BooksAdd, BooksEmpty and BooksPhone artboards):
- The page title has an **Add a book** button beside it, which opens the Add tab ready for an ISBN.
- **Browse** is a plain table: cover and title with the author under it, genre, price, copies, reorder level, and stock in words (In stock, Low, Out of stock). Search covers title, author **and ISBN**. Under the table, one line says how many books are shown ("12 books.", "Showing 2 of 12 books.").
- On a phone, the table becomes a list: title, then "author · ₹price · copies in stock", and the status.
- **Add a book** offers its three ways (ISBN, title or author, type it in) as a segmented control. A book found on Open Library shows its cover and facts in one box ("Found on Open Library. The God of Small Things · Arundhati Roy · Flamingo, 1998…"), and the shop's own fields sit under "Your shop's details".
- An empty catalogue shows a card, "No books yet", with "Add your first book".

**Why:** The old page's table was Streamlit's spreadsheet-style grid (hard to read, codes like "Low stock" in a narrow column), the ISBN box in Browse didn't search ISBNs, and adding a book started with a radio list under a label.

**Details worth knowing:**
- ISBN search needs at least 4 digits, so typing "000" doesn't match every ISBN.
- The table draws at most 100 books at once; the line underneath says so and asks for a search to find the rest. A shop with thousands of books stays quick.
- Overview's reorder list and Books now share one rule for stock in words.

**Departures from the canvas:** Genre and Sort are Streamlit's dropdowns with labels, not the canvas's compact buttons. Edit a book keeps its existing form, now in a card.

## 2026-11-13: Inventory, as designed

**Decision:** Inventory now follows the canvas (Inventory and InventoryClear artboards), as three cards:
- **Low on stock:** cover, title and author, copies, reorder level and stock in words, emptiest first ("All 6 shown, emptiest first."). A list on a phone. When nothing is low, a green line: "Nothing to reorder. Every book is above its reorder level."
- **Correct stock** (owners only): choose the book, type the copies counted, and a line says what will happen **before** saving: "Lekha has 3 in stock, so it will record a change of −1." When the count matches, it says so and Save stays off. Then the reason, and a note (still required for "Other").
- **Recent corrections:** when, book, before, after, change (+4, −1), reason, note and who, never edited or deleted. With none yet, a line says what will appear there.

**Why:** The old page used Streamlit's spreadsheet-style tables and labels above every heading, and the correction form gave no hint of what it would record until after saving.

**Details worth knowing:**
- The correction fields are no longer inside a form, so the line can update as the count changes. The safety check is unchanged: the correction is refused if the stock changed since the page showed it.
- The Book list shows title and author, not the stock. Streamlit keeps the chosen option's wording after a save, so "0 in stock" stayed on screen after a delivery made it 4. The line under the count says Lekha's current count instead, and is always fresh.
- Changes use a real minus sign (−1), easier to read than a hyphen.

**Departures from the canvas:** The Book list's options read "Godaan · Premchand" rather than "Godaan · 3 in stock", for the reason above. The note says it's required for "Other", where the canvas just said optional.
## 2026-11-13: Less text

**Decision:** Cut text that explains what's already clear, so pages read at a glance:
- A brand-new shop's Overview says only **"Welcome to Lekha!"** at the top: no date or shop line.
- "Three steps to get started" keeps its headings and buttons; the explanation under each step is gone.
- Overview's three figures show just the amount: no "₹1,620 by this time last Thursday", "2 sales · 4 copies", "Monday to today" or percentage change under them.
- Books has no line under its title, and "No books yet" says only "Look a book up by its ISBN, then add your price and stock."
- Insights' too-little-history line is now "Trends appear after two weeks of sales."

**Why:** The owner's review: every extra sentence made the dashboard look more complex than it is, and the labels already say what each figure means.

**What it costs:** Overview no longer compares today with the same time last week, or the last 30 days with the 30 before. The comparison code stays (it's tested, and Insights can use it); bringing a short "▲ 12%" back is a one-line change if it's missed.

**Second round (approved the same day):** the same rule across every rebuilt page:
- No line under the titles of Sales, Inventory, Get started or Switch shop, and none under most card headings ("Reorder these", "Latest sales", "Low on stock", "Correct stock", "Cancel a sale", "Start a shop", "Join with a code").
- Shorter messages: "Your shop is ready.", "Your books are in. Record your first sale.", "5 matches.", "No corrections yet.", and Sign in's note "Signs out after 60 minutes without activity."
- "Selling well this week" says something only when a book sold out. The step labels "After your first book" and "After 2 weeks" are gone. No match at the till is the message and an "Add it in Books" link.
- No "Showing the last 20 sales." or "The latest 20 changes…" lines; shorter hover help on the book form; the Open Library credit only on the Add tab, where its details come in.
- The design canvas was updated to match (16 artboards).


**Spacing after the cuts (same day):** taking the lines away left gaps sized for them. Closed them using the canvas's own spacing:
- **Under page titles:** the header kept 40px below it, plus Streamlit's 16px gap: 56px, sized for a line that's gone. It's now 16px plus the gap, so the first card or tab row sits 32px under every title, as on the canvas (and as Books already was).
- **New-shop steps:** each step is one row: the heading fills it, and its button sits at the right edge, as on the canvas. Before, the button floated in a narrow column, and steps without one kept an empty column, so on a phone the steps were unevenly spaced. On a phone the button wraps under its step, lined up with the step's words.
- **Phone and desktop versions of a list:** the hidden version (the desktop table on a phone, the phone list on a desktop) still took one of Streamlit's 16px gaps. Its slot is now hidden too.
- **Canvas:** card headings whose line was cut get back the canvas's own 12px spacer, instead of sitting on the table or field below. Fields in a column were set to grow 200px, which left holes in Get started, Settings, Team and Sign in. Side-by-side cards now hug their content, as in the app.

**Third round (the till and Insights, same day):**
- The till has no "Recorded as now…" line. It appears only when a sale is set to another time ("Recorded as Tuesday 10 Nov, 09:05."), so a receipt entered afterwards still can't be saved at the wrong time unnoticed. "Change date or time" stays.
- The basket's total row says **Total**, not "3 copies".
- After a sale, the message ends at the amount: no "Ready for the next customer."
- On the canvas, the single search match no longer says "Press Enter to add one copy." (the Enter key label beside it already says it).
- Estimated gross profit has one short line: "From the 92% of revenue with a cost recorded. Rent and wages aren't included." The first half shows only when some books have no cost; with none, it says "No books have a cost recorded yet." Gone: the note that today's cost per copy is used, and the line under the heading.
- "What the numbers suggest" has a short line instead of two sentences: "Patterns in your sales, not proof of why."

## 2026-11-15: Insights, as designed

**Decision:** Rebuild Insights to the canvas (Insights and InsightsEmpty artboards):
- **At the top:** the dates and what they're compared with ("17 Oct to 15 Nov 2026 · compared with the 30 days before"), one sentence that sums up the figures, and the genre and period filters beside them.
- **Four figures** (Revenue, Copies sold, Sales, Average per sale), each compared with the period before ("48% more than ₹12,789"; the average is shown neutrally, "₹609 before"). These are the comparisons taken off Overview: Insights is the page for trends.
- **Revenue by day, week or month,** chosen from the period's length (up to 14 days by day, up to about six months by week, then by month), so there's no "Group sales by" control. Every bar is a whole week (or day or month): the first bar starts on the Monday before the period. The latest finished bar is crimson, earlier ones lighter, and the one still running is a dashed outline ("₹8,596 so far"). A sentence above says how the latest compares with the best: "Last week brought in ₹450. The best week was 19 Oct, at ₹6,294." The numbers are also offered as a table.
- **Revenue by genre** as labelled bars (always every genre; with a genre filter on, the others are drawn quieter), next to **estimated gross profit** (owners only).
- **Most copies sold:** the top five, with covers.
- **What the numbers suggest:** one card per finding, saying in words whether it's good news ("Doing well") or worth a look, with what to try beside it. When there's nothing to try, the side says what the finding can't tell you.
- **Before two weeks of sales,** the page says "Trends appear after two weeks of sales.", shows how many of the 14 days there are so far ("Two weeks of sales", "3 of 14 days") and gives the figures so far.

**Why:** The old page stacked six sections with labels above every heading and long explanations. The canvas answers "how are sales trending?" in the first screen.

**What changed from the old page:**
- "No sales in this period" (the list of unsold books) is gone as its own section. Its useful part, books on the shelf that didn't sell, is a finding.
- The small-sample warning is said once above the findings, not repeated in each.
- Findings use whole rupees, like the rest of the page, and their suggestions lost the "Possible action:" label (the card says "Worth trying").
- Each finding keeps its limits in the code (and its tests), but the card shows one of them only when there's nothing to try, as on the canvas.

**Departures from the canvas:** The canvas chart showed nine weeks for "Last 30 days"; the app shows the weeks the period touches. The canvas had example findings (such as fewer books per sale) that Lekha doesn't calculate; the app shows only the findings it can back with figures.

**Cut after review (the owner's less-text rule, same day):** "· owners only" after the profit share (staff never see the card); "Fiction brought in 91%." under Revenue by genre (the bars and the summary sentence say it); "Dashed bar: this week so far." under the chart (the bar is labelled "so far"); and the waiting card's explanation and list of what's coming. Its heading became "Two weeks of sales", to name what the bar counts towards. The canvas was updated to match.

## 2026-11-15: Team and Settings, as designed

**Decision:** Rebuild the last two pages to the canvas (Team and Settings artboards), with the less-text rule: no line under either title.
- **Team:** "Who's in the shop" as a table (name, with "(you)"; role in words, Owner or Staff; how each person signs in, Password or Google; when they joined). Below it, side by side, "Change someone's role" (a person, then Make staff, Make owner or Remove from shop, then Apply) and "Invite someone" (Staff or Owner, then Make an invite code).
- **Removing someone asks first:** "Remove Vikram from Kitab Ghar?" with Yes, remove and Keep. It can't be undone from here (they'd need a new invite), so it gets a second step; changing a role doesn't, because it can be changed back.
- **An invite code** is shown once, large, with "Shown once. Works once, for 7 days." Codes not yet used are listed under it with Cancel code.
- **Settings:** four cards, two by two: Shop (owners only), Your account, Change password (only for people who sign in with a password) and More shops.

**Why:** The old pages had a label above each heading, a sentence under each, and Team's role change behind a tick box for every change.

**Departures from the canvas:** The canvas has no list of unused codes; the app keeps it, so an owner can cancel a code that was never handed over. Staff don't see the Shop card at all (the old page showed them the reorder level and said only owners could change it). A password change now says just "Password changed.", since the card already says other tabs will be signed out.

**Cut after review (same day):** "Other tabs signed in with the old password will be signed out." under Change password, and "Run another bookshop, or help at a friend's?" under More shops (the link says it). Other tabs are still signed out; the page just doesn't say so. The canvas was updated to match, including the lines under the Team and Settings titles, which the app already left out.

## 2026-11-15: Polish (Phase 5)

**Decision:** Fix what the accessibility pass and the worst-case data check found (page titles, field focus, a hint covering numbers, the chart axis's number format), remove the first design's unused pieces, and rewrite [design-system.md](design-system.md) to describe the design as built.

**Why:** The pages were each checked as they were built, but not together, and not against the accessibility rules as a set.

**Not done here:** the automatic design scan needs the Impeccable engine, which hasn't been downloaded (the owner hasn't approved the download), so the final critique was a review by eye against the same heuristics as before. The README's screenshots still show the first design: `scripts/capture_screenshots.py` signs in as the owner, so the owner runs it.

## 2026-11-15: Sign in's tabs, and two more cuts

**Decision:**
- **Sign in's two tabs share the card's width,** each label centred over its half, like the full-width button below. Before, they sat together at the card's left edge (in line with the fields, but they looked off-balance in a centred card with a full-width button).
- **No "Signs out after 60 minutes without activity."** under Sign in. People are still signed out after an hour without activity, and the sign-in page says so when it happens.
- **Inventory with nothing to reorder says only "Nothing to reorder."** ("Every book is above its reorder level." repeated it.)

**Why:** The owner's review. The canvas was updated to match (SignIn and InventoryClear artboards).

**Create an account's password note (same day):** trimmed to "At least 10 characters.", and moved from the top of the tab to just under "Choose a password", where it applies. Gone: the advice about unrelated words and the note that Lekha keeps only a salted hash. Both are still true: a password that's too easy to guess is refused with that advice, and only the hash is stored.

## 2026-11-15: Quieter forms, a palette success colour, suggestions as you type

**Decision:**
- **No "Press Enter to submit form" or character count** ("12/60") inside fields while typing, anywhere. Enter still submits, every form has its button, and the length limits still apply.
- **"Confirm password"** instead of "Type the password again" (Create an account), and "Confirm new password" in Settings, to match.
- **Success is Persian Teal on warm parchment** (`#263F3C` on `#EFE3D1`, 8.9:1) instead of mint green, for messages after saving, "In stock", "Doing well" and the up arrows in figures. The owner found the green didn't sit with the page. Both colours were already in the palette (links and hover). Success boxes get a thin parchment edge, because the parchment is close to the page's paper.
- **Book suggestions as you type:** in Add a book, "Search by title or author" asks Open Library after a short pause in typing, from three letters, instead of waiting for Enter. Each search is cached for a day.

**Why:** The owner's review.

**Not changed:** the till's "Find a book" still waits for Enter: a barcode scanner types the ISBN and presses Enter, and one match goes straight into the sale, so searching mid-typing could add the wrong book.

## 2026-11-15: One reorder level for the whole shop

**Decision:** Nobody types a reorder level per book any more. The shop has one, set by an owner in Settings ("Reorder level", "Used for every book"). New books get it automatically, and saving Settings sets it on every book. The Add and Edit forms no longer have the field.

**Why:** The owner's review: the term wasn't clear, and asking for it on every book was one more thing to type.

**How:** Books still store their reorder level, so the low-stock rule and every query stay the same (low at or below it). `services/books.set_reorder_level_for_all` sets it on every book in one step.

**What it costs:** a slow seller and a bestseller can no longer have different levels. Existing books keep their old levels until an owner next saves Settings.

**No "Reorder at" column (next day, 16 Nov):** with one reorder level for the shop, the column showed the same number on every row, so it was removed from Overview's "Reorder these", Inventory's "Low on stock" and the Books table, and the phone lists say "0 left" instead of "0 left · reorder at 3". The level is in Settings; the status word (Low, Out of stock) still says which books need reordering. The canvas was updated to match.

## Selling price from Google Books (16 Nov 2026)

**Context:** the owner asked whether the selling price could be fetched, so it doesn't have to be typed for every book. Until now Lekha never suggested prices.

**Checked first:** Google Books refused every keyless request ("quota exceeded"): without a key, all apps share one daily limit. Its prices are what Google Play charges in India, usually the ebook, and many print books have none.

**Decision (the owner's):** use the shop's own free API key from `secrets.toml` (or the host's secret settings, once hosted: one key serves everyone using that Lekha), and fill in the price field rather than only showing a hint. Only after an ISBN lookup, because a title search doesn't give an exact edition.

**How:** `services/googlebooks.py` asks for `isbn:<the ISBN>` in India and uses only the edition with that ISBN, its list price (closest to the printed price) or else its retail price, in rupees, ₹0 to ₹1,00,000. The field shows "Google Play ebook price" (or "Google Books price") under it, the found-book line says "check the price", and "Only you set prices." shows only when there is no suggestion. With no key, or any trouble, the field is empty as before. Cached for a day like Open Library.

**What it costs:** an ebook price can be lower than the printed copy, so the label matters, and the owner still has to check it. This reverses the earlier "never guessed" rule for prices; stock is still never guessed.

**Canvas:** BooksAdd shows the filled-in price with its label, and its out-of-date per-book "Reorder level" field (removed from the app in #29) is gone.

**Price by title and author (next day, 17 Nov):** with the owner's key, real answers showed Google has no price for printed ISBNs: all 8 tried were "not for sale" (and one ISBN, 9780143028574, was even catalogued under The God of Small Things instead of Train to Pakistan). Its prices belong to its own ebook editions. Offered removing the feature or searching by title; the owner chose the title search.

Now, when the ISBN has no price (or a book is chosen from a title search, which has no ISBN), Lekha searches Google for the title and the first author's surname and takes a priced edition whose authors include that surname and whose title is the same (ignoring a subtitle) or starts with it, like "Train to Pakistan Penguin Premium Classic Edition". Exact titles come first, then English editions for a title in Latin letters (Google listed a Marathi edition of The God of Small Things), then Google's order. The label stays "Google Play ebook price".

**What it costs:** it's an ebook price for some edition of the book, not the copy in the shop's hand; Google's answers change between calls (a ₹199 Train to Pakistan was listed once, then not); and some prices are odd (₹1,146 for a Penguin Pride and Prejudice ebook). 9 of 16 well-known books got a price. The owner checks every price before saving.

Tests now never read the real `.streamlit/secrets.toml` and can't reach the internet: an autouse fixture in `tests/conftest.py` gives every test empty secrets and blocks `urlopen`.

**"Recommended price" (18 Nov):** the owner didn't want the label to say "Google Play ebook price". The field now says **Recommended price** under it, whatever Google's edition: it's a starting point the owner changes as they like. Where it comes from is in the setup guide and in `services/googlebooks.py`. The canvas BooksAdd artboard matches.