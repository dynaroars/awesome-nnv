import argparse
import collections
import datetime
import json
import math
import sys

import charts
import graph
from common import (all_papers, display_title, conference_month, TRACK_MIN, LABEL_MIN, slugify, dblp_name, VIRTUAL_COVERAGE, AREA_KEYS, JSON_DIR, assign_ids, held, AREA_NAME, AREAS, CANDIDATES, FIELD_OF, FIELDS, FRONTEND, GROUPS_CSV, LAST_YEAR,
                    PAPERS, PEOPLE_JSON, ROSTER, SCORED_FIELDS, TOPICS, VENUE_KEYS, VENUE_NAME, VENUES, WORK, YEARS,
                    norm_name, read_csv, read_json, read_jsonl_gz, split_list, write_json)

CONTENT = FRONTEND / "content"
DATA = FRONTEND / "data"
FIELD_NAME = {f["key"]: f["name"] for f in FIELDS}
HUES = 8
SHAPES = ["circle", "square", "diamond", "triangle"]


def assign_marks(out, groups, papers):
    labelled = [g for g in out if len(g["members"]) >= LABEL_MIN or groups[g["slug"]].get("legend") == "yes"]
    labelled.sort(key=lambda g: (-len(g["members"]), -g["score"], g["name"]))
    members = {g["slug"]: {m["slug"] for m in g["members"]} for g in labelled}
    shared = collections.Counter()
    for p in papers:
        present = [s for s, ms in members.items() if ms & set(p["slugs"])]
        for a in present:
            for b in present:
                if a != b:
                    shared[(a, b)] += 1
    by_hue, marks = collections.defaultdict(list), {}
    for k, g in enumerate(labelled):
        shape = SHAPES[min(k // HUES, len(SHAPES) - 1)]
        taken = {hue for hue, sh in marks.values() if sh == shape}
        free = [h for h in range(1, HUES + 1) if h not in taken] or list(range(1, HUES + 1))
        hue = min(free, key=lambda h: (sum(shared[(g["slug"], o)] for o in by_hue[h]), h))
        by_hue[hue].append(g["slug"])
        marks[g["slug"]] = (hue, shape)
    order = {g["slug"]: k for k, g in enumerate(labelled)}
    for g in out:
        g["color"] = g["slug"] if g["slug"] in marks else "other"
        g["hue"], g["shape"] = marks.get(g["slug"], (0, "circle"))
        g["filled"] = len(g["members"]) >= LABEL_MIN
        g["legend_order"] = order.get(g["slug"])


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
    for p in out:
        p["date"] = conference_month(p["venue"], p["year"])
    out.sort(key=lambda p: p["title"].lower())
    out.sort(key=lambda p: (p["date"], -VENUE_KEYS.index(p["venue"])), reverse=True)
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
    return {"id": p["id"], "key": p["key"], "date": p["date"], "venue": p["venue"], "venue_name": VENUE_NAME[p["venue"]], "year": p["year"],
            "field": FIELD_OF[p["venue"]], "title": display_title(p["title"]), "url": p["url"], "citations": p["citations"],
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


def logo_of(slug):
    for ext in ("svg", "png", "jpg"):
        if (FRONTEND / "static" / "img" / "groups" / f"{slug}.{ext}").exists():
            return f"img/groups/{slug}.{ext}"
    return ""


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
                    "logo": logo_of(slug), "chart": year_chart(f"{g['name']}: NNV papers per year by field", mine),
                    "paper_list": [paper_entry(p, names) for p in mine]})
    out = [g for g in out if g["members"]]
    out.sort(key=lambda g: (-g["score"], -g["papers"], g["name"]))
    assign_marks(out, groups, papers)
    return out


LEADING_MIN = 2


def top(items, key, n=10):
    ranked = [i for i in sorted(items, key=lambda i: (-key(i), -i["score"], i["name"])) if key(i) >= LEADING_MIN]
    cut = key(ranked[n - 1]) if len(ranked) >= n else 0
    return [i for k, i in enumerate(ranked) if k < n or (key(i) == cut and cut > LEADING_MIN)]


def build_areas(papers, researchers, groups, names):
    out = []
    for a in AREAS:
        mine = [p for p in papers if p["area"] == a["key"]]
        tagged = [p for p in papers if a["key"] in p["tags"]]
        out.append({**a, **counts(mine), "tagged": len(tagged), "total": len(mine) + len(tagged),
                    "chart": year_chart(f"{a['name']}: NNV papers per year by field", mine + tagged),
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


def add_panels(venues):
    for f in FIELDS:
        mine = [v for v in venues if v["field"] == f["key"]]
        top = charts.tidy_top(max([n for v in mine for n in v["years"].values()] + [1]))
        for v in mine:
            v["panel"] = charts.venue_panel(v["name"], f["key"], YEARS, v["years"], v["all_years"], v["missing"],
                                            v["not_held"], top)
            v["panel_top"] = top


def field_series(papers, present_only=False):
    series = [(f"ar-{f['key']}", f["name"], [sum(1 for p in papers if p["year"] == y and FIELD_OF[p["venue"]] == f["key"])
                                             for y in YEARS]) for f in FIELDS]
    return [s for s in series if sum(s[2])] if present_only else series


def year_chart(label, papers):
    return charts.stacked_columns(label, YEARS, field_series(papers, present_only=True))


def area_trends(papers):
    count = {a["key"]: [sum(1 for p in papers if p["year"] == y and (p["area"] == a["key"] or a["key"] in p["tags"]))
                        for y in YEARS] for a in AREAS}
    ranked = sorted(AREAS, key=lambda a: -sum(count[a["key"]]))
    series = [(f"hue{a['line'][0]} {a['line'][1]}", a["name"], count[a["key"]], a["key"]) for a in ranked]
    return charts.multi_lines("NNV papers per year by area", YEARS, series)


def overview(papers):
    areas = [("v1", a["name"], sum(1 for p in papers if p["area"] == a["key"])) for a in AREAS]
    trends = area_trends(papers)
    return {"years": charts.stacked_columns("NNV papers per year by field", YEARS, field_series(papers)),
            "areas": charts.hbars("NNV papers per area", areas), "area_trends": trends}


def write_stubs(section, items):
    folder = CONTENT / section
    folder.mkdir(parents=True, exist_ok=True)
    for old in folder.glob("*.md"):
        if not old.name.startswith("_index."):
            old.unlink()
    for key, title in items:
        stub = f"---\ntitle: {json.dumps(title, ensure_ascii=False)}\nkey: {json.dumps(key)}\n---\n"
        (folder / f"{key}.md").write_text(stub, encoding="utf-8")


def candidates(shown, hidden, count):
    rows = []
    for r in read_csv(CANDIDATES)[:400]:
        if r["status"] != "undecided" and slugify(r["name"]) in shown:
            continue
        rows.append({**r, "nnv_papers": int(r["nnv_papers"]), "last_author": int(r["last_author"]),
                     "first_author": int(r["first_author"]), "titles": r["titles"].split(" | ")})
    listed = {slugify(r["name"]) for r in rows}
    for r in hidden:
        if r["slug"] in listed:
            continue
        pids = split_list(r["dblp_pids"])
        rows.append({"status": f"on the roster, below {TRACK_MIN} papers", "pid": pids[0] if pids else "",
                     "name": r["name"], "group": r["group"], "nnv_papers": count[r["slug"]], "last_author": 0,
                     "first_author": 0, "first_year": "", "last_year": "", "venues": "", "affiliation": r["institution"],
                     "homepage": r["homepage"], "titles": []})
    return rows


def main():
    ap = argparse.ArgumentParser(description="Write the site data (frontend/data) and page stubs from the hand-kept tables.")
    ap.parse_args()
    warnings = []
    topics = load_topics(warnings)
    people, groups, by_pid, by_name = load_people(warnings)
    count = collections.Counter(s for p in nnv_papers(topics, by_pid, by_name) for s in p["slugs"])
    shown = {r["slug"] for r in people if count[r["slug"]] >= TRACK_MIN}
    hidden = [r for r in people if r["slug"] not in shown]
    people = [r for r in people if r["slug"] in shown]
    by_pid = {k: v for k, v in by_pid.items() if v in shown}
    by_name = {k: v for k, v in by_name.items() if v in shown}
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
    group_list = build_groups(groups, researchers, papers, names)
    mark = {g["slug"]: {k: g[k] for k in ("color", "hue", "shape", "filled")} for g in group_list}
    for r in researchers:
        r.update(mark.get(r["group"], {"color": "other", "hue": 0, "shape": "circle", "filled": False}))
    areas = build_areas(papers, researchers, group_list, names)
    venues = build_venues(papers, researchers, coverage, names)
    add_panels(venues)
    decided = {pid for r in read_csv(ROSTER) for pid in split_list(r["dblp_pids"])}
    gaps = [{"venue": VENUE_NAME[v["key"]], "years": v["missing"]} for v in venues if v["missing"]]
    meta = {"generated_date": datetime.date.today().isoformat(), "first_year": YEARS[0], "last_year": LAST_YEAR,
            "years": YEARS, "venues": [{"key": v["key"], "name": v["name"]} for v in VENUES],
            "fields": [{**f, "names": f["names"]} for f in FIELDS], "scored_fields": SCORED_FIELDS,
            "areas": [{"key": a["key"], "name": a["name"]} for a in AREAS],
            "label_min": LABEL_MIN, "papers": len(papers), "tracked_papers": sum(1 for p in papers if p["slugs"]),
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
    write_json(DATA / "candidates.json", candidates({r["slug"] for r in researchers}, hidden, count))
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
