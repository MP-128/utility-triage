"""Loads asset health data from the Google Sheet, falling back to the saved backup copy.

Import policy (what happens to each download):
- Usable: the columns are right and at least one row is valid, or the sheet is deliberately empty
  (header row only). It's shown, and saved as the new backup. Invalid rows are skipped and listed
  as warnings on the dashboard.
- Unusable: missing columns, too large, unreadable, or it has rows but none of them are valid.
  It's rejected. The previous backup is kept untouched and shown instead, with the reason.
"""
import csv
import io
import logging
import os
import re
import urllib.error
import urllib.request
from datetime import date, datetime
from zoneinfo import ZoneInfo

from config import (
    APP_TIMEZONE,
    BACKUP_PATH,
    FETCH_TIMEOUT_SECONDS,
    MAX_DOWNLOAD_BYTES,
    MAX_ROWS,
    SEED_BACKUP_PATH,
    SHEET_CSV_URL,
    local_now,
)

log = logging.getLogger(__name__)

COLUMNS = [
    "asset_id",
    "asset_type",
    "network",
    "location",
    "last_inspection_date",
    "next_maintenance_date",
    "cv_health_score",
    "condition_notes",
]
ASSET_TYPES = ["Pole", "Transformer", "Overhead Line", "Meter"]
NETWORKS = ["Distribution", "Transmission"]
DATE_COLUMNS = ["last_inspection_date", "next_maintenance_date"]

# Letters, digits, dot, dash and underscore; starts with a letter or digit; at most 64 characters.
# This keeps every ID safe to put in a web address (no slashes, quotes or spaces).
ASSET_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}")
EXTRA = "_extra_values"  # where csv.DictReader puts values that have no column header
MAX_WARNINGS_SHOWN = 20


class SheetNotShared(Exception):
    """Google sent back a web page (usually a sign-in page) instead of CSV."""


class DownloadTooLarge(Exception):
    """The sheet is bigger than MAX_DOWNLOAD_BYTES."""


def _parse_date(text):
    """Read a YYYY-MM-DD date. Also accepts M/D/YYYY, which Google Sheets may show after a hand edit."""
    try:
        return date.fromisoformat(text)
    except ValueError:
        return datetime.strptime(text, "%m/%d/%Y").date()


def _parse(csv_text):
    """Validate CSV text. Returns (assets, warnings, data_rows, problem).

    `problem` is a reason the whole file can't be used (wrong columns, too many rows), or None.
    `data_rows` counts non-blank rows, so an empty sheet can be told apart from an all-invalid one.
    """
    if csv_text.startswith("﻿"):  # byte-order mark some programs add to the start of a CSV
        csv_text = csv_text[1:]
    reader = csv.DictReader(io.StringIO(csv_text), restkey=EXTRA)
    missing_columns = [c for c in COLUMNS if c not in (reader.fieldnames or [])]
    if missing_columns:
        problem = f"the sheet is missing these columns: {', '.join(missing_columns)}"
        return [], [problem[0].upper() + problem[1:]], 0, problem

    assets, warnings, seen_ids, data_rows = [], [], set(), 0
    # Row 1 is the header, so the first asset is on sheet row 2.
    for row_number, row in enumerate(reader, start=2):
        values = {c: (row.get(c) or "").strip() for c in COLUMNS}
        extras = [v for v in row.get(EXTRA, []) if v and v.strip()]
        if not any(values.values()) and not extras:
            continue  # completely blank row
        data_rows += 1
        if data_rows > MAX_ROWS:
            return [], [], data_rows, f"the sheet has more than {MAX_ROWS} rows"
        label = f"Row {row_number} ({values['asset_id'] or 'no asset_id'})"

        if extras:
            warnings.append(f"{label} skipped: it has more values than column headers, so its data may be shifted")
            continue
        empty = [c for c in COLUMNS if not values[c]]
        if empty:
            warnings.append(f"{label} skipped: missing {', '.join(empty)}")
            continue
        if not ASSET_ID_PATTERN.fullmatch(values["asset_id"]):
            warnings.append(
                f"Row {row_number} skipped: asset_id may only use letters, numbers, '.', '-' and '_' "
                "(no spaces or slashes), up to 64 characters"
            )
            continue
        if values["asset_type"] not in ASSET_TYPES:
            warnings.append(f"{label} skipped: unknown asset_type '{values['asset_type']}'")
            continue
        if values["network"] not in NETWORKS:
            warnings.append(f"{label} skipped: unknown network '{values['network']}'")
            continue
        bad_date = None
        for c in DATE_COLUMNS:
            try:
                values[c] = _parse_date(values[c])
            except ValueError:
                bad_date = c
                break
        if bad_date:
            warnings.append(f"{label} skipped: bad {bad_date} '{values[bad_date]}' (expected YYYY-MM-DD)")
            continue
        try:
            score = int(values["cv_health_score"])
        except ValueError:
            score = None
        if score is None or not 0 <= score <= 100:
            warnings.append(
                f"{label} skipped: cv_health_score '{values['cv_health_score']}' must be a whole number from 0 to 100"
            )
            continue
        values["cv_health_score"] = score
        if values["asset_id"] in seen_ids:
            warnings.append(f"{label} skipped: duplicate asset_id")
            continue

        seen_ids.add(values["asset_id"])
        assets.append(values)
    return assets, warnings, data_rows, None


def parse_assets(csv_text):
    """Turn CSV text into (assets, warnings). Bad rows are skipped with a readable warning."""
    assets, warnings, _rows, problem = _parse(csv_text)
    if problem and not warnings:
        warnings = [problem[0].upper() + problem[1:]]
    return assets, warnings


def _fetch_sheet_csv():
    """Download the sheet as CSV text. Raises if Google can't be reached, the sheet isn't public, or it's too big."""
    request = urllib.request.Request(SHEET_CSV_URL, headers={"User-Agent": "utility-triage/1.0"})
    with urllib.request.urlopen(request, timeout=FETCH_TIMEOUT_SECONDS) as response:
        content_type = response.headers.get("Content-Type", "")
        body = response.read(MAX_DOWNLOAD_BYTES + 1)
    if len(body) > MAX_DOWNLOAD_BYTES:
        raise DownloadTooLarge()
    text = body.decode("utf-8-sig")
    if "text/html" in content_type or text.lstrip().lower().startswith(("<!doctype html", "<html")):
        raise SheetNotShared()
    return text


def _explain(error):
    """A plain-language reason for a failed download."""
    if isinstance(error, SheetNotShared) or (
        isinstance(error, urllib.error.HTTPError) and error.code in (401, 403)
    ):
        return "the Google Sheet isn't shared as 'Anyone with the link' (Google sent a sign-in page instead of data)"
    if isinstance(error, DownloadTooLarge):
        return f"the sheet is larger than the {MAX_DOWNLOAD_BYTES // 1_000_000} MB limit"
    if isinstance(error, urllib.error.HTTPError) and error.code == 404:
        return "Google couldn't find the sheet (HTTP 404). Check SHEET_ID"
    if isinstance(error, urllib.error.HTTPError):
        return f"Google returned an error (HTTP {error.code})"
    if isinstance(error, UnicodeDecodeError):
        return "the download wasn't readable text (expected UTF-8 CSV)"
    if isinstance(error, (urllib.error.URLError, TimeoutError, OSError)):
        return f"couldn't reach Google ({getattr(error, 'reason', error)}). Check the internet connection"
    return f"unexpected error ({type(error).__name__})"


def _check_live(text):
    """Validate a download. Returns (assets, warnings, problem); problem is None when it's usable."""
    try:
        assets, warnings, data_rows, problem = _parse(text)
    except Exception as error:  # e.g. csv.Error on a corrupted file
        return [], [], f"the sheet couldn't be read ({type(error).__name__})"
    if problem is None and data_rows and not assets:
        problem = f"none of the sheet's {data_rows} rows were valid"
    return assets, warnings, problem


def _save_backup(text):
    """Save a good download. Failing to save never breaks the page."""
    try:
        os.makedirs(os.path.dirname(BACKUP_PATH) or ".", exist_ok=True)
        with open(BACKUP_PATH, "w", encoding="utf-8", newline="") as f:
            f.write(text)
    except OSError as error:
        log.warning("Couldn't save the backup copy: %s", error)


def _load_backup(reason, now, live_warnings):
    """Read the newest available backup after a failed or rejected download."""
    path = next((p for p in (BACKUP_PATH, SEED_BACKUP_PATH) if os.path.exists(p)), None)
    if path is None:
        return [], {
            "mode": "none",
            "fetched_at": now.strftime("%H:%M"),
            "message": f"No data: {reason}, and there is no backup copy yet.",
            "warnings": live_warnings,
        }
    if path == BACKUP_PATH:
        saved = datetime.fromtimestamp(os.path.getmtime(path), ZoneInfo(APP_TIMEZONE))
        copy = f"the backup copy saved {saved:%Y-%m-%d %H:%M}"
    else:
        copy = "the backup copy that ships with the app"
    with open(path, encoding="utf-8-sig") as f:
        assets, warnings, _rows, _problem = _parse(f.read())
    return assets, {
        "mode": "backup",
        "fetched_at": now.strftime("%H:%M"),
        "message": f"Showing {copy} because {reason}.",
        "warnings": live_warnings + warnings,
    }


def load_assets():
    """Return (assets, source_info). Tries the live sheet, then the backup. Never raises."""
    now = local_now()
    try:
        live_warnings = []
        try:
            text = _fetch_sheet_csv()
        except Exception as error:
            reason = _explain(error)
        else:
            assets, warnings, problem = _check_live(text)
            if problem is None:
                _save_backup(text)
                return assets, {
                    "mode": "live",
                    "fetched_at": now.strftime("%H:%M"),
                    "message": "Live from Google Sheet",
                    "warnings": warnings,
                }
            reason = f"the latest version of the sheet was rejected: {problem}"
            live_warnings = [f"Latest sheet: {w}" for w in warnings[:MAX_WARNINGS_SHOWN]]
        log.warning("Live sheet not used: %s", reason)  # the reason only, never asset data
        return _load_backup(reason, now, live_warnings)
    except Exception as error:  # last-resort guard so the dashboard always loads
        log.exception("Loading assets failed")
        return [], {
            "mode": "none",
            "fetched_at": now.strftime("%H:%M"),
            "message": f"No data: unexpected error ({type(error).__name__})",
            "warnings": [],
        }


if __name__ == "__main__":
    assets, info = load_assets()
    if info["mode"] == "live":
        print(f"{len(assets)} assets loaded (live from Google Sheet)")
        print(f"Fetched at {info['fetched_at']} ({APP_TIMEZONE}), backup saved to {BACKUP_PATH}")
    else:
        print(f"{len(assets)} assets loaded ({info['mode']})")
        print(info["message"])
    for warning in info["warnings"]:
        print("  Warning:", warning)
    if assets:
        print("Example asset:")
        for key, value in assets[0].items():
            print(f"  {key}: {value!r}")
