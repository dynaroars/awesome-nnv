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
    for p in todo:
        text, src = "", ""
        if p["key"].startswith("openreview/"):
            forum = p["key"].split("/", 1)[1]
            text, src = openreview(forum, args.refresh), f"https://openreview.net/forum?id={forum}"
        if not text and arx.get(p.get("arxiv", "")):
            text, src = arx[p["arxiv"]], f"https://arxiv.org/abs/{p['arxiv']}"
        if not text:
            for w in (cites.get(p["key"]) or {}).get("openalex", []):
                if len(oa.get(w, "")) > 200:
                    text, src = oa[w], f"https://openalex.org/{w}"
                    break
        out[p["key"]] = {"title": p["title"], "abstract": text, "source": src if text else ""}
    write_json(OUT, out)
    missing = [k for k, v in out.items() if not v["abstract"]]
    print(f"{len(out) - len(missing)}/{len(out)} with an abstract; missing: {len(missing)}", file=sys.stderr)


if __name__ == "__main__":
    main()
