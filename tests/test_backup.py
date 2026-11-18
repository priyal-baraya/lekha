"""Tests for backup.py: copying every account and shop file safely."""

import sqlite3
from datetime import datetime

import pytest

import backup
import database
from services import accounts

NOW = datetime(2026, 11, 18, 21, 30, 5)
PASSWORD = "paper lanterns at dusk 42"


@pytest.fixture
def data(tmp_path, monkeypatch):
    """A data folder with one person and two empty shops."""
    folder = tmp_path / "data"
    monkeypatch.setenv("LEKHA_DATA_DIR", str(folder))
    with database.connect_accounts() as conn:
        asha = accounts.create_user(conn, "asha", "Asha", PASSWORD)
        first = accounts.create_shop(conn, asha, "Chapter One")
        second = accounts.create_shop(conn, asha, "Second Chapter")
    for shop_id in (first, second):
        database.ensure_shop_database(shop_id)
    return folder


def rows(path, sql):
    conn = sqlite3.connect(path)
    try:
        return conn.execute(sql).fetchall()
    finally:
        conn.close()


def test_copies_accounts_and_every_shop(data, tmp_path):
    copy = backup.back_up(data, tmp_path / "backups", NOW)

    assert copy == tmp_path / "backups" / "2026-11-18_213005"
    assert rows(copy / "accounts.db", "SELECT username FROM users") == [("asha",)]
    assert sorted(p.name for p in (copy / "shops").iterdir()) == ["shop_1.db", "shop_2.db"]
    assert rows(copy / "shops" / "shop_1.db", "PRAGMA integrity_check") == [("ok",)]


def test_copy_has_only_committed_changes(data, tmp_path):
    """Lekha may be writing while the backup runs; the copy is still whole."""
    writer = sqlite3.connect(data / "accounts.db")
    try:
        writer.execute("BEGIN")
        writer.execute("UPDATE users SET display_name = 'Half-written'")
        copy = backup.back_up(data, tmp_path / "backups", NOW)
    finally:
        writer.rollback()
        writer.close()

    assert rows(copy / "accounts.db", "SELECT display_name FROM users") == [("Asha",)]


def test_ignores_other_files(data, tmp_path):
    (data / "notes.txt").write_text("not Lekha's", encoding="utf-8")
    sqlite3.connect(data / "shops" / "shop_old.db").close()

    copy = backup.back_up(data, tmp_path / "backups", NOW)

    assert sorted(p.name for p in copy.iterdir()) == ["accounts.db", "shops"]
    assert sorted(p.name for p in (copy / "shops").iterdir()) == ["shop_1.db", "shop_2.db"]


def test_nothing_to_back_up_yet(tmp_path):
    empty = tmp_path / "data"

    assert backup.back_up(empty, tmp_path / "backups", NOW) is None
    assert not empty.exists()
    assert not (tmp_path / "backups").exists()


def test_never_overwrites_a_backup(data, tmp_path):
    backup.back_up(data, tmp_path / "backups", NOW)

    with pytest.raises(FileExistsError):
        backup.back_up(data, tmp_path / "backups", NOW)


def test_backup_inside_the_data_folder_is_refused(data):
    with pytest.raises(ValueError):
        backup.back_up(data, data / "backups", NOW)


def test_prune_keeps_the_newest(tmp_path):
    root = tmp_path / "backups"
    names = ["2026-11-15_020000", "2026-11-16_020000", "2026-11-17_020000", "2026-11-18_020000"]
    for name in names:
        (root / name / "shops").mkdir(parents=True)
        (root / name / "accounts.db").write_bytes(b"")
    (root / "keep-me").mkdir()

    removed = backup.prune(root, keep=2)

    assert [p.name for p in removed] == names[:2]
    assert sorted(p.name for p in root.iterdir()) == ["2026-11-17_020000", "2026-11-18_020000", "keep-me"]


def test_prune_needs_at_least_one(tmp_path):
    with pytest.raises(ValueError):
        backup.prune(tmp_path, keep=0)


def test_main_uses_the_data_and_backup_folders(data, tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("LEKHA_BACKUP_DIR", str(tmp_path / "backups"))

    assert backup.main([]) == 0

    made = list((tmp_path / "backups").iterdir())
    assert len(made) == 1
    assert rows(made[0] / "accounts.db", "SELECT username FROM users") == [("asha",)]
    assert str(made[0]) in capsys.readouterr().out


def test_main_needs_a_backup_folder(data, monkeypatch, capsys):
    monkeypatch.delenv("LEKHA_BACKUP_DIR", raising=False)

    assert backup.main([]) == 2
    assert "LEKHA_BACKUP_DIR" in capsys.readouterr().err


def test_main_refuses_keeping_none(data, tmp_path, monkeypatch):
    monkeypatch.setenv("LEKHA_BACKUP_DIR", str(tmp_path / "backups"))

    with pytest.raises(SystemExit):
        backup.main(["--keep", "0"])
    assert not (tmp_path / "backups").exists()
