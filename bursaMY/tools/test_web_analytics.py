"""Tests for fetch_web_analytics.py using canned API responses (no network, no token).
Run:  python3 bursaMY/tools/test_web_analytics.py
"""
import importlib.util
import json
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path

spec = importlib.util.spec_from_file_location("fwa", Path(__file__).parent / "fetch_web_analytics.py")
fwa = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fwa)


def fake_fetch(token, params):
    by = params["by"]
    if by == "day":
        return {"version": 1, "data": [
            {"timestamp": "2026-10-14T00:00:00.000Z", "pageviews": 12, "visitors": 9},
            {"timestamp": "2026-10-15T00:00:00.000Z", "pageviews": 20, "visitors": 14}]}
    rows = {
        "requestPath": [{"requestPath": "/", "pageviews": 30, "visitors": 20}, {"requestPath": "/data.json", "pageviews": 2, "visitors": 1}],
        "referrerHostname": [{"referrerHostname": "", "pageviews": 20, "visitors": 15}, {"referrerHostname": "google.com", "pageviews": 12, "visitors": 8}],
        "country": [{"country": "MY", "pageviews": 25, "visitors": 18}, {"country": "SG", "pageviews": 7, "visitors": 5}],
        "deviceType": [{"deviceType": "desktop", "pageviews": 28, "visitors": 20}, {"deviceType": "mobile", "pageviews": 4, "visitors": 3}],
        "browserName": [{"browserName": "Chrome", "pageviews": 0, "visitors": 0}, {"browserName": "Safari", "pageviews": 5, "visitors": 4}],
    }[by]
    assert params["filter"] == "environment eq 'production'" and params["since"] < params["until"]
    return {"version": 1, "data": rows}


class Collect(unittest.TestCase):
    def test_shape_and_totals(self):
        out = fwa.collect("tok", "prj_1", "team_1", today=date(2026, 10, 15), fetch=fake_fetch)
        self.assertEqual(out["status"], "ok")
        self.assertEqual(len(out["daily"]), 30)                       # missing days filled with zeros
        self.assertEqual(out["daily"][0]["date"], "2026-09-16")
        self.assertEqual(out["daily"][-1], {"date": "2026-10-15", "pageviews": 20, "visitors": 14})
        self.assertEqual(out["totals"]["pageviews"], 32)
        self.assertEqual(out["totals"]["peak_day"], {"date": "2026-10-15", "pageviews": 20})
        self.assertEqual(out["totals"]["avg_daily_visitors"], round(23 / 30, 1))
        self.assertIsNone(out["referrers"][0]["label"])               # direct traffic has no hostname
        self.assertEqual([b["label"] for b in out["browsers"]], ["Safari"])   # zero rows dropped
        self.assertEqual(out["countries"][0]["label"], "MY")

    def test_no_visits_yet(self):
        out = fwa.collect("tok", "prj_1", "", today=date(2026, 10, 15), fetch=lambda t, p: {"data": []})
        self.assertEqual(out["totals"], {"pageviews": 0, "avg_daily_visitors": 0.0, "peak_day": None})


class Main(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        fwa.OUT = self.tmp / "analytics.json"
        for k in ("VERCEL_TOKEN", "VERCEL_PROJECT_ID", "VERCEL_TEAM_ID"):
            os.environ.pop(k, None)

    def test_missing_token_is_not_an_error(self):
        self.assertEqual(fwa.main(), 0)
        self.assertEqual(json.loads(fwa.OUT.read_text())["status"], "unavailable")

    def test_api_failure_keeps_previous_good_data_and_hides_token(self):
        os.environ.update(VERCEL_TOKEN="secret-token", VERCEL_PROJECT_ID="prj_1")
        fwa.main(fetch=fake_fetch)
        good = json.loads(fwa.OUT.read_text())
        self.assertEqual(good["status"], "ok")

        def boom(token, params):
            raise RuntimeError("HTTP 403 from Vercel: bad token secret-token")
        fwa.main(fetch=boom)
        kept = json.loads(fwa.OUT.read_text())
        self.assertEqual(kept["status"], "ok")
        self.assertTrue(kept["stale"])
        self.assertNotIn("secret-token", fwa.OUT.read_text())


if __name__ == "__main__":
    unittest.main()
