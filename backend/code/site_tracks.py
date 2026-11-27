"""Main-track and other-track titles of AAAI and IJCAI, from the proceedings sites (ojs.aaai.org, ijcai.org).

dblp lists every AAAI and IJCAI track in one table of contents a year, so these section lists decide which dblp papers
are main-track papers. Adapted from vn-ai-ranking's fetch_accepted.py, with the 2017-2019 issues and sections added.
"""
import gzip
import html
import re
import sys
import unicodedata

from common import LAST_YEAR, RAW, norm_title
from fetch_dblp import fetch as fetch_raw

AAAI = "https://ojs.aaai.org/index.php/AAAI"
IJCAI = "https://www.ijcai.org/proceedings"
# The AAAI-17 and AAAI-18 issues carry ordinal titles ("Thirty-First AAAI Conference ...") instead of "AAAI-17".
AAAI_ISSUE_YEAR = {302: 2017, 301: 2018}
# AAAI-17 and AAAI-18 name their main-track sections by area, without "AAAI Technical Track".
AAAI_2017_MAIN = {"Machine Learning Methods", "Cognitive Modeling and Cognitive Systems", "Human-Aware Artificial Intelligence"}
# Special tracks run inside the technical-track issues; like vn-ai-ranking, they are not the main track.
AAAI_SPECIAL = re.compile(r"Safe, Robust and Responsible|AI for Social Impact|AI Alignment|Special", re.I)


# Text every real page of each kind carries; a bot-check or error page lacks it.
LOOKS_RIGHT = {"archive": b"issue/view/", "issue": b"obj_article_summary", "ijcai": b"paper_wrapper"}


def fetch(url, name, refresh=False):
    """fetch_dblp.fetch, but a refresh that fails or returns a page without the expected content (a bot check) keeps
    the cached copy instead of losing it."""
    path = RAW / (name + ".gz")
    old = path.read_bytes() if path.exists() else None
    kind = "ijcai" if name.startswith("ijcai/") else name.split("/")[1].split("-")[0]
    data = fetch_raw(url, name, refresh)
    if data is not None and LOOKS_RIGHT[kind] in data:
        return data
    if old is not None:
        path.write_bytes(old)
        if refresh:
            print(f"  warning: {url} did not give a proper page; keeping the cached copy", file=sys.stderr)
        return gzip.decompress(old)
    if data is not None:  # never cache a page without the expected content
        path.unlink(missing_ok=True)
    return None


def text_of(fragment):
    return unicodedata.normalize("NFC", re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", fragment)))).strip()


# IJCAI sections that are not the main track; any other heading right after "Main track" continues it ("Machine
# Learning S-Z" in 2017, "Machine Learning M-Z" in 2019, "Search" and "Uncertainty in AI" in 2026).
IJCAI_OTHER = re.compile(r"track|special|\bAI (?:for|and)\b|AI4|arts|human|sister|survey|journal|demo|doctoral|early|invited"
                         r"|late|autonomy|evolution|understanding|good", re.I)


def aaai_main(section):
    if AAAI_SPECIAL.search(section):
        return False
    # "Intelligent Robots (ROB)" (2024) sits among the technical tracks under its area code alone.
    return (bool(re.match(r"(?:AAAI Technical Track|Main Track)\b", section)) or section in AAAI_2017_MAIN
            or bool(re.fullmatch(r"[\w ,&-]+ \([A-Z]{2,4}\)", section)))


def main_flags(venue, rows):
    """For each (section, title) row, whether it is a main-track paper."""
    if venue == "aaai":
        return [aaai_main(s) for s, _ in rows]
    out, inside = [], False
    for section, _ in rows:
        if section.lower().startswith("main track"):
            inside = True
        elif IJCAI_OTHER.search(section):
            inside = False
        out.append(inside)
    return out


def aaai_issues(refresh=False):
    """year -> the ojs issue ids of that year's AAAI conference."""
    out, page = {}, 1
    while True:
        data = fetch(f"{AAAI}/issue/archive/{page}", f"aaai/archive-{page}.html", refresh)
        found = re.findall(r'<a class="title" href="[^"]*issue/view/(\d+)">(.*?)</a>', data.decode("utf-8", "replace"),
                           re.S) if data else []
        for issue, title in found:
            m = re.search(r"\bAAAI-(\d\d)\b", text_of(title))
            year = 2000 + int(m.group(1)) if m else AAAI_ISSUE_YEAR.get(int(issue))
            if year:
                out.setdefault(year, []).append(int(issue))
        if not found or any(int(i) in AAAI_ISSUE_YEAR and AAAI_ISSUE_YEAR[int(i)] == min(AAAI_ISSUE_YEAR.values())
                            for i, _ in found):
            return out
        page += 1


def parse_aaai(page):
    out = []
    for part in re.split(r'<div class="section">', page)[1:]:
        h = re.search(r"<h2[^>]*>(.*?)</h2>", part, re.S)
        section = text_of(h.group(1)) if h else ""
        for t in re.findall(r'<h3 class="title">\s*<a[^>]*>(.*?)</a>', part, re.S):
            out.append((section, text_of(t)))
    return out


def parse_ijcai(page):
    out = []
    for part in re.split(r'<div class="section_title">', page)[1:]:
        h = re.match(r"\s*<h3>(.*?)</h3>", part, re.S)
        section = text_of(h.group(1)) if h else ""
        for t in re.findall(r'<a class="title" href="[^"]*">(.*?)</a>|<div class="title">(.*?)</div>', part, re.S):
            out.append((section, text_of(t[0] or t[1])))
    return out


_ISSUES = {}


def sections(venue, year, refresh=False):
    """(section, title) of every paper the proceedings site lists for that year, or [] when it lists none yet."""
    recent = refresh and year >= LAST_YEAR - 1
    if venue == "aaai":
        if "aaai" not in _ISSUES:
            _ISSUES["aaai"] = aaai_issues(refresh)
        out = []
        for issue in _ISSUES["aaai"].get(year, []):
            page = fetch(f"{AAAI}/issue/view/{issue}", f"aaai/issue-{issue}.html", recent)
            if not page:
                print(f"  warning: AAAI {year} issue {issue} could not be read; its main-track papers are missing",
                      file=sys.stderr)
            out += parse_aaai(page.decode("utf-8", "replace")) if page else []
        return out
    if venue == "ijcai":
        page = fetch(f"{IJCAI}/{year}/", f"ijcai/{year}.html", recent)
        return parse_ijcai(page.decode("utf-8", "replace")) if page else []
    return []


def tracks(venue, year, refresh=False):
    """(main-track titles, other-track titles) as normalized titles; both empty when the site has no list."""
    rows = sections(venue, year, refresh)
    main, other = set(), set()
    for (section, title), is_main in zip(rows, main_flags(venue, rows)):
        (main if is_main else other).add(norm_title(title))
    return main, other - main


def main():
    import collections
    for venue in ("aaai", "ijcai"):
        for year in range(2017, LAST_YEAR + 2):
            rows = sections(venue, year)
            c = collections.Counter((m, s) for (s, _), m in zip(rows, main_flags(venue, rows)))
            print(venue, year, sum(n for (m, _), n in c.items() if m), "main;",
                  "; ".join(f"{s}={n}" for (m, s), n in sorted(c.items()) if not m), file=sys.stderr)


if __name__ == "__main__":
    main()
