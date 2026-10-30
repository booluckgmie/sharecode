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

## Failure alerts

Bursa's Cloudflare blocks some runner IPs, so roughly four runs in ten fail to scrape, and the next
scheduled run usually recovers (the longest gap between successes seen was about 29 hours). A failed
scrape therefore does not turn the run red: the workflow prints a warning and keeps going.
`tools/check_scrape_freshness.py` fails the run (GitHub emails you) only when no scrape has succeeded
for **36 hours**, and the dashboard shows "Data may be out of date" under the same rule. Until then
the page shows "Checked N hours ago". Change `LIMIT_HOURS` in the script and the `36` in `index.html`
together if you want a different limit. Tests: `python3 bursaMY/tools/test_check_scrape_freshness.py`.

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

## Site analytics (Vercel Web Analytics)

`index.html` loads Vercel's cookieless Web Analytics script, and the page has a **Site analytics**
section at the bottom (page views and visitors per day, top pages, referrers, countries, devices,
browsers). The section stays hidden until it has real data.

**One-time setup (cannot be done from code):**

1. **Enable Web Analytics** for the project: Vercel dashboard > project > *Analytics* tab > *Enable*
   (or `vercel project web-analytics enable <project>`). Do this for every Vercel project you want
   measured. Until it is enabled, the script request is a harmless 404.
2. **Create a token** that can read the team's analytics: Vercel > Account Settings > *Tokens*.
3. **Add it as a GitHub secret** named `VERCEL_TOKEN` (repo > Settings > Secrets and variables >
   Actions). The project and team ids are already set in the workflow.

After that the daily workflow runs `bursaMY/tools/fetch_web_analytics.py`, which reads
`GET /v1/query/web-analytics/visits/aggregate` for the last 30 days and commits
`dashboard/analytics.json`. If the token is missing or the API call fails, the section is hidden
(or shows the last good numbers with a "last updated" warning); the monitor run is never failed.
`python3 bursaMY/tools/test_web_analytics.py` runs the offline tests.

The numbers are aggregated, with no cookies and no personal data. The section is public if the
site is public. To keep it private, remove the `VERCEL_TOKEN` secret (no `analytics.json` is
produced) or password-protect the deployment in Vercel.

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
| `analytics.json` | Site traffic snapshot (only exists once the setup above is done) |
| `vercel.json` | Cache and deploy-skip rules for Vercel |
