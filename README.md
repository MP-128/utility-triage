# Utility Asset Triage

A small web dashboard for dispatchers and engineering teams. It reads electric distribution and
transmission asset health (poles, transformers, overhead lines and meters) **live from a Google Sheet**
and ranks every asset by urgency, so the assets that need maintenance in the next 1–2 months are at the top.

For each asset you see its current state, how long until its scheduled maintenance, its computer-vision
(CV) health score, a risk rating (Critical / High / Medium / Low) and the plain-English reasons for it.

**To put it online, follow [DEPLOY.md](DEPLOY.md)** (GitHub + Vercel, password-protected).

## Setup and run

Requires Python 3.14 (pinned in `.python-version`).

```bash
cd ~/Desktop/utility-triage
python3 -m venv .venv                          # first time only
.venv/bin/pip install -r requirements-dev.txt  # first time only: app + test tools
.venv/bin/python app.py          # then open http://127.0.0.1:5001
.venv/bin/pytest -v              # run all tests (no internet needed)
.venv/bin/python data_source.py  # check the Google Sheet connection
.venv/bin/python risk.py         # print every live asset with its rating
```

Locally the app has no password. To try the password locally:
`APP_PASSWORD=test .venv/bin/python app.py` (username `triage`). All settings are listed in `.env.example`.

The app uses port **5001** because macOS AirPlay Receiver takes port 5000.

> **macOS + python.org Python:** if you see `CERTIFICATE_VERIFY_FAILED`, run
> `"/Applications/Python 3.14/Install Certificates.command"` once.

## How it works

| File | Job |
|---|---|
| `config.py` | Settings: which Google Sheet (`SHEET_ID`), backup location, timezone, size limits |
| `data_source.py` | Downloads the sheet as CSV, validates every row, decides whether to accept it, falls back to the backup |
| `risk.py` | The triage rules: turns dates and CV scores into a rating with reasons |
| `app.py` | The Flask web app: dashboard, filters, asset detail page, 404 page, password check, `/healthz` |
| `templates/` | The HTML pages (`base.html` holds the shared layout and styles) |
| `tests/` | Automatic tests for all of the above (no network needed) |
| `vercel.json`, `.python-version`, `requirements.txt` | Deployment settings for Vercel (runtime packages only) |
| `requirements-dev.txt` | Runtime packages plus test tools, for your Mac |

### The Google Sheet connection

- Data lives in the Google Sheet **Utility Asset Health**, with columns
  `asset_id, asset_type, network, location, last_inspection_date, next_maintenance_date, cv_health_score, condition_notes`.
- The sheet is shared as **"Anyone with the link → Viewer"**. That lets the app download it from
  `https://docs.google.com/spreadsheets/d/<SHEET_ID>/export?format=csv` with no login.
- The data is fetched fresh on every page load, so an edit in the sheet shows up after you click **Refresh data**.
- To use a different sheet, set the `SHEET_ID` environment variable or edit `config.py`.
- Rows with a missing field, a bad date, a score outside 0–100, an unknown type or network, a duplicate ID,
  more values than column headers, or an unsafe `asset_id` are skipped, and the dashboard lists a warning
  for each one. An `asset_id` may only use letters, numbers, `.`, `-` and `_` (up to 64 characters), so
  every ID works in a web address and can't smuggle code into the page.

### Import policy: good data is never replaced by unusable data

| The download… | What happens |
|---|---|
| has the right columns and at least one valid row | **Shown.** Invalid rows are skipped and listed as warnings. Saved as the new backup. |
| has only the header row (the sheet is deliberately empty) | **Shown** as empty ("There are no assets to show yet"). Saved as the new backup. |
| is missing columns, has rows but none valid, is unreadable, larger than 2 MB, or over 5,000 rows | **Rejected.** The previous backup stays untouched and is shown, with the reason and the sheet's row problems. |
| can't be fetched (no internet, sheet not shared, wrong ID) | The previous backup is shown, with the reason. |

### Offline backup

Each accepted download is saved: to `data/backup.csv` on your Mac, or to `/tmp` on Vercel, whose servers
can't write anywhere else. When the live sheet can't be used, the app shows the newest saved copy, or
failing that, the `data/backup.csv` that ships with the code, under an orange **"Showing backup copy"**
banner explaining why. If there's no backup at all, it shows an empty dashboard with the reason. It never crashes.

### Dates and timezone

"Today" and the "fetched at" time use `APP_TIMEZONE` (default `America/Toronto`), not the server's clock.
Servers usually run on UTC, which would make "days until maintenance" wrong by a day in the evening.

### Security

- **Password:** set `APP_PASSWORD` to require a username (`APP_USERNAME`, default `triage`) and password.
  On Vercel the app refuses to run without one (503). `/healthz` stays open and returns only `{"status": "ok"}`.
- **No scripts:** the pages contain no JavaScript, and a Content-Security-Policy header blocks scripts entirely.
  Responses also send `nosniff`, `no-store` caching and a framing ban.
- **Limits:** downloads over 2 MB or 5,000 rows are rejected. Logs record why a sheet wasn't used, never asset data.

## Risk rules

Each asset gets two signals. **The more severe signal wins.**

| Rating | Time signal (days until next maintenance) | CV signal (health score, 100 = perfect) |
|---|---|---|
| **Critical** (red) | overdue (< 0 days) | < 20 (very poor) |
| **High** (orange) | 0–60 days | 20–39 (poor) |
| **Medium** (yellow) | 61–120 days | 40–59 (fair) |
| **Low** (green) | more than 120 days | 60 or more |

Reasons list every signal that isn't Low, e.g. "Maintenance overdue by 5 days", "CV health 31/100 (poor)".
The thresholds live in `risk.py` (`time_rating` and `cv_rating`) and are covered by `tests/test_risk.py`.

## Next steps

- **Private sheet:** use OAuth or a service account with the Google Sheets API, so the sheet doesn't need to be link-shared.
- **Map view:** plot assets by location, colored by rating, so crews can plan routes.
- **Ingest CV images directly:** score inspection photos or drone footage automatically, without typing scores into the sheet.
- **Create work orders:** turn a Critical or High asset into a work order in the maintenance system with one click.
- **User accounts:** sign-in, roles (dispatcher vs engineer) and an audit trail of who reviewed what.
