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
