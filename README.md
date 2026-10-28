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
| 3. Catalogue and inventory | Book list, search, add/edit, low-stock alerts | Not started |
| 4. Sales | Recording sales safely, updating stock | Not started |
| 5. Analytics | Business questions, SQL queries, charts | Not started |
| 6. Visual refinement | Accessibility and layout polish | Not started |
| 7. Quality and portfolio | Tests, documentation, case study | Not started |

The database and its fictional sample data exist and are tested, but the app does not read from them yet. The Overview page still shows **placeholders only**, each labelled with the phase it arrives in. The Books, Sales, Inventory and Insights pages say "Not built yet".

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
│   └── 01_first_queries.sql  Practice queries with expected results
├── tests/                 Automated tests (pytest)
└── docs/                  Product brief, schema, design system, decisions, logs
```

## Documentation

- [Product brief](docs/product-brief.md): user, problem, goals and core features
- [Database schema](docs/schema.md): tables, relationships and the reasons behind them
- [Sample data](docs/sample-data.md): what the fictional dataset contains and its hand-checked results
- [Design system](docs/design-system.md): colours, fonts, spacing, shapes and motifs
- [Decision log](docs/decision-log.md): important technical and design decisions
- [Testing log](docs/testing-log.md): checks performed, issues found, fixes made
- [Dev log](docs/devlog/): dated build notes

## Data

All data in this project is fictional sample data, clearly labelled as such. Nothing here comes from a real bookstore.
