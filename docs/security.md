# Security

What Lekha protects, how, and what it doesn't cover yet. Every check listed here has an automated test unless it says otherwise.

## What needs protecting

- **Accounts:** passwords, and who belongs to which shop with which role.
- **Each shop's records:** books, prices, stock, sales and profit, visible only to that shop's members (profit only to owners).
- **The people using it:** a shared till computer, staff with fewer rights than owners, and book details that come from Open Library, an outside service edited by volunteers.

## Signing in

| Check | How | Where |
|---|---|---|
| Passwords never stored | Salted **scrypt** hash (n=2¹⁴, r=8, p=1, 16-byte salt); constant-time comparison | `services/accounts.py` |
| Strong enough passwords | 10 to 128 characters; can't contain the username or be the person's name; very common ones (`password123`, `1234567890`, …) and one-character repeats refused | `_check_new_password` |
| Guessing one account | 5 wrong passwords lock it for 15 minutes. **Wrong current passwords on the Settings page count too**, so that form can't be used to guess | `authenticate`, `change_password` |
| Guessing across accounts | At most 20 failed sign-ins per device per 15 minutes | `services/limits.py`, `views/signin.py` |
| Finding out who has an account | A wrong password and an unknown username give the same message and take the same time | `authenticate` |
| Flooding with accounts | At most 10 new accounts per device per hour | `views/signin.py` |
| Huge inputs | Passwords over 128 characters are never hashed; names, usernames and shop names have length limits | `services/accounts.py`, input boxes |
| Google sign-in | Matched on Google's permanent ID, not the email; switched off unless the cookie secret is at least 32 characters | `ui/session.py` |

## Staying signed in

| Check | How |
|---|---|
| A till left open | Signed out after **60 minutes** with no clicks |
| A changed password | Every other tab signed in with the old password is signed out on its next click (each tab remembers a fingerprint of the password hash, never the password) |
| A removed person or changed role | Read fresh from the accounts database on every click, so it takes effect immediately |
| Signing out | Clears everything the tab knew, including a half-finished sale |

## What each person can do

- Roles are checked in the services (`PermissionError`), not only by hiding buttons.
- Owner-only saves (editing a book, correcting stock) are checked again at the moment of saving.
- Each shop's books and sales are in **their own database file**, so a query for one shop can't reach another's.
- Invite codes: 10 random characters, stored as SHA-256 hashes, single-use, valid 7 days, can be cancelled, and at most 10 wrong codes per person per 15 minutes.

## Text from people and from Open Library

- **SQL:** every value goes through `?` or `:name` placeholders. The few queries that join text into SQL only join fixed text from the code (column names, a sort order from a fixed list), and each is marked and explained for the code scanner.
- **HTML:** Lekha's own page pieces escape text with `html.escape`.
- **Markdown:** Streamlit reads text in `st.markdown`, `st.info` and similar as Markdown. Anything a person typed or Open Library sent goes through `ui.plain()` first, so a title like `The $100 *Startup*` shows as typed, not as maths and italics, a name can't fake bold "owner" text, a picture link can't load an image from another website, and a bare web address doesn't become a link.
- **Open Library:** only `https://openlibrary.org` is ever fetched; answers over 2 MB are refused; record references, cover numbers and years must have the expected shape, or they're ignored; text is trimmed to sensible lengths. Book details are only pre-filled: a person checks them before saving.
- **Google Books:** only `https://www.googleapis.com/books/v1/volumes` is fetched, and only when an API key is set. The key must look like a Google API key (`AIza` and 35 letters, digits, `-` or `_`), so a mistyped one can't change the address. It is read from `secrets.toml` and never shown, logged or put in an error message. Only a price in rupees between ₹0 and ₹1,00,000 is used, for the exact ISBN or for an edition with the same title and author; quotes are taken out of titles before searching, and titles are cut to 200 characters; answers over 2 MB are refused; any trouble just leaves the price empty. The price is only filled in: a person checks it before saving.
- **Length limits:** title 300, author 200, genre 60, publisher 200, cancellation reason and stock note 300 characters.

## The server

Set in `.streamlit/config.toml`, and a test checks they stay that way:

- **Only this computer can open Lekha** (`address = "localhost"`). Lekha has no HTTPS of its own, so on a shop's Wi-Fi, passwords would cross the network unencrypted. See [the setup guide](setup.md#letting-other-devices-in) before changing this.
- Requests from other websites refused (CORS) and every form submission checked with a token (XSRF protection).
- No file uploads, no extra files served, no error details or tracebacks in the browser.
- Secrets (`.streamlit/secrets.toml`) are in `.gitignore`, and a test checks it.

## The hosted Lekha

On Streamlit Community Cloud with its data in Turso ([docs/hosting.md](hosting.md)):

- **HTTPS** from Community Cloud. Lekha reaches Turso over HTTPS too, checking its certificate, and refuses a Turso address that isn't `libsql://` or `https://` or that has unexpected characters in it. The token travels only in the request's `Authorization` header; an error from Turso shows Turso's own short explanation, never what was sent. A request that fails on a stale connection is sent again only if it can't have changed anything.
- **The Turso token** lives in the app's secrets on Community Cloud and in `.streamlit/secrets.toml` (never committed). It's never logged: the start-up line names the address only. It can read and write Lekha's databases, but it can't create or delete them, which is why each shop's database is made in advance.
- **A leaked token** is stopped by invalidating the group's tokens in Turso and making a new one.
- **Each shop is still its own database**, as with files, so one shop's queries can't reach another's books.
- **Backups:** Turso keeps one day of history on the free plan. That's short: a mistake noticed after a day can't be undone there.

## Logging

Security events go to the terminal Lekha runs in, under `lekha.security`: sign-ins, failed sign-ins, lockouts, new accounts, password changes, invites, role changes, removals and refused actions. People appear by account number. Passwords and invite codes are never logged.

## Automatic checks on GitHub

| Check | When | What it does |
|---|---|---|
| Tests (`tests.yml`) | Every push and pull request | All automated tests, including `tests/test_security.py` |
| **pip-audit** (`security.yml`) | Every push, pull request, and every Monday | Fails if any package Lekha installs has a published vulnerability |
| **bandit** (`security.yml`) | Same | Scans the code for risky patterns |
| **Dependabot** (`dependabot.yml`) | Weekly | Opens a pull request when a package or GitHub Action has an update |

Both workflows run with read-only access to the repository.

On 2026-11-10, pip-audit found no known vulnerabilities in the pinned packages, and bandit found 8 possible issues: 7 SQL strings and 1 web request. Each was reviewed and found safe (see the comments next to each `# nosec` line).

## Not covered yet

- **No HTTPS of its own.** Fine on one computer; the hosted Lekha gets it from Community Cloud ([docs/hosting.md](hosting.md)).
- **Limits on repeated attempts are kept in memory**, so restarting Lekha resets them (the account lockout is stored and survives). Behind a proxy, every visitor can look like the same address unless the proxy passes the real one on. On Community Cloud this hasn't been checked yet.
- **The lockout message shows that an account exists** (only for usernames that have one). This is a common trade-off: hiding it would mean locking usernames nobody has.
- **The sign-up page says when a username is taken.** Same trade-off.
- **No password reset by email, and no two-step sign-in** (Google sign-in can use Google's).
- **The database files aren't encrypted.** Anyone who can open the `data/` folder on the computer can read them; protect the computer's own account with a password.
- **Google sign-in hasn't been tried with real Google credentials** yet.
