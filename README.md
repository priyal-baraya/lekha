# Lekha

**Reading between the numbers.**

An inventory and sales insights tool for independent bookstores, built with Python, SQLite, SQL, Pandas and Streamlit.

Lekha is meant to help a small bookstore owner answer everyday questions from their own records: which books sell, which genres earn the most, what is running low, and what has not moved in a while. The visual identity draws on Indian illustrated manuscripts: crimson and Persian teal on parchment, Lora and Lato type, square editorial layout and a few fine ornaments.

## Current status

| Phase | What it covers | Status |
|---|---|---|
| 1. Foundation | Environment, project structure, starter page | Done |
| Design foundation | Theme, typography, layout shell, ornaments | Done (visual design to be refined separately) |
| 2. Database and sample data | Schema, constraints, fictional sample data, tests, first queries | Done |
| 3. Catalogue and inventory | Book list, search, add/edit, low-stock alerts, recorded stock corrections | Done |
| 4. Sales | Recording and cancelling sales, updating stock in one transaction | Done |
| 5. Analytics | Revenue, best sellers, genres, trends, estimated profit, observations, date and genre filters | Done |
| 6. Visual refinement | Accessibility and layout polish | Not started |
| 7. Quality and portfolio | Tests, documentation, case study | Not started |

**Working now:** the Books page (browse, search, filter, sort, add and edit books), the Inventory page (low-stock alerts, stock corrections with a reason, and their history), and the Sales page (record a sale from a basket, see recent sales, cancel a sale with a reason), and the Insights page (revenue, copies, transactions, revenue over time, revenue by genre, best sellers, unsold books, estimated gross profit and plain-language observations, filtered by period and genre). The Overview shows live figures for the last 30 days.

**Next:** visual refinement (Phase 6) and portfolio quality (Phase 7).

## Run it locally (Windows, PowerShell)

Requires Python 3.13.

```powershell
git clone https://github.com/priyal-baraya/lekha.git
cd lekha
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe database.py --reset-sample
.\.venv\Scripts\python.exe -m streamlit run app.py
```

The app opens at http://localhost:8501. Press `Ctrl+C` in the terminal to stop it.

`database.py --reset-sample` deletes `data/lekha.db` and rebuilds it with the fictional sample data.

### Tests

```powershell
.\.venv\Scripts\python.exe -m pytest
```

### Practise SQL against the sample data

```powershell
.\.venv\Scripts\python.exe query.py sql\01_first_queries.sql
.\.venv\Scripts\python.exe query.py "SELECT title, stock_quantity FROM books"
```

If you change `.streamlit/config.toml`, stop and restart Streamlit: the theme is only read at start-up.

## Project structure

```
lekha/
├── app.py                 Entry point: page setup, shared styles, navigation
├── database.py            Database connection, schema set-up, sample-data reset
├── query.py               Runs SQL and prints the results as tables (learning tool)
├── services/              Business rules: books, inventory, money (no Streamlit code)
├── requirements.txt       Python packages with exact versions
├── pyproject.toml         Test settings
├── .streamlit/config.toml Theme: colours, fonts, square corners, chart palette
├── ui/
│   ├── components.py      Reusable page pieces (hero, divider, section header…)
│   ├── styles.css         Custom styles Streamlit has no setting for
│   └── assets/            Original SVG ornaments
├── views/                 One file per page (Overview, Books, Sales, …)
├── data/
│   ├── sample_data.sql    Fictional sample dataset
│   └── lekha.db           The database file (created locally, not committed)
├── sql/
│   ├── schema.sql         Tables and rules
│   ├── analytics/         The analytics queries, one file each
│   └── 01_first_queries.sql  Practice queries with expected results
├── tests/                 Automated tests (pytest)
└── docs/                  Product brief, schema, design system, decisions, logs
```

## Documentation

- [Product brief](docs/product-brief.md): user, problem, goals and core features
- [Database schema](docs/schema.md): tables, relationships and the reasons behind them
- [Sample data](docs/sample-data.md): what the fictional dataset contains and its hand-checked results
- [Analytics](docs/analytics.md): every metric's definition, with the hand calculations the tests check
- [Design system](docs/design-system.md): colours, fonts, spacing, shapes and motifs
- [Decision log](docs/decision-log.md): important technical and design decisions
- [Testing log](docs/testing-log.md): checks performed, issues found, fixes made
- [Dev log](docs/devlog/): dated build notes

## Data

All data in this project is fictional sample data, clearly labelled as such. Nothing here comes from a real bookstore.
