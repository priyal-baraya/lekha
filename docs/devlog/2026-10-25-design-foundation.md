# Giving Lekha a visual identity

*2026-10-25 · Design foundation, branch `design/manuscript-theme`*

## The brief

The reference was an antique Indian floral manuscript: crimson arches, teal and olive panels, aged parchment, gold borders, peonies on slender stems. The aim was not to copy it, but to translate its feel into a contemporary product. Its colour, type and a few fine ornaments would carry the identity, while the layout stays clear and practical.

## What changed

- **Theme** (`.streamlit/config.toml`): crimson primary colour, Manuscript Paper background, Porcelain surfaces, Sepia Ink text, Lato for body and Lora for headings, square corners, taupe borders, the four status colours and the chart palettes.
- **Layout**: a Deep Wine hero panel with a fine gold frame, then full-width sections separated by an ornamental divider: The daily read (summary), Sales and trends, The bookshelf and Shelf check.
- **Ornaments**: two original SVG drawings, a rosette for the divider and a botanical arch for the hero and empty states, plus a jaali-style lattice made with CSS.
- **Navigation**: Overview, Books, Sales, Inventory, Insights across the top. Unbuilt pages say "Not built yet" and name their phase.
- **Honesty**: the metric strip shows "—" and "Not connected yet". No invented numbers.

## Things I learned

**Check the framework before writing settings.** `streamlit config show` prints every option the installed version supports, with descriptions. That turned out more reliable than guessing from older tutorials.

**Contrast must be measured, not eyeballed.** Antique Gold looks rich on parchment, but it measures 2.66:1, too faint for text. On Deep Wine the same gold measures 4.82:1, which is fine. The same colour can pass or fail depending on what's behind it.

**Frameworks clean the HTML you give them.** `st.html` removed my SVG drawings for safety. Moving them into the stylesheet as background images fixed it, and turned out to be better for accessibility: screen readers skip CSS backgrounds automatically.

**Frameworks can quietly hide focus.** Streamlit's navigation links showed no outline when reached with the Tab key. One small CSS rule fixed it, but I only found it because I tested with the keyboard.

## Open questions

- Should the tagline stay "Reading between the numbers." or change to the wording in the design brief?
- How will the palette look on real charts in Phase 5? The categorical colours are set but not yet seen on data.
