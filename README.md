# Lekha

**Reading between the numbers.**

[![Tests](https://github.com/priyal-baraya/lekha/actions/workflows/tests.yml/badge.svg)](https://github.com/priyal-baraya/lekha/actions/workflows/tests.yml)

An inventory and sales insights tool for independent bookstores, built with **Python, SQLite, SQL, pandas and Streamlit**, with real book details from **[Open Library](https://openlibrary.org)**.

Lekha helps a small bookstore owner answer everyday questions from their own records: *What sells? Which genres earn the most? What's running low? What hasn't moved?* Books are found in Open Library's real catalogue (by ISBN or by title), prices and stock come from the owner, and every figure is calculated from sales actually recorded. Nothing in the app is invented: there are no sample books, made-up sales or reviews. Its look draws on Indian illustrated manuscripts: crimson and Persian teal on parchment, Lora and Lato type, square editorial layout.

![Adding a real book: Open Library's details for The God of Small Things (Flamingo, 1998) pre-fill the form; price and stock are left for the owner](docs/screenshots/books-isbn-desktop.png)

## What it does

| Page | For the owner | Under the hood |
|---|---|---|
| **Books** | Look up a book by ISBN, search Open Library by title or author, or type it in; browse, search, filter and edit the catalogue, with covers | Open Library answers pre-fill the form for checking; edition facts (publisher, year) saved only from an exact ISBN match; prices converted to paise exactly with `Decimal` |
| **Sales** | Build a sale in a basket, complete it, cancel a mistaken sale | Sale, lines and stock reduction in **one transaction**; stock checked and reduced in a single `UPDATE … WHERE stock >= n`; cancelling returns stock exactly once |
| **Inventory** | Books at or below their reorder level; correct stock after a count, with a reason | Every correction recorded with before/after counts; refused if the stock changed since the page loaded |
| **Insights** | Revenue over time, revenue by genre, best sellers, unsold books, estimated gross profit, plain-language observations, for any period and genre | Readable SQL files sharing one definition of "a completed sale in the period"; `RANK()` for ties; partial periods marked; every figure tested against hand calculations |
| **Overview** | The day's key figures and the weekly trend | Same analytics code as Insights; an empty shop shows real zeros and where to start |

<p>
  <img src="docs/screenshots/books-search-desktop.png" alt="Searching Open Library for 'the god of small things': real results with covers, authors and first-published years" width="62%">
  <img src="docs/screenshots/books-search-phone.png" alt="The same search on a phone" width="30%">
</p>

*Screenshots show a new, empty shop and live Open Library results. Open Library is edited by volunteers, so results can include study guides, translations and the occasional mistake, which is why the owner checks the details before saving.*

## How it's built

```
views/       Pages: what the owner sees (Streamlit)
   │  call
services/    Rules: books, sales, inventory, analytics, money, Open Library
             (plain Python, no Streamlit)
   │  run SQL through
database.py  One connection function: foreign keys on, path from LEKHA_DB_PATH,
             numbered migrations tracked with PRAGMA user_version
   │
SQLite       5 STRICT tables with CHECK, UNIQUE and foreign-key rules (sql/schema.sql)
```

Keeping SQL and network calls out of the pages means the rules are tested without a browser or the internet, reused across pages, and untouched by a redesign.

## Quality

- **225 automated tests** (pytest), run on every push and pull request by GitHub Actions: rules the database must refuse, transactions that must roll back, every analytics figure against numbers worked out by hand, Open Library lookups replayed from **real saved responses** (so the tests don't need the internet), a schema migration that must keep existing data, and the pages themselves via Streamlit's `AppTest`, including adding a real book by ISBN and a 2-copy sale that must reduce stock by exactly 2.
- **Test data stays in the tests.** The analytics are checked against a small, hand-calculated fictional dataset (`data/sample_data.sql`). It is loaded only into temporary test databases, never into the app.
- **Accessibility:** a contrast audit of every piece of text on every page went from 37 failures to 0 (WCAG 2.2 AA); visible keyboard focus; charts with alt text, tooltips, written summaries and table views; layouts checked at 1280px and 375px.
- **Graceful errors:** database problems, an unreachable Open Library and unexpected errors all show a plain message, not a traceback.

## Run it

Requires Python 3.13, and an internet connection for looking books up. Full instructions for Windows, macOS and Linux are in **[docs/setup.md](docs/setup.md)**. On Windows:

```powershell
git clone https://github.com/priyal-baraya/lekha.git
cd lekha
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Then open http://localhost:8501. Lekha creates an empty shop on first start; add your first book on the **Books** page.

| Task | Command |
|---|---|
| Run the tests | `.\.venv\Scripts\python.exe -m pytest` |
| Start again with an empty shop (deletes everything) | `.\.venv\Scripts\python.exe database.py --reset` |
| Practise SQL on the test dataset (in memory, nothing saved) | `.\.venv\Scripts\python.exe query.py --sample sql\01_first_queries.sql` |

## Project structure

```
lekha/
├── app.py                  Entry point: page setup, styles, navigation, error handling
├── database.py             Connection, schema, migrations, empty-shop reset
├── query.py                Runs SQL and prints the results (learning tool)
├── services/               Business rules: books, sales, inventory, analytics, money,
│                           Open Library lookups
├── views/                  One file per page
├── ui/                     Shared page pieces, charts, styles, SVG ornaments
├── sql/
│   ├── schema.sql          Tables and rules
│   ├── migrations/         Numbered schema changes, applied once each
│   ├── analytics/          The analytics queries, one commented file each
│   └── 01_first_queries.sql
├── data/sample_data.sql    The fictional, hand-checked dataset the tests use
├── tests/                  225 pytest tests; fixtures/ holds real Open Library responses
├── scripts/                Screenshot capture (development only)
├── .github/workflows/      Runs the tests on GitHub
└── docs/                   Case study, setup, schema, analytics, design, decisions, logs
```

## Documentation

- **[Case study](docs/case-study.md)**: the problem, the design, the SQL, the results and the limits, in one read
- [Setup guide](docs/setup.md)
- [Product brief](docs/product-brief.md) · [Database schema](docs/schema.md) · [Test dataset](docs/sample-data.md) · [Analytics definitions](docs/analytics.md)
- [Design system](docs/design-system.md) · [Decision log](docs/decision-log.md) · [Testing log](docs/testing-log.md) · [Dev log](docs/devlog/)

## Data and credits

- **Book details and covers** come from [Open Library](https://openlibrary.org), an open catalogue run by the Internet Archive and edited by volunteers. Lekha pre-fills them; the owner checks them.
- **Prices, stock and sales** come only from the owner. No API knows a particular shop's prices or sales, so Lekha never guesses them.
- **Reviews and ratings** are not shown.

## Limitations

- One shop, one user, on one computer: no logins, no multi-store support.
- Looking books up needs the internet; typing a book in works offline.
- No deliveries or supplier records yet ("delivery received" is a stock-correction reason), so stock can't be rebuilt from history, and profit uses each book's *current* cost.
- No partial returns or discounts.
- Numbers inside tables and chart axes use Western digit grouping (₹1,047.00); elsewhere Indian grouping (₹1,11,444.00).
- Observations describe recorded sales; they can't prove causes, and say so.
