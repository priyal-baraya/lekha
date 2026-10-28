# Sample data

**Everything in this dataset is fictional.** Titles, authors, ISBNs, prices and sales were invented for testing and demonstration. Nothing describes a real bookstore. ISBNs start with `000`, which no real 13-digit ISBN does.

Source: [`data/sample_data.sql`](../data/sample_data.sql). Build it with:

```powershell
.\.venv\Scripts\python.exe database.py --reset-sample
```

## Size

12 books · 15 sales (14 completed, 1 cancelled) · 23 sale lines · 1 to 26 October 2026

Small on purpose: every number below can be checked with a pencil.

## Situations it contains

| Situation | Where | Why it's there |
|---|---|---|
| Price change | Book 1: sold at ₹349.00 in sales 1 and 4, then at ₹399.00 from sale 8 (12 Oct) | Proves past revenue uses the price at the time of sale |
| Cancelled sale | Sale 9 (book 10) | Must be excluded from revenue and copies sold |
| Multi-book sales | Sales 1, 3, 5, 6, 8, 10, 13, 14 | One transaction, several lines |
| Several copies of one book | Sale 1 (2 × book 1), sale 11 (2 × book 2) and others | Copies sold ≠ transactions |
| Out of stock | Book 5: 0 copies, reorder level 2 | Low-stock alert |
| At reorder level exactly | Book 2: 2 copies, reorder level 2 | Tests the `<=` boundary |
| Below reorder level | Book 9: 1 copy, reorder level 3 | Low-stock alert |
| Never sold | Books 11 and 12 | "No recorded sales" |
| Only sold in a cancelled sale | Book 10 | Must also count as "no completed sales" |
| Unknown cost price | Book 7 | Profit must skip it, not treat it as zero |
| Same author, several books | Asha Varkey (1, 5), Rohan Dsouza (3, 8) and others | Author-level analysis later |

## Hand-calculated results

These are checked automatically by [`tests/test_sample_data.py`](../tests/test_sample_data.py).

### Revenue per completed sale (paise)

| Sale | Lines | Total |
|---|---|---|
| 1 | 2 × 34900 + 1 × 34900 | 104,700 |
| 2 | 1 × 55000 | 55,000 |
| 3 | 2 × 29900 + 1 × 27500 | 87,300 |
| 4 | 1 × 34900 | 34,900 |
| 5 | 1 × 25000 + 1 × 44900 | 69,900 |
| 6 | 1 × 32900 + 1 × 34900 | 67,800 |
| 7 | 1 × 59900 | 59,900 |
| 8 | 1 × 39900 + 2 × 44900 | 129,700 |
| 9 | *cancelled, excluded* | — |
| 10 | 2 × 27500 + 1 × 29900 | 84,900 |
| 11 | 2 × 55000 | 110,000 |
| 12 | 2 × 32900 | 65,800 |
| 13 | 2 × 39900 + 1 × 25000 | 104,800 |
| 14 | 1 × 44900 + 1 × 59900 | 104,800 |
| 15 | 1 × 34900 | 34,900 |
| **Total** | | **1,114,400 paise = ₹11,144.00** |

### Headline figures (completed sales only)

| Figure | Value |
|---|---|
| Revenue | ₹11,144.00 |
| Transactions | 14 |
| Copies sold | 29 |

### Copies sold per book

| Book | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Copies | 6 | 3 | 3 | 2 | 4 | 2 | 3 | 3 | 3 | 0 | 0 | 0 |

Total 29, which matches the headline figure.

### Stock

- At or below reorder level: books **2, 5, 9**
- No completed sales: books **10, 11, 12**

These are facts about an invented dataset, used to check that the queries are correct. They are not business findings.

## Known limitation

`stock_quantity` is a snapshot of "today". There are no restocking records, so stock can't be recalculated from sales history. A later phase may add stock movements if the inventory workflow needs them.
