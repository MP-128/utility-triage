# Deploying Utility Asset Triage to Vercel

This guide takes you from the folder on your Mac to a password-protected website. Allow about 15 minutes.
You'll do three things:

1. Put the code in a **private GitHub repository** (Vercel deploys from GitHub).
2. **Import** that repository on vercel.com and set your password.
3. **Check** the live site.

> **Before you start:** the app's tests should pass on your Mac:
> `cd ~/Desktop/utility-triage && .venv/bin/pytest -q` → `98 passed`.

---

## Part 1: Put the code on GitHub (private)

Open **Terminal** and run these commands one at a time.

**1. One-time Git setup** (skip if you've done it before). Use the email on your GitHub account:

```bash
git config --global user.name "Your Name"
git config --global user.email "you@example.com"
```

**2. Go to the project and create the repository history:**

```bash
cd ~/Desktop/utility-triage
git init -b main
git add .
git status
```

Check the list `git status` prints. You should see files like `app.py`, `vercel.json`, `templates/` and
`data/backup.csv`. You should **not** see `.venv/` or `.env`. The `.gitignore` file keeps those out.

**3. Save the first version (a "commit"):**

```bash
git commit -m "Utility Asset Triage: production-ready for Vercel"
```

**4. Create a private repository on GitHub and upload the code:**

```bash
gh repo create utility-triage --private --source . --push
```

It prints a link like `https://github.com/<your-username>/utility-triage`. Open it to check that the files
are there and the repository is labelled **Private**.

> No `gh`? In a browser, go to github.com → **New repository** → name `utility-triage` → **Private** →
> **Create repository** (no README). Then run the two commands GitHub shows under
> "…or push an existing repository from the command line".

---

## Part 2: Deploy on vercel.com

**1. Sign in.** Go to **vercel.com** → **Sign Up** (or **Log In**) → **Continue with GitHub**. The free
**Hobby** plan is enough for a demo. Vercel's Hobby plan is for personal, non-commercial use.

**2. Start a project.** On your Vercel dashboard click **Add New…** → **Project**.

**3. Import the repository.** Under **Import Git Repository**, find `utility-triage` and click **Import**.
- Don't see it? Click **Adjust GitHub App Permissions** (or "Configure GitHub App"), give Vercel access
  to the `utility-triage` repository, then come back.

**4. Check the settings** on the **Configure Project** screen:

| Setting | What it should be |
|---|---|
| Project Name | `utility-triage` (this becomes part of your web address) |
| Framework Preset | **Flask** (Vercel detects it from `app.py`). If it shows "Other", that's also fine. |
| Root Directory | `./` (leave as is) |
| Build and Output Settings | leave everything as is |

**5. Add your password.** Open **Environment Variables** and add:

| Key | Value | Required? |
|---|---|---|
| `APP_PASSWORD` | a password you choose (long and not reused elsewhere) | **Yes**. Without it, the site shows "Password not configured" |
| `APP_USERNAME` | the username people type | Optional (default: `triage`) |
| `APP_TIMEZONE` | e.g. `America/Toronto` | Optional (default: `America/Toronto`) |
| `SHEET_ID` | the ID of a different Google Sheet | Optional (default: the demo sheet) |

Type each **Key** and **Value**, then click **Add**. Don't add `TZ`: Vercel reserves it. The app handles the
timezone itself with `APP_TIMEZONE`.

**6. Click Deploy.** The first build takes about a minute. When you see the success screen, click
**Continue to Dashboard**. Your address is listed under **Domains**, e.g. `https://utility-triage.vercel.app`
(Vercel may add extra letters if the name is taken).

---

## Part 3: Check the live site

Work through this list on the address from step 6:

- [ ] `https://<your-address>/healthz` shows `{"status":"ok"}` with no password prompt.
- [ ] `https://<your-address>/` asks for a username and password. A wrong password is refused.
- [ ] With `triage` (or your `APP_USERNAME`) and your password, the dashboard opens.
- [ ] The banner says **"Live from Google Sheet · fetched HH:MM"** and the time matches the clock in Toronto.
- [ ] The tiles show the count per rating, and the table lists all 16 assets, most urgent first.
- [ ] A filter (e.g. Network = Transmission) works, and clicking a row opens that asset's detail page.
- [ ] **Live edit:** in the Google Sheet, change POL-1150's `cv_health_score` to `15`. Click **Refresh data**
      and POL-1150 is now Critical. Change it back to `88` afterwards.
- [ ] On your phone, the page is readable and the table scrolls sideways.

---

## Everyday tasks

**Update the site after changing code:**

```bash
cd ~/Desktop/utility-triage
.venv/bin/pytest -q
git add .
git commit -m "Describe the change"
git push
```

Vercel redeploys automatically on every push to `main`.

**Change the password:** Vercel → your project → **Settings** → **Environment Variables** → edit
`APP_PASSWORD` → **Save**. Then **Deployments** → the top deployment's **⋯** menu → **Redeploy**.
New settings only apply after a redeploy.

**Roll back a bad deployment:** **Deployments** → find the last good one → **⋯** →
**Instant Rollback** (or **Promote to Production**). The site switches back within seconds. Fix the code,
then push again.

**Take the site offline:** **Settings** → **General** → scroll to the bottom → **Delete Project**.
Your GitHub repository is not affected.

---

## Troubleshooting

| What you see | Why | Fix |
|---|---|---|
| "Password not configured: set APP_PASSWORD…" (503) | `APP_PASSWORD` is missing | Add it (Part 2, step 5), then **Redeploy** |
| A **Vercel** login page instead of the app's password prompt | You opened a preview address; Vercel protects those by default | Use the production address listed under **Domains** |
| Orange banner: "Showing backup copy… isn't shared as 'Anyone with the link'" | The Google Sheet isn't link-shared | Sheet → **Share** → General access → **Anyone with the link** → Viewer |
| Orange banner: "…Google couldn't find the sheet (HTTP 404)" | Wrong `SHEET_ID` | Fix or remove the `SHEET_ID` variable, then **Redeploy** |
| Orange banner: "…the latest version of the sheet was rejected" | The sheet's columns were changed, or every row is invalid | Read the "Latest sheet: …" warnings under the banner and fix those rows; the last good data stays visible meanwhile |
| Build fails mentioning Python | Python version | The `.python-version` file pins 3.14. If Vercel rejects it, change the file to `3.13`, commit and push |
| Build log or **Logs** tab shows an error | Code problem | Vercel → project → **Logs**. Messages say why the sheet wasn't used, never the asset data. Roll back if needed |

## What runs where

- **Vercel** runs `app.py` as a serverless function. It installs only `requirements.txt` (Flask, tzdata);
  test tools stay local in `requirements-dev.txt`. `vercel.json` keeps tests and notes out of the upload.
- On every page load the app downloads the sheet, validates it and rates each asset. A good download is
  cached in `/tmp` on that server. If Google can't be reached, the app shows the newest cached copy, or
  failing that, `data/backup.csv`, which ships with the code.
- The page has no JavaScript, and a Content-Security-Policy header stops any script from running.
- The password check is HTTP Basic Auth over HTTPS (Vercel provides HTTPS automatically). That's fine for a
  demo, but it isn't a substitute for individual user accounts.
