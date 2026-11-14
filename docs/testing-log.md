# Testing log

Checks that were actually run, what they found, and what was fixed. Newest at the bottom.

---

## 2026-10-24: Environment and starter page

| Check | How | Result |
|---|---|---|
| Python available | `python --version` | 3.13.3 |
| Packages in the venv | Imported `streamlit` and `pandas` from `.venv` and printed `sys.prefix` | Prefix `...\lekha\.venv`; streamlit 1.66.1, pandas 3.1.0 |
| App starts | `GET /_stcore/health` | `ok` |
| Page content | Read the page text in a browser | Matched `app.py` |

---

## 2026-10-25: Design foundation (branch `design/manuscript-theme`)

Tested in the Claude desktop app's built-in browser (Chromium), against Streamlit 1.66.1 on Windows 11.

| Check | How | Result |
|---|---|---|
| Theme options exist in this version | `streamlit config show`, theme section | All options used are listed |
| Fonts load | Browser `document.fonts`, filtered to loaded faces | Lato 400 and 700, Lora 500 and 600 loaded |
| Fonts applied | Computed `font-family` of body text and hero title | Lato and Lora respectively |
| Page background | Computed background of `.stApp` | `rgb(245, 235, 221)` = Manuscript Paper |
| Info box colours | Computed colour and background of `st.info` | `#254D67` on `#E6EFF5`, radius 0 |
| No rounded corners | Script listing every visible element with `border-radius > 0` on Overview | None found |
| Colour contrast | Calculated WCAG ratios for every foreground/background pair | See `design-system.md`. Gold and Faded Rose fail as text and are kept decorative |
| Ornaments render | Size and background of each `.lekha-ornament` | Arch 140×210 in hero, 44×66 in empty states; rosette 120×24 in each divider |
| Desktop layout (1280px) | Measured element sizes | Hero 1110px wide, metric strip 4 equal columns, description lines capped at 672px |
| Phone layout (375px) | Mobile viewport, measured right edges, screenshot | No sideways scrolling; all sections end 16px from the edge; metrics stack in 1 column; hero ornament hidden |
| Placeholder page | Opened `/books` | Shows "Not built yet" and "Planned · Phase 3" |
| Keyboard focus | Tab to the first navigation link, read computed outline | See issue 3 |

### Issues found and fixed

1. **Ornaments missing.** Inline `<svg>` passed to `st.html` was removed by its HTML cleaning. An `<img>` with an SVG data URL was removed too. **Fix:** draw ornaments as CSS background images (see decision log). Re-checked: all seven ornaments render.
2. **Uneven columns.** In the Books/Inventory band, the "Shelf check" description wrapped to two lines and pushed its panel lower than its neighbour. **Fix:** shortened both descriptions.
3. **No visible keyboard focus.** Streamlit's navigation links had `outline: none` when focused (fails WCAG 2.4.7). **Fix:** a `:focus-visible` rule in `styles.css`. Re-checked: 2px solid crimson outline on the focused link.
4. **Large gap above the hero.** Streamlit's default 8rem top padding with top navigation. **Fix:** `paddingTop = "2rem"` in `config.toml`.
5. **Style edits not appearing.** `_read()` was cached with `@cache`, so edits to `styles.css` would not show until a restart. **Fix:** removed the cache. Files are tiny.

### Known limitations (not fixed)

- **Collapsed navigation is still reachable by Tab.** Below about 640px wide, Streamlit moves the navigation into a collapsed side menu, but its links can still receive keyboard focus while off screen. This is Streamlit's own behaviour. Patching it would need CSS that depends on Streamlit's internal markup.
- **Live reload not confirmed.** During this session, file edits only appeared after restarting Streamlit. The cause was not confirmed (it may be specific to the testing environment). If edits do not show up, stop the app with `Ctrl+C` and start it again.
- **Not tested:** other browsers (Firefox, Safari), screen-reader software, Windows high-contrast mode, 200% browser zoom.

---

## 2026-10-28: Database schema and sample data (branch `phase-2/database`)

SQLite 3.49.1, Python 3.13.3, pytest 9.2.0.

| Check | How | Result |
|---|---|---|
| Automated tests | `python -m pytest` | **44 passed** |
| Schema rules refuse bad data | `tests/test_schema.py`: duplicate ISBN, malformed ISBN, blank title, negative numbers, text in a number column, decimal price, six kinds of bad date, unknown status, sale line for a missing book or sale, zero/negative quantity, negative price, the same book twice in one sale, deleting a book that has sales | Every case raised `IntegrityError` |
| Rules don't block valid data | Valid sale accepted; NULL ISBNs and unknown cost allowed; book without sales can be deleted; schema can run twice | Pass |
| Tests can fail | Created the schema **without** `PRAGMA foreign_keys = ON` and inserted a sale line for book 999 | Accepted: shows the PRAGMA is essential and the foreign-key test guards it |
| Sample data matches hand calculations | `tests/test_sample_data.py` vs `docs/sample-data.md` | Revenue 1,114,400 paise; 14 transactions; 29 copies; per-book copies; low stock 2, 5, 9; no completed sales 10, 11, 12; old price kept for book 1 |
| Database builds from scratch | `python database.py --reset-sample` | 12 books, 15 sales, 23 sale lines |
| Practice queries | `python query.py sql\01_first_queries.sql`, each result compared with its "Expected" note | All 9 match |
| Database file not committed | `git status` | `data/lekha.db` ignored |

### Not covered yet

- Sale recording, stock updates and cancellation (Phase 4). The schema allows them, but the transaction logic doesn't exist yet.
- The app does not read from the database yet (Phase 3).

---

## 2026-11-08: Catalogue and inventory (branch `phase-3/catalogue`)

Streamlit 1.66.1, SQLite 3.49.1, pytest 9.2.0. Browser checks in the Claude desktop app's built-in browser (Chromium).

### Automated tests: **118 passed** (74 new)

| File | What it covers |
|---|---|
| `tests/test_money.py` | Exact rupee-to-paise conversion, including values where plain floats lose a paisa (19.99, 4.35, 0.57); rejecting negative, non-numeric and sub-paisa amounts; Indian digit grouping |
| `tests/test_books.py` | Search by title or author, ignoring case; genre filter; sorting; `%` and `_` matched literally; SQL typed into search treated as text; stock status words; adding with tidying, genre matching and optional fields; all errors reported at once; duplicate ISBN message; editing without touching stock; past sale prices unchanged after a price edit |
| `tests/test_inventory.py` | Low-stock list and count; a correction updates stock and history; invalid corrections refused with nothing saved; stale count refused; the same correction submitted twice applied once; a failure inside the transaction rolls back the stock update; the history table's own rules |

### Manual checks in the browser

| Check | Result |
|---|---|
| Books: search "menon" as you type | 2 of 12 books, both by Tara Menon |
| Books: search with no match | "Showing 0 of 12" and a hint |
| Books: sort by stock | Out-of-stock book first, then 1, then 2 copies |
| Add: title and a bad ISBN only | One box listing 4 problems; typed values kept |
| Add: genre typed "poetry", price 19.99 | Saved as genre "Poetry" (no new genre) and 1999 paise |
| Add: same title and author again | Saved, with a note naming the existing book |
| Edit: price of book 1 to ₹425 | 42500 paise saved; stock still 8; past sale lines still 34900 and 39900 |
| Inventory: save without changing the count | Refused: "nothing to correct" |
| Inventory: count book 1 as 5 (shelf count) | Stock 5; history row 8 → 5, −3, "Shelf count" |
| Inventory: stock changed in the database while the page showed 5, then saved 4 | Refused: "stock changed since the page was loaded"; stock stayed 7; no history row added |
| Overview: books low on stock | 3, matching the hand-checked sample data (books 2, 5, 9) |
| Overview: "Open Inventory →" | Opens the Inventory page |
| Rounded corners on Inventory | None found |

The database was rebuilt from the sample data afterwards, removing the test books and corrections.

### Issues found and fixed

1. **Add form didn't empty after saving.** Deleting the field values from `st.session_state` left the typed text on screen, so a second click would have added the book twice. **Fix:** a version number in the form's keys, increased after each save. Re-tested: the form empties.
2. **Two wrong expectations in my own tests.** I guessed a title order ("The…" before "Ten…") instead of working it out: the second letters are "e" and "h", so "Ten" comes first. I also claimed `349.99 * 100` goes wrong as a float; it happens not to. I checked which values really fail (19.99, 4.35, 0.57) and used those. Lesson: work expected values out, don't guess them.
3. **"None" shown for empty notes** in the correction history. **Fix:** show blank.
4. **The duplicate warning mixed two string-formatting styles**, which would crash on a title containing `{` or `}`. Fixed before testing.

### Not problems

- Opening a page address directly (for example `/books`) logs two "404 Not Found" errors, for `/books/_stcore/health` and `/books/_stcore/host-config`. Streamlit tries those first and then uses the main address. It is Streamlit's own start-up behaviour.
- In screenshots shrunk from 1280 to 800 pixels, minus signs and dashes in tables disappeared. At full size they display correctly.

### Not covered

- Automated tests of the pages themselves. The rules are tested; the pages were checked by hand.
- Two people using the app at the same moment, beyond the stale-count check.

---

## 2026-11-08: Sales (branch `phase-4/sales`)

Streamlit 1.66.1, SQLite 3.49.1, pytest 9.2.0. Browser checks in the Claude desktop app's built-in browser (Chromium).

### Automated tests: **145 passed** (27 new, in `tests/test_sales.py`)

| Area | What is checked |
|---|---|
| Recording | Selling 2 copies saves the sale and its line at the shown price, reduces stock by exactly 2, and adds exactly 79,800 paise to completed revenue; multi-book sales; selling the last copies; combining lines for the same book; dating a sale in the past |
| Refusals change nothing | Not enough stock; out of stock; the **second line failing after the first line's stock update** (rollback); a changed price; a missing book; an empty sale; zero, negative, decimal and true/false quantities; a future date; the same book at two prices. Each compares a snapshot of sales, lines, cancellations and all stock counts before and after |
| Cancelling | Stock returned exactly; status, time and reason recorded; revenue back to 1,114,400 paise; a second cancel refused with stock unchanged; a reason required; a missing sale; a failure in the last step rolls back the status change and the stock refund; the database refuses a second cancellation record |
| Listing | Newest first; per-sale copies, totals and line counts match the hand-checked sample data |
| Consistency | Every cancelled sale has exactly one cancellation record, and every record belongs to a cancelled sale |

**Can the tests fail?** I loaded a copy of `record_sale` in memory with the rollback removed. A two-line sale where the second line is short then left book 1's stock at 6 instead of 8 and an extra sale row behind. The rollback test checks both, so it would fail.

### Manual checks in the browser

| Check | Result |
|---|---|
| Add 2 × *The Monsoon Ledger* and 1 × *Small Hours* | Basket shows ₹798.00 + ₹225.00 = ₹1,023.00, 3 copies |
| Complete sale | "Sale #16 recorded: 3 copies, ₹1,023.00"; basket emptied; in the database: 2 lines at 39900 and 22500, stock 8 → 6 and 4 → 3 |
| Recent sales | Sale #16 at the top; older totals match the sample data (sales 11–14) |
| Cancel without ticking the confirmation | Refused; typed reason kept |
| Cancel with confirmation | "Copies returned to stock: The Monsoon Ledger (2), Small Hours (1)"; stock back to 8 and 4; cancellation time and reason recorded; completed revenue back to 1,114,400 paise |
| Choose an out-of-stock book | Warning, and no quantity field or Add button |
| "This sale happened earlier" | Date and time fields appear (today, current time) |
| Clear sale | Basket emptied; nothing saved |

### Issues found and fixed

1. **A stray horizontal line above the Remove buttons.** The empty heading for that column became `****` in Markdown, which draws a line. **Fix:** no heading for that column.
2. **Cancel-sale stock refund** was first written as one SQL statement with a nested query. It worked, but was hard to explain, so it was rewritten as a plain loop over the sale's lines. Tests unchanged and passing.

### Known limitations

- Totals in the Recent sales table show as ₹1023.00, without the thousands comma used elsewhere (₹1,023.00). Streamlit's number formats have no rupee option with Indian grouping, and turning totals into text would break sorting by total.
- No partial returns or discounts.
- Refreshing the browser loses an unfinished basket.
- The local database still contains test sale #16 (recorded, then cancelled). It doesn't count as revenue. `python database.py --reset-sample` removes it.

---

## 2026-11-08: Analytics (branch `phase-5/analytics`)

Streamlit 1.66.1, Altair 6.3.0, SQLite 3.49.1, pytest 9.2.0. Browser checks in the Claude desktop app's built-in browser (Chromium).

### Automated tests: **179 passed** (34 new, in `tests/test_analytics.py`)

Every expected value was worked out by hand first (see `docs/analytics.md`): headline figures, the Mystery filter, an empty period, cancelled sales excluded, both date edges, all six genres and their rounded shares (summing to 100.2%), all nine books' copies, revenue and tied ranks, unsold books for three periods, estimated profit with coverage and margin, weekly buckets with partial flags, zero-filled days, the monthly bucket, the in-progress current week, all period choices (including "last month" in January), and the wording of observations.

### Manual checks in the browser

| Check | Result |
|---|---|
| Insights, last 30 days (10 Oct – 8 Nov) | ₹6,948.00, 17 copies, 8 sales, average ₹868.50. **Checked by hand**: sales 7, 8, 10–15 |
| Genre chart, last 30 days | Fiction ₹2,544.00 (36.6%) … Poetry ₹250.00; totals ₹6,948.00; note says shares add to 99.9% |
| Trend chart, last 30 days | Week of 5 Oct outlined (period starts 10 Oct); week of 2 Nov outlined (in progress, ₹0) |
| Insights, all time | Every figure matches `docs/analytics.md`: ₹11,144.00, 29, 14, ₹796.00, all genres, profit ₹3,992.00 at 39.0% on 92.0% of revenue |
| Mystery filter | ₹2,034.00, 6 copies, 4 sales; trend recalculated; genre chart stays on all genres and says so; profit ₹804.00 at 39.5% (checked by hand) |
| Overview | Last-30-day figures identical to the Insights page; weekly chart shown |
| Screen readers | Each chart's alt text reaches its toolbar buttons; each bar is announced with its period, revenue, copies, sales and completeness |
| Phone width (375px) | No sideways scrolling, nothing past the edge, no rounded corners |

### Issues found and fixed

1. **Genre chart labels cut off on phones.** "₹2,544.00 · 36.6%" lost its end at 375px. **Fix:** extend the value scale to 1.8× the largest bar to leave room for labels. Re-checked on a phone-sized screen.
2. **One figure in a four-column strip.** The profit figure would have filled a quarter of its box. **Fix:** a single-figure strip spans the full width.
3. **Ambiguous labels with a genre selected.** "Per sale that included Mystery" became "Mystery revenue ÷ sales that included it", and "Every book had at least one sale" became "Every Mystery book…".
4. **Month names lowercased** ("10 oct") in the Overview description. Fixed before release.
5. **Limits shown in faded caption text** were switched to normal text, so they aren't harder to read than the finding.
6. **One wrong test expectation (mine):** I assumed tied best sellers are listed alphabetically. They're listed by revenue, so *The Clockmaker's Cat* (₹897.00) comes before *Ten Thousand Mangoes* (₹825.00).
7. **A claim in my design notes was wrong:** the week of 26 Oct is only partial when the period ends on 26 Oct. Corrected in `docs/analytics.md`.

### Known limitations

- Western digit grouping inside Streamlit tables and chart axes (₹1,047.00) versus Indian grouping in text; identical below one lakh.
- No comparison with a previous period.
- The 30-sale "hint, not a pattern" threshold is a judgement call, not a statistical test.

---

## 2026-11-08: Visual refinement (branch `phase-6/refinement`)

Streamlit 1.66.1. Browser checks in the Claude desktop app's built-in browser (Chromium) at 1280px and 375px.

### Method

A script run in the browser on every page: for each visible piece of text (including chart text drawn as SVG), it finds the real background colour, allows for transparency, calculates the WCAG contrast ratio, and compares it with 4.5:1 (3:1 for large text). It also lists headings and any text under 12px, and measures placeholder text separately. Tables are drawn on a canvas, so the script can't read them; they use the theme's text colours, which pass.

### Before and after

| Page | Before: contrast failures | After | Lowest ratio after |
|---|---|---|---|
| Overview | 15 (chart axis text, 3.15:1) | **0** | 4.82 (gold label on the wine hero) |
| Books | 0 (placeholders 3.89:1, measured separately) | **0** (placeholders 6.61:1) | 5.99 |
| Sales | 0 (placeholders 3.89:1) | **0** (6.61:1) | 5.99 |
| Inventory | 0 (placeholders 3.89:1) | **0** (6.61:1) | 5.99 |
| Insights | 22 (chart axis text, 3.15:1) | **0** (placeholders 6.61:1) | 5.99 |

Headings: one h1 per page, h2 for each section, no skipped levels. No text under 12px.

### Visual checks

| Check | Before | After |
|---|---|---|
| Sales basket at 375px | Headings and values stacked as separate lines; numbers detached from labels | Each line reads "The Monsoon Ledger / 1 copy × ₹399.00 = ₹399.00" with its Remove button |
| Sales basket at 1280px | Five-column grid | Sentence lines with Remove buttons aligned right; total below |
| Low-stock table at 375px | Status hidden behind sideways scroll | Title and Status visible without scrolling |
| Inventory opening at 1280px | Notice pressed against the first heading | 40px gap after the notice, same on every page |
| Sample-data notice at 375px | "fictional." dropped below the tag | Sentence wraps beside the tag |

`python -m pytest`: 179 passed (no rules changed).

### Still not fixed (documented limits)

- Western digit grouping inside tables and chart axes.
- Collapsed navigation reachable by Tab on narrow screens (Streamlit behaviour).
- Not tested: screen-reader software, Firefox, Safari, 200% browser zoom.

---

## 2026-11-08: Quality and portfolio (branch `phase-7/portfolio`)

### Automated tests: **192 passed** (13 new)

| File | Tests | What it covers |
|---|---|---|
| `tests/test_pages.py` | 11 | Streamlit's `AppTest` runs the pages without a browser, each against its own copy of the sample data (via `LEKHA_DB_PATH`): Books, Sales, Inventory and Insights open with no error and show the sample-data notice; the whole app opens on the Overview without the old message; **2 copies of book 1 sold through the Sales page: stock 8 → 6 and "Sale #16 recorded: 2 copies, ₹798.00"**; an out-of-stock book offers no Add button; search "menon" shows 2 of 12; a stock correction through the Inventory form saves 8 → 5; Insights "All time" shows ₹11,144.00, ₹796.00 and ₹3,992.00; **a corrupt database file shows the friendly message, not a traceback** |
| `tests/test_demo_data.py` | 2 | The demo dataset is identical on every run, has 30 books, more than 300 completed sales, some cancellations, no negative stock, status and cancellation records that agree, and exactly 2 unsold books |

**On GitHub:** the workflow `.github/workflows/tests.yml` ran all tests on a fresh Linux machine with Python 3.13: every step passed.

### Issues found and fixed

1. **The Overview can't be tested on its own.** Its links to other pages need `app.py`'s navigation, so `AppTest` raised "Could not find page". **Fix:** test the Overview through `app.py`, which opens on it by default.
2. **A form test saved nothing.** The test pressed `run()` between typing a number and clicking Save; inside a form, typed values only count on submit. **Fix:** type and submit in one step, as a person would. The app was fine; the test was wrong.
3. **Headless Edge screenshots showed only Streamlit's loading skeleton.** The page content arrives after "load" over a live connection. **Fix:** Playwright drives Edge and waits until Streamlit reports it has finished running the page.
4. **Streamlit's "Deploy" button appeared in every screenshot.** **Fix:** `toolbarMode = "viewer"` in `config.toml` hides developer controls.

### Screenshots

Seven screenshots in `docs/screenshots/` (desktop at 1280px, phone at 390px), captured by `scripts/capture_screenshots.py` from the demo dataset. Each was opened and checked by eye: the right page, fully drawn, the sample-data notice visible, no developer controls.

*Superseded on 2026-11-10: the demo dataset and these screenshots were removed; see below.*

---

## 2026-11-10: Real books from Open Library, real data only (branch `phase-8/real-books`)

### Automated tests: **225 passed**

| File | Tests | What it covers |
|---|---|---|
| `tests/test_openlibrary.py` | 31 | Replaying **real Open Library responses** saved on 2026-11-08: ISBN lookup of *The God of Small Things* (Flamingo, 1998, cover 10585942, edition `/books/OL31903694M`); hyphens accepted; unknown ISBN returns nothing; malformed ISBNs refused **before** any request; title search returns works with author and first-published year; no ISBN or edition facts invented for a work; plain messages for "unreachable" and "busy"; genre suggestions (including "Historical fiction" staying Fiction); saving and editing keep the book details; bad details refused by both Python and the database; migrating a Phase 7 database keeps its book and runs only once |
| `tests/test_pages.py` | 15 (4 new) | An empty shop's Overview shows real zeros and where to start; the empty Books page; **adding a real book by ISBN through the page** (form pre-filled, price left empty, saved row has exactly Open Library's details plus the entered price and stock); searching Open Library lists real matches and leaves ISBN and publisher empty for a work |
| `tests/test_demo_data.py` | removed | Demo dataset deleted |

### Live checks against the real Open Library (browser, 2026-11-10)

Done on the real, empty shop. Books were looked up and **never saved**, so no price or stock was invented.

| Check | Result |
|---|---|
| ISBN 978-0-14-303965-5 (not in the saved test files) | *Malgudi days*, Rasipuram Krishnaswamy Narayan, Penguin Books, 2006, genre suggested Fiction; Open Library has no cover for it, so none shown; price and cost empty |
| Search "Shyam Selvadurai Funny Boy" | 7 matches with real covers; the first is the French translation *Drôle de garçon*, a reminder to check before choosing |
| "Start again" | Discarded the lookup; the shop still has 0 books |

### Issues found and fixed

1. **A "made-up" ISBN was real.** `9780000000002`, chosen for a "not found" test, is a real 1985 book on Open Library. **Fix:** confirmed `9790000000001` returns nothing, and used that.
2. **The test helper missed encoded addresses.** `ISBN:` is sent as `ISBN%3A`. **Fix:** decode before matching.
3. **Docs edits mangled backslashes** in two Windows paths in `docs/setup.md` (`\01` became a control character). **Fix:** corrected by hand, and both files checked for stray control characters.
4. **Screenshots missed the covers.** Open Library's image server is slower than the page. **Fix:** the script waits until every image has loaded.
5. **A screenshot step matched two elements** ("Title or author" also appears in "Search by title or author"). **Fix:** exact label match.

### Screenshots

Four screenshots in `docs/screenshots/`, captured from the real, empty shop and live Open Library: the Overview (real zeros), an ISBN lookup, and a title search (desktop and phone). Each checked by eye. No fictional data appears in any of them.

---

## 2026-11-10: Accounts, shared shops and roles (branch `phase-9/accounts`)

### Automated tests: **271 passed**

| File | Tests | What it covers |
|---|---|---|
| `tests/test_accounts.py` | 39 (new) | Passwords stored only as scrypt hashes, different each time for the same password; bad usernames, names and short passwords refused; usernames unique ignoring case; a wrong password and an unknown username give the same message; 5 wrong passwords lock the account and a correct one resets the count; one Lekha account per Google ID; Google-only accounts can't sign in with a password; changing a password; creating a shop makes you its owner; every role's permissions; invite codes shown once, stored hashed, single-use, expiring, revocable; staff refused owner actions; outsiders refused everything; a shop always keeps an owner; one person in several shops; **two shops never see each other's books**; **two visitors at the same moment each see only their own shop** (two threads); sales, cancellations and corrections record who; older records have no recorder; `--reset` deletes accounts and shop files and nothing else |
| `tests/test_pages.py` | 22 (7 new) | Signed-out visitors see only the sign-in page; **sign up, create a shop and land on its Overview** with the "shop is ready" message; a wrong password refused on the page; each person sees only their own shop; **removed staff lose access on their next click**; staff see no Edit tab, no stock correction, no profit and no Team page; a broken accounts database shows a friendly message |
| `tests/test_openlibrary.py` | 31 | Migration tests now expect version 2 |

### Browser check (2026-11-10)

Run on a copy of Lekha using a **temporary data folder** (`LEKHA_DATA_DIR`), with test accounts, deleted afterwards. Nothing touched the real `data/` folder.

| Check | Result |
|---|---|
| Open the app signed out | Only the sign-in page; no menu |
| Create an account (owner) | Lands on "Your shops" with the account bar |
| Start a shop | Overview of the new, empty shop; the bar shows the shop and "owner"; all seven pages in the menu |
| Team → staff invite code | Code shown once (`XXXXX-XXXXX`) with its expiry; listed under "Codes not yet used" |
| Second tab: create a staff account, join with the code typed **in lowercase without the dash** | Joined; Overview shows "You've joined the shop"; bar shows "staff" |
| Staff menu | Overview, Books, Sales, Inventory, Insights, Settings: no Team |
| Staff on Books | Tabs "Browse" and "Add a book" only |
| Staff on Inventory and Insights | Low-stock alerts only, no correction or history; no profit section |

### Issues found and fixed

1. **"Your shop is ready" appeared on the wrong page.** The Overview never showed waiting messages, so it popped up on whichever page was opened next (Team, in the browser check). **Fix:** the Overview shows it; the sign-up page test now checks for it.
2. **Staff were told about things they can't do.** The Inventory intro offered "a recorded way to correct stock counts", and the Overview said "edit the catalogue". **Fix:** both now depend on the role.
3. **`database.py --reset` reset a file the app no longer reads.** **Fix:** it now deletes the accounts and shop files, after asking; a test checks it leaves other files alone.
4. **The screenshot script broke with sign-in.** It opened pages by address, which now shows the sign-in page, and reloading a tab ends a password sign-in. **Fix:** it signs in (username and password from environment variables, never a file) and follows menu links. Tried on a throwaway shop: all four pictures were drawn signed in; the first ISBN picture was taken before the form appeared, so the script now waits for it. The throwaway pictures were discarded.
5. **Jumping to the Overview after creating a shop couldn't work.** `st.switch_page` only goes to pages in the current menu, and for someone with no shop yet, the menu holds only Get started. **Fix:** the page sets a flag and reruns; `app.py`, which knows the full menu, opens the Overview.
6. **A migration test hard-coded version 1.** **Fix:** a single `LATEST_VERSION` constant.
7. **A test's `match=""` accepted any error message.** **Fix:** the exact message is checked.

### Not yet checked

- **Google sign-in with real Google credentials.** The account rules behind it are tested, and the button only appears once credentials are set up; the round trip to Google needs those credentials first (see `docs/setup.md`).

---

## 2026-11-10: Security hardening (branch `security/hardening`)

### Automated tests: **307 passed**

| File | Tests | What it covers |
|---|---|---|
| `tests/test_security.py` | 26 (new) | `ui.plain()` shows maths, emphasis, picture links, links, Streamlit colours and icons, headings and lists exactly as typed, and stops bare web addresses becoming links; the attempt limiter blocks after its limit and forgets after its window; wrong current passwords lock the account; a new password must differ; the credential stamp changes with the password and is absent for Google accounts; a 1,000,000-character password is cut to 129 characters before hashing; long Google names shortened; a short cookie secret keeps Google sign-in off; overlong book details, reasons and notes refused; only `https://openlibrary.org` is fetched (not `file://`, `http://`, or a look-alike host); oversized answers refused; search results with bad record IDs, non-text titles or odd cover numbers ignored; overlong searches refused; the server settings stay safe; `secrets.toml` stays ignored by git |
| `tests/test_accounts.py` | 45 (6 new) | New password rules: can't contain the username or be the person's name, common and one-character passwords refused, 128-character maximum, 60-character name maximum |
| `tests/test_pages.py` | 26 (4 new) | **A password change signs out another tab on its next click**; an idle tab is signed out with a message; failed sign-ins from one device are refused even with the right password once the limit is reached; a display name full of Markdown shows as typed in the account bar |

### Scans

| Check | Result |
|---|---|
| `pip-audit -r requirements.txt` | No known vulnerabilities |
| `bandit` on all of Lekha's code | 8 possible issues before the review (7 SQL f-strings, 1 `urlopen`). All read and found safe; the `urlopen` check was also made stricter. Each line now marked with its reason; the scan passes |

### Browser check (2026-11-10)

On a throwaway copy with a temporary data folder, deleted afterwards. The test account's name was `**Boss** :red[owner] $5`, its shop `Books & $ales #1 ![x](https://example.com/p.png)`, and its book `The $100 *Startup*: :fire: [read](https://example.com)`.

| Check | Result |
|---|---|
| Account bar | Name and shop shown exactly as typed: no bold, colour, maths, picture or link |
| Stock correction message quoting the title | Shown as typed: no italics, emoji or link |
| Which addresses Lekha listens on | Only `127.0.0.1` |

### Issues found and fixed

1. **Escaped names still became links.** The first version escaped Markdown, but Streamlit still turned a bare `https://…` in a shop name into a clickable link. **Fix:** an invisible word joiner (U+2060) after `https`, `www` and similar; a test covers it.
2. **The device limit didn't work in the page test.** In Streamlit's test runner, the visitor's address is a placeholder object, different on every run. **Fix:** `network_address()` accepts only real text, otherwise "unknown". It's safer in real use too.
3. **A `# nosec` marker ended up inside an SQL string** while marking reviewed queries, which would have broken the search. Caught before running; a small experiment showed bandit accepts the marker after the closing `"""`.
4. **bandit read the explanation after `# nosec` as test names** and printed dozens of warnings. **Fix:** the reason goes on the line above.
5. **Tests compared raw Markdown.** After escaping, `Sale #16` became `Sale \#16`. **Fix:** a `shown()` helper compares the text as a person reads it.

---

## 2026-11-12: Redesign foundations (branch `redesign/foundations`)

### Automated tests: **373 passed**

The new calculations were written test-first: every test below existed, and failed, before its code.

| File | Tests | What it covers |
|---|---|---|
| `tests/test_comparisons.py` | 22 (new) | Whole-rupee amounts with Indian grouping (₹1,11,444), rounded half up; revenue compared as "12% more than ₹43,080", down as "less", under 1% as "about the same"; **no comparison at all when the earlier figure is zero**; counts as a percentage or a difference ("25 more than 140"); neutral "₹308 before"; "₹1,620 by this time last Thursday" |
| `tests/test_sentences.py` | 21 (new) | Overview's sentence for a brand-new shop, books without sales, and every mix of today's sales and books to reorder (1 book, 137 books, nothing); Insights' sentence for no sales, too little history, rises, falls, about the same, one genre, nothing to compare against; "Showing 5 of 137" |
| `tests/test_time_windows.py` | 8 (new) | Today so far stops at now; **the same time last week stops at the same minute** (a sale at exactly that minute is left out); the week starts on Monday; cancelled sales never count; the period before has the same length; days of history |
| `tests/test_components.py` | 13 (new) | The page header has one h1 and no label above it; names in the date line are escaped; a good or bad change gets a drawn arrow, a neutral one none; a missing figure is a dash that screen readers hear as "No data yet"; unknown tones and status kinds are refused; a missing cover shows the title's first letter |
| `tests/test_pages.py` | 28 (2 new, 1 rewritten) | The account menu's label shows Markdown in names as typed and cuts long names to 24 characters; Switch shop lists every shop, marks the open one and opens the chosen one. The text helper now reads HTML as a person would (`&#x27;` as `'`) |

### Browser check (throwaway data folder, port 8502)

Created an account and a shop, then checked the navigation: the five daily pages, and "Asha · Kitab Ghar" as a menu holding Team, Settings, Start or join a shop and Sign out (Switch shop correctly absent with one shop). Settings opened from the menu; Sign out returned to the sign-in page. The data folder was deleted afterwards.

### Issues found and fixed

1. **Wrong weekday in my own test data and on the canvas.** I'd assumed 12 November 2026 was a Wednesday; it's a Thursday. The test caught it (a "Sunday" sale was really Monday, inside the week). **Fix:** the test data names the right days; the canvas's "Wednesday" was corrected too.

### Noted, not changed

- **The account menu sits straight after the page links, not at the far right of the bar.** Streamlit places navigation sections in order; moving it would mean drawing our own navigation, which isn't worth losing Streamlit's built-in phone menu for.


---

## 2026-11-12: Sign in and Get started (branch `redesign/signin-get-started`)

### Automated tests: **378 passed**

Written before the pages changed, and failing first:

| File | Tests | What it covers |
|---|---|---|
| `tests/test_components.py` | 15 (2 new) | The sign-in wordmark is the page's one h1, with its tagline; a card heading is an h2 with escaped text and no label above it |
| `tests/test_pages.py` | 31 (3 new) | Sign in has no label above its heading and the new note; with Google not set up there's no Google button or Google line; with it set up, Google is a plain (secondary) button so the password form's button leads; Get started has the page header and both card headings, and none of the old labels |

### Browser check (throwaway data folder, port 8502)

- **Desktop:** Sign in matches the canvas (centred name, one 400px card, tabs, full-width button, note). Created an account through the Create an account tab, with a 26-character name: it landed on Get started, and the account menu cut the name short ("Venkatalakshmi Subraman…"). Get started shows two cards side by side.
- **Phone (375px):** the sign-in card fills the width with even margins; the Get started cards stack.
- **Keyboard only:** typed the username, Tab to the password, Enter signed in. Tab from Shop name reaches Create shop, with a visible focus ring.
- The data folder was deleted afterwards.

### Not yet checked

- Google sign-in end to end (it still needs `.streamlit/secrets.toml`). Its button's place and style are covered by a test.

---

## 2026-11-12: Overview (branch `redesign/overview`)

### Automated tests: **401 passed**

Written before the code, and failing first:

| File | Tests | What it covers |
|---|---|---|
| `tests/test_overview_data.py` | 15 (new) | The reorder list carries each book's cover; the latest sales are newest first, with their books in words ("Malgudi Days ×2, Train to Pakistan"), cancelled sales marked, older ones left out; this week's best sellers count only Monday to now and know which sold out; sale times read "16:45", "Yesterday 18:05" or "5 Nov 10:00"; the shelf's note names sold-out books |
| `tests/test_components.py` | 20 (5 new) | Tables escape plain text and keep built HTML; numbers are right-aligned; a cover image has an empty alt (the title is beside it), a missing one shows its letter; "Sold out" is said in words; the phone list says "0 left · reorder at 3" |
| `tests/test_pages.py` | 34 (3 new, 3 changed) | Overview for a new shop (steps, "None yet", no empty cards) and a trading one at a fixed Thursday 16:45 (the sentence, "₹250 by this time last Thursday", all three cards); a book called `<b>Bold</b> & Co` shows as typed. Three older tests now look for the new welcome sentence |

One test was wrong, not the code: two books tied on copies, and Insights' rule puts the one that brought in more money first.

### Browser check (throwaway data folder, port 8502)

Filled a throwaway shop with seven books and 50 days of sales, then signed in.
- **Desktop:** matches the canvas. Today compared with the same time last Thursday; the last 30 days showed "48% more than ₹12,789, compared with 14 Sep to 13 Oct"; the reorder table, latest sales (a cancelled sale marked) and the shelf with a real Open Library cover.
- **Phone (375px):** today, the last 30 days and the reorder list as a list; nothing left behind where the hidden cards were.
- **Keyboard only:** Tab reaches See all in Inventory, All recent sales and See trends in Insights in reading order, each with a visible focus ring.
- The data folder was deleted afterwards.

### Issues found and fixed

1. **The shelf sat indented inside its card.** Streamlit gives every list 32px of left padding. **Fix:** the shelf's own rule is more specific.
2. **"All 2 shown."** appeared under a two-book reorder list. **Fix:** the line appears only when the list is cut short.
3. **A wrong cover in my check data.** I'd typed a cover number for Malgudi Days that belongs to another book. The app was right; the check data was wrong. The tests now use an obviously made-up number that is never fetched.

### Not yet checked

- Overview for staff (they can see everything on it today; the links check permissions anyway).

---

## 2026-11-13: Sales, the till (branch `redesign/sales`)

### Automated tests: **422 passed**

| File | Tests | What it covers |
|---|---|---|
| `tests/test_till.py` | 16 (new) | Search: one title match, every book by an author, an ISBN typed with dashes finds exactly that book, an unknown ISBN finds nothing, an empty search finds nothing (not the whole catalogue), a few shown and the rest counted. Basket: adding twice makes two copies, an out-of-stock book is refused with the reason, never more copies than the shelf ("Only 2 copies of The Guide are in stock, and both are in this sale."), one more and one fewer (stopping at one), remove and clear, sale lines at the price shown. "Recorded as now…" and an earlier time. Recent sales list every sale with its copies |
| `tests/test_pages.py` | 39 (7 new, 2 replaced) | Through the whole app: a sale from search to scan to + to Record sale to Undo (stock back, sale cancelled not deleted); several matches; no match; out of stock; the basket stopping at the shelf; a staff member's sale recorded under their name; Recent sales listing the books and cancelling with a reason |

The till's tests were written first and failed first (the module didn't exist). The page tests were written before the new page, but I didn't run them against the old one; they can't pass there, as it has no Find a book box.

### Browser check (throwaway data folder, port 8502)

- **Desktop:** "narayan" listed two books with Add buttons; Add put The Guide in the sale; typing Malgudi Days' ISBN and Enter added it at once; "train" and Enter added Train to Pakistan. Ctrl + Enter from the search box recorded the sale; the notice offered Undo; Undo cancelled it and Recent sales showed it as Cancelled. "Change date or time" set the sale to the day before ("Recorded as Thursday 12 Nov, 00:05").
- **Phone (375px):** search, then the sale card; each line wraps its total and Remove under the title. Recent sales scrolls sideways, one line per sale.
- **Keyboard:** typing, Enter and Ctrl + Enter run the whole sale without the mouse; focus stays in Find a book after each book, ready for the next scan.
- The data folder was deleted afterwards.

### Issues found and fixed

1. **"Ctrl + Enter" appeared twice.** Streamlit prints the shortcut inside the button; my note under it repeated it. **Fix:** the note is gone.
2. **Streamlit's "Press Enter to submit form · 0/100" ran over the placeholder on a phone.** **Fix:** hidden for the till's search box only.
3. **Recent sales squashed on a phone** (dates and titles wrapped a word per line). **Fix:** tables keep a minimum width and scroll sideways; Recent sales keeps each sale on one line.
4. **My check data's ISBN never saved.** My script didn't commit; the till correctly said "No book matches". Fixed in the check data, not the app.

### Not yet checked

- A real barcode scanner (it types digits and presses Enter, which is what the check did by hand).

---

## 2026-11-13: Books (branch `redesign/books`)

### Automated tests: **437 passed**

Written before the code, and failing first:

| File | Tests | What it covers |
|---|---|---|
| `tests/test_books.py` | 35 (2 new) | The catalogue can be searched by ISBN, with or without dashes; a short number isn't treated as an ISBN |
| `tests/test_sentences.py` | 27 (6 new) | The line under the catalogue: "12 books.", "1 book.", "Showing 2 of 12 books.", the first 100 of 2,000, the first 100 of 150 matches, and what to try when nothing matches |
| `tests/test_components.py` | 25 (5 new) | Stock in words for 0, at, below and above the reorder level; a phone list escapes its details |
| `tests/test_pages.py` | 41 (2 new, 4 changed) | Books searched by ISBN; the header button and "Add your first book" both open Add a book; the ISBN lookup and Open Library search tests now find their boxes and buttons by name, not by position |

### Browser check (throwaway data folder, port 8502)

- **Desktop:** the table, statuses and header button match the canvas. Add a book opened on the ISBN lookup; a real lookup (978-0-00-655068-6) on Open Library showed the cover and "Found on Open Library. The God of Small Things · Arundhati Roy · Flamingo, 1998"; with a price and stock it was added. Searching Browse by that ISBN found it, with its cover and "Showing 1 of 8 books."
- **Phone (375px):** the list with "author · ₹price · copies in stock" and the status, as on the phone artboard.
- **Keyboard:** Tab goes from the header's Add a book, to the tabs, to the search box.
- The data folder was deleted afterwards.

### Issues found and fixed

1. **The Open Library link was the browser's default blue.** **Fix:** links inside Lekha's own HTML take the theme's teal.
2. **Long author names hid the price on a phone** ("Rabindranath Tagore · ₹30…"). **Fix:** the detail line wraps in phone lists.
3. **A script edit was interrupted** when the session ended; I checked the page had been rewritten before carrying on.

---

## 2026-11-13: Inventory (branch `redesign/inventory`)

### Automated tests: **444 passed**

Written before the code, and failing first:

| File | Tests | What it covers |
|---|---|---|
| `tests/test_sentences.py` | 32 (5 new) | The low-stock note ("1 book.", "All 6 shown, emptiest first."); the correction line for a loss (−1, with a real minus sign), a gain (+6) and a matching count |
| `tests/test_pages.py` | 43 (2 new, 3 changed) | The correction line appears before saving and shows the new count after; a matching count leaves Save off; a shop with nothing low says "Nothing to reorder." and "No corrections yet."; staff see the low-stock card but neither correction card |

### Browser check (throwaway data folder, port 8502)

- **Desktop:** low-stock card matches the canvas. Chose Gitanjali (0 in stock): Save stayed off until the count changed. Typed 4 and chose "Delivery received": the line read "+4"; saving recorded it in Recent corrections, and Gitanjali left the low-stock list.
- **Phone (375px):** the low-stock list, then the correction form; Recent corrections scrolls sideways.
- **Keyboard:** the Book and Reason lists can be chosen by typing and Enter; Tab moves between the fields.
- The data folder was deleted afterwards.

### Issues found and fixed

1. **The Book list kept saying "Gitanjali · 0 in stock" after the delivery made it 4.** Streamlit keeps the chosen option's wording. **Fix:** the options show title and author; the line under the count says Lekha's current count. A test now checks the line shows the new count after saving.
2. **That line repeated itself** ("Lekha has 4 in stock. That matches Lekha's count…"). **Fix:** one sentence: "Lekha has 4 in stock too, so there's nothing to record."
