# Lekha: a case study

*An inventory and sales insights tool for independent bookstores.*
*Python · SQLite · SQL · pandas · Streamlit · Altair · pytest · Open Library*

> **The app holds only real data:** books found on Open Library (or typed in), and prices, stock and sales entered by the owner. Nothing is invented or pre-filled. The results in section 7 come from a small **fictional test dataset** that exists only inside the automated tests, to prove the calculations are correct. They are not business findings.

---

## 1. The problem

A small independent bookstore often tracks stock and sales in spreadsheets or on paper. That makes ordinary questions hard to answer with confidence:

- Which books and genres actually sell?
- What is running low, and what hasn't moved?
- Did revenue go up or down this month?
- Was that stock count wrong because of theft, damage, or a typing mistake?

The data exists, but it isn't trustworthy enough, or summarised enough, to support decisions.

## 2. The user

The owner or manager of one small shop: knows their books and readers well, isn't a data specialist, has little time, and needs to trust a number before acting on it. That shaped two principles: **every figure must be checkable**, and **every suggestion must state its limits**.

A second user arrived later: **staff** at the till, who need to sell and add books quickly, but not to change prices, correct stock or see the shop's margins.

## 3. Requirements

| Need | Requirement |
|---|---|
| Find and maintain books | Find real books by ISBN or title; search, filter, sort, add and edit, with clear validation |
| Record sales | Several books per sale; stock reduced exactly once; nothing half-saved |
| Fix mistakes | Cancel a sale (stock returned exactly once); correct stock with a recorded reason |
| See what's happening | Revenue, copies, transactions, trends, genres, best sellers, unsold books, for any period |
| Act on it, carefully | Plain-language observations with evidence and limits |
| Several people, several shops | Sign in with a password or Google; owners invite staff; each person sees only their own shops; staff limited to day-to-day work; who did what is recorded |
| Honesty | Nothing invented: real book details, owner-entered prices and stock, recorded sales only; revenue never called profit; partial periods marked; small samples flagged |

## 4. Data model

Each shop has its own SQLite file with five tables (`sql/schema.sql`); a separate `accounts.db` holds people, shops, roles and invite codes (`sql/accounts_schema.sql`):

```
books 1 ───< sale_items >─── 1 sales ─── 0..1 sale_cancellations
  1
  └──< stock_adjustments
```

| Decision | Why |
|---|---|
| `sales` and `sale_items` separate | One visit can include several books; each fact is stored once, and **transactions** (rows in `sales`) stay distinct from **copies sold** (sum of quantities) |
| Price stored on each sale line | Prices change; past revenue must not change with them |
| Money in whole **paise** | Binary floats lose money: `int(19.99 * 100)` is 1998. Conversion uses `Decimal` |
| Sale totals calculated, not stored | A stored total is a second copy of the truth that could disagree |
| Sales cancelled, never deleted | Deleting erases evidence; analytics count only `completed` sales |
| `sale_cancellations.sale_id` is the **primary key** | The database itself refuses a second cancellation |
| `STRICT` tables, `CHECK`, `UNIQUE`, foreign keys, `PRAGMA foreign_keys = ON` | The database refuses bad data even if application code has a bug. A test showed that without the PRAGMA, a sale line for a non-existent book was accepted |
| **One file per shop** instead of a `shop_id` column | With a column, every query, forever, must remember `WHERE shop_id = ?`, and one slip shows a shop another shop's sales. Separate files leave nothing to forget, and the tested analytics SQL didn't change |

## 5. Features and technical design

**Layers.** Pages (`views/`) only display; rules live in `services/` (plain Python) and are tested without a browser; one function in `database.py` opens every connection with the right settings.

**Recording a sale, in one transaction:**

```sql
-- for each book in the basket; zero rows changed = not enough stock
UPDATE books
SET stock_quantity = stock_quantity - :quantity
WHERE book_id = :book_id AND stock_quantity >= :quantity
```

The check and the change happen in one statement, so nothing can slip in between "is there enough?" and "take it". Any problem raises an error inside `with conn:`, which rolls back everything, including stock already reduced for earlier lines.

**Stock corrections** record before/after counts and a reason, and only apply if the stock still matches the number shown on screen (`… AND stock_quantity = <shown>`), so a stale page or a double click can't apply a correction twice.

**Real books from Open Library.** The owner looks a book up by ISBN (one exact edition) or searches by title or author (works across editions). Open Library is free, open and edited by volunteers, so it's usually right but not always: a search for *The God of Small Things* also returns study guides, translations and one record crediting the wrong author. So Lekha only **pre-fills** the add form, and the owner checks it. Two rules keep the data honest:
- **Edition facts** (publisher, year) are saved only from an ISBN match, because a title search describes the book in general, not the copy in hand.
- **Prices and stock** are never guessed. No free API knows a particular shop's prices (Google Books' free quota was refused during testing), and only the shop knows its stock.

Answers are cached for a day, errors are shown plainly ("Couldn't reach Open Library…"), and typing a book in always works offline. Adding the new columns to existing databases needed Lekha's first **migration**: numbered SQL files applied once each, tracked with SQLite's `PRAGMA user_version`.

**Accounts and roles.** People sign in with a username and password or with Google (Streamlit's built-in OpenID Connect sign-in). An owner invites staff with a one-time code. On every page run, `app.py` reads the person's role fresh from `accounts.db`, shows only the pages that role allows, and points every query at their chosen shop's file. The current shop is held in a `ContextVar`, not a global, because Streamlit serves every visitor from one Python process: a test runs two visits at once and checks neither sees the other's shop. Permissions are also enforced in the services, so a hidden button is never the only protection, and removing someone takes effect on their next click.

**Security** ([full list](security.md)): passwords are stored only as salted **scrypt** hashes, 10 to 128 characters, with very common ones refused; five wrong tries lock an account for 15 minutes, including on the change-password form; a wrong password and an unknown username look identical, in message and in timing; repeated failures from one device are limited; a tab is signed out after 60 idle minutes or when the password changes elsewhere; invite codes are stored as SHA-256 hashes, work once and expire after 7 days. Streamlit reads displayed text as Markdown, so names, titles and reasons go through an escaping helper: otherwise a book title like *The $100 Startup* would turn into maths, and a display name could load a picture from another website. Open Library answers are checked (only its own address is fetched, size capped, record IDs validated). By default only the computer running Lekha can open it, because it has no HTTPS. GitHub runs **pip-audit** and **bandit** on every push and weekly. User input reaches SQL only through `?` placeholders. Sorting, which can't use placeholders, picks from a fixed list. A test types `'; DROP TABLE books; --` into search.

## 6. Analytics and SQL

Every analytics query (`sql/analytics/`) starts from one shared definition, so no chart can count cancelled sales by accident:

```sql
WITH period_lines AS (
    SELECT s.sale_id, s.sale_datetime, si.book_id, b.genre, si.quantity,
           si.quantity * si.unit_price_paise AS revenue_paise
    FROM sales s
    JOIN sale_items si ON si.sale_id = s.sale_id
    JOIN books b       ON b.book_id = si.book_id
    WHERE s.status = 'completed'
      AND s.sale_datetime >= :start AND s.sale_datetime < :end   -- half-open range
      AND (:genre IS NULL OR b.genre = :genre)
)
SELECT book_id, SUM(quantity) AS copies,
       RANK() OVER (ORDER BY SUM(quantity) DESC) AS copies_rank   -- ties share a rank
FROM period_lines
GROUP BY book_id
```

| Work | Where | Why |
|---|---|---|
| Filter, join, sum, group, rank | SQL | Next to the data |
| Fill empty weeks with zero | pandas `reindex` | One line in pandas, awkward in SQL |
| Periods, percentages, wording | Python | Easy to test |

**Method: define, calculate by hand, then code.** Every metric was written out and worked by hand on the small sample dataset first (`docs/analytics.md`). The tests assert those numbers.

## 7. Results on the test dataset

The **fictional test dataset** (12 books, 15 sales, 1 cancelled) exists only inside the tests. Every figure was worked out by hand first:

| Figure | Hand calculation | App |
|---|---|---|
| Revenue | ₹11,144.00 | ₹11,144.00 |
| Transactions / copies | 14 / 29 | 14 / 29 |
| Average sale | 1,114,400 ÷ 14 = ₹796.00 | ₹796.00 |
| Top genre | Fiction ₹4,040.00 (36.3%) | same |
| Estimated gross profit | ₹3,992.00 on ₹10,247.00 covered (92.0%), margin 39.0% | same |

The app showed exactly those figures, and a page test still checks them.

An earlier version used a larger *generated* dataset for screenshots. It was removed: screenshots now show the real, empty shop and live Open Library results, so nothing in the project's pictures is invented.

**Observations** are written to match: *"Fiction brought in the most revenue: ₹4,040.00 of ₹11,144.00 (36.3%) across 14 sales. Possible action: consider a Fiction display. Limit: recorded sales can't show that a display would increase sales. Only 14 sales, so treat this as a hint, not a pattern."*

## 8. Interface and design decisions

- **Identity:** antique Indian manuscript art translated into a calm product: Manuscript Crimson and Persian Teal on parchment, Lora headings, Lato body, slightly rounded corners (6px), two original SVG ornaments (an arch and a rosette divider), used sparingly.
- **Practical navigation:** Overview, Books, Sales, Inventory, Insights, each role sees only the pages it can use. Team, Settings, switching shops and Sign out sit in an account menu at the end of the navigation bar, labelled with the person and the shop. Literary names ("The daily read", "Shelf check") appear only in section introductions.
- **Honest charts:** one series, one colour; partial periods drawn as outlines (shape, not colour); empty weeks shown as zero; bars instead of pies.
- **Phones:** a five-column basket grid fell apart when Streamlit stacked it, so basket lines became sentences ("1 copy × ₹399.00 = ₹399.00"); tables put decision columns straight after the title.
- **Tokens:** colours and a six-step spacing scale live in `.streamlit/config.toml` and `ui/styles.css`, ready to map onto Figma variables.

## 9. Testing

| Kind | What it proves | Count |
|---|---|---|
| Schema rules | Bad data is refused by the database itself | 34 |
| Test dataset | Queries match hand calculations | 10 |
| Services | Books, money, inventory, sales, analytics behave as defined, including rollbacks | 135 |
| Open Library and migration | Lookups and searches against **real saved Open Library responses** (no internet needed); genre suggestions; plain errors; a Phase 7 database upgraded without losing data | 31 |
| Accounts and shops | Password hashing, rules and lockout, Google accounts, invite codes, every role's limits, a shop never losing its last owner, two shops never seeing each other's books, two simultaneous visitors kept apart, who-did-what recorded | 45 |
| Security | Escaping of names and titles, limits on repeated attempts, password changes and lockout, Open Library answers checked, input sizes, safe server settings | 26 |
| Redesign foundations | Fair comparisons ("12% more than ₹43,080", and none when there's nothing to compare against); a summary sentence for every case, including a brand-new shop; today so far against the same time last week, to the minute; whole-rupee amounts with Indian grouping; the new page pieces escape text and never show a missing figure as a real one | 64 |
| Pages (`AppTest`) | Every page opens; sign up, create a shop and land on it; staff see no editing, stock correction, profit or Team page; removed staff lose access on their next click; an empty shop shows real zeros; a real book added by ISBN saves exactly what Open Library said plus the owner's price; a 2-copy sale reduces stock by exactly 2; a broken database shows a friendly message; a password change signs out other tabs; idle tabs are signed out; repeated failed sign-ins are refused; names show as typed, including in the account menu; Switch shop opens the chosen shop | 28 |
| **Total** | Run on every push and pull request by GitHub Actions | **373** |

**Testing the tests.** Twice I broke the code on purpose to check a test could fail: once removing the foreign-key PRAGMA (a bad sale line got in), once removing the sale rollback (stock was left at 6 instead of 8). Both times the relevant test caught it.

**Accessibility audit.** A script measured the contrast of every piece of text against its real background on all five pages. **37 failures** (chart axis text at 3.15:1) became **0**, and placeholder hints, measured separately, went from 3.89:1 to 6.61:1 (target 4.5:1).

**Mistakes the process caught**, all recorded in `docs/testing-log.md`: a form that didn't empty after saving (it would have allowed duplicate books), wrong expectations in my own tests (an alphabetical order, a float example), chart labels cut off on phones, and a claim in my own design notes about a "partial week" that turned out to be wrong.

## 10. Limitations and next steps

**Limitations**
- Runs on one computer or server, not hosted online yet, and without HTTPS of its own (so only that computer can open it by default).
- A password sign-in lasts until the tab is refreshed; there's no "forgot password" yet.
- Google sign-in hasn't yet been tried with real Google credentials.
- No delivery or supplier records, so profit uses each book's current cost and stock can't be rebuilt from history.
- No partial returns or discounts.
- Patterns only appear once real sales have been recorded; the tested dataset is far too small for patterns.
- Book details are only as good as Open Library's records, and looking books up needs the internet.
- The 30-sale "hint, not a pattern" threshold is a judgement call, not a statistical test.

**Next steps**
- A fuller visual redesign from Figma, using the existing tokens.
- Deliveries with cost per delivery, for accurate profit and a full stock history.
- Comparison with the previous period; CSV import and export.
- An online demo (with the caveat that free hosting resets its storage).

---

*Source: [github.com/priyal-baraya/lekha](https://github.com/priyal-baraya/lekha). Detailed reasoning: [decision log](decision-log.md) · [testing log](testing-log.md) · [analytics definitions](analytics.md).*
