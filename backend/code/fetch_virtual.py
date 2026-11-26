import argparse
import collections
import html
import json
import re
import sys

from common import (LAST_YEAR, PAPERS, RAW, VIRTUAL, VIRTUAL_COVERAGE, VIRTUAL_SITES, read_jsonl_gz, virtual_track, write_json,
                    write_jsonl_gz)
from fetch_dblp import fetch


def parse(venue, year, data):
    rows = json.loads(data).get("results", [])
    has_source = sum(1 for r in rows if r.get("sourceurl")) > len(rows) / 2
    papers = {}
    for r in rows:
        title = html.unescape(r.get("name") or "").strip()
        authors = [{"name": html.unescape(a.get("fullname") or "").strip(), "dblp_name": "", "pid": "",
                    "inst": [x for x in [html.unescape(a.get("institution") or "").strip()] if x]}
                   for a in r.get("authors") or [] if (a.get("fullname") or "").strip()]
        if not title or not authors or virtual_track(title, r.get("sourceurl"), r.get("event_type"), has_source) != "main":
            continue
        forum = re.search(r"openreview\.net/forum\?id=([\w-]+)", r.get("paper_url") or "")
        key = f"openreview/{forum.group(1)}" if forum else f"{venue}{year}/{re.sub(r'[^a-z0-9]+', '', title.lower())[:60]}"
        url = (f"https://openreview.net/forum?id={forum.group(1)}" if forum
               else VIRTUAL_SITES[venue] + r["virtualsite_url"] if r.get("virtualsite_url") else "")
        papers.setdefault(key, {"key": key, "venue": venue, "year": year, "title": title, "doi": "", "pages": "",
                                "page_count": None, "url": url, "source": VIRTUAL_SITES[venue].split("//")[1],
                                "authors": authors})
    return list(papers.values())


def main():
    ap = argparse.ArgumentParser(description="Read the accepted main-track papers of venue-years that dblp does not list yet from the conference sites (neurips.cc, icml.cc, iclr.cc).")
    ap.add_argument("--refresh", action="store_true", help="download the lists again")
    args = ap.parse_args()
    listed = {(p["venue"], p["year"]) for p in read_jsonl_gz(PAPERS)}
    papers, coverage = [], collections.defaultdict(dict)
    for venue, site in VIRTUAL_SITES.items():
        for year in (LAST_YEAR, LAST_YEAR + 1):
            if (venue, year) in listed:
                continue
            data = fetch(f"{site}/static/virtual/data/{venue}-{year}-orals-posters.json", f"virtual/{venue}-{year}.json",
                         args.refresh)
            if not data or not data.lstrip().startswith(b"{"):
                (RAW / f"virtual/{venue}-{year}.json.gz").unlink(missing_ok=True)
                continue
            rows = parse(venue, year, data)
            if not rows:
                (RAW / f"virtual/{venue}-{year}.json.gz").unlink(missing_ok=True)
            else:
                papers.extend(rows)
                coverage[venue][str(year)] = {"papers": len(rows), "short": 0, "tocs": [site.split("//")[1]]}
                print(f"{venue} {year}: {len(rows)} main-track papers from {site}", file=sys.stderr)
    write_jsonl_gz(VIRTUAL, papers)
    write_json(VIRTUAL_COVERAGE, coverage)


if __name__ == "__main__":
    main()
