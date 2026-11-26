import argparse
import collections
import re
import sys

from common import ROSTER, all_papers, CSV_DIR, PAPERS, TOPICS, WORK, read_csv, read_jsonl_gz, split_list, write_csv

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
          r"|provabl[ey] robust|verified training|verifiabl[ey] robust|verifying robust|convex barrier")
# A listed researcher's paper is a candidate on one broad word alone: titles such as "Relational Verification Leaps
# Forward with RABBit" or "Local vs. Global Interpretability: A Computational Complexity Perspective" name no model.
AUTHOR = (r"verif|certif|provabl|guarant|proof|sound|abstract interp|abstraction|lyapunov|barrier|reachab|explanation"
          r"|explain|robust|lipschitz|smooth|bound|relax|branch|satisf|\bsat\b|\bsmt\b|formal|safe|repair|interpret"
          r"|sensitiv|orthogonal|conformal")
MODEL_RX, CHECK_RX, STRONG_RX, AUTHOR_RX = (re.compile(p, re.I) for p in (MODEL, CHECK, STRONG, AUTHOR))
TOPIC_FIELDS = ["key", "venue", "year", "title", "decision", "area", "tags", "note"]


def hit(title, listed_author=False):
    if STRONG_RX.search(title):
        return "strong"
    if MODEL_RX.search(title) and CHECK_RX.search(title):
        return "keyword"
    if listed_author and AUTHOR_RX.search(title):
        return "author"
    return ""


def listed(p, pids, names):
    return any(a["pid"] in pids if a["pid"] else a["name"] in names for a in p["authors"])


def main():
    ap = argparse.ArgumentParser(description="Add every paper whose title may be about neural-network verification to topics.csv, undecided.")
    ap.add_argument("--dry-run", action="store_true", help="only print the counts")
    args = ap.parse_args()
    rows = read_csv(TOPICS)
    known = {r["key"] for r in rows}
    roster = [r for r in read_csv(ROSTER) if r["approved"] == "yes"]
    pids = {pid for r in roster for pid in split_list(r["dblp_pids"])}
    names = {n for r in roster for n in [r["name"], *split_list(r["aliases"])]}
    counts, added = collections.Counter(), []
    for p in all_papers():
        kind = hit(p["title"], listed(p, pids, names))
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
