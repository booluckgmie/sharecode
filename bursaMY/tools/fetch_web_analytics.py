#!/usr/bin/env python3
"""
Pull Vercel Web Analytics for the dashboard project into bursaMY/dashboard/analytics.json,
which the "Site analytics" section of the dashboard reads. Run daily by the monitor workflow.

Needs (environment):
  VERCEL_TOKEN        a Vercel access token that can read the team's analytics   (secret)
  VERCEL_PROJECT_ID   project id or name, e.g. prj_...
  VERCEL_TEAM_ID      team id, e.g. team_...   (omit for a personal account)

API: GET https://api.vercel.com/v1/query/web-analytics/visits/aggregate
Never fails the workflow: problems are written to analytics.json as status "unavailable"
(the dashboard then hides the section), and a previous good file is kept, marked stale.
The token is never printed or written to disk.
"""
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "dashboard" / "analytics.json"
API = "https://api.vercel.com/v1/query/web-analytics/visits/aggregate"
DAYS = 30
TOP_N = 8
BREAKDOWNS = {
    "top_pages": "requestPath",
    "referrers": "referrerHostname",
    "countries": "country",
    "devices": "deviceType",
    "browsers": "browserName",
}


def query(token: str, params: dict) -> dict:
    url = API + "?" + urllib.parse.urlencode({k: v for k, v in params.items() if v not in (None, "")})
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        try:
            msg = json.load(e).get("error", {}).get("message", "")
        except Exception:
            msg = ""
        raise RuntimeError(f"HTTP {e.code} from Vercel{': ' + msg[:160] if msg else ''}") from None
    except urllib.error.URLError as e:
        raise RuntimeError(f"network error: {e.reason}") from None


def _num(row: dict, *keys) -> int:
    for k in keys:
        v = row.get(k)
        if isinstance(v, (int, float)):
            return int(v)
        if isinstance(v, str) and v.replace(".", "", 1).isdigit():
            return int(float(v))
    return 0


def _rows(resp: dict) -> list:
    data = resp.get("data") if isinstance(resp, dict) else None
    return data if isinstance(data, list) else []


def collect(token: str, project: str, team: str, today=None, fetch=query) -> dict:
    today = today or datetime.now(timezone.utc).date()
    since = today - timedelta(days=DAYS - 1)
    base = {
        "projectId": project,
        "teamId": team,
        "since": since.isoformat(),
        "until": today.isoformat(),
        "filter": "environment eq 'production'",
    }

    # daily series, with missing days filled so the chart has one point per day
    by_day = {}
    for r in _rows(fetch(token, {**base, "by": "day"})):
        stamp = str(r.get("timestamp") or r.get("day") or r.get("date") or "")[:10]
        if len(stamp) == 10:
            by_day[stamp] = {"pageviews": _num(r, "pageviews", "count", "visits"), "visitors": _num(r, "visitors", "uniqueVisitors")}
    daily = []
    for i in range(DAYS):
        d = (since + timedelta(days=i)).isoformat()
        v = by_day.get(d, {"pageviews": 0, "visitors": 0})
        daily.append({"date": d, **v})

    out = {"status": "ok", "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "period": {"since": since.isoformat(), "until": today.isoformat(), "days": DAYS}, "daily": daily}
    total = sum(d["pageviews"] for d in daily)
    peak = max(daily, key=lambda d: d["pageviews"])
    out["totals"] = {
        "pageviews": total,
        "avg_daily_visitors": round(sum(d["visitors"] for d in daily) / DAYS, 1),
        "peak_day": {"date": peak["date"], "pageviews": peak["pageviews"]} if peak["pageviews"] else None,
    }

    for name, dim in BREAKDOWNS.items():
        items = []
        for r in _rows(fetch(token, {**base, "by": dim, "limit": TOP_N})):
            pv = _num(r, "pageviews", "count", "visits")
            if pv > 0:
                label = r.get(dim)
                items.append({"label": label if isinstance(label, str) and label else None, "pageviews": pv, "visitors": _num(r, "visitors", "uniqueVisitors")})
        items.sort(key=lambda i: -i["pageviews"])
        out[name] = items[:TOP_N]
    return out


def write(obj: dict):
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def fail(reason: str):
    """Record the problem; keep the last good data (marked stale) so the section doesn't vanish."""
    print(f"[analytics] unavailable: {reason}")
    prev = None
    try:
        prev = json.loads(OUT.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass
    if prev and prev.get("status") == "ok":
        prev["stale"] = True
        prev["last_error"] = reason
        write(prev)
    else:
        write({"status": "unavailable", "reason": reason,
               "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")})


def main(fetch=query) -> int:
    token = os.environ.get("VERCEL_TOKEN", "").strip()
    project = os.environ.get("VERCEL_PROJECT_ID", "").strip()
    team = os.environ.get("VERCEL_TEAM_ID", "").strip()
    if not token or not project:
        fail("VERCEL_TOKEN or VERCEL_PROJECT_ID is not set")
        return 0
    try:
        out = collect(token, project, team, fetch=fetch)
    except Exception as e:  # any API or parsing problem
        fail(str(e).replace(token, "***"))
        return 0
    write(out)
    print(f"[analytics] {out['totals']['pageviews']} page views in the last {DAYS} days -> {OUT.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
