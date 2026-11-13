# Redesign plan

How Lekha moves from the manuscript-panel look to a calm, analytics-first dashboard. Design is settled on a canvas first, then built in Streamlit one piece at a time, with checks at every step.

## Where the design lives

- **Lekha Design System** (Claude Design): palette, type, spacing, components and their rules. [Open it](https://claude.ai/artifact/2Pt2zJdEYY247eivGFWkSu). Approved version: 12 Nov 2026 (`1794491686-7b1e`); `1794494145-873d` only corrects the sample date to Thursday.
- **Lekha redesign** canvas (Claude Design): 23 artboards covering every page, first-run and empty states, the till's edge cases, phone versions and how things respond. [Open it](https://claude.ai/artifact/Gmpsom9RijvZxzbmmZnVXP). Approved version: 12 Nov 2026 (`1794492702-7a02`); `1794494141-794d` only corrects the weekday to Thursday.

Both are private to the owner. A change to either after sign-off is a new change, agreed before it's built.

## Phases

| Phase | What | Status |
|---|---|---|
| 1. Design fixes on the canvas | First-run screens; a faster till (search, quantity buttons, Undo); Overview about today and Insights about trends; readable charts; rules for real data; phone versions; how things respond | Done, 12 Nov 2026 |
| 2. Design review checkpoint | Critique re-run (25/40 → 33/40, no P1 issues), five smaller fixes, design system updated, owner sign-off | Done, 12 Nov 2026 |
| 3. Foundations in code | Theme; shared components; the account menu in the navigation; fair comparisons and summary sentences, written test-first | Done |
| 4. Pages, one at a time | Sign in and Get started → Overview → Sales (the till) → Books → Inventory → Insights → Team and Settings | In progress: Sign in, Get started and Overview done; Sales (PR #19); Books |
| 5. Polish, check and ship | Accessibility pass, automatic design scan, final critique, screenshots and docs | |

## The loop for every change (phases 3 and 4)

1. **Design:** the canvas artboard for this piece is final.
2. **Build** on its own branch, reusing the shared components.
3. **Check:** all tests pass (new ones for anything that calculates); the browser matches the canvas at desktop width; worst-case data (long names, lakh-sized figures, an empty shop, one sale, 137 low-stock books); phone width; keyboard only.
4. **Show** the owner screenshots, and anything Streamlit couldn't match exactly, with the reason.
5. **Record** choices made along the way in the decision log.
6. **Pull request:** tests and security checks pass on GitHub, then the owner merges.

## Who decides

| Who | Decides |
|---|---|
| The owner | The look (canvas sign-off), anything Streamlit can't match, merges |
| The checks | Whether a step moves on: tests, contrast, worst-case data, critique score |
| Claude | How it's built, within the design system's rules, reporting every compromise |
