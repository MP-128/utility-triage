# Build prompt: Utility Asset Triage (3 phases)

> **How to use:** open a new Claude Code window in `~/Desktop/utility-triage` and type:
> `Follow the instructions in PROMPT.md`

---

## 1. Who I am and how to work with me

I have limited coding experience and I'm preparing for a two-hour vibe-coding interview. Build a **working prototype** (real data, really runs, not a mockup) in `~/Desktop/utility-triage` in **three phases**.

After each phase:
1. Run that phase's checks and show me the results.
2. Explain in plain language what each new file does and why it exists.
3. Append an entry to `PROGRESS.md` covering what was built, the check results, and notes for the next phase.
4. **STOP and wait for me to confirm** before starting the next phase.

Rules:
- Use `.venv/bin/python` and `.venv/bin/pytest` (the virtual environment already exists with Flask and pytest). Don't add other packages; use the Python standard library (`urllib`, `csv`, `datetime`) for everything else.
- The app runs on **port 5001**. Port 5000 is taken by macOS AirPlay Receiver. That only matters for the port number and has nothing to do with the data.
- Keep the app runnable at the end of every phase.
- If you lose track (for example, after a long conversation), re-read `PROMPT.md` and `PROGRESS.md`.

## 2. Product summary

- **Users:** dispatchers and engineering teams reviewing the health of their assets.
- **Assets:** electric **distribution and transmission** equipment: poles, transformers, overhead lines and meters.
- **Data source:** a **Google Sheet in Google Drive** that records asset health. The app reads it live.
- **What makes an asset urgent:** it needs maintenance within about 1–2 months, either because its scheduled maintenance date is near (or past) or because its computer-vision (CV) health rating is poor.
- **Demo goal (2 minutes):** a supervisor or engineer opens the dashboard and sees each asset's current state, how long until its scheduled maintenance, and its current risk rating, with the most urgent assets first.

**Already done (Stage 0):** `.venv/`, `app.py` (a "hello" page on port 5001), `requirements.txt`, `.gitignore`.

## 3. Contracts (follow exactly so all phases fit together)

**Google Sheet columns** (row 1 is the header):
`asset_id, asset_type, network, location, last_inspection_date, next_maintenance_date, cv_health_score, condition_notes`
- `asset_type` is one of: `Pole`, `Transformer`, `Overhead Line`, `Meter`
- `network` is one of: `Distribution`, `Transmission`
- Dates are `YYYY-MM-DD`; `cv_health_score` is an integer from 0 to 100 (100 = perfect health)

**`config.py`**
- `SHEET_ID` (the `SHEET_ID` environment variable overrides it if set)
- `SHEET_CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"`
- `BACKUP_PATH = "data/backup.csv"`

**`data_source.py`**
- `parse_assets(csv_text) -> (assets, warnings)`: returns a list of dicts using the column names above. Dates become `datetime.date` and the score becomes `int`. Invalid rows (missing field, bad date, score outside 0–100, unknown type or network) are skipped, and a readable warning string is added for each.
- `load_assets() -> (assets, source_info)` where `source_info = {"mode": "live" | "backup" | "none", "fetched_at": "HH:MM", "message": str, "warnings": [str]}`.
  - Fetch `SHEET_CSV_URL` with a 10-second timeout. On success, save the text to `BACKUP_PATH`.
  - If the fetch fails, or Google returns an HTML page instead of CSV (meaning the sheet isn't shared publicly), fall back to `BACKUP_PATH` and explain why in `message`.
  - If there's no backup either, return `[]` with mode `"none"`. **This function never raises.**
- Running `python data_source.py` prints a short summary.

**`risk.py`**
- `RATINGS = ["Critical", "High", "Medium", "Low"]` (most to least severe)
- `days_until_maintenance(asset, today) -> int` (negative means overdue)
- `rate_asset(asset, today) -> (rating, reasons)`
  - Time signal: overdue (< 0 days) → Critical; ≤ 60 days → High; ≤ 120 days → Medium; otherwise Low
  - CV signal: score < 20 (very poor) → Critical; < 40 (poor) → High; < 60 (fair) → Medium; otherwise Low
  - **The more severe of the two signals wins.** `reasons` lists every signal that is not Low, e.g. `"Maintenance overdue by 5 days"`, `"Maintenance due in 23 days"`, `"CV health 31/100 (poor)"`. If both signals are Low, use `["No issues: maintenance in 200 days, CV health 85/100"]`.

**Routes in `app.py`**
- `/` is the dashboard, with optional query params `type`, `network`, `risk`
- `/asset/<asset_id>` is the detail page
- Unknown pages and unknown assets show a friendly 404 page

---

## 4. Phase 1: Google Sheet + data loader

*Purpose: get real data flowing from my Google Drive into the app.*

1. Create a Google Sheet named **"Utility Asset Health"** in my Google Drive using the Google Drive connector (`create_file` with CSV text content and `contentMimeType: text/csv`, which converts automatically to a Google Sheet). Include about 15 realistic rows that:
   - cover **all four ratings** (some overdue, some due within 60 days, some within 61–120 days, some healthy; plus some with poor CV scores but distant maintenance dates),
   - include all four asset types and both networks,
   - use dates relative to **today**, and have useful `condition_notes` (e.g. "Crossarm cracked, woodpecker damage at 12 ft").

   If the Google Drive connector isn't available, write the same data to `data/sample_assets.csv` and walk me through importing it (Google Sheets → File → Import → Upload).
2. Walk me step by step through making the sheet readable by the app: **Share → General access → "Anyone with the link" → Viewer → Done**, then ask me to paste the sheet's link. Extract the `SHEET_ID` from it (the part between `/d/` and `/edit`).
3. Write `config.py` and `data_source.py` following the contracts.
4. Write `tests/test_data_source.py` (no network needed) covering a good row, a missing field, a bad date, an out-of-range score, and an HTML-instead-of-CSV response.

**Checks:**
- `.venv/bin/pytest -v` is all green
- `.venv/bin/python data_source.py` prints "N assets loaded (live from Google Sheet)" plus one example asset
- `data/backup.csv` exists
- Record the `SHEET_ID` and sheet link in `PROGRESS.md`

**→ STOP and wait for my confirmation.**

---

## 5. Phase 2: Risk rules + tests

*Purpose: the core triage logic, kept separate from the web pages so it's easy to test, explain and change.*

1. Write `risk.py` following the contract.
2. Write `tests/test_risk.py`. Always pass a fixed `today` so the results never change. Cover:
   - days until maintenance: −1, 0, 60, 61, 120, 121
   - CV scores: 19, 20, 39, 40, 59, 60
   - worst signal wins (e.g. due in 200 days but CV 15 → Critical)
   - the wording of the reasons

**Checks:**
- `.venv/bin/pytest -v` is all green
- Print a table of every live asset (from `load_assets()`) with its days until maintenance, CV score, rating and reasons, and confirm that all four ratings appear. If one is missing, tell me which rows in the sheet to change.

**→ STOP and wait for my confirmation.**

---

## 6. Phase 3: Dashboard, filters, detail page, demo prep

*Purpose: the screens the supervisor and engineers actually use, plus everything needed for a smooth demo.*

1. **Templates** (Jinja, in `templates/`):
   - `base.html`: shared layout and inline CSS. Use a clear color per rating (Critical = red, High = orange, Medium = yellow, Low = green), with the text label always shown next to the color. It must be readable at phone width; the table may scroll sideways inside its own box.
   - `dashboard.html`:
     - a data-source banner ("Live from Google Sheet · fetched 14:32" or "Offline: showing backup copy" plus the reason) and any skipped-row warnings
     - **count tiles** per rating (clicking a tile filters to that rating)
     - a **filter form** (GET) for asset type, network and risk, with a "Clear" link
     - a **table** sorted by rating severity, then by days until maintenance: Asset ID, Type, Network, Location, CV health, Next maintenance, Days remaining ("Overdue 5 days" / "23 days"), Risk badge + reasons. Each row links to its detail page
     - a "Refresh data" link
   - `asset.html`: every field, condition notes, last inspection date, maintenance countdown, CV score, rating and all reasons, and a "Back to dashboard" link.
   - `404.html`: a friendly message and a link back.
2. **Update `app.py`** to use `load_assets()` and `rate_asset()` with today's date. Keep `app.run(debug=True, port=5001)`.
3. **`tests/test_app.py`** using Flask's test client, with `load_assets` replaced by fixed sample data (no network): `/` → 200, `?type=Transformer` shows only transformers, `/asset/<id>` → 200, an unknown asset → 404.
4. **`README.md`**: what the app does, setup and run commands, how the Google Sheet connection works (and the offline backup), the risk rules table, and next steps (private sheet via OAuth / Google Sheets API, map view, ingesting CV images directly, creating work orders, user accounts).
5. **`DEMO.md`**: a 2-minute demo script:
   1. open the dashboard and point out the tiles and the most urgent asset
   2. filter (e.g. Transmission only)
   3. open one asset's detail page
   4. **live moment:** change an asset's CV score to 15 in the Google Sheet, click "Refresh data", and it jumps to Critical
   5. one sentence on next steps

**Checks:**
- `.venv/bin/pytest -v` is all green
- Start the server in the background, `curl` `/`, `/?network=Transmission`, one `/asset/<id>`, and `/asset/NOPE`, and show the status codes
- Ask me to open **http://127.0.0.1:5001**, try a filter, open an asset, and do the live sheet edit

**→ STOP with a final summary:** what was built, how to start the app (`cd ~/Desktop/utility-triage && .venv/bin/python app.py`), and anything I should re-check before the interview (sample dates are relative to today, so the ratings change as days pass).
