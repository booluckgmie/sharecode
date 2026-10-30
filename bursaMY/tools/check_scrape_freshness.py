#!/usr/bin/env python3
"""
Decide whether a failed scrape should turn the monitor run red.

A single blocked scrape is normal (Bursa's Cloudflare blocks some runner IPs) and the next
scheduled run recovers. So after a failed scrape this exits 1 (run goes red, GitHub emails)
only when no scrape has succeeded for LIMIT_HOURS; otherwise it prints a warning annotation
and exits 0. The dashboard uses the same limit for its "may be out of date" label.

Reads last_success_at from bursaMY/dashboard/data.json (kept across failed runs by
build_dashboard_data.py). Longest gap between successes seen in practice: about 29 hours.
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "dashboard" / "data.json"
LIMIT_HOURS = 36


def hours_since(stamp, now=None):
    try:
        t = datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None
    return ((now or datetime.now(timezone.utc)) - t).total_seconds() / 3600


def evaluate(data, now=None, limit=LIMIT_HOURS):
    """Return (exit_code, annotation) for a run whose scrape just failed."""
    age = hours_since((data or {}).get("last_success_at"), now)
    if age is None:
        return 1, "::error::Bursa scrape failed and there is no record of a successful scrape. The dashboard may be empty or out of date."
    if age > limit:
        return 1, (f"::error::Bursa scrape has not succeeded for {age:.0f} hours (limit {limit}). "
                   "The dashboard is showing old data; check whether Bursa or Cloudflare changed something.")
    return 0, (f"::warning::Bursa scrape failed on this run (usually a Cloudflare block), but the last success was "
               f"{age:.0f} hours ago, so the run stays green. The next scheduled run retries.")


def main(now=None):
    try:
        data = json.loads(DATA.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = None
    code, message = evaluate(data, now)
    print(message)
    return code


if __name__ == "__main__":
    sys.exit(main())
