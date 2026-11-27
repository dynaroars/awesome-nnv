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
RESEARCHR = WORK / "researchr.jsonl.gz"
RESEARCHR_COVERAGE = WORK / "coverage_researchr.json"
ROBOTICS = WORK / "robotics.jsonl.gz"
ROBOTICS_COVERAGE = WORK / "coverage_robotics.json"
# Accepted-paper lists on conf.researchr.org (the conference's own site) for the SE and PL venues: track page and the
# track label of the main research track on it ({y} is the year).
RESEARCHR_TRACKS = {"icse": ("icse-{y}/icse-{y}-research-track", "Research Track"),
                    "fse": ("fse-{y}/fse-{y}-research-papers", "Research Papers"),
                    "ase": ("ase-{y}/ase-{y}-research-track", "Research Papers"),
                    "issta": ("issta-{y}/issta-{y}-research-papers", "Research papers"),
                    "popl": ("popl-{y}/popl-{y}-popl-research-papers", "POPL"),
                    "pldi": ("pldi-{y}/pldi-{y}-papers", "PLDI Research Papers"),
                    "oopsla": ("splash-{y}/oopsla-{y}", "OOPSLA")}

ROSTER = CSV_DIR / "roster.csv"
TOPICS = CSV_DIR / "topics.csv"
GROUPS_CSV = CSV_DIR / "groups.csv"
CANDIDATES = CSV_DIR / "candidates.csv"
ACCEPTED = CSV_DIR / "accepted.csv"
PEOPLE_JSON = JSON_DIR / "people.json"

FIRST_YEAR = 2017
LAST_YEAR = datetime.date.today().year  # the current year; there is no upper limit on paper years
YEARS = list(range(FIRST_YEAR, LAST_YEAR + 1))  # build_site_data.py extends it to the latest year with a paper
MIN_PAGES = 6
TRACK_MIN = 2
LABEL_MIN = 4

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
    {"key": "aaai", "name": "AAAI", "full_name": "AAAI Conference on Artificial Intelligence",
     "stream": "aaai", "tocs": [r"conf/aaai/aaai(\d{4})"]},
    {"key": "ijcai", "name": "IJCAI", "full_name": "International Joint Conference on Artificial Intelligence",
     "stream": "ijcai", "tocs": [r"conf/ijcai/ijcai(\d{4})"]},
    {"key": "ccs", "name": "CCS", "full_name": "ACM Conference on Computer and Communications Security",
     "stream": "ccs", "tocs": [r"conf/ccs/ccs(\d{4})"]},
    {"key": "sp", "name": "S&P", "full_name": "IEEE Symposium on Security and Privacy",
     "stream": "sp", "tocs": [r"conf/sp/sp(\d{4})"]},
    {"key": "uss", "name": "USENIX Security", "full_name": "USENIX Security Symposium",
     "stream": "uss", "tocs": [r"conf/uss/uss(\d{4})"]},
    {"key": "ndss", "name": "NDSS", "full_name": "Network and Distributed System Security Symposium",
     "stream": "ndss", "tocs": [r"conf/ndss/ndss(\d{4})"]},
    {"key": "icra", "name": "ICRA", "full_name": "IEEE International Conference on Robotics and Automation",
     "stream": "icra", "tocs": [r"conf/icra/icra(\d{4})"]},
    {"key": "iros", "name": "IROS", "full_name": "IEEE/RSJ International Conference on Intelligent Robots and Systems",
     "stream": "iros", "tocs": [r"conf/iros/iros(\d{4})"]},
    {"key": "rss", "name": "RSS", "full_name": "Robotics: Science and Systems",
     "stream": "rss", "tocs": [r"conf/rss/rss(\d{4})"]},
]
VENUE_KEYS = [v["key"] for v in VENUES]


VENUE_MONTH = {"icml": 7, "iclr": 5, "neurips": 12, "cvpr": 6, "iccv": 10, "eccv": 10, "pldi": 6, "popl": 1,
               "icfp": 9, "oopsla": 10, "fse": 11, "icse": 5, "ase": 10, "issta": 7, "cav": 7, "lics": 7,
               "aaai": 2, "ijcai": 8, "ccs": 11, "sp": 5, "uss": 8, "ndss": 2, "icra": 5, "iros": 10, "rss": 7}
MONTH_EXCEPTIONS = {("iclr", 2020): 4, ("iclr", 2021): 5, ("iclr", 2022): 4, ("iclr", 2026): 4, ("eccv", 2020): 8,
                    ("eccv", 2018): 9, ("eccv", 2024): 9, ("fse", 2024): 7, ("fse", 2025): 6, ("fse", 2026): 7,
                    ("fse", 2017): 9, ("fse", 2018): 11, ("fse", 2019): 8, ("ase", 2018): 9, ("ase", 2019): 11,
                    ("ase", 2020): 9, ("ase", 2021): 11, ("ase", 2023): 9, ("ase", 2025): 11, ("issta", 2024): 9,
                    ("icse", 2017): 5, ("icse", 2025): 4, ("lics", 2018): 7, ("lics", 2019): 6, ("lics", 2022): 8,
                    ("lics", 2024): 7, ("icfp", 2025): 10, ("oopsla", 2023): 10,
                    ("oopsla", 2024): 10, ("oopsla", 2025): 10, ("neurips", 2017): 12,
                    # IJCAI-PRICAI 2020 met in January 2021; its proceedings came out in July 2020.
                    ("aaai", 2019): 1, ("aaai", 2026): 1, ("ijcai", 2018): 7, ("ijcai", 2020): 7, ("ijcai", 2022): 7,
                    ("ccs", 2017): 10, ("ccs", 2018): 10, ("ccs", 2024): 10, ("ccs", 2025): 10, ("icra", 2026): 6,
                    ("iros", 2017): 9, ("iros", 2019): 11, ("iros", 2021): 9, ("rss", 2018): 6, ("rss", 2019): 6,
                    ("rss", 2022): 6, ("rss", 2025): 6}


def conference_month(venue, year):
    return f"{year}-{MONTH_EXCEPTIONS.get((venue, year), VENUE_MONTH[venue]):02d}"


def held(venue, year):
    return not ((venue == "iccv" and year % 2 == 0) or (venue == "eccv" and year % 2 == 1))
VENUE_NAME = {v["key"]: v["name"] for v in VENUES}

FIELDS = [
    {"key": "ml", "name": "ML", "full_name": "Machine learning", "venues": ["icml", "iclr", "neurips"]},
    {"key": "cv", "name": "CV", "full_name": "Computer vision", "venues": ["cvpr", "iccv", "eccv"]},
    {"key": "pl", "name": "PL", "full_name": "Programming languages", "venues": ["pldi", "popl", "icfp", "oopsla"]},
    {"key": "se", "name": "SE", "full_name": "Software engineering", "venues": ["fse", "icse", "ase", "issta"]},
    {"key": "lv", "name": "LV", "full_name": "Logic and verification", "venues": ["cav", "lics"]},
    {"key": "ai", "name": "AI", "full_name": "Artificial intelligence", "venues": ["aaai", "ijcai"]},
    {"key": "sec", "name": "Sec", "full_name": "Computer security", "venues": ["ccs", "sp", "uss", "ndss"]},
    {"key": "ro", "name": "Rob", "full_name": "Robotics", "venues": ["icra", "iros", "rss"]},
]
for _f in FIELDS:
    _f["names"] = [VENUE_NAME[k] for k in _f["venues"]]
FIELD_OF = {v: f["key"] for f in FIELDS for v in f["venues"]}
SCORED_FIELDS = [f["key"] for f in FIELDS]

AREAS = [
    {"key": "complete", "line": (3, "dashed"), "name": "Complete verification",
     "description": "SMT, MILP, and branch-and-bound verifiers that decide properties exactly."},
    {"key": "bounds", "line": (2, "solid"), "name": "Bound propagation & abstract interpretation",
     "description": "Sound over-approximations of network behavior using abstract domains, linear relaxations, and LP or SDP bounds."},
    {"key": "probabilistic", "line": (1, "solid"), "name": "Probabilistic certification",
     "description": "Randomized smoothing and statistical (PAC) certification guarantees."},
    {"key": "training", "line": (3, "solid"), "name": "Certified training",
     "description": "Training networks to be easier to verify, including IBP, CROWN-IBP, SABR, and related methods."},
    {"key": "repair", "line": (1, "dashdot"), "name": "Repair & patching",
     "description": "Provable repair, verification-guided patching, and editing of neural networks."},
    {"key": "explanations", "line": (3, "dotted"), "name": "Formal explanations",
     "description": "Using formal verification to produce abductive and minimal explanations of model decisions."},
    {"key": "control", "line": (1, "dotted"), "name": "NN control systems",
     "description": "Closed-loop reachability, neural controllers, barrier and Lyapunov certificates, and verified reinforcement learning."},
    {"key": "relational", "line": (2, "dotted"), "name": "Global & relational properties",
     "description": "Global robustness, universal perturbations, fairness, monotonicity, and hyperproperties."},
    {"key": "architectures", "line": (1, "dashed"), "name": "Beyond feed-forward nets",
     "description": "Verification for transformers, RNNs, GNNs, language and vision-language models, and object detectors."},
    {"key": "quantized", "line": (2, "dashdot"), "name": "Quantized & bit-level",
     "description": "Bit-precise verification of quantized and binarized networks, including bit-flip resilience."},
    {"key": "other", "line": (2, "dashed"), "name": "Other",
     "description": "Lipschitz certification, verifier soundness, proof checking, tools, benchmarks, and surveys."},
    # Specification areas (added 2026-11-27 at the maintainer's request): what is certified, not how. Primary only when
    # the new specification is the paper's main contribution; otherwise a tag.
    {"key": "inputs", "line": (3, "dashdot"), "name": "Beyond ℓp input properties",
     "description": "Input sets other than an ℓp ball: geometric, semantic and structural transformations, coordinated (convolutional) perturbations, patches, text edits, and graph and point-cloud changes."},
    {"key": "outputs", "line": (1, "longdash"), "name": "Beyond linear output properties",
     "description": "Properties that are not linear constraints on the outputs: IoU and detection, segmentation-level properties, pose, confidence and calibration, embedding distances, generation risks, and non-linear specifications."},
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


SMALL_WORDS = {"a", "an", "the", "and", "or", "but", "nor", "for", "of", "on", "in", "to", "via", "vs", "vs.", "with",
               "at", "by", "from", "into", "as", "per", "over", "under", "without", "through"}
ACRONYMS = {"ai", "ml", "nn", "nns", "dnn", "dnns", "cnn", "cnns", "rnn", "rnns", "gnn", "gnns", "llm", "llms", "vlm",
            "vlms", "rag", "rl", "drl", "smt", "milp", "lp", "sdp", "ibp", "pac", "gpu", "gpus", "nnv", "vnn", "ood",
            "nlp", "cv", "2d", "3d", "4d", "relu", "api", "iou", "sat", "mdp", "mdps", "ode", "odes", "vla", "vlas"}
ACRONYM_FORM = {"llms": "LLMs", "gnns": "GNNs", "dnns": "DNNs", "cnns": "CNNs", "rnns": "RNNs", "nns": "NNs",
                "vlms": "VLMs", "gpus": "GPUs", "mdps": "MDPs", "odes": "ODEs", "vlas": "VLAs", "relu": "ReLU"}


def display_title(title):
    letters = [c for c in title if c.isalpha()]
    if len(letters) < 8 or sum(c.isupper() for c in letters) < 0.8 * len(letters):
        return title
    out, start = [], True
    for token in re.split(r"(\s+)", title):
        if not token or token.isspace():
            out.append(token)
            continue
        parts = []
        for k, part in enumerate(token.split("-")):
            core = re.sub(r"[^A-Za-z0-9.]", "", part).lower()
            if core in ACRONYMS:
                word = part.replace(core.upper(), ACRONYM_FORM.get(core, core.upper())) if part.upper() == part else part
            elif any(c.isdigit() for c in part):
                word = part
            elif core in SMALL_WORDS and not start and k == 0:
                word = part.lower()
            else:
                low = part.lower()
                word = re.sub(r"[a-z]", lambda m: m.group(0).upper(), low, count=1)
            parts.append(word)
        out.append("-".join(parts))
        start = token.endswith(":") or token.endswith("?") or token.endswith(".")
    return "".join(out)


# Items in the proceedings that are not main-track research papers: keynotes, invited papers and talks, award
# retrospectives, chairs' messages, forewords and corrigenda; at ICML, NeurIPS and ICLR also position papers.
NOT_A_PAPER = re.compile(r"\([^()]*\b(?:keynote|invited|tutorial|impact paper)\b[^()]*\)|^message from the\b|\bforeword$"
                         r"|^(?:corrigendum|erratum)\b", re.I)
POSITION = re.compile(r"\s*position\s*:", re.I)
OFF_TRACKS = {"datasets_benchmarks", "position", "blog", "journal"}


def not_a_paper(venue, title):
    return bool(NOT_A_PAPER.search(title or "")) or (venue in VIRTUAL_SITES and bool(POSITION.match(title or "")))


def norm_title(title):
    return re.sub(r"[^a-z0-9]+", "", html.unescape(title or "").lower())


def virtual_track(title, sourceurl, event_type, file_has_source):
    src, ev = sourceurl or "", event_type or ""
    if re.search(r"blog", f"{src} {ev}", re.I):
        return "blog"
    if re.search(r"datasets_and_benchmarks|evaluations_and_datasets", src, re.I):
        return "datasets_benchmarks"
    if re.search(r"position_paper", src, re.I) or POSITION.match(title or ""):
        return "position"
    if re.search(r"jmlr|tmlr|j2c|journal|ann-stats|projecteuclid|imstat|rescience|reproducibility", f"{src} {ev}", re.I):
        return "journal"
    if re.search(r"/\d{4}/Conference", src):
        return "main"
    if not src and not file_has_source:
        return "main"
    return "other"


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


def accepted_rows():
    """Accepted papers known only from an author's page or announcement (accepted.csv): counted, tagged unofficial."""
    out = []
    for r in read_csv(ACCEPTED) if Path(ACCEPTED).exists() else []:
        key = f"accepted/{r['venue']}{r['year']}/{norm_title(r['title'])[:60]}"
        out.append({"key": key, "venue": r["venue"], "year": int(r["year"]), "title": r["title"], "doi": "", "pages": "",
                    "page_count": None, "url": r["source_url"], "source": "author page", "unofficial": True,
                    "authors": [{"name": n, "dblp_name": "", "pid": "", "inst": []} for n in split_list(r["authors"])]})
    return out


def all_papers():
    """dblp, then the conference sites for venue-years dblp lacks (ICML/NeurIPS/ICLR lists, researchr lists, RSS
    proceedings and OpenAlex's IROS records), then
    accepted.csv; a paper already listed by an earlier source (same venue, same title) is not added again."""
    papers = list(read_jsonl_gz(PAPERS))
    listed = {(p["venue"], p["year"]) for p in papers}
    if Path(VIRTUAL).exists():
        papers.extend(p for p in read_jsonl_gz(VIRTUAL) if (p["venue"], p["year"]) not in listed)
    seen = {(p["venue"], norm_title(p["title"])) for p in papers}
    later = [p for f in (RESEARCHR, ROBOTICS) if Path(f).exists() for p in read_jsonl_gz(f)]
    for p in later + accepted_rows():
        if (p["venue"], norm_title(p["title"])) not in seen:
            seen.add((p["venue"], norm_title(p["title"])))
            papers.append(p)
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


COUNTRY_NAME = {"US": "United States", "CN": "China", "GB": "United Kingdom", "DE": "Germany", "CH": "Switzerland",
                "FR": "France", "AU": "Australia", "SG": "Singapore", "AT": "Austria", "JP": "Japan", "IL": "Israel",
                "CA": "Canada", "RU": "Russia", "ES": "Spain", "KR": "South Korea", "IN": "India", "HK": "Hong Kong",
                "DK": "Denmark", "HU": "Hungary", "TW": "Taiwan", "RS": "Serbia", "VN": "Vietnam", "PT": "Portugal",
                "FI": "Finland", "MO": "Macao", "NL": "Netherlands", "BE": "Belgium", "SE": "Sweden", "IT": "Italy",
                "NO": "Norway", "IE": "Ireland", "PL": "Poland", "CZ": "Czechia", "GR": "Greece", "SA": "Saudi Arabia",
                "AE": "United Arab Emirates", "BR": "Brazil", "NZ": "New Zealand", "LU": "Luxembourg", "CY": "Cyprus",
                "IR": "Iran", "TR": "Turkey", "MX": "Mexico", "CL": "Chile", "QA": "Qatar"}
_COUNTRY_WORDS = {**{v.lower(): k for k, v in COUNTRY_NAME.items()}, "usa": "US", "u.s.a.": "US", "uk": "GB",
                  "england": "GB", "scotland": "GB", "korea": "KR", "republic of korea": "KR", "prc": "CN",
                  "finnland": "FI", "the netherlands": "NL", "macau": "MO"}
# Institutions that dblp or the roster name without a country.
_COUNTRY_HINTS = [
    ("CH", r"\beth\b|zurich|zürich|epfl|lausanne|\bidsia\b|swiss federal"),
    ("GB", r"\blse\b|london school|strathclyde|royal holloway|university of kent|oxford|cambridge|imperial college|\bucl\b|university college london|edinburgh|liverpool|manchester|"
           r"surrey|birmingham|southampton|warwick|king's college|queen mary|bristol|glasgow|\bdeepmind\b"),
    ("IL", r"technion|hebrew university|tel aviv|weizmann|bar-ilan|ben-gurion"),
    ("DE", r"\btum\b|technical university of munich|technische universität münchen|tübingen|tuebingen|cispa|saarland|"
           r"saarbrücken|konstanz|kassel|cologne|köln|rwth|aachen|freiburg|max planck|darmstadt|heidelberg|bosch|"
           r"bielefeld|stuttgart|karlsruhe|berlin|dresden|oldenburg|ludwig-maximilians"),
    ("AT", r"\bista\b|ist austria|institute of science and technology austria|klosterneuburg|tu wien|vienna|graz|linz"),
    ("FR", r"paul sabatier|aniti|\birit\b|sncf|foxstream|paris|espci|inria|sorbonne|toulouse|grenoble|\bens\b|cnrs|saclay|lille|lyon|thales|irt saint"),
    ("NL", r"delft|amsterdam|eindhoven|utrecht|radboud|twente|leiden"),
    ("BE", r"leuven|ghent|louvain|brussel|bruxelles|antwerp"),
    ("FR", r"payflows"),
    ("SA", r"kaust|king abdullah|saudi"),
    ("RU", r"moscow|skolkovo|skoltech|saint petersburg|innopolis"),
    ("SE", r"\bkth\b|lund|uppsala|chalmers|linköping"),
    ("DK", r"aalborg|copenhagen|\bdtu\b|aarhus"),
    ("VN", r"cmc corporation|cmc global|vietnam|hanoi|ho chi minh|vinai|vinuni|fpt software"),
    ("HU", r"szeged|budapest"),
    ("CZ", r"masaryk|prague|brno|czech technical"),
    ("CY", r"limassol|cyprus"),
    ("CN", r"southwest university|nanchang|chinese academy|peking|tsinghua|nanjing|east china normal|\becnu\b|zhejiang|shanghai|fudan|wuhan|"
           r"beijing|harbin|sun yat-sen|huazhong|xi'an|xidian|nankai|tianjin|sichuan|shenzhen|hunan|"
           r"university of science and technology of china|\bustc\b|alibaba|baidu|tencent|huawei|beihang|jilin|"
           r"guangzhou|zhengzhou|chongqing|hangzhou|southern university of science"),
    ("HK", r"hong kong"),
    ("TW", r"taiwan|national tsing hua|academia sinica"),
    ("SG", r"singapore|\bnus\b|nanyang|\bntu\b|\bsmu\b|a\*star"),
    ("AU", r"melbourne|sydney|monash|\banu\b|australian national|queensland|adelaide|unsw|csiro|data61|deakin|"
           r"western australia|macquarie"),
    ("CA", r"toronto|waterloo|simon fraser|british columbia|\bubc\b|mcgill|montr[eé]al|mila\b|alberta|ottawa|"
           r"vector institute|queen's university|calgary|concordia"),
    ("KR", r"kaist|seoul|korea|yonsei|postech|sungkyunkwan"),
    ("JP", r"tokyo|kyoto|nict|\bnii\b|national institute of informatics|osaka|kyushu|riken|tohoku|nagoya|japan"),
    ("IN", r"\biit\b|indian institute|bangalore|bengaluru|iisc|delhi|mumbai"),
    ("IT", r"verona|genoa|genova|padua|padova|venice|venezia|foscari|milano|milan|politecnico|roma|rome|torino|turin|pisa|bologna|padova|trento"),
    ("ES", r"madrid|barcelona|imdea|valencia"),
    ("US", r"\buiuc\b|ames research|kent state|liquid ai|consensys|international business machines|\bibm research|\bucsb\b|santa barbara|whiting school|siebel school|machine learning department|milwaukee|morgan stanley|massachusetts|\bmit\b|stanford|carnegie mellon|\bcmu\b|illinois|berkeley|university of california|"
           r"\bucla\b|\bucsd\b|uc san diego|princeton|harvard|columbia university|cornell|duke|purdue|penn state|"
           r"pennsylvania|university of texas|ut austin|maryland|virginia|wisconsin|university of chicago|michigan|"
           r"university of washington|washington university|vanderbilt|rutgers|johns hopkins|george mason|"
           r"stony brook|drexel|nebraska|southern california|\busc\b|nasa|northeastern|georgia tech|"
           r"georgia institute|caltech|california institute|new york university|\bnyu\b|yale|brown university|"
           r"boston|rice university|northwestern|university of minnesota|ohio state|arizona|utah|colorado|"
           r"oregon|florida|north carolina|iowa|indiana|kansas|kentucky|tennessee|notre dame|dartmouth|"
           r"lehigh|syracuse|case western|vmware|ibm|microsoft|nvidia|amazon|meta ai|\bmeta\b|openai|google|"
           r"toyota research|sri international|lawrence livermore|los alamos|sandia|argonne|oak ridge|"
           r"pacific northwest|mitre|\bnec labs|rice|tufts|emory|clemson|auburn|univ.* of houston|texas a&m|"
           r"university at buffalo|rensselaer|worcester|stevens|new jersey|delaware|missouri|alabama|"
           r"louisiana|vermont|new hampshire|connecticut|rhode island|wyoming|montana|idaho|nevada|"
           r"new mexico|oklahoma|arkansas|mississippi|south carolina|west virginia|maine|hawaii|alaska"),
]
_COUNTRY_RX = [(cc, re.compile(rx, re.I)) for cc, rx in _COUNTRY_HINTS]


def country_of(text):
    """ISO code of the country an affiliation string names (its last comma part) or implies (a known institution)."""
    t = (text or "").strip()
    if not t:
        return ""
    last = t.rsplit(",", 1)[-1].strip().lower().rstrip(".")
    if last in _COUNTRY_WORDS:
        return _COUNTRY_WORDS[last]
    for cc, rx in _COUNTRY_RX:
        if rx.search(t):
            return cc
    return ""
