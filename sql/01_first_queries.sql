-- First queries: from simple SELECT to JOIN.
-- ---------------------------------------------------------------------
-- Run them all against the sample database with:
--     .\.venv\Scripts\python.exe query.py sql\01_first_queries.sql
-- Each "Expected" note is for the FICTIONAL sample data and was worked
-- out by hand (see docs/sample-data.md). Money is shown in rupees by
-- dividing paise by 100.0 (the .0 keeps the decimal part).


-- Q1. SELECT: which books do we have?
-- Expected: 12 rows.
SELECT book_id, title, author, genre
FROM books;


-- Q2. WHERE: which books are mysteries?
-- Expected: books 3 and 8.
SELECT book_id, title, author
FROM books
WHERE genre = 'Mystery';


-- Q3. ORDER BY: which books have the fewest copies on the shelf?
-- Expected: book 5 first (0 copies), then book 9 (1), then book 2 (2).
SELECT book_id, title, stock_quantity
FROM books
ORDER BY stock_quantity ASC, title ASC;


-- Q4. Comparing two columns: which books are at or below their reorder level?
-- Expected: books 2 (2 <= 2), 5 (0 <= 2) and 9 (1 <= 3).
SELECT book_id, title, stock_quantity, reorder_level
FROM books
WHERE stock_quantity <= reorder_level
ORDER BY stock_quantity;


-- Q5. Aggregates and NULL: how many books, and how many have a known cost price?
-- Expected: 12 books, 11 with cost. COUNT(column) skips NULLs; COUNT(*) counts rows.
SELECT COUNT(*)                AS books,
       COUNT(cost_price_paise) AS books_with_cost_price
FROM books;


-- Q6. GROUP BY: how many titles in each genre?
-- Expected: Children 2, Cookery 1, Fiction 3, History 2, Mystery 2, Poetry 2.
SELECT genre, COUNT(*) AS titles
FROM books
GROUP BY genre
ORDER BY genre;


-- Q7. JOIN: what was in sale 1, with book titles instead of numbers?
-- Expected: 2 x The Monsoon Ledger at 349.00, 1 x The Lighthouse at Kovalam at 349.00.
SELECT si.sale_id,
       b.title,
       si.quantity,
       si.unit_price_paise / 100.0                 AS unit_price_rupees,
       si.quantity * si.unit_price_paise / 100.0   AS line_total_rupees
FROM sale_items AS si
JOIN books AS b ON b.book_id = si.book_id
WHERE si.sale_id = 1;


-- Q8. JOIN + filter + SUM: total revenue from completed sales.
-- Expected: 11144.00 rupees from 14 transactions and 29 copies.
-- The cancelled sale (9) is excluded by the WHERE clause.
SELECT COUNT(DISTINCT s.sale_id)                     AS transactions,
       SUM(si.quantity)                              AS copies_sold,
       SUM(si.quantity * si.unit_price_paise) / 100.0 AS revenue_rupees
FROM sale_items AS si
JOIN sales AS s ON s.sale_id = si.sale_id
WHERE s.status = 'completed';


-- Q9. LEFT JOIN: which books have no completed sales?
-- Expected: books 10, 11 and 12.
-- A plain JOIN would drop books with no sale lines at all (11 and 12).
-- LEFT JOIN keeps every book. The status check sits in the ON clause, so
-- the cancelled sale of book 10 simply fails to match instead of
-- removing book 10 from the results.
SELECT b.book_id, b.title
FROM books AS b
LEFT JOIN sale_items AS si ON si.book_id = b.book_id
LEFT JOIN sales      AS s  ON s.sale_id = si.sale_id AND s.status = 'completed'
GROUP BY b.book_id, b.title
HAVING COUNT(s.sale_id) = 0
ORDER BY b.book_id;
