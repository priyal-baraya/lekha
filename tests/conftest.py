"""Shared test set-up.

A pytest "fixture" is a function that prepares something a test needs.
A test asks for it by naming it as a parameter, for example
`def test_something(empty_db):`.

Every test gets its own fresh in-memory database, so tests never touch
data/lekha.db and cannot affect each other.
"""

import pytest

from database import create_schema, get_connection, load_sample_data


@pytest.fixture
def empty_db():
    """A brand-new database with the tables created but no rows."""
    connection = get_connection(":memory:")
    create_schema(connection)
    yield connection
    connection.close()


@pytest.fixture
def sample_db(empty_db):
    """The empty database plus the fictional sample data."""
    load_sample_data(empty_db)
    return empty_db
