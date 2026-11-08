# Analytics: definitions and hand-checked results

Every figure on the Insights and Overview pages is defined here, together with the result for the **fictional** sample data worked out by hand. `tests/test_analytics.py` checks the code against these numbers. They are facts about an invented dataset, used to prove the calculations are right. They are not business findings.

## Common rules

- **Completed sales only.** Cancelled sales never count.
- **Period:** whole days, both ends included. In SQL: `sale_datetime >= 'start 00:00:00' AND sale_datetime < 'day after end 00:00:00'`. "Before the next day" leaves no gap at 23:59:59. A test records sales at 23:59:59 on the last day (counted) and 00:00:00 the next day (not counted).
- **One shared definition.** Every query starts from `sql/analytics/_period_lines.sql`: one row per book in a completed sale in the period, optionally limited to one genre.
- **Money** is whole paise. Percentages are calculated with `Decimal` and rounded half up to one decimal place.

## Where each calculation lives

| Work | Where | Why |
|---|---|---|
| Filtering, joining, summing, grouping | SQL (`sql/analytics/*.sql`) | Done next to the data; only small results come back |
| Ranking with ties | SQL window function `RANK()` | Tied books share a rank |
| Filling empty days, weeks and months with 0 | pandas `reindex` | Simple in pandas, awkward in SQL |
| Periods, percentages, partial-period flags, wording | Python (`services/analytics.py`) | Presentation logic, easy to test |

## Definitions and sample results (1–26 October 2026, all genres)

| Metric | Definition | Result |
|---|---|---|
| Revenue | Σ quantity × price paid | 1,114,400 paise = **₹11,144.00** |
| Copies sold | Σ quantity | **29** |
| Transactions | Number of distinct sales | **14** |
| Average sale | Revenue ÷ transactions, rounded to whole paise | 1,114,400 ÷ 14 = **79,600 = ₹796.00** |

With a genre selected, revenue and copies count only that genre's books, and transactions count sales that **included** that genre. Mystery: books 3 (sales 1, 6, 15) and 8 (sales 6, 12) → **₹2,034.00, 6 copies, 4 sales**.

### Revenue by genre

| Genre | Books | Revenue (paise) | Share |
|---|---|---|---|
| Fiction | 1 (224,400) + 5 (179,600) | 404,000 | 36.3% |
| Mystery | 3 (104,700) + 8 (98,700) | 203,400 | 18.3% |
| Children | 7 (89,700) + 9 (82,500) | 172,200 | 15.5% |
| Cookery | 2 (165,000) | 165,000 | 14.8% |
| History | 6 (119,800) | 119,800 | 10.8% |
| Poetry | 4 (50,000) | 50,000 | 4.5% |
| **Total** | | **1,114,400** | 100.2% (rounding) |

The genre chart always shows all genres, even when a genre filter is selected, so genres can be compared. The page says so.

### Best sellers (ranked by copies)

| Rank | Book | Copies | Revenue (paise) |
|---|---|---|---|
| 1 | 1 *The Monsoon Ledger* | 6 | 224,400 |
| 2 | 5 *The Cartographer's Daughter* | 4 | 179,600 |
| 3 | 2, 3, 8, 7, 9 (tied, listed by revenue) | 3 each | 165,000 / 104,700 / 98,700 / 89,700 / 82,500 |
| 8 | 6, 4 (tied) | 2 each | 119,800 / 50,000 |

Rank 8, not 4: with `RANK()`, five books sharing rank 3 use up ranks 3–7.

### Revenue over time (weekly, weeks start Monday)

| Week starting | Sales | Revenue (paise) | Partial? |
|---|---|---|---|
| 28 Sep | 1, 2, 3 | 247,000 | Yes: the period starts on Thursday 1 Oct |
| 5 Oct | 4, 5, 6, 7 | 232,500 | |
| 12 Oct | 8, 10, 11 (9 cancelled) | 324,600 | |
| 19 Oct | 12, 13, 14 | 275,400 | |
| 26 Oct | 15 | 34,900 | Yes: the period ends on 26 Oct |
| **Total** | | **1,114,400** | |

A bucket is **partial** when it starts before the period, ends after it, or includes today (the day isn't over). Partial bars are drawn as outlines, so a short week can't be mistaken for a bad week. Days, weeks or months with no sales show as 0. For example, 1–7 Oct by day: 104,700 / 55,000 / **0** / 87,300 / 34,900 / **0** / 69,900.

**Correction to the design notes:** the Phase 5 design said the week of 26 Oct is partial because "data ends 26 Oct". That is only true when the period ends on 26 Oct. With "All time", the period runs to today, so that week is complete and genuinely shows ₹349.00. The current week is marked partial instead, because it hasn't finished.

### No sales in the period

Books with stock and no completed sales: **12 (6 copies), 11 (4), 10 (3)**. Book 10 appears only in the cancelled sale 9.

This is "no recorded sales", not "slow-selling". Lekha doesn't record when each book arrived, so a recently added book would also appear here.

### Estimated gross profit

Σ copies × (price paid − the book's **current** cost per copy), for books with a known cost.

| Book | Calculation | Profit (paise) |
|---|---|---|
| 1 | 3 × (34,900 − 24,000) + 3 × (39,900 − 24,000) | 80,400 |
| 2 | 3 × (55,000 − 33,000) | 66,000 |
| 3 | 3 × (34,900 − 21,000) | 41,700 |
| 4 | 2 × (25,000 − 15,000) | 20,000 |
| 5 | 4 × (44,900 − 27,000) | 71,600 |
| 6 | 2 × (59,900 − 36,000) | 47,800 |
| 7 | no cost recorded: **left out** | — |
| 8 | 3 × (32,900 − 20,000) | 38,700 |
| 9 | 3 × (27,500 − 16,500) | 33,000 |
| **Total** | | **399,200 = ₹3,992.00** |

Covers 1,024,700 of 1,114,400 paise of revenue (**92.0%**). Estimated margin: 399,200 ÷ 1,024,700 = **39.0%**.

Limits, also shown on screen: today's cost rather than each copy's actual cost; books without a cost are left out, not treated as free; rent, wages and other running costs aren't included. **Revenue is never labelled as profit.**

## Observations

Built only from the figures above, each with evidence and limits:

| Observation | Shown when | Limits stated |
|---|---|---|
| Top genre by revenue | No genre filter, at least two genres sold | Recorded sales can't show that a display would help |
| Best seller (or a tie) | Any sales | Copies, not profit |
| Selling, and low on stock | A low-stock book sold in the period | An alert, not a reorder recommendation |
| On the shelf, no sales | Unsold books with stock | Not the same as slow-selling; arrival dates unknown |
| No completed sales | No sales at all | Nothing can be concluded |

With fewer than **30** sales in the period, each observation adds: "Only N sales in this period, so treat this as a hint, not a pattern." The threshold is a judgement call, not a statistical test. It's a plain-language guard against over-reading a small sample.

## Periods

Relative to today (examples for 8 Nov 2026):

| Choice | Dates |
|---|---|
| Last 7 days | 2 Nov – 8 Nov |
| Last 30 days (default) | 10 Oct – 8 Nov |
| This month | 1 Nov – 8 Nov |
| Last month | 1 Oct – 31 Oct |
| All time | first completed sale (1 Oct) – today |
| Custom | any start and end, both included |

## Known limitations

- 14 sales is far too few for real patterns. The dataset is small so every figure can be checked by hand.
- Number formats inside Streamlit tables and chart axes use Western grouping (₹1,047.00, ₹3,000). Text and figures elsewhere use Indian grouping (₹1,11,444.00). The two agree below one lakh, which covers all the sample data.
- No comparison with a previous period yet.
