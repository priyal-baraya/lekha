# Making Lekha ready to show

*2026-11-08 · Phase 7: Quality and portfolio*

## What I built

- **Graceful errors:** one safety net around every page. A broken database now shows a plain message instead of a Python traceback.
- **A configurable database path** (`LEKHA_DB_PATH`), so tests and demos never touch real data.
- **Page tests:** 11 tests that run the actual pages without a browser, including selling 2 copies through the Sales page and checking stock falls by exactly 2.
- **Tests on GitHub:** every push and pull request runs all 192 tests on a fresh Linux machine.
- **A demo dataset:** 30 invented books and about 14 weeks of invented sales, generated through Lekha's own code.
- **Screenshots, a setup guide, a new README and a case study.**

## What I learned

**Know how your framework signals things.** Before catching every error, I checked how `st.rerun()` works: it raises a special signal that is deliberately *not* a normal Python `Exception`. If it were, my error handler would have silently broken every form.

**Configuration belongs outside the code.** One environment variable lets the same app run on real data, test data or demo data.

**Tests can be wrong too.** One page test failed because I pressed "run" between typing and submitting a form, something no person does. The app was fine; the test needed fixing.

**Tools need to wait for the page.** A quick screenshot only captured Streamlit's grey loading skeleton. Playwright could wait until the page had actually finished drawing.

**Generate demo data through the real code.** Building the demo dataset with `record_sale` and `cancel_sale` meant hundreds of sales went through the same transactions and checks as the app, a bonus test.

**Separate what you check from what you show.** The small dataset is for proving the numbers right; the larger one is for showing the app at a realistic size. Mixing them would make both less trustworthy.

## Where the project stands

Seven phases, 192 tests, a contrast audit at zero failures, and documentation that explains every decision. Next could be a Figma-led redesign, deliveries with real costs, or an online demo.
