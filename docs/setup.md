# Setup guide

How to get Lekha running on your own computer. Takes about five minutes.

## 1. What you need

- **Python 3.13.** Check with `python --version` (Windows) or `python3 --version` (macOS, Linux). Download from python.org if needed. On Windows, tick "Add python.exe to PATH" during installation.
- **Git**, to download the code. Alternatively, use "Code → Download ZIP" on the GitHub page.

## 2. Download the code

```
git clone https://github.com/priyal-baraya/lekha.git
cd lekha
```

## 3. Create a virtual environment and install packages

A virtual environment is a private copy of Python for this project, so its packages don't clash with anything else on your computer.

**Windows (PowerShell)**

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

**macOS / Linux**

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

The commands below are written for Windows. On macOS and Linux, replace `.\.venv\Scripts\python.exe` with `.venv/bin/python`.

## 4. Start Lekha

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Your browser opens at http://localhost:8501. The first time, Lekha creates an empty shop in `data/lekha.db`. To stop Lekha, press `Ctrl+C` in the terminal.

## 5. Add your first book

Go to **Books → Add a book** and choose how:

- **Look up by ISBN**: type the 10 or 13 digits printed by the barcode. Open Library fills in that exact edition: title, author, publisher, year and cover.
- **Search by title or author**: pick the right book from the results (check the author and year: results can include study guides and translations).
- **Type it in myself**: for books Open Library doesn't have, or when you're offline.

Check the details against the book, correct anything that's wrong, then enter **your** selling price, copies in stock and reorder level. These come only from you: Lekha never guesses them.

Looking books up needs an internet connection. Lekha remembers each answer for a day, so repeated lookups are instant.

## Optional

**Run the tests**

```powershell
.\.venv\Scripts\python.exe -m pytest
```

All 225 should pass. They never touch `data/lekha.db` and don't need the internet: Open Library lookups are replayed from real responses saved in `tests/fixtures/`.

**Start again with an empty shop**

```powershell
.\.venv\Scripts\python.exe database.py --reset
```

**This deletes every book, sale and correction.**

**Use a different database file**

```powershell
$env:LEKHA_DB_PATH = "D:\shop\lekha.db"     # macOS/Linux: export LEKHA_DB_PATH=/path/to/lekha.db
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Close the terminal (or run `Remove-Item Env:LEKHA_DB_PATH`) to go back to `data/lekha.db`.

**Practise SQL** on the small fictional dataset the tests use. It's built in memory for that run only; nothing is saved:

```powershell
.\.venv\Scripts\python.exe query.py --sample sql\01_first_queries.sql
```

**Retake the screenshots**

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
# with Lekha running on port 8501:
.\.venv\Scripts\python.exe scripts\capture_screenshots.py
```

This needs Microsoft Edge and an internet connection. It looks books up but never adds them.

## Common problems

| Problem | Fix |
|---|---|
| `python` is not recognised | Python isn't on your PATH. Reinstall with "Add python.exe to PATH" ticked, or use the `py` launcher: `py -3.13 -m venv .venv` |
| "running scripts is disabled on this system" | You tried `Activate.ps1`. You don't need it: these instructions call `.venv\Scripts\python.exe` directly |
| `ModuleNotFoundError: No module named 'streamlit'` | You're using the system Python. Run the commands with `.\.venv\Scripts\python.exe`, not plain `python` |
| "Port 8501 is already in use" | Lekha is already running in another terminal. Stop it with `Ctrl+C`, or add `--server.port 8502` |
| Lekha shows "couldn't read or write its database" | Another program has `data\lekha.db` open, or the file is damaged. Close the other program and reload. If the file is damaged, `database.py --reset` starts an empty shop (this deletes its data) |
| "Couldn't reach Open Library" | Check the internet connection. You can still type the book in yourself |
| "Open Library is busy right now" | Wait a minute and try again |
| Changes to `.streamlit/config.toml` don't show | The theme is read at start-up. Stop Lekha and start it again |
| You want Streamlit's Rerun button and full error details while developing | In `.streamlit/config.toml`, set `toolbarMode = "auto"` and `showErrorDetails = "full"` |
