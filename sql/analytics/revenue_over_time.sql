-- Revenue, copies and transactions per day, week or month.
--
-- :grain is 'day', 'week' or 'month'. Each sale is placed in a bucket
-- named after the bucket's first day:
--   day   -> the date itself
--   week  -> the Monday of its week: jump forward to Sunday
--            ('weekday 0'), then back 6 days
--   month -> the first of the month
-- Only buckets that HAVE sales come back from here. Empty buckets are
-- filled with zero in Python (pandas), so gaps show as 0, not missing.
--
-- Sample data, weekly, 1–26 Oct 2026:
--   2026-09-28: 247000   2026-10-05: 232500   2026-10-12: 324600
--   2026-10-19: 275400   2026-10-26:  34900

SELECT CASE :grain
           WHEN 'day'   THEN date(sale_datetime)
           WHEN 'week'  THEN date(sale_datetime, 'weekday 0', '-6 days')
           WHEN 'month' THEN date(sale_datetime, 'start of month')
       END                     AS bucket_start,
       SUM(revenue_paise)      AS revenue_paise,
       SUM(quantity)           AS copies,
       COUNT(DISTINCT sale_id) AS transactions
FROM period_lines
GROUP BY bucket_start
ORDER BY bucket_start
