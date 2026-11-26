import csv
import datetime
import gzip
import html
import json
import re
import unicodedata
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
CSV_DIR = BACKEND / "data" / "csv"
JSON_DIR = BACKEND / "data" / "json"
FRONTEND = BACKEND.parent / "frontend"
RAW = BACKEND / "data" / "raw"
WORK = BACKEND / "work"
PAPERS = WORK / "papers.jsonl.gz"
VIRTUAL = WORK / "virtual.jsonl.gz"
VIRTUAL_COVERAGE = WORK / "coverage_virtual.json"
VIRTUAL_SITES = {"neurips": "https://neurips.cc", "icml": "https://icml.cc", "iclr": "https://iclr.cc"}

ROSTER = CSV_DIR / "roster.csv"
TOPICS = CSV_DIR / "topics.csv"
GROUPS_CSV = CSV_DIR / "groups.csv"
CANDIDATES = CSV_DIR / "candidates.csv"
PEOPLE_JSON = JSON_DIR / "people.json"

FIRST_YEAR = 2017
LAST_YEAR = datetime.date.today().year
YEARS = list(range(FIRST_YEAR, LAST_YEAR + 1))
MIN_PAGES = 6

PACMPL = "journals/pacmpl/pacmpl"
PACMSE = "journals/pacmse/pacmse"

VENUES = [
    {"key": "icml", "name": "ICML", "full_name": "International Conference on Machine Learning",
     "stream": "icml", "tocs": [r"conf/icml/icml(\d{4})"]},
    {"key": "iclr", "name": "ICLR", "full_name": "International Conference on Learning Representations",
     "stream": "iclr", "tocs": [r"conf/iclr/iclr(\d{4})"]},
    {"key": "neurips", "name": "NeurIPS", "full_name": "Conference on Neural Information Processing Systems",
     "stream": "nips", "tocs": [r"conf/nips/(?:nips|neurips)(\d{4})"]},
    {"key": "cvpr", "name": "CVPR", "full_name": "IEEE/CVF Conference on Computer Vision and Pattern Recognition",
     "stream": "cvpr", "tocs": [r"conf/cvpr/cvpr(\d{4})"]},
    {"key": "iccv", "name": "ICCV", "full_name": "IEEE/CVF International Conference on Computer Vision",
     "stream": "iccv", "tocs": [r"conf/iccv/iccv(\d{4})"]},
    {"key": "eccv", "name": "ECCV", "full_name": "European Conference on Computer Vision",
     "stream": "eccv", "tocs": [r"conf/eccv/eccv(\d{4})-\d+"]},
    {"key": "pldi", "name": "PLDI", "full_name": "ACM SIGPLAN Conference on Programming Language Design and Implementation",
     "stream": "pldi", "tocs": [r"conf/pldi/pldi(\d{4})", PACMPL + r"\d+#PLDI"]},
    {"key": "popl", "name": "POPL", "full_name": "ACM SIGPLAN Symposium on Principles of Programming Languages",
     "stream": "popl", "tocs": [r"conf/popl/popl(\d{4})", PACMPL + r"\d+#POPL"]},
    {"key": "icfp", "name": "ICFP", "full_name": "ACM SIGPLAN International Conference on Functional Programming",
     "stream": "icfp", "tocs": [PACMPL + r"\d+#ICFP"]},
    {"key": "oopsla", "name": "OOPSLA", "full_name": "Object-Oriented Programming, Systems, Languages, and Applications",
     "stream": "oopsla", "tocs": [PACMPL + r"\d+#OOPSLA\d?"]},
    {"key": "fse", "name": "FSE", "full_name": "ACM International Conference on the Foundations of Software Engineering",
     "stream": "sigsoft", "tocs": [r"conf/sigsoft/fse(\d{4})", PACMSE + r"\d+#FSE"]},
    {"key": "icse", "name": "ICSE", "full_name": "International Conference on Software Engineering",
     "stream": "icse", "tocs": [r"conf/icse/icse(\d{4})"]},
    {"key": "ase", "name": "ASE", "full_name": "IEEE/ACM International Conference on Automated Software Engineering",
     "stream": "kbse", "tocs": [r"conf/kbse/ase(\d{4})"]},
    {"key": "issta", "name": "ISSTA", "full_name": "ACM SIGSOFT International Symposium on Software Testing and Analysis",
     "stream": "issta", "tocs": [r"conf/issta/issta(\d{4})", PACMSE + r"\d+#ISSTA"]},
    {"key": "cav", "name": "CAV", "full_name": "International Conference on Computer Aided Verification",
     "stream": "cav", "tocs": [r"conf/cav/cav(\d{4})-\d"]},
    {"key": "lics", "name": "LICS", "full_name": "ACM/IEEE Symposium on Logic in Computer Science",
     "stream": "lics", "tocs": [r"conf/lics/lics(\d{4})"]},
    {"key": "nfm", "name": "NFM", "full_name": "NASA Formal Methods Symposium",
     "stream": "nfm", "tocs": [r"conf/nfm/nfm(\d{4})"]},
]
VENUE_KEYS = [v["key"] for v in VENUES]


def held(venue, year):
    return not ((venue == "iccv" and year % 2 == 0) or (venue == "eccv" and year % 2 == 1))
VENUE_NAME = {v["key"]: v["name"] for v in VENUES}

FIELDS = [
    {"key": "ml", "name": "ML", "full_name": "Machine learning", "venues": ["icml", "iclr", "neurips"], "scored": True},
    {"key": "cv", "name": "CV", "full_name": "Computer vision", "venues": ["cvpr", "iccv", "eccv"], "scored": True},
    {"key": "pl", "name": "PL", "full_name": "Programming languages", "venues": ["pldi", "popl", "icfp", "oopsla"],
     "scored": True},
    {"key": "se", "name": "SE", "full_name": "Software engineering", "venues": ["fse", "icse", "ase", "issta"],
     "scored": True},
    {"key": "lv", "name": "LV", "full_name": "Logic and verification", "venues": ["cav", "lics"], "scored": True},
    {"key": "fm", "name": "Other FM", "full_name": "Other formal methods (not in CSRankings)", "venues": ["nfm"],
     "scored": False},
]
for _f in FIELDS:
    _f["names"] = [VENUE_NAME[k] for k in _f["venues"]]
FIELD_OF = {v: f["key"] for f in FIELDS for v in f["venues"]}
SCORED_FIELDS = [f["key"] for f in FIELDS if f["scored"]]

AREAS = [
    {"key": "complete", "name": "Complete verification",
     "description": "SMT, MILP and branch-and-bound verifiers that decide a property exactly."},
    {"key": "bounds", "name": "Bound propagation & abstract interpretation",
     "description": "Sound over-approximation of network behaviour: abstract domains, linear relaxations, LP and SDP bounds."},
    {"key": "probabilistic", "name": "Probabilistic certification",
     "description": "Randomized smoothing and statistical (PAC) guarantees."},
    {"key": "training", "name": "Certified training",
     "description": "Training networks so that they can be verified: IBP, CROWN-IBP, SABR and successors."},
    {"key": "repair", "name": "Repair & patching",
     "description": "Provable repair, verification-guided patching and editing of networks."},
    {"key": "explanations", "name": "Formal explanations",
     "description": "Verification used to explain decisions: abductive and minimal explanations."},
    {"key": "control", "name": "NN control systems",
     "description": "Closed-loop reachability, neural controllers, barrier and Lyapunov certificates, verified reinforcement learning."},
    {"key": "relational", "name": "Global & relational properties",
     "description": "Global robustness, universal perturbations, fairness, monotonicity, hyperproperties and semantic specifications."},
    {"key": "architectures", "name": "Beyond feed-forward nets",
     "description": "Transformers, recurrent and graph networks, tree ensembles, language and vision-language models, detectors."},
    {"key": "quantized", "name": "Quantized & bit-level",
     "description": "Bit-precise verification of quantized and binarized networks, bit-flip resilience."},
    {"key": "other", "name": "Other",
     "description": "Lipschitz certification, soundness of verifiers, proof checking, tools, benchmarks and surveys."},
]
AREA_KEYS = [a["key"] for a in AREAS]
AREA_NAME = {a["key"]: a["name"] for a in AREAS}


def strip_accents(s):
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def norm_name(s):
    s = strip_accents(html.unescape(s or ""))
    return " ".join(re.sub(r"[^A-Za-z0-9]+", " ", s).lower().split())


def norm_title(s):
    s = strip_accents(html.unescape(s or ""))
    s = re.sub(r"\\[a-zA-Z]+|\\.", "", s)
    return re.sub(r"[^a-z0-9]+", "", s.lower())


def slugify(s):
    return re.sub(r"[^a-z0-9]+", "-", strip_accents(s).lower()).strip("-")


def dblp_name(name):
    return re.sub(r"\s+\d{4}$", "", name or "")


TITLE_STOPWORDS = {"a", "an", "the", "on", "of", "in", "for", "and", "to", "with", "at", "by", "from", "is", "are"}


def family_name(name):
    tokens = [t for t in norm_name(dblp_name(name)).split() if not t.isdigit()]
    return tokens[-1] if tokens else "anon"


def scholar_id(first_author, year, title):
    words = [w for w in re.findall(r"[a-z0-9]+", strip_accents(html.unescape(title or "")).lower())]
    word = next((w for w in words if w not in TITLE_STOPWORDS), words[0] if words else "untitled")
    return f"{family_name(first_author)}{year}{word}"


def assign_ids(papers):
    seen = {}
    for p in sorted(papers, key=lambda p: (p["year"], p["key"])):
        base = scholar_id(p["authors"][0]["name"] if p["authors"] else "", p["year"], p["title"])
        n = seen.get(base, 0)
        seen[base] = n + 1
        p["id"] = base if n == 0 else f"{base}{chr(ord('a') + n)}"
    return papers


def page_count(pagination):
    p = (pagination or "").strip()
    m = re.fullmatch(r"(?:\d+:)?(\d+)\s*-\s*(?:\d+:)?(\d+)", p)
    if not m:
        return None
    a, b = int(m.group(1)), int(m.group(2))
    return b - a + 1 if b >= a else None


def split_list(value):
    return [x.strip() for x in (value or "").split(";") if x.strip()]


def read_jsonl_gz(path):
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def all_papers():
    papers = list(read_jsonl_gz(PAPERS))
    listed = {(p["venue"], p["year"]) for p in papers}
    if Path(VIRTUAL).exists():
        papers.extend(p for p in read_jsonl_gz(VIRTUAL) if (p["venue"], p["year"]) not in listed)
    return papers


def write_jsonl_gz(path, rows):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def write_json(path, obj):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
        f.write("\n")


def read_json(path, default=None):
    if not Path(path).exists():
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def write_csv(path, fields, rows):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def read_csv(path):
    if not Path(path).exists():
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))
