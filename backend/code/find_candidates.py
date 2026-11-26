import argparse
import collections
import sys

from common import (CANDIDATES, PAPERS, PEOPLE_JSON, ROSTER, TOPICS, VENUE_NAME, read_csv, read_json, read_jsonl_gz,
                    split_list, write_csv)

FIELDS = ["pid", "name", "nnv_papers", "last_author", "first_author", "first_year", "last_year", "venues",
          "affiliation", "homepage", "titles"]


def nnv_papers():
    yes = {r["key"] for r in read_csv(TOPICS) if r["decision"] == "yes"}
    return [p for p in read_jsonl_gz(PAPERS) if p["key"] in yes]


def main():
    ap = argparse.ArgumentParser(description="Rank the authors of NNV papers who are not yet decided in roster.csv.")
    ap.add_argument("--min-papers", type=int, default=2, help="least NNV papers to be listed")
    args = ap.parse_args()
    decided = set()
    for r in read_csv(ROSTER):
        decided.update(split_list(r["dblp_pids"]))
    people = read_json(PEOPLE_JSON, {})
    stats = collections.defaultdict(lambda: {"papers": [], "last": 0, "first": 0, "name": ""})
    for p in nnv_papers():
        n = len(p["authors"])
        for k, a in enumerate(p["authors"]):
            if not a["pid"]:
                continue
            s = stats[a["pid"]]
            s["name"] = a["name"]
            s["papers"].append(p)
            s["first"] += k == 0
            s["last"] += k == n - 1 and n > 1
    rows = []
    for pid, s in stats.items():
        if pid in decided or len(s["papers"]) < args.min_papers:
            continue
        years = [p["year"] for p in s["papers"]]
        venues = collections.Counter(VENUE_NAME[p["venue"]] for p in s["papers"])
        info = people.get(pid, {})
        rows.append({"pid": pid, "name": s["name"], "nnv_papers": len(s["papers"]), "last_author": s["last"],
                     "first_author": s["first"], "first_year": min(years), "last_year": max(years),
                     "venues": "; ".join(f"{v} {n}" for v, n in venues.most_common()),
                     "affiliation": info.get("primary") or "; ".join(info.get("affiliations", [])),
                     "homepage": info.get("homepage", ""),
                     "titles": " | ".join(p["title"] for p in sorted(s["papers"], key=lambda p: -p["year"])[:3])})
    rows.sort(key=lambda r: (-r["nnv_papers"], -r["last_author"], r["name"]))
    write_csv(CANDIDATES, FIELDS, rows)
    print(f"{len(rows)} candidates with {args.min_papers}+ NNV papers", file=sys.stderr)


if __name__ == "__main__":
    main()
