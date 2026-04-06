# Bursa Malaysia PN17/GN3 Monitor

Automated daily tracker for Bursa Malaysia's PN17 and GN3 distressed-company listings.
No local machine needed — runs entirely on **GitHub Actions**, free of charge.

---

## What the two files do

### `bursa_notifier.py` — the brain

This is the Python script that does all the actual work. Every time it runs, it goes through five stages:

**Stage 1 — Scrape Bursa Malaysia**
It visits the [Bursa PN17/GN3 page](https://www.bursamalaysia.com/bm/trade/trading_resources/listing_directory/pn17_and_gn3_companies) and extracts three things:
- The "List updated" date (e.g. `17 March 2026`)
- The direct PDF download link
- The full list of PN17 and GN3 company names

**Stage 2 — Check for changes**
It opens `last_run.json` (stored in the repo) and compares the scraped date and PDF link against the previous run. If both are identical, the script exits immediately — nothing to do.

**Stage 3 — Process new release** *(only runs when something changed)*
- Downloads the PDF and saves it to `pn17_gn3_pdfs/PN17_GN3_<date>.pdf`
- Overwrites `pn17_gn3_companies.csv` with the current company snapshot
- Appends new rows to `pn17_gn3_historical.csv` (skips if the date is already recorded)
- Appends one summary row to `summary-reportPN17.csv` with count and percentage of total listed companies

**Stage 4 — Send email**
Sends an HTML email to every address in `NOTIFY_EMAILS` containing:
- The "List updated" date
- A clickable link to download the PDF directly from Bursa Malaysia
- A formatted table of all current PN17 companies
- A formatted table of all current GN3 companies
- The PDF attached to the email

**Stage 5 — Save state**
Writes the new date and PDF link back to `last_run.json` so the next run has a baseline to compare against.

---

### `.github/workflows/bursa_pn17_monitor.yml` — the scheduler

This is the GitHub Actions workflow file. It is the automation layer that calls `bursa_notifier.py` on a schedule without you doing anything.

**When does it run?**
Every day at **10:00 AM Malaysia Time (MYT)**, which is `02:00 UTC`. You can also trigger it manually from the GitHub Actions tab at any time using the "Run workflow" button.

**What does it actually do, step by step?**

```
Step 1  Checkout the repo
        Pulls the latest version of all files, including last_run.json and
        the CSV files, so the script has the current state to work from.

Step 2  Set up Python 3.11
        Installs Python on the GitHub-hosted runner (a fresh Ubuntu machine
        that starts up, does its job, then disappears).

Step 3  Install dependencies
        Runs: pip install -r requirements.txt
        Installs requests, beautifulsoup4, pandas, pdfplumber, etc.

Step 4  Run the monitor
        Runs: python bursa_notifier.py
        This is where all the scraping, downloading, CSV updating, and
        emailing happens. The three email secrets are passed in as
        environment variables so the script can read them securely.

Step 5  Commit and push
        If any files changed (new PDF, updated CSVs, updated last_run.json),
        the workflow commits them back to the repo automatically under the
        name "github-actions[bot]". If nothing changed, this step is skipped
        (the git diff check prevents empty commits).
```

**Why does the workflow need `permissions: contents: write`?**
By default, GitHub Actions workflows are read-only. This permission allows Step 5 to push commits back to your repository.

---

## Repository structure

```
.
├── .github/
│   └── workflows/
│       └── bursa_pn17_monitor.yml   ← scheduler (runs daily at 10am MYT)
│
├── pn17_gn3_pdfs/                   ← all downloaded PDFs, one per release
│   └── PN17_GN3_17_March_2026.pdf
│
├── bursa_notifier.py                ← main script
├── requirements.txt                 ← Python dependencies
├── last_run.json                    ← stores last seen date + PDF link
│
├── pn17_gn3_companies.csv           ← current snapshot (overwritten each release)
├── pn17_gn3_historical.csv          ← full history, one row per company per release
└── summary-reportPN17.csv           ← one summary row per release
```

---

## CSV schemas

**`pn17_gn3_companies.csv`** — current snapshot, overwritten on each new release

| Column | Example |
|--------|---------|
| Company Name | Capital A Berhad |
| Type | PN17 |
| List Updated | 17 March 2026 |
| PDF Link | https://www.bursamalaysia.com/... |

**`pn17_gn3_historical.csv`** — full log, rows appended and never deleted

| Column | Example |
|--------|---------|
| Run Date | 2026-03-17 |
| List Updated | 17 March 2026 |
| Company Name | Capital A Berhad |
| Type | PN17 |
| PDF Link | https://www.bursamalaysia.com/... |

**`summary-reportPN17.csv`** — one row per Bursa release

| Column | Example |
|--------|---------|
| Report Date | 17 March 2026 |
| PN17_GN3_Count | 17 |
| Percentage_of_Total | 1.63% |
| Total_Listed_Companies | 1040 |
| Source File | Status_of_PN17_and_GN3_Companies.pdf |

> **Note:** `Total_Listed_Companies` and `Percentage_of_Total` are carried forward from the previous row because Bursa does not publish the total count on the PN17/GN3 page. Update this column manually when you know the current total, or leave it to accumulate from the last known figure.

---

## One-time setup

### Step 1 — Create your GitHub repository

Create a new repository on GitHub (public or private). Clone it locally, copy all these files in, and push.

```bash
git init
git add .
git commit -m "initial commit"
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
git push -u origin main
```

### Step 2 — Add your existing data files

If you already have historical data, push those files too:

```bash
git add pn17_gn3_companies.csv pn17_gn3_historical.csv summary-reportPN17.csv \
        last_run.json pn17_gn3_pdfs/
git commit -m "add existing historical data"
git push
```

### Step 3 — Add the three GitHub Secrets

Go to your repo → **Settings → Secrets and variables → Actions → New repository secret**

| Secret name | What to put in it |
|-------------|-------------------|
| `GMAIL_USER` | The Gmail address that will send the alerts, e.g. `yourname@gmail.com` |
| `GMAIL_APP_PASS` | A Gmail App Password — **not** your normal Gmail password (see below) |
| `NOTIFY_EMAILS` | Comma-separated list of who receives the alert, e.g. `you@gmail.com,colleague@gmail.com` |

**How to create a Gmail App Password:**
1. Your Google account must have 2-Step Verification turned on
2. Go to [https://myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
3. Create a new app password — name it anything (e.g. `BursaBot`)
4. Copy the 16-character password and paste it as the `GMAIL_APP_PASS` secret

### Step 4 — Enable Actions

Go to the **Actions** tab of your repository. If prompted, click "I understand my workflows, go ahead and enable them."

### Step 5 — Test manually

Actions tab → **Bursa PN17/GN3 Monitor** → **Run workflow** → **Run workflow**

Watch the logs in real time. A successful first run will show all five steps completing with green ticks.

---

## Changing the schedule

The workflow runs at `0 2 * * *` (UTC), which equals 10:00 AM MYT daily. To change it, edit the cron line in `.github/workflows/bursa_pn17_monitor.yml`:

```yaml
- cron: "0 2 * * *"   # daily at 10am MYT
```

Cron format: `minute  hour  day  month  weekday` (all in UTC).
Use [crontab.guru](https://crontab.guru) to build a custom schedule.

---

## Running locally (for testing)

```bash
pip install -r requirements.txt

# Set your secrets as environment variables
export GMAIL_USER="you@gmail.com"
export GMAIL_APP_PASS="xxxx xxxx xxxx xxxx"
export NOTIFY_EMAILS="you@gmail.com"

python bursa_notifier.py
```

To force a re-run even if there is no new release (useful for testing email), temporarily edit `last_run.json` and change the `list_updated` value to something old like `1 January 2000`.

---

## How the change detection works

`last_run.json` holds the last seen values:

```json
{
  "list_updated": "17 March 2026",
  "pdf_link": "https://www.bursamalaysia.com/sites/.../Status_of_PN17_and_GN3_Companies.pdf"
}
```

The script triggers a full update if **either** value changes. Bursa typically updates both at the same time (new date + new PDF URL), but checking both guards against edge cases where only one changes.

---

## Bugs fixed from original `bursa_notifier.py`

| Bug | Original | Fixed |
|-----|----------|-------|
| Linux-only date format | `strftime("%-d %B %Y")` crashes on Windows/macOS | `f"{now.day} {now.strftime('%B %Y')}"` |
| Wrong email MIME type | `MIMEMultipart("alternative")` cannot carry binary attachments | `MIMEMultipart("mixed")` |
| Unnecessary git history fetch | `fetch-depth: 0` downloads entire repo history | `fetch-depth: 1` (latest commit only) |
