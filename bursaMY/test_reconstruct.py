"""Tests for the gap reconstruction in build_dashboard_data.py.   Run:  python3 bursaMY/test_reconstruct.py

Reconstructed snapshots are built only from dated, sourced exits (gap_events.json) and only when those
exits turn the earlier published list into the later one exactly. The last test runs the real data.
"""
import importlib.util
import json
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).parent
spec = importlib.util.spec_from_file_location("build_dashboard_data", ROOT / "build_dashboard_data.py")
bd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bd)


def snap(d, *names, src="pdf"):
    return {"date": d, "members": {n: {"type": "PN17", "stage": 1, "trading": "Trading"} for n in names},
            "src": src, "summary": None}


def exited(company, d):
    return {"company": company, "kind": "exited", "date": d, "how": "test", "source": "x"}


class Reconstruct(unittest.TestCase):
    A = snap(date(2025, 11, 3), "a", "b", "c", "d")
    B = snap(date(2026, 4, 2), "a", "d")

    def run_it(self, events, a=None, b=None):
        return bd.add_reconstructed([a or self.A, b or self.B], events, lambda n: n)

    def test_inserts_one_snapshot_per_exit_date(self):
        out, notes = self.run_it([exited("b", "2026-02-27"), exited("c", "2026-03-10")])
        self.assertEqual([s["date"].isoformat() for s in out], ["2025-11-03", "2026-02-27", "2026-03-10", "2026-04-02"])
        self.assertEqual([sorted(s["members"]) for s in out[1:3]], [["a", "c", "d"], ["a", "d"]])
        self.assertEqual([s["src"] for s in out], ["pdf", "reconstructed", "reconstructed", "pdf"])
        self.assertEqual(notes, [(date(2025, 11, 3), date(2026, 4, 2), 2)])

    def test_two_exits_on_the_same_day_make_one_snapshot(self):
        out, _ = self.run_it([exited("b", "2026-03-10"), exited("c", "2026-03-10")])
        self.assertEqual(len(out), 3)
        self.assertEqual(sorted(out[1]["members"]), ["a", "d"])

    def test_events_that_do_not_explain_the_change_leave_the_gap_alone(self):
        out, notes = self.run_it([exited("b", "2026-02-27")])  # c is still missing from the later list
        self.assertEqual(len(out), 2)
        self.assertEqual(notes, [])

    def test_an_exit_of_a_company_that_was_not_listed_is_refused(self):
        out, notes = self.run_it([exited("zzz", "2026-02-27"), exited("b", "2026-03-01"), exited("c", "2026-03-02")])
        self.assertEqual((len(out), notes), (2, []))

    def test_entries_are_not_reconstructed(self):
        ev = [{"company": "e", "kind": "entered", "date": "2026-01-05", "how": "t", "source": "x"}]
        out, notes = self.run_it(ev, b=snap(date(2026, 4, 2), "a", "b", "c", "d", "e"))
        self.assertEqual((len(out), notes), (2, []))

    def test_events_outside_the_gap_are_ignored(self):
        out, _ = self.run_it([exited("b", "2025-10-01"), exited("b", "2026-02-27"), exited("c", "2026-03-10"),
                              exited("q", "2026-04-02")])
        self.assertEqual(len(out), 4)

    def test_short_gaps_are_never_touched(self):
        out, notes = bd.add_reconstructed([snap(date(2026, 3, 1), "a", "b"), snap(date(2026, 3, 20), "a")],
                                          [exited("b", "2026-03-10")], lambda n: n)
        self.assertEqual((len(out), notes), (2, []))


class RealData(unittest.TestCase):
    """The 3 Nov 2025 -> 2 Apr 2026 gap in the committed data."""

    @classmethod
    def setUpClass(cls):
        cls.d = json.loads((ROOT / "dashboard" / "data.json").read_text(encoding="utf-8"))

    def test_gap_series(self):
        pts = {p["date"]: p for p in self.d["series"] if "2025-11-03" <= p["date"] <= "2026-04-02"}
        self.assertEqual({k: (v["pn17"], v["gn3"]) for k, v in pts.items()},
                         {"2025-11-03": (15, 4), "2026-02-27": (14, 4), "2026-03-10": (13, 4),
                          "2026-03-17": (12, 4), "2026-04-02": (12, 4)})
        self.assertEqual([k for k, v in pts.items() if v.get("reconstructed")], ["2026-02-27", "2026-03-10", "2026-03-17"])

    def test_reconstructed_points_are_not_counted_as_published_lists(self):
        self.assertEqual(self.d["n_reconstructed"], 3)
        self.assertEqual(self.d["n_snapshots"], sum(1 for s in self.d["snapshots"] if s["source"] != "reconstructed"))

    def test_exits_are_dated_and_sourced(self):
        got = {e["company"]: (e["date"], e["approx"], bool(e.get("source")))
               for e in self.d["events"] if "2026-02-01" <= e["date"] <= "2026-03-31"}
        self.assertEqual(got, {"Bintai Kinden Corporation Berhad": ("2026-02-27", False, True),
                               "Ireka Corporation Berhad": ("2026-03-10", False, True),
                               "Pharmaniaga Berhad": ("2026-03-17", False, True)})

    def test_latest_figures_do_not_use_reconstructed_points(self):
        self.assertFalse(self.d["kpi"]["current"].get("reconstructed"))
        self.assertEqual(self.d["kpi"]["current"]["date"], self.d["latest_snapshot"])


if __name__ == "__main__":
    unittest.main()
