"""Tests for the web pages, using Flask's test client. No network: load_assets is replaced with sample data."""
from datetime import date, timedelta

import pytest

import app as app_module

TODAY = date.today()


def sample(asset_id, asset_type, network, days, score):
    return {
        "asset_id": asset_id,
        "asset_type": asset_type,
        "network": network,
        "location": f"{asset_id} location",
        "last_inspection_date": TODAY - timedelta(days=100),
        "next_maintenance_date": TODAY + timedelta(days=days),
        "cv_health_score": score,
        "condition_notes": f"{asset_id} notes",
    }


SAMPLE_ASSETS = [
    sample("POL-1", "Pole", "Distribution", 200, 90),  # Low
    sample("TRF-1", "Transformer", "Transmission", -5, 80),  # Critical (overdue)
    sample("TRF-2", "Transformer", "Distribution", 100, 70),  # Medium
    sample("OHL-1", "Overhead Line", "Transmission", 300, 31),  # High (poor CV)
    sample("MTR-1", "Meter", "Distribution", 30, 85),  # High (due soon)
]
LIVE = {"mode": "live", "fetched_at": "14:32", "message": "Live from Google Sheet", "warnings": []}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(app_module, "load_assets", lambda: (SAMPLE_ASSETS, LIVE))
    app_module.app.config["TESTING"] = True
    return app_module.app.test_client()


def test_dashboard_ok(client):
    response = client.get("/")
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Live from Google Sheet" in html and "14:32" in html
    for asset_id in ["POL-1", "TRF-1", "TRF-2", "OHL-1", "MTR-1"]:
        assert asset_id in html


def test_dashboard_sorted_most_urgent_first(client):
    html = client.get("/").get_data(as_text=True)
    positions = [html.index(f">{asset_id}<") for asset_id in ["TRF-1", "MTR-1", "OHL-1", "TRF-2", "POL-1"]]
    assert positions == sorted(positions)


def test_filter_by_type_shows_only_transformers(client):
    response = client.get("/?type=Transformer")
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "TRF-1" in html and "TRF-2" in html
    for other in ["POL-1", "OHL-1", "MTR-1"]:
        assert other not in html


def test_filter_by_network_and_risk(client):
    html = client.get("/?network=Transmission&risk=High").get_data(as_text=True)
    assert "OHL-1" in html
    for other in ["POL-1", "TRF-1", "TRF-2", "MTR-1"]:
        assert other not in html


def test_unknown_filter_value_is_ignored(client):
    html = client.get("/?type=Spaceship").get_data(as_text=True)
    assert "POL-1" in html and "TRF-1" in html


def test_days_remaining_wording(client):
    html = client.get("/").get_data(as_text=True)
    assert "Overdue 5 days" in html
    assert "30 days" in html


def test_asset_detail_ok(client):
    response = client.get("/asset/TRF-1")
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "TRF-1 notes" in html
    assert "Critical" in html
    assert "Maintenance overdue by 5 days" in html
    assert "Back to dashboard" in html


def test_unknown_asset_is_404(client):
    response = client.get("/asset/NOPE")
    assert response.status_code == 404
    assert "There is no asset with ID" in response.get_data(as_text=True)


def test_unknown_page_is_404(client):
    response = client.get("/no-such-page")
    assert response.status_code == 404
    assert "Back to dashboard" in response.get_data(as_text=True)


def test_backup_banner_and_warnings(monkeypatch):
    backup = {
        "mode": "backup",
        "fetched_at": "09:15",
        "message": "Offline: showing backup copy from 2026-10-04 09:15 because couldn't reach Google.",
        "warnings": ["Row 7 (X-1) skipped: missing location"],
    }
    monkeypatch.setattr(app_module, "load_assets", lambda: (SAMPLE_ASSETS, backup))
    html = app_module.app.test_client().get("/").get_data(as_text=True)
    assert "Offline: showing backup copy" in html
    assert "Row 7 (X-1) skipped: missing location" in html


# --- production hardening -------------------------------------------------

import re
from datetime import datetime
from zoneinfo import ZoneInfo


def client_with(monkeypatch, assets, source=LIVE):
    monkeypatch.setattr(app_module, "load_assets", lambda: (assets, source))
    return app_module.app.test_client()


def test_no_inline_javascript_anywhere(client):
    for path in ["/", "/asset/TRF-1", "/no-such-page"]:
        html = client.get(path).get_data(as_text=True)
        assert "onclick" not in html and "<script" not in html


def test_script_payload_in_data_is_escaped(monkeypatch):
    # The parser rejects IDs like these, but the page must stay safe even if one slipped through.
    evil = sample("x');alert(1);//", "Pole", "Distribution", 200, 90)
    evil["location"] = "<script>alert(1)</script>"
    html = client_with(monkeypatch, [evil]).get("/").get_data(as_text=True)
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html
    assert "onclick" not in html


def test_every_asset_link_opens_its_detail_page(client):
    html = client.get("/").get_data(as_text=True)
    links = re.findall(r'href="(/asset/[^"]+)"', html)
    assert len(links) == len(SAMPLE_ASSETS)
    for link in links:
        assert client.get(link.replace("&amp;", "&")).status_code == 200


def test_security_headers(client):
    response = client.get("/")
    csp = response.headers["Content-Security-Policy"]
    assert "default-src 'none'" in csp and "script-src" not in csp  # so no scripts may run
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["Cache-Control"] == "no-store"
    assert client.get("/no-such-page").headers["Content-Security-Policy"] == csp


def test_empty_sheet_message_differs_from_filter_mismatch(monkeypatch):
    c = client_with(monkeypatch, [])
    html = c.get("/").get_data(as_text=True)
    assert "There are no assets to show yet" in html
    assert "No assets match these filters" not in html


def test_filter_mismatch_message(client):
    html = client.get("/?type=Meter&risk=Critical").get_data(as_text=True)
    assert "No assets match these filters" in html
    assert "There are no assets to show yet" not in html


def test_toronto_late_evening_is_still_today(monkeypatch):
    # 23:30 in Toronto on Oct 5 is already 03:30 UTC on Oct 6. An asset due Oct 5 is due today, not overdue.
    toronto = datetime(2026, 10, 5, 23, 30, tzinfo=ZoneInfo("America/Toronto"))
    assert toronto.astimezone(ZoneInfo("UTC")).date().isoformat() == "2026-10-06"
    monkeypatch.setattr(app_module, "local_now", lambda: toronto)
    asset = sample("POL-9", "Pole", "Distribution", 0, 90)
    asset["next_maintenance_date"] = toronto.date()
    html = client_with(monkeypatch, [asset]).get("/").get_data(as_text=True)
    assert "Due today" in html and "Overdue" not in html


# --- password protection --------------------------------------------------


def basic(username, password):
    import base64

    token = base64.b64encode(f"{username}:{password}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


def test_no_password_set_locally_means_open(client):
    assert client.get("/").status_code == 200


def test_password_required_when_set(client, monkeypatch):
    monkeypatch.setenv("APP_PASSWORD", "s3cret")
    for path in ["/", "/asset/TRF-1", "/no-such-page"]:
        response = client.get(path)
        assert response.status_code == 401
        assert response.headers["WWW-Authenticate"].startswith("Basic")
        assert "TRF-1" not in response.get_data(as_text=True)


def test_wrong_password_or_username_rejected(client, monkeypatch):
    monkeypatch.setenv("APP_PASSWORD", "s3cret")
    assert client.get("/", headers=basic("triage", "wrong")).status_code == 401
    assert client.get("/", headers=basic("someone", "s3cret")).status_code == 401


def test_correct_password_allowed(client, monkeypatch):
    monkeypatch.setenv("APP_PASSWORD", "s3cret")
    assert client.get("/", headers=basic("triage", "s3cret")).status_code == 200
    assert client.get("/asset/TRF-1", headers=basic("triage", "s3cret")).status_code == 200


def test_custom_username(client, monkeypatch):
    monkeypatch.setenv("APP_PASSWORD", "s3cret")
    monkeypatch.setenv("APP_USERNAME", "dispatch")
    assert client.get("/", headers=basic("dispatch", "s3cret")).status_code == 200
    assert client.get("/", headers=basic("triage", "s3cret")).status_code == 401


def test_vercel_without_password_fails_closed(client, monkeypatch):
    monkeypatch.setattr(app_module, "ON_VERCEL", True)
    response = client.get("/")
    assert response.status_code == 503
    assert "APP_PASSWORD" in response.get_data(as_text=True)


def test_healthz_needs_no_password_and_reveals_nothing(client, monkeypatch):
    monkeypatch.setenv("APP_PASSWORD", "s3cret")
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}
