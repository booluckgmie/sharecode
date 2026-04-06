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
       d. Rebuilds summary   →  summary-reportPN17.csv
       e. Sends email with inline summary + PDF download link
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

# ─── Paths ────────────────────────────────────────────────────────────────────
ROOT          = Path(__file__).parent
PDF_DIR       = ROOT / "pn17_gn3_pdfs"
COMPANIES_CSV = ROOT / "pn17_gn3_companies.csv"
HISTORICAL_CSV= ROOT / "pn17_gn3_historical.csv"
SUMMARY_CSV   = ROOT / "summary-reportPN17.csv"
CACHE_FILE    = ROOT / "last_run.json"

# ─── Bursa constants ──────────────────────────────────────────────────────────
URL      = "https://www.bursamalaysia.com/bm/trade/trading_resources/listing_directory/pn17_and_gn3_companies"
BASE_URL = "https://www.bursamalaysia.com"


# ══════════════════════════════════════════════════════════════════════════════
# 1. SCRAPING
# ══════════════════════════════════════════════════════════════════════════════

def fetch_current() -> dict:
    """Return {list_updated, pdf_link, pn17_companies, gn3_companies}."""
    resp = requests.get(URL, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.content, "html.parser")

    # List updated date
    note = soup.find("p", class_="footnote")
    list_updated = (
        note.text.split("List updated:")[-1].strip()
        if note and "List updated:" in note.text
        else "N/A"
    )

    # PDF link
    pdf_tag = soup.select_one('p.bm_download a[href$=".pdf"]')
    pdf_link = (BASE_URL + pdf_tag["href"]) if pdf_tag and pdf_tag.get("href") else "N/A"

    # Company lists
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
    if CACHE_FILE.exists():
        with open(CACHE_FILE) as f:
            return json.load(f)
    return None


def save_current(data: dict):
    payload = {k: data[k] for k in ("list_updated", "pdf_link")}
    with open(CACHE_FILE, "w") as f:
        json.dump(payload, f, indent=2)


# ══════════════════════════════════════════════════════════════════════════════
# 2. PDF DOWNLOAD
# ══════════════════════════════════════════════════════════════════════════════

def download_pdf(pdf_url: str, list_updated: str) -> Path | None:
    """Download PDF, save with dated filename, return local path."""
    if pdf_url == "N/A":
        return None

    PDF_DIR.mkdir(exist_ok=True)

    # Build a clean filename from the date  e.g. PN17_GN3_2026-03-17.pdf
    safe_date = re.sub(r"[^\w]", "_", list_updated.strip())
    dest = PDF_DIR / f"PN17_GN3_{safe_date}.pdf"

    if dest.exists():
        print(f"[PDF] Already downloaded: {dest.name}")
        return dest

    resp = requests.get(pdf_url, timeout=60)
    resp.raise_for_status()
    dest.write_bytes(resp.content)
    print(f"[PDF] Saved: {dest.name}  ({len(resp.content)//1024} KB)")
    return dest


# ══════════════════════════════════════════════════════════════════════════════
# 3. CSV UPDATES
# ══════════════════════════════════════════════════════════════════════════════

COMPANIES_HEADER  = ["Company Name", "Type", "List Updated", "PDF Link"]
HISTORICAL_HEADER = ["Run Date", "List Updated", "Company Name", "Type", "PDF Link"]
SUMMARY_HEADER    = ["Report Date", "PN17_GN3_Count", "Percentage_of_Total", "Total_Listed_Companies", "Source File"]

# Bursa publishes total listed companies on their stats page; we track it in
# summary-reportPN17.csv.  The helper below reads the last known total so we
# can carry it forward when Bursa doesn't publish an updated figure.
def _read_last_total_listed() -> int:
    """Return the most recently recorded Total_Listed_Companies value, or 0."""
    if not SUMMARY_CSV.exists():
        return 0
    last = 0
    with open(SUMMARY_CSV, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            try:
                last = int(str(row.get("Total_Listed_Companies", 0)).replace(",", ""))
            except ValueError:
                pass
    return last


def update_companies_csv(data: dict):
    """Overwrite companies CSV with the current snapshot."""
    rows = []
    for name in data["pn17_companies"]:
        rows.append([name, "PN17", data["list_updated"], data["pdf_link"]])
    for name in data["gn3_companies"]:
        rows.append([name, "GN3", data["list_updated"], data["pdf_link"]])

    with open(COMPANIES_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(COMPANIES_HEADER)
        w.writerows(rows)
    print(f"[CSV] pn17_gn3_companies.csv updated  ({len(rows)} companies)")


def append_historical_csv(data: dict):
    """Append new entries to the historical CSV (skip if date already present)."""
    run_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Read existing to avoid duplicates
    existing_dates: set[str] = set()
    if HISTORICAL_CSV.exists():
        with open(HISTORICAL_CSV, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                existing_dates.add(row.get("List Updated", ""))

    if data["list_updated"] in existing_dates:
        print(f"[CSV] historical – {data['list_updated']} already recorded, skipping.")
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
    print(f"[CSV] pn17_gn3_historical.csv – appended {len(new_rows)} rows")


def rebuild_summary_csv(new_data: dict | None = None):
    """
    Append a new row to summary-reportPN17.csv matching the schema:
      Report Date, PN17_GN3_Count, Percentage_of_Total,
      Total_Listed_Companies, Source File

    Total_Listed_Companies is carried forward from the previous row when it
    cannot be scraped (Bursa doesn't expose this on the live page).
    If new_data is None, rebuilds the entire file from historical CSV.
    """
    if new_data is None:
        # Full rebuild from historical CSV (used for migrations/repairs)
        if not HISTORICAL_CSV.exists():
            return
        counts: dict[str, dict] = {}
        with open(HISTORICAL_CSV, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                key = row["List Updated"]
                if key not in counts:
                    counts[key] = {"count": 0, "source": row.get("PDF Link", "N/A")}
                counts[key]["count"] += 1
        existing_totals: dict[str, str] = {}
        if SUMMARY_CSV.exists():
            with open(SUMMARY_CSV, encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    existing_totals[row.get("Report Date", "")] = row.get("Total_Listed_Companies", "")
        last_total = _read_last_total_listed()
        with open(SUMMARY_CSV, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(SUMMARY_HEADER)
            for lu, c in counts.items():
                total = int(existing_totals.get(lu, last_total) or last_total)
                pct   = f"{c['count']/total*100:.2f}%" if total else "N/A"
                w.writerow([lu, c["count"], pct, total, c["source"]])
        print(f"[CSV] summary-reportPN17.csv rebuilt  ({len(counts)} entries)")
        return

    # Normal path: append one new row
    total_listed = _read_last_total_listed()
    count = len(new_data["pn17_companies"]) + len(new_data["gn3_companies"])
    pct   = f"{count/total_listed*100:.2f}%" if total_listed else "N/A"
    # Derive source filename from pdf_link URL
    source_file = new_data["pdf_link"].split("/")[-1] if new_data["pdf_link"] != "N/A" else "N/A"
    report_date = datetime.now(timezone.utc).strftime("%-d %B %Y")

    write_header = not SUMMARY_CSV.exists()
    with open(SUMMARY_CSV, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if write_header:
            w.writerow(SUMMARY_HEADER)
        w.writerow([report_date, count, pct, total_listed, source_file])
    print(f"[CSV] summary-reportPN17.csv – appended row for {report_date}  ({count} companies, {pct})")


# ══════════════════════════════════════════════════════════════════════════════
# 4. EMAIL
# ══════════════════════════════════════════════════════════════════════════════

def build_email_html(data: dict, pdf_path: Path | None) -> str:
    pn17 = data["pn17_companies"]
    gn3  = data["gn3_companies"]

    pn17_rows = "".join(
        f"<tr><td style='padding:4px 8px'>{i+1}</td><td style='padding:4px 8px'>{c}</td></tr>"
        for i, c in enumerate(pn17)
    )
    gn3_rows = "".join(
        f"<tr style='background:#f9f9f9'><td style='padding:4px 8px'>{i+1}</td><td style='padding:4px 8px'>{c}</td></tr>"
        for i, c in enumerate(gn3)
    )

    pdf_section = (
        f"<p>📎 <a href='{data['pdf_link']}'>Download latest PDF from Bursa Malaysia</a></p>"
        if data["pdf_link"] != "N/A"
        else "<p>⚠️ PDF link not available.</p>"
    )

    return f"""
<html><body style="font-family:Arial,sans-serif;max-width:700px;margin:auto;color:#222">
<h2 style="color:#cc0000">🔔 Bursa Malaysia PN17/GN3 Update Detected</h2>
<p><strong>List Updated:</strong> {data['list_updated']}</p>
<p><strong>Checked on:</strong> {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}</p>
{pdf_section}

<h3>PN17 Companies &nbsp;<span style="font-size:0.85em;color:#666">({len(pn17)} companies)</span></h3>
<table border="1" cellspacing="0" cellpadding="0"
       style="border-collapse:collapse;border-color:#ddd;width:100%">
  <tr style="background:#cc0000;color:#fff">
    <th style="padding:6px 8px">#</th>
    <th style="padding:6px 8px;text-align:left">Company</th>
  </tr>
  {pn17_rows}
</table>

<h3>GN3 Companies &nbsp;<span style="font-size:0.85em;color:#666">({len(gn3)} companies)</span></h3>
<table border="1" cellspacing="0" cellpadding="0"
       style="border-collapse:collapse;border-color:#ddd;width:100%">
  <tr style="background:#1a6699;color:#fff">
    <th style="padding:6px 8px">#</th>
    <th style="padding:6px 8px;text-align:left">Company</th>
  </tr>
  {gn3_rows}
</table>

<hr style="margin-top:24px">
<p style="font-size:0.8em;color:#888">
  Automated alert via GitHub Actions · Bursa Malaysia PN17/GN3 Monitor
</p>
</body></html>
"""


def send_email(data: dict, pdf_path: Path | None):
    gmail_user  = os.environ.get("GMAIL_USER", "")
    gmail_pass  = os.environ.get("GMAIL_APP_PASS", "")
    notify_raw  = os.environ.get("NOTIFY_EMAILS", "")

    if not gmail_user or not gmail_pass:
        print("[EMAIL] GMAIL_USER / GMAIL_APP_PASS not set – skipping email.")
        return
    if not notify_raw.strip():
        print("[EMAIL] NOTIFY_EMAILS not set – skipping email.")
        return

    recipients = [e.strip() for e in notify_raw.split(",") if e.strip()]

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"🔔 Bursa PN17/GN3 Update – {data['list_updated']}"
    msg["From"]    = gmail_user
    msg["To"]      = ", ".join(recipients)

    html_body = build_email_html(data, pdf_path)
    msg.attach(MIMEText(html_body, "html"))

    # Attach PDF if downloaded
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

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(gmail_user, gmail_pass)
            server.sendmail(gmail_user, recipients, msg.as_string())
        print(f"[EMAIL] Sent to: {', '.join(recipients)}")
    except Exception as e:
        print(f"[EMAIL] Failed: {e}", file=sys.stderr)


# ══════════════════════════════════════════════════════════════════════════════
# 5. MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    print(f"\n{'='*60}")
    print(f"  Bursa PN17/GN3 Monitor  –  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"{'='*60}\n")

    current  = fetch_current()
    previous = load_previous()

    print(f"  List Updated : {current['list_updated']}")
    print(f"  PDF Link     : {current['pdf_link']}")
    print(f"  PN17 Count   : {len(current['pn17_companies'])}")
    print(f"  GN3  Count   : {len(current['gn3_companies'])}\n")

    # Detect change
    changed = (
        not previous
        or previous.get("list_updated") != current["list_updated"]
        or previous.get("pdf_link")     != current["pdf_link"]
    )

    if not changed:
        print("✅ No update detected – nothing to do.\n")
        return

    print("🆕 New release detected! Processing…\n")

    pdf_path = download_pdf(current["pdf_link"], current["list_updated"])
    update_companies_csv(current)
    append_historical_csv(current)
    rebuild_summary_csv(new_data=current)
    send_email(current, pdf_path)
    save_current(current)

    print("\n✅ All done.\n")


if __name__ == "__main__":
    main()
