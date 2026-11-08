-- Headline figures for the period.
-- Sample data, 1–26 Oct 2026, all genres: 1114400 paise, 29 copies, 14 transactions.
-- COALESCE turns "no rows" (NULL) into 0, so an empty period reads as zero.
-- COUNT(DISTINCT sale_id): a sale with three lines is still one transaction.

SELECT COALESCE(SUM(revenue_paise), 0) AS revenue_paise,
       COALESCE(SUM(quantity), 0)      AS copies,
       COUNT(DISTINCT sale_id)         AS transactions
FROM period_lines
