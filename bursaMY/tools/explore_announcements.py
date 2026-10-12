#!/usr/bin/env python3
"""
One-off explorer for Bursa's company-announcements page (run on a GitHub runner, where the
Cloudflare check passes). It records what the page loads so a search can be built:

  * every JSON/XHR response the page makes while loading (URL, status, first bytes)
  * the page's filter controls (inputs / selects, with option labels)
  * a first attempt at the search endpoint with a PN17 keyword and Apr-Oct 2026 dates

Output goes to bursaMY/raw/explore/ and is committed by the workflow. Temporary tool.
"""
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlencode

from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parent.parent / "raw" / "explore"
OUT.mkdir(parents=True, exist_ok=True)
BASE = "https://www.bursamalaysia.com"
PAGE = BASE + "/market_information/announcements/company_announcement"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")


def save(name, obj):
    p = OUT / name
    p.write_text(obj if isinstance(obj, str) else json.dumps(obj, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"[explore] wrote {p.name} ({p.stat().st_size} bytes)")


def main():
    seen = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, args=[
            "--disable-blink-features=AutomationControlled", "--no-sandbox", "--disable-dev-shm-usage"])
        ctx = browser.new_context(user_agent=UA, locale="en-US", viewport={"width": 1366, "height": 900})
        ctx.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined});")
        page = ctx.new_page()

        def on_response(resp):
            url = resp.url
            if "bursamalaysia.com" not in url:
                return
            ct = (resp.headers.get("content-type") or "").lower()
            if "json" in ct or "/api/" in url:
                try:
                    body = resp.text()
                except Exception:
                    body = ""
                seen.append({"url": url, "status": resp.status, "content_type": ct, "bytes": len(body), "head": body[:1500]})

        page.on("response", on_response)
        page.goto(BASE, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(3000)
        page.goto(PAGE, wait_until="domcontentloaded", timeout=60000)
        for _ in range(25):                       # wait out the Cloudflare challenge
            if "Just a moment" not in page.title():
                break
            page.wait_for_timeout(2000)
        page.wait_for_timeout(6000)               # let the page's own XHRs finish
        print("[explore] title:", page.title())
        html = page.content()
        save("announcements_page.html", html[:400000])

        controls = page.evaluate("""() => [...document.querySelectorAll('input,select,button,a[href*="announcement"]')].slice(0, 200).map(e => ({
            tag: e.tagName, type: e.type || '', id: e.id || '', name: e.name || '', cls: (e.className || '').toString().slice(0, 80),
            placeholder: e.placeholder || '', text: (e.innerText || e.value || '').trim().slice(0, 80),
            href: e.getAttribute('href') || '',
            options: e.tagName === 'SELECT' ? [...e.options].slice(0, 80).map(o => o.value + ' | ' + o.text.trim()) : undefined}))""")
        save("controls.json", controls)
        save("page_xhr.json", seen)

        # First guess at the search endpoint (the page's own requests, listed above, are the ground truth)
        tries = []
        guesses = [
            {"ann_type": "company", "company": "", "keyword": "PN17", "dt_ht": "12/10/2026", "dt_lt": "01/04/2026", "cat": "", "sec": "", "subsec": "", "per_page": 50, "page": 1},
            {"ann_type": "company", "company": "", "keyword": "PN17", "dt_ht": "2026-10-12", "dt_lt": "2026-04-01", "cat": "", "sec": "", "subsec": "", "per_page": 50, "page": 1},
        ]
        for q in guesses:
            url = f"{BASE}/api/v1/announcements/search?{urlencode(q)}"
            try:
                r = page.request.get(url, headers={"Accept": "application/json", "X-Requested-With": "XMLHttpRequest"})
                body = r.text()
                tries.append({"url": url, "status": r.status, "bytes": len(body), "head": body[:3000]})
            except Exception as e:
                tries.append({"url": url, "error": str(e)})
        save("search_guesses.json", tries)
        browser.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:                        # never fail the monitor run because of the explorer
        print("[explore] error:", e)
        sys.exit(0)
