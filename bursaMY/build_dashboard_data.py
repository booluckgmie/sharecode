#!/usr/bin/env python3
"""
Build bursaMY/dashboard/data.json from the CSVs written by bursa_notifier.py.

The historical CSV has two layouts (both are handled here):
  * PDF era  (Jan 2020 - Nov 2025): one row per company with market, stage ticks,
    trading status and the list "as of" date in the `Status` column.
  * HTML era (Apr 2026 onward)    : rows were appended with shifted columns:
    run date | list-updated date | company | type (PN17 / GN3).

Output is one JSON document that the static dashboard (dashboard/index.html)
reads. Pure standard library - no pandas needed.
"""
import csv
import json
import re
import sys
from collections import Counter, OrderedDict, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent
HIST = ROOT / "pn17_gn3_historical.csv"
SUMMARY = ROOT / "summary-reportPN17.csv"
OUT = ROOT / "dashboard" / "data.json"

ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")
DATE_RE = re.compile(r"(?<![\w])(\d{1,2})\s+([A-Z][a-z]+)\s+(\d{4})")
STAGE_COLS = [
    "Pending submission to authorities",
    "Submitted, pending authorities’ approval",
    "Approval obtained, pending implementation",
    "Implemented, pending compliance with Paragraph 5.2(c) of PN17",
]
STAGE_LABELS = [
    "Pending submission to authorities",
    "Submitted, pending approval",
    "Approved, pending implementation",
    "Implemented, pending compliance",
]
GAP_DAYS = 75  # snapshots further apart than this => event date is a range


# ── helpers ───────────────────────────────────────────────────────────────────
def clean(s) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip()


def parse_date(s):
    m = DATE_RE.search(clean(s))
    if not m:
        return None
    for fmt in ("%d %B %Y", "%d %b %Y"):
        try:
            return datetime.strptime(" ".join(m.groups()), fmt).date()
        except ValueError:
            pass
    return None


def norm(name: str) -> str:
    n = clean(name).lower().replace("’", "").replace("'", "")
    n = re.sub(r"\bbhd\b", "berhad", n)
    n = re.sub(r"[^a-z0-9 ]", " ", n)
    return re.sub(r"\s+", " ", n).strip()


def strip_parens(name: str) -> str:
    return clean(re.sub(r"\(.*?\)", "", clean(name)))


def iso(d):
    return d.isoformat() if d else None


# ── load ──────────────────────────────────────────────────────────────────────
def load_rows():
    with open(HIST, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_summary():
    by_file, by_date = {}, {}
    with open(SUMMARY, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            d = parse_date(r["Report Date"])
            by_file[clean(r.get("Source File"))] = r
            if d:
                by_date[d] = r
    return by_file, by_date


def pct_float(s):
    try:
        return float(str(s).replace("%", ""))
    except (TypeError, ValueError):
        return None


def to_int(s):
    try:
        return int(str(s).replace(",", ""))
    except (TypeError, ValueError):
        return None


def build_snapshots(rows, sum_file, sum_date):
    """Return OrderedDict date -> {'entries': [...], 'src': ..., 'summary': row|None}."""
    snaps = {}

    # PDF era: group by source file, as-of date = most common parsed `Status` date
    pdf_groups = OrderedDict()
    html_rows = []
    for r in rows:
        if ISO.match(r[""] or ""):
            html_rows.append(r)
        else:
            pdf_groups.setdefault(clean(r["Source File"]), []).append(r)

    for sf, rs in pdf_groups.items():
        dates = Counter(
            parse_date(r["Status"])
            for r in rs
            if clean(r["Status"])
            and not clean(r["Status"]).startswith(("Announcement", "Hyperlink", "Note", "October"))
        )
        dates.pop(None, None)
        if not dates:
            continue
        asof = dates.most_common(1)[0][0]
        entries = []
        for r in rs:
            name, market = clean(r["Company name"]), clean(r["Market"])
            if not name or not market:
                continue  # continuation / note lines from the PDF parse
            stage = next((i + 1 for i, c in enumerate(STAGE_COLS) if clean(r.get(c))), None)
            entries.append(
                {
                    "name": name,
                    "type": "PN17" if "PN17" in market.upper() else "GN3",
                    "stage": stage,
                    "trading": clean(r["Trading status of listed securities"]) or None,
                }
            )
        snaps[asof] = {"entries": entries, "src": "pdf", "summary": sum_file.get(sf), "file": sf}

    # HTML era: run date | list-updated date | company | type
    by_list = defaultdict(list)
    for r in html_rows:
        asof = parse_date(r["Company name"])
        name, typ = clean(r["Market"]), clean(r["Pending submission to authorities"]).upper()
        if asof and name and typ in ("PN17", "GN3"):
            by_list[asof].append((r[""], name, typ))
    for asof, items in by_list.items():
        latest_run = max(i[0] for i in items)  # if a list date was scraped twice, keep the latest run
        items = [i for i in items if i[0] == latest_run]
        run = datetime.strptime(latest_run, "%Y-%m-%d").date()
        snaps[asof] = {
            "entries": [{"name": n, "type": t, "stage": None, "trading": None} for _, n, t in items],
            "src": "html",
            "summary": sum_date.get(run),
        }
    return OrderedDict(sorted(snaps.items()))


def build_aliases(snaps):
    """'X (formerly known as Y)' => key(Y) maps to key(X)."""
    alias = {}
    pat = re.compile(r"^(.*?)\s*\(formerly known as (.*?)\)\s*$", re.I)
    for s in snaps.values():
        for e in s["entries"]:
            m = pat.match(clean(e["name"]))
            if m:
                alias[norm(m.group(2))] = norm(m.group(1))
    # resolve chains
    for k in list(alias):
        seen = {k}
        while alias[k] in alias and alias[k] not in seen:
            seen.add(alias[k])
            alias[k] = alias[alias[k]]
    return alias


# ── main ──────────────────────────────────────────────────────────────────────
def main():
    rows = load_rows()
    sum_file, sum_date = load_summary()
    snaps = build_snapshots(rows, sum_file, sum_date)
    alias = build_aliases(snaps)

    def key_of(name):
        k = norm(strip_parens(name))
        return alias.get(k, k)

    # per-snapshot normalised membership, deduped by company key
    snap_list = []  # [{date, members: {key: entry}, ...}]
    display = {}    # key -> most recent display name
    for d, s in snaps.items():
        members = {}
        for e in s["entries"]:
            k = key_of(e["name"])
            members[k] = e
            display[k] = strip_parens(e["name"])
        snap_list.append({"date": d, "members": members, "src": s["src"], "summary": s["summary"]})

    warnings = []

    # ── series ──
    series = []
    for i, s in enumerate(snap_list):
        pn17 = sum(1 for e in s["members"].values() if e["type"] == "PN17")
        gn3 = len(s["members"]) - pn17
        sm = s["summary"]
        total_listed = to_int(sm["Total_Listed_Companies"]) if sm else None
        pct = pct_float(sm["Percentage_of_Total"]) if sm else None
        if sm and to_int(sm["PN17_GN3_Count"]) not in (None, len(s["members"])):
            warnings.append(
                f"{s['date']}: scraped {len(s['members'])} companies but Bursa summary says "
                f"{to_int(sm['PN17_GN3_Count'])} (parsing quirk in source)"
            )
        series.append(
            {
                "date": iso(s["date"]),
                "pn17": pn17,
                "gn3": gn3,
                "total": pn17 + gn3,
                "listed": total_listed,
                "pct": pct,
            }
        )

    # ── events between consecutive snapshots ──
    events = []
    for a, b in zip(snap_list, snap_list[1:]):
        gap = (b["date"] - a["date"]).days
        ka, kb = set(a["members"]), set(b["members"])
        for k in sorted(kb - ka):
            events.append((b["date"], a["date"], gap, "entered", k, b["members"][k]["type"]))
        for k in sorted(ka - kb):
            events.append((b["date"], a["date"], gap, "exited", k, a["members"][k]["type"]))
    events_json = [
        {
            "date": iso(d),
            "from": iso(prev),
            "gap_days": gap,
            "approx": gap > GAP_DAYS,
            "kind": kind,
            "company": display[k],
            "type": typ,
        }
        for d, prev, gap, kind, k, typ in events
    ]
    events_json.sort(key=lambda e: (e["date"], e["company"]), reverse=True)

    # entries / exits per calendar year (year the change was observed)
    # Only changes seen between regular snapshots (gap <= GAP_DAYS) are dated precisely;
    # changes detected across long gaps are counted separately as "approx".
    yearly = defaultdict(lambda: {"entered": 0, "exited": 0, "approx": 0})
    for e in events_json:
        if e["approx"]:
            yearly[e["date"][:4]]["approx"] += 1
        else:
            yearly[e["date"][:4]][e["kind"]] += 1
    yearly_json = [{"year": y, **v} for y, v in sorted(yearly.items())]

    # ── companies ──
    latest = snap_list[-1]
    first_date = snap_list[0]["date"]
    companies = []
    all_keys = set().union(*(set(s["members"]) for s in snap_list))
    for k in all_keys:
        present = [k in s["members"] for s in snap_list]
        n_present = sum(present)
        in_now = present[-1]
        # start of the run that ends at the last snapshot the company appeared in
        last_i = max(i for i, p in enumerate(present) if p)
        start_i = last_i
        while start_i > 0 and present[start_i - 1]:
            start_i -= 1
        since = snap_list[start_i]["date"]
        end = latest["date"] if in_now else snap_list[last_i]["date"]
        last_entry = snap_list[last_i]["members"][k]
        # last snapshot that carried a stage / trading status
        stage = trading = stage_asof = None
        for i in range(last_i, -1, -1):
            m = snap_list[i]["members"].get(k)
            if m and m["stage"]:
                stage, trading, stage_asof = m["stage"], m["trading"], snap_list[i]["date"]
                break
        companies.append(
            {
                "name": display[k],
                "type": last_entry["type"],
                "current": in_now,
                "since": iso(since),
                "since_censored": start_i == 0,  # already listed at first snapshot => "at least"
                "last_seen": iso(snap_list[last_i]["date"]),
                "tenure_days": (end - since).days,
                "snapshots": n_present,
                "stage": stage,
                "stage_label": STAGE_LABELS[stage - 1] if stage else None,
                "trading": trading,
                "stage_asof": iso(stage_asof),
            }
        )
    companies.sort(key=lambda c: (not c["current"], -c["tenure_days"], c["name"]))

    # ── KPIs / insights ──
    cur, prev = series[-1], series[-2] if len(series) > 1 else None
    year_ago = None
    target = latest["date"].toordinal() - 365
    cands = [s for s in series if datetime.strptime(s["date"], "%Y-%m-%d").toordinal() <= target + 60]
    if cands:
        year_ago = min(cands, key=lambda s: abs(datetime.strptime(s["date"], "%Y-%m-%d").toordinal() - target))

    def fmt(d):
        d = datetime.strptime(d, "%Y-%m-%d").date() if isinstance(d, str) else d
        return f"{d.day} {d.strftime('%b %Y')}"

    insights = []
    if prev:
        d = cur["total"] - prev["total"]
        delta = " (unchanged since the previous update)" if d == 0 else f" ({d:+d} since the previous update)"
    else:
        delta = ""
    insights.append(
        f"{cur['total']} companies on the list as of {fmt(cur['date'])}: "
        f"{cur['pn17']} PN17 and {cur['gn3']} GN3{delta}."
    )
    if year_ago and year_ago["date"] != cur["date"]:
        insights.append(
            f"A year earlier ({fmt(year_ago['date'])}) there were {year_ago['total']}, "
            f"a net change of {cur['total'] - year_ago['total']:+d}.".replace("-", "\u2212")
        )
    def names(xs, n=3):
        return ", ".join(xs[:n]) + (f" and {len(xs) - n} more" if len(xs) > n else "")

    recent = [e for e in events_json if e["date"] >= iso(date.fromordinal(latest["date"].toordinal() - 120))]
    ex = [e["company"] for e in recent if e["kind"] == "exited"]
    en = [e["company"] for e in recent if e["kind"] == "entered"]
    if ex:
        insights.append(f"{len(ex)} left the list in the last 4 months: {names(ex)}.")
    if en:
        insights.append(f"{len(en)} joined in the last 4 months: {names(en)}.")
    curr = [c for c in companies if c["current"]]
    if curr:
        longest = max(curr, key=lambda c: c["tenure_days"])
        yrs = longest["tenure_days"] / 365.25
        insights.append(
            f"Longest on the list: {longest['name']} — {'at least ' if longest['since_censored'] else ''}"
            f"{yrs:.1f} years (since {fmt(longest['since'])})."
        )
    # biggest data gap
    gaps = [(b["date"] - a["date"]).days for a, b in zip(snap_list, snap_list[1:])]
    big = max(range(len(gaps)), key=lambda i: gaps[i]) if gaps else None
    recent_gaps = [(i, g) for i, g in enumerate(gaps) if g > 120 and snap_list[i]["date"].year >= 2025]
    for i, g in recent_gaps:
        warnings.append(
            f"No snapshots between {fmt(snap_list[i]['date'])} and {fmt(snap_list[i + 1]['date'])} "
            f"({g} days) - changes in that window are shown as date ranges."
        )

    out = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": "Bursa Malaysia - PN17 and GN3 companies (listing directory)",
        "first_snapshot": iso(first_date),
        "latest_snapshot": iso(latest["date"]),
        "n_snapshots": len(snap_list),
        "kpi": {
            "current": cur,
            "previous": prev,
            "year_ago": year_ago,
        },
        "insights": insights,
        "series": series,
        "yearly": yearly_json,
        "events": events_json,
        "companies": companies,
        "stage_labels": STAGE_LABELS,
        "data_quality": warnings,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"[dashboard] {len(snap_list)} snapshots, {len(companies)} companies "
          f"({len(curr)} current), {len(events_json)} events -> {OUT.relative_to(ROOT.parent)}")
    for w in warnings:
        print(f"[dashboard] note: {w}", file=sys.stderr)


if __name__ == "__main__":
    main()
