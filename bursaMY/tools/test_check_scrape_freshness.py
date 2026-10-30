"""Tests for check_scrape_freshness.py.   Run:  python3 bursaMY/tools/test_check_scrape_freshness.py"""
import importlib.util
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

spec = importlib.util.spec_from_file_location("csf", Path(__file__).parent / "check_scrape_freshness.py")
csf = importlib.util.module_from_spec(spec)
spec.loader.exec_module(csf)

NOW = datetime(2026, 10, 30, 12, 0, tzinfo=timezone.utc)


class Evaluate(unittest.TestCase):
    def test_recent_success_stays_green_with_a_warning(self):
        code, msg = csf.evaluate({"last_success_at": "2026-10-30T02:00:00Z"}, NOW)      # 10 h ago
        self.assertEqual(code, 0)
        self.assertTrue(msg.startswith("::warning::"))

    def test_longest_gap_seen_in_practice_does_not_alert(self):
        code, _ = csf.evaluate({"last_success_at": "2026-10-29T07:00:00Z"}, NOW)        # 29 h ago
        self.assertEqual(code, 0)

    def test_old_success_turns_the_run_red(self):
        code, msg = csf.evaluate({"last_success_at": "2026-10-28T20:00:00Z"}, NOW)      # 40 h ago
        self.assertEqual(code, 1)
        self.assertTrue(msg.startswith("::error::"))
        self.assertIn("40 hours", msg)

    def test_boundary(self):
        self.assertEqual(csf.evaluate({"last_success_at": "2026-10-29T00:00:00Z"}, NOW)[0], 0)   # exactly 36 h
        self.assertEqual(csf.evaluate({"last_success_at": "2026-10-28T23:59:00Z"}, NOW)[0], 1)   # 36 h 1 min

    def test_missing_or_bad_record_is_an_error(self):
        for data in (None, {}, {"last_success_at": None}, {"last_success_at": "yesterday"}):
            self.assertEqual(csf.evaluate(data, NOW)[0], 1, data)


class Main(unittest.TestCase):
    def test_reads_data_json_and_handles_a_missing_file(self):
        tmp = Path(tempfile.mkdtemp())
        csf.DATA = tmp / "data.json"
        self.assertEqual(csf.main(NOW), 1)                       # no file
        csf.DATA.write_text(json.dumps({"last_success_at": "2026-10-30T09:00:00Z"}))
        self.assertEqual(csf.main(NOW), 0)


if __name__ == "__main__":
    unittest.main()
