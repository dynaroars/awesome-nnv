import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from common import BACKEND, JSON_DIR, FRONTEND, norm_title, read_json

PDF_DIR = BACKEND / "data" / "pdf"
WIKI = Path.home() / "Area" / "llmwiki" / "raw"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; awesome-nnv paper archive script)"}
HEAD = 4000  # characters of a wiki paper's extracted text searched for the title


def norm(text):
    return norm_title(unicodedata.normalize("NFKC", text))  # NFKC folds ligatures such as "ﬁ"


def is_pdf(data):
    return bool(data) and data[:5] == b"%PDF-"


def get(url, timeout=120):
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read()
    except (urllib.error.URLError, TimeoutError, ConnectionError, ValueError) as e:
        print(f"    {url}: {e}", file=sys.stderr)
        return None


def wiki_index():
    """Normalised opening text of every PDF in the wiki (its extracted .txt, else its first page)."""
    out = []
    for pdf in WIKI.rglob("*.pdf"):
        txt = pdf.with_suffix(".txt")
        if txt.exists():
            text = txt.read_text(errors="ignore")
        else:  # no extracted text next to it: read the first page
            run = subprocess.run(["pdftotext", "-l", "1", str(pdf), "-"], capture_output=True, timeout=60)
            text = run.stdout.decode("utf-8", "ignore")
        out.append((pdf, norm(text[:HEAD])))
    return out


def from_wiki(title, index):
    t = norm(title)
    if len(t) < 15:
        return None
    for pdf, head in index:
        if t in head:
            return pdf
    return None


def openalex_pdf_urls(ids, key):
    urls = []
    for w in ids:
        q = urllib.parse.urlencode({"select": "best_oa_location,locations", **({"api_key": key} if key else {})})
        data = get(f"https://api.openalex.org/works/{w}?{q}", timeout=60)
        if not data:
            continue
        work = json.loads(data)
        for loc in [work.get("best_oa_location") or {}, *(work.get("locations") or [])]:
            if loc and loc.get("pdf_url") and loc["pdf_url"] not in urls:
                urls.append(loc["pdf_url"])
    return urls


def landing_pdf_urls(url):
    """PDF links that follow from a proceedings landing page's address."""
    out = []
    m = re.match(r"https?://proceedings\.mlr\.press/(v\d+)/([\w-]+)\.html", url or "")
    if m:
        out.append(f"https://proceedings.mlr.press/{m[1]}/{m[2]}/{m[2]}.pdf")
    m = re.match(r"https?://(?:papers|proceedings)\.n(?:eur)?ips\.cc/paper(?:_files/paper)?/(\d{4})/hash/(\w+)-Abstract(-Conference)?\.html", url or "")
    if m:
        suffix = "-Paper-Conference.pdf" if m[3] else "-Paper.pdf"
        out.append(f"https://proceedings.neurips.cc/paper_files/paper/{m[1]}/file/{m[2]}{suffix}")
    if "openaccess.thecvf.com" in (url or "") and url.endswith(".html"):
        out.append(url.replace("/html/", "/papers/").replace(".html", ".pdf"))
    m = re.search(r"openreview\.net/(?:forum|pdf)\?id=([\w-]+)", url or "")
    if m:
        out.append(f"https://openreview.net/pdf?id={m[1]}")
    return out


def main():
    ap = argparse.ArgumentParser(description="Keep a PDF of every NNV paper in backend/data/pdf/<area>/<id>.pdf: copied from ~/Area/llmwiki when it has the paper, downloaded otherwise (arXiv, OpenReview, OpenAlex open-access links, proceedings pages).")
    ap.add_argument("--no-download", action="store_true", help="only copy from the wiki")
    ap.add_argument("--only", nargs="*", help="paper ids")
    args = ap.parse_args()
    papers = read_json(FRONTEND / "data" / "papers.json", [])
    cites = read_json(JSON_DIR / "citations.json", {})
    key = os.environ.get("OPENALEX_API_KEY", "")
    index = wiki_index()
    print(f"{len(index)} wiki PDFs with text, {len(papers)} NNV papers", file=sys.stderr)
    stats, missing = {"have": 0, "wiki": 0, "download": 0}, []
    for p in papers:
        if args.only and p["id"] not in args.only:
            continue
        dest = PDF_DIR / p["area"] / f"{p['id']}.pdf"
        others = [f for f in PDF_DIR.glob(f"*/{p['id']}.pdf") if f != dest]
        if dest.exists() and is_pdf(dest.read_bytes()[:5]):
            stats["have"] += 1
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        if others:  # the paper moved to another area
            shutil.move(others[0], dest)
            stats["have"] += 1
            continue
        src = from_wiki(p["title"], index)
        if src and is_pdf(src.read_bytes()[:5]):
            shutil.copyfile(src, dest)
            stats["wiki"] += 1
            continue
        if args.no_download:
            missing.append(p)
            continue
        info = cites.get(p["key"], {})
        urls = [f"https://arxiv.org/pdf/{p['arxiv']}"] if p.get("arxiv") else []
        urls += landing_pdf_urls(p.get("url", ""))
        if p["key"].startswith("openreview/"):
            urls.append(f"https://openreview.net/pdf?id={p['key'].split('/', 1)[1]}")
        tried = set()
        done = False
        for stage in (urls, None):
            for url in (stage if stage is not None else openalex_pdf_urls(info.get("openalex", []), key)):
                if url in tried:
                    continue
                tried.add(url)
                data = get(url)
                time.sleep(3 if "arxiv.org" in url else 1)
                if is_pdf(data):
                    dest.write_bytes(data)
                    stats["download"] += 1
                    print(f"  {p['id']}: {url}", file=sys.stderr)
                    done = True
                    break
            if done:
                break
        if not done:
            missing.append(p)
    print(f"{stats['have']} already there, {stats['wiki']} copied from the wiki, {stats['download']} downloaded, "
          f"{len(missing)} missing", file=sys.stderr)
    for p in missing:
        print(f"  missing: {p['id']} | {p['venue_name']} {p['year']} | {p['title'][:80]} | {p.get('url', '')}", file=sys.stderr)


if __name__ == "__main__":
    main()
