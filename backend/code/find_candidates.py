import argparse
import collections
import datetime
import sys

from common import (CANDIDATES, GROUPS_CSV, PEOPLE_JSON, ROSTER, TOPICS, TRACK_MIN, VENUE_NAME, all_papers, read_csv,
                    read_json, slugify, split_list, write_csv)

FIELDS = ["status", "pid", "name", "group", "nnv_papers", "last_author", "first_author", "first_year", "last_year",
          "venues", "affiliation", "homepage", "titles"]


def nnv_papers():
    yes = {r["key"] for r in read_csv(TOPICS) if r["decision"] == "yes"}
    return [p for p in all_papers() if p["key"] in yes]


def author_stats(papers):
    stats = collections.defaultdict(lambda: {"papers": [], "last": 0, "first": 0, "name": ""})
    for p in papers:
        n = len(p["authors"])
        for k, a in enumerate(p["authors"]):
            if not a["pid"]:
                continue
            s = stats[a["pid"]]
            s["name"] = a["name"]
            s["papers"].append(p)
            s["first"] += k == 0
            s["last"] += k == n - 1 and n > 1
    return stats


def summary(papers):
    years = [p["year"] for p in papers]
    venues = collections.Counter(VENUE_NAME[p["venue"]] for p in papers)
    return {"nnv_papers": len(papers), "first_year": min(years), "last_year": max(years),
            "venues": "; ".join(f"{v} {n}" for v, n in venues.most_common()),
            "titles": " | ".join(p["title"] for p in sorted(papers, key=lambda p: -p["year"])[:3])}


def promote(stats, roster, groups):
    stamp = datetime.date.today().isoformat()
    pid_slug = {pid: r["slug"] for r in roster if r["approved"] == "yes" for pid in split_list(r["dblp_pids"])}
    slug_group = {r["slug"]: r["group"] for r in roster}
    decided = {pid for r in roster for pid in split_list(r["dblp_pids"])}
    known_groups = {g["slug"] for g in groups}
    added = []
    for pid, s in sorted(stats.items(), key=lambda x: (-len(x[1]["papers"]), x[1]["name"])):
        if pid in decided or len(s["papers"]) < TRACK_MIN:
            continue
        shared = collections.Counter()
        for p in s["papers"]:
            for g in {slug_group[pid_slug[a["pid"]]] for a in p["authors"] if a.get("pid") in pid_slug}:
                shared[g] += 1
        slug = slugify(s["name"])
        if shared:
            group, n = shared.most_common(1)[0]
            why = f"group by co-authorship ({n} shared NNV papers)"
        else:
            group = slug
            why = "no co-author on the list: own group"
            if group not in known_groups:
                groups.append({"slug": group, "name": f"{s['name']} group", "tools": "", "url": "", "description": "",
                               "legend": "", "notes": f"added automatically {stamp}, to confirm"})
                known_groups.add(group)
        roster.append({"approved": "yes", "slug": slug, "name": s["name"], "dblp_pids": pid, "aliases": "",
                       "group": group, "role": "", "institution": "", "institution_short": "", "homepage": "",
                       "to_confirm": f"added automatically ({len(s['papers'])} NNV papers); {why}; current post",
                       "notes": f"promoted from the candidates (2+ NNV papers) at the maintainer's request, {stamp}"})
        added.append(f"{s['name']} -> {group}")
    return added


def main():
    ap = argparse.ArgumentParser(description="Rank the authors of NNV papers who are not on the site: undecided authors and roster people below the threshold.")
    ap.add_argument("--min-papers", type=int, default=2, help="least NNV papers for an undecided author to be listed")
    ap.add_argument("--promote", action="store_true", help=f"add every undecided author with {TRACK_MIN}+ NNV papers to roster.csv")
    args = ap.parse_args()
    papers = nnv_papers()
    stats = author_stats(papers)
    roster = read_csv(ROSTER)
    if args.promote:
        groups = read_csv(GROUPS_CSV)
        added = promote(stats, roster, groups)
        write_csv(ROSTER, list(roster[0].keys()), roster)
        write_csv(GROUPS_CSV, list(groups[0].keys()), groups)
        print(f"{len(added)} authors promoted to roster.csv:\n  " + "\n  ".join(added), file=sys.stderr)
    people = read_json(PEOPLE_JSON, {})
    decided = {pid for r in roster for pid in split_list(r["dblp_pids"])}
    rows = []
    for r in roster:
        if r["approved"] != "yes":
            continue
        mine = {p["key"]: p for pid in split_list(r["dblp_pids"]) for p in stats.get(pid, {"papers": []})["papers"]}
        if not mine or len(mine) >= TRACK_MIN:
            continue
        pid = split_list(r["dblp_pids"])[0]
        s = stats[pid]
        info = people.get(pid, {})
        rows.append({"status": f"on the roster, below {TRACK_MIN} papers", "pid": pid, "name": r["name"], "group": r["group"],
                     "last_author": s["last"], "first_author": s["first"], **summary(list(mine.values())),
                     "affiliation": r["institution"] or info.get("primary") or "", "homepage": r["homepage"] or info.get("homepage", "")})
    for pid, s in stats.items():
        if pid in decided or len(s["papers"]) < args.min_papers:
            continue
        info = people.get(pid, {})
        rows.append({"status": "undecided", "pid": pid, "name": s["name"], "group": "", "last_author": s["last"],
                     "first_author": s["first"], **summary(s["papers"]),
                     "affiliation": info.get("primary") or "; ".join(info.get("affiliations", [])),
                     "homepage": info.get("homepage", "")})
    rows.sort(key=lambda r: (r["status"] != "undecided", -r["nnv_papers"], -r["last_author"], r["name"]))
    write_csv(CANDIDATES, FIELDS, rows)
    print(f"{sum(r['status'] == 'undecided' for r in rows)} undecided candidates with {args.min_papers}+ NNV papers, "
          f"{sum(r['status'] != 'undecided' for r in rows)} roster people below {TRACK_MIN}", file=sys.stderr)


if __name__ == "__main__":
    main()
