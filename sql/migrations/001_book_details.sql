-- Migration 001: details about each book from Open Library (Phase 8).
-- ---------------------------------------------------------------------
-- Adds four optional columns to books. Every database, old or new, gets
-- them through this same file, applied once by database.apply_migrations().
-- Existing rows are kept; their new columns start empty (NULL).
--
--   publisher        the publisher of THIS edition (only saved from an
--                    ISBN lookup, where it is known for the exact edition)
--   published_year   the year THIS edition was published (same rule)
--   cover_id         Open Library's cover image number; the picture is at
--                    https://covers.openlibrary.org/b/id/<cover_id>-M.jpg
--   openlibrary_key  the Open Library record the details came from:
--                    /books/OL...M (an edition) or /works/OL...W (a work)

ALTER TABLE books ADD COLUMN publisher TEXT
    CHECK (publisher IS NULL OR length(trim(publisher)) > 0);

ALTER TABLE books ADD COLUMN published_year INTEGER
    CHECK (published_year IS NULL OR published_year BETWEEN 1450 AND 2100);

ALTER TABLE books ADD COLUMN cover_id INTEGER
    CHECK (cover_id IS NULL OR cover_id > 0);

ALTER TABLE books ADD COLUMN openlibrary_key TEXT
    CHECK (openlibrary_key IS NULL
           OR openlibrary_key GLOB '/books/OL*M'
           OR openlibrary_key GLOB '/works/OL*W');
