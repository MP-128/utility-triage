"""Tests for data_source.py. No network: the Google download is replaced with a fake."""
import csv
import urllib.error
from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

import data_source
from data_source import load_assets, parse_assets

HEADER = (
    "asset_id,asset_type,network,location,last_inspection_date,"
    "next_maintenance_date,cv_health_score,condition_notes\n"
)
GOOD_ROW = 'POL-1042,Pole,Distribution,"Maple Ave & 3rd St, Riverside",2026-03-28,2026-09-22,52,Crossarm cracked\n'


class FakeResponse:
    """Stands in for the object urllib.request.urlopen returns."""

    def __init__(self, text, content_type="text/csv; charset=utf-8"):
        self.text = text
        self.headers = {"Content-Type": content_type}

    def read(self, amt=None):
        data = self.text.encode("utf-8")
        return data if amt is None else data[:amt]

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def fake_google(monkeypatch, tmp_path, response=None, error=None):
    """Make the 'download' return `response` (or raise `error`), and keep both backups in a temp folder."""
    backup = tmp_path / "backup.csv"
    monkeypatch.setattr(data_source, "BACKUP_PATH", str(backup))
    monkeypatch.setattr(data_source, "SEED_BACKUP_PATH", str(tmp_path / "seed.csv"))

    def fake_urlopen(request, timeout):
        assert timeout == 10
        if error:
            raise error
        return response

    monkeypatch.setattr(data_source.urllib.request, "urlopen", fake_urlopen)
    return backup


# --- parse_assets ---------------------------------------------------------


def test_good_row_is_parsed_with_real_types():
    assets, warnings = parse_assets(HEADER + GOOD_ROW)
    assert warnings == []
    assert assets == [
        {
            "asset_id": "POL-1042",
            "asset_type": "Pole",
            "network": "Distribution",
            "location": "Maple Ave & 3rd St, Riverside",
            "last_inspection_date": date(2026, 3, 28),
            "next_maintenance_date": date(2026, 9, 22),
            "cv_health_score": 52,
            "condition_notes": "Crossarm cracked",
        }
    ]


def test_missing_field_is_skipped_with_warning():
    row = "TRF-2207,Transformer,Transmission,,2026-05-07,2026-09-29,34,Oil leak\n"
    assets, warnings = parse_assets(HEADER + GOOD_ROW + row)
    assert [a["asset_id"] for a in assets] == ["POL-1042"]
    assert warnings == ["Row 3 (TRF-2207) skipped: missing location"]


def test_bad_date_is_skipped_with_warning():
    row = "TRF-2207,Transformer,Transmission,Bay 2,2026-05-07,2026-13-45,34,Oil leak\n"
    assets, warnings = parse_assets(HEADER + row)
    assert assets == []
    assert warnings == [
        "Row 2 (TRF-2207) skipped: bad next_maintenance_date '2026-13-45' (expected YYYY-MM-DD)"
    ]


def test_score_out_of_range_is_skipped_with_warning():
    rows = (
        "A-1,Meter,Distribution,Here,2026-01-01,2026-12-01,101,ok\n"
        "A-2,Meter,Distribution,Here,2026-01-01,2026-12-01,-1,ok\n"
        "A-3,Meter,Distribution,Here,2026-01-01,2026-12-01,good,ok\n"
        "A-4,Meter,Distribution,Here,2026-01-01,2026-12-01,0,ok\n"
        "A-5,Meter,Distribution,Here,2026-01-01,2026-12-01,100,ok\n"
    )
    assets, warnings = parse_assets(HEADER + rows)
    assert [a["asset_id"] for a in assets] == ["A-4", "A-5"]
    assert len(warnings) == 3
    assert "cv_health_score '101' must be a whole number from 0 to 100" in warnings[0]


def test_unknown_type_or_network_is_skipped():
    rows = (
        "A-1,Substation,Distribution,Here,2026-01-01,2026-12-01,50,ok\n"
        "A-2,Pole,Generation,Here,2026-01-01,2026-12-01,50,ok\n"
    )
    assets, warnings = parse_assets(HEADER + rows)
    assert assets == []
    assert warnings == [
        "Row 2 (A-1) skipped: unknown asset_type 'Substation'",
        "Row 3 (A-2) skipped: unknown network 'Generation'",
    ]


def test_blank_rows_are_ignored_silently():
    assets, warnings = parse_assets(HEADER + GOOD_ROW + ",,,,,,,\n")
    assert len(assets) == 1
    assert warnings == []


def test_missing_column_gives_one_clear_warning():
    assets, warnings = parse_assets("asset_id,asset_type\nA-1,Pole\n")
    assert assets == []
    assert "missing these columns" in warnings[0]


# --- load_assets ----------------------------------------------------------


def test_live_fetch_saves_backup(monkeypatch, tmp_path):
    backup = fake_google(monkeypatch, tmp_path, response=FakeResponse(HEADER + GOOD_ROW))
    assets, info = load_assets()
    assert info["mode"] == "live"
    assert len(assets) == 1
    assert backup.read_text() == HEADER + GOOD_ROW


def test_html_instead_of_csv_falls_back_to_backup(monkeypatch, tmp_path):
    sign_in_page = FakeResponse("<!DOCTYPE html><html>Sign in</html>", "text/html; charset=utf-8")
    backup = fake_google(monkeypatch, tmp_path, response=sign_in_page)
    backup.write_text(HEADER + GOOD_ROW)
    assets, info = load_assets()
    assert info["mode"] == "backup"
    assert len(assets) == 1
    assert "Anyone with the link" in info["message"]
    assert backup.read_text() == HEADER + GOOD_ROW  # the backup was not overwritten with HTML


def test_no_network_and_no_backup_returns_empty(monkeypatch, tmp_path):
    fake_google(monkeypatch, tmp_path, error=urllib.error.URLError("no internet"))
    assets, info = load_assets()
    assert assets == []
    assert info["mode"] == "none"
    assert "couldn't reach Google" in info["message"]


def test_load_assets_never_raises(monkeypatch, tmp_path):
    fake_google(monkeypatch, tmp_path, error=RuntimeError("something odd"))
    assets, info = load_assets()
    assert assets == []
    assert info["mode"] == "none"


# --- validation added for production --------------------------------------


@pytest.mark.parametrize(
    "bad_id",
    ["POL/9", "x');alert(1);//", "<script>alert(1)</script>", "A B", "-starts-with-dash", "A" * 65],
)
def test_unsafe_asset_ids_are_skipped(bad_id):
    row = f'"{bad_id}",Pole,Distribution,Here,2026-01-01,2026-12-01,50,ok\n'
    assets, warnings = parse_assets(HEADER + GOOD_ROW + row)
    assert [a["asset_id"] for a in assets] == ["POL-1042"]
    assert len(warnings) == 1
    assert "asset_id may only use letters, numbers" in warnings[0]
    assert bad_id not in warnings[0]  # the bad value is never echoed back into the page


@pytest.mark.parametrize("good_id", ["POL-1042", "TRF_2207", "OHL.3315", "9-A"])
def test_safe_asset_ids_are_accepted(good_id):
    row = f"{good_id},Pole,Distribution,Here,2026-01-01,2026-12-01,50,ok\n"
    assets, warnings = parse_assets(HEADER + row)
    assert warnings == [] and assets[0]["asset_id"] == good_id


def test_bom_at_start_of_text_is_handled():
    assets, warnings = parse_assets("﻿" + HEADER + GOOD_ROW)
    assert warnings == [] and len(assets) == 1


def test_extra_unnamed_values_are_skipped_not_silently_dropped():
    row = "A-1,Meter,Distribution,Here,2026-01-01,2026-12-01,50,ok,SURPRISE\n"
    assets, warnings = parse_assets(HEADER + GOOD_ROW + row)
    assert [a["asset_id"] for a in assets] == ["POL-1042"]
    assert warnings == ["Row 3 (A-1) skipped: it has more values than column headers, so its data may be shifted"]


def test_extra_named_columns_are_ignored():
    text = HEADER.strip() + ",inspector\n" + GOOD_ROW.strip() + ",J. Smith\n"
    assets, warnings = parse_assets(text)
    assert warnings == [] and len(assets) == 1


def test_too_many_rows_is_rejected(monkeypatch):
    monkeypatch.setattr(data_source, "MAX_ROWS", 2)
    rows = "".join(f"A-{i},Meter,Distribution,Here,2026-01-01,2026-12-01,50,ok\n" for i in range(3))
    assets, warnings = parse_assets(HEADER + rows)
    assert assets == []
    assert "more than 2 rows" in warnings[0]


def test_header_only_sheet_is_empty_without_warnings():
    assert parse_assets(HEADER) == ([], [])


# --- import policy: never replace good data with unusable data ------------


def test_empty_sheet_is_published_and_saved(monkeypatch, tmp_path):
    backup = fake_google(monkeypatch, tmp_path, response=FakeResponse(HEADER))
    backup.write_text(HEADER + GOOD_ROW)
    assets, info = load_assets()
    assert info["mode"] == "live" and assets == [] and info["warnings"] == []
    assert backup.read_text() == HEADER  # a deliberately empty sheet is real data


def test_partial_import_publishes_valid_rows_with_warnings(monkeypatch, tmp_path):
    bad = "TRF-1,Transformer,Transmission,,2026-05-07,2026-09-29,34,Oil leak\n"
    backup = fake_google(monkeypatch, tmp_path, response=FakeResponse(HEADER + GOOD_ROW + bad))
    assets, info = load_assets()
    assert info["mode"] == "live" and len(assets) == 1
    assert info["warnings"] == ["Row 3 (TRF-1) skipped: missing location"]
    assert backup.exists()


def test_all_invalid_rows_keep_the_previous_backup(monkeypatch, tmp_path):
    bad = "TRF-1,Transformer,Transmission,,2026-05-07,2026-09-29,34,Oil leak\n"
    backup = fake_google(monkeypatch, tmp_path, response=FakeResponse(HEADER + bad))
    backup.write_text(HEADER + GOOD_ROW)
    assets, info = load_assets()
    assert info["mode"] == "backup"
    assert [a["asset_id"] for a in assets] == ["POL-1042"]
    assert "none of the sheet's 1 rows were valid" in info["message"]
    assert info["warnings"] == ["Latest sheet: Row 2 (TRF-1) skipped: missing location"]
    assert backup.read_text() == HEADER + GOOD_ROW  # untouched


def test_missing_columns_keep_the_previous_backup(monkeypatch, tmp_path):
    backup = fake_google(monkeypatch, tmp_path, response=FakeResponse("name,score\nA,1\n"))
    backup.write_text(HEADER + GOOD_ROW)
    assets, info = load_assets()
    assert info["mode"] == "backup" and len(assets) == 1
    assert "missing these columns" in info["message"]
    assert backup.read_text() == HEADER + GOOD_ROW


def test_parse_crash_falls_back_to_backup(monkeypatch, tmp_path):
    backup = fake_google(monkeypatch, tmp_path, response=FakeResponse(HEADER + GOOD_ROW))
    backup.write_text(HEADER + GOOD_ROW)
    real_parse = data_source._parse
    calls = []

    def crash_on_live_data(text):
        calls.append(text)
        if len(calls) == 1:
            raise csv.Error("corrupted")
        return real_parse(text)

    monkeypatch.setattr(data_source, "_parse", crash_on_live_data)
    assets, info = load_assets()
    assert info["mode"] == "backup" and len(assets) == 1
    assert "couldn't be read (Error)" in info["message"]


def test_oversized_download_falls_back(monkeypatch, tmp_path):
    monkeypatch.setattr(data_source, "MAX_DOWNLOAD_BYTES", 50)
    backup = fake_google(monkeypatch, tmp_path, response=FakeResponse(HEADER + GOOD_ROW))
    backup.write_text(HEADER + GOOD_ROW)
    assets, info = load_assets()
    assert info["mode"] == "backup"
    assert "larger than" in info["message"]


def test_falls_back_to_shipped_seed_when_no_runtime_backup(monkeypatch, tmp_path):
    fake_google(monkeypatch, tmp_path, error=urllib.error.URLError("no internet"))
    (tmp_path / "seed.csv").write_text(HEADER + GOOD_ROW)
    assets, info = load_assets()
    assert info["mode"] == "backup" and len(assets) == 1
    assert "the backup copy that ships with the app" in info["message"]


def test_backup_with_bom_is_read(monkeypatch, tmp_path):
    backup = fake_google(monkeypatch, tmp_path, error=urllib.error.URLError("no internet"))
    backup.write_text("﻿" + HEADER + GOOD_ROW, encoding="utf-8")
    assets, info = load_assets()
    assert info["mode"] == "backup" and len(assets) == 1 and info["warnings"] == []


def test_fetched_time_uses_app_timezone(monkeypatch, tmp_path):
    fake_google(monkeypatch, tmp_path, response=FakeResponse(HEADER + GOOD_ROW))
    toronto = datetime(2026, 10, 5, 23, 45, tzinfo=ZoneInfo("America/Toronto"))
    monkeypatch.setattr(data_source, "local_now", lambda: toronto)
    _assets, info = load_assets()
    assert info["fetched_at"] == "23:45"
