import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import build_site_data
from common import AREA_KEYS, FIELD_OF, assign_ids, display_title, scholar_id, VENUES, dblp_name, norm_name, not_a_paper, page_count, split_list
from scan_topics import hit


class CommonTest(unittest.TestCase):
    def test_page_count(self):
        self.assertEqual(page_count("41:1-41:30"), 30)
        self.assertEqual(page_count("97-117"), 21)
        self.assertIsNone(page_count(""))
        self.assertIsNone(page_count("e12"))

    def test_dblp_name(self):
        self.assertEqual(dblp_name("Gagandeep Singh 0001"), "Gagandeep Singh")
        self.assertEqual(dblp_name("Guy Katz"), "Guy Katz")

    def test_norm_name(self):
        self.assertEqual(norm_name("Markus Püschel"), "markus puschel")

    def test_scholar_id(self):
        self.assertEqual(scholar_id("Guy Katz", 2017, "Reluplex: An Efficient SMT Solver"), "katz2017reluplex")
        self.assertEqual(scholar_id("Gagandeep Singh 0001", 2019, "An abstract domain for certifying neural networks"),
                         "singh2019abstract")
        self.assertEqual(scholar_id("Markus Püschel", 2020, "On the Paradox"), "puschel2020paradox")

    def test_assign_ids_suffix(self):
        papers = [{"key": k, "year": 2020, "title": "Towards X", "authors": [{"name": "Li Wang"}]} for k in ("b", "a")]
        assign_ids(papers)
        self.assertEqual(sorted(p["id"] for p in papers), ["wang2020towards", "wang2020towardsb"])

    def test_display_title(self):
        self.assertEqual(display_title("CERTIFIED VS. EMPIRICAL ADVERSARIAL ROBUSTNESS VIA HYBRID CONVOLUTIONS WITH ATTENTION STOCHASTICITY"),
                         "Certified vs. Empirical Adversarial Robustness via Hybrid Convolutions with Attention Stochasticity")
        self.assertEqual(display_title("RHOPE: LLM-AUGMENTED ADAPTIVE DESIGN FOR GNNS"), "Rhope: LLM-Augmented Adaptive Design for GNNs")
        self.assertEqual(display_title("Reluplex: An Efficient SMT Solver"), "Reluplex: An Efficient SMT Solver")

    def test_split_list(self):
        self.assertEqual(split_list("a; b;;c "), ["a", "b", "c"])

    def test_every_venue_has_a_field(self):
        self.assertEqual({v["key"] for v in VENUES}, set(FIELD_OF))

    def test_toc_patterns(self):
        pldi = next(v for v in VENUES if v["key"] == "pldi")
        self.assertTrue(any(re.fullmatch(p, "journals/pacmpl/pacmpl8#PLDI") for p in pldi["tocs"]))
        self.assertTrue(any(re.fullmatch(p, "conf/pldi/pldi2019") for p in pldi["tocs"]))
        icse = next(v for v in VENUES if v["key"] == "icse")
        self.assertFalse(any(re.fullmatch(p, "conf/icse/icse2019c") for p in icse["tocs"]))
        iclr = next(v for v in VENUES if v["key"] == "iclr")
        self.assertFalse(any(re.fullmatch(p, "conf/iclr/iclr2018w") for p in iclr["tocs"]))


class PrefilterTest(unittest.TestCase):
    def test_hits(self):
        self.assertEqual(hit("Reluplex: An Efficient SMT Solver for Verifying Deep Neural Networks"), "strong")
        self.assertEqual(hit("Reachability Analysis of Deep Neural Networks"), "keyword")
        self.assertEqual(hit("Certified Adversarial Robustness via Randomized Smoothing"), "strong")
        self.assertEqual(hit("A Type System for Rust Lifetimes"), "")


class ScoreTest(unittest.TestCase):
    def test_geomean(self):
        self.assertAlmostEqual(build_site_data.geomean([0, 0, 0, 0]), 1.0)
        self.assertAlmostEqual(build_site_data.geomean([3, 0, 0, 0]), 4 ** 0.25, places=3)

    def test_score_fields_counts_each_member_share(self):
        papers = [{"venue": "cav", "authors": [{}, {}, {}, {}], "slugs": ["a", "b"]},
                  {"venue": "icml", "authors": [{}, {}], "slugs": ["a"]}]
        self.assertEqual(build_site_data.score_fields(papers, {"a"})["lv"], 0.25)
        self.assertEqual(build_site_data.score_fields(papers, {"a", "b"})["lv"], 0.5)
        self.assertEqual(build_site_data.score_fields(papers, {"a"})["ml"], 0.5)

    def test_not_a_paper(self):
        self.assertTrue(not_a_paper("fse", "Safety and robustness for deep learning with provable guarantees (keynote)"))
        self.assertTrue(not_a_paper("cav", "Learning to Split: A Heuristic for Neural Network Verification (Invited Talk)"))
        self.assertTrue(not_a_paper("issta", "Automated debugging: past, present, and future (ISSTA impact paper award)"))
        self.assertTrue(not_a_paper("icml", "Position: Future Directions in the Theory of Graph Machine Learning"))
        self.assertFalse(not_a_paper("lics", "A type theory for cartesian closed bicategories (Extended Abstract)"))
        self.assertFalse(not_a_paper("iccv", "Preface: A Data-driven Volumetric Prior for Few-shot Face Synthesis"))
        self.assertFalse(not_a_paper("iclr", "(Certified!!) Adversarial Robustness for Free!"))

    def test_areas_known(self):
        self.assertIn("other", AREA_KEYS)


if __name__ == "__main__":
    unittest.main()


class SiteTracksTest(unittest.TestCase):
    def test_aaai_main(self):
        from site_tracks import aaai_main
        self.assertTrue(aaai_main("AAAI Technical Track on Machine Learning I"))
        self.assertTrue(aaai_main("Main Track: NLP and Machine Learning"))
        self.assertTrue(aaai_main("Machine Learning Methods"))
        self.assertTrue(aaai_main("Intelligent Robots (ROB)"))
        self.assertFalse(aaai_main("AAAI Technical Track on Safe, Robust and Responsible AI Track"))
        self.assertFalse(aaai_main("AAAI Special Track on AI Alignment"))
        self.assertFalse(aaai_main("Student Abstract Track"))
        self.assertFalse(aaai_main("IAAI Technical Track on Emerging Applications of AI"))

    def test_ijcai_main_continues(self):
        from site_tracks import main_flags
        rows = [("Invited Speakers", "a"), ("Main track", "b"), ("Machine Learning S-Z", "c"), ("Search", "d"),
                ("AI for Good", "e"), ("Survey Track", "f"), ("Demo Track", "g")]
        self.assertEqual(main_flags("ijcai", rows), [False, True, True, True, False, False, False])


class SecurityRoboticsTest(unittest.TestCase):
    def test_workshop_volumes_are_not_main_track(self):
        tocs = {v["key"]: v["tocs"] for v in VENUES}
        self.assertTrue(any(re.fullmatch(p, "conf/sp/sp2024") for p in tocs["sp"]))
        self.assertFalse(any(re.fullmatch(p, "conf/sp/spw2024") for p in tocs["sp"]))
        self.assertFalse(any(re.fullmatch(p, "conf/ccs/ccsw2024") for p in tocs["ccs"]))

    def test_rss_proceedings_parse(self):
        import fetch_robotics
        page = ('<tr><td width=500>\n<a href="p007.html">Certified &amp; Safe Navigation</a><br>\n'
                '<i>Ada Lovelace, Alan Turing</i><br>\n</td></tr>').encode()
        fetch_robotics.fetch = lambda url, name, refresh=False: page
        rows = fetch_robotics.rss(2025)
        self.assertEqual([(r["key"], r["title"]) for r in rows], [("rss2025/p007", "Certified & Safe Navigation")])
        self.assertEqual([a["name"] for a in rows[0]["authors"]], ["Ada Lovelace", "Alan Turing"])
        self.assertEqual(rows[0]["url"], "https://www.roboticsproceedings.org/rss21/p007.html")


class DigestTest(unittest.TestCase):
    def test_resolution_order(self):
        import datetime as dt
        import digest
        d = dt.date
        one = [(d(2026, 1, 25), "", "u")]
        two = [(d(2025, 12, 17), "OOPSLA1", "a"), (d(2026, 6, 10), "OOPSLA2", "b")]
        row = {"accepted": "2026-02-02", "accepted_source": "s"}
        self.assertEqual(digest.resolve("iclr", 2026, row, one)["date"], d(2026, 2, 2))  # the paper's own date wins
        self.assertEqual(digest.resolve("iclr", 2026, {}, one), {"date": d(2026, 1, 25), "approx": False, "cycle": "", "source": "u"})
        self.assertEqual(digest.resolve("oopsla", 2026, {}, two, issue="OOPSLA1")["date"], d(2025, 12, 17))  # named round
        r = digest.resolve("oopsla", 2026, {}, two, today=d(2026, 3, 1))  # unknown round: latest so far, approximate
        self.assertEqual((r["date"], r["approx"]), (d(2025, 12, 17), True))
        self.assertIsNone(digest.resolve("cav", 2026, {}, None))  # no date: never the conference month

    def test_record_survives_key_change(self):
        import digest
        site = {"venue": "neurips", "year": 2026, "title": "Verifying Things", "key": "openreview/abc"}
        dblp = {**site, "key": "conf/nips/X26", "title": "Verifying things."}
        self.assertEqual(digest.ident(site["venue"], site["year"], site["title"]),
                         digest.ident(dblp["venue"], dblp["year"], dblp["title"]))
