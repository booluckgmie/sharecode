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
