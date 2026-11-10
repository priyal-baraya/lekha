-- Migration 002: who did what (Phase 9, accounts and shared shops).
-- ---------------------------------------------------------------------
-- When several people share a shop, every sale, cancellation and stock
-- correction records who made it. The number is a user_id from the
-- accounts database (data/accounts.db). It's a different file, so SQLite
-- can't enforce it as a foreign key; the app looks the names up there.
-- Older rows, made before accounts existed, stay NULL ("not recorded").

ALTER TABLE sales ADD COLUMN recorded_by INTEGER
    CHECK (recorded_by IS NULL OR recorded_by > 0);

ALTER TABLE sale_cancellations ADD COLUMN cancelled_by INTEGER
    CHECK (cancelled_by IS NULL OR cancelled_by > 0);

ALTER TABLE stock_adjustments ADD COLUMN recorded_by INTEGER
    CHECK (recorded_by IS NULL OR recorded_by > 0);
