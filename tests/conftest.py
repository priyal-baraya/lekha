"""Shared test set-up.

A pytest "fixture" is a function that prepares something a test needs.
A test asks for it by naming it as a parameter, for example
`def test_something(empty_db):`.

Every test gets its own fresh in-memory database, so tests never touch
data/lekha.db and cannot affect each other.
"""

import functools
import os

import pytest

import database
from database import create_schema, get_connection, load_sample_data

# LEKHA_TEST_THROUGH_TURSO=1 runs every test through turso.py, the hosted
# Lekha's connection to Turso, against a stand-in Turso server on local
# files (tests/fake_turso.py). GitHub runs the suite both ways.
THROUGH_TURSO = os.environ.get("LEKHA_TEST_THROUGH_TURSO") == "1"


@pytest.fixture(autouse=True)
def through_turso(monkeypatch):
    if not THROUGH_TURSO:
        yield
        return
    import turso
    from tests.fake_turso import FakeTurso

    real = database._turso_connection
    servers = []

    @functools.wraps(real)
    def stand_in(target):
        remote = real(target)          # still Turso proper when a test sets LEKHA_TURSO_URL
        if remote is not None:
            return remote
        servers.append(FakeTurso(str(target)))
        return turso.Connection(servers[-1])

    monkeypatch.setattr(database, "_turso_connection", stand_in)
    yield
    for server in servers:
        server.close_all()


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


@pytest.fixture(autouse=True)
def no_local_secrets_or_google(monkeypatch):
    """Tests never read the real .streamlit/secrets.toml (which may hold a
    Google Books key) and never reach Google: a test that needs either
    sets it up itself."""
    import streamlit as st
    from streamlit.runtime.secrets import Secrets

    from services import googlebooks

    empty = Secrets()
    empty._secrets = {}
    monkeypatch.setattr(st, "secrets", empty)

    def no_internet(request, timeout):
        raise AssertionError("A test tried to reach the internet")

    # urlopen, not fetch_json, so googlebooks' own checks are still tested.
    monkeypatch.setattr(googlebooks.urllib.request, "urlopen", no_internet)
