"""Tests for config.py: settings that change on Vercel."""
import importlib

import config


def reload_config(monkeypatch, **env):
    for name in ["VERCEL", "BACKUP_PATH", "APP_TIMEZONE", "SHEET_ID"]:
        monkeypatch.delenv(name, raising=False)
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    return importlib.reload(config)


def teardown_function():
    importlib.reload(config)  # put the normal settings back for other tests


def test_local_backup_is_the_shipped_copy(monkeypatch):
    c = reload_config(monkeypatch)
    assert c.ON_VERCEL is False
    assert c.BACKUP_PATH == c.SEED_BACKUP_PATH
    assert c.SEED_BACKUP_PATH.endswith("data/backup.csv")


def test_vercel_backup_goes_to_tmp(monkeypatch):
    c = reload_config(monkeypatch, VERCEL="1")
    assert c.ON_VERCEL is True
    assert c.BACKUP_PATH.startswith("/tmp/")


def test_local_now_is_toronto_by_default(monkeypatch):
    now = reload_config(monkeypatch).local_now()
    assert now.tzinfo is not None
    assert str(now.tzinfo) == "America/Toronto"


def test_timezone_can_be_changed(monkeypatch):
    assert str(reload_config(monkeypatch, APP_TIMEZONE="America/Vancouver").local_now().tzinfo) == "America/Vancouver"


def test_blank_settings_use_defaults(monkeypatch):
    c = reload_config(monkeypatch, APP_TIMEZONE="  ", SHEET_ID="")
    assert c.APP_TIMEZONE == "America/Toronto"
    assert c.SHEET_ID.startswith("1LQml")


def test_unknown_timezone_falls_back_instead_of_crashing(monkeypatch):
    c = reload_config(monkeypatch, APP_TIMEZONE="Toronto")
    assert c.APP_TIMEZONE == "America/Toronto"
    assert c.local_now().tzinfo is not None
