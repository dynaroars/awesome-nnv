import argparse
import collections
import datetime
import json
import math
import sys

import charts
import graph
from common import (all_papers, dblp_name, VIRTUAL_COVERAGE, AREA_KEYS, JSON_DIR, assign_ids, held, AREA_NAME, AREAS, CANDIDATES, FIELD_OF, FIELDS, FRONTEND, GROUPS_CSV, LAST_YEAR,
                    PAPERS, PEOPLE_JSON, ROSTER, SCORED_FIELDS, TOPICS, VENUE_KEYS, VENUE_NAME, VENUES, WORK, YEARS,
                    norm_name, read_csv, read_json, read_jsonl_gz, split_list, write_json)

CONTENT = FRONTEND / "content"
DATA = FRONTEND / "data"
GROUP_COLORS = 9
FIELD_NAME = {f["key"]: f["name"] for f in FIELDS}


def warn(warnings, text):
    warnings.append(text)
    print(f"warning: {text}", file=sys.stderr)


def load_topics(warnings):
    out = {}
    for r in read_csv(TOPICS):
        if r["decision"] != "yes":
            continue
        if r["area"] not in AREA_KEYS:
            warn(warnings, f"topics.csv: {r['key']} has no valid area ({r['area']!r})")
            continue
        tags = [t for t in split_list(r["tags"]) if t != r["area"]]
        for t in tags:
            if t not in AREA_KEYS:
                warn(warnings, f"topics.csv: {r['key']} has an unknown tag {t!r}")
        out[r["key"]] = {"area": r["area"], "tags": [t for t in tags if t in AREA_KEYS]}
    return out


def paper_url(p):
    return f"https://doi.org/{p['doi']}" if p.get("doi") else f"https://dblp.org/rec/{p['key']}"


def load_people(warnings):
    dblp = read_json(PEOPLE_JSON, {})
    groups = {g["slug"]: g for g in read_csv(GROUPS_CSV)}
    people, by_pid, by_name = [], {}, {}
    for r in read_csv(ROSTER):
        if r["approved"] != "yes":
            continue
        if r["group"] not in groups:
            warn(warnings, f"roster.csv: {r['slug']} is in an unknown group {r['group']!r}")
        pids = split_list(r["dblp_pids"])
        if not pids:
            warn(warnings, f"roster.csv: {r['slug']} has no DBLP pid")
        for pid in pids:
            by_pid[pid] = r["slug"]
        for name in [r["name"], *split_list(r["aliases"]), *(dblp_name(dblp.get(pid, {}).get("name", "")) for pid in pids)]:
            if name:
                by_name[norm_name(name)] = r["slug"]
        people.append(r)
    return people, groups, by_pid, by_name


def nnv_papers(topics, by_pid, by_name):
    cites = read_json(JSON_DIR / "citations.json", {})
    out = []
    for p in all_papers():
        t = topics.get(p["key"])
        if not t:
            continue
        authors = []
        for a in p["authors"]:
            slug = by_pid.get(a["pid"]) if a.get("pid") else by_name.get(norm_name(a["name"]))
            authors.append({"name": a["name"], "slug": slug or ""})
        out.append({**p, **t, "authors": authors, "url": p.get("url") or paper_url(p),
                    "citations": cites[p["key"]]["citations"] if p["key"] in cites else None,
                    "arxiv": cites.get(p["key"], {}).get("arxiv", ""),
                    "by_name": [a["slug"] for a, src in zip(authors, p["authors"]) if a["slug"] and not src.get("pid")],
                    "source": p.get("source", "dblp.org"),
                    "slugs": list(dict.fromkeys(a["slug"] for a in authors if a["slug"]))})
    assign_ids(out)
    out.sort(key=lambda p: (-p["year"], VENUE_KEYS.index(p["venue"]), p["title"].lower()))
    return out


def counts(papers):
    return {"papers": len(papers), "citations": sum(p["citations"] or 0 for p in papers),
            "venues": {v: n for v, n in collections.Counter(p["venue"] for p in papers).items()},
            "fields": {f["key"]: sum(1 for p in papers if FIELD_OF[p["venue"]] == f["key"]) for f in FIELDS},
            "areas": {a: sum(1 for p in papers if p["area"] == a) for a in AREA_KEYS},
            "years": {str(y): sum(1 for p in papers if p["year"] == y) for y in YEARS}}


def share(p):
    return 1 / max(len(p["authors"]), 1)


def score_fields(papers, members):
    out = {f: 0.0 for f in SCORED_FIELDS}
    for p in papers:
        f = FIELD_OF[p["venue"]]
        if f in out:
            out[f] += share(p) * sum(1 for s in p["slugs"] if s in members)
    return {f: round(v, 3) for f, v in out.items()}


def geomean(values):
    return round(math.prod(v + 1 for v in values) ** (1 / len(values)), 3)


def paper_entry(p, names):
    return {"id": p["id"], "key": p["key"], "venue": p["venue"], "venue_name": VENUE_NAME[p["venue"]], "year": p["year"],
            "field": FIELD_OF[p["venue"]], "title": p["title"], "url": p["url"], "citations": p["citations"],
            "arxiv": p["arxiv"], "source": p["source"],
            "area": p["area"],
            "area_name": AREA_NAME[p["area"]], "tags": [{"key": t, "name": AREA_NAME[t]} for t in p["tags"]],
            "authors": [{"name": names.get(a["slug"], a["name"]), "slug": a["slug"]} for a in p["authors"]]}


def institution(r, info):
    dblp = info.get("primary", "")
    local = r["institution"] or dblp
    local_short = r["institution_short"] or local.split(",")[0]
    if "current post" in r["to_confirm"] or not r["institution"]:
        public, public_short = dblp, dblp.split(",")[0]
    else:
        public, public_short = r["institution"], r["institution_short"] or r["institution"]
    return {"institution": public, "institution_short": public_short,
            "institution_local": local, "institution_local_short": local_short}


def build_researchers(people, groups, papers, dblp_people):
    by_slug = collections.defaultdict(list)
    for p in papers:
        for s in p["slugs"]:
            by_slug[s].append(p)
    names = {r["slug"]: r["name"] for r in people}
    out = []
    for r in people:
        mine = by_slug.get(r["slug"], [])
        sf = score_fields(mine, {r["slug"]})
        co = collections.Counter(s for p in mine for s in p["slugs"] if s != r["slug"])
        g = groups.get(r["group"], {})
        pids = split_list(r["dblp_pids"])
        info = dblp_people.get(pids[0], {}) if pids else {}
        out.append({
            "slug": r["slug"], "name": r["name"], "group": r["group"], "group_name": g.get("name", r["group"]),
            "role": r["role"], **institution(r, info),
            "homepage": r["homepage"] or info.get("homepage", ""), "orcid": info.get("orcid", ""),
            "dblp": [f"https://dblp.org/pid/{p}.html" for p in pids], "to_confirm": r["to_confirm"],
            **counts(mine), "score_fields": sf, "score": round(sum(sf.values()), 3),
            "first_author": sum(1 for p in mine if p["authors"] and p["authors"][0]["slug"] == r["slug"]),
            "last_author": sum(1 for p in mine if len(p["authors"]) > 1 and p["authors"][-1]["slug"] == r["slug"]),
            "coauthors": [{"slug": s, "name": names[s], "papers": n} for s, n in co.most_common()],
            "paper_list": [paper_entry(p, names) for p in mine],
        })
    out.sort(key=lambda r: (-r["score"], -r["papers"], r["name"]))
    return out, names


def build_groups(groups, researchers, papers, names):
    out = []
    for slug, g in groups.items():
        members = [r for r in researchers if r["group"] == slug]
        ids = {r["slug"] for r in members}
        mine = [p for p in papers if ids & set(p["slugs"])]
        sf = score_fields(mine, ids)
        out.append({"slug": slug, "name": g["name"], "tools": split_list(g["tools"]), "url": g["url"],
                    "description": g["description"],
                    "members": [{"slug": r["slug"], "name": r["name"], "institution_short": r["institution_short"],
                                 "papers": r["papers"], "score": r["score"]} for r in members],
                    "institutions": list(dict.fromkeys(r["institution_short"] for r in members if r["institution_short"])),
                    **counts(mine), "score_fields": sf, "score": geomean(sf.values()),
                    "paper_list": [paper_entry(p, names) for p in mine]})
    out = [g for g in out if g["members"]]
    out.sort(key=lambda g: (-g["score"], -g["papers"], g["name"]))
    pinned = [g["slug"] for g in out if groups[g["slug"]].get("legend") == "yes"]
    colored = set(pinned[:GROUP_COLORS])
    colored |= set([g["slug"] for g in out if g["slug"] not in colored][:GROUP_COLORS - len(colored)])
    k = 0
    for g in out:
        if g["slug"] in colored:
            g["color"], k = f"g{k}", k + 1
        else:
            g["color"] = "g-other"
    return out


def top(items, key, n=10):
    ranked = [i for i in sorted(items, key=lambda i: (-key(i), -i["score"], i["name"])) if key(i)]
    cut = key(ranked[n - 1]) if len(ranked) >= n else 0
    return [i for k, i in enumerate(ranked) if k < n or key(i) == cut]


def build_areas(papers, researchers, groups, names):
    out = []
    for a in AREAS:
        mine = [p for p in papers if p["area"] == a["key"]]
        tagged = [p for p in papers if a["key"] in p["tags"]]
        out.append({**a, **counts(mine), "tagged": len(tagged),
                    "tracked": sum(1 for p in mine if p["slugs"]),
                    "researchers": [{"slug": r["slug"], "name": r["name"], "papers": r["areas"][a["key"]],
                                     "group": r["group"], "group_name": r["group_name"]}
                                    for r in top(researchers, lambda r: r["areas"][a["key"]])],
                    "groups": [{"slug": g["slug"], "name": g["name"], "papers": g["areas"][a["key"]]}
                               for g in top(groups, lambda g: g["areas"][a["key"]])],
                    "paper_list": [paper_entry(p, names) for p in mine + tagged]})
    return out


def build_venues(papers, researchers, coverage, names):
    out = []
    for v in VENUES:
        mine = [p for p in papers if p["venue"] == v["key"]]
        cov = coverage.get(v["key"], {})
        totals = {str(y): cov.get(str(y), {}).get("papers", 0) for y in YEARS}
        out.append({"key": v["key"], "name": v["name"], "full_name": v["full_name"], "field": FIELD_OF[v["key"]],
                    "field_name": FIELD_NAME[FIELD_OF[v["key"]]], **counts(mine), "all_years": totals,
                    "all_papers": sum(totals.values()),
                    "share": round(100 * len(mine) / max(sum(totals.values()), 1), 2),
                    "missing": [y for y in YEARS if not totals[str(y)] and held(v["key"], y)],
                    "not_held": [y for y in YEARS if not held(v["key"], y)],
                    "researchers": [{"slug": r["slug"], "name": r["name"], "papers": r["venues"].get(v["key"], 0)}
                                    for r in top(researchers, lambda r: r["venues"].get(v["key"], 0))],
                    "paper_list": [paper_entry(p, names) for p in mine]})
    return out


def overview(papers):
    by_field = [(f"ar-{f['key']}", f["name"], [sum(1 for p in papers if p["year"] == y and FIELD_OF[p["venue"]] == f["key"])
                                               for y in YEARS]) for f in FIELDS]
    areas = [("v1", a["name"], sum(1 for p in papers if p["area"] == a["key"])) for a in AREAS]
    return {"years": charts.stacked_columns("NNV papers per year by field", YEARS, by_field),
            "areas": charts.hbars("NNV papers per area", areas)}


def write_stubs(section, items):
    folder = CONTENT / section
    folder.mkdir(parents=True, exist_ok=True)
    for old in folder.glob("*.md"):
        if not old.name.startswith("_index."):
            old.unlink()
    for key, title in items:
        stub = f"---\ntitle: {json.dumps(title, ensure_ascii=False)}\nkey: {json.dumps(key)}\n---\n"
        (folder / f"{key}.md").write_text(stub, encoding="utf-8")


def candidates(decided):
    rows = []
    for r in read_csv(CANDIDATES)[:300]:
        if r["pid"] in decided:
            continue
        rows.append({**r, "nnv_papers": int(r["nnv_papers"]), "last_author": int(r["last_author"]),
                     "first_author": int(r["first_author"]), "titles": r["titles"].split(" | ")})
    return rows


def main():
    ap = argparse.ArgumentParser(description="Write the site data (frontend/data) and page stubs from the hand-kept tables.")
    ap.parse_args()
    warnings = []
    topics = load_topics(warnings)
    people, groups, by_pid, by_name = load_people(warnings)
    papers = nnv_papers(topics, by_pid, by_name)
    for p in papers:
        for slug in p["by_name"]:
            warn(warnings, f"name match to check: {slug} on {p['key']} ({VENUE_NAME[p['venue']]} {p['year']}) {p['title'][:60]}")
    missing = set(topics) - {p["key"] for p in papers}
    if missing:
        warn(warnings, f"{len(missing)} papers in topics.csv are not in the fetched lists: {sorted(missing)[:5]}")
    dblp_people = read_json(PEOPLE_JSON, {})
    coverage = read_json(WORK / "coverage.json", {})
    from_sites = read_json(VIRTUAL_COVERAGE, {})
    for venue, years in from_sites.items():
        for y, c in years.items():
            coverage.setdefault(venue, {}).setdefault(y, c)
    researchers, names = build_researchers(people, groups, papers, dblp_people)
    for r in researchers:
        if not r["papers"]:
            warn(warnings, f"{r['name']} has no NNV paper")
    group_list = build_groups(groups, researchers, papers, names)
    color = {g["slug"]: g["color"] for g in group_list}
    for r in researchers:
        r["color"] = color.get(r["group"], "g-other")
    areas = build_areas(papers, researchers, group_list, names)
    venues = build_venues(papers, researchers, coverage, names)
    decided = {pid for r in read_csv(ROSTER) for pid in split_list(r["dblp_pids"])}
    gaps = [{"venue": VENUE_NAME[v["key"]], "years": v["missing"]} for v in venues if v["missing"]]
    meta = {"generated_date": datetime.date.today().isoformat(), "first_year": YEARS[0], "last_year": LAST_YEAR,
            "years": YEARS, "venues": [{"key": v["key"], "name": v["name"]} for v in VENUES],
            "fields": [{**f, "names": f["names"]} for f in FIELDS], "scored_fields": SCORED_FIELDS,
            "areas": [{"key": a["key"], "name": a["name"]} for a in AREAS],
            "papers": len(papers), "tracked_papers": sum(1 for p in papers if p["slugs"]),
            "researchers": sum(1 for r in researchers if r["papers"]), "groups": len(group_list), "gaps": gaps,
            "from_sites": [{"venue": VENUE_NAME[v], "year": int(y), "site": c["tocs"][0]}
                           for v, ys in from_sites.items() for y, c in ys.items()
                           if coverage[v][y] is c]}
    researchers = [r for r in researchers if r["papers"]]
    write_json(DATA / "meta.json", meta)
    write_json(DATA / "researchers.json", researchers)
    write_json(DATA / "groups.json", group_list)
    write_json(DATA / "areas.json", areas)
    write_json(DATA / "venues.json", venues)
    write_json(DATA / "papers.json", [{**paper_entry(p, names), "tracked": bool(p["slugs"])} for p in papers])
    write_json(DATA / "overview.json", overview(papers))
    write_json(DATA / "graph.json", graph.layout(researchers, group_list, papers))
    write_json(DATA / "candidates.json", candidates(decided))
    write_stubs("researchers", [(r["slug"], r["name"]) for r in researchers])
    write_stubs("groups", [(g["slug"], g["name"]) for g in group_list])
    write_stubs("areas", [(a["key"], a["name"]) for a in AREAS])
    write_stubs("conferences", [(v["key"], v["name"]) for v in VENUES])
    WORK.mkdir(parents=True, exist_ok=True)
    (WORK / "build_report.txt").write_text("\n".join(warnings) + "\n", encoding="utf-8")
    print(f"{len(papers)} NNV papers, {meta['tracked_papers']} with a listed researcher, {len(researchers)} researchers, "
          f"{len(group_list)} groups, {len(warnings)} warnings", file=sys.stderr)


if __name__ == "__main__":
    main()
