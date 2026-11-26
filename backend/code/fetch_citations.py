import argparse
import datetime
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

from common import all_papers, JSON_DIR, PAPERS, TOPICS, norm_title, read_csv, read_json, read_jsonl_gz, write_json

API = "https://api.openalex.org/works"
SELECT = "id,doi,title,publication_year,cited_by_count"
USER_AGENT = "awesome-nnv/1.0 (research statistics script)"
CITATIONS = JSON_DIR / "citations.json"
KEY = os.environ.get("OPENALEX_API_KEY")


def call(params):
    params = {**params, "select": SELECT, "per-page": 50}
    if KEY:
        params["api_key"] = KEY
    req = urllib.request.Request(f"{API}?{urllib.parse.urlencode(params)}", headers={"User-Agent": USER_AGENT})
    err = ""
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)["results"]
        except urllib.error.HTTPError as e:
            err = f"HTTP {e.code}"
            if e.code in (400, 404):
                break
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            err = str(e).replace(KEY or "\0", "***")
        time.sleep(3 * 2 ** attempt)
    print(f"  warning: OpenAlex did not answer: {err}", file=sys.stderr)
    return None


def search_text(title):
    return " ".join(re.sub(r"[^A-Za-z0-9]+", " ", title).split())


def versions(p):
    found = call({"filter": f"title.search:{search_text(p['title'])},"
                            f"publication_year:{p['year'] - 2}-{p['year'] + 1}"})
    if found is None:
        return None
    want = norm_title(p["title"])
    return [w for w in found if norm_title(w.get("title") or "") == want]


def main():
    ap = argparse.ArgumentParser(description="Read citation counts of the NNV papers from OpenAlex (run as zsh -ic so that OPENALEX_API_KEY is set).")
    ap.add_argument("--refresh", action="store_true", help="read every paper again, not only missing ones")
    args = ap.parse_args()
    if not KEY:
        print("  note: OPENALEX_API_KEY is not set; OpenAlex may limit the requests", file=sys.stderr)
    yes = {r["key"] for r in read_csv(TOPICS) if r["decision"] == "yes"}
    papers = [p for p in all_papers() if p["key"] in yes]
    known = {} if args.refresh else read_json(CITATIONS, {})
    todo = [p for p in papers if p["key"] not in known]
    by_doi = {}
    with_doi = [p for p in todo if p["doi"]]
    for k in range(0, len(with_doi), 40):
        chunk = with_doi[k:k + 40]
        for w in call({"filter": "doi:" + "|".join(p["doi"] for p in chunk)}) or []:
            by_doi[(w.get("doi") or "").split("doi.org/")[-1].lower()] = w
        time.sleep(0.2)
    stamp = datetime.date.today().isoformat()
    for n, p in enumerate(todo, 1):
        works = versions(p)
        if works is None:
            continue
        if p["doi"] in by_doi:
            works.append(by_doi[p["doi"]])
        unique = {w["id"]: w for w in works}
        if unique:
            arxiv = next((d.split("arxiv.")[-1] for w in unique.values()
                          for d in [(w.get("doi") or "").lower()] if "10.48550/arxiv." in d), "")
            known[p["key"]] = {"citations": sum(w["cited_by_count"] or 0 for w in unique.values()), "arxiv": arxiv,
                               "openalex": sorted(i.rsplit("/", 1)[-1] for i in unique),
                               "matched": "doi+title" if p["doi"] in by_doi else "title", "fetched": stamp}
        else:
            print(f"  no match: {p['key']} {p['title'][:70]}", file=sys.stderr)
        if n % 100 == 0:
            print(f"  {n}/{len(todo)} papers", file=sys.stderr)
            write_json(CITATIONS, dict(sorted(known.items())))
        time.sleep(0.12)
    write_json(CITATIONS, dict(sorted(known.items())))
    print(f"{sum(1 for p in papers if p['key'] in known)}/{len(papers)} papers with a citation count", file=sys.stderr)


if __name__ == "__main__":
    main()
