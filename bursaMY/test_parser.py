"""Regression test for the scraper's table parser, using the real table Bursa served on
12 Oct 2026 (bursaMY/raw/table_2026-10-12.html).   Run:  python3 bursaMY/test_parser.py
"""
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).parent
spec = importlib.util.spec_from_file_location("bursa_notifier", ROOT / "bursa_notifier.py")
bn = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bn)


class ParseRealTable(unittest.TestCase):
    def setUp(self):
        table = (ROOT / "raw" / "table_2026-10-12.html").read_text(encoding="utf-8")
        self.res = bn._parse_html(f"<html><body><em>Last updated: 12 October 2026</em>{table}</body></html>")
        self.by_name = {d["name"]: d for d in self.res["details"]}

    def test_counts(self):
        self.assertEqual(len(self.res["pn17_companies"]), 8)
        self.assertEqual(len(self.res["gn3_companies"]), 4)

    def test_every_company_has_one_stage_and_a_trading_status(self):
        for d in self.res["details"]:
            self.assertEqual(d["stages_ticked"], 1, d["name"])
            self.assertTrue(d["stage"], d["name"])
            self.assertIn(d["trading"], ("Trading", "Suspended"), d["name"])

    def test_known_values(self):
        self.assertTrue(self.by_name["Khee San Berhad"]["stage"].startswith("Regularisation Plan approved by authorities"))
        self.assertTrue(self.by_name["Zelan Berhad"]["stage"].startswith("Regularisation Plans under authorities"))
        self.assertTrue(self.by_name["Asdion Berhad"]["stage"].startswith("Pending submission"))
        self.assertEqual(self.by_name["Pertama Digital Berhad"]["trading"], "Suspended")

    def test_stage_numbers(self):
        self.assertEqual(bn._stage_no("Pending submission to authorities"), 1)          # PDF era
        self.assertEqual(bn._stage_no("Implemented, pending compliance with Paragraph 5.2(c) of PN17"), 3)
        self.assertEqual(bn._stage_no("Regularisation Plans under authorities’ review"), 2)


if __name__ == "__main__":
    unittest.main()
