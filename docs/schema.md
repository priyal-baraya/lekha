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

## Design decisions

**Sales and sale items are separate.** One visit can include several books. Keeping the transaction's facts (date, status) in `sales` and each book's facts in `sale_items` stores every fact once. It also separates **transactions** (rows in `sales`) from **copies sold** (the sum of `quantity`).

**The price is recorded on each sale line.** `books.selling_price_paise` is the price *now*. `sale_items.unit_price_paise` is what the customer actually paid. Without it, a price change would rewrite past revenue. The sample data shows this: book 1 sold at ₹349 before its price rose to ₹399.

**Money is whole paise.** ₹349.00 is stored as `34900`. Decimal numbers like 0.1 can't be stored exactly in binary, so totals of many decimal prices drift. Whole numbers don't. Values are converted to rupees only for display.

**A sale's total is calculated, not stored.** The total is `SUM(quantity × unit_price_paise)` over the sale's lines. Storing it as well would create two copies of one truth that could disagree.

**Cancelled sales are marked, not deleted.** Analytics count only `status = 'completed'`. Phase 4 will cancel a sale and return its stock in one transaction.

**Books with sales history can't be deleted** (`ON DELETE RESTRICT`), because that would orphan their sale lines.

**Genre is plain text** rather than a separate table. This keeps queries simple. The app will offer a dropdown of existing genres to prevent variants like "fiction" vs "Fiction". Revisit if that proves insufficient.

**Foreign keys must be switched on per connection.** SQLite ignores them by default. `database.get_connection()` runs `PRAGMA foreign_keys = ON` every time. A check in the testing log showed that without it, a sale line for a missing book is accepted.

## Rules the schema cannot enforce (handled in application code later)

| Rule | Where it will be enforced |
|---|---|
| A sale has at least one line | Phase 4 sale recording |
| A sale can't sell more copies than are in stock | Phase 4, inside the same transaction |
| Recording a sale reduces stock exactly once | Phase 4, one transaction |
| Cancelling a sale returns its stock exactly once | Phase 4, one transaction |
| Stock corrections are recorded with a reason | Phase 3 (likely a new table) |

## How it supports the business questions

| Question | Tables used |
|---|---|
| Which books sell the most? | `sale_items` + `sales` (completed) grouped by `book_id`, joined to `books` for titles |
| Which genres earn the most? | The same, grouped by `books.genre` |
| What is running low? | `books` alone: `stock_quantity <= reorder_level` |
| What hasn't sold recently? | `books` LEFT JOIN `sale_items` + `sales` filtered by date |
| How are sales changing over time? | `sales.sale_datetime` grouped by day, week or month |
| Estimated gross profit | `sale_items` × (`unit_price_paise` − `books.cost_price_paise`), only where cost is known. Note this uses *today's* cost, a limitation to state clearly |
