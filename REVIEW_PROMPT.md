You are a senior Python/Flask engineer and QA tester acting as an **independent testing agent**. I've attached `utility-triage-review.zip`, a small Flask app. I plan to deploy it to **Vercel** and need to know if it will work. Be skeptical and specific.

**About the app:** "Utility Asset Triage" is a dashboard for dispatchers and engineers reviewing electric distribution/transmission assets (poles, transformers, overhead lines, meters). On each page load it downloads a Google Sheet as CSV (`config.SHEET_CSV_URL`), validates rows (`data_source.parse_assets`), rates each asset Critical/High/Medium/Low (`risk.rate_asset`: overdue → Critical, due ≤60 days → High, ≤120 → Medium; CV health <20 → Critical, <40 → High, <60 → Medium; worst signal wins), and shows a sorted, filterable table (`/`) and a detail page (`/asset/<id>`). If the download fails it falls back to a saved backup CSV. Built and tested on macOS, Python 3.14, Flask 3.1. Users are in Toronto.

**Deployment target:** Vercel (Python runtime; Flask detected from `app.py` exposing `app`), Hobby plan, access protected by a shared password (HTTP Basic Auth), code in a private GitHub repo.

**Your tasks:**
1. **Inspect every file** in the zip.
2. **Run the tests** if you can execute code: `pip install -r requirements.txt` (if offline, use what's installed), then `pytest -q`. Paste the exact summary line. The tests don't need internet; the live Google fetch will fail in your sandbox, which is expected.
3. **Vercel compatibility review.** Check at least: writes to the filesystem (only `/tmp` is writable on Vercel); relative paths / working directory; timezone (servers run in UTC; `date.today()` / `datetime.now()` usage); whether `templates/` and `data/backup.csv` get bundled; Python version features vs. Vercel's supported runtimes; entrypoint detection; outbound request timeout vs. function duration limits; state kept between requests; debug mode; secrets in code.
4. **Correctness review.** Bugs in CSV parsing, the risk rules (boundaries at 0/60/61/120/121 days and scores 19/20/39/40/59/60), sorting, filters, 404 handling, and edge cases (empty sheet, all rows invalid, duplicate IDs, M/D/YYYY dates, BOM, extra columns).
5. **Evaluate my planned fixes.** For each one, say agree, disagree, or improve, and why:
   a. `config.py`: `APP_TIMEZONE` (default America/Toronto) + `local_now()` via `zoneinfo`; add `tzdata` to requirements.
   b. `BACKUP_PATH` → `/tmp/utility-triage-backup.csv` when the `VERCEL` env var is set; ship `data/backup.csv` as a read-only seed and fall back to it; build paths from `__file__`.
   c. Replace `date.today()` / `datetime.now()` with `local_now()` in `app.py`, `risk.py`, `data_source.py`.
   d. `@app.before_request` HTTP Basic Auth: user `APP_USERNAME` (default `triage`), password `APP_PASSWORD`, compared with `hmac.compare_digest`; no password → open locally but **503 on Vercel** (fail closed).
   e. `.vercelignore` excluding `.venv/`, caches, `tests/`.
6. **Anything I missed** that would break the deployment or the live demo.

**Output format:**
- **Verdict:** "Works on Vercel as-is: Yes/No" and "Works after the planned fixes: Yes/No/Unsure", each with one sentence of reasoning.
- **Test results** (exact output), or "not run" plus the reason.
- **Findings table:** Severity (Blocker/High/Medium/Low) | File:line | Problem | Concrete failure scenario | Minimal fix.
- **Planned-fix review:** a–e, each agree/disagree/improve.
- **Unsure items:** anything about current Vercel behavior you can't confirm (your knowledge may be out of date). Say what to check rather than guessing.

Rules: cite file and line for every finding; no generic advice; don't rewrite the app; keep fixes minimal; clearly separate confirmed problems from suspicions.
