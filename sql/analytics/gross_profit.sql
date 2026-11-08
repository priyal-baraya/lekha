-- ESTIMATED gross profit for the period.
--
-- Estimated gross profit = for each line, copies x (price paid - cost per copy).
-- Two limits, both shown on screen:
--   1. cost_price_paise is the book's CURRENT cost, not what each copy
--      actually cost when bought, so this is an estimate.
--   2. Books with no recorded cost are left out entirely (not counted as
--      zero cost), and the page reports how much revenue is covered.
-- CASE WHEN ... END gives NULL for books without a cost, and SUM skips NULLs.
--
-- Sample data, 1–26 Oct 2026: profit 399200 on 1024700 of revenue with a
-- known cost, out of 1114400 total (book 7 has no cost).

SELECT COALESCE(SUM(revenue_paise), 0) AS revenue_paise,
       COALESCE(SUM(CASE WHEN cost_price_paise IS NOT NULL
                         THEN revenue_paise END), 0) AS revenue_with_cost_paise,
       COALESCE(SUM(CASE WHEN cost_price_paise IS NOT NULL
                         THEN quantity * (unit_price_paise - cost_price_paise) END), 0)
                                       AS estimated_gross_profit_paise
FROM period_lines
