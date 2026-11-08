-- Books with NO completed sales in the period, most copies on the shelf first.
--
-- NOT EXISTS asks "is there any matching row?" and stops at the first
-- one. (sql/01_first_queries.sql Q9 answers a similar question with a
-- LEFT JOIN; both are common.)
-- This is "no recorded sales", not "slow-selling": Lekha doesn't know
-- when each book arrived, so a new book can't be judged yet.
-- Sample data, 1–26 Oct 2026, all genres: books 12, 11, 10.

SELECT b.book_id,
       b.title,
       b.author,
       b.genre,
       b.stock_quantity
FROM books AS b
WHERE (:genre IS NULL OR b.genre = :genre)
  AND NOT EXISTS (SELECT 1 FROM period_lines AS pl WHERE pl.book_id = b.book_id)
ORDER BY b.stock_quantity DESC, b.title
