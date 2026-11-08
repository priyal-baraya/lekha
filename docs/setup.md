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

## 4. Create the database with the sample data

```powershell
.\.venv\Scripts\python.exe database.py --reset-sample
```

This creates `data/lekha.db` with 12 fictional books and 15 fictional sales. Run it again at any time to start fresh. **It deletes the database first**, including anything you added.

## 5. Start Lekha

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Your browser opens at http://localhost:8501. To stop Lekha, press `Ctrl+C` in the terminal.

## Optional

**Run the tests**

```powershell
.\.venv\Scripts\python.exe -m pytest
```

All 192 should pass. They never touch `data/lekha.db`.

**Use the larger demo dataset** (30 books, about 14 weeks of sales, all fictional)

```powershell
.\.venv\Scripts\python.exe demo_data.py
$env:LEKHA_DB_PATH = "data\demo.db"          # macOS/Linux: export LEKHA_DB_PATH=data/demo.db
.\.venv\Scripts\python.exe -m streamlit run app.py
```

`LEKHA_DB_PATH` tells Lekha which database file to use. Close the terminal (or run `Remove-Item Env:LEKHA_DB_PATH`) to go back to `data/lekha.db`.

**Retake the screenshots**

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
# with the demo app running on port 8502:
.\.venv\Scripts\python.exe scripts\capture_screenshots.py
```

This needs Microsoft Edge installed.

## Common problems

| Problem | Fix |
|---|---|
| `python` is not recognised | Python isn't on your PATH. Reinstall with "Add python.exe to PATH" ticked, or use the `py` launcher: `py -3.13 -m venv .venv` |
| "running scripts is disabled on this system" | You tried `Activate.ps1`. You don't need it: these instructions call `.venv\Scripts\python.exe` directly |
| `ModuleNotFoundError: No module named 'streamlit'` | You're using the system Python. Run the commands with `.\.venv\Scripts\python.exe`, not plain `python` |
| "Port 8501 is already in use" | Lekha is already running in another terminal. Stop it with `Ctrl+C`, or add `--server.port 8502` |
| Lekha shows "couldn't read or write its database" | Another program has `data\lekha.db` open, or the file is damaged. Close the other program, or rebuild it with `database.py --reset-sample` (this deletes its data) |
| Changes to `.streamlit/config.toml` don't show | The theme is read at start-up. Stop Lekha and start it again |
| You want Streamlit's Rerun button and full error details while developing | In `.streamlit/config.toml`, set `toolbarMode = "auto"` and `showErrorDetails = "full"` |
