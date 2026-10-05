# 2-minute demo script

**Before you start:** run `.venv/bin/python app.py`, open http://127.0.0.1:5001, and open the
[Utility Asset Health](https://docs.google.com/spreadsheets/d/1LQmlWcPRNL-WhnyOXdU0b7FXrfNDpoCiKjQhjLT3nzU/edit)
sheet in a second tab. Check the banner is green ("Live from Google Sheet").

---

**1. The dashboard (≈30 s)**
> "This is what a supervisor sees first thing in the morning. It reads our asset health sheet in Google
> Drive live (see the banner and fetch time). The tiles count assets by risk: 4 Critical, 4 High, 4 Medium, 4 Low.
> The table is sorted most urgent first. At the top, meter MTR-4481 is overdue by 30 days. Every row says
> *why* it's rated that way, so nobody has to trust a black box."

Point out OHL-3315: maintenance isn't due for 210 days, but it's **Critical** because the camera scored it 14/100.
> "Two signals, and the worse one wins: the calendar *or* what the inspection imagery shows."

**2. Filter (≈15 s)**
Choose **Network → Transmission**, click **Apply** (or click the **Critical** tile).
> "A transmission engineer only cares about their network. Filters combine, and Clear resets them."

**3. Asset detail (≈20 s)**
Click **OHL-3315**.
> "Here's everything for one asset: why it's Critical, the maintenance countdown, the CV score,
> the last inspection, and the field crew's notes: broken conductor strands near the clamp."

Click **Back to dashboard** (your filter is kept).

**4. Live moment (≈40 s)**
Switch to the Google Sheet tab. Find **POL-1150** (currently Low, CV 88). Change its `cv_health_score` to **15**
and press Enter. Switch back and click **Refresh data**.
> "An inspector just uploaded new imagery and the pole scored 15. One refresh and it jumps from Low
> to Critical, straight to the top of the list. No deploy, no database: the sheet the team already uses
> is the source of truth."

(If it hasn't changed yet, wait 2–3 seconds and click Refresh again; Google takes a moment to save.)
Afterwards, set POL-1150 back to **88**.

**5. Next steps (≈15 s)**
> "Next I'd move to the Google Sheets API for private sheets, add a map view, score CV images directly,
> and let a dispatcher turn a Critical asset into a work order with one click."

---

**Backup plan:** if the Wi-Fi drops, the app automatically shows the last downloaded copy with an orange
"Showing backup copy" banner. Say: "It also degrades gracefully: here it's showing the backup and telling us why."
