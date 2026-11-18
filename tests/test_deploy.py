"""Checks on the hosting files in deploy/ (docs/hosting.md)."""

import re
import tomllib
from pathlib import Path

PROJECT = Path(__file__).parent.parent
DEPLOY = PROJECT / "deploy"


def settings(name):
    """A systemd file's settings, as {key: [values]} (keys can repeat)."""
    found = {}
    for line in (DEPLOY / name).read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.startswith(("#", "[")):
            key, value = line.split("=", 1)
            found.setdefault(key.strip(), []).append(value.strip())
    return found


def test_app_and_backup_use_the_same_data_folder():
    app = settings("lekha.service")["Environment"]
    backup = settings("lekha-backup.service")["Environment"]

    assert "LEKHA_DATA_DIR=/var/lib/lekha/data" in app
    assert "LEKHA_DATA_DIR=/var/lib/lekha/data" in backup
    assert "LEKHA_BACKUP_DIR=/var/lib/lekha/backups" in backup


def test_streamlit_stays_on_localhost_behind_caddy():
    """Only Caddy faces the internet: Streamlit keeps config.toml's
    localhost-only address, and Caddy passes requests to its port."""
    command = settings("lekha.service")["ExecStart"][0]
    port = re.search(r"--server\.port (\d+)", command).group(1)
    config = tomllib.loads((PROJECT / ".streamlit" / "config.toml").read_text(encoding="utf-8"))

    assert "--server.address" not in command
    assert config["server"]["address"] == "localhost"
    assert f"reverse_proxy localhost:{port}" in (DEPLOY / "Caddyfile").read_text(encoding="utf-8")


def test_lekha_runs_as_its_own_locked_down_user():
    for name in ("lekha.service", "lekha-backup.service"):
        service = settings(name)
        assert service["User"] == ["lekha"], name
        assert service["ProtectSystem"] == ["strict"], name
        assert service["NoNewPrivileges"] == ["yes"], name
        assert service["UMask"] == ["0077"], name


def test_backups_run_nightly_and_catch_up():
    timer = settings("lekha-backup.timer")

    assert timer["OnCalendar"] == ["*-*-* 02:30:00 Asia/Kolkata"]
    assert timer["Persistent"] == ["true"]
