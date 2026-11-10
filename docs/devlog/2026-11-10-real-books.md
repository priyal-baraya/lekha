# Real books, real data

*2026-11-10 · Phase 8: Real books from Open Library*

## The request

Make everything in Lekha real: search for real books through an API and add them, with no fake values and no fake reviews.

## What "real" can mean

Book *details* can come from an API. A shop's *prices, stock and sales* can't: no API knows them. So "real" became a clear split:

- Title, author, ISBN, publisher, year, cover: **Open Library**, checked by the owner.
- Price, stock, reorder level: **the owner**, never guessed.
- Sales, revenue, insights: **calculated from sales actually recorded**. An empty shop shows real zeros.

The fictional dataset didn't disappear. It moved to where it belongs: inside the tests, which need known numbers to check the maths.

## What I learned

**Check the API before designing around it.** Open Library answered; Google Books refused without a key. Ten minutes of testing chose the API.

**Real data is messy.** Searching *The God of Small Things* returns study guides, translations and one record crediting the wrong author. An ISBN I chose because it looked fake turned out to be a real 1985 book. So Lekha pre-fills and lets a person confirm, rather than trusting the API blindly.

**A work isn't an edition.** A title search finds the book in general; only an ISBN pins down the copy in your hand. Saving a search result's publisher would have put wrong facts in the catalogue, so Lekha doesn't.

**Schema changes need migrations.** Adding columns to a table that already holds data needs an upgrade step. Numbered SQL files, plus SQLite's built-in `user_version` counter, give every database, old or new, the same path.

**Test against real responses, offline.** I recorded Open Library's actual answers once, and the tests replay them. They stay fast, run on GitHub without calling Open Library, and still reflect the real format.

## Next

Add real books to the shop, record real sales, and retake the screenshots when the Insights page has something real to show.
