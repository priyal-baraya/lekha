# Design system

Lekha should feel like an antique illustrated manuscript translated into a contemporary, accessible product. The identity comes from typography, the crimson-and-teal palette, parchment surfaces and a few fine ornaments. Usability comes from clear hierarchy, rectangular composition and honest data.

**Where things live**

| What | File |
|---|---|
| Theme (colours, fonts, radius, borders, chart colours) | `.streamlit/config.toml` |
| Custom styles Streamlit has no setting for | `ui/styles.css` |
| Functions that output the styled page pieces | `ui/components.py` |
| Ornament drawings | `ui/assets/*.svg` |

## Colour

### Brand

| Token | Hex | Use |
|---|---|---|
| Manuscript Crimson | `#791A24` | Primary brand colour, primary actions, selected states, section labels |
| Deep Wine | `#4A111B` | Hero panel and occasional dark brand panels |
| Persian Teal | `#263F3C` | Secondary colour, supporting actions, second chart series |

### Surfaces

| Token | Hex | Use |
|---|---|---|
| Manuscript Paper | `#F5EBDD` | Main app background |
| Porcelain Paper | `#FBF7F0` | Content surfaces: panels, inputs, tables, charts |
| Aged Parchment | `#E3D1B2` | Table headers, light inner dividers |

### Text

| Token | Hex | Use |
|---|---|---|
| Sepia Ink | `#352821` | Primary text and headings |
| Secondary Text | `#67554A` | Descriptions, labels, metadata |

### Decorative accents (never for essential text on light backgrounds)

| Token | Hex | Use |
|---|---|---|
| Antique Gold | `#B28A5C` | Ornament lines, hero frame, dividers. Allowed as small text on Deep Wine only |
| Terracotta | `#A6543C` | Chart series, selected accents |
| Botanical Olive | `#62633D` | Chart series, leaves in ornaments |
| Faded Rose | `#C98F86` | Petals in ornaments only |

### Functional addition

| Token | Hex | Use | Why it exists |
|---|---|---|---|
| Border Taupe | `#8C7A68` | Outlines of inputs, panels and the metric strip | Input outlines must reach 3:1 against the background (WCAG 1.4.11). No palette colour meets that without looking heavy. See the decision log. |

### Semantic states

Always paired with words or icons, never colour alone.

| State | Text | Background | Streamlit element |
|---|---|---|---|
| Success | `#215C42` | `#E5F1E8` | `st.success` |
| Warning | `#704A0E` | `#F8EBCB` | `st.warning` |
| Critical / error | `#8B1E2D` | `#F8E5E5` | `st.error` |
| Information | `#254D67` | `#E6EFF5` | `st.info`, the `.lekha-tag` status tags |

### Charts

- **Categories** (in order): `#791A24`, `#263F3C`, `#A6543C`, `#62633D`, `#4A111B`
- **Sequential** ("more" vs "less"), light to dark crimson: `#F3E4DC` → `#4A111B` in ten steps (listed in `config.toml`)

### Measured contrast (WCAG 2.2 AA: 4.5:1 normal text, 3:1 large text and UI parts)

| Pair | Ratio | Verdict |
|---|---|---|
| Sepia Ink on Manuscript Paper | 12.06 | Pass |
| Secondary Text on Manuscript Paper | 5.99 | Pass |
| Secondary Text on Aged Parchment | 4.72 | Pass |
| Crimson on Manuscript Paper | 8.97 | Pass |
| Teal on Manuscript Paper | 9.58 | Pass |
| Terracotta on Manuscript Paper | 4.50 | Borderline: charts and large text only |
| Olive on Manuscript Paper | 5.28 | Pass |
| Gold on Manuscript Paper | 2.66 | **Fail**: decorative only |
| Faded Rose on Manuscript Paper | 2.30 | **Fail**: decorative only |
| Porcelain on Deep Wine | 14.18 | Pass |
| Aged Parchment on Deep Wine | 10.11 | Pass |
| Gold on Deep Wine | 4.82 | Pass (hero label) |
| Border Taupe on Manuscript Paper | 3.49 | Pass for UI outlines |
| All four semantic pairs | 6.63–7.72 | Pass |

## Typography

Both fonts load from Google Fonts through `config.toml` and fall back to system fonts if they cannot load.

| Font | Weights loaded | Used for |
|---|---|---|
| **Lora** (serif) | 500, 600 | Wordmark, hero tagline, page and section titles, metric values |
| **Lato** (sans-serif) | 400, 700 | Navigation, body text, buttons, labels, tables, charts, status text |

| Style | Size | Line height | Font |
|---|---|---|---|
| Display (hero wordmark) | 48px (40px on phones) | 1.15 | Lora 600 |
| Page title | 32px | 1.25 | Lora 600 |
| Section title | 28px | 1.25 | Lora 600 |
| Hero tagline | 24px | 1.3 | Lora 500 |
| Metric value | 32px | 1.2 | Lora 500 |
| Body | 16px | 1.5 (24px) | Lato 400 |
| Labels, notes, tags | 13–14px | 1.4 | Lato 400/700 |
| Section label ("eyebrow") | 13px, uppercase, 0.12em spacing | — | Lato 700 |

Streamlit headings written with `st.header` and similar use the `headingFontSizes` in `config.toml`: 44, 30, 22, 18, 16 and 14px for h1–h6.

Long text is capped at about 42rem (roughly 70 characters per line).

## Shape and layout

- **Corners:** square everywhere. `baseRadius = "none"` and `buttonRadius = "none"` in `config.toml`. A scan of every visible element on the Overview page found no rounded corners.
- **Borders:** thin 1px lines. Border Taupe for outer edges, Aged Parchment for inner dividers, Antique Gold for ornamental rules.
- **Composition:** full-width bands stacked vertically and separated by the ornamental divider, not a grid of floating cards.
- **Responsive:** the metric strip goes from 4 columns to 2 (below 900px) to 1 (below 640px). Below 640px the hero hides its decorative strip so the text gets the full width.
- **Focus:** links and buttons show a 2px crimson outline when reached by keyboard.

## Ornaments

Original SVG drawings inspired by the reference artwork, kept deliberately simple.

| Ornament | File | Where it appears |
|---|---|---|
| Rosette divider | `ui/assets/divider-rosette.svg` | Centre of the divider between major sections, between two double gold rules |
| Botanical arch | `ui/assets/arch-botanical.svg` | Hero (140px) on a jaali-style lattice; empty states (44px) |

Rules:
- Ornaments are CSS background images on empty `<span>` elements, so screen readers skip them and they never interrupt reading order or keyboard navigation.
- Never behind charts, tables or essential text.
- Used at section transitions, the brand introduction and empty states only.

The jaali lattice in the hero is two repeating CSS gradients at 22% gold opacity. No image file is involved.

## Components (`ui/components.py`)

| Function | What it draws |
|---|---|
| `load_styles()` | Adds `styles.css` and the ornament images to the page. Called once in `app.py` |
| `hero(...)` | Deep Wine brand panel with gold frame, wordmark, tagline and arch |
| `divider()` | Ornamental section divider |
| `section_header(...)` | Section label, Lora title, optional status tag and description |
| `metric_placeholders(...)` | Connected row of metric slots showing "—" and "Not connected yet" |
| `empty_state(...)` | Porcelain panel with small arch, message and status tag |
| `planned_page(...)` | Full layout for a page that is not built yet |
