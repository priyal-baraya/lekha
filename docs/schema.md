# Database schema

The schema lives in [`sql/schema.sql`](../sql/schema.sql). This page explains it.

## Overview

```
books 1 ───────< sale_items >─────── 1 sales
(one book can appear       (one sale can contain
 in many sale lines)        many sale lines)
```

- **books**: one row per title the store stocks
- **sales**: one row per transaction at the till
- **sale_items**: one row per book within a sale
- **sale_cancellations**: when and why a sale was cancelled (added in Phase 4)
- **stock_adjustments**: one row per manual stock correction (added in Phase 3)

## Key ideas

| Term | Meaning | In Lekha |
|---|---|---|
| Primary key | A column whose value is unique per row and never changes | `book_id`, `sale_id`, `sale_item_id`, numbered by SQLite |
| Foreign key | A column holding another table's primary key, creating a link the database enforces | `sale_items.sale_id` → `sales`, `sale_items.book_id` → `books` |
| Constraint | A rule checked on every insert and update | `quantity > 0`, unique ISBN, valid status |
| STRICT table | SQLite rejects values of the wrong type | Text in a number column is refused |
| Transaction | Several changes that succeed or fail together | Recording a sale (Phase 4) |
| Index | A sorted lookup list that speeds up searches | `sale_items.book_id`, `sales.sale_datetime` |

## Tables

### `books`

| Column | Type | Rule | Purpose |
|---|---|---|---|
| `book_id` | INTEGER | primary key | Stable identity |
| `isbn` | TEXT | unique; optional; 10 or 13 characters of digits or X | Stops the same edition being added twice |
| `title` | TEXT | required, not blank | |
| `author` | TEXT | required, not blank | |
| `genre` | TEXT | required, not blank | Revenue-by-genre analysis |
| `selling_price_paise` | INTEGER | ≥ 0 | Current shelf price |
| `cost_price_paise` | INTEGER | ≥ 0; optional | Purchase cost per copy. NULL means unknown, so profit can't be calculated for that book |
| `stock_quantity` | INTEGER | ≥ 0, default 0 | Copies on the shelf now |
| `reorder_level` | INTEGER | ≥ 0, default 0 | Low-stock alert threshold |
| `publisher` | TEXT | optional, not blank | Publisher of this edition. Saved from an ISBN lookup (an exact edition) or typed by the owner, never guessed from a title search |
| `published_year` | INTEGER | optional, 1450–2100 | Year this edition was published (same rule) |
| `cover_id` | INTEGER | optional, > 0 | Open Library's cover number; the picture is at `https://covers.openlibrary.org/b/id/<cover_id>-M.jpg` |
| `openlibrary_key` | TEXT | optional; `/books/OL…M` (an edition) or `/works/OL…W` (a work) | Which Open Library record the details came from, so they can be traced and checked |

The last four columns were added in Phase 8 by a migration (see below).

## Migrations: changing the schema safely

`CREATE TABLE IF NOT EXISTS` can create a missing table, but it can't add a column to a table that already holds data. Schema changes after the first release go in numbered files in [`sql/migrations/`](../sql/migrations/):

| File | What it does |
|---|---|
| `001_book_details.sql` | Adds `publisher`, `published_year`, `cover_id` and `openlibrary_key` to `books` (Phase 8) |

SQLite keeps a spare whole number in every database file's header, `PRAGMA user_version`. `database.apply_migrations()` runs every migration numbered higher than it, in order. Each file and its new version number run in one transaction, so a failure leaves the database as it was. New databases go through exactly the same files, so old and new databases always end up identical. It runs on every start, and a database already up to date changes nothing.

Tested: a database in the Phase 7 shape with a book in it is upgraded to version 1 with the book kept and its new columns empty; running it again applies nothing; the database refuses a bad cover number or record reference.

### `sales`

| Column | Type | Rule | Purpose |
|---|---|---|---|
| `sale_id` | INTEGER | primary key | |
| `sale_datetime` | TEXT | must be a real date and time in the form `YYYY-MM-DD HH:MM:SS` | When it happened, in store local time (IST) |
| `status` | TEXT | `completed` or `cancelled`, default `completed` | Cancel without deleting history |

### `sale_items`

| Column | Type | Rule | Purpose |
|---|---|---|---|
| `sale_item_id` | INTEGER | primary key | |
| `sale_id` | INTEGER | foreign key → `sales`; delete restricted | Which transaction |
| `book_id` | INTEGER | foreign key → `books`; delete restricted | Which book |
| `quantity` | INTEGER | > 0 | Copies of this book in this sale |
| `unit_price_paise` | INTEGER | ≥ 0 | Price per copy **at the time of sale** |
| (`sale_id`, `book_id`) | | unique together | One line per book per sale |

### `sale_cancellations` (Phase 4)

| Column | Type | Rule | Purpose |
|---|---|---|---|
| `sale_id` | INTEGER | **primary key** and foreign key → `sales` | Which sale. Being the primary key, it can appear only once: the database itself refuses a second cancellation |
| `cancelled_at` | TEXT | real date and time | When |
| `reason` | TEXT | required, not blank | Why |

`sales.status` is set to `cancelled` in the same transaction that inserts this row, and a test checks that the two always agree.

**Why a new table instead of new columns on `sales`?** Adding columns to a table that already holds data needs a *migration* (a script that upgrades existing databases), and SQLite limits which rules can be added that way. A new table is created by `CREATE TABLE IF NOT EXISTS` on start-up, like `stock_adjustments`.

### `stock_adjustments` (Phase 3)

| Column | Type | Rule | Purpose |
|---|---|---|---|
| `adjustment_id` | INTEGER | primary key | |
| `book_id` | INTEGER | foreign key → `books`; delete restricted | Which book |
| `adjusted_at` | TEXT | real date and time, `YYYY-MM-DD HH:MM:SS` | When |
| `quantity_before` | INTEGER | ≥ 0 | Stock before the correction |
| `quantity_after` | INTEGER | ≥ 0; must differ from `quantity_before` | Stock after the correction |
| `reason` | TEXT | `shelf_count`, `damaged_or_lost`, `delivery_received` or `other` | Why it changed |
| `note` | TEXT | required when the reason is `other` | Explanation |

The change itself (`quantity_after − quantity_before`) is calculated, not stored.

## Design decisions

**Sales and sale items are separate.** One visit can include several books. Keeping the transaction's facts (date, status) in `sales` and each book's facts in `sale_items` stores every fact once. It also separates **transactions** (rows in `sales`) from **copies sold** (the sum of `quantity`).

**The price is recorded on each sale line.** `books.selling_price_paise` is the price *now*. `sale_items.unit_price_paise` is what the customer actually paid. Without it, a price change would rewrite past revenue. The sample data shows this: book 1 sold at ₹349 before its price rose to ₹399.

**Money is whole paise.** ₹349.00 is stored as `34900`. Decimal numbers like 0.1 can't be stored exactly in binary, so totals of many decimal prices drift. Whole numbers don't. Values are converted to rupees only for display.

**A sale's total is calculated, not stored.** The total is `SUM(quantity × unit_price_paise)` over the sale's lines. Storing it as well would create two copies of one truth that could disagree.

**Cancelled sales are marked, not deleted.** Analytics count only `status = 'completed'`. `services.sales.cancel_sale` marks the sale, returns its stock and records when and why, in one transaction.

**Books with sales history can't be deleted** (`ON DELETE RESTRICT`), because that would orphan their sale lines.

**Genre is plain text** rather than a separate table. This keeps queries simple. The app will offer a dropdown of existing genres to prevent variants like "fiction" vs "Fiction". Revisit if that proves insufficient.

**Foreign keys must be switched on per connection.** SQLite ignores them by default. `database.get_connection()` runs `PRAGMA foreign_keys = ON` every time. A check in the testing log showed that without it, a sale line for a missing book is accepted.

## Rules the schema cannot enforce (handled in application code)

| Rule | Where it will be enforced |
|---|---|
| A sale has at least one line | Done (Phase 4): `record_sale` refuses an empty sale |
| A sale can't sell more copies than are in stock | Done (Phase 4): `UPDATE … SET stock_quantity = stock_quantity - n WHERE … AND stock_quantity >= n`, checked and changed in one statement |
| Recording a sale reduces stock exactly once | Done (Phase 4): sale, lines and stock updates in one transaction |
| Cancelling a sale returns its stock exactly once | Done (Phase 4): only a `completed` sale can change, and `sale_cancellations.sale_id` is a primary key |
| Stock corrections update stock and history together | Done (Phase 3): `services.inventory.correct_stock`, one transaction |
| A correction is checked against the stock the user saw | Done (Phase 3): `UPDATE … WHERE stock_quantity = <number shown>` |

## How it supports the business questions

| Question | Tables used |
|---|---|
| Which books sell the most? | `sale_items` + `sales` (completed) grouped by `book_id`, joined to `books` for titles |
| Which genres earn the most? | The same, grouped by `books.genre` |
| What is running low? | `books` alone: `stock_quantity <= reorder_level` |
| What hasn't sold recently? | `books` LEFT JOIN `sale_items` + `sales` filtered by date |
| How are sales changing over time? | `sales.sale_datetime` grouped by day, week or month |
| Estimated gross profit | `sale_items` × (`unit_price_paise` − `books.cost_price_paise`), only where cost is known. Note this uses *today's* cost, a limitation to state clearly |
