import argparse
import collections
import re
import sys

from common import CSV_DIR, PAPERS, TOPICS, WORK, read_csv, read_jsonl_gz, write_csv

MODEL = (r"neural|network|\bnets?\b|\bdnns?\b|\bcnns?\b|\brnns?\b|\bgnns?\b|\bllms?\b|deep|relu|transformer|perceptron"
         r"|classifier|learn(ed|ing)[- ]enabled|learned (controller|component|model|polic)|machine[- ]learn|\bml\b|\bai\b"
         r"|language model|vision|detector|segment|polic(y|ies)|reinforcement|tree ensemble|ensemble|boost|autoencoder"
         r"|attention|activation|embedding|quantized|binari[sz]ed|\bbnns?\b|\bqnns?\b|neuro|classif|image|detection"
         r"|recognition|segmentation|point cloud|\bvit\b|diffusion")
CHECK = (r"verif|certif|provabl|provably|formal|reachab|bound propagation|\bbounds?\b|abstract interpret|abstract domain"
         r"|abstraction|\bsmt\b|\bmilp\b|mixed[- ]integer|branch[- ]and[- ]bound|lipschitz|randomi[sz]ed smoothing"
         r"|smoothing|barrier certificate|lyapunov|\brepair|patch|abductive|explanation|relaxation|polytope|zonotope"
         r"|star[- ]set|symbolic interval|interval|decision procedure|satisfiab|over[- ]?approximat|under[- ]?approximat"
         r"|guarantee|sound|complete|exact|robustness analysis|safety|safe\b|invariant|counterexample|hyperpropert"
         r"|fairness|monoton|backdoor|bit[- ]flip|linear programming|semidefinite|\bsdp\b|convex|dual")
STRONG = (r"reluplex|marabou|crown|deeppoly|deepz\b|\beran\b|\bprima\b|neurify|reluval|\bnnv\b|nnenum|neuralsat"
          r"|verisig|\bpolar\b|venus|\bpyrat\b|mn-bab|deept\b|\bai2\b|diffai|\bibp\b|interval bound propagation"
          r"|certified (robust|defen|training|accuracy|radius|radii)|certifiabl|provable (robust|defen|guarantee)"
          r"|adversarial(ly)? robust.{0,40}(verif|certif|provabl|guarantee|bound)"
          r"|(verif|certif|provabl).{0,60}adversarial|vnn-?comp|verified robust|robustness verif|globally[- ]robust"
          r"|randomi[sz]ed smoothing|smoothed (\w+ )?(classifier|agent|polic|model)|relu hull|robustness (bound|quantif|certif|guarantee)"
          r"|quantifying (the )?robustness|lipschitz (constant|bound|network|neural|certif)|certified|certifying"
          r"|provabl[ey] robust|verified training|verifiabl[ey] robust|verifying robust")
MODEL_RX, CHECK_RX, STRONG_RX = (re.compile(p, re.I) for p in (MODEL, CHECK, STRONG))
TOPIC_FIELDS = ["key", "venue", "year", "title", "decision", "area", "tags", "note"]


def hit(title):
    if STRONG_RX.search(title):
        return "strong"
    if MODEL_RX.search(title) and CHECK_RX.search(title):
        return "keyword"
    return ""


def main():
    ap = argparse.ArgumentParser(description="Add every paper whose title may be about neural-network verification to topics.csv, undecided.")
    ap.add_argument("--dry-run", action="store_true", help="only print the counts")
    args = ap.parse_args()
    rows = read_csv(TOPICS)
    known = {r["key"] for r in rows}
    counts, added = collections.Counter(), []
    for p in read_jsonl_gz(PAPERS):
        kind = hit(p["title"])
        if not kind:
            continue
        counts[(p["venue"], kind)] += 1
        if p["key"] in known:
            continue
        added.append({"key": p["key"], "venue": p["venue"], "year": p["year"], "title": p["title"],
                      "decision": "", "area": "", "tags": "", "note": f"prefilter {kind}"})
    for (venue, kind), n in sorted(counts.items()):
        print(f"{venue:8} {kind:8} {n}", file=sys.stderr)
    print(f"{len(added)} new candidates, {len(rows)} already in topics.csv", file=sys.stderr)
    if not args.dry_run:
        rows.extend(added)
        rows.sort(key=lambda r: (r["venue"], int(r["year"]), r["title"].lower()))
        write_csv(TOPICS, TOPIC_FIELDS, rows)


if __name__ == "__main__":
    main()
