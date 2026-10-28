"""Checks the sample data against numbers worked out by hand.

The expected values come from docs/sample-data.md, where each one is
calculated step by step. If a query and the hand calculation disagree,
one of them is wrong, and the test says so before the number ever
reaches the dashboard.
"""


def scalar(db, sql):
    """Run a query that returns a single value and return that value."""
    return db.execute(sql).fetchone()[0]


def test_row_counts(sample_db):
    assert scalar(sample_db, "SELECT COUNT(*) FROM books") == 12
    assert scalar(sample_db, "SELECT COUNT(*) FROM sales") == 15
    assert scalar(sample_db, "SELECT COUNT(*) FROM sale_items") == 23


def test_completed_and_cancelled_transactions(sample_db):
    assert scalar(sample_db, "SELECT COUNT(*) FROM sales WHERE status = 'completed'") == 14
    assert scalar(sample_db, "SELECT COUNT(*) FROM sales WHERE status = 'cancelled'") == 1


def test_revenue_from_completed_sales(sample_db):
    revenue = scalar(
        sample_db,
        """
        SELECT SUM(si.quantity * si.unit_price_paise)
        FROM sale_items AS si
        JOIN sales AS s ON s.sale_id = si.sale_id
        WHERE s.status = 'completed'
        """,
    )
    assert revenue == 1_114_400  # Rs 11,144.00


def test_copies_sold_in_completed_sales(sample_db):
    copies = scalar(
        sample_db,
        """
        SELECT SUM(si.quantity)
        FROM sale_items AS si
        JOIN sales AS s ON s.sale_id = si.sale_id
        WHERE s.status = 'completed'
        """,
    )
    assert copies == 29


def test_single_sale_total(sample_db):
    # Sale 8: 1 x 39900 + 2 x 44900
    total = scalar(
        sample_db,
        "SELECT SUM(quantity * unit_price_paise) FROM sale_items WHERE sale_id = 8",
    )
    assert total == 129_700


def test_copies_sold_per_book(sample_db):
    rows = sample_db.execute(
        """
        SELECT si.book_id, SUM(si.quantity) AS copies
        FROM sale_items AS si
        JOIN sales AS s ON s.sale_id = si.sale_id
        WHERE s.status = 'completed'
        GROUP BY si.book_id
        """
    ).fetchall()
    copies = {row["book_id"]: row["copies"] for row in rows}
    assert copies == {1: 6, 2: 3, 3: 3, 4: 2, 5: 4, 6: 2, 7: 3, 8: 3, 9: 3}


def test_low_stock_books(sample_db):
    rows = sample_db.execute(
        "SELECT book_id FROM books WHERE stock_quantity <= reorder_level ORDER BY book_id"
    ).fetchall()
    assert [row["book_id"] for row in rows] == [2, 5, 9]


def test_books_with_no_completed_sales(sample_db):
    rows = sample_db.execute(
        """
        SELECT b.book_id
        FROM books AS b
        LEFT JOIN sale_items AS si ON si.book_id = b.book_id
        LEFT JOIN sales AS s ON s.sale_id = si.sale_id AND s.status = 'completed'
        GROUP BY b.book_id
        HAVING COUNT(s.sale_id) = 0
        ORDER BY b.book_id
        """
    ).fetchall()
    assert [row["book_id"] for row in rows] == [10, 11, 12]


def test_price_at_time_of_sale_is_kept(sample_db):
    # Book 1 now costs 39900 but sold for 34900 before 2026-10-12.
    assert scalar(sample_db, "SELECT selling_price_paise FROM books WHERE book_id = 1") == 39900
    old_prices = scalar(
        sample_db,
        """
        SELECT COUNT(*) FROM sale_items AS si
        JOIN sales AS s ON s.sale_id = si.sale_id
        WHERE si.book_id = 1 AND si.unit_price_paise = 34900
          AND s.sale_datetime < '2026-10-12 00:00:00'
        """,
    )
    assert old_prices == 2  # sales 1 and 4


def test_every_sale_has_at_least_one_item(sample_db):
    # The schema cannot enforce this rule; Phase 4's sale recording will.
    # This test checks the sample data obeys it.
    empty_sales = scalar(
        sample_db,
        """
        SELECT COUNT(*) FROM sales AS s
        WHERE NOT EXISTS (SELECT 1 FROM sale_items AS si WHERE si.sale_id = s.sale_id)
        """,
    )
    assert empty_sales == 0
