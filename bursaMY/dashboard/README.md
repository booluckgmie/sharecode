# PN17 Watch dashboard

Static page (`index.html`) that reads one file, `data.json`. No backend, no database.

## How the data stays current

1. `.github/workflows/bursa_pn17_monitor.yml` runs daily (02:00 and 06:00 UTC) and on demand.
2. `bursa_notifier.py` scrapes Bursa and updates the CSVs.
3. `build_dashboard_data.py` rebuilds `dashboard/data.json` from the CSVs, **every run**, even
   when the scrape failed. `data.json` records `last_check.status` and `last_success_at`, so the
   page shows "Last check failed" or "Last checked N days ago" instead of looking fresh.
4. The workflow commits `data.json` to `master`. Vercel redeploys from that commit.
5. If the scrape failed, the last step turns the run red so GitHub emails you.

`data.json` holds everything the page needs: headline numbers, the per-list time series,
entries/exits, per-company history, and every published snapshot (`snapshots`). The CSVs stay
the source of truth; `data.json` is rebuilt from them and can be deleted and regenerated.

## Stage and trading status

The scraper reads both from Bursa's table (columns are located from the header text) and keeps
the raw `<table>` HTML in `bursaMY/raw/` so it can be re-parsed if the parser changes. Run
`python3 bursaMY/test_parser.py` to check the parser against the real table saved there.

Bursa used four stage columns in the PDF lists (to Nov 2025) and three since 2026. `data.json`
puts both on the three-stage scale:

| Stage | Label | Bursa wording |
|---|---|---|
| 1 | Pending submission of regularisation plan | "Pending submission of Regularisation Plan to authorities" (PDF: "Pending submission to authorities") |
| 2 | Regularisation plan under review | "Regularisation Plans under authorities' review" (PDF: "Submitted, pending authorities' approval") |
| 3 | Plan approved, pending upliftment | "Regularisation Plan approved by authorities, pending upliftment from PN17 / GN3" (PDF: "Approval obtained, pending implementation" and "Implemented, pending compliance") |

Folding the two old late stages into stage 3 is an interpretation. The original wording stays in
the CSVs. A run on an unchanged list fills in or corrects stage/trading for the current snapshot
(no email, no duplicate rows). Companies that left the list keep their last known value, shown with
an "as of" date.

## Run locally

```bash
python3 bursaMY/build_dashboard_data.py        # CSVs -> dashboard/data.json
python3 -m http.server -d bursaMY/dashboard 8000
# open http://localhost:8000
```

## Deploy on Vercel

1. Import the GitHub repo in Vercel.
2. **Root Directory:** `bursaMY/dashboard`. **Framework Preset:** Other. Leave build command and
   output directory empty.
3. Production branch: `master`.

`vercel.json` already sets `Cache-Control: max-age=0, must-revalidate` on `data.json`, and an
`ignoreCommand` so other workflows in this repo (gold, weather, ...) don't trigger redeploys: a
deploy only happens when something under `bursaMY/dashboard/` changed.

The repo root also has a `vercel.json` that serves `bursaMY/dashboard` as a static site, so a
Vercel project that still has the default Root Directory (the repo root) deploys the dashboard
instead of failing with "No python entrypoint found". Setting Root Directory to
`bursaMY/dashboard` is the cleaner setup; when it is set, the root `vercel.json` is ignored.

Vercel's free Hobby plan is for non-commercial use. Move to Pro before charging customers.

## Files

| File | Purpose |
|---|---|
| `index.html` | The dashboard (HTML, CSS and JS in one file) |
| `data.json` | Generated data. Committed by the workflow; don't edit by hand |
| `vercel.json` | Cache and deploy-skip rules for Vercel |
