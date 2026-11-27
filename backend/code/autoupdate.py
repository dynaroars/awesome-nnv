#!/usr/bin/env python3
"""Unattended daily update of Awesome NNV, modelled on vietprofs' scripts/maintain-roster.ts.

    python3 backend/code/autoupdate.py run            # what the 22:00 systemd timer runs (make auto)
    python3 backend/code/autoupdate.py run --dry-run  # fetch and report only: no Claude, no commit, no email
    python3 backend/code/autoupdate.py status

One run: refresh the paper lists (conference sites daily around a venue's notification date in acceptance.csv,
weekly otherwise; dblp daily, which re-reads only stale recent tables); watch arXiv for preprints by listed
researchers whose comment says they were accepted at a tracked conference (added to accepted.csv, tagged
unofficial); find notification dates still missing; label the new prefilter hits with Claude (yes / no, or
left undecided when unsure); write digest summaries and month summaries for new papers; rebuild, test and build;
then commit on local main WITHOUT pushing, and email a summary to the maintainer. Nothing goes live until the
maintainer says "ship" (git push, make publish).

Claude runs as `claude -p` with read and web tools only and returns JSON against a schema; this script alone
edits files, as in vietprofs. A run refuses to start on a dirty checkout or a branch other than main (and emails
why). A failed check stashes the run's changes (git stash list: "auto-failed ...") and emails the log.
The summary email goes through msmtp to the account named in AWESOME_NNV_MAIL (set by the maintainer; never
written in this repository). State and logs: ~/.local/state/awesome-nnv-auto (AWESOME_NNV_AUTO_STATE overrides).
"""
import argparse
import csv
import datetime
import fcntl
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

CODE = Path(__file__).resolve().parent
REPO = CODE.parent.parent
sys.path.insert(0, str(CODE))
from common import (ACCEPTED, AREA_KEYS, CSV_DIR, FRONTEND, ROSTER, TOPICS, VENUES, norm_name,  # noqa: E402
                    norm_title, read_csv, split_list)

STATE = Path(os.environ.get("AWESOME_NNV_AUTO_STATE") or Path.home() / ".local" / "state" / "awesome-nnv-auto")
MAIL = os.environ.get("AWESOME_NNV_MAIL", "")  # msmtp account, also the recipient
TODAY = datetime.date.today()
WINDOW = (-3, 21)  # days around a notification date in which the conference sites are re-read daily
ARXIV_DAYS = 3  # look-back of the daily arXiv watch (overlaps so a missed day is caught)
ARXIV_CATS = ["cs.LG", "cs.AI", "cs.CR", "cs.LO", "cs.SE", "cs.PL", "cs.CV", "cs.RO", "stat.ML", "eess.SY"]
LABEL_BATCH = 50
MODEL = os.environ.get("AWESOME_NNV_MODEL", "")
log_file = None


# ---------------------------------------------------------------- small helpers

def log(text):
    line = f"[{datetime.datetime.now():%H:%M:%S}] {text}"
    print(line, file=sys.stderr)
    if log_file:
        log_file.write(line + "\n")
        log_file.flush()


def sh(cmd, check=True, timeout=7200):
    """Run a command in the repository, logging its output."""
    log("$ " + (cmd if isinstance(cmd, str) else " ".join(cmd)))
    r = subprocess.run(cmd, cwd=REPO, shell=isinstance(cmd, str), capture_output=True, text=True, timeout=timeout)
    out = (r.stdout + r.stderr).strip()
    if out and log_file:
        log_file.write(out[-20000:] + "\n")
    if check and r.returncode:
        raise RuntimeError(f"{cmd} failed ({r.returncode}):\n{out[-3000:]}")
    return out


def write_rows(path, rows, fields):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def load_state():
    try:
        return json.loads((STATE / "state.json").read_text())
    except (OSError, ValueError):
        return {}


def save_state(state):
    (STATE / "state.json").write_text(json.dumps(state, indent=1, default=str))


def send_mail(subject, body):
    if not MAIL:
        log("AWESOME_NNV_MAIL is not set: summary saved to unsent-mail.txt instead of mailed")
        (STATE / "unsent-mail.txt").write_text(f"Subject: {subject}\n\n{body}\n")
        return
    msg = f"From: {MAIL}\nTo: {MAIL}\nSubject: {subject}\nContent-Type: text/plain; charset=utf-8\n\n{body}\n"
    try:
        subprocess.run(["msmtp", "-a", MAIL, MAIL], input=msg, text=True, check=True, timeout=120)
        log(f"mail sent: {subject}")
    except (OSError, subprocess.SubprocessError) as e:
        log(f"mail failed: {e}")
        (STATE / "unsent-mail.txt").write_text(msg)


# ---------------------------------------------------------------- Claude

def claude(prompt, schema, tools="Read,Grep,Glob,WebFetch,WebSearch", timeout=3600):
    """Structured answer from `claude -p` (read/web tools only), retrying rate limits with growing waits."""
    args = ["claude", "-p", "--output-format", "json", "--permission-mode", "dontAsk", "--json-schema",
            json.dumps(schema)]
    if tools:
        args += ["--allowedTools", tools]
    if MODEL:
        args += ["--model", MODEL]
    for attempt, wait in enumerate((0, 900, 1800, 3600)):
        if wait:
            log(f"claude: waiting {wait // 60} min before retry {attempt}")
            time.sleep(wait)
        r = subprocess.run(args + [prompt], cwd=REPO, capture_output=True, text=True, timeout=timeout)
        try:
            outer = json.loads(r.stdout)
        except ValueError:
            outer = {"is_error": True, "result": (r.stdout + r.stderr)[-2000:]}
        if not outer.get("is_error"):
            out = outer.get("structured_output") or outer.get("result")
            if isinstance(out, str):
                m = re.search(r"\{.*\}", out, re.S)
                out = json.loads(m.group(0)) if m else None
            if isinstance(out, dict):
                return out
        text = str(outer.get("result", ""))
        log(f"claude error: {text[:300]}")
        if not re.search(r"limit|overloaded|rate|529|429", text, re.I):
            break
    raise RuntimeError("claude did not return a usable answer")


def agent_rules():
    """The counting and area rules of AGENT.md, given to Claude verbatim."""
    text = (REPO / "AGENT.md").read_text()
    return text[text.index("- **Only NNV papers count**"):text.index("- **Name matches**")]


def items_schema(props, required):
    return {"type": "object", "required": ["items"], "properties": {"items": {"type": "array", "items": {
        "type": "object", "required": required, "properties": props}}}}


# ---------------------------------------------------------------- steps

def conference_windows(today=None):
    """(venue, year) pairs whose notification date is within WINDOW days of today."""
    today = today or TODAY
    out = set()
    for r in read_csv(CSV_DIR / "acceptance.csv"):
        if r["notified"]:
            d = (today - datetime.date.fromisoformat(r["notified"])).days
            if WINDOW[0] <= d <= WINDOW[1]:
                out.add((r["venue"], int(r["year"])))
    return sorted(out)


def fetch(state, report):
    windows = conference_windows()
    weekly = TODAY.isoformat() >= state.get("next_weekly", "")
    refresh = bool(windows) or weekly
    report["windows"] = [f"{v} {y}" for v, y in windows]
    report["weekly"] = weekly
    flag = " --refresh" if refresh else ""
    sh("cd backend/code && python3 fetch_dblp.py")
    sh(f"cd backend/code && python3 fetch_virtual.py{flag}")
    sh(f"cd backend/code && python3 fetch_researchr.py{flag}")
    sh(f"cd backend/code && python3 fetch_robotics.py{flag}")
    if weekly:
        state["next_weekly"] = (TODAY + datetime.timedelta(days=7)).isoformat()


VENUE_RX = {k: re.compile(p, re.I) for k, p in {
    "icml": r"\bICML\b", "iclr": r"\bICLR\b", "neurips": r"\bNeur ?IPS\b", "cvpr": r"\bCVPR\b", "iccv": r"\bICCV\b",
    "eccv": r"\bECCV\b", "pldi": r"\bPLDI\b", "popl": r"\bPOPL\b", "icfp": r"\bICFP\b", "oopsla": r"\bOOPSLA\b",
    "fse": r"\b(?:ESEC/)?FSE\b", "icse": r"\bICSE\b", "ase": r"\bASE\b", "issta": r"\bISSTA\b", "cav": r"\bCAV\b",
    "lics": r"\bLICS\b", "aaai": r"\bAAAI\b", "ijcai": r"\bIJCAI\b", "ccs": r"\bCCS\b",
    "sp": r"\bS&(?:amp;)?P\b|Symposium on Security and Privacy|\bOakland\b", "uss": r"USENIX Security",
    "ndss": r"\bNDSS\b", "icra": r"\bICRA\b", "iros": r"\bIROS\b", "rss": r"\bRSS\b|Robotics: Science and Systems",
}.items()}
NOT_MAIN = re.compile(r"workshop|tiny paper|findings|\bdemo|doctoral|student abstract|extended abstract", re.I)


def tracked_venues(comment):
    """Tracked venues a comment names as the place of acceptance; [] for workshops, demos and the like."""
    if NOT_MAIN.search(comment) or not re.search(r"accept|appear|to be published", comment, re.I):
        return []
    return [k for k, rx in VENUE_RX.items() if rx.search(comment)]


def roster_names():
    names = {}
    for r in read_csv(ROSTER):
        if r["approved"] == "yes":
            for n in [r["name"], *split_list(r["aliases"])]:
                names[norm_name(n)] = r["name"]
    return names


def arxiv_candidates(days=ARXIV_DAYS):
    """Recent arXiv preprints whose comment says accepted at a tracked venue and with a listed researcher among
    their authors: [{id, title, comment, authors, venues, researchers, published}]."""
    names = roster_names()
    cats = "+OR+".join(f"cat:{c}" for c in ARXIV_CATS)
    since = TODAY - datetime.timedelta(days=days)
    out, start = [], 0
    while start < 2000:
        url = (f"https://export.arxiv.org/api/query?search_query=%28{cats}%29+AND+%28co:accepted+OR+co:accept+OR+"
               f"co:appear%29&sortBy=submittedDate&sortOrder=descending&start={start}&max_results=200")
        req = urllib.request.Request(url, headers={"User-Agent": "awesome-nnv/1.0 (research statistics script)"})
        data = urllib.request.urlopen(req, timeout=120).read().decode("utf-8", "replace")
        entries = re.findall(r"<entry>(.*?)</entry>", data, re.S)
        if not entries:
            break
        old = False
        for e in entries:
            published = re.search(r"<published>(\d{4}-\d\d-\d\d)", e).group(1)
            if datetime.date.fromisoformat(published) < since:
                old = True
                continue
            m = re.search(r"<arxiv:comment[^>]*>(.*?)</arxiv:comment>", e, re.S)
            comment = re.sub(r"\s+", " ", m.group(1)).strip() if m else ""
            venues = tracked_venues(comment)
            if not venues:
                continue
            authors = [re.sub(r"\s+", " ", a).strip() for a in re.findall(r"<name>(.*?)</name>", e, re.S)]
            listed = sorted({names[norm_name(a)] for a in authors if norm_name(a) in names})
            if listed:
                aid = re.search(r"<id>https?://arxiv.org/abs/([^<]+?)(?:v\d+)?</id>", e).group(1)
                title = re.sub(r"\s+", " ", re.search(r"<title>(.*?)</title>", e, re.S).group(1)).strip()
                out.append({"id": aid, "title": title, "comment": comment, "authors": authors, "venues": venues,
                            "researchers": listed, "published": published})
        if old:
            break
        start += 200
        time.sleep(3)
    return out


def arxiv_watch(report, dry):
    from common import all_papers
    cands = arxiv_candidates()
    have = {(r["venue"], norm_title(r["title"])) for r in read_csv(ACCEPTED)}
    have |= {(p["venue"], norm_title(p["title"])) for p in all_papers()}
    cands = [c for c in cands if not any((v, norm_title(c["title"])) in have for v in c["venues"])]
    report["arxiv_seen"] = len(cands)
    if not cands or dry:
        report["arxiv_candidates"] = cands
        return
    schema = items_schema({"id": {"type": "string"}, "add": {"type": "boolean"}, "venue": {"type": "string"},
                           "year": {"type": "integer"}, "reason": {"type": "string"}},
                          ["id", "add", "venue", "year", "reason"])
    prompt = (
        "You check arXiv preprints for the Awesome NNV site. Each item below is a recent preprint by a researcher the "
        "site lists, whose arXiv comment says it was accepted somewhere. For each, decide `add` = true only when ALL "
        "hold: (1) the paper is in scope under the rules below (read the abstract at https://arxiv.org/abs/<id> with "
        "WebFetch if the title is not enough); (2) the comment states acceptance (not 'submitted' or 'under review') "
        "at the MAIN research track of one of these venues: "
        + ", ".join(f"{v['key']} = {v['full_name']}" for v in VENUES)
        + "; workshops, findings, demos, poster-only tracks, student abstracts and journal-first do not count. "
        "Give `venue` as the key above and `year` as the edition year of the conference (e.g. 'ICLR 2027' -> 2027; "
        "for OOPSLA/POPL/PLDI/ICFP the PACMPL edition year). `reason`: one short sentence quoting the comment.\n\n"
        f"RULES:\n{agent_rules()}\n\nITEMS:\n" + json.dumps(cands, ensure_ascii=False, indent=1))
    answer = {x["id"]: x for x in claude(prompt, schema)["items"]}
    rows = list(read_csv(ACCEPTED))
    fields = list(rows[0].keys()) if rows else ["venue", "year", "title", "authors", "track", "source_url", "fetched",
                                                "note"]
    added, skipped = [], []
    for c in cands:
        a = answer.get(c["id"]) or {}
        if a.get("add") and a.get("venue") in VENUE_RX and (a["venue"], norm_title(c["title"])) not in have:
            rows.append({"venue": a["venue"], "year": str(a["year"]), "title": c["title"],
                         "authors": "; ".join(c["authors"]), "track": "main",
                         "source_url": f"https://arxiv.org/abs/{c['id']}", "fetched": TODAY.isoformat(),
                         "note": f"arXiv comment: \"{c['comment']}\"; added by the automatic update ({a['reason']})"})
            added.append({**c, "venue": a["venue"], "year": a["year"]})
        else:
            skipped.append({**c, "reason": a.get("reason", "no answer")})
    if added:
        write_rows(ACCEPTED, rows, fields)
    report["arxiv_added"], report["arxiv_skipped"] = added, skipped


def label_topics(report, dry):
    sh("cd backend/code && python3 scan_topics.py" + (" --dry-run" if dry else ""))
    if dry:
        return
    rows = list(read_csv(TOPICS))
    fields = list(rows[0].keys())
    todo = [r for r in rows if not r["decision"]]
    report["prefilter_new"] = len(todo)
    if not todo:
        return
    schema = items_schema({"key": {"type": "string"}, "decision": {"type": "string", "enum": ["yes", "no", "unsure"]},
                           "area": {"type": "string"}, "tags": {"type": "array", "items": {"type": "string"}},
                           "basis": {"type": "string", "enum": ["title", "abstract"]}, "reason": {"type": "string"}},
                          ["key", "decision", "area", "tags", "basis", "reason"])
    by_key = {r["key"]: r for r in rows}
    yes, unsure = [], []
    for k in range(0, len(todo), LABEL_BATCH):
        batch = todo[k:k + LABEL_BATCH]
        prompt = (
            "Label papers for the Awesome NNV site, which counts neural-network verification (NNV) papers. Each item "
            "is a title that a broad keyword prefilter flagged. Decide yes / no by the rules below; when the title is "
            "not enough, read the abstract (dblp record https://dblp.org/rec/<key>, the DOI, arXiv or OpenReview) "
            "with WebFetch and set basis = abstract. Use unsure only when you still cannot tell. For yes give one "
            f"primary `area` and optional secondary `tags`, all from: {', '.join(AREA_KEYS)}. For no, area '' and "
            "tags []. `reason`: a few words (e.g. 'empirical attack, no certificate').\n\n"
            f"RULES:\n{agent_rules()}\n\nITEMS:\n"
            + json.dumps([{x: r[x] for x in ("key", "venue", "year", "title")} for r in batch], ensure_ascii=False))
        for a in claude(prompt, schema)["items"]:
            r = by_key.get(a["key"])
            if not r or r["decision"]:
                continue
            area = a["area"] if a["area"] in AREA_KEYS else ""
            if a["decision"] == "unsure" or (a["decision"] == "yes" and not area):
                unsure.append({**r, "reason": a["reason"]})
                continue
            r["decision"] = a["decision"]
            r["area"] = area if a["decision"] == "yes" else ""
            r["tags"] = ";".join(t for t in a["tags"] if t in AREA_KEYS and t != area) if a["decision"] == "yes" else ""
            r["note"] = f"{a['basis']}, Claude (automatic update) {TODAY}; {a['reason']}"
            if a["decision"] == "yes":
                yes.append(r)
        write_rows(TOPICS, rows, fields)
    report["labelled_yes"] = [{x: r[x] for x in ("venue", "year", "title", "area")} for r in yes]
    report["unsure"] = [{x: r[x] for x in ("key", "venue", "year", "title", "reason")} for r in unsure]


def notification_dates(report):
    """Ask for notification dates the digest still lacks (undated in-scope papers), at most 6 venue-years a run."""
    d = json.loads((FRONTEND / "data" / "digest.json").read_text())
    have = {(r["venue"], int(r["year"])) for r in read_csv(CSV_DIR / "acceptance.csv")}
    need = [n for n in sorted({(p["venue"], p["year"]) for p in d.get("undated", [])}) if n not in have][:6]
    report["dates_needed"] = [f"{v} {y}" for v, y in need]
    if not need:
        return
    schema = items_schema({"venue": {"type": "string"}, "year": {"type": "integer"}, "cycle": {"type": "string"},
                           "notified": {"type": "string"}, "source_url": {"type": "string"},
                           "quote": {"type": "string"}},
                          ["venue", "year", "cycle", "notified", "source_url", "quote"])
    prompt = (
        "Find the official paper-acceptance NOTIFICATION date (when authors learn their main-track paper is accepted; "
        "not the conference or camera-ready date) of each conference edition below, from the conference's own "
        "important-dates or call-for-papers page (an archived copy on web.archive.org is acceptable). Never answer "
        "from memory: give `source_url` you actually read and `quote` = the verbatim line stating the date. Return "
        "one item per submission cycle (cycle '' for a single cycle; for OOPSLA name the PACMPL issue, e.g. "
        "OOPSLA1). Leave an edition out if no page you read states its date. notified = YYYY-MM-DD.\n\n"
        + json.dumps([{"venue": v, "year": y, "conference": next(x["full_name"] for x in VENUES if x["key"] == v)}
                      for v, y in need]))
    rows = list(read_csv(CSV_DIR / "acceptance.csv"))
    fields = list(rows[0].keys())
    added = []
    for a in claude(prompt, schema)["items"]:
        if (a["venue"], a["year"]) in need and re.fullmatch(r"\d{4}-\d\d-\d\d", a["notified"]) and a["quote"] \
                and a["source_url"].startswith("http"):
            rows.append({"venue": a["venue"], "year": str(a["year"]), "cycle": a["cycle"], "notified": a["notified"],
                         "source_url": a["source_url"],
                         "note": f"\"{a['quote']}\"; found by the automatic update {TODAY}"})
            added.append(" ".join(x for x in (a["venue"], str(a["year"]), a["cycle"], a["notified"]) if x))
    if added:
        rows.sort(key=lambda r: (r["venue"], r["year"], r["notified"] or "9999"))
        write_rows(CSV_DIR / "acceptance.csv", rows, fields)
    report["dates_added"] = added


def digest_text(report, before):
    """Summaries for new in-scope papers that have an abstract; month summaries for months whose papers changed."""
    sh("cd backend/code && python3 fetch_abstracts.py")
    abstracts = json.loads((REPO / "backend" / "work" / "abstracts.json").read_text())
    papers = {p["key"]: p for p in json.loads((FRONTEND / "data" / "papers.json").read_text()) if p.get("area")}

    def ident(v, y, t):
        return f"{v}/{y}/{norm_title(t)}"
    key_of = {ident(p["venue"], p["year"], p["title"]): k for k, p in papers.items()}
    path = CSV_DIR / "digest.csv"
    rows = list(read_csv(path))
    fields = list(rows[0].keys())
    todo = []
    for r in rows:
        k = key_of.get(ident(r["venue"], r["year"], r["title"]))
        if k and not r["summary"] and (abstracts.get(k) or {}).get("abstract"):
            todo.append((r, k))
    schema = items_schema({"key": {"type": "string"}, "summary": {"type": "string"}}, ["key", "summary"])
    done = 0
    for k in range(0, len(todo), 40):
        batch = todo[k:k + 40]
        prompt = (
            "Write one-line summaries for a monthly digest of neural-network verification papers. For each item: one "
            "or two sentences, 25-45 words, in your own words (no copied sentences, no quotes); say what is "
            "verified or certified (model, property), how, and the headline result if the abstract states one. Use "
            "only facts in the abstract. Plain tone, no hype, no first person, no 'This paper' opener. If the "
            "abstract is clearly about a different paper than the title, return summary ''.\n\nITEMS:\n"
            + json.dumps([{"key": key, "title": papers[key]["title"], "abstract": abstracts[key]["abstract"]}
                          for _, key in batch], ensure_ascii=False))
        answer = {a["key"]: a["summary"] for a in claude(prompt, schema, tools="")["items"]}
        for r, key in batch:
            if answer.get(key):
                r["summary"], r["basis"] = answer[key], abstracts[key]["source"]
                r["written"] = f"{TODAY} (Claude, from the abstract; automatic update)"
                done += 1
    write_rows(path, rows, fields)
    report["summaries"] = done
    sh("cd backend/code && python3 build_site_data.py")
    after = json.loads((FRONTEND / "data" / "digest.json").read_text())
    changed = [m for m in after["months"] if sorted(p["key"] for p in m["papers"]) != before.get(m["month"])]
    report["months_changed"] = [m["label"] for m in changed]
    if not changed:
        return
    schema = items_schema({"month": {"type": "string"}, "intro": {"type": "string"}}, ["month", "intro"])
    prompt = (
        "Write the short 'what happened this month' summary of each month below for a monthly digest of "
        "neural-network verification papers (the papers whose acceptance was announced that month). 1 to 3 "
        "sentences, at most 70 words: which conference decisions arrived and the main themes, naming a tool or "
        "method only if a title or summary names it. No paper counts, no ranking of months, only facts from the "
        "titles and summaries, plain tone, start with the substance (e.g. 'ICLR 2027 decisions: ...').\n\n"
        + json.dumps([{"month": m["month"], "venues": m["venues"],
                       "papers": [{"title": p["title"], "venue": f"{p['venue_name']} {p['year']}",
                                   "summary": p["summary"]} for p in m["papers"]]} for m in changed],
                     ensure_ascii=False))
    intros = {a["month"]: a["intro"] for a in claude(prompt, schema, tools="")["items"]}
    path = CSV_DIR / "digest_months.csv"
    rows = {r["month"]: r for r in read_csv(path)}
    for m, text in intros.items():
        if text and m in {x["month"] for x in changed}:
            rows[m] = {"month": m, "intro": text, "written": f"{TODAY} (Claude, automatic update)"}
    write_rows(path, [rows[m] for m in sorted(rows)], ["month", "intro", "written"])


# ---------------------------------------------------------------- the run

def email_body(report, committed, error=""):
    out = [f"Awesome NNV automatic update, {TODAY}", ""]
    if error:
        out += ["FAILED. The run's changes were stashed (git stash list: auto-failed); the site is unchanged.", "",
                error, ""]
    out.append(f"Conference sites re-read: {'weekly refresh' if report.get('weekly') else 'no weekly refresh'}"
               + (f"; notification windows: {', '.join(report['windows'])}" if report.get("windows") else ""))
    out.append(f"New prefilter hits labelled: {report.get('prefilter_new', 0)}")
    if report.get("labelled_yes"):
        out += ["", "New NNV papers:"] + [f"  - {p['venue'].upper()} {p['year']}: {p['title']} [{p['area']}]"
                                         for p in report["labelled_yes"]]
    if report.get("arxiv_added"):
        out += ["", "Accepted papers announced on arXiv by listed researchers (added as unofficial):"]
        out += [f"  - {p['venue'].upper()} {p['year']}: {p['title']} ({', '.join(p['researchers'])}) "
                f"https://arxiv.org/abs/{p['id']}" for p in report["arxiv_added"]]
    if report.get("arxiv_candidates"):
        out += ["", "arXiv acceptances by listed researchers (not checked in a dry run):"]
        out += [f"  - {p['title']} ({', '.join(p['researchers'])}): {p['comment']}" for p in report["arxiv_candidates"]]
    if report.get("arxiv_skipped"):
        out += ["", "arXiv acceptances by listed researchers, not added:"]
        out += [f"  - {p['title']} ({', '.join(p['researchers'])}): {p['reason']}" for p in report["arxiv_skipped"]]
    needs = [f"  - unsure: {p['venue'].upper()} {p['year']}: {p['title']} ({p['reason']}) [{p['key']}]"
             for p in report.get("unsure", [])]
    needs += [f"  - new candidate with 2+ NNV papers: {c}" for c in report.get("new_candidates", [])]
    needs += [f"  - notification date still unknown: {d}" for d in report.get("dates_needed", [])
              if not any(x.startswith(d) for x in report.get("dates_added", []))]
    if needs:
        out += ["", "Needs you:"] + needs
    if report.get("dates_added"):
        out += ["", "Notification dates added: " + "; ".join(report["dates_added"])]
    if report.get("summaries") or report.get("months_changed"):
        out += ["", f"Digest: {report.get('summaries', 0)} paper summaries written; month summaries updated: "
                    f"{', '.join(report.get('months_changed', [])) or 'none'}"]
    out.append("")
    if committed:
        out += [f"Committed on local main ({committed}), not pushed; {report.get('unpushed', 0)} commit(s) waiting.",
                "To publish: say \"ship\" in a Claude session in awesome-nnv, or run: git push origin main && make publish",
                "To drop this update before shipping: git reset --hard HEAD~1"]
    elif not error:
        out.append("Nothing changed; no commit.")
    out += ["", f"Log: {STATE / 'logs' / (TODAY.isoformat() + '.log')}"]
    return "\n".join(out)


def preflight():
    branch = sh(["git", "rev-parse", "--abbrev-ref", "HEAD"])
    if branch != "main":
        return f"the checkout is on branch {branch}, not main"
    if sh(["git", "status", "--porcelain"]):
        return "the checkout has uncommitted changes (commit, stash or ship them first)"
    if subprocess.run(["claude", "auth", "status"], capture_output=True).returncode:
        return "the claude CLI is not logged in (run: claude auth login)"
    return ""


def run(args):
    global log_file
    (STATE / "logs").mkdir(parents=True, exist_ok=True)
    lock = open(STATE / "lock", "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        print("another run is active", file=sys.stderr)
        return 1
    log_file = open(STATE / "logs" / f"{TODAY}.log", "a")
    state, report = load_state(), {}
    why = "" if args.dry_run else preflight()
    if why:
        log(f"not started: {why}")
        if not args.no_email:
            send_mail(f"[awesome-nnv] automatic update skipped {TODAY}", f"The automatic update did not run: {why}.")
        return 1
    digest_path = FRONTEND / "data" / "digest.json"
    before = {m["month"]: sorted(p["key"] for p in m["papers"])
              for m in json.loads(digest_path.read_text())["months"]} if digest_path.exists() else {}
    cand_path = CSV_DIR / "candidates.csv"
    old_cands = {r.get("name") for r in read_csv(cand_path)} if cand_path.exists() else set()
    committed, error = "", ""
    try:
        fetch(state if not args.dry_run else dict(state), report)
        arxiv_watch(report, args.dry_run)
        label_topics(report, args.dry_run)
        if args.dry_run:
            print(email_body(report, ""))
            return 0
        sh("make data")
        notification_dates(report)
        digest_text(report, before)
        sh("make citations", check=False)
        sh("make data")
        report["new_candidates"] = sorted(r["name"] for r in read_csv(cand_path) if r.get("name") not in old_cands)[:20]
        sh("make test")
        sh("make build")
        if sh(["git", "status", "--porcelain"]):
            n_yes, n_arx = len(report.get("labelled_yes", [])), len(report.get("arxiv_added", []))
            title = (f"Automatic update {TODAY}: {n_yes} new NNV paper{'s' * (n_yes != 1)}, {n_arx} arXiv "
                     f"acceptance{'s' * (n_arx != 1)}, {report.get('summaries', 0)} digest summaries")
            sh(["git", "add", "-A"])
            sh(["git", "commit", "-q", "-m", title + "\n\nCo-Authored-By: Claude <noreply@anthropic.com>"])
            committed = sh(["git", "rev-parse", "--short", "HEAD"])
        report["unpushed"] = int(sh(["git", "rev-list", "--count", "origin/main..main"], check=False) or 0)
        state["last_success"] = datetime.datetime.now().isoformat(timespec="seconds")
    except Exception as e:  # keep the checkout clean and tell the maintainer
        error = str(e)[-3000:]
        log(f"FAILED: {error}")
        if not args.dry_run:
            sh(["git", "stash", "push", "-u", "-m", f"auto-failed {TODAY}"], check=False)
    finally:
        if not args.dry_run:
            state["last_run"] = datetime.datetime.now().isoformat(timespec="seconds")
            state["last_report"] = report
            save_state(state)
    if not args.no_email and not args.dry_run and (committed or error or report.get("unsure") or args.always_email):
        n = len(report.get("labelled_yes", [])) + len(report.get("arxiv_added", []))
        subject = (f"[awesome-nnv] update FAILED {TODAY}" if error else
                   f"[awesome-nnv] {n} new paper{'s' * (n != 1)}, ready to ship ({TODAY})" if committed else
                   f"[awesome-nnv] nothing new ({TODAY})")
        send_mail(subject, email_body(report, committed, error))
    return 1 if error else 0


def status():
    state = load_state()
    print(json.dumps({k: state.get(k) for k in ("last_run", "last_success", "next_weekly")}, indent=1))
    print("unpushed commits:", sh(["git", "rev-list", "--count", "origin/main..main"], check=False))
    print(subprocess.run(["systemctl", "--user", "list-timers", "awesome-nnv-auto.timer", "--no-pager"],
                         capture_output=True, text=True).stdout.strip())


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("command", choices=["run", "status"])
    ap.add_argument("--dry-run", action="store_true", help="fetch and report only: no Claude, no commit, no email")
    ap.add_argument("--no-email", action="store_true")
    ap.add_argument("--always-email", action="store_true", help="email even when nothing changed")
    args = ap.parse_args()
    if args.command == "status":
        return status()
    return run(args)


if __name__ == "__main__":
    sys.exit(main() or 0)
