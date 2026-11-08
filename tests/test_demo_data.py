"""The demo dataset is generated, so check it is repeatable and consistent."""

import demo_data
from database import get_connection


def build_and_read(path):
    summary = demo_data.build(path)
    conn = get_connection(path)
    try:
        negative_stock = conn.execute("SELECT COUNT(*) FROM books WHERE stock_quantity < 0").fetchone()[0]
        mismatched = conn.execute(
            """
            SELECT COUNT(*) FROM sales AS s
            LEFT JOIN sale_cancellations AS c ON c.sale_id = s.sale_id
            WHERE (s.status = 'cancelled') <> (c.sale_id IS NOT NULL)
            """
        ).fetchone()[0]
        unsold = conn.execute(
            "SELECT COUNT(*) FROM books b WHERE NOT EXISTS (SELECT 1 FROM sale_items si WHERE si.book_id = b.book_id)"
        ).fetchone()[0]
    finally:
        conn.close()
    return summary, negative_stock, mismatched, unsold


def test_demo_data_is_the_same_every_time(tmp_path):
    first, *_ = build_and_read(tmp_path / "a.db")
    second, *_ = build_and_read(tmp_path / "b.db")
    assert first == second


def test_demo_data_is_consistent(tmp_path):
    summary, negative_stock, mismatched, unsold = build_and_read(tmp_path / "demo.db")
    assert summary["books"] == 30
    assert summary["completed sales"] > 300
    assert summary["cancelled sales"] > 0
    assert negative_stock == 0
    assert mismatched == 0       # every cancelled sale has its record, and only those
    assert unsold == 2           # the two books with popularity 0
