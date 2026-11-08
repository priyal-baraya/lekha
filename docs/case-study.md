# Lekha: a case study

*An inventory and sales insights tool for independent bookstores.*
*Python · SQLite · SQL · pandas · Streamlit · Altair · pytest*

> All data in this project is **fictional**. No real bookstore, customer or sale is involved. Results below describe invented datasets and exist to show the calculations are correct, not to make business claims.

---

## 1. The problem

A small independent bookstore often tracks stock and sales in spreadsheets or on paper. That makes ordinary questions hard to answer with confidence:

- Which books and genres actually sell?
- What is running low, and what hasn't moved?
- Did revenue go up or down this month?
- Was that stock count wrong because of theft, damage, or a typing mistake?

The data exists, but it isn't trustworthy enough, or summarised enough, to support decisions.

## 2. The user

The owner or manager of one small shop: knows their books and readers well, isn't a data specialist, has little time, and needs to trust a number before acting on it. That shaped two principles: **every figure must be checkable**, and **every suggestion must state its limits**.

## 3. Requirements

| Need | Requirement |
|---|---|
| Find and maintain books | Search, filter, sort, add and edit, with clear validation |
| Record sales | Several books per sale; stock reduced exactly once; nothing half-saved |
| Fix mistakes | Cancel a sale (stock returned exactly once); correct stock with a recorded reason |
| See what's happening | Revenue, copies, transactions, trends, genres, best sellers, unsold books, for any period |
| Act on it, carefully | Plain-language observations with evidence and limits |
| Honesty | Revenue never called profit; partial periods marked; small samples flagged; fictional data labelled |

## 4. Data model

Five SQLite tables (`sql/schema.sql`):

```
books 1 ───< sale_items >─── 1 sales ─── 0..1 sale_cancellations
  1
  └──< stock_adjustments
```

| Decision | Why |
|---|---|
| `sales` and `sale_items` separate | One visit can include several books; each fact is stored once, and **transactions** (rows in `sales`) stay distinct from **copies sold** (sum of quantities) |
| Price stored on each sale line | Prices change; past revenue must not change with them |
| Money in whole **paise** | Binary floats lose money: `int(19.99 * 100)` is 1998. Conversion uses `Decimal` |
| Sale totals calculated, not stored | A stored total is a second copy of the truth that could disagree |
| Sales cancelled, never deleted | Deleting erases evidence; analytics count only `completed` sales |
| `sale_cancellations.sale_id` is the **primary key** | The database itself refuses a second cancellation |
| `STRICT` tables, `CHECK`, `UNIQUE`, foreign keys, `PRAGMA foreign_keys = ON` | The database refuses bad data even if application code has a bug. A test showed that without the PRAGMA, a sale line for a non-existent book was accepted |

## 5. Features and technical design

**Layers.** Pages (`views/`) only display; rules live in `services/` (plain Python) and are tested without a browser; one function in `database.py` opens every connection with the right settings.

**Recording a sale, in one transaction:**

```sql
-- for each book in the basket; zero rows changed = not enough stock
UPDATE books
SET stock_quantity = stock_quantity - :quantity
WHERE book_id = :book_id AND stock_quantity >= :quantity
```

The check and the change happen in one statement, so nothing can slip in between "is there enough?" and "take it". Any problem raises an error inside `with conn:`, which rolls back everything, including stock already reduced for earlier lines.

**Stock corrections** record before/after counts and a reason, and only apply if the stock still matches the number shown on screen (`… AND stock_quantity = <shown>`), so a stale page or a double click can't apply a correction twice.

**Security:** user input reaches SQL only through `?` placeholders. Sorting, which can't use placeholders, picks from a fixed list. A test types `'; DROP TABLE books; --` into search.

## 6. Analytics and SQL

Every analytics query (`sql/analytics/`) starts from one shared definition, so no chart can count cancelled sales by accident:

```sql
WITH period_lines AS (
    SELECT s.sale_id, s.sale_datetime, si.book_id, b.genre, si.quantity,
           si.quantity * si.unit_price_paise AS revenue_paise
    FROM sales s
    JOIN sale_items si ON si.sale_id = s.sale_id
    JOIN books b       ON b.book_id = si.book_id
    WHERE s.status = 'completed'
      AND s.sale_datetime >= :start AND s.sale_datetime < :end   -- half-open range
      AND (:genre IS NULL OR b.genre = :genre)
)
SELECT book_id, SUM(quantity) AS copies,
       RANK() OVER (ORDER BY SUM(quantity) DESC) AS copies_rank   -- ties share a rank
FROM period_lines
GROUP BY book_id
```

| Work | Where | Why |
|---|---|---|
| Filter, join, sum, group, rank | SQL | Next to the data |
| Fill empty weeks with zero | pandas `reindex` | One line in pandas, awkward in SQL |
| Periods, percentages, wording | Python | Easy to test |

**Method: define, calculate by hand, then code.** Every metric was written out and worked by hand on the small sample dataset first (`docs/analytics.md`). The tests assert those numbers.

## 7. Results (fictional data)

**Hand-checked sample dataset** (12 books, 15 sales, 1 cancelled), the one the tests use:

| Figure | Hand calculation | App |
|---|---|---|
| Revenue | ₹11,144.00 | ₹11,144.00 |
| Transactions / copies | 14 / 29 | 14 / 29 |
| Average sale | 1,114,400 ÷ 14 = ₹796.00 | ₹796.00 |
| Top genre | Fiction ₹4,040.00 (36.3%) | same |
| Estimated gross profit | ₹3,992.00 on ₹10,247.00 covered (92.0%), margin 39.0% | same |

The app showed exactly those figures in the browser.

**Generated demo dataset** (`demo_data.py`: 30 invented books, 3 Aug – 7 Nov 2026, fixed random seed), used for screenshots: 434 completed and 13 cancelled sales, ₹2,41,752.00 revenue, Fiction the largest genre at 37.1%. These numbers come from a random generator: they show the app at a realistic size, and **say nothing about real bookstores**.

**Observations** are written to match: *"Fiction brought in the most revenue: ₹4,040.00 of ₹11,144.00 (36.3%) across 14 sales. Possible action: consider a Fiction display. Limit: recorded sales can't show that a display would increase sales. Only 14 sales, so treat this as a hint, not a pattern."*

## 8. Interface and design decisions

- **Identity:** antique Indian manuscript art translated into a calm product: Manuscript Crimson and Persian Teal on parchment, Lora headings, Lato body, square corners, two original SVG ornaments (an arch and a rosette divider), used sparingly.
- **Practical navigation:** Overview, Books, Sales, Inventory, Insights. Literary names ("The daily read", "Shelf check") appear only in section introductions.
- **Honest charts:** one series, one colour; partial periods drawn as outlines (shape, not colour); empty weeks shown as zero; bars instead of pies.
- **Phones:** a five-column basket grid fell apart when Streamlit stacked it, so basket lines became sentences ("1 copy × ₹399.00 = ₹399.00"); tables put decision columns straight after the title.
- **Tokens:** colours and a six-step spacing scale live in `.streamlit/config.toml` and `ui/styles.css`, ready to map onto Figma variables.

## 9. Testing

| Kind | What it proves | Count |
|---|---|---|
| Schema rules | Bad data is refused by the database itself | 34 |
| Sample data | Queries match hand calculations | 10 |
| Services | Books, money, inventory, sales, analytics behave as defined, including rollbacks | 135 |
| Pages (`AppTest`) | Every page opens; a 2-copy sale through the Sales page reduces stock by exactly 2; a broken database shows a friendly message | 11 |
| Demo data | Repeatable and internally consistent | 2 |
| **Total** | Run on every push and pull request by GitHub Actions | **192** |

**Testing the tests.** Twice I broke the code on purpose to check a test could fail: once removing the foreign-key PRAGMA (a bad sale line got in), once removing the sale rollback (stock was left at 6 instead of 8). Both times the relevant test caught it.

**Accessibility audit.** A script measured the contrast of every piece of text against its real background on all five pages. **37 failures** (chart axis text at 3.15:1) became **0**, and placeholder hints, measured separately, went from 3.89:1 to 6.61:1 (target 4.5:1).

**Mistakes the process caught**, all recorded in `docs/testing-log.md`: a form that didn't empty after saving (it would have allowed duplicate books), wrong expectations in my own tests (an alphabetical order, a float example), chart labels cut off on phones, and a claim in my own design notes about a "partial week" that turned out to be wrong.

## 10. Limitations and next steps

**Limitations**
- One shop, one user, one computer; no logins.
- No delivery or supplier records, so profit uses each book's current cost and stock can't be rebuilt from history.
- No partial returns or discounts.
- The small dataset can't show real patterns; the demo dataset is random by design.
- The 30-sale "hint, not a pattern" threshold is a judgement call, not a statistical test.

**Next steps**
- A fuller visual redesign from Figma, using the existing tokens.
- Deliveries with cost per delivery, for accurate profit and a full stock history.
- Comparison with the previous period; CSV import and export.
- An online demo (with the caveat that free hosting resets its storage).

---

*Source: [github.com/priyal-baraya/lekha](https://github.com/priyal-baraya/lekha). Detailed reasoning: [decision log](decision-log.md) · [testing log](testing-log.md) · [analytics definitions](analytics.md).*
