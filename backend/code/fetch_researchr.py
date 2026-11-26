import argparse
import collections
import difflib
import html
import re
import sys

from common import (LAST_YEAR, PAPERS, RESEARCHR, RESEARCHR_COVERAGE, RESEARCHR_TRACKS, norm_title, not_a_paper,
                    read_jsonl_gz, write_json, write_jsonl_gz)
from fetch_dblp import fetch, stale

SITE = "https://conf.researchr.org/track/"
ENTRY = re.compile(r'<a href="#" data-event-modal="([0-9a-f-]{36})">((?:(?!</a>).)*)</a>(?:</strong>)?\s*'
                   r'<div class="prog-track">([^<]*)</div>\s*<div class="performers">((?:(?!</div>).)*)</div>', re.S)
PERSON = re.compile(r'<a [^>]*class="navigate"[^>]*>(.*?)</a>(?:<span class="prog-aff">(.*?)</span>)?', re.S)
# Talks that are not this venue's own papers: journal-first and earlier-venue papers ("[TOPLAS] ...",
# "[SIGPLAN OOPSLA'25] ...", "(TOPLAS) ...").
OTHER_VENUE = re.compile(r"^\s*\[|\((?:TOPLAS|TOSEM|TSE|JFP)\)", re.I)
COMPLETE = 0.8  # dblp lists at least this share of the site's papers: the venue-year is taken from dblp alone
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; awesome-nnv research statistics script)"}


def text(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", s or ""))).strip()


def parse(venue, year, page, track, url):
    """The accepted papers of the main research track; a paper shows up several times (list, schedule), once per id."""
    papers = {}
    for mid, title, label, performers in ENTRY.findall(page):
        title = text(re.sub(r"<span.*", "", title, flags=re.S))
        if text(label) != track or mid in papers or OTHER_VENUE.search(title) or not_a_paper(venue, title):
            continue
        authors = [{"name": text(n), "dblp_name": "", "pid": "", "inst": [x for x in [text(a)] if x]}
                   for n, a in PERSON.findall(performers) if text(n)]
        if title and authors:
            papers[mid] = {"key": f"researchr/{venue}{year}/{mid}", "venue": venue, "year": year, "title": title,
                           "doi": "", "pages": "", "page_count": None, "url": url, "source": "conf.researchr.org",
                           "authors": authors}
    return list(papers.values())


def main():
    ap = argparse.ArgumentParser(description="Read the accepted main-track papers of the SE and PL venues from conf.researchr.org for this year and next year, for papers dblp does not list yet.")
    ap.add_argument("--refresh", action="store_true", help="download the lists again")
    args = ap.parse_args()
    dblp = list(read_jsonl_gz(PAPERS))
    listed = collections.Counter((p["venue"], p["year"]) for p in dblp)
    titles = collections.defaultdict(list)
    for p in dblp:
        titles[p["venue"]].append(norm_title(p["title"]))
    papers, coverage = [], collections.defaultdict(dict)
    for venue, (slug, track) in RESEARCHR_TRACKS.items():
        for year in (LAST_YEAR, LAST_YEAR + 1):
            path = slug.format(y=year)
            name = f"researchr/{path.replace('/', '_')}.html"
            data = fetch(SITE + path, name, args.refresh or stale(name), HEADERS)
            rows = parse(venue, year, (data or b"").decode("utf-8", "ignore"), track, SITE + path)
            if not rows or listed[(venue, year)] >= COMPLETE * len(rows):
                continue
            known = set(titles[venue])
            new = [p for p in rows if norm_title(p["title"]) not in known
                   and not difflib.get_close_matches(norm_title(p["title"]), titles[venue], n=1, cutoff=0.9)]
            papers.extend(new)
            coverage[venue][str(year)] = {"papers": len(rows), "short": 0, "tocs": ["conf.researchr.org"]}
            print(f"{venue} {year}: {len(rows)} main-track papers on conf.researchr.org, {len(new)} not in dblp "
                  f"(dblp lists {listed[(venue, year)]} for the year)", file=sys.stderr)
    write_jsonl_gz(RESEARCHR, papers)
    write_json(RESEARCHR_COVERAGE, coverage)


if __name__ == "__main__":
    main()
