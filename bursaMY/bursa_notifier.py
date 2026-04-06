"""
bursa_notifier.py
─────────────────
GitHub Actions version of the Bursa Malaysia PN17/GN3 monitor.

What it does every run
  1. Scrapes Bursa Malaysia for the latest list-updated date and PDF link.
  2. Compares against last_run.json (committed to repo).
  3. If NEW:
       a. Downloads the PDF  →  pn17_gn3_pdfs/<dated_filename>.pdf
       b. Parses companies   →  updates pn17_gn3_companies.csv (current snapshot)
       c. Appends new rows   →  pn17_gn3_historical.csv
       d. Appends summary    →  summary-reportPN17.csv
       e. Sends email with inline summary + PDF attached
  4. Saves last_run.json (git commit handled by the workflow).

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
from email import encoders
from email.mime.base import MIMEBase
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
PDF_DIR        = ROOT / "pn17_gn3_pdfs"
COMPANIES_CSV  = ROOT / "pn17_gn3_companies.csv"
HISTORICAL_CSV = ROOT / "pn17_gn3_historical.csv"
SUMMARY_CSV    = ROOT / "summary-reportPN17.csv"
CACHE_FILE     = ROOT / "last_run.json"

# ─── Bursa constants ──────────────────────────────────────────────────────────
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
    """Use a headless Chromium browser as the last resort (always works)."""
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
        page.goto(URL, wait_until="networkidle", timeout=30000)
        html = page.content()
        browser.close()
    return html


def fetch_current() -> dict:
    """
    Scrape Bursa and return {list_updated, pdf_link, pn17_companies, gn3_companies}.

    Strategy (in order):
      1. cloudscraper  — handles Cloudflare JS challenges via TLS fingerprinting
      2. playwright    — full headless Chromium, unblockable fallback
    """
    html = None

    # ── Method 1: cloudscraper ────────────────────────────────────────────────
    if _CLOUDSCRAPER_OK:
        try:
            print("[SCRAPE] Trying cloudscraper...")
            html = _fetch_html_cloudscraper()
            print("[SCRAPE] cloudscraper succeeded.")
        except Exception as e:
            print(f"[SCRAPE] cloudscraper failed: {e}")

    # ── Method 2: playwright headless browser ─────────────────────────────────
    if html is None:
        try:
            print("[SCRAPE] Falling back to playwright headless browser...")
            html = _fetch_html_playwright()
            print("[SCRAPE] playwright succeeded.")
        except Exception as e:
            print(f"[SCRAPE] playwright failed: {e}", file=sys.stderr)
            raise RuntimeError(
                "All fetch methods failed. "
                "Check if Bursa is down or if playwright is installed."
            ) from e

    soup = BeautifulSoup(html, "html.parser")

    # "List updated:" date in the footnote paragraph
    note = soup.find("p", class_="footnote")
    list_updated = (
        note.text.split("List updated:")[-1].strip()
        if note and "List updated:" in note.text
        else "N/A"
    )

    # PDF download link
    pdf_tag = soup.select_one('p.bm_download a[href$=".pdf"]')
    pdf_link = (BASE_URL + pdf_tag["href"]) if pdf_tag and pdf_tag.get("href") else "N/A"

    # Company name lists from the ordered lists on the page
    def extract_list(label: str) -> list[str]:
        heading = soup.find("div", string=lambda t: t and label in t)
        if heading:
            ol = heading.find_next_sibling("ol")
            if ol:
                return [li.get_text(strip=True) for li in ol.find_all("li")]
        return []

    return {
        "list_updated":   list_updated,
        "pdf_link":       pdf_link,
        "pn17_companies": extract_list("PN17 Companies"),
        "gn3_companies":  extract_list("GN3 Companies"),
    }


def load_previous() -> dict | None:
    """Load last_run.json. Returns None if it does not exist yet."""
    if CACHE_FILE.exists():
        with open(CACHE_FILE) as f:
            return json.load(f)
    return None


def save_current(data: dict):
    """Write the current date + PDF link to last_run.json for the next comparison."""
    payload = {k: data[k] for k in ("list_updated", "pdf_link")}
    with open(CACHE_FILE, "w") as f:
        json.dump(payload, f, indent=2)


# ══════════════════════════════════════════════════════════════════════════════
# 2. PDF DOWNLOAD
# ══════════════════════════════════════════════════════════════════════════════

def download_pdf(pdf_url: str, list_updated: str) -> Path | None:
    """Download the PDF from Bursa, save with a clean dated filename."""
    if pdf_url == "N/A":
        return None

    PDF_DIR.mkdir(exist_ok=True)

    # e.g. "17 March 2026" → "PN17_GN3_17_March_2026.pdf"
    safe_date = re.sub(r"[^\w]", "_", list_updated.strip())
    dest = PDF_DIR / f"PN17_GN3_{safe_date}.pdf"

    if dest.exists():
        print(f"[PDF] Already exists, skipping download: {dest.name}")
        return dest

    headers = {"User-Agent": "Mozilla/5.0 (compatible; BursaMonitor/1.0)"}
    resp = requests.get(pdf_url, headers=headers, timeout=60)
    resp.raise_for_status()
    dest.write_bytes(resp.content)
    print(f"[PDF] Saved: {dest.name}  ({len(resp.content) // 1024} KB)")
    return dest


# ══════════════════════════════════════════════════════════════════════════════
# 3. CSV UPDATES
# ══════════════════════════════════════════════════════════════════════════════

COMPANIES_HEADER  = ["Company Name", "Type", "List Updated", "PDF Link"]
HISTORICAL_HEADER = ["Run Date", "List Updated", "Company Name", "Type", "PDF Link"]
SUMMARY_HEADER    = ["Report Date", "PN17_GN3_Count", "Percentage_of_Total",
                     "Total_Listed_Companies", "Source File"]


def _read_last_total_listed() -> int:
    """
    Read the most recently recorded Total_Listed_Companies from summary CSV.
    Used to carry the figure forward since Bursa does not publish it on the
    PN17/GN3 page itself.
    """
    if not SUMMARY_CSV.exists():
        return 0
    last = 0
    with open(SUMMARY_CSV, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            try:
                val = str(row.get("Total_Listed_Companies", "0")).replace(",", "").strip()
                if val.isdigit():
                    last = int(val)
            except (ValueError, AttributeError):
                pass
    return last


def update_companies_csv(data: dict):
    """Overwrite pn17_gn3_companies.csv with the latest snapshot."""
    rows = []
    for name in data["pn17_companies"]:
        rows.append([name, "PN17", data["list_updated"], data["pdf_link"]])
    for name in data["gn3_companies"]:
        rows.append([name, "GN3", data["list_updated"], data["pdf_link"]])

    with open(COMPANIES_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(COMPANIES_HEADER)
        w.writerows(rows)
    print(f"[CSV] pn17_gn3_companies.csv updated — {len(rows)} companies")


def append_historical_csv(data: dict):
    """
    Append new company rows to pn17_gn3_historical.csv.
    Skips silently if this list_updated date is already recorded.
    """
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
        new_rows.append([run_date, data["list_updated"], name, "PN17", data["pdf_link"]])
    for name in data["gn3_companies"]:
        new_rows.append([run_date, data["list_updated"], name, "GN3", data["pdf_link"]])

    write_header = not HISTORICAL_CSV.exists()
    with open(HISTORICAL_CSV, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if write_header:
            w.writerow(HISTORICAL_HEADER)
        w.writerows(new_rows)
    print(f"[CSV] pn17_gn3_historical.csv — appended {len(new_rows)} rows")


def append_summary_csv(data: dict):
    """
    Append one row to summary-reportPN17.csv.
    Percentage_of_Total uses the last known Total_Listed_Companies figure
    carried forward from the previous row (update manually for accuracy).
    """
    total_listed = _read_last_total_listed()
    count        = len(data["pn17_companies"]) + len(data["gn3_companies"])
    pct          = f"{count / total_listed * 100:.2f}%" if total_listed else "N/A"

    # Source filename extracted from the PDF URL
    source_file  = data["pdf_link"].split("/")[-1] if data["pdf_link"] != "N/A" else "N/A"

    # Cross-platform day without leading zero: use .day attribute, not %-d
    now         = datetime.now(timezone.utc)
    report_date = f"{now.day} {now.strftime('%B %Y')}"

    write_header = not SUMMARY_CSV.exists()
    with open(SUMMARY_CSV, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if write_header:
            w.writerow(SUMMARY_HEADER)
        w.writerow([report_date, count, pct, total_listed, source_file])
    print(f"[CSV] summary-reportPN17.csv — appended row: {report_date}, {count} companies, {pct}")


# ══════════════════════════════════════════════════════════════════════════════
# 4. EMAIL
# ══════════════════════════════════════════════════════════════════════════════

def _build_html(data: dict) -> str:
    """Build the HTML body for the alert email."""
    pn17 = data["pn17_companies"]
    gn3  = data["gn3_companies"]

    def make_rows(companies: list, bg_alt: str = "#f9f9f9") -> str:
        return "".join(
            f"<tr style='background:{'#ffffff' if i % 2 == 0 else bg_alt}'>"
            f"<td style='padding:5px 10px;color:#555'>{i + 1}</td>"
            f"<td style='padding:5px 10px'>{c}</td></tr>"
            for i, c in enumerate(companies)
        )

    pdf_btn = (
        f"<p style='margin:12px 0'>"
        f"<a href='{data['pdf_link']}' "
        f"style='background:#cc0000;color:#fff;padding:8px 18px;border-radius:4px;"
        f"text-decoration:none;font-size:14px'>Download PDF from Bursa Malaysia</a></p>"
        if data["pdf_link"] != "N/A"
        else "<p style='color:#999'>⚠️ PDF link not available on Bursa page.</p>"
    )

    now_str = datetime.now(timezone.utc).strftime("%d %b %Y %H:%M UTC")

    return f"""<html><body style="font-family:Arial,sans-serif;max-width:700px;margin:auto;color:#222;font-size:14px">
<h2 style="color:#cc0000;margin-bottom:4px">🔔 Bursa Malaysia PN17/GN3 Update</h2>
<p style="color:#666;font-size:13px;margin-top:0">Detected on {now_str}</p>

<table style="width:100%;border-collapse:collapse;margin-bottom:12px">
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
    <td style="padding:6px 10px"><strong>{len(pn17) + len(gn3)}</strong></td>
  </tr>
</table>

{pdf_btn}
<p style="font-size:12px;color:#888">The PDF is also attached to this email.</p>

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
  Source: <a href="{URL}" style="color:#aaa">{URL}</a>
</p>
</body></html>"""


def send_email(data: dict, pdf_path: Path | None):
    """Send the alert email with the HTML summary and PDF attachment."""
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

    # "mixed" is required when combining HTML body + binary attachment
    msg = MIMEMultipart("mixed")
    msg["Subject"] = f"🔔 Bursa PN17/GN3 Update — {data['list_updated']}"
    msg["From"]    = gmail_user
    msg["To"]      = ", ".join(recipients)

    # HTML body wrapped in a "related" part so images can be embedded later
    msg.attach(MIMEText(_build_html(data), "html", "utf-8"))

    # PDF attachment
    if pdf_path and pdf_path.exists():
        with open(pdf_path, "rb") as fp:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(fp.read())
        encoders.encode_base64(part)
        part.add_header(
            "Content-Disposition",
            f'attachment; filename="{pdf_path.name}"',
        )
        msg.attach(part)
        print(f"[EMAIL] Attaching: {pdf_path.name}")
    else:
        print("[EMAIL] No PDF to attach (PDF not downloaded or link was N/A).")

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(gmail_user, gmail_pass)
            server.sendmail(gmail_user, recipients, msg.as_string())
        print(f"[EMAIL] Sent successfully to: {', '.join(recipients)}")
    except smtplib.SMTPAuthenticationError:
        print("[EMAIL] Authentication failed — check GMAIL_USER and GMAIL_APP_PASS.", file=sys.stderr)
    except Exception as e:
        print(f"[EMAIL] Failed: {e}", file=sys.stderr)


# ══════════════════════════════════════════════════════════════════════════════
# 5. MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    print(f"\n{'=' * 60}")
    print(f"  Bursa PN17/GN3 Monitor  —  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"{'=' * 60}\n")

    current  = fetch_current()
    previous = load_previous()

    print(f"  List Updated : {current['list_updated']}")
    print(f"  PDF Link     : {current['pdf_link']}")
    print(f"  PN17 Count   : {len(current['pn17_companies'])}")
    print(f"  GN3  Count   : {len(current['gn3_companies'])}")
    print()

    # Trigger update if EITHER the date OR the PDF link has changed
    changed = (
        not previous
        or previous.get("list_updated") != current["list_updated"]
        or previous.get("pdf_link")     != current["pdf_link"]
    )

    if not changed:
        print("✅ No update detected — nothing to do.\n")
        return

    print("🆕 New release detected! Processing...\n")

    pdf_path = download_pdf(current["pdf_link"], current["list_updated"])
    update_companies_csv(current)
    append_historical_csv(current)
    append_summary_csv(current)
    send_email(current, pdf_path)
    save_current(current)

    print("\n✅ All done.\n")


if __name__ == "__main__":
    main()
