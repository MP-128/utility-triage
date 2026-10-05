# Progress log

## Phase 1: Google Sheet + data loader (2026-10-04) ✅

**Google Sheet**
- Name: Utility Asset Health
- Link: https://docs.google.com/spreadsheets/d/1LQmlWcPRNL-WhnyOXdU0b7FXrfNDpoCiKjQhjLT3nzU/edit
- `SHEET_ID`: `1LQmlWcPRNL-WhnyOXdU0b7FXrfNDpoCiKjQhjLT3nzU`
- Shared as "Anyone with the link → Viewer" (needed for the CSV export URL to work).
- 16 assets: all 4 types (Pole, Transformer, Overhead Line, Meter) and both networks. Dates were
  chosen relative to 2026-10-04 so the ratings spread out:
  - Critical: POL-1042, TRF-2207, MTR-4481 (overdue); OHL-3315 (CV 14, maintenance far off)
  - High: POL-1077, TRF-2251, MTR-4502 (due ≤ 60 days); OHL-3390 (CV 31, maintenance far off)
  - Medium: POL-1103, OHL-3402, MTR-4560 (due 61–120 days); TRF-2288 (CV 47, maintenance far off)
  - Low: MTR-4533, POL-1150, TRF-2310, OHL-3455

**Built**
- `config.py`: `SHEET_ID` (overridable by the `SHEET_ID` env var), `SHEET_CSV_URL`, `BACKUP_PATH`.
- `data_source.py`: `parse_assets(csv_text)` and `load_assets()` per the contract; `python data_source.py` prints a summary.
- `tests/test_data_source.py` (11 tests, no network) and `tests/conftest.py` (lets tests import the app modules).
- `data/backup.csv`: written automatically after each successful live fetch.

**Check results**
- `.venv/bin/pytest -v` → 11 passed
- `.venv/bin/python data_source.py` → `16 assets loaded (live from Google Sheet)` plus example asset POL-1042
- `data/backup.csv` exists (header + 16 rows)

**Issues hit and fixed**
- `CERTIFICATE_VERIFY_FAILED` on HTTPS: the python.org installer hadn't installed certificates. Fixed by
  running `/Applications/Python 3.14/Install Certificates.command` (one-time, machine-wide, not a project
  dependency). **If the interview uses a different Mac with python.org Python, run this again there.**
- Before the sheet was shared, Google returned a sign-in HTML page; the loader detected it and reported
  "isn't shared as 'Anyone with the link'" as designed.

**Notes for Phase 2**
- Asset dicts use the exact column names; dates are `datetime.date`, score is `int`.
- Dates in the sheet export as `YYYY-MM-DD`. The parser also accepts `M/D/YYYY` in case a hand edit in
  Sheets reformats a date.
- `load_assets()` skips duplicate `asset_id`s with a warning (so `/asset/<id>` is never ambiguous).
- The sample dates are fixed in the sheet, so ratings drift as real days pass. Re-check before the interview.

## Phase 2: Risk rules + tests (2026-10-04) ✅

**Built**
- `risk.py`: `RATINGS`, `days_until_maintenance(asset, today)`, `rate_asset(asset, today)` per the contract,
  plus small helpers `time_rating(days)` and `cv_rating(score)`. `python risk.py` prints the live table below.
- `tests/test_risk.py`: 35 tests, all with fixed `today = 2026-10-04`: day boundaries (−1, 0, 60, 61, 120, 121),
  CV boundaries (19, 20, 39, 40, 59, 60), worst-signal-wins combinations, and the exact reason wording.

**Wording decisions (beyond the contract examples)**
- 1 day is singular: "Maintenance overdue by 1 day".
- 0 days reads "Maintenance due today" (still High).
- Reasons are listed time-signal first, then CV.

**Check results**
- `.venv/bin/pytest -v` → 46 passed (11 data source + 35 risk)
- Live table as of 2026-10-04: Critical 4, High 4, Medium 4, Low 4. All four ratings present.
  Most urgent: MTR-4481 (overdue 30 days), POL-1042, TRF-2207, OHL-3315 (CV 14).

**Notes for Phase 3**
- Dashboard sort: `(RATINGS.index(rating), days_until_maintenance)`, the same key `risk.py`'s table uses.
- "Days remaining" display: negative → "Overdue N days", otherwise "N days".
- Demo live moment: changing a Low asset's CV score to 15 (e.g. POL-1150) makes it Critical.

## Phase 3: Dashboard, filters, detail page, demo prep (2026-10-04) ✅

**Built**
- `templates/base.html`: shared layout + inline CSS, rating colors (Critical red, High orange, Medium yellow,
  Low green) always shown with the text label, data-source banner, phone layout (2-column tiles; table
  scrolls sideways inside its own box).
- `templates/dashboard.html`: banner + skipped-row warnings, "Refresh data" link, clickable count tiles
  (click again to un-filter), GET filter form (type / network / risk) with Clear, sorted table, each row
  links to its detail page.
- `templates/asset.html`: rating + reasons, maintenance countdown, CV score bar, last inspection,
  condition notes, all fields, Back to dashboard.
- `templates/404.html`: friendly not-found page (unknown pages and unknown asset IDs).
- `app.py`: `/` and `/asset/<asset_id>`, using `load_assets()` + `rate_asset()` with today's date.
- `tests/test_app.py`: 10 tests with `load_assets` replaced by sample data.
- `README.md` and `DEMO.md`.

**Design decisions**
- Tile counts respect the type/network filters (not the risk filter), so a tile shows how many you'd get by clicking it.
- Filters are carried into the detail-page link, so "Back to dashboard" returns to the same filtered view.
- Unknown filter values in the URL are ignored rather than showing an error.
- Data is fetched from Google on every page load (about 0.3 s), so there's no cache to go stale during the live demo.

**Check results**
- `.venv/bin/pytest -v` → 56 passed (11 data source + 35 risk + 10 app)
- Live server: `/` 200, `/?network=Transmission` 200 (7 transmission assets), `/asset/OHL-3315` 200,
  `/asset/NOPE` 404, `/no-such-page` 404
- Visual check in Chrome: dashboard and detail page render correctly at desktop width. Phone width was
  not checked visually (the window resize didn't apply); the CSS has a ≤ 640px layout.
- Manual check by the user (filter, open an asset, live sheet edit): pending.

**Before the interview**
- Sample dates are fixed in the sheet, so ratings drift as days pass. Run `.venv/bin/python risk.py` the day
  before and adjust dates in the sheet if a rating group has emptied.
- On a different Mac with python.org Python, run "Install Certificates.command" once.
- After the demo's live edit, set POL-1150's CV score back to 88.

## Production hardening for Vercel (2026-10-05) ✅ verified locally · ⏳ not yet deployed

Prompted by an outside review (ChatGPT). All 9 reported issues were reproduced against the code, then fixed.
The multi-company SaaS scope it proposed was deliberately left out. The user will deploy themselves using `DEPLOY.md`.

**Fixed**
- Script injection: an asset ID like `x');alert(1);//` ran JavaScript through the row's inline `onclick`.
  Removed all inline JavaScript (rows are now clickable with a CSS-only stretched link), added a CSP that
  blocks scripts, and the parser rejects unsafe IDs.
- Slash IDs (`POL/9`) made dead links. IDs are now limited to letters, numbers, `.`, `-`, `_` (≤ 64 chars).
- A bad download could overwrite the last good backup. Now rejected downloads never touch the backup.
- A parse crash skipped the fallback. Now it falls back to the backup with the reason.
- UTC dates: "today" and "fetched at" now use `APP_TIMEZONE` (default America/Toronto). Vercel reserves `TZ`.
- BOM handling is consistent (parser and backup reader). Rows with extra unnamed values are skipped with a warning.
- An empty sheet now says "There are no assets to show yet", not "No assets match these filters".
- No authentication: HTTP Basic Auth via `APP_PASSWORD` / `APP_USERNAME`, which fails closed (503) on Vercel if unset.

**Vercel readiness**
- Backup goes to `/tmp` on Vercel. `data/backup.csv` ships as the read-only last resort; the bundled copy
  is labelled as such, not given a misleading file time.
- `requirements.txt` is runtime only (+ `tzdata`); `requirements-dev.txt` adds pytest; `.python-version` = 3.14;
  `vercel.json` excludes tests/notes; `.env.example`; `.gitignore` covers `.env` and `.vercel/`.
- `/healthz` endpoint; security headers; 2 MB / 5,000-row limits; failure reasons logged (no asset data).

**Check results (local)**
- `.venv/bin/pytest -q` → 98 passed (56 original + 42 new: data source, app/security/auth, config).
- Simulated Vercel (`VERCEL=1`) on port 5055: no credentials 401, wrong 401, correct 200; banner time matched
  Toronto; 16 assets, 0 inline scripts; detail 200; `/healthz` 200 without credentials; CSP header present;
  backup written to `/tmp`; `data/backup.csv` checksum unchanged.
- Simulated Google failure (bad `SHEET_ID`, no `/tmp` copy): 200 with "Showing the backup copy that ships with the app…".
- `VERCEL=1` with no password: 503 "Password not configured".
- Local server on 5001 auto-reloaded: 200, new links, CSP present.

**Not verified (needs the real deployment):** Vercel build with Python 3.14, Flask auto-detection, `/tmp`
writes, `vercel.json` exclusions, the HTTPS password prompt in a browser. Use the checklist in DEPLOY.md, Part 3.
