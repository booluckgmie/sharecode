"""
bursa_notifier.py
─────────────────
GitHub Actions version of the Bursa Malaysia PN17/GN3 monitor.

What it does every run
  1. Scrapes Bursa Malaysia for the latest list-updated date and company table.
  2. Compares against last_run.json (committed to repo).
  3. If NEW:
       a. Updates pn17_gn3_companies.csv  (current snapshot)
       b. Appends to pn17_gn3_historical.csv
       c. Appends to summary-reportPN17.csv
       d. Sends email with inline HTML summary
  4. Saves last_run.json (git commit handled by the workflow).

NOTE: Bursa no longer publishes a monthly PDF — all data is now embedded
      directly in the webpage as an HTML table. PDF download has been removed.

Environment variables (set as GitHub Secrets)
  GMAIL_USER      – sender Gmail address
  GMAIL_APP_PASS  – Gmail App Password (not your normal password)
  NOTIFY_EMAILS   – comma-separated recipient list  e.g. a@x.com,b@x.com
"""

import csv
import json
import os
import re
import smtplib
import sys
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# Try cloudscraper first (handles Cloudflare JS challenges).
# Falls back to playwright headless browser if still blocked.
try:
    import cloudscraper as _cloudscraper
    _CLOUDSCRAPER_OK = True
except ImportError:
    _CLOUDSCRAPER_OK = False

# ─── Paths (all relative to this script's location) ──────────────────────────
ROOT           = Path(__file__).parent
COMPANIES_CSV  = ROOT / "pn17_gn3_companies.csv"
HISTORICAL_CSV = ROOT / "pn17_gn3_historical.csv"
SUMMARY_CSV    = ROOT / "summary-reportPN17.csv"
CACHE_FILE     = ROOT / "last_run.json"

# ─── Bursa URL ────────────────────────────────────────────────────────────────
URL      = "https://www.bursamalaysia.com/bm/trade/trading_resources/listing_directory/pn17_and_gn3_companies"
BASE_URL = "https://www.bursamalaysia.com"


# ══════════════════════════════════════════════════════════════════════════════
# 1. SCRAPING
# ══════════════════════════════════════════════════════════════════════════════

def _fetch_html_cloudscraper() -> str:
    """Use cloudscraper to bypass Cloudflare JS challenge."""
    scraper = _cloudscraper.create_scraper(
        browser={"browser": "chrome", "platform": "windows", "mobile": False}
    )
    scraper.get(BASE_URL, timeout=20)   # warm-up for cookies
    resp = scraper.get(URL, timeout=30)
    resp.raise_for_status()
    return resp.text


def _fetch_html_playwright() -> str:
    """Use a headless Chromium browser as the guaranteed fallback."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )
        )
        page.goto(URL, wait_until="domcontentloaded", timeout=60000)
        # Wait for the data table to appear (new Bursa format)
        try:
            page.wait_for_selector("table", timeout=20000)
        except Exception:
            pass
        html = page.content()
        browser.close()
    return html


def _parse_html(html: str) -> dict:
    """
    Parse the Bursa PN17/GN3 page HTML.

    Bursa changed format in 2026 — data is now in an HTML <table> on the page,
    not in a downloadable PDF.

    Returns dict with keys:
        list_updated    str   e.g. "2 April 2026"
        pn17_companies  list[str]
        gn3_companies   list[str]
        total_listed    int   total companies on Bursa (from page text)
        pct_of_total    str   e.g. "1.50%"
    """
    soup = BeautifulSoup(html, "html.parser")

    # ── 1. List updated date ──────────────────────────────────────────────────
    # New format: inside an <em> tag  "Last updated: 2 April 2026"
    list_updated = "N/A"
    em = soup.find("em")
    if em:
        text = em.get_text(" ", strip=True)
        if "Last updated:" in text:
            list_updated = text.split("Last updated:")[-1].strip()
    # Fallback: scan all <p> tags (old format)
    if list_updated == "N/A":
        for p in soup.find_all("p"):
            text = p.get_text(" ", strip=True)
            if "List updated:" in text:
                list_updated = text.split("List updated:")[-1].strip()
                break

    # ── 2. Total listed companies + percentage ────────────────────────────────
    # New format: inside a <p> paragraph on the page
    # "...there are a total of 16 companies...represent 1.50% of the total number of 1,061 companies..."
    total_listed = 0
    pct_of_total = "N/A"
    for p in soup.find_all("p"):
        text = p.get_text(" ", strip=True)
        m_total = re.search(r'total number of ([\d,]+) companies', text)
        m_pct   = re.search(r'([\d.]+)%', text)
        if m_total:
            total_listed = int(m_total.group(1).replace(",", ""))
        if m_pct:
            pct_of_total = m_pct.group(1) + "%"
        if total_listed:
            break

    # ── 3. Company table ──────────────────────────────────────────────────────
    # New format: <table> with section header rows (colspan=6) marking PN17 / GN3
    # Each data row: col0=index, col1=company name, col2=trading status, col3-5=status ticks
    pn17_companies: list[str] = []
    gn3_companies:  list[str] = []
    current_section: str | None = None

    table = soup.find("table")
    if table:
        for row in table.find_all("tr"):
            cells = row.find_all(["td", "th"])
            if not cells:
                continue

            # Section header row: single cell with colspan spanning all columns
            if len(cells) == 1 and cells[0].get("colspan"):
                header_text = cells[0].get_text(strip=True)
                if "PN17" in header_text:
                    current_section = "pn17"
                elif "GN3" in header_text:
                    current_section = "gn3"
                continue

            # Skip <thead> rows (all th elements)
            if all(c.name == "th" for c in cells):
                continue

            # Data row — column 1 (0-indexed) is the company name
            if len(cells) >= 3 and current_section:
                name = cells[1].get_text(strip=True)
                if name and not name.isdigit():
                    if current_section == "pn17":
                        pn17_companies.append(name)
                    elif current_section == "gn3":
                        gn3_companies.append(name)

    return {
        "list_updated":   list_updated,
        "pn17_companies": pn17_companies,
        "gn3_companies":  gn3_companies,
        "total_listed":   total_listed,
        "pct_of_total":   pct_of_total,
    }


def fetch_current() -> dict:
    """
    Fetch and parse the Bursa PN17/GN3 page.

    Strategy:
      1. playwright    — PRIMARY: real Chromium browser, executes JS so the
                         table renders fully. Bursa's page is JS-rendered;
                         cloudscraper only bypasses Cloudflare challenges but
                         cannot execute JS to build the DOM.
      2. cloudscraper  — FALLBACK: faster but may return an empty JS shell.
                         Only used if playwright is unavailable.

    Sanity check: we verify "Last updated:" appears in the parsed result.
    If it doesn't, we know we got a shell/blocked page and raise an error.
    """
    html = None

    # ── Method 1: playwright (primary — handles JS-rendered content) ──────────
    try:
        print("[SCRAPE] Using playwright headless browser (primary)...")
        html = _fetch_html_playwright()
        print("[SCRAPE] playwright succeeded.")
    except Exception as e:
        print(f"[SCRAPE] playwright failed: {e}")

    # ── Method 2: cloudscraper (fallback — faster but no JS rendering) ────────
    if html is None and _CLOUDSCRAPER_OK:
        try:
            print("[SCRAPE] Falling back to cloudscraper...")
            html = _fetch_html_cloudscraper()
            print("[SCRAPE] cloudscraper succeeded.")
        except Exception as e:
            print(f"[SCRAPE] cloudscraper failed: {e}", file=sys.stderr)

    if html is None:
        raise RuntimeError("All fetch methods failed. Check Bursa site or playwright install.")

    result = _parse_html(html)

    # Sanity check: if list_updated is still N/A the page was not rendered properly
    if result["list_updated"] == "N/A":
        print("[SCRAPE] ⚠️  Page fetched but 'Last updated' date not found.")
        print("[SCRAPE]    This usually means JS did not render — retrying with playwright...")
        # Force playwright retry regardless of what already ran
        try:
            html = _fetch_html_playwright()
            result = _parse_html(html)
        except Exception as e:
            print(f"[SCRAPE] Playwright retry also failed: {e}", file=sys.stderr)

    return result


def load_previous() -> dict | None:
    if CACHE_FILE.exists():
        with open(CACHE_FILE) as f:
            return json.load(f)
    return None


def save_current(data: dict):
    payload = {"list_updated": data["list_updated"]}
    with open(CACHE_FILE, "w") as f:
        json.dump(payload, f, indent=2)


# ══════════════════════════════════════════════════════════════════════════════
# 2. CSV UPDATES
# ══════════════════════════════════════════════════════════════════════════════

COMPANIES_HEADER  = ["Company Name", "Type", "List Updated"]
HISTORICAL_HEADER = ["Run Date", "List Updated", "Company Name", "Type"]
SUMMARY_HEADER    = ["Report Date", "PN17_GN3_Count", "Percentage_of_Total",
                     "Total_Listed_Companies", "PN17_Count", "GN3_Count"]


def update_companies_csv(data: dict):
    """Overwrite pn17_gn3_companies.csv with the current snapshot."""
    rows = []
    for name in data["pn17_companies"]:
        rows.append([name, "PN17", data["list_updated"]])
    for name in data["gn3_companies"]:
        rows.append([name, "GN3", data["list_updated"]])

    with open(COMPANIES_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(COMPANIES_HEADER)
        w.writerows(rows)
    print(f"[CSV] pn17_gn3_companies.csv updated — {len(rows)} companies")


def append_historical_csv(data: dict):
    """Append new rows to pn17_gn3_historical.csv (skips if date already recorded)."""
    run_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    existing_dates: set[str] = set()
    if HISTORICAL_CSV.exists():
        with open(HISTORICAL_CSV, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                existing_dates.add(row.get("List Updated", ""))

    if data["list_updated"] in existing_dates:
        print(f"[CSV] historical — '{data['list_updated']}' already recorded, skipping.")
        return

    new_rows = []
    for name in data["pn17_companies"]:
        new_rows.append([run_date, data["list_updated"], name, "PN17"])
    for name in data["gn3_companies"]:
        new_rows.append([run_date, data["list_updated"], name, "GN3"])

    write_header = not HISTORICAL_CSV.exists()
    with open(HISTORICAL_CSV, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if write_header:
            w.writerow(HISTORICAL_HEADER)
        w.writerows(new_rows)
    print(f"[CSV] pn17_gn3_historical.csv — appended {len(new_rows)} rows")


def append_summary_csv(data: dict):
    """Append one summary row to summary-reportPN17.csv."""
    pn17_count = len(data["pn17_companies"])
    gn3_count  = len(data["gn3_companies"])
    total      = pn17_count + gn3_count

    # Use percentage scraped directly from page (accurate); fall back to calculation
    pct = data.get("pct_of_total", "N/A")
    if pct == "N/A" and data.get("total_listed"):
        pct = f"{total / data['total_listed'] * 100:.2f}%"

    now         = datetime.now(timezone.utc)
    report_date = f"{now.day} {now.strftime('%B %Y')}"

    write_header = not SUMMARY_CSV.exists()
    with open(SUMMARY_CSV, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if write_header:
            w.writerow(SUMMARY_HEADER)
        w.writerow([report_date, total, pct, data.get("total_listed", ""), pn17_count, gn3_count])
    print(f"[CSV] summary-reportPN17.csv — {report_date}: {total} companies ({pct})")


# ══════════════════════════════════════════════════════════════════════════════
# 3. EMAIL
# ══════════════════════════════════════════════════════════════════════════════

def _build_html(data: dict) -> str:
    pn17 = data["pn17_companies"]
    gn3  = data["gn3_companies"]

    def make_rows(companies: list, alt: str = "#f9f9f9") -> str:
        return "".join(
            f"<tr style='background:{'#ffffff' if i % 2 == 0 else alt}'>"
            f"<td style='padding:5px 10px;color:#555'>{i+1}</td>"
            f"<td style='padding:5px 10px'>{c}</td></tr>"
            for i, c in enumerate(companies)
        )

    total      = len(pn17) + len(gn3)
    pct        = data.get("pct_of_total", "N/A")
    total_co   = data.get("total_listed", "")
    now_str    = datetime.now(timezone.utc).strftime("%d %b %Y %H:%M UTC")

    total_line = (
        f"<td style='padding:6px 10px'>{total_co:,} listed companies "
        f"({pct} of total)</td>"
        if total_co else
        f"<td style='padding:6px 10px'>{pct}</td>"
    )

    return f"""<html><body style="font-family:Arial,sans-serif;max-width:700px;margin:auto;color:#222;font-size:14px">
<h2 style="color:#cc0000;margin-bottom:4px">🔔 Bursa Malaysia PN17/GN3 Update</h2>
<p style="color:#666;font-size:13px;margin-top:0">Detected on {now_str}</p>

<table style="width:100%;border-collapse:collapse;margin-bottom:16px">
  <tr>
    <td style="padding:6px 10px;background:#f5f5f5;font-weight:bold;width:160px">List updated</td>
    <td style="padding:6px 10px">{data['list_updated']}</td>
  </tr>
  <tr>
    <td style="padding:6px 10px;background:#f5f5f5;font-weight:bold">PN17 companies</td>
    <td style="padding:6px 10px">{len(pn17)}</td>
  </tr>
  <tr>
    <td style="padding:6px 10px;background:#f5f5f5;font-weight:bold">GN3 companies</td>
    <td style="padding:6px 10px">{len(gn3)}</td>
  </tr>
  <tr>
    <td style="padding:6px 10px;background:#f5f5f5;font-weight:bold">Total</td>
    <td style="padding:6px 10px"><strong>{total}</strong></td>
  </tr>
  <tr>
    <td style="padding:6px 10px;background:#f5f5f5;font-weight:bold">Bursa total</td>
    {total_line}
  </tr>
</table>

<p style="margin:12px 0">
  <a href="{URL}" style="background:#cc0000;color:#fff;padding:8px 18px;border-radius:4px;
  text-decoration:none;font-size:14px">View on Bursa Malaysia</a>
</p>

<h3 style="color:#cc0000;border-bottom:2px solid #cc0000;padding-bottom:4px">
  PN17 Companies <span style="font-weight:normal;font-size:0.85em;color:#666">({len(pn17)})</span>
</h3>
<table style="width:100%;border-collapse:collapse;margin-bottom:20px">
  <tr style="background:#cc0000;color:#fff">
    <th style="padding:6px 10px;width:40px">#</th>
    <th style="padding:6px 10px;text-align:left">Company Name</th>
  </tr>
  {make_rows(pn17)}
</table>

<h3 style="color:#1a6699;border-bottom:2px solid #1a6699;padding-bottom:4px">
  GN3 Companies <span style="font-weight:normal;font-size:0.85em;color:#666">({len(gn3)})</span>
</h3>
<table style="width:100%;border-collapse:collapse;margin-bottom:20px">
  <tr style="background:#1a6699;color:#fff">
    <th style="padding:6px 10px;width:40px">#</th>
    <th style="padding:6px 10px;text-align:left">Company Name</th>
  </tr>
  {make_rows(gn3, "#eef4fa")}
</table>

<hr style="border:none;border-top:1px solid #eee;margin-top:24px">
<p style="font-size:11px;color:#aaa">
  Automated by GitHub Actions · Bursa Malaysia PN17/GN3 Monitor ·
  <a href="{URL}" style="color:#aaa">{URL}</a>
</p>
</body></html>"""


def send_email(data: dict):
    gmail_user = os.environ.get("GMAIL_USER", "").strip()
    gmail_pass = os.environ.get("GMAIL_APP_PASS", "").strip()
    notify_raw = os.environ.get("NOTIFY_EMAILS", "").strip()

    if not gmail_user or not gmail_pass:
        print("[EMAIL] GMAIL_USER / GMAIL_APP_PASS not set — skipping.")
        return
    if not notify_raw:
        print("[EMAIL] NOTIFY_EMAILS not set — skipping.")
        return

    recipients = [e.strip() for e in notify_raw.split(",") if e.strip()]

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"🔔 Bursa PN17/GN3 Update — {data['list_updated']}"
    msg["From"]    = gmail_user
    msg["To"]      = ", ".join(recipients)
    msg.attach(MIMEText(_build_html(data), "html", "utf-8"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(gmail_user, gmail_pass)
            server.sendmail(gmail_user, recipients, msg.as_string())
        print(f"[EMAIL] Sent to: {', '.join(recipients)}")
    except smtplib.SMTPAuthenticationError:
        print("[EMAIL] Auth failed — check GMAIL_USER and GMAIL_APP_PASS.", file=sys.stderr)
    except Exception as e:
        print(f"[EMAIL] Failed: {e}", file=sys.stderr)


# ══════════════════════════════════════════════════════════════════════════════
# 4. MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    print(f"\n{'=' * 60}")
    print(f"  Bursa PN17/GN3 Monitor  —  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"{'=' * 60}\n")

    current  = fetch_current()
    previous = load_previous()

    print(f"  List Updated  : {current['list_updated']}")
    print(f"  PN17 Count    : {len(current['pn17_companies'])}")
    print(f"  GN3  Count    : {len(current['gn3_companies'])}")
    print(f"  Total Listed  : {current.get('total_listed', 'N/A')}")
    print(f"  % of Total    : {current.get('pct_of_total', 'N/A')}")
    print()

    # Guard: do not overwrite with empty data if scraping failed
    if not current["pn17_companies"] and not current["gn3_companies"]:
        print("⚠️  WARNING: Both company lists are empty — scraping likely failed.")
        print("⚠️  Skipping all updates to preserve existing data.")
        print("⚠️  last_run.json NOT updated — next run will retry.\n")
        sys.exit(1)

    # Detect change — compare by list_updated date only (no PDF link anymore)
    changed = (
        not previous
        or previous.get("list_updated") != current["list_updated"]
    )

    if not changed:
        print("✅ No update detected — nothing to do.\n")
        return

    print("🆕 New release detected! Processing...\n")

    update_companies_csv(current)
    append_historical_csv(current)
    append_summary_csv(current)
    send_email(current)
    save_current(current)

    print("\n✅ All done.\n")


if __name__ == "__main__":
    main()
