# Measuring before polishing

*2026-11-08 · Phase 6: Visual refinement*

## What I did

Instead of tweaking the design by eye, I measured it first. A small script checked the contrast of every piece of text on every page against its actual background, listed the headings, and flagged tiny text. Then I looked at each page on a desktop screen and a phone screen.

## What the measurements found

- **Chart text was too faint:** 3.15:1, against a target of 4.5:1. Streamlit's chart theme draws axis labels in a faded ink.
- **Placeholder hints were too faint:** 3.89:1.
- **The sales basket fell apart on phones:** Streamlit stacks columns on narrow screens, so "Copies", "Unit price" and their numbers ended up on separate lines.
- **Tables hid what mattered:** on a phone, the low-stock table's Status column was off-screen.
- **Spacing was inconsistent:** each page opened differently, and one notice sat right against a heading.

## What changed

- Chart axes and placeholders now use Secondary Text: **37 contrast failures down to 0** across all five pages.
- A **spacing scale** (4, 8, 16, 24, 40, 64px) replaced one-off values.
- Every page except Overview opens the same way: label, title, description, sample-data notice, then a section gap.
- The basket shows each line as a sentence: *"1 copy × ₹399.00 = ₹399.00"*.
- Tables put the decision columns straight after the title.

## What I learned

**Measure, then fix.** Two of the five problems (chart text and placeholders) weren't obvious by eye, but the numbers made them undeniable.

**Frameworks have opinions.** Streamlit's faded defaults look elegant, but some of them fail accessibility checks. Setting the colour on each chart axis overrides the theme cleanly.

**Design for the narrowest screen.** A grid that looks tidy at 1280px can be meaningless at 375px. A sentence works at any width.

**Tokens make design consistent.** With named spacing values, every gap is a deliberate choice, and the same values carry straight into Figma.

## Next

Phase 7: quality and portfolio. Page tests, error handling, a setup guide, screenshots and the case study.
