"""Abstracts of the NNV papers the monthly digest covers, for writing their one-line summaries: the OpenReview
submission (ICLR/NeurIPS/ICML), arXiv, or OpenAlex (its inverted index), first found wins. Written to
backend/work/abstracts.json (not committed); digest.csv records which source each summary was written from."""
import argparse
import html
import json
import re
import sys
import urllib.parse

from common import JSON_DIR, RAW, WORK, read_json, write_json
from fetch_dblp import fetch

OUT = WORK / "abstracts.json"
ARX = JSON_DIR / "arxiv_titles.json"


def clean(text):
    return re.sub(r"\s+", " ", html.unescape(text or "")).strip()


def openreview(forum, refresh=False):
    data = fetch(f"https://api2.openreview.net/notes?id={forum}", f"abstracts/openreview-{forum}.json", refresh)
    try:
        note = json.loads(data)["notes"][0]["content"]
        return clean(note.get("abstract", {}).get("value", ""))
    except (TypeError, ValueError, KeyError, IndexError):
        return ""


def arxiv(aid, refresh=False):
    data = fetch(f"https://export.arxiv.org/api/query?id_list={aid}", f"abstracts/arxiv-{aid.replace('/', '_')}.xml", refresh)
    m = re.search(r"<entry>.*?<summary>(.*?)</summary>", (data or b"").decode("utf-8", "replace"), re.S)
    return clean(m.group(1)) if m else ""


def openalex(work, refresh=False):
    data = fetch(f"https://api.openalex.org/works/{work}?select=abstract_inverted_index", f"abstracts/openalex-{work}.json",
                 refresh)
    try:
        inv = json.loads(data).get("abstract_inverted_index") or {}
    except (TypeError, ValueError):
        return ""
    return clean(" ".join(w for _, w in sorted((p, w) for w, ps in inv.items() for p in ps)))


def openalex_search(title, refresh=False):
    q = urllib.parse.urlencode({"search": title, "per-page": 1, "select": "id,title"})
    data = fetch(f"https://api.openalex.org/works?{q}", f"abstracts/openalex-search-{re.sub(r'[^a-z0-9]+', '', title.lower())[:60]}.json", refresh)
    try:
        hit = json.loads(data)["results"][0]
    except (TypeError, ValueError, KeyError, IndexError):
        return ""
    same = re.sub(r"[^a-z0-9]", "", hit["title"].lower()) == re.sub(r"[^a-z0-9]", "", title.lower())
    return hit["id"].rsplit("/", 1)[-1] if same else ""


def abstract(p, cites, refresh=False):
    """(abstract, source URL) of one paper of papers.json."""
    if p["key"].startswith("openreview/"):
        forum = p["key"].split("/", 1)[1]
        text = openreview(forum, refresh)
        if text:
            return text, f"https://openreview.net/forum?id={forum}"
    if p.get("arxiv"):
        text = arxiv(p["arxiv"], refresh)
        if text:
            return text, f"https://arxiv.org/abs/{p['arxiv']}"
    works = (cites.get(p["key"]) or {}).get("openalex") or []
    if not works:
        found = openalex_search(p["title"], refresh)
        works = [found] if found else []
    for w in works:
        text = openalex(w, refresh)
        if len(text) > 200:
            return text, f"https://openalex.org/{w}"
    return "", ""


def openalex_batch(works, refresh=False):
    """work id -> abstract, 50 works a request (OpenAlex shares a small daily budget between anonymous clients)."""
    out = {}
    for k in range(0, len(works), 50):
        chunk = works[k:k + 50]
        q = urllib.parse.urlencode({"filter": "openalex:" + "|".join(chunk), "per-page": 50,
                                    "select": "id,abstract_inverted_index"})
        data = fetch(f"https://api.openalex.org/works?{q}", f"abstracts/openalex-batch-{chunk[0]}-{len(chunk)}.json", refresh)
        try:
            results = json.loads(data)["results"]
        except (TypeError, ValueError, KeyError):
            continue
        for r in results:
            inv = r.get("abstract_inverted_index") or {}
            out[r["id"].rsplit("/", 1)[-1]] = clean(" ".join(w for _, w in sorted((q, w) for w, ps in inv.items() for q in ps)))
    return out


def arxiv_batch(ids, refresh=False):
    """arXiv id -> abstract, 40 ids a request, with a pause between requests (arXiv's API etiquette)."""
    import time
    out = {}
    for k in range(0, len(ids), 40):
        chunk = ids[k:k + 40]
        name = f"abstracts/arxiv-batch-{chunk[0].replace('/', '_')}-{len(chunk)}.xml"
        cached = (RAW / (name + ".gz")).exists()
        data = fetch(f"https://export.arxiv.org/api/query?id_list={','.join(chunk)}&max_results={len(chunk)}", name, refresh)
        for entry in re.findall(r"<entry>(.*?)</entry>", (data or b"").decode("utf-8", "replace"), re.S):
            aid = re.search(r"<id>https?://arxiv.org/abs/([^<]+?)(v\d+)?</id>", entry)
            summ = re.search(r"<summary>(.*?)</summary>", entry, re.S)
            if aid and summ:
                out[aid.group(1)] = clean(summ.group(1))
        if not cached:
            time.sleep(3)
    return out


def nt(s):
    return re.sub(r"[^a-z0-9]", "", s.lower())


def sur(n):
    return nt(re.sub(r"\s+\d{4}$", "", n).split()[-1]) if n.strip() else ""


def arxiv_title(p, refresh=False):
    import time
    q = re.sub(r"[^A-Za-z0-9]+", " ", p["title"]).strip()
    name = f"abstracts/arxiv-title-{nt(p['title'])[:60]}.xml"
    cached = (RAW / (name + ".gz")).exists()
    data = fetch("https://export.arxiv.org/api/query?" + urllib.parse.urlencode({"search_query": f'ti:"{q}"', "max_results": 5}), name, refresh)
    if not cached:
        time.sleep(3)
    au = {sur(a["name"]) for a in p["authors"]}
    for e in re.findall(r"<entry>(.*?)</entry>", (data or b"").decode("utf-8", "replace"), re.S):
        t = re.search(r"<title>(.*?)</title>", e, re.S)
        i = re.search(r"<id>https?://arxiv.org/abs/([^<]+?)(v\d+)?</id>", e)
        s = re.search(r"<summary>(.*?)</summary>", e, re.S)
        na = {sur(clean(n)) for n in re.findall(r"<name>(.*?)</name>", e, re.S)}
        if t and i and s and nt(clean(t.group(1))) == nt(p["title"]) and au & na:
            return i.group(1), clean(s.group(1))
    return "", ""


def pdf(p):
    import subprocess
    f = next(iter(sorted((JSON_DIR.parent / "pdf").glob(f"*/{p['id']}.pdf"))), None)
    if not f:
        return ""
    t = subprocess.run(["pdftotext", "-l", "2", str(f), "-"], capture_output=True, text=True).stdout
    m = re.search(r"\bA\s?BSTRACT\b|\bAbstract\b", t)
    if not m:
        return ""
    t = t[m.end():]
    e = re.search(r"\n\s*(1\.?\s+I\s?NTRODUCTION|1\.?\s+Introduction|I\.\s+I\s?NTRODUCTION|Introduction\n|Keywords|CCS Concepts|Index Terms)", t)
    t = clean(re.sub(r"-\n(?=[a-z])", "", t[:e.start()] if e else t[:2500])).lstrip(".:—- ")
    return t if 300 < len(t) < 4000 else ""


def main():
    from digest import in_scope
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--refresh", action="store_true")
    args = ap.parse_args()
    cites = read_json(JSON_DIR / "citations.json", {})
    out = read_json(OUT, {})
    todo = [p for p in in_scope() if args.refresh or not (out.get(p["key"]) or {}).get("abstract")]
    arx = arxiv_batch(sorted({p["arxiv"] for p in todo if p.get("arxiv")}), args.refresh)
    works = sorted({w for p in todo for w in (cites.get(p["key"]) or {}).get("openalex", [])})
    oa = openalex_batch(works, args.refresh)
    ax = read_json(ARX, {})
    for p in todo:
        text, src = "", ""
        if p["key"].startswith("openreview/"):
            forum = p["key"].split("/", 1)[1]
            text, src = openreview(forum, args.refresh), f"https://openreview.net/forum?id={forum}"
        if not text and arx.get(p.get("arxiv", "")):
            text, src = arx[p["arxiv"]], f"https://arxiv.org/abs/{p['arxiv']}"
        if not text and not p.get("arxiv"):
            i, t = arxiv_title(p, args.refresh)
            if i:
                ax[p["key"]] = i
                text, src = t, f"https://arxiv.org/abs/{i}"
        if not text:
            for w in (cites.get(p["key"]) or {}).get("openalex", []):
                if len(oa.get(w, "")) > 200:
                    text, src = oa[w], f"https://openalex.org/{w}"
                    break
        if not text:
            text, src = pdf(p), p.get("url", "")
        out[p["key"]] = {"title": p["title"], "abstract": text, "source": src if text else ""}
    write_json(OUT, out)
    write_json(ARX, dict(sorted(ax.items())))
    missing = [k for k, v in out.items() if not v["abstract"]]
    print(f"{len(out) - len(missing)}/{len(out)} with an abstract; missing: {len(missing)}", file=sys.stderr)


if __name__ == "__main__":
    main()
