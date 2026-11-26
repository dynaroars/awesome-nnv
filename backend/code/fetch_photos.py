import argparse
import csv
import datetime
import hashlib
import json
import os
import re
import socket
import subprocess
import sys
import time
import urllib.parse

socket.setdefaulttimeout(90)


def _timeout_requests():
    """openreview-py sends its requests with no timeout and a slow search can hang for ever: give every request 60 s."""
    import requests

    original = requests.Session.request

    def request(self, *args, **kwargs):
        if kwargs.get("timeout") is None:
            kwargs["timeout"] = 60
        return original(self, *args, **kwargs)

    requests.Session.request = request


_timeout_requests()

from common import CSV_DIR, FRONTEND, JSON_DIR, RAW, WORK, ROSTER, norm_name, read_csv, read_json, split_list, write_csv, write_json

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"
CAND = RAW / "images" / "people"
CAND_CSV = CAND / "candidates.csv"
PROFILES = JSON_DIR / "profiles.json"  # public profile links: OpenReview, Google Scholar, homepages found there
IMAGES = CSV_DIR / "images.csv"
STATIC = FRONTEND / "static" / "img" / "people"
PORTRAIT = re.compile(r"profile|avatar|portrait|photo|headshot|\bme\.(jpe?g|png|webp)|bio|author|selfie|face", re.I)
NOT_PORTRAIT = re.compile(r"logo|icon|banner|favicon|sprite|badge|flag|arrow|button|cover|background|header|qr", re.I)


def get(url, binary=False):
    r = subprocess.run(["curl", "-sL", "--max-time", "40", "-A", UA, url], capture_output=True)
    return r.stdout if binary else r.stdout.decode("utf-8", "ignore")


def images_on(page_url, html):
    out = []
    for m in re.finditer(r'<meta[^>]+(?:property|name)=["\'](?:og:image|twitter:image)["\'][^>]*>', html, re.I):
        c = re.search(r'content=["\']([^"\']+)', m.group(0))
        if c:
            out.append((urllib.parse.urljoin(page_url, c.group(1)), "", "preview image"))
    for m in re.finditer(r"<img\b[^>]*>", html, re.I):
        tag = m.group(0)
        src = re.search(r'\s(?:data-src|src)=["\']([^"\']+)', tag)
        alt = re.search(r'\salt=["\']([^"\']*)', tag)
        if src and not src.group(1).startswith("data:"):
            out.append((urllib.parse.urljoin(page_url, src.group(1)), alt.group(1) if alt else "", "img"))
    return out


SCHOLAR_LINK = re.compile(r"scholar\.google\.[a-z.]+/citations\?[^\"'<> ]*user=([\w-]{12})")
OPENREVIEW_LINK = re.compile(r"openreview\.net/profile\?id=(~[\w.%-]+\d)")


def from_submissions(clients, p, papers, forums):
    """The profile id OpenReview records for this author on one of their own ICLR/NeurIPS/ICML submissions."""
    for paper in papers:
        slugs = [a["slug"] for a in paper["authors"]]
        forum = forums.get(paper["key"])
        if p["slug"] not in slugs or not forum:
            continue
        for c in clients:
            try:
                note = c.get_note(forum)
            except Exception:
                continue
            ids = note.content.get("authorids")
            ids = ids.get("value") if isinstance(ids, dict) else ids
            pos = slugs.index(p["slug"])
            if ids and len(ids) == len(slugs) and str(ids[pos]).startswith("~"):
                return ids[pos], f"author id on {paper['venue_name']} {paper['year']} submission {forum}"
            break
    return "", ""


def openreview_match(clients, p, papers, forums):
    """The person's OpenReview profile: the author id on one of their own submissions; otherwise a profile that links
    their dblp pid and lists one of their NNV papers (a dblp link alone is not enough: namesakes link the wrong page)."""
    client = clients[0]
    pid, why = from_submissions(clients, p, papers, forums)
    if pid:
        try:
            return client.get_profile(pid), why
        except Exception:
            pass
    titles = {norm_name(x["title"]) for x in papers if p["slug"] in [a["slug"] for a in x["authors"]]}
    try:
        profiles = client.search_profiles(fullname=p["name"]) or []
    except Exception as e:
        if "RateLimit" in str(e):
            time.sleep(30)
        return None, ""
    linked = [pr for pr in profiles if any(x and f"/pid/{x}" in (pr.content.get("dblp") or "") for x in p["pids"])]
    for pr in linked[:3]:
        try:
            notes = client.get_notes(content={"authorids": pr.id}, limit=1000)
        except Exception:
            continue
        for n in notes:
            t = n.content.get("title")
            if norm_name((t.get("value") if isinstance(t, dict) else t) or "") in titles:
                return pr, "dblp link on the profile and lists one of their NNV papers"
    return None, ""


def current(pr):
    """Institution and country of the latest position on an OpenReview profile."""
    hist = [h for h in pr.content.get("history") or [] if h.get("institution")]
    hist.sort(key=lambda h: (h.get("end") is None, h.get("end") or 0, h.get("start") or 0), reverse=True)
    if not hist:
        return {}
    inst = hist[0]["institution"]
    return {k: v for k, v in {"institution": inst.get("name", ""), "country": inst.get("country", ""),
                              "position": hist[0].get("position", "")}.items() if v}


def profile_links(people, papers):
    """profiles.json: each person's OpenReview profile and Google Scholar page, from OpenReview and their homepages."""
    import openreview

    known = read_json(PROFILES, {})
    todo = [p for p in people if p["slug"] not in known]
    if not todo:
        return known
    user, pw = os.environ.get("OPENREVIEW_USERNAME"), os.environ.get("OPENREVIEW_PASSWORD")
    clients = [retry(openreview.api.OpenReviewClient, baseurl="https://api2.openreview.net", username=user, password=pw)]
    try:
        clients.append(retry(openreview.Client, baseurl="https://api.openreview.net", username=user, password=pw))
    except Exception:
        pass
    forums = read_json(WORK / "openreview_forums.json", {})
    for p in todo:
        e = {"fetched": datetime.date.today().isoformat()}
        pr, why = openreview_match(clients, p, papers, forums)
        if pr:
            c = pr.content
            e.update(openreview=pr.id, openreview_match=why, homepage=c.get("homepage") or "", **current(pr))
            m = SCHOLAR_LINK.search(c.get("gscholar") or "")
            if m:
                e.update(scholar=m.group(1), scholar_from="OpenReview profile")
        for page in [p["homepage"], *p["dblp_homepages"], e.get("homepage", "")]:
            if not page or ("scholar" in e and "openreview" in e):
                continue
            html = get(page)
            m = SCHOLAR_LINK.search(html)
            if m and "scholar" not in e:
                e.update(scholar=m.group(1), scholar_from=page)
            m = OPENREVIEW_LINK.search(html)
            if m and "openreview" not in e:
                e.update(openreview=urllib.parse.unquote(m.group(1)), openreview_match=f"linked from {page}")
        known[p["slug"]] = {k: v for k, v in e.items() if v}
        write_json(PROFILES, dict(sorted(known.items())))
        print(f"  {p['slug']}: openreview {e.get('openreview', '-')}, scholar {e.get('scholar', '-')}", file=sys.stderr)
    return known


def retry(call, *args, **kwargs):
    for _ in range(8):
        try:
            return call(*args, **kwargs)
        except Exception as e:
            if "RateLimit" not in str(e):
                raise
            m = re.search(r"try again in (\d+) seconds", str(e))
            time.sleep(int(m.group(1)) + 2 if m else 30)
    return call(*args, **kwargs)


def scholar_photo(user):
    return f"https://scholar.googleusercontent.com/citations?view_op=view_photo&user={user}&citpid=2" if user else ""


def collect(people, only, profiles):
    CAND.mkdir(parents=True, exist_ok=True)
    rows = [r for r in read_csv(CAND_CSV)] if CAND_CSV.exists() else []
    done = {r["key"] for r in rows}
    for p in people:
        if p["slug"] in done and not only:
            continue
        rows = [r for r in rows if r["key"] != p["slug"]]
        prof = profiles.get(p["slug"], {})
        pages = list(dict.fromkeys(x for x in [p["homepage"], *p["dblp_homepages"], prof.get("homepage", "")]
                                   if x and not re.search(r"researchgate|openreview|linkedin|twitter|x\.com|github\.com/[^/]+/?$", x)))
        tokens = {t for t in norm_name(p["name"]).split() if len(t) > 2}
        found, seen = [], set()
        for page in pages:
            html = get(page)
            for url, alt, how in images_on(page, html):
                if url in seen or NOT_PORTRAIT.search(url + " " + alt):
                    continue
                low = norm_name(urllib.parse.unquote(url.rsplit("/", 1)[-1]) + " " + alt)
                named = any(t in low.split() or t in low.replace(" ", "") for t in tokens)
                if how == "preview image" or named or PORTRAIT.search(url + " " + alt):
                    seen.add(url)
                    found.append((url, page, f"{how}; alt: {alt[:60]}"))
        photo = scholar_photo(prof.get("scholar"))
        if photo:
            found.append((photo, f"https://scholar.google.com/citations?user={prof['scholar']}", "Google Scholar profile photo"))
        for url, page, note in found[:6]:
            data = get(url, binary=True)
            if len(data) < 1500 or data[:5] in (b"<!DOC", b"<html", b"<?xml") and not url.endswith(".svg"):
                continue
            name = f"{p['slug']}-{hashlib.md5(url.encode()).hexdigest()[:6]}"
            (CAND / name).write_bytes(data)
            rows.append({"key": p["slug"], "file": name, "image_url": url, "source_page": page, "note": note})
        print(f"  {p['slug']}: {sum(r['key'] == p['slug'] for r in rows)} candidates from {len(pages)} pages", file=sys.stderr)
        write_csv(CAND_CSV, ["key", "file", "image_url", "source_page", "note"], rows)
    return rows


def sheets(rows, per=48):
    """Contact sheets of all candidates (label: row number), to check them by eye."""
    out = CAND / "sheets"
    out.mkdir(exist_ok=True)
    for old in out.glob("*.png"):
        old.unlink()
    for s in range(0, len(rows), per):
        args = []
        for i, r in enumerate(rows[s:s + per], s):
            args += ["-label", f"{i} {r['key'][:18]}", f"{CAND / r['file']}[0]"]
        subprocess.run(["magick", "montage", *args, "-geometry", "150x150+4+4", "-tile", "8x", "-pointsize", "11",
                        str(out / f"sheet{s // per:02d}.png")], check=False, capture_output=True)
    print(f"{len(rows)} candidates -> {out}")


FLAGS = FRONTEND / "static" / "img" / "flags"
FLAG_SOURCE = "https://cdn.jsdelivr.net/gh/lipis/flag-icons@7.2.3/flags/4x3/{}.svg"  # flag-icons, MIT licence


def flags():
    """The flag of every country a researcher or group is shown with, as frontend/static/img/flags/<code>.svg."""
    FLAGS.mkdir(parents=True, exist_ok=True)
    codes = {r[k] for r in read_json(FRONTEND / "data" / "researchers.json", []) for k in ("country", "country_local")}
    codes |= {g["country"] for g in read_json(FRONTEND / "data" / "groups.json", [])}
    for cc in sorted(c for c in codes if c):
        dest = FLAGS / f"{cc.lower()}.svg"
        if not dest.exists():
            data = get(FLAG_SOURCE.format(cc.lower()), binary=True)
            if data.lstrip().startswith(b"<svg"):
                dest.write_bytes(data)
            else:
                print(f"  no flag for {cc}", file=sys.stderr)
    print(f"{len(list(FLAGS.glob('*.svg')))} flags -> {FLAGS}")


def apply():
    STATIC.mkdir(parents=True, exist_ok=True)
    cands = {(r["key"], r["image_url"]): r for r in read_csv(CAND_CSV)}
    done = 0
    for r in read_csv(IMAGES):
        if r["kind"] != "person":
            continue
        c = cands.get((r["key"], r["source"]))
        if not c:
            print(f"  not downloaded: {r['key']}", file=sys.stderr)
            continue
        dest = STATIC / f"{r['key']}.jpg"
        subprocess.run(["magick", f"{CAND / c['file']}[0]", "-auto-orient", "-resize", "400x400>", "-strip",
                        "-background", "white", "-flatten", str(dest)], check=True)
        done += 1
    print(f"{done} photos -> {STATIC}")


def main():
    ap = argparse.ArgumentParser(description="Researcher photos: collect candidates from personal pages, dblp and OpenReview homepages and Google Scholar (--collect), make contact sheets to check them (--sheets), copy the photos approved in images.csv into frontend/static/img/people (--apply).")
    ap.add_argument("--profiles", action="store_true", help="find OpenReview and Google Scholar profiles (profiles.json)")
    ap.add_argument("--collect", action="store_true")
    ap.add_argument("--sheets", action="store_true")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--flags", action="store_true", help="download the country flags the site shows")
    ap.add_argument("--only", nargs="*", help="researcher slugs")
    args = ap.parse_args()
    shown = {r["slug"] for r in read_json(FRONTEND / "data" / "researchers.json", [])}
    dblp = read_json(JSON_DIR / "people.json", {})
    people = []
    for r in read_csv(ROSTER):
        if r["approved"] != "yes" or r["slug"] not in shown or (args.only and r["slug"] not in args.only):
            continue
        pids = split_list(r["dblp_pids"])
        people.append({"slug": r["slug"], "name": r["name"], "pids": pids, "homepage": r["homepage"],
                       "dblp_homepages": [dblp[x]["homepage"] for x in pids if dblp.get(x, {}).get("homepage")]})
    papers = read_json(FRONTEND / "data" / "papers.json", [])
    profiles = read_json(PROFILES, {})
    if args.profiles:
        profiles = profile_links(people, papers)
    if args.collect:
        collect(people, args.only, profiles)
    if args.sheets:
        sheets(read_csv(CAND_CSV))
    if args.apply:
        apply()
    if args.flags:
        flags()


if __name__ == "__main__":
    main()
