"""Tests for risk.py. A fixed 'today' keeps results the same every day."""
from datetime import date, timedelta

import pytest

from risk import RATINGS, days_until_maintenance, rate_asset

TODAY = date(2026, 10, 4)


def make_asset(days=200, score=85):
    """An asset whose maintenance is `days` from TODAY, with the given CV score."""
    return {
        "asset_id": "TEST-1",
        "asset_type": "Pole",
        "network": "Distribution",
        "location": "Test St",
        "last_inspection_date": date(2026, 1, 1),
        "next_maintenance_date": TODAY + timedelta(days=days),
        "cv_health_score": score,
        "condition_notes": "test",
    }


def test_ratings_order():
    assert RATINGS == ["Critical", "High", "Medium", "Low"]


@pytest.mark.parametrize("days", [-30, -1, 0, 60, 61, 120, 121, 365])
def test_days_until_maintenance(days):
    assert days_until_maintenance(make_asset(days=days), TODAY) == days


@pytest.mark.parametrize(
    "days, expected",
    [(-1, "Critical"), (0, "High"), (60, "High"), (61, "Medium"), (120, "Medium"), (121, "Low")],
)
def test_time_signal_boundaries(days, expected):
    rating, _ = rate_asset(make_asset(days=days, score=85), TODAY)
    assert rating == expected


@pytest.mark.parametrize(
    "score, expected",
    [(19, "Critical"), (20, "High"), (39, "High"), (40, "Medium"), (59, "Medium"), (60, "Low")],
)
def test_cv_signal_boundaries(score, expected):
    rating, _ = rate_asset(make_asset(days=200, score=score), TODAY)
    assert rating == expected


@pytest.mark.parametrize(
    "days, score, expected",
    [
        (200, 15, "Critical"),  # distant maintenance, very poor CV
        (-5, 90, "Critical"),  # overdue, healthy CV
        (30, 50, "High"),  # High time beats Medium CV
        (100, 35, "High"),  # High CV beats Medium time
        (90, 55, "Medium"),  # both Medium
    ],
)
def test_worst_signal_wins(days, score, expected):
    rating, _ = rate_asset(make_asset(days=days, score=score), TODAY)
    assert rating == expected


def test_reason_overdue():
    assert rate_asset(make_asset(days=-5), TODAY) == ("Critical", ["Maintenance overdue by 5 days"])


def test_reason_overdue_one_day_is_singular():
    assert rate_asset(make_asset(days=-1), TODAY)[1] == ["Maintenance overdue by 1 day"]


def test_reason_due_soon():
    assert rate_asset(make_asset(days=23), TODAY) == ("High", ["Maintenance due in 23 days"])


def test_reason_due_today():
    assert rate_asset(make_asset(days=0), TODAY)[1] == ["Maintenance due today"]


@pytest.mark.parametrize(
    "score, reason",
    [(15, "CV health 15/100 (very poor)"), (31, "CV health 31/100 (poor)"), (55, "CV health 55/100 (fair)")],
)
def test_reason_cv(score, reason):
    assert rate_asset(make_asset(days=200, score=score), TODAY)[1] == [reason]


def test_both_reasons_listed():
    rating, reasons = rate_asset(make_asset(days=23, score=31), TODAY)
    assert rating == "High"
    assert reasons == ["Maintenance due in 23 days", "CV health 31/100 (poor)"]


def test_no_issues_reason():
    assert rate_asset(make_asset(days=200, score=85), TODAY) == (
        "Low",
        ["No issues: maintenance in 200 days, CV health 85/100"],
    )
