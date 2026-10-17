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

Vercel's free Hobby plan is for non-commercial use. Move to Pro before charging customers.

## Files

| File | Purpose |
|---|---|
| `index.html` | The dashboard (HTML, CSS and JS in one file) |
| `data.json` | Generated data. Committed by the workflow; don't edit by hand |
| `analytics.json` | Site traffic snapshot (only exists once the setup above is done) |
| `vercel.json` | Cache and deploy-skip rules for Vercel |
