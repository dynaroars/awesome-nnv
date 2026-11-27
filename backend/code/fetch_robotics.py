"""Papers of robotics venue-years that dblp does not list (or lists only a few papers of): RSS from its own proceedings
site (roboticsproceedings.org), IROS from OpenAlex's record of the IEEE proceedings. Only venue-years where dblp has
fewer than MIN_LISTED papers are read; build_site_data.py then counts whichever source lists more papers."""
import argparse
import collections
import html
import json
import re
import sys
import urllib.parse

from common import (FIRST_YEAR, LAST_YEAR, MIN_PAGES, PAPERS, RAW, ROBOTICS, ROBOTICS_COVERAGE, page_count,
                    read_jsonl_gz, write_json, write_jsonl_gz)
from fetch_dblp import fetch

MIN_LISTED = 20
RSS = "https://www.roboticsproceedings.org"
OPENALEX = "https://api.openalex.org/works"
OPENALEX_SOURCE = {"iros": "S4393918188"}  # IEEE/RSJ International Conference on Intelligent Robots and Systems


def text(fragment):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", fragment))).strip()


def rss(year, refresh=False):
    """RSS proceedings: volume N is the conference of year 2004 + N; every listed paper is a main-track paper."""
    vol = year - 2004
    data = fetch(f"{RSS}/rss{vol:02d}/index.html", f"rss/rss{vol:02d}.html", refresh)
    if not data:
        return []
    out = []
    for num, title, names in re.findall(r'<a href="(p\d+)\.html">(.*?)</a>\s*<br>\s*<i>(.*?)</i>',
                                        data.decode("utf-8", "replace"), re.S):
        authors = [{"name": n.strip(), "dblp_name": "", "pid": "", "inst": []} for n in text(names).split(",") if n.strip()]
        if authors:
            out.append({"key": f"rss{year}/{num}", "venue": "rss", "year": year, "title": text(title), "doi": "",
                        "pages": "", "page_count": None, "url": f"{RSS}/rss{vol:02d}/{num}.html",
                        "source": "roboticsproceedings.org", "authors": authors})
    return out


def openalex(venue, year, refresh=False):
    """The proceedings papers OpenAlex lists for that venue-year; papers shorter than MIN_PAGES are left out."""
    out, page, pages = [], 1, 1
    while page <= pages:
        query = urllib.parse.urlencode({"filter": f"primary_location.source.id:{OPENALEX_SOURCE[venue]},publication_year:{year}",
                                        "per-page": 200, "page": page,
                                        "select": "id,doi,title,authorships,biblio,type"})
        data = fetch(f"{OPENALEX}?{query}", f"openalex/{venue}-{year}-{page}.json", refresh)
        if not data or not data.lstrip().startswith(b"{"):
            print(f"  warning: OpenAlex page {page} of {venue} {year} could not be read; its papers are missing",
                  file=sys.stderr)
            break
        body = json.loads(data)
        for w in body.get("results", []):
            b = w.get("biblio") or {}
            pages = f"{b.get('first_page') or ''}-{b.get('last_page') or ''}".strip("-")
            n = page_count(pages)
            authors = [{"name": (a.get("author") or {}).get("display_name", ""), "dblp_name": "", "pid": "",
                        "inst": [i["display_name"] for i in a.get("institutions") or [] if i.get("display_name")]}
                       for a in w.get("authorships") or []]
            authors = [a for a in authors if a["name"]]
            if not w.get("title") or not authors or (n is not None and n < MIN_PAGES):
                continue
            out.append({"key": f"openalex/{w['id'].rsplit('/', 1)[-1]}", "venue": venue, "year": year,
                        "title": text(w["title"]), "doi": (w.get("doi") or "").split("doi.org/")[-1].lower(),
                        "pages": pages, "page_count": n, "url": w.get("doi") or w["id"], "source": "openalex.org",
                        "authors": authors})
        pages = -(-(body.get("meta") or {}).get("count", 0) // 200)
        page += 1
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--refresh", action="store_true", help="download the lists again")
    args = ap.parse_args()
    listed = collections.Counter((p["venue"], p["year"]) for p in read_jsonl_gz(PAPERS))
    papers, coverage = [], collections.defaultdict(dict)
    for venue, reader, site in (("rss", rss, "roboticsproceedings.org"), ("iros", openalex, "openalex.org")):
        for year in range(FIRST_YEAR, LAST_YEAR + 1):
            if listed[(venue, year)] >= MIN_LISTED:
                continue
            rows = reader(year, args.refresh) if venue == "rss" else reader(venue, year, args.refresh)
            if rows:
                papers.extend(rows)
                coverage[venue][str(year)] = {"papers": len(rows), "short": 0, "tocs": [site]}
            print(f"{venue} {year}: {len(rows)} papers from {site} (dblp lists {listed[(venue, year)]})", file=sys.stderr)
    write_jsonl_gz(ROBOTICS, papers)
    write_json(ROBOTICS_COVERAGE, coverage)


if __name__ == "__main__":
    main()
