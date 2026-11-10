-- Lekha database schema
-- ---------------------------------------------------------------------
-- Tables: books, sales, sale_items, sale_cancellations, stock_adjustments.
-- See docs/schema.md for the reasoning behind every column and rule.
--
-- Conventions
--   * Money is stored in paise as whole numbers (Rs 349.00 -> 34900),
--     because decimal numbers like 0.1 cannot be stored exactly.
--   * Dates and times are text in the form 'YYYY-MM-DD HH:MM:SS',
--     in the store's local time (India Standard Time).
--   * STRICT makes SQLite reject values of the wrong type, for example
--     the text 'twelve' in an INTEGER column. Without STRICT, SQLite
--     would quietly store it.
--   * Foreign keys are only enforced when each connection runs
--     PRAGMA foreign_keys = ON. database.py does that.
--   * IF NOT EXISTS makes this file safe to run more than once.


-- One row per title the store stocks.
-- More columns (publisher, published_year, cover_id, openlibrary_key) are
-- added by sql/migrations/001_book_details.sql, so old and new databases
-- get them the same way.
CREATE TABLE IF NOT EXISTS books (
    book_id             INTEGER PRIMARY KEY,
    isbn                TEXT UNIQUE
                        CHECK (isbn IS NULL
                               OR (length(isbn) IN (10, 13) AND isbn NOT GLOB '*[^0-9X]*')),
    title               TEXT NOT NULL CHECK (length(trim(title)) > 0),
    author              TEXT NOT NULL CHECK (length(trim(author)) > 0),
    genre               TEXT NOT NULL CHECK (length(trim(genre)) > 0),
    selling_price_paise INTEGER NOT NULL CHECK (selling_price_paise >= 0),
    cost_price_paise    INTEGER CHECK (cost_price_paise >= 0),   -- NULL means "not known"
    stock_quantity      INTEGER NOT NULL DEFAULT 0 CHECK (stock_quantity >= 0),
    reorder_level       INTEGER NOT NULL DEFAULT 0 CHECK (reorder_level >= 0)
) STRICT;


-- One row per transaction at the till.
-- A sale's total is not stored: it is calculated from its sale_items.
CREATE TABLE IF NOT EXISTS sales (
    sale_id       INTEGER PRIMARY KEY,
    -- strftime() rebuilds the text from the date it understands. If the
    -- result is not identical, the input was badly formatted or impossible
    -- (like month 13). "IS" is used instead of "=" because strftime()
    -- returns NULL for nonsense input, and a CHECK that evaluates to NULL
    -- would quietly pass.
    sale_datetime TEXT NOT NULL
                  CHECK (strftime('%Y-%m-%d %H:%M:%S', sale_datetime) IS sale_datetime),
    status        TEXT NOT NULL DEFAULT 'completed'
                  CHECK (status IN ('completed', 'cancelled'))
) STRICT;


-- One row per book within a sale.
CREATE TABLE IF NOT EXISTS sale_items (
    sale_item_id     INTEGER PRIMARY KEY,
    sale_id          INTEGER NOT NULL REFERENCES sales (sale_id) ON DELETE RESTRICT,
    book_id          INTEGER NOT NULL REFERENCES books (book_id) ON DELETE RESTRICT,
    quantity         INTEGER NOT NULL CHECK (quantity > 0),
    unit_price_paise INTEGER NOT NULL CHECK (unit_price_paise >= 0),  -- price at the time of sale
    UNIQUE (sale_id, book_id)   -- the same book appears once per sale; use quantity for copies
) STRICT;


-- One row per cancelled sale (Phase 4): when and why it was cancelled.
-- sale_id is the PRIMARY KEY, so the database itself refuses a second
-- cancellation of the same sale. sales.status is set to 'cancelled' in
-- the same transaction that inserts this row.
CREATE TABLE IF NOT EXISTS sale_cancellations (
    sale_id      INTEGER PRIMARY KEY REFERENCES sales (sale_id) ON DELETE RESTRICT,
    cancelled_at TEXT NOT NULL
                 CHECK (strftime('%Y-%m-%d %H:%M:%S', cancelled_at) IS cancelled_at),
    reason       TEXT NOT NULL CHECK (length(trim(reason)) > 0)
) STRICT;


-- One row per manual change to a book's stock (Phase 3).
-- Stock never changes silently: every correction records the count
-- before and after, why it changed, and when.
CREATE TABLE IF NOT EXISTS stock_adjustments (
    adjustment_id   INTEGER PRIMARY KEY,
    book_id         INTEGER NOT NULL REFERENCES books (book_id) ON DELETE RESTRICT,
    adjusted_at     TEXT NOT NULL
                    CHECK (strftime('%Y-%m-%d %H:%M:%S', adjusted_at) IS adjusted_at),
    quantity_before INTEGER NOT NULL CHECK (quantity_before >= 0),
    quantity_after  INTEGER NOT NULL CHECK (quantity_after >= 0),
    reason          TEXT NOT NULL
                    CHECK (reason IN ('shelf_count', 'damaged_or_lost', 'delivery_received', 'other')),
    note            TEXT,
    CHECK (quantity_after <> quantity_before),                          -- a correction must change something
    CHECK (reason <> 'other' OR length(trim(coalesce(note, ''))) > 0)  -- "other" needs an explanation
) STRICT;


-- Indexes: sorted lookup lists that let SQLite find rows without reading
-- the whole table, like the index at the back of a book.
-- (sale_id lookups already use the index created by UNIQUE above.)
CREATE INDEX IF NOT EXISTS idx_sale_items_book_id ON sale_items (book_id);
CREATE INDEX IF NOT EXISTS idx_sales_sale_datetime ON sales (sale_datetime);
CREATE INDEX IF NOT EXISTS idx_stock_adjustments_book_id ON stock_adjustments (book_id);
