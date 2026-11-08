-- Revenue and copies per genre, largest revenue first.
-- Sample data, 1–26 Oct 2026: Fiction 404000, Mystery 203400, Children 172200,
-- Cookery 165000, History 119800, Poetry 50000 (total 1114400).
-- Percentages are worked out in Python from these exact whole numbers.

SELECT genre,
       SUM(revenue_paise) AS revenue_paise,
       SUM(quantity)      AS copies
FROM period_lines
GROUP BY genre
ORDER BY revenue_paise DESC, genre
