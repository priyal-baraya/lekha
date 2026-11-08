# Turning sales into insights

*2026-11-08 · Phase 5: Analytics*

## What I built

- **Insights page:** revenue, copies, transactions and average sale; revenue over time; revenue by genre; best sellers; books with no sales; estimated gross profit; and plain-language observations. All filtered by period and genre.
- **Overview:** the last 30 days' figures and a weekly chart, from the same code.
- **`sql/analytics/`:** one readable file per query, all starting from one shared definition of "a completed sale in the period".

## What I learned

**Define, calculate by hand, then code.** I worked out every number on paper first: ₹11,144.00 revenue, Fiction at 36.3%, a ₹3,992.00 profit estimate. The tests use those numbers. When the code was finished, the page showed exactly those figures.

**One definition, used everywhere.** All queries start from the same `period_lines` CTE, so it's impossible for one chart to include cancelled sales while another excludes them.

**Window functions solve ties.** `RANK()` gives five books with 3 copies each the same rank, then skips to 8. Numbering them 3 to 7 would invent differences that aren't in the data.

**Dates need half-open ranges.** "From midnight on the first day, until midnight after the last day" leaves no gap at 23:59:59.

**Charts can mislead without lying.** A week that's only half inside the period looks like a bad week. Lekha draws partial periods as outlines and says so in words, and shows empty weeks as zero instead of skipping them.

**Profit is an estimate, and must say so.** Lekha only knows each book's current cost, and one book has none. So the page shows how much revenue the estimate covers, and never calls revenue "profit".

**Small samples deserve honesty.** With 14 sales, every observation says it's a hint, not a pattern.

**I was wrong twice, and the process caught it.** I assumed tied books are listed alphabetically (they're listed by revenue), and my design notes called a week partial when it wasn't. The tests and the hand calculations caught both.

## Next

Phase 6: visual refinement and accessibility, including bringing in the Figma redesign when it's ready.
