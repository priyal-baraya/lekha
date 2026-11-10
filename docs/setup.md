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

Your browser opens at http://localhost:8501. To stop Lekha, press `Ctrl+C` in the terminal.

## 5. Create an account and your shop

1. On the sign-in page, choose **Create an account**: your name, a username (3 to 32 letters, numbers, dots, dashes or underscores) and a password of at least 10 characters.
2. Choose **Start a shop** and give it a name. You're its owner.
3. To bring in staff, open **Team**, choose **Staff** and **Make an invite code**. Give the code to the person: they create their own account, then choose **Join with a code**. Each code works once, for 7 days, and is shown only once.

Lekha keeps accounts in `data/accounts.db` and each shop's books and sales in its own file, `data/shops/shop_<number>.db`.

## 6. Add your first book

Go to **Books → Add a book** and choose how:

- **Look up by ISBN**: type the 10 or 13 digits printed by the barcode. Open Library fills in that exact edition: title, author, publisher, year and cover.
- **Search by title or author**: pick the right book from the results (check the author and year: results can include study guides and translations).
- **Type it in myself**: for books Open Library doesn't have, or when you're offline.

Check the details against the book, correct anything that's wrong, then enter **your** selling price, copies in stock and reorder level. These come only from you: Lekha never guesses them.

Looking books up needs an internet connection. Lekha remembers each answer for a day, so repeated lookups are instant.

## Optional: Google sign-in

Username and password sign-in works without any of this. To add a **Sign in with Google** button, Lekha needs its own credentials from Google. They're secret, so they live in a file that is never committed (`.streamlit/secrets.toml` is in `.gitignore`).

1. Go to the [Google Cloud Console](https://console.cloud.google.com/) and create a project (any name, such as "Lekha").
2. Open **APIs & Services → OAuth consent screen** (also called **Google Auth Platform**). Choose **External**, fill in the app name and your email, and add yourself as a **test user**. While the app is in testing, only test users can sign in.
3. Open **Credentials → Create credentials → OAuth client ID**. Choose **Web application**. Under **Authorised redirect URIs**, add exactly `http://localhost:8501/oauth2callback`.
4. Copy the **client ID** and **client secret** Google shows you.
5. Make a random cookie secret:

   ```powershell
   .\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_hex(32))"
   ```

6. Create `.streamlit/secrets.toml` with:

   ```toml
   [auth]
   redirect_uri = "http://localhost:8501/oauth2callback"
   cookie_secret = "the random text from step 5"

   [auth.google]
   client_id = "your client ID"
   client_secret = "your client secret"
   server_metadata_url = "https://accounts.google.com/.well-known/openid-configuration"
   ```

7. Restart Lekha. The sign-in page now shows **Sign in with Google**. The first time someone signs in with Google, Lekha creates their account from their Google name and email.

If the button doesn't appear, one of the three settings (`redirect_uri`, `cookie_secret`, `[auth.google]`) is missing. If Google says "redirect_uri_mismatch", the address in step 3 doesn't exactly match the one in `secrets.toml`, including `http` and the port.

## Optional

**Run the tests**

```powershell
.\.venv\Scripts\python.exe -m pytest
```

All 271 should pass. They use their own temporary folders, never your `data/` folder, and don't need the internet: Open Library lookups are replayed from real responses saved in `tests/fixtures/`.

**Start again from nothing**

```powershell
.\.venv\Scripts\python.exe database.py --reset
```

**This deletes every account and every shop's books, sales and corrections.** It asks you to type `DELETE` first.

**Keep Lekha's data somewhere else**

```powershell
$env:LEKHA_DATA_DIR = "D:\lekha-data"     # macOS/Linux: export LEKHA_DATA_DIR=/path/to/folder
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Accounts and shops are then kept in that folder. Close the terminal (or run `Remove-Item Env:LEKHA_DATA_DIR`) to go back to `data/`.

**Practise SQL** on the small fictional dataset the tests use. It's built in memory for that run only; nothing is saved:

```powershell
.\.venv\Scripts\python.exe query.py --sample sql\01_first_queries.sql
```

**Retake the screenshots**

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
# with Lekha running on port 8501, and your own Lekha username and password:
$env:LEKHA_SCREENSHOT_USERNAME = "your username"
$env:LEKHA_SCREENSHOT_PASSWORD = "your password"
.\.venv\Scripts\python.exe scripts\capture_screenshots.py
```

This needs Microsoft Edge and an internet connection. It signs in as you, so the pictures show your own shop, and it looks books up but never adds them. The username and password are only read from those two settings, never saved; close the terminal afterwards to forget them.

## Common problems

| Problem | Fix |
|---|---|
| `python` is not recognised | Python isn't on your PATH. Reinstall with "Add python.exe to PATH" ticked, or use the `py` launcher: `py -3.13 -m venv .venv` |
| "running scripts is disabled on this system" | You tried `Activate.ps1`. You don't need it: these instructions call `.venv\Scripts\python.exe` directly |
| `ModuleNotFoundError: No module named 'streamlit'` | You're using the system Python. Run the commands with `.\.venv\Scripts\python.exe`, not plain `python` |
| "Port 8501 is already in use" | Lekha is already running in another terminal. Stop it with `Ctrl+C`, or add `--server.port 8502` |
| Lekha shows "couldn't read or write its database" | Another program has `data\accounts.db` or a file in `data\shops\` open, or a file is damaged. Close the other program and reload. If a file is damaged, `database.py --reset` starts again from nothing (this deletes every account and shop) |
| You're signed out after refreshing the page | Expected for username-and-password sign-in: it lasts for the open tab. Sign in again. Google sign-in is remembered |
| "Too many wrong passwords" | Wait 15 minutes, then try again |
| "Couldn't reach Open Library" | Check the internet connection. You can still type the book in yourself |
| "Open Library is busy right now" | Wait a minute and try again |
| Changes to `.streamlit/config.toml` don't show | The theme is read at start-up. Stop Lekha and start it again |
| You want Streamlit's Rerun button and full error details while developing | In `.streamlit/config.toml`, set `toolbarMode = "auto"` and `showErrorDetails = "full"` |
