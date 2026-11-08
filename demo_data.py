"""Generate a larger, FICTIONAL demo dataset for screenshots and demos.

Everything this creates is invented: titles, authors, ISBNs, prices and
sales. It is NOT the hand-checked sample dataset the tests use
(data/sample_data.sql); it exists so charts have enough data to show
their shape.

    .\\.venv\\Scripts\\python.exe demo_data.py            # writes data/demo.db
    $env:LEKHA_DB_PATH = "data\\demo.db"                 # then run the app on it
    .\\.venv\\Scripts\\python.exe -m streamlit run app.py

How it works
  * A fixed random seed, so every run produces exactly the same data.
  * Fixed dates (3 Aug to 7 Nov 2026), so the data doesn't depend on today.
  * Every book, sale, cancellation and stock correction goes through
    Lekha's own service functions, so the same rules and transactions
    the app uses are exercised hundreds of times while building it.
"""

import random
import sys
from datetime import date, datetime, time, timedelta
from pathlib import Path

from database import DEFAULT_DB_PATH, create_schema, get_connection
from services.books import BookInput, add_book
from services.inventory import correct_stock
from services.money import paise_to_rupees
from services.sales import SaleLine, cancel_sale, record_sale

SEED = 2026
START = date(2026, 8, 3)          # a Monday
END = date(2026, 11, 7)
NOW = datetime.combine(END, time(20, 0))
DEMO_PATH = DEFAULT_DB_PATH.parent / "demo.db"

# (title, author, genre, price in paise, popularity weight)
# The first 12 match the sample dataset; the rest are new and equally invented.
# A weight of 0 means the book never sells, so "no sales" has examples.
BOOKS = [
    ("The Monsoon Ledger", "Asha Varkey", "Fiction", 34900, 9),
    ("Salt and Saffron", "Meera Pillai", "Cookery", 55000, 5),
    ("The Lighthouse at Kovalam", "Rohan Dsouza", "Mystery", 34900, 6),
    ("Letters to a Quiet River", "Nila Sen", "Poetry", 25000, 2),
    ("The Cartographer's Daughter", "Asha Varkey", "Fiction", 44900, 7),
    ("A Short History of Ink", "Farhan Qureshi", "History", 59900, 3),
    ("The Clockmaker's Cat", "Tara Menon", "Children", 29900, 5),
    ("Murder on the Night Mail", "Rohan Dsouza", "Mystery", 32900, 6),
    ("Ten Thousand Mangoes", "Tara Menon", "Children", 27500, 6),
    ("The Silk Road Atlas", "Farhan Qureshi", "History", 79900, 1),
    ("Small Hours", "Nila Sen", "Poetry", 22500, 1),
    ("Harbour Lights", "Kabir Rao", "Fiction", 37500, 4),
    ("The Tamarind Letters", "Anjali Bose", "Fiction", 39900, 6),
    ("A House by the Backwaters", "Rhea Fernandes", "Fiction", 42500, 4),
    ("Monsoon Trains", "Dev Kulkarni", "Fiction", 35000, 3),
    ("The Last Bookbinder", "Lila Thomas", "Fiction", 44900, 5),
    ("The Ferry at Midnight", "Rohan Dsouza", "Mystery", 33900, 5),
    ("Death in the Spice Market", "Sana Iqbal", "Mystery", 36500, 4),
    ("The Silent Courtyard", "Arjun Mehra", "Mystery", 31900, 2),
    ("Ink and Rain", "Nila Sen", "Poetry", 24900, 2),
    ("Notes from a Rooftop", "Lila Thomas", "Poetry", 21900, 0),
    ("Breakfasts of the Coast", "Meera Pillai", "Cookery", 59900, 3),
    ("A Pinch of Cardamom", "Rhea Fernandes", "Cookery", 49900, 3),
    ("One-Pot Evenings", "Dev Kulkarni", "Cookery", 45000, 2),
    ("Ports of the Old World", "Farhan Qureshi", "History", 64900, 2),
    ("The Paper Trail: A History of Letters", "Arjun Mehra", "History", 52500, 0),
    ("The Elephant Who Loved Books", "Tara Menon", "Children", 25900, 6),
    ("Moon over the Mango Tree", "Sana Iqbal", "Children", 23900, 4),
    ("Pip and the Paper Boat", "Anjali Bose", "Children", 19900, 4),
    ("The Very Curious Crab", "Tara Menon", "Children", 21500, 3),
]
PRICE_CHANGE = (1, date(2026, 10, 12), 39900)    # book 1 goes up to Rs 399 from 12 Oct
NO_COST_BOOK = 7                                 # one book without a recorded cost
CANCEL_RATE = 0.03


def plan_sales(rng: random.Random) -> list[tuple[datetime, list[tuple[int, int]]]]:
    """Decide every sale up front: when, and which books in what quantities."""
    weights = [book[4] for book in BOOKS]
    ids = list(range(1, len(BOOKS) + 1))
    sales, day = [], START
    while day <= END:
        weeks_in = (day - START).days / 7
        base = {5: 7, 6: 6}.get(day.weekday(), 3)             # Saturday, Sunday busier
        count = max(0, round(base * (1 + 0.03 * weeks_in) + rng.uniform(-2, 2)))
        for _ in range(count):
            minute = rng.randint(10 * 60, 19 * 60 + 30)
            when = datetime.combine(day, time(minute // 60, minute % 60, rng.randint(0, 59)))
            distinct = rng.choices([1, 2, 3], weights=[70, 24, 6])[0]
            chosen = []
            while len(chosen) < distinct:
                book_id = rng.choices(ids, weights=weights)[0]
                if book_id not in chosen:
                    chosen.append(book_id)
            sales.append((when, [(book_id, rng.choices([1, 2], weights=[88, 12])[0]) for book_id in chosen]))
        day += timedelta(days=1)
    return sorted(sales)


def build(path: Path = DEMO_PATH) -> dict:
    rng = random.Random(SEED)
    sales = plan_sales(rng)

    # Opening stock = everything that will be sold, plus some left over, so
    # every sale can go through and the final shelf shows a realistic mix.
    needed = {book_id: 0 for book_id in range(1, len(BOOKS) + 1)}
    for _, lines in sales:
        for book_id, quantity in lines:
            needed[book_id] += quantity
    leftover = {book_id: rng.choice([0, 1, 2, 3, 4, 5, 6, 8, 10, 12]) for book_id in needed}

    path.parent.mkdir(parents=True, exist_ok=True)
    path.unlink(missing_ok=True)
    conn = get_connection(path)
    try:
        create_schema(conn)
        for book_id, (title, author, genre, price, _) in enumerate(BOOKS, start=1):
            cost = None if book_id == NO_COST_BOOK else paise_to_rupees(price * 3 // 5)
            add_book(conn, BookInput(
                title=title, author=author, genre=genre, isbn=f"{book_id:013d}",
                selling_price=paise_to_rupees(price), cost_price=cost,
                stock_quantity=needed[book_id] + leftover[book_id],
                reorder_level=rng.choice([2, 3, 4]),
            ))

        price_changed = False
        cancelled = 0
        for when, lines in sales:
            book_id, change_day, new_price = PRICE_CHANGE
            if not price_changed and when.date() >= change_day:
                with conn:
                    conn.execute("UPDATE books SET selling_price_paise = ? WHERE book_id = ?", (new_price, book_id))
                price_changed = True
            prices = dict(conn.execute("SELECT book_id, selling_price_paise FROM books"))
            sale_id = record_sale(
                conn, [SaleLine(b, q, prices[b]) for b, q in lines], sale_datetime=when, now=NOW,
            )
            if rng.random() < CANCEL_RATE:
                cancel_sale(conn, sale_id, "Entered by mistake", now=when + timedelta(minutes=12))
                cancelled += 1

        # A few recorded stock corrections, so the history isn't empty.
        for book_id, removed, reason, note in [
            (3, 1, "damaged_or_lost", ""), (16, 2, "damaged_or_lost", ""),
            (27, 1, "other", "Display copy given to the reading group"),
        ]:
            current = conn.execute("SELECT stock_quantity FROM books WHERE book_id = ?", (book_id,)).fetchone()[0]
            if current >= removed:
                correct_stock(conn, book_id, current, current - removed, reason, note,
                              now=datetime.combine(END, time(19, 45)))

        summary = dict(conn.execute(
            """
            SELECT 'completed sales', COUNT(*) FROM sales WHERE status = 'completed'
            UNION ALL SELECT 'cancelled sales', COUNT(*) FROM sales WHERE status = 'cancelled'
            UNION ALL SELECT 'books', COUNT(*) FROM books
            UNION ALL SELECT 'revenue (paise)', SUM(si.quantity * si.unit_price_paise)
                      FROM sale_items si JOIN sales s USING (sale_id) WHERE s.status = 'completed'
            """
        ).fetchall())
    finally:
        conn.close()
    return summary


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else DEMO_PATH
    result = build(target)
    print(f"Built FICTIONAL demo data in {target}:")
    for name, value in result.items():
        print(f"  {name}: {value}")
