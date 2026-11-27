import argparse
import collections
import datetime
import json
import math
import re
import sys

import charts
import digest
import graph
from common import (COUNTRY_NAME, country_of, CSV_DIR, RESEARCHR_COVERAGE, ROBOTICS_COVERAGE, FIRST_YEAR, all_papers, display_title, conference_month, TRACK_MIN, LABEL_MIN, slugify, dblp_name, VIRTUAL_COVERAGE, AREA_KEYS, JSON_DIR, assign_ids, held, AREA_NAME, AREAS, CANDIDATES, FIELD_OF, FIELDS, FRONTEND, GROUPS_CSV, LAST_YEAR,
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
    groups = {g["slug"]: {**g, "name": re.sub(r"\s*\([^()]*\)$", "", g["name"])} for g in read_csv(GROUPS_CSV)}
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
            authors.append({"name": a["name"], "slug": slug or "", "inst": a.get("inst") or []})
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
            "arxiv": p["arxiv"], "source": p["source"], "unofficial": bool(p.get("unofficial")), "issue": p.get("issue", ""),
            "area": p["area"],
            "area_name": AREA_NAME[p["area"]], "tags": [{"key": t, "name": AREA_NAME[t]} for t in p["tags"]],
            "authors": [{"name": names.get(a["slug"], a["name"]), "slug": a["slug"]} for a in p["authors"]]}


def institution(r, info, prof=None, site=None, signed=""):
    """Public: the roster's confirmed institution, else the current one on the person's own OpenReview profile, else
    the one printed on their latest ICML/NeurIPS/ICLR conference page, else dblp's (the person page's primary
    affiliation, else the one on their signature of their latest NNV paper). Local: the roster's, then the same
    fallbacks. The country goes with the institution shown."""
    prof = prof or {}
    dblp = info.get("primary", "") or signed
    fallback = prof.get("institution") or (site or {}).get("institution") or dblp
    local = r["institution"] or fallback
    local_short = r["institution_short"] or local.split(",")[0]
    if "current post" in r["to_confirm"] or not r["institution"]:
        public, public_short = fallback, fallback.split(",")[0]
    else:
        public, public_short = r["institution"], r["institution_short"] or r["institution"]

    def country(name):
        # A university's or institute's own name wins over the profile's country field, which can be stale (Si Liu
        # at CUHK listed as US); for companies, which are multinational, the profile's country stays.
        if country_of(name) and re.search(r"universit|college|institut|school|academy|polytechn|école|ecole", name, re.I):
            return country_of(name)
        if prof.get("institution") and name == prof["institution"] and prof.get("country"):
            return prof["country"]
        return country_of(name) or prof.get("country", "") or country_of(dblp) or next(
            (c for c in map(country_of, info.get("affiliations", [])) if c), "")

    return {"institution": public, "institution_short": public_short,
            "institution_local": local, "institution_local_short": local_short,
            "country": country(public), "country_local": country(local)}


def build_researchers(people, groups, papers, dblp_people):
    by_slug = collections.defaultdict(list)
    for p in papers:
        for s in p["slugs"]:
            by_slug[s].append(p)
    names = {r["slug"]: r["name"] for r in people}
    links = read_json(JSON_DIR / "profiles.json", {})
    printed = read_json(JSON_DIR / "site_affiliations.json", {})
    out = []
    for r in people:
        mine = by_slug.get(r["slug"], [])
        sf = score_fields(mine, {r["slug"]})
        co = collections.Counter(s for p in mine for s in p["slugs"] if s != r["slug"])
        g = groups.get(r["group"], {})
        pids = split_list(r["dblp_pids"])
        info = dblp_people.get(pids[0], {}) if pids else {}
        signed = next((a["inst"][0] for p in sorted(mine, key=lambda p: p["date"], reverse=True)
                       for a in p["authors"] if a["slug"] == r["slug"] and a.get("inst")), "")
        out.append({
            "slug": r["slug"], "name": r["name"], "group": r["group"], "group_name": g.get("name", r["group"]),
            "role": r["role"], **institution(r, info, links.get(r["slug"]), printed.get(r["slug"]), signed),
            "homepage": r["homepage"] or info.get("homepage", "") or links.get(r["slug"], {}).get("homepage", ""),
            "orcid": info.get("orcid", ""),
            "openreview": links.get(r["slug"], {}).get("openreview", ""), "scholar": links.get(r["slug"], {}).get("scholar", ""),
            "photo": photo_of(r["slug"]),
            "dblp": [f"https://dblp.org/pid/{p}.html" for p in pids], "to_confirm": r["to_confirm"],
            **counts(mine), "score_fields": sf, "score": round(sum(sf.values()), 3),
            "first_author": sum(1 for p in mine if p["authors"] and p["authors"][0]["slug"] == r["slug"]),
            "last_author": sum(1 for p in mine if len(p["authors"]) > 1 and p["authors"][-1]["slug"] == r["slug"]),
            "coauthors": [{"slug": s, "name": names[s], "papers": n} for s, n in co.most_common()],
            "paper_list": [paper_entry(p, names) for p in mine],
        })
    inherit_institutions(out)
    for r in out:
        recent = [p for p in by_slug.get(r["slug"], []) if p["recent"]]
        r["recent_papers"] = len(recent)
        r["recent_score"] = round(sum(score_fields(recent, {r["slug"]}).values()), 3)
    # The Researchers page ranks active people: this year's papers, then this year's score, then the all-year score.
    for k, r in enumerate(sorted(out, key=lambda r: (-r["recent_papers"], -r["recent_score"], -r["score"],
                                                    -r["papers"], r["name"]))):
        r["recent_rank"] = k
    # Group pages (the maintainer's order, 2026-11-27): this year's papers, this year's score, all-year papers,
    # all-year score, citations.
    for k, r in enumerate(sorted(out, key=lambda r: (-r["recent_papers"], -r["recent_score"], -r["papers"], -r["score"],
                                                    -(r.get("citations") or 0), r["name"]))):
        r["member_rank"] = k
    for r in out:
        r["institution_name"] = institution_name(r["institution"])
        r["institution_local_name"] = institution_name(r["institution_local"])
        r["group_label"] = group_label(r["group_name"], r["institution"], r["institution_short"])
        r["group_label_local"] = group_label(r["group_name"], r["institution_local"], r["institution_local_short"])
    out.sort(key=lambda r: (-r["score"], -r["papers"], r["name"]))
    return out, names


# Short names in group names ("Reliable AI Lab (UMD)") and the institution names they stand for.
SHORT_NAMES = {"UMD": r"maryland", "UIUC": r"illinois at urbana|illinois urbana|urbana-champaign|\buiuc\b|siebel school", "TUM": r"technical university of munich|"
               r"technische universität münchen", "CMU": r"carnegie mellon", "MIT": r"massachusetts institute of technology",
               "SMU": r"singapore management", "UCSD": r"san diego", "SFU": r"simon fraser", "USC": r"southern california",
               "WashU": r"washington university", "JHU": r"johns hopkins|whiting school", "UCI": r"irvine", "UT Austin": r"texas at austin",
               "Penn": r"university of pennsylvania", "Penn State": r"pennsylvania state|penn state",
               "UW-Madison": r"wisconsin", "ISTA": r"institute of science and technology austria|ist austria",
               "CMU/NASA": r"carnegie mellon|nasa", "Imperial": r"imperial college", "Tübingen": r"tübingen|tuebingen"}


def group_label(name, *institutions):
    """The group's name without its "(short name)" when the row's institution already says it."""
    m = re.match(r"^(.*\S)\s*\(([^()]+)\)$", name)
    if not m:
        return name
    short = m.group(2)
    for inst in institutions:
        if not inst:
            continue
        if short.lower() in inst.lower() or (short in SHORT_NAMES and re.search(SHORT_NAMES[short], inst, re.I)):
            return m.group(1)
    return name


# Institutions written out in full in the Institution column (the maintainer's rule: no abbreviations).
FULL_NAMES = {"Technische Universität München": "Technical University of Munich",
              "Institute of Software": "Institute of Software, Chinese Academy of Sciences",
              "Universität Köln": "University of Cologne", "Technische Universität Dortmund": "TU Dortmund University",
              "Universität Konstanz": "University of Konstanz", "Universität St. Gallen": "University of St. Gallen",
              "Università degli Studi di Verona": "University of Verona", "nanjing university": "Nanjing University",
              "saarland university": "Saarland University", "university Jean Jaurès": "University of Toulouse Jean Jaurès",
              "Rheinland-Pfälzische Technische Universität": "RPTU Kaiserslautern-Landau",
              "UIUC": "University of Illinois Urbana-Champaign", "UMD": "University of Maryland",
              "CMU": "Carnegie Mellon University", "MIT": "Massachusetts Institute of Technology",
              "UCSB": "University of California, Santa Barbara", "UCLA": "University of California, Los Angeles",
              "UC Berkeley": "University of California, Berkeley", "UCSD": "University of California San Diego",
              "UT Austin": "University of Texas at Austin", "UW Madison": "University of Wisconsin–Madison",
              "NYU": "New York University", "LSE": "London School of Economics and Political Science",
              "KAIST": "Korea Advanced Institute of Science and Technology", "Oxford": "University of Oxford",
              "EPFL": "École Polytechnique Fédérale de Lausanne", "TU Delft": "Delft University of Technology",
              "TU Wien": "Vienna University of Technology", "IST Austria": "Institute of Science and Technology Austria",
              "ISTA": "Institute of Science and Technology Austria", "Technion": "Technion – Israel Institute of Technology",
              "CISPA": "CISPA Helmholtz Center for Information Security", "DeepMind": "Google DeepMind",
              "Deepmind": "Google DeepMind", "ANITI": "Artificial and Natural Intelligence Toulouse Institute",
              "IRIT": "Institut de Recherche en Informatique de Toulouse",
              "LAAS-CNRS": "Laboratoire d'Analyse et d'Architecture des Systèmes (CNRS)",
              "LAAS / CNRS": "Laboratoire d'Analyse et d'Architecture des Systèmes (CNRS)",
              "ETHZ - ETH Zurich": "ETH Zurich", "CNRS": "French National Centre for Scientific Research", "VMWare": "VMware", "GMU": "George Mason University",
              "ECNU": "East China Normal University", "SMU": "Singapore Management University",
              "TUM": "Technical University of Munich", "JHU": "Johns Hopkins University", "HUJI": "Hebrew University of Jerusalem",
              "USC": "University of Southern California", "SFU": "Simon Fraser University", "NUS": "National University of Singapore",
              "PKU": "Peking University", "UCI": "University of California, Irvine", "WashU": "Washington University in St. Louis",
              "Siebel School of Computing and Data Science": "University of Illinois Urbana-Champaign",
              "Whiting School of Engineering": "Johns Hopkins University",
              "Software Engineering Institute": "Software Engineering Institute, Carnegie Mellon University",
              "Tsinghua Univiersity": "Tsinghua University", "university Paul Sabatier": "Université Paul Sabatier",
              "Karlsruhe Institute of Technologie": "Karlsruhe Institute of Technology",
              "CISPA Helmholtz Center for Infomation Security": "CISPA Helmholtz Center for Information Security",
              "CISPA Helmholtz Center": "CISPA Helmholtz Center for Information Security",
              "Technical University Munich": "Technical University of Munich", "Universität Kassel": "University of Kassel",
              "University of Tuebingen": "University of Tübingen", "University of Wisconsin-Madison": "University of Wisconsin–Madison",
              "MPI for Informatics": "Max Planck Institute for Informatics",
              "Lawrence Livermore National Lab": "Lawrence Livermore National Laboratory",
              "University of Illinois Urbana Champaign": "University of Illinois Urbana-Champaign",
              "University of Illinois at Urbana-Champaign": "University of Illinois Urbana-Champaign",
              "University of California Berkeley": "University of California, Berkeley",
              "Singapore Management University (SMU)": "Singapore Management University",
              "The Chinese University of Hong Kong": "Chinese University of Hong Kong",
              "Technische Universität Wien": "Vienna University of Technology",
              "University of Illinois, Urbana Champaign": "University of Illinois Urbana-Champaign",
              "University of Illinois, Urbana-Champaign": "University of Illinois Urbana-Champaign",
              "University of Wisconsin, Madison": "University of Wisconsin–Madison",
              "Washington University, Saint Louis": "Washington University in St. Louis",
              "Washington University, St. Louis": "Washington University in St. Louis",
              "University of Maryland College Park": "University of Maryland, College Park",
              "The University of Melbourne": "University of Melbourne", "The Hebrew University of Jerusalem":
              "Hebrew University of Jerusalem", "The Pennsylvania State University": "Pennsylvania State University"}
# Names that need the next part ("University of California, Berkeley") or the one before ("Birkbeck, University of London").
CAMPUS = {"University of California", "University of Illinois", "University of Wisconsin", "University of Texas",
          "University of Massachusetts", "Washington University", "University of Colorado"}
UNIT = re.compile(r"^(?:the\s+)?(?:department|dept\.?|school of|faculty|division|chair|group|laboratory for|lab of)\b", re.I)
ORG = re.compile(r"universit|institut|college|eth\b|epfl|technion|kaist|cnrs|inria|deepmind|google|microsoft|ibm|"
                 r"amazon|nvidia|meta|research|center|centre|laborator|academy|school of economics", re.I)


def institution_name(full):
    """The institution as written out in full: the part of an affiliation that names the organisation (not the
    department, city or country), with abbreviations expanded."""
    parts = [p.strip(' "\'“”') for p in (full or "").split(",") if p.strip(' "\'“”')]
    parts = list(dict.fromkeys(parts))
    if not parts:
        return ""
    keep = [p for p in parts if not UNIT.match(p)] or parts
    i = next((k for k, p in enumerate(keep) if ORG.search(p)), 0)
    name = keep[i]
    after = keep[i + 1] if i + 1 < len(keep) else ""
    if name in CAMPUS and after and len(after) > 3 and not country_of(after) == after:
        name = f"{name}, {after}" if not re.fullmatch(r"[A-Z]{2}|USA|United States", after) else name
    elif re.match(r"institute of|state key lab", name, re.I) and "universit" not in name.lower() and ORG.search(after):
        name = f"{name}, {after}"
    elif name == "University of London" and i > 0:
        name = f"{keep[i - 1]}, {name}"
    name = re.sub(r"\bUniv\.\s*", "University ", name)
    name = re.sub(r"\s+\([A-Za-z][A-Za-z&.-]{1,11}\)$", "", name)  # dblp's "(KAUST)", "(UniGe)" after the full name
    return FULL_NAMES.get(name, name)


def inherit_institutions(researchers):
    """Someone with no institution on record (the roster, their OpenReview profile and dblp have none; usually a
    student) takes their supervisor's: the co-author they share the most NNV papers with, preferring a member of their
    own group and someone often last author. Shown with a * and a note under the table."""
    by_slug = {r["slug"]: r for r in researchers}
    for r in researchers:
        for public, short, country in (("institution", "institution_short", "country"),
                                       ("institution_local", "institution_local_short", "country_local")):
            if r[public]:
                continue
            options = [(by_slug[c["slug"]], c["papers"]) for c in r["coauthors"]
                       if c["slug"] in by_slug and by_slug[c["slug"]][public]]
            if not options:
                continue
            boss, _ = max(options, key=lambda o: (o[0]["group"] == r["group"], o[1], o[0]["last_author"]))
            r.update({public: boss[public], short: boss[short], country: boss[country]})
            r[f"{public}_via"] = boss["name"]


def photo_of(slug):
    """A researcher's photo: only one recorded in images.csv (kind person) and copied by fetch_photos.py --apply."""
    approved = {r["key"] for r in read_csv(CSV_DIR / "images.csv") if r["kind"] == "person"}
    f = FRONTEND / "static" / "img" / "people" / f"{slug}.jpg"
    return f"img/people/{slug}.jpg" if slug in approved and f.exists() else ""


def logo_of(slug):
    for ext in ("svg", "png", "jpg"):
        if (FRONTEND / "static" / "img" / "groups" / f"{slug}.{ext}").exists():
            return f"img/groups/{slug}.{ext}"
    return ""


RECENT_YEAR = LAST_YEAR
_T = datetime.date.today()
RECENT_FROM = f"{_T.year - 1}-{_T.month:02d}-01"


def group_home(g, members):
    """A group's institution: groups.csv's `institution` if set; else the member institution its name's bracket names
    ("Jia group (Penn State)"); else the one most members are at (a tie goes to the higher-ranked member)."""
    named = [r for r in members if r["institution_name"]]
    if g.get("institution"):
        hit = next((r for r in named if r["institution_name"] == g["institution"]), None)
        return g["institution"], hit["country"] if hit else country_of(g["institution"])
    for r in named:
        if group_label(g["name"], r["institution_name"], r["institution"]) != g["name"]:
            return r["institution_name"], r["country"]
    count = collections.Counter(r["institution_name"] for r in named)
    best = max(named, key=lambda r: count[r["institution_name"]], default=None)  # first of the top count = highest rank
    return (best["institution_name"], best["country"]) if best else ("", "")


def build_groups(groups, researchers, papers, names):
    out = []
    for slug, g in groups.items():
        members = [r for r in researchers if r["group"] == slug]
        ids = {r["slug"] for r in members}
        mine = [p for p in papers if ids & set(p["slugs"])]
        sf = score_fields(mine, ids)
        # The country most members are at; a tie goes to the higher-ranked member's country.
        where = collections.Counter(r["country"] for r in members if r["country"]).most_common(1)
        country = where[0][0] if where else ""
        home, home_country = group_home(g, members)
        recent = [p for p in mine if p["recent"]]
        sf_recent = score_fields(recent, ids)
        out.append({"recent_score": geomean(sf_recent.values()), "recent_papers": len(recent),
                    "recent_score_fields": sf_recent,
                    "country": country, "country_name": COUNTRY_NAME.get(country, country),
                    "institution": home, "institution_country": home_country,
                    "label": group_label(g["name"], home),
                    "slug": slug, "name": g["name"], "tools": split_list(g["tools"]), "url": g["url"],
                    "description": g["description"],
                    "topic": g.get("topic", ""), "topic_source": g.get("topic_source", ""),
                    "members": [{"slug": r["slug"], "name": r["name"], "institution_short": r["institution_short"],
                                 "papers": r["papers"], "score": r["score"]} for r in members],
                    "institutions": list(dict.fromkeys(r["institution_name"] for r in members if r["institution_name"])),
                    **counts(mine), "score_fields": sf, "score": geomean(sf.values()),
                    "logo": logo_of(slug), "chart": year_chart(f"{g['name']}: NNV papers per year by field", mine, 342),
                    "pie": area_pie(f"{g['name']}: NNV papers per primary area", mine, "../../areas/{key}/"),
                    "paper_list": [paper_entry(p, names) for p in mine]})
    out = [g for g in out if g["members"]]
    # The leaderboard ranks active groups: by this year's papers, then this year's score, then all-time score (the
    # maintainer's rule).
    out.sort(key=lambda g: (-g["recent_papers"], -g["recent_score"], -g["score"], -g["papers"], g["name"]))
    assign_marks(out, groups, papers)
    return out


LEADING_MIN = 2


def top(items, key, n=10):
    ranked = [i for i in sorted(items, key=lambda i: (-key(i), -i["score"], i["name"])) if key(i) >= LEADING_MIN]
    cut = key(ranked[n - 1]) if len(ranked) >= n else 0
    return [i for k, i in enumerate(ranked) if k < n or (key(i) == cut and cut > LEADING_MIN)]


def group_pie(a, mine, groups):
    lead = top(groups, lambda g: g["areas"][a["key"]])
    ids = {g["slug"]: {m["slug"] for m in g["members"]} for g in lead}
    rest = sum(1 for p in mine if not any(ids[g["slug"]] & set(p["slugs"]) for g in lead))
    rows = [(f"g{k}", g["name"], g["areas"][a["key"]], f"../../groups/{g['slug']}/") for k, g in enumerate(lead)]
    return charts.pie(f"{a['name']}: NNV papers of the leading groups", rows + [("rest", "Other groups", rest, "../")], r=140)


def build_areas(papers, researchers, groups, names):
    out = []
    for a in AREAS:
        mine = [p for p in papers if p["area"] == a["key"]]
        tagged = [p for p in papers if a["key"] in p["tags"]]
        out.append({**a, **counts(mine), "tagged": len(tagged), "total": len(mine) + len(tagged),
                    "chart": year_chart(f"{a['name']}: NNV papers per year by field", mine + tagged, 342),
                    "tracked": sum(1 for p in mine if p["slugs"]),
                    "researchers": [{"slug": r["slug"], "name": r["name"], "papers": r["areas"][a["key"]],
                                     "group": r["group"], "group_name": r["group_name"]}
                                    for r in top(researchers, lambda r: r["areas"][a["key"]])],
                    "group_pie": group_pie(a, mine, groups),
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
                    "missing": [y for y in YEARS if not totals[str(y)] and held(v["key"], y) and y <= LAST_YEAR],
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


SMALL = 20
PAT = {"ml": " pat-hash", "ai": " pat-stripe"}


ALL = []


def big_fields(papers):
    n = collections.Counter(FIELD_OF[p["venue"]] for p in (ALL or papers))
    big = sorted((f for f in FIELDS if n[f["key"]] >= SMALL), key=lambda f: -n[f["key"]])
    return big, [f for f in sorted(FIELDS, key=lambda f: -n[f["key"]]) if f not in big]


def field_series(papers, present_only=False):
    big, rest = big_fields(papers)
    cnt = lambda ks: [sum(1 for p in papers if p["year"] == y and FIELD_OF[p["venue"]] in ks) for y in YEARS]
    s = [(f"ar-{f['key']}{PAT.get(f['key'], '')}", f["name"], cnt({f["key"]})) for f in big]
    if rest:
        s.append(("ar-other", f"Other ({', '.join(f['name'] for f in rest)})", cnt({f["key"] for f in rest})))
    return [x for x in s if sum(x[2])] if present_only else s


def field_charts(papers, venues):
    big, rest = big_fields(papers)
    out = []
    for f in big:
        vs = sorted((v for v in venues if v["field"] == f["key"] and v["papers"]), key=lambda v: -v["papers"])
        s = [(f"vs{i}", v["name"], [v["years"].get(str(y), 0) for y in YEARS]) for i, v in enumerate(vs)]
        out.append({"key": f["key"], "name": f["full_name"], "short": f["name"], "papers": sum(v["papers"] for v in vs),
                    "chart": charts.stacked_columns(f"{f['full_name']}: NNV papers per year", YEARS, s)})
    if rest:
        s = [(f"vs{i}", f["name"], [sum(1 for p in papers if p["year"] == y and FIELD_OF[p["venue"]] == f["key"])
                                    for y in YEARS]) for i, f in enumerate(rest)]
        out.append({"key": "other", "name": "Other fields", "short": ", ".join(f["name"] for f in rest),
                    "papers": sum(sum(x[2]) for x in s),
                    "chart": charts.stacked_columns("Other fields: NNV papers per year", YEARS, [x for x in s if sum(x[2])])})
    return out


def year_chart(label, papers, h=180):
    return charts.stacked_columns(label, YEARS, field_series(papers), plot_h=h)


def area_pie(label, papers, link):
    return charts.pie(label, [(a["key"], a["name"], sum(1 for p in papers if p["area"] == a["key"])) for a in AREAS], link=link)


def area_trends(papers):
    years = [y for y in YEARS if y <= LAST_YEAR]
    count = {a["key"]: [sum(1 for p in papers if p["year"] == y and (p["area"] == a["key"] or a["key"] in p["tags"]))
                        for y in years] for a in AREAS}
    ranked = sorted(AREAS, key=lambda a: -sum(count[a["key"]]))
    series = [(f"hue{a['line'][0]} {a['line'][1]}", a["name"], count[a["key"]], a["key"]) for a in ranked]
    return charts.multi_lines("NNV papers per year by area", years, series)


def overview(papers):
    areas = [(a["key"], a["name"], sum(1 for p in papers if p["area"] == a["key"])) for a in AREAS]
    trends = area_trends(papers)
    return {"years": charts.stacked_columns("NNV papers per year by field", YEARS, field_series(papers), plot_h=342),
            "areas": charts.pie("NNV papers per primary area", areas), "area_trends": trends}


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
    # TRACK_MIN papers, or one paper for a member of a group that is tracked through its other members (the
    # maintainer's rule, 2026-11-27).
    tracked = {r["group"] for r in people if count[r["slug"]] >= TRACK_MIN}
    shown = {r["slug"] for r in people if count[r["slug"]] >= TRACK_MIN or (count[r["slug"]] and r["group"] in tracked)}
    hidden = [r for r in people if r["slug"] not in shown]
    people = [r for r in people if r["slug"] in shown]
    by_pid = {k: v for k, v in by_pid.items() if v in shown}
    by_name = {k: v for k, v in by_name.items() if v in shown}
    papers = nnv_papers(topics, by_pid, by_name)
    # No upper year limit: the charts and per-year counts run to the latest year with an NNV paper (an accepted
    # paper of next year's conference).
    YEARS[:] = list(range(FIRST_YEAR, max([LAST_YEAR, *(p["year"] for p in papers)]) + 1))
    for p in papers:
        for slug in p["by_name"]:
            warn(warnings, f"name match to check: {slug} on {p['key']} ({VENUE_NAME[p['venue']]} {p['year']}) {p['title'][:60]}")
    missing = set(topics) - {p["key"] for p in papers}
    if missing:
        warn(warnings, f"{len(missing)} papers in topics.csv are not in the fetched lists: {sorted(missing)[:5]}")
    dblp_people = read_json(PEOPLE_JSON, {})
    coverage = read_json(WORK / "coverage.json", {})
    from_sites = read_json(VIRTUAL_COVERAGE, {})
    for extra in (RESEARCHR_COVERAGE, ROBOTICS_COVERAGE):
        for venue, years in read_json(extra, {}).items():
            from_sites.setdefault(venue, {}).update(years)
    for venue, years in from_sites.items():
        for y, c in years.items():
            if c["papers"] > coverage.setdefault(venue, {}).get(y, {}).get("papers", 0):
                coverage[venue][y] = c
    ALL[:] = papers
    acc = digest.accepted(papers)
    for p in papers:
        p["recent"] = (acc.get(p["key"]) or f"{p['date']}-01") >= RECENT_FROM
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
    meta = {"generated_date": datetime.date.today().isoformat(), "first_year": YEARS[0], "last_year": YEARS[-1],
            "years": YEARS, "venues": [{"key": v["key"], "name": v["name"]} for v in VENUES],
            "fields": [{**f, "names": f["names"]} for f in FIELDS], "scored_fields": SCORED_FIELDS,
            "areas": [{"key": a["key"], "name": a["name"]} for a in AREAS],
            "label_min": LABEL_MIN, "countries": COUNTRY_NAME, "recent_year": RECENT_YEAR, "recent_from": RECENT_FROM[:7], "papers": len(papers), "tracked_papers": sum(1 for p in papers if p["slugs"]),
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
    entries = [{**paper_entry(p, names), "tracked": bool(p["slugs"])} for p in papers]
    write_json(DATA / "papers.json", entries)
    digest.update(entries)  # the record only grows: a row for every new in-scope paper, none removed
    month_digest = digest.build(entries, lambda text: warn(warnings, text))
    write_json(DATA / "digest.json", month_digest)
    write_json(DATA / "overview.json", {**overview(papers), "fields": field_charts(papers, venues)})
    now = [{**r, "papers": r["recent_papers"]} for r in researchers if r["recent_papers"]]
    write_json(DATA / "graph.json", {"all": graph.layout(researchers, group_list, papers),
                                     "recent": graph.layout(now, group_list, [p for p in papers if p["recent"]]),
                                     "recent_year": RECENT_YEAR})
    write_json(DATA / "candidates.json", candidates({r["slug"] for r in researchers}, hidden, count))
    write_stubs("researchers", [(r["slug"], r["name"]) for r in researchers])
    write_stubs("groups", [(g["slug"], g["name"]) for g in group_list])
    write_stubs("areas", [(a["key"], a["name"]) for a in AREAS])
    write_stubs("conferences", [(v["key"], v["name"]) for v in VENUES])
    write_stubs("digest", [(m["month"], m["label"]) for m in month_digest["months"]]  # one call: it clears the folder
                + [(y["year"], f"Monthly digest {y['year']}") for y in month_digest["years"]])
    WORK.mkdir(parents=True, exist_ok=True)
    (WORK / "build_report.txt").write_text("\n".join(warnings) + "\n", encoding="utf-8")
    print(f"{len(papers)} NNV papers, {meta['tracked_papers']} with a listed researcher, {len(researchers)} researchers, "
          f"{len(group_list)} groups, {len(warnings)} warnings", file=sys.stderr)


if __name__ == "__main__":
    main()
