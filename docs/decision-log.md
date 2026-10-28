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
