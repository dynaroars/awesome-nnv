import argparse
import collections
import gzip
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

from common import (FIRST_YEAR, LAST_YEAR, MIN_PAGES, OFF_TRACKS, PAPERS, RAW, VENUES, VIRTUAL_SITES, WORK, dblp_name,
                    norm_title, not_a_paper, page_count, virtual_track, write_json, write_jsonl_gz)

USER_AGENT = "awesome-nnv/1.0 (research statistics script)"
DBLP_SPARQL = "https://sparql.dblp.org/sparql"
PREFIX = "PREFIX dblp: <https://dblp.org/rdf/schema#> PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#> "


def fetch(url, name, refresh=False, headers=None):
    path = RAW / (name + ".gz")
    if path.exists() and not refresh:
        return gzip.decompress(path.read_bytes())
    path.parent.mkdir(parents=True, exist_ok=True)
    print(f"  downloading {name}", file=sys.stderr)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, **(headers or {})})
    err = None
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=600) as r:
                data = r.read()
            break
        except urllib.error.HTTPError as e:
            err = e
            if e.code in (403, 404, 410):
                return None
            time.sleep(5 * (attempt + 1))
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            err = e
            time.sleep(5 * (attempt + 1))
    else:
        print(f"  warning: could not download {name}: {err}", file=sys.stderr)
        return None
    path.write_bytes(gzip.compress(data))
    time.sleep(1)
    return data


def stale(name, days=7):
    path = RAW / (name + ".gz")
    return not path.exists() or time.time() - path.stat().st_mtime > days * 86400


def sparql(query, name, refresh=False):
    data = fetch(f"{DBLP_SPARQL}?{urllib.parse.urlencode({'query': PREFIX + query})}", name, refresh,
                 headers={"Accept": "application/sparql-results+json"})
    if not data:
        return []
    return [{k: v["value"] for k, v in row.items()} for row in json.loads(data)["results"]["bindings"]]


def stream_tocs(stream, refresh=False):
    query = (f"SELECT ?toc ?iss (MIN(?y) AS ?year) (COUNT(?p) AS ?n) WHERE {{ "
             f"?p dblp:publishedInStream <https://dblp.org/streams/conf/{stream}> ; dblp:yearOfPublication ?y ; "
             f"dblp:listedOnTocPage ?toc . OPTIONAL {{ ?p dblp:publishedInJournalVolumeIssue ?iss }} "
             f"FILTER(STR(?y) >= \"{FIRST_YEAR}\") }} GROUP BY ?toc ?iss")
    return sparql(query, f"dblp/tocs/{stream}.json", refresh)


def toc_papers(stream, toc, issue, name, refresh=False):
    issue_filter = f'?p dblp:publishedInJournalVolumeIssue "{issue}" . ' if issue else ""
    query = ("SELECT ?p ?type ?title ?doi ?pages ?y ?ord ?pid ?name ?inst ?instname WHERE { "
             f"?p dblp:listedOnTocPage <https://dblp.org/db/{toc}> ; "
             f"dblp:publishedInStream <https://dblp.org/streams/conf/{stream}> ; "
             "a ?type ; dblp:title ?title ; dblp:yearOfPublication ?y ; dblp:hasSignature ?s . "
             f"{issue_filter}"
             "VALUES ?type { dblp:Inproceedings dblp:Article } "
             "?s a dblp:AuthorSignature ; dblp:signatureOrdinal ?ord ; dblp:signatureDblpName ?name . "
             "OPTIONAL { ?s dblp:signatureCreator ?pid } "
             "OPTIONAL { ?s dblp:signatureInstitution ?inst . ?inst rdfs:label ?instname } "
             "OPTIONAL { ?p dblp:doi ?doi } OPTIONAL { ?p dblp:pagination ?pages } }")
    return sparql(query, name, refresh)


def selected_tocs(venue, refresh=False):
    out = []
    for row in stream_tocs(venue["stream"], refresh):
        toc = row["toc"].replace("https://dblp.org/db/", "")
        issue = row.get("iss", "")
        label = f"{toc}#{issue}" if issue else toc
        for pattern in venue["tocs"]:
            m = re.fullmatch(pattern, label)
            if m:
                year = int(m.group(1)) if m.groups() else int(row["year"])
                if FIRST_YEAR <= year <= LAST_YEAR:
                    out.append({"toc": toc, "issue": issue, "year": year, "listed": int(row["n"])})
                break
    return sorted(out, key=lambda t: (t["year"], t["toc"], t["issue"]))


def parse(venue, year, rows):
    papers = {}
    for r in rows:
        key = r["p"].replace("https://dblp.org/rec/", "")
        p = papers.setdefault(key, {"title": r["title"], "doi": r.get("doi", ""), "pages": r.get("pages", ""),
                                    "authors": {}})
        ordinal = int(r["ord"])
        a = p["authors"].setdefault(ordinal, {"name": dblp_name(r["name"]), "dblp_name": r["name"],
                                              "pid": r.get("pid", "").replace("https://dblp.org/pid/", ""),
                                              "inst": []})
        if r.get("instname") and r["instname"] not in a["inst"]:
            a["inst"].append(r["instname"])
    out = []
    for key, p in sorted(papers.items()):
        out.append({"key": key, "venue": venue, "year": year, "title": re.sub(r"(?<!\.)\.$", "", p["title"]),
                    "doi": p["doi"].split("doi.org/")[-1].lower(), "pages": p["pages"],
                    "page_count": page_count(p["pages"]),
                    "authors": [a for _, a in sorted(p["authors"].items())]})
    return out


def off_track_titles(venue, year, refresh=False):
    """Titles that the conference site lists outside the main track (Datasets & Benchmarks, position papers): dblp
    files NeurIPS D&B (2022 on) and ICML position papers in the same proceedings as the main track."""
    site = VIRTUAL_SITES.get(venue)
    if not site or year < 2020:  # the sites publish these lists from 2020; D&B and position tracks came later
        return set()
    data = fetch(f"{site}/static/virtual/data/{venue}-{year}-orals-posters.json", f"virtual/{venue}-{year}.json",
                 refresh and year >= LAST_YEAR - 1)
    if not data or not data.lstrip().startswith(b"{"):
        return set()
    rows = json.loads(data).get("results", [])
    has_source = sum(1 for r in rows if r.get("sourceurl")) > len(rows) / 2
    return {norm_title(r.get("name")) for r in rows
            if virtual_track(r.get("name"), r.get("sourceurl"), r.get("event_type"), has_source) in OFF_TRACKS}


def collect(refresh=False, only=None):
    papers, coverage = [], collections.defaultdict(dict)
    for venue in VENUES:
        if only and venue["key"] not in only:
            continue
        for t in selected_tocs(venue, refresh):
            slug = re.sub(r"[^a-z0-9]+", "-", f"{t['toc']}-{t['issue']}".lower()).strip("-")
            name = f"dblp/{venue['key']}/{slug}.json"
            recent = refresh or (t["year"] >= LAST_YEAR - 1 and stale(name))
            parsed = parse(venue["key"], t["year"], toc_papers(venue["stream"], t["toc"], t["issue"], name, recent))
            if len(parsed) < 0.8 * t["listed"]:
                parsed = parse(venue["key"], t["year"], toc_papers(venue["stream"], t["toc"], t["issue"], name, True))
            if len(parsed) < 0.8 * t["listed"]:
                print(f"warning: {t['toc']} {t['issue']}: {len(parsed)} papers parsed, dblp lists {t['listed']}",
                      file=sys.stderr)
            off = off_track_titles(venue["key"], t["year"], refresh)
            papers_only = [p for p in parsed if not not_a_paper(venue["key"], p["title"]) and norm_title(p["title"]) not in off]
            kept = [p for p in papers_only if p["page_count"] is None or p["page_count"] >= MIN_PAGES]
            c = coverage[venue["key"]].setdefault(t["year"], {"papers": 0, "short": 0, "other_tracks": 0, "tocs": []})
            c["papers"] += len(kept)
            c["short"] += len(papers_only) - len(kept)
            c["other_tracks"] += len(parsed) - len(papers_only)
            c["tocs"].append(f"{t['toc']}#{t['issue']}" if t["issue"] else t["toc"])
            papers.extend(kept)
            print(f"{venue['name']} {t['year']} {t['toc']} {t['issue']}: {len(kept)} papers"
                  f" ({len(papers_only) - len(kept)} short, {len(parsed) - len(papers_only)} other tracks or not papers)", file=sys.stderr)
    return papers, coverage


def main():
    ap = argparse.ArgumentParser(description="Download the main-track papers of the tracked venues from DBLP.")
    ap.add_argument("--refresh", action="store_true", help="download every table of contents again")
    ap.add_argument("--only", nargs="*", help="venue keys to fetch")
    args = ap.parse_args()
    papers, coverage = collect(args.refresh, args.only)
    seen, unique = set(), []
    for p in papers:
        if p["key"] not in seen:
            seen.add(p["key"])
            unique.append(p)
    if not args.only:
        write_jsonl_gz(PAPERS, unique)
        write_json(WORK / "coverage.json", {v: {str(y): c for y, c in sorted(ys.items())} for v, ys in coverage.items()})
    print(f"{len(unique)} papers", file=sys.stderr)


if __name__ == "__main__":
    main()
