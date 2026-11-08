-- period_lines: the shared starting point for every analytics query.
-- ---------------------------------------------------------------------
-- One row per book in a COMPLETED sale inside the chosen period,
-- optionally limited to one genre. services/analytics.py places this
-- in front of each query as:  WITH period_lines AS ( <this> ) <query>
-- so every metric uses exactly the same definition of "a sale".
--
-- Parameters
--   :start   first moment included,  e.g. '2026-10-01 00:00:00'
--   :end     first moment EXCLUDED,  e.g. '2026-11-01 00:00:00'
--            ("before the next day" leaves no gap at 23:59:59)
--   :genre   one genre, or NULL for all genres

SELECT s.sale_id,
       s.sale_datetime,
       si.book_id,
       b.title,
       b.author,
       b.genre,
       b.cost_price_paise,
       si.quantity,
       si.unit_price_paise,
       si.quantity * si.unit_price_paise AS revenue_paise
FROM sales AS s
JOIN sale_items AS si ON si.sale_id = s.sale_id
JOIN books AS b       ON b.book_id = si.book_id
WHERE s.status = 'completed'
  AND s.sale_datetime >= :start
  AND s.sale_datetime <  :end
  AND (:genre IS NULL OR b.genre = :genre)
