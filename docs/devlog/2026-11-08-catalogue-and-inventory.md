# Catalogue and inventory

*2026-11-08 · Phase 3: Catalogue and inventory*

## What I built

- **Books page:** search as you type, filter by genre, sort by title, price or stock. Add books with every problem listed at once. Edit details, but not stock.
- **Inventory page:** books at or below their reorder level, a form to correct stock after counting (with a reason), and a history of every correction.
- **Overview:** the low-stock figure and list now come from the database.
- **A service layer** (`services/`): the rules, written once and tested without a browser.

## What I learned

**Keep SQL out of the pages.** Pages decide what to show; services decide what's allowed. That made 74 new tests possible without clicking anything, and means a future redesign won't touch the rules.

**Never paste user input into SQL.** Search text goes in as a `?` placeholder, so typing `'; DROP TABLE books; --` just searches for that odd title. A test proves it. Column names can't be placeholders, so sorting uses a fixed list of allowed options.

**Floats lose money.** `int(19.99 * 100)` is 1998, so a paisa disappears. `Decimal` keeps the digits exactly.

**Stock should never change silently.** Corrections need a reason and leave a history row, saved in the same transaction as the stock update. A test forces the second step to fail and checks that the first is undone.

**Check against what the user saw.** The stock update only applies if the number in the database still matches the number on screen. I proved it in the browser by changing the stock behind the page's back: the save was refused and nothing changed.

**Low stock is an alert, not advice.** "At or below 2 copies" is a fact. Whether to reorder depends on how fast a book sells and how long delivery takes. That's analysis for later.

**Work out expected answers, don't guess them.** Two of my own test expectations were wrong. The tests caught the mistakes, which is exactly their job.

## Next

Phase 4: recording sales, reducing stock in the same transaction, and cancelling sales safely.
