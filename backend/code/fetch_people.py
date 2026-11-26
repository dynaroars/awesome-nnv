import argparse
import datetime
import sys

from common import CANDIDATES, PEOPLE_JSON, ROSTER, read_csv, read_json, split_list, write_json
from fetch_dblp import sparql

BATCH = 80


def person_rows(pids, tag):
    values = " ".join(f"<https://dblp.org/pid/{p}>" for p in pids)
    query = ("SELECT ?pid ?name ?aff ?primary ?home ?orcid WHERE { "
             f"VALUES ?pid {{ {values} }} "
             "?pid dblp:primaryCreatorName ?name . "
             "OPTIONAL { ?pid dblp:affiliation ?aff } OPTIONAL { ?pid dblp:primaryAffiliation ?primary } "
             "OPTIONAL { ?pid dblp:primaryHomepage ?home } OPTIONAL { ?pid dblp:orcid ?orcid } }")
    return sparql(query, f"dblp/people/{tag}.json", refresh=True)


def main():
    ap = argparse.ArgumentParser(description="Read DBLP person records (name, affiliation, homepage) of roster and candidate authors.")
    ap.add_argument("--candidates", type=int, default=150, help="also read this many top candidates")
    args = ap.parse_args()
    people = read_json(PEOPLE_JSON, {})
    pids = []
    for r in read_csv(ROSTER):
        pids.extend(split_list(r["dblp_pids"]))
    pids.extend(r["pid"] for r in read_csv(CANDIDATES)[:args.candidates] if r.get("pid"))
    todo = sorted({p for p in pids if p and p not in people})
    stamp = datetime.date.today().isoformat()
    for k in range(0, len(todo), BATCH):
        chunk = todo[k:k + BATCH]
        for row in person_rows(chunk, f"{stamp}-{k // BATCH}"):
            pid = row["pid"].replace("https://dblp.org/pid/", "")
            p = people.setdefault(pid, {"name": row["name"], "affiliations": [], "primary": "", "homepage": "",
                                        "orcid": "", "fetched": stamp})
            if row.get("aff") and row["aff"] not in p["affiliations"]:
                p["affiliations"].append(row["aff"])
            p["primary"] = row.get("primary", p["primary"])
            p["homepage"] = row.get("home", p["homepage"])
            p["orcid"] = row.get("orcid", "").replace("https://orcid.org/", "") or p["orcid"]
        print(f"  {min(k + BATCH, len(todo))}/{len(todo)} people", file=sys.stderr)
    write_json(PEOPLE_JSON, dict(sorted(people.items())))


if __name__ == "__main__":
    main()
