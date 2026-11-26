import argparse
import datetime
import getpass
import json
import os
import re
import socket
import sys
import time

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

from common import FRONTEND, WORK, norm_title, read_json, write_json
from fetch_pdfs import PDF_DIR

FORUMS = WORK / "openreview_forums.json"
CONFERENCE = {"iclr": "ICLR.cc", "neurips": "NeurIPS.cc", "icml": "ICML.cc"}
KINDS = [("Decision", ("Decision", "Acceptance_Decision")), ("Meta-review", ("Meta_Review",)),
         ("Review", ("Official_Review",))]
SKIP_FIELDS = {"title", "authors", "authorids", "pdf"}


def login():
    """The maintainer's OpenReview account from OPENREVIEW_USERNAME / OPENREVIEW_PASSWORD, as vn-ai-ranking logs in."""
    import openreview

    user = os.environ.get("OPENREVIEW_USERNAME") or input("OpenReview username: ")
    pw = os.environ.get("OPENREVIEW_PASSWORD") or getpass.getpass("OpenReview password: ")
    v2 = retry(openreview.api.OpenReviewClient, baseurl="https://api2.openreview.net", username=user, password=pw)
    try:
        v1 = retry(openreview.Client, baseurl="https://api.openreview.net", username=user, password=pw)
    except Exception as e:
        print(f"warning: API v1 login failed ({e}); forums before 2024 will be missing", file=sys.stderr)
        v1 = None
    return v2, v1


def retry(call, *args, **kwargs):
    for _ in range(6):
        try:
            return call(*args, **kwargs)
        except Exception as e:
            if "RateLimit" not in str(e):
                raise
            m = re.search(r"try again in (\d+) seconds", str(e))
            time.sleep(int(m.group(1)) + 2 if m else 30)
    return call(*args, **kwargs)


def val(x):
    return x.get("value") if isinstance(x, dict) else x


def invitations(n):
    return getattr(n, "invitations", None) or [getattr(n, "invitation", "") or ""]


def find_forum(clients, p):
    """The conference's own submission forum with the paper's exact title (not a dblp or arXiv record)."""
    venue = f"{CONFERENCE[p['venue']]}/{p['year']}/Conference"
    for c in clients:
        try:
            notes = retry(c.search_notes, term=p["title"], content="title", group="all", source="forum", limit=10)
        except Exception as e:
            print(f"    search failed: {e}", file=sys.stderr)
            continue
        for n in notes:
            where = " ".join([str(val(n.content.get("venueid")) or ""), *invitations(n)])
            if venue in where and norm_title(val(n.content.get("title")) or "") == norm_title(p["title"]):
                return n.forum
    return ""


def site_forums():
    """(venue, year, title) -> OpenReview forum, from the conference sites' paper lists (cached; no search needed)."""
    import gzip

    from common import RAW

    out = {}
    for f in (RAW / "virtual").glob("*.json.gz"):
        venue, year = f.name.split(".")[0].split("-")
        try:
            rows = json.loads(gzip.decompress(f.read_bytes())).get("results", [])
        except ValueError:
            continue
        for r in rows:
            m = re.search(r"openreview\.net/(?:forum|pdf)\?id=([\w-]+)", json.dumps(r))
            if m:
                out[(venue, int(year), norm_title(r.get("name") or ""))] = m.group(1)
    return out


def needs_search(p):
    """Only ICLR before 2021 has public reviews that the conference site lists do not link; ICML before 2025 and
    NeurIPS 2020 have no public OpenReview reviews at all."""
    return p["venue"] == "iclr" and p["year"] <= 2020


def forum_notes(clients, forum):
    for c in clients:
        try:
            notes = retry(c.get_all_notes, forum=forum)
        except Exception:
            continue
        if notes:
            return notes
    return []


def text(v):
    v = val(v)
    if isinstance(v, list):
        return ", ".join(str(x) for x in v)
    return str(v).strip()


def markdown(p, forum, notes):
    sections = []
    for heading, suffixes in KINDS:
        picked = [n for n in notes if n.id != n.forum and any(i.endswith(s) for i in invitations(n) for s in suffixes)]
        picked.sort(key=lambda n: getattr(n, "cdate", 0) or getattr(n, "tcdate", 0) or 0)
        for k, n in enumerate(picked, 1):
            who = (n.signatures or [""])[0].split("/")[-1].replace("_", " ")
            title = heading if len(picked) == 1 else f"{heading} {k}"
            lines = [f"## {title}" + (f" ({who})" if heading == "Review" and who else "")]
            for field, value in n.content.items():
                body = text(value)
                if field in SKIP_FIELDS or not body:
                    continue
                name = field.replace("_", " ").capitalize()
                lines.append(f"**{name}:** {body}" if "\n" not in body and len(body) < 120 else f"**{name}:**\n\n{body}")
            sections.append("\n\n".join(lines))
    if not sections:
        return ""
    head = (f"# {p['title']}\n\n{p['venue_name']} {p['year']} · OpenReview: https://openreview.net/forum?id={forum}"
            f" · fetched {datetime.date.today().isoformat()}\n")
    return head + "\n" + "\n\n".join(sections) + "\n"


def main():
    ap = argparse.ArgumentParser(description="Save the OpenReview reviews, meta-review and decision of every ICLR, NeurIPS and ICML NNV paper that has them, as backend/data/pdf/<area>/<paper id>.md next to the PDF.")
    ap.add_argument("--refresh", action="store_true", help="look the forums up and download the reviews again")
    ap.add_argument("--only", nargs="*", help="paper ids")
    args = ap.parse_args()
    papers = [p for p in read_json(FRONTEND / "data" / "papers.json", []) if p["venue"] in CONFERENCE
              and (not args.only or p["id"] in args.only)]
    forums = {} if args.refresh else read_json(FORUMS, {})
    listed = site_forums()
    v2, v1 = login()
    clients = [c for c in (v2, v1) if c is not None]
    written = 0
    for i, p in enumerate(papers, 1):
        dest = PDF_DIR / p["area"] / f"{p['id']}.md"
        for old in PDF_DIR.glob(f"*/{p['id']}.md"):
            if old != dest:  # the paper moved to another area
                dest.parent.mkdir(parents=True, exist_ok=True)
                old.rename(dest)
        if dest.exists() and not args.refresh:
            written += 1
            continue
        if not forums.get(p["key"]):
            m = re.search(r"openreview\.net/forum\?id=([\w-]+)", p.get("url") or "")
            forum = m.group(1) if m else listed.get((p["venue"], p["year"], norm_title(p["title"])), "")
            if not forum and needs_search(p) and p["key"] not in forums:
                forum = find_forum(clients, p)
            forums[p["key"]] = forum
            write_json(FORUMS, forums)
        forum = forums[p["key"]]
        if not forum:
            continue
        md = markdown(p, forum, forum_notes(clients, forum))
        print(f"{i}/{len(papers)} {p['id']}: {forum} {'reviews' if md else 'no public reviews'}", file=sys.stderr)
        if md:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(md, encoding="utf-8")
            written += 1
    found = sum(1 for p in papers if forums.get(p["key"]))
    print(f"{found} of {len(papers)} ICLR/NeurIPS/ICML papers found on OpenReview; {written} have reviews saved",
          file=sys.stderr)


if __name__ == "__main__":
    main()
