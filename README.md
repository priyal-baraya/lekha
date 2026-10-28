# Lekha

**Reading between the numbers.**

An inventory and sales insights tool for independent bookstores, built with Python, SQLite, SQL, Pandas and Streamlit.

Lekha is meant to help a small bookstore owner answer everyday questions from their own records: which books sell, which genres earn the most, what is running low, and what has not moved in a while. The visual identity draws on Indian illustrated manuscripts: crimson and Persian teal on parchment, Lora and Lato type, square editorial layout and a few fine ornaments.

## Current status

| Phase | What it covers | Status |
|---|---|---|
| 1. Foundation | Environment, project structure, starter page | Done |
| Design foundation | Theme, typography, layout shell, ornaments | Done (on branch `design/manuscript-theme`) |
| 2. Database and sample data | Schema, constraints, fictional sample data | Not started |
| 3. Catalogue and inventory | Book list, search, add/edit, low-stock alerts | Not started |
| 4. Sales | Recording sales safely, updating stock | Not started |
| 5. Analytics | Business questions, SQL queries, charts | Not started |
| 6. Visual refinement | Accessibility and layout polish | Not started |
| 7. Quality and portfolio | Tests, documentation, case study | Not started |

The app currently shows the Overview page with **placeholders only**. No figures on screen are real or calculated yet; each section is labelled with the phase it arrives in. The Books, Sales, Inventory and Insights pages say "Not built yet".

## Run it locally (Windows, PowerShell)

Requires Python 3.13.

```powershell
git clone https://github.com/priyal-baraya/lekha.git
cd lekha
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

The app opens at http://localhost:8501. Press `Ctrl+C` in the terminal to stop it.

If you change `.streamlit/config.toml`, stop and restart Streamlit: the theme is only read at start-up.

## Project structure

```
lekha/
├── app.py                 Entry point: page setup, shared styles, navigation
├── requirements.txt       Python packages with exact versions
├── .streamlit/config.toml Theme: colours, fonts, square corners, chart palette
├── ui/
│   ├── components.py      Reusable page pieces (hero, divider, section header…)
│   ├── styles.css         Custom styles Streamlit has no setting for
│   └── assets/            Original SVG ornaments
├── views/                 One file per page (Overview, Books, Sales, …)
├── data/                  Future: local database and sample-data scripts
├── sql/                   Future: saved analytical queries
└── docs/                  Product brief, design system, decisions, logs
```

## Documentation

- [Product brief](docs/product-brief.md): user, problem, goals and core features
- [Design system](docs/design-system.md): colours, fonts, spacing, shapes and motifs
- [Decision log](docs/decision-log.md): important technical and design decisions
- [Testing log](docs/testing-log.md): checks performed, issues found, fixes made
- [Dev log](docs/devlog/): dated build notes

## Data

All data in this project will be fictional sample data, clearly labelled as such. Nothing here comes from a real bookstore.
