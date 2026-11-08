-- Books ranked by copies sold, with their revenue.
--
-- RANK() is a window function: it looks across all the grouped rows to
-- number them, giving tied books the same rank and skipping the next
-- numbers. Sample data, 1–26 Oct 2026: book 1 (6 copies) rank 1, book 5
-- (4) rank 2, five books with 3 copies all rank 3, then two books with
-- 2 copies rank 8 (not 4).

SELECT book_id,
       title,
       author,
       genre,
       SUM(quantity)      AS copies,
       SUM(revenue_paise) AS revenue_paise,
       RANK() OVER (ORDER BY SUM(quantity) DESC) AS copies_rank
FROM period_lines
GROUP BY book_id, title, author, genre
ORDER BY copies_rank, revenue_paise DESC, title
