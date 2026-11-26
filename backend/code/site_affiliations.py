import gzip
import json
import re
import sys

from common import FRONTEND, JSON_DIR, RAW, VIRTUAL_SITES, norm_name, norm_title, read_json, write_json
from fetch_dblp import fetch

OUT = JSON_DIR / "site_affiliations.json"
FIRST_SITE_YEAR = 2020  # the conference sites publish these lists from 2020
# A department or school with no university named ("Department of Computer Science") says nothing on its own.
UNIT = re.compile(r"^\s*(?:the\s+)?(?:(?:machine learning )?department|school|faculty|division|college of)\b", re.I)


def generic(inst):
    return bool(UNIT.match(inst)) and not re.search(r"universit|institut|college\b", inst, re.I) \
        and not re.search(r"\b[A-Z]{3,}\b", inst)


def site_lists(years):
    """(venue, title) -> the authors with the institution each printed, from the ICML/NeurIPS/ICLR sites."""
    out = {}
    for venue, site in VIRTUAL_SITES.items():
        for year in years:
            path = RAW / f"virtual/{venue}-{year}.json.gz"
            data = gzip.decompress(path.read_bytes()) if path.exists() else fetch(
                f"{site}/static/virtual/data/{venue}-{year}-orals-posters.json", f"virtual/{venue}-{year}.json")
            if not data or not data.lstrip().startswith(b"{"):
                continue
            for r in json.loads(data).get("results", []):
                authors = [((a.get("fullname") or "").strip(), (a.get("institution") or "").strip())
                           for a in r.get("authors") or []]
                out.setdefault((venue, norm_title(r.get("name") or "")), authors)
    return out


def same_person(a, b):
    a, b = norm_name(a).split(), norm_name(b).split()
    return bool(a and b) and (a == b or (a[-1] == b[-1] and a[0][0] == b[0][0]))


def main():
    """Each listed researcher's institution as printed on their most recent ICML/NeurIPS/ICLR paper's conference
    page (as vn-ai-ranking reads affiliations): used when the roster and their OpenReview profile have none."""
    papers = read_json(FRONTEND / "data" / "papers.json", [])
    years = sorted({p["year"] for p in papers if p["venue"] in VIRTUAL_SITES and p["year"] >= FIRST_SITE_YEAR})
    lists = site_lists(years)
    found = {}
    for p in sorted(papers, key=lambda p: p["date"]):
        printed = lists.get((p["venue"], norm_title(p["title"])))
        if not printed:
            continue
        for a in p["authors"]:
            if not a["slug"]:
                continue
            inst = next((i for n, i in printed if i and same_person(n, a["name"]) and not generic(i)), "")
            if inst:  # later papers overwrite earlier ones: the most recent wins
                found[a["slug"]] = {"institution": inst, "year": p["year"], "venue": p["venue_name"],
                                    "paper": p["id"]}
    write_json(OUT, dict(sorted(found.items())))
    print(f"{len(found)} researchers with an institution from {len(years)} years of conference pages -> {OUT}",
          file=sys.stderr)


if __name__ == "__main__":
    main()
