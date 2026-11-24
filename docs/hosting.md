# Hosting Lekha for free: Streamlit Community Cloud and Turso

This puts Lekha online at an HTTPS address, such as `https://lekha-bookshops.streamlit.app`, for a few people. Both services are free and neither asks for a card.

How it fits together:

- **[Streamlit Community Cloud](https://share.streamlit.io)** runs Lekha from this GitHub repository and gives it the HTTPS address. Every change merged into `main` is deployed automatically.
- **[Turso](https://turso.tech)** keeps the data. Community Cloud can wipe its own files whenever the app restarts, so Lekha can't keep its SQLite files there. Turso is SQLite online: each of Lekha's files becomes one Turso database.

| On a computer | In Turso |
|---|---|
| `accounts.db` | `lekha-accounts` |
| `shops/shop_1.db` | `lekha-shop-1` |
| `shops/shop_2.db` | `lekha-shop-2`, and so on |

Lekha uses Turso only when two settings are present, `LEKHA_TURSO_URL` and `LEKHA_TURSO_TOKEN`. Without them it uses files, as always. [`turso.py`](../turso.py) makes Turso's driver behave like Python's `sqlite3`, and every test runs through it as well.

## What's free, and the limits

- **Turso's free plan:** 100 databases and 5 GB, with no card. Turso keeps one day of history, so a database can be put back to how it was earlier that day.
- **Community Cloud:** free for public repositories. The app **sleeps after 12 hours without visitors**; the next visit wakes it, which takes about a minute.
- **Each shop needs a Turso database made in advance.** Lekha doesn't hold a key that could create or delete databases. When none is ready, creating a shop says "Lekha couldn't set up this shop's database" and nothing is half-made.
- **Speed:** every query crosses the internet. Lekha keeps one secure connection to each database open and sends each query as one request: about a quarter of a second from India to Turso's Virginia servers, so a page took 2 to 4 seconds from here, and less from Community Cloud's servers. Each page writes a line to the app's log, such as `Overview: 16 requests to Turso, 0.41 s of 0.62 s`, so you can see.

## 1. Turso: account, databases and token

1. Sign up at [turso.tech](https://turso.tech) with GitHub. No card is needed.
2. **Create Database** three times, named exactly `lekha-accounts`, `lekha-shop-1` and `lekha-shop-2` (two shops), all in the same group (`default`) and in a US region such as **Virginia** (`aws-us-east-1`).
3. Make one **group token** that works for every database in the group: click the group's name (the `default` badge next to any database), then **Create Token**. Choose **full access** (Lekha saves sales, so it needs to write) and **no expiry**. Copy it; it's shown once.
4. Open `lekha-accounts` and copy its URL, for example `libsql://lekha-accounts-yourname.aws-us-east-1.turso.io`. Replace `accounts` with `{name}`:
   `libsql://lekha-{name}-yourname.aws-us-east-1.turso.io`

## 2. Check it from your computer

Add the two settings at the top of `.streamlit/secrets.toml`, **above** any `[section]` such as `[google_books]` (anything below a section belongs to it):

```toml
LEKHA_TURSO_URL = "libsql://lekha-{name}-yourname.aws-us-east-1.turso.io"
LEKHA_TURSO_TOKEN = "your group token"
```

Then check every database (the number is how many shop databases you made):

```powershell
.\.venv\Scripts\python.exe scripts\check_turso.py 2
```

Each one should say `ready`. The check sets up Lekha's tables, checks that foreign keys are enforced and that a failed save leaves nothing behind, and times a query. It never prints the token.

While those two lines are in your `secrets.toml`, Lekha on your computer uses Turso too. Remove them to go back to your own files.

## 3. Community Cloud

1. Sign in at [share.streamlit.io](https://share.streamlit.io) with GitHub.
2. **Create app → Deploy a public app from GitHub.** Repository: this one. Branch: **`main`**. Main file path: `app.py`. App URL: a name of your choice.
3. **Advanced settings:** Python version **3.13** (the version the tests run on). In **Secrets**, paste the whole of your `.streamlit/secrets.toml`. Copy it from Notepad: TOML needs plain straight quotes (`"`), and copying from a chat or a document can turn them into curly ones, which Community Cloud rejects as "Invalid format".
4. **Deploy**, and wait a few minutes while it installs.

To change these later: **My apps → ⋮ → Settings**. The branch can't be changed there; deploy from `main`.

## 4. Check the hosted Lekha

1. Open **Manage app** (bottom right of the app) to see its log. Near the top it should say **`Lekha keeps its data in Turso (libsql://lekha-{name}-…)`**. If it says "in files", the secrets are missing or the app isn't running the code from `main`.
2. Create your account and your shop. Your shop takes the first free shop database.
3. Invite the others from **Team**.

## More shops

Create the next database in Turso (`lekha-shop-3`, in the same group). The group token covers it, so nothing else changes.

## Google sign-in on the hosted Lekha

Follow [setup.md](setup.md#optional-google-sign-in), with the hosted address: the redirect URI is your app's address + `/oauth2callback`, for example `https://lekha-bookshops.streamlit.app/oauth2callback`, in both Google's **Authorised redirect URIs** and the app's secrets. Make a new cookie secret for it.

## If the token leaks

In Turso, invalidate the group's tokens (this stops every old token), create a new one, and paste it into the app's **Secrets** and your local `secrets.toml`.

## When something's wrong

| Problem | What to do |
|---|---|
| Accounts and shops disappear after a while | Lekha is using Community Cloud's files, not Turso. Check the log line in step 4, the **Secrets**, and that the app runs `main` |
| "Invalid format: please enter valid TOML" | Curly quotes or a token split over two lines. Copy `secrets.toml` from Notepad |
| "Lekha couldn't set up this shop's database" | No Turso database is ready for the next shop: create the next `lekha-shop-N` |
| Pages are slow | Open **Manage app**: each page's log line says how long it waited for Turso. The first page after the app wakes up is slower: it checks every database's tables |
| "Lekha couldn't read or write its database" | Turso couldn't be reached, or the token has expired or been invalidated. Run `scripts/check_turso.py` on your computer to see which |
| The first visit takes a minute | The app was asleep after 12 hours without visitors |
