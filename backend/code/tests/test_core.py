import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import build_site_data
from common import AREA_KEYS, FIELD_OF, assign_ids, scholar_id, VENUES, dblp_name, norm_name, page_count, split_list
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
                  {"venue": "nfm", "authors": [{}, {}], "slugs": ["a"]}]
        self.assertEqual(build_site_data.score_fields(papers, {"a"})["lv"], 0.25)
        self.assertEqual(build_site_data.score_fields(papers, {"a", "b"})["lv"], 0.5)
        self.assertNotIn("fm", build_site_data.score_fields(papers, {"a"}))

    def test_areas_known(self):
        self.assertIn("other", AREA_KEYS)


if __name__ == "__main__":
    unittest.main()
