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
