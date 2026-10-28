-- Lekha sample data. FICTIONAL.
-- ---------------------------------------------------------------------
-- Every title, author, ISBN, price and sale below is invented for
-- testing and demonstration. None of it comes from a real bookstore.
-- ISBNs start with 000, which no real 13-digit ISBN does.
--
-- The dataset is deliberately small so every number can be checked by
-- hand. docs/sample-data.md lists the situations it contains and the
-- hand-calculated results that tests/test_sample_data.py checks.
--
-- stock_quantity is the count on the shelf "today" (2026-10-28). There
-- are no restocking records yet, so stock cannot be rebuilt from sales.

BEGIN;

INSERT INTO books
    (book_id, isbn, title, author, genre,
     selling_price_paise, cost_price_paise, stock_quantity, reorder_level)
VALUES
    ( 1, '0000000000001', 'The Monsoon Ledger',          'Asha Varkey',    'Fiction',  39900, 24000, 8, 3),
    ( 2, '0000000000002', 'Salt and Saffron',            'Meera Pillai',   'Cookery',  55000, 33000, 2, 2),
    ( 3, '0000000000003', 'The Lighthouse at Kovalam',   'Rohan Dsouza',   'Mystery',  34900, 21000, 6, 3),
    ( 4, '0000000000004', 'Letters to a Quiet River',    'Nila Sen',       'Poetry',   25000, 15000, 5, 2),
    ( 5, '0000000000005', 'The Cartographer''s Daughter','Asha Varkey',    'Fiction',  44900, 27000, 0, 2),
    ( 6, '0000000000006', 'A Short History of Ink',      'Farhan Qureshi', 'History',  59900, 36000, 4, 2),
    ( 7, '0000000000007', 'The Clockmaker''s Cat',       'Tara Menon',     'Children', 29900, NULL,  7, 3),
    ( 8, '0000000000008', 'Murder on the Night Mail',    'Rohan Dsouza',   'Mystery',  32900, 20000, 5, 3),
    ( 9, '0000000000009', 'Ten Thousand Mangoes',        'Tara Menon',     'Children', 27500, 16500, 1, 3),
    (10, '0000000000010', 'The Silk Road Atlas',         'Farhan Qureshi', 'History',  79900, 48000, 3, 1),
    (11, '0000000000011', 'Small Hours',                 'Nila Sen',       'Poetry',   22500, 13500, 4, 2),
    (12, '0000000000012', 'Harbour Lights',              'Kabir Rao',      'Fiction',  37500, 22500, 6, 2);

INSERT INTO sales (sale_id, sale_datetime, status) VALUES
    ( 1, '2026-10-01 10:42:00', 'completed'),
    ( 2, '2026-10-02 16:05:00', 'completed'),
    ( 3, '2026-10-04 11:30:00', 'completed'),
    ( 4, '2026-10-05 13:15:00', 'completed'),
    ( 5, '2026-10-07 18:20:00', 'completed'),
    ( 6, '2026-10-09 12:00:00', 'completed'),
    ( 7, '2026-10-11 15:45:00', 'completed'),
    ( 8, '2026-10-12 17:10:00', 'completed'),
    ( 9, '2026-10-14 11:05:00', 'cancelled'),
    (10, '2026-10-16 14:30:00', 'completed'),
    (11, '2026-10-18 10:15:00', 'completed'),
    (12, '2026-10-20 16:50:00', 'completed'),
    (13, '2026-10-22 12:40:00', 'completed'),
    (14, '2026-10-24 18:05:00', 'completed'),
    (15, '2026-10-26 11:55:00', 'completed');

-- Book 1 sold at 34900 until its price rose to 39900 on 2026-10-12.
INSERT INTO sale_items (sale_id, book_id, quantity, unit_price_paise) VALUES
    ( 1,  1, 2, 34900),
    ( 1,  3, 1, 34900),
    ( 2,  2, 1, 55000),
    ( 3,  7, 2, 29900),
    ( 3,  9, 1, 27500),
    ( 4,  1, 1, 34900),
    ( 5,  4, 1, 25000),
    ( 5,  5, 1, 44900),
    ( 6,  8, 1, 32900),
    ( 6,  3, 1, 34900),
    ( 7,  6, 1, 59900),
    ( 8,  1, 1, 39900),
    ( 8,  5, 2, 44900),
    ( 9, 10, 1, 79900),   -- sale 9 was cancelled
    (10,  9, 2, 27500),
    (10,  7, 1, 29900),
    (11,  2, 2, 55000),
    (12,  8, 2, 32900),
    (13,  1, 2, 39900),
    (13,  4, 1, 25000),
    (14,  5, 1, 44900),
    (14,  6, 1, 59900),
    (15,  3, 1, 34900);

COMMIT;
