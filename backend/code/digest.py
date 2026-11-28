"""Monthly digest: the NNV papers accepted each month, each with a short summary, kept as a permanent record.

A paper's month is its acceptance (notification) month, not the month the conference meets: papers are usually shared
when they are accepted. Dates come from `acceptance.csv` (one row per venue, year and submission cycle, read from the
conference's own pages), resolved per paper in this order:
  1. the paper's own date in `digest.csv` (`accepted`, with `accepted_source`);
  2. the venue-year's notification date when it has one cycle;
  3. for several cycles, the cycle named like the paper's journal issue (OOPSLA1, OOPSLA2); otherwise the last
     notification not after the day the acceptance was first seen (approximate: the paper may come from an earlier
     cycle);
  4. none: the paper is listed under "no acceptance date yet", never placed by its conference month.
`digest.csv` is the record: one row per paper, keyed by venue, year and normalized title (paper keys change when dblp
replaces a conference-site record), never deleted. `digest_months.csv` holds each month's short introduction.
"""
import argparse
import calendar
import csv
import datetime
import gzip
import json
import re
import sys
import zoneinfo

from common import CSV_DIR, FRONTEND, RAW, virtual_track, VENUE_NAME, conference_month, norm_title, read_csv, read_json

ACCEPTANCE = CSV_DIR / "acceptance.csv"
DIGEST = CSV_DIR / "digest.csv"
DIGEST_MONTHS = CSV_DIR / "digest_months.csv"
ACCEPTED = CSV_DIR / "accepted.csv"
# Every conference year since 2017 is covered; the record started on LAUNCH, and only rows added after both their
# month and the launch say "added later".
FIRST_YEAR = 2017
LAUNCH = datetime.date(2026, 11, 27)
DIGEST_FIELDS = ["venue", "year", "title", "accepted", "accepted_source", "summary", "basis", "written", "added"]


def ident(venue, year, title):
    return f"{venue}/{year}/{norm_title(title)}"


def day(text):
    return datetime.date.fromisoformat(text) if text else None


def notifications():
    """(venue, year) -> [(date, cycle, source url)], oldest first."""
    out = {}
    for r in read_csv(ACCEPTANCE) if ACCEPTANCE.exists() else []:
        if r["notified"]:
            out.setdefault((r["venue"], int(r["year"])), []).append((day(r["notified"]), r["cycle"], r["source_url"]))
    return {k: sorted(v) for k, v in out.items()}


def seen_dates():
    """ident -> the day an author-page acceptance was first recorded (accepted.csv `fetched`)."""
    return {ident(r["venue"], int(r["year"]), r["title"]): day(r["fetched"])
            for r in (read_csv(ACCEPTED) if ACCEPTED.exists() else []) if r.get("fetched")}


def resolve(venue, year, row, cycles, seen=None, today=None, issue=""):
    """{date, approx, cycle, source} or None, following the order in the module docstring; a paper's journal issue
    (OOPSLA1, OOPSLA2) picks the cycle of the same name."""
    if row and row.get("accepted"):
        return {"date": day(row["accepted"]), "approx": False, "cycle": "", "source": row.get("accepted_source", "")}
    if not cycles:
        return None
    named = [c for c in cycles if issue and c[1] and c[1].lower() == issue.lower()]
    if named:
        d, cycle, src = named[0]
        return {"date": d, "approx": False, "cycle": cycle, "source": src}
    if len(cycles) == 1:
        d, cycle, src = cycles[0]
        return {"date": d, "approx": False, "cycle": cycle, "source": src}
    limit = seen or today or datetime.date.today()
    past = [c for c in cycles if c[0] <= limit] or cycles[:1]
    d, cycle, src = past[-1]
    return {"date": d, "approx": True, "cycle": cycle, "source": src}


def in_scope(papers=None):
    """The NNV papers of the conference years the digest covers (papers.json entries)."""
    papers = papers if papers is not None else read_json(FRONTEND / "data" / "papers.json", [])
    return [p for p in papers if p.get("area") and p["year"] >= FIRST_YEAR]


def read_record():
    return {ident(r["venue"], int(r["year"]), r["title"]): r for r in read_csv(DIGEST)} if DIGEST.exists() else {}


def update(papers=None, today=None):
    """Add a row for every in-scope paper that has none yet; existing rows are kept as they are."""
    today = (today or datetime.date.today()).isoformat()
    rows = list(read_csv(DIGEST)) if DIGEST.exists() else []
    have = {ident(r["venue"], int(r["year"]), r["title"]) for r in rows}
    added = 0
    for p in in_scope(papers):
        k = ident(p["venue"], p["year"], p["title"])
        if k not in have:
            have.add(k)
            rows.append({"venue": p["venue"], "year": str(p["year"]), "title": p["title"], "accepted": "",
                         "accepted_source": "", "summary": "", "basis": "", "written": "", "added": today})
            added += 1
    with open(DIGEST, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=DIGEST_FIELDS)
        w.writeheader()
        w.writerows(rows)
    return added


SITE = {"Sydney": ("AU", "Australia/Sydney"), "Atlanta": ("US", "America/New_York"), "Paris": ("FR", "Europe/Paris")}


def sites(venue, year):
    f = RAW / "virtual" / f"{venue}-{year}.json.gz"
    if not f.exists():
        return None
    al = json.loads(gzip.open(f).read()).get("results", [])
    hs = sum(1 for r in al if r.get("sourceurl")) > len(al) / 2
    rs = [r for r in al if r.get("event_type") in ("Poster", "Oral") and r.get("starttime") and r.get("name")
          and virtual_track(r["name"], r.get("sourceurl"), r.get("event_type"), hs) == "main"]
    cy = lambda r: (r.get("session") or "").split(" ")[0]
    room = {r["room_name"]: cy(r) for r in rs if cy(r) in SITE and r.get("room_name")}
    if not room:
        return None
    by = {}
    for r in rs:
        by.setdefault(ident(venue, year, r["name"]), []).append(r)
    out, tot = {}, {}
    for k, v in by.items():
        home = next((cy(r) for r in v if cy(r) in SITE), "")
        if home:
            tot[home] = tot.get(home, 0) + 1
        w = []
        for r in sorted(v, key=lambda r: (r["event_type"] != "Poster", r["starttime"])):
            c = cy(r) if cy(r) in SITE else room.get(r.get("room_name")) or home
            if c not in SITE:
                continue
            z = zoneinfo.ZoneInfo(SITE[c][1])
            a = datetime.datetime.fromisoformat(r["starttime"]).astimezone(z)
            b = datetime.datetime.fromisoformat(r["endtime"]).astimezone(z) if r.get("endtime") else None
            t = a.strftime("%a %-d %b, %H:%M") + (b.strftime("–%H:%M") if b else "")
            w.append({"at": a.astimezone(datetime.timezone.utc).isoformat(), "city": c, "flag": SITE[c][0], "kind": r["event_type"], "pos": r.get("poster_position") or "",
                      "room": re.sub(r"\s+-\s+", "–", re.sub(r"\s+", " ", r.get("room_name") or "")).strip(), "when": t})
        out[k] = w
    return out, tot


def kind(t):
    t = t.lower()
    if "oral" in t or "talk" in t or "top-5%" in t or "long presentation" in t:
        return "oral"
    if "spotlight" in t or "top-25%" in t:
        return "spotlight"
    return ""


def presentations(papers):
    rk, out = {"": 0, "spotlight": 1, "oral": 2}, {}
    for v, y in {(p["venue"], p["year"]) for p in papers}:
        f = RAW / "virtual" / f"{v}-{y}.json.gz"
        if not f.exists():
            continue
        for r in json.loads(gzip.open(f).read()).get("results", []):
            if not r.get("name"):
                continue
            d = r.get("decision") or ""
            x = "" if (v, y) == ("icml", 2021) and kind(d) == "spotlight" else kind(d)
            if "oral" in f"{r.get('event_type') or ''} {r.get('eventtype') or ''}".lower():
                x = "oral"
            k = ident(v, y, r["name"])
            if rk[x] > rk[out.get(k, "")]:
                out[k] = x
    return out


def vlogo(v):
    return next((f"img/venues/{v}.{x}" for x in ("svg", "png") if (FRONTEND / "static" / "img" / "venues" / f"{v}.{x}").exists()), "")


def month_label(month):
    y, m = month.split("-")
    return f"{calendar.month_name[int(m)]} {y}"


def accepted(papers, today=None):
    rec, cyc, seen = read_record(), notifications(), seen_dates()
    out = {}
    for p in papers:
        k = ident(p["venue"], p["year"], p["title"])
        w = resolve(p["venue"], p["year"], rec.get(k), cyc.get((p["venue"], p["year"])), seen.get(k), today, p.get("issue", ""))
        out[p["key"]] = w["date"].isoformat() if w else ""
    return out


def build(papers, warn=lambda text: None, today=None):
    """digest.json: the months (newest first) with their papers, and the in-scope papers without an acceptance date."""
    today = today or datetime.date.today()
    record, cycles, seen = read_record(), notifications(), seen_dates()
    intros = {r["month"]: r for r in read_csv(DIGEST_MONTHS)} if DIGEST_MONTHS.exists() else {}
    months, undated, sw = {}, [], {}
    pr = presentations(in_scope(papers))
    for p in in_scope(papers):
        k = ident(p["venue"], p["year"], p["title"])
        row = record.get(k)
        if row is None:
            warn(f"digest: no digest.csv row for {p['key']} (run digest.py)")
        when = resolve(p["venue"], p["year"], row, cycles.get((p["venue"], p["year"])), seen.get(k), today,
                       p.get("issue", ""))
        entry = {**p, "summary": (row or {}).get("summary", ""), "basis": (row or {}).get("basis", ""), "pres": pr.get(k, "")}
        vy = (p["venue"], p["year"])
        if vy not in sw:
            sw[vy] = sites(*vy)
        if sw[vy] is not None:
            entry["where"] = sw[vy][0].get(k, [])
            for w in entry["where"]:
                w["total"] = sw[vy][1].get(w["city"], 0)
            if not entry["where"]:
                warn(f"digest: {p['key']} not found in the {p['venue']} {p['year']} schedule")
        if not when:
            undated.append(entry)
            continue
        month = when["date"].strftime("%Y-%m")
        if month > conference_month(p["venue"], p["year"]):
            warn(f"digest: {p['key']} accepted {when['date']} after its conference month {conference_month(p['venue'], p['year'])}")
        end = datetime.date(when["date"].year, when["date"].month, calendar.monthrange(when["date"].year, when["date"].month)[1])
        added = day((row or {}).get("added", ""))
        late = added and added > end and added > LAUNCH
        entry.update(accepted=when["date"].isoformat(), approx=when["approx"], cycle=when["cycle"],
                     accepted_source=when["source"], late=added.isoformat() if late else "")
        months.setdefault(month, []).append(entry)
    out = []
    for month in sorted(months, reverse=True):
        items = sorted(months[month], key=lambda e: (e["accepted"], e["venue_name"], e["title"]))
        venues = sorted({(e["venue_name"], e["year"]) for e in items})
        vc = {}
        for e in items:
            vc.setdefault((e["venue"], e["venue_name"], e["year"]), 0)
            vc[(e["venue"], e["venue_name"], e["year"])] += 1
        vl = [{"key": v, "name": n, "year": y, "n": c, "logo": vlogo(v)} for (v, n, y), c in sorted(vc.items(), key=lambda x: (-x[1], x[0][1]))]
        gs = {}
        for e in items:
            w = (e.get("where") or [{}])[0]
            gs.setdefault(w.get("city") or e["venue_name"], {"name": w.get("city") or e["venue_name"], "flag": w.get("flag", ""),
                                                            "total": w.get("total", 0), "label": f"{e['venue_name']} {e['year']}", "papers": []})["papers"].append(e)
        for g in gs.values():
            g["papers"].sort(key=lambda e: (e.get("where") or [{}])[0].get("at", ""))
        intro = intros.get(month, {})
        out.append({"month": month, "label": month_label(month), "in_progress": month == today.strftime("%Y-%m"),
                    "intro": intro.get("intro", ""), "papers": items, "count": len(items),
                    "groups": sorted(gs.values(), key=lambda g: -len(g["papers"])),
                    "venues": [f"{v} {y}" for v, y in venues], "vlist": vl,
                    "summarised": sum(1 for e in items if e["summary"])})
    years = []
    for m in out:
        y = m["month"][:4]
        if not years or years[-1]["year"] != y:
            years.append({"year": y, "months": [], "count": 0})
        years[-1]["months"].append(m["month"])
        years[-1]["count"] += m["count"]
    return {"first_year": FIRST_YEAR, "months": out, "years": years, "undated": sorted(undated, key=lambda e: (e["venue_name"], e["title"])),
            "generated": today.isoformat()}


def main():
    ap = argparse.ArgumentParser(description="Add a digest.csv row for every NNV paper the monthly digest covers, and list those without a summary or an acceptance date.")
    ap.parse_args()
    papers = read_json(FRONTEND / "data" / "papers.json", [])
    added = update(papers)
    d = build(papers)
    missing = [e for m in d["months"] for e in m["papers"] if not e["summary"]]
    print(f"{added} rows added to digest.csv; {sum(m['count'] for m in d['months'])} papers in {len(d['months'])} months, "
          f"{len(missing)} without a summary, {len(d['undated'])} without an acceptance date", file=sys.stderr)
    for e in d["undated"]:
        print(f"  no acceptance date: {VENUE_NAME[e['venue']]} {e['year']} {e['title'][:80]}", file=sys.stderr)


if __name__ == "__main__":
    main()
