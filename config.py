"""Settings shared by the whole app: where the Google Sheet lives, where the backup goes, and the local timezone.

Every setting can be overridden with an environment variable (see .env.example). On Vercel, set them in
Project → Settings → Environment Variables.
"""
import os
from datetime import datetime
from zoneinfo import ZoneInfo

# The long ID in the sheet's link: docs.google.com/spreadsheets/d/<SHEET_ID>/edit
SHEET_ID = os.environ.get("SHEET_ID", "1LQmlWcPRNL-WhnyOXdU0b7FXrfNDpoCiKjQhjLT3nzU")

# Google turns any sheet shared as "Anyone with the link" into CSV at this address.
SHEET_CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"

# Vercel sets VERCEL=1 automatically on its servers.
ON_VERCEL = bool(os.environ.get("VERCEL"))

# The backup copy that ships with the code. It's the last resort if Google can't be reached.
SEED_BACKUP_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "backup.csv")

# Where each good download is saved. Vercel's servers can only write to /tmp, so use that there.
BACKUP_PATH = os.environ.get("BACKUP_PATH") or (
    "/tmp/utility-triage-backup.csv" if ON_VERCEL else SEED_BACKUP_PATH
)

# Safety limits so a huge or broken sheet can't slow the app down.
FETCH_TIMEOUT_SECONDS = 10
MAX_DOWNLOAD_BYTES = 2_000_000
MAX_ROWS = 5000

# Ratings depend on "today", so pin the timezone. Servers run on UTC, and Vercel doesn't allow
# setting the usual TZ variable, so the app converts the time itself.
APP_TIMEZONE = os.environ.get("APP_TIMEZONE", "America/Toronto")


def local_now():
    """The current date and time in APP_TIMEZONE (timezone-aware)."""
    return datetime.now(ZoneInfo(APP_TIMEZONE))
