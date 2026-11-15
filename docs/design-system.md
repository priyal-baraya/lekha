# Design system

Lekha is a calm, light analytics tool for an independent bookshop. The identity comes from the manuscript palette (crimson on parchment), Lora headings and Indian number formats; usability comes from one job per page, plain words and very little text. Approved on the design canvas on 12 November 2026 and built page by page in Phase 4 (see [redesign-plan.md](redesign-plan.md)).

**Where things live**

| What | File |
|---|---|
| Theme (colours, fonts, radius, borders, chart colours) | `.streamlit/config.toml` |
| Tokens and styles Streamlit has no setting for | `ui/styles.css` (`:root` holds every token) |
| Functions that write the styled page pieces | `ui/components.py` |
| The Insights chart | `ui/charts.py` |
| The approved designs | The "Lekha redesign" canvas, one artboard per page and state |

## Principles

- **One job per page.** Overview is today and what to do; Sales is the till; Books is the catalogue; Inventory is stock; Insights is trends; Team and Settings are the shop's people and setup.
- **Headings and numbers.** No line under page titles or card headings; no label above a heading. A line stays only when it says something the screen doesn't (for example "Shown once. Works once, for 7 days." under a new invite code).
- **Say it in words.** Overview and Insights open with one sentence built from the figures by fixed rules (`services/sentences.py`), never invented. Status is a word ("Low", "Out of stock", "Doing well"), with colour only reinforcing it.
- **Fair comparisons.** A figure is compared only with a like period, and the earlier figure is named ("12% more than ₹43,080"). With nothing fair to compare against, no change is shown.
- **Nothing fake.** Real data only; empty states say what's missing instead of showing invented examples.

## Colour

| Token | Hex | Use |
|---|---|---|
| Manuscript Crimson `--lekha-crimson` | `#791A24` | Primary actions, selected states, the latest bar in a chart, focus outlines |
| Crimson 50 `--lekha-crimson-50` | `#F6E8E4` | Selected backgrounds (the first step's number, the chosen option in a group of buttons) |
| Persian Teal `--lekha-teal` | `#263F3C` | Links |
| Manuscript Paper | `#F5EBDD` | Page background |
| Porcelain Paper `--lekha-porcelain` | `#FBF7F0` | Cards and figure strips |
| Field `--lekha-field` | `#FFFDF9` | Inside text fields; the invite code |
| Aged Parchment `--lekha-parchment` | `#E3D1B2` | Card borders, row dividers, chart grid lines |
| Border Taupe `--lekha-border` | `#8C7A68` | Field outlines and table header rules (they must reach 3:1, WCAG 1.4.11) |
| Sepia Ink `--lekha-ink` | `#352821` | Text and headings |
| Secondary Text `--lekha-ink-secondary` | `#67554A` | Labels, notes, axis text |
| Earlier bars `--lekha-chart-past` | `#C4767E` | Earlier periods in the Insights chart; the quieter genres when one is chosen |

**States** (always with a word, never colour alone):

| State | Text | Background | Where |
|---|---|---|---|
| Success | `#215C42` | `#E5F1E8` | "In stock", "Doing well", messages after saving |
| Warning | `#704A0E` | `#F8EBCB` | "Low", "Worth a look", the remove-someone question |
| Error | `#B42318` | `#FBE9E7` | "Out of stock", errors. Kept well apart from crimson, so an error never reads as branding |
| Information | `#254D67` | `#E6EFF5` | "To keep in mind", the Owner tag |
| Neutral | `#67554A` | `#EFE3D1` | The Staff tag |

**Chart colours** (in `config.toml`): one series uses crimson; several use madder, peacock, turmeric and indigo, in that order, checked for colour-blind separation. A fifth series becomes "Other".

### Measured contrast (WCAG 2.2 AA: 4.5:1 for text, 3:1 for large text and UI parts)

| Pair | Ratio |
|---|---|
| Sepia Ink on Paper / on Porcelain | 12.06 / 13.32 |
| Secondary Text on Paper / on Porcelain | 5.99 / 6.61 |
| Crimson on Paper / on Porcelain / on Crimson 50 | 8.97 / 9.90 / 8.85 |
| Teal on Paper / on Porcelain | 9.58 / 10.58 |
| Border Taupe on Paper / on Porcelain (UI outline) | 3.49 / 3.86 |
| Earlier bars on Porcelain (graphic) | 3.15 |
| Success, warning, error, information, neutral tags | 6.76, 6.63, 5.61, 7.72, 5.57 |

The Phase 5 browser check measured every piece of visible text on every page against its background: none fell below 4.5:1.

## Typography

Both fonts load from Google Fonts through `config.toml`, with system fallbacks.

| Style | Size | Font |
|---|---|---|
| Page title | 32px | Lora 600 |
| Summary sentence (Overview, Insights) | 28px | Lora 500 |
| Section title ("What the numbers suggest") | 24px | Lora 600 |
| Card heading | 20px | Lora 600 |
| Figure value | 30px (22px when it's words, "No sales yet") | Lora 500 |
| Body | 15–16px | Lato 400 |
| Labels, notes, table headers | 13–14px | Lato 400/700 |
| Invite code | 20px, letter-spaced | Consolas (monospace, so 0 and O differ) |

Amounts use Indian grouping (₹1,25,000), whole rupees in figures and sentences, paise in tables. The chart axis shortens them: ₹5k, ₹50k, ₹1L.

## Spacing

Every gap uses one of six tokens in `ui/styles.css`: 4, 8, 16, 24, 40 and 64px (`--lekha-space-1` to `-6`). Streamlit adds 16px between elements, so:

- a page title sits **32px** above the first card or tab row (16px margin + 16px gap), as on the canvas;
- cards have 24px padding and sit 16px apart;
- a short hint under a field (such as "Used for new books") is pulled up to sit just under it;
- side-by-side cards are as tall as their own content.

## Shape and layout

- **Corners:** 6px everywhere (`baseRadius` in `config.toml`, `--lekha-radius`); tags 4px. Chart bars round only their top corners.
- **Cards** are `st.container(key="lekha_card_…")`, styled by their key. Figures sit in one connected strip, not separate cards.
- **Navigation** is at the top: the five daily pages, then the account menu (Team, Settings, Switch shop, Start or join a shop, Sign out).
- **Phones (under 640px):** cards stack; tables with a phone version switch to a list (the reorder list, books, best sellers); other wide tables scroll sideways; Overview shows today, the last 30 days and what to reorder.

## Accessibility

- Every page has its own tab title ("Books · Lekha"), one h1 and headings in order.
- Keyboard focus is always visible: a 2px crimson outline on links, buttons, text fields, number fields and dropdowns (Streamlit's own cue is a 1px border).
- Every control has a name; every image has alt text (covers are decorative, `alt=""`); tables use real header cells.
- Status is always a word. The chart's running period is a dashed outline, not just a lighter colour, and its numbers are available as a table.
- Motion is limited to a slight press on buttons, switched off when the system asks for reduced motion.

## Charts (`ui/charts.py`)

One chart, on Insights: revenue by day, week or month, chosen from the period's length.
- One series, one hue. The latest finished bar is crimson; earlier bars are lighter; the bar still running is a dashed outline marked "so far".
- Only the bars that matter are labelled: the best, the latest finished and the running one.
- Every bar has a tooltip; the chart has alt text; "Show as a table" gives the numbers.
- Revenue by genre is drawn as HTML bars (`genre_bars_html`), each with its amount and share written beside it.

## Components (`ui/components.py`)

| Function | What it draws |
|---|---|
| `load_styles()` | Adds `styles.css` to the page. Called once in `app.py` |
| `page_header(title)` | A page's title (its only h1) |
| `summary_header(date_line, sentence)` | Overview's and Insights' opening: the dates, then the sentence as the h1 |
| `card_heading(title, line="")` | A card's h2, and a line under it only when needed |
| `figure_strip([Figure…])` | Connected figures; a missing value shows "—" and is read as "No data yet" |
| `status_html(kind, text)` / `stock_status_html(...)` | A status in words: In stock, Low, Out of stock |
| `data_table_html(...)` / `book_cell_html(...)` | Plain tables; a book's cover (or its letter) beside title and author |
| `book_rows_html(...)` / `book_list_html(...)` | The phone versions of book tables |
| `shelf_html(...)` | Overview's "Selling well" covers |
| `step_html(...)` | A first-run step |
| `genre_bars_html(...)` | Insights' revenue by genre |
| `observation_html(...)` | A finding card: its tone in words, title, evidence and what to try |
| `progress_html(...)` | Progress towards two weeks of sales, announced to screen readers |
| `flash(...)` / `show_flash()` | A message that survives the reload after saving |
| `show_errors(...)` | One box listing every problem with a form |
| `wordmark(...)` / `or_divider()` | Sign in's wordmark, and the "or" between ways to sign in |
