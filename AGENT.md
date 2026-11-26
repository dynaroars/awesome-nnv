# AGENT.md: how to operate and maintain this site

You are maintaining a public, English-only Hugo site that counts **neural-network verification (NNV)** papers of the
field's leading researchers at sixteen top venues, grouped as CSRankings groups venues. The maintainer gives short
requests in plain words; this file tells you how to carry them out. Read it before changing anything. It is the only
instruction file: keep it up to date when the code or the rules change. The layout and workflow follow the sibling
project `../vn-ai-ranking` (same folder structure, same CSS and `site.js`).

## Layout

The top level holds only `backend/`, `frontend/`, `README.md`, `makefile`, `AGENT.md`, `LICENSE` and `.gitignore`.

- `backend/code/`: Python scripts (run them from `backend/code/`) and `backend/code/tests/`.
  - `fetch_dblp.py`: main-track papers of every venue from DBLP's SPARQL service (`sparql.dblp.org`), into
    `backend/work/papers.jsonl.gz` and `backend/work/coverage.json`. dblp.org itself answers scripts with a bot check:
    never get around it, use SPARQL.
  - `fetch_virtual.py`: for ICML, NeurIPS and ICLR years that dblp does not list yet, the accepted main-track papers
    from the conference site (`<site>/static/virtual/data/<venue>-<year>-orals-posters.json`, as vn-ai-ranking reads
    them; same track rule: no Datasets & Benchmarks, position, journal or blog entries) into
    `backend/work/virtual.jsonl.gz`, keyed `openreview/<forum id>`, linking the OpenReview forum. `all_papers()` in
    `common.py` drops a site's venue-year as soon as dblp lists it: then label the dblp rows again (the
    `openreview/...` rows of `topics.csv` become unused and the build warns about them; delete them).
  - `scan_topics.py`: a broad title prefilter; adds every hit to `topics.csv` with an empty `decision`.
  - `find_candidates.py`: ranks the authors of the `yes` papers who are not decided in `roster.csv` (`candidates.csv`).
  - `fetch_people.py`: DBLP person records (affiliation, homepage, ORCID) of roster and top candidates into
    `backend/data/json/people.json`.
  - `fetch_citations.py`: citation counts of the NNV papers from OpenAlex into `backend/data/json/citations.json`
    (only missing papers; `--refresh` reads all again). OpenAlex keeps a preprint and its published version as
    separate works, so a paper's count adds every work whose normalised title equals the paper's, published from
    two years before to one year after it, plus the work of its DOI. The key `OPENALEX_API_KEY` is set only in the
    maintainer's interactive shell: run it as `zsh -ic 'python3 fetch_citations.py'` (what `make citations` does).
    Never print, log or commit the key. Google Scholar answers scripts with a bot check: never scrape it.
  - `build_site_data.py`: writes `frontend/data/*.json` and the page stubs; `graph.py` lays out the collaboration
    graph; `charts.py` draws the SVG charts.
- `backend/data/csv/`: hand-kept tables (below). `backend/data/json/`: snapshots kept in the repository.
- `backend/data/raw/` (downloads, gzip cache of every SPARQL answer) and `backend/work/` are git-ignored.
- `frontend/`: Hugo site, own layouts (no theme), data in `frontend/data/*.json`, one `static/site.js` (sorting, cups,
  pinned columns, pagination, graph hover, theme) and `static/style.css`.
- Page stubs in `frontend/content/{researchers,groups,areas,conferences}/` are rewritten on every build: never edit
  them by hand. The section `_index.md` files and the other pages in `content/` are hand-written.

**No comments in the code** (as in vn): no comments or docstrings in Python, the makefile, templates, JavaScript, CSS,
TOML or `.gitignore`. Explanations belong in this file. Command-line help texts are strings and stay. Keep only code
the site uses.

## The usual cycle

1. `make fetch` (or `make refresh` to download every table of contents again and rescan).
2. `make topics`, then label the new rows of `topics.csv` (below).
3. `make candidates`, then decide people with the maintainer (below).
4. `make data`: rebuilds `frontend/data/` and the stubs (a few seconds). Read `backend/work/build_report.txt`.
5. `make build` (no warnings) and `make test` (must pass).
6. Look at what changed: diff the numbers you expected to move and take headless screenshots
   (`chromium --headless --screenshot`, served with `python3 -m http.server` from `frontend/public`), light and dark
   (`--blink-settings=preferredColorScheme=0`).
7. Commit, push and publish only when the maintainer asks (see Git and publishing).

## Hand-kept files

| file | what it holds |
|---|---|
| `backend/data/csv/topics.csv` | one row per prefilter hit: `key` (DBLP record), `venue`, `year`, `title`, `decision` (`yes`/`no`, empty = undecided), `area` (primary area key), `tags` (secondary area keys, `;`-separated), `note` (who labelled it and how, dated). Only `yes` rows count. |
| `backend/data/csv/roster.csv` | everyone decided: `approved` (`yes` on the site, `no` with the reason in `notes`, empty = waiting), `slug`, `name`, `dblp_pids` (`;`-separated, first is primary), `aliases` (name forms for sources without DBLP pids), `group` (a `groups.csv` slug), `role` (`faculty`, `industry`, `researcher` or `student`), `institution`, `institution_short`, `homepage`, `to_confirm`, `notes`. |
| `backend/data/csv/groups.csv` | research groups: `slug`, `name` (the signature tool or line of work, as at VNN-COMP), `tools`, `url`, `description`, `legend` (`yes` gives the group its own colour on the Collaboration graph whatever its size; nnenum, CORA and Venus since 2026-11-26), `notes`. Every group with 4 or more shown researchers (`LABEL_MIN_MEMBERS`) also gets its own colour; colours come from `palette` in `build_site_data.py` (golden-angle hues), smaller groups are grey. |
| `backend/data/csv/candidates.csv` | generated by `find_candidates.py`; read by the local Candidates page. |
| `backend/data/csv/images.csv` | group logos: `kind`, `key` (group slug), `source`, `note`, `fetched`. Only a group's own mark (tool or lab logo from its repository, site or organisation avatar), never a university crest, a portrait or a generated identicon. Raw downloads in `backend/data/raw/images/`, a copy of at most 320 px in `frontend/static/img/groups/<slug>.png|jpg|svg`; the build shows any file found there. |
| `backend/data/json/people.json` | DBLP person snapshots (`fetch_people.py`), CC0. |
| `backend/data/json/citations.json` | OpenAlex citation counts per DBLP key, with the OpenAlex work ids added up, `matched` (`title` or `doi+title`) and `fetched` date (`fetch_citations.py`). |

## Counting rules (the About page states them; keep both in sync)

- **Venues**, grouped as CSRankings does (`FIELDS` in `common.py`): ML (ICML, ICLR, NeurIPS), CV (CVPR, ICCV in
  odd years, ECCV in even years; added at the maintainer's request on 2026-11-26), PL (PLDI, POPL, ICFP,
  OOPSLA), SE (FSE, ICSE, ASE, ISSTA), LV, logic and verification (CAV, LICS). NFM is not tracked at all (the maintainer's
  choice, 2026-11-26; it was an unscored "Other FM" field before).
- **Years** 2017 on (Reluplex, CAV 2017). Conference years: the year in the DBLP table of contents, or the PACMPL /
  PACMSE issue year.
- **Main track only.** Each venue is a DBLP stream plus a whitelist of table-of-contents pages (`tocs` in `VENUES`):
  POPL, OOPSLA, ICFP and PLDI (2023 on) are PACMPL issues, FSE (2024 on) and ISSTA (2025 on) PACMSE issues.
  CVPR and ICCV workshop volumes (`cvprw`, `iccvw`, `iccv2025w`), ECCV workshop volumes (`-w`), companion, workshop, NIER, SEIS, demo, Tiny Papers, position-paper and Datasets & Benchmarks volumes are left out,
  as are papers with a known page count under `MIN_PAGES` (6), as CSRankings does.
- **Only NNV papers count** (the maintainer's choice): a paper whose main contribution is to verify, certify or give
  formal guarantees about the behaviour of a neural network or another learned model. In scope: complete and
  incomplete verifiers, bound propagation and abstract interpretation, certified training, randomized smoothing and
  other probabilistic certification, Lipschitz certification, verification of NN controllers and closed-loop
  systems, neural certificates (barrier, Lyapunov) that are formally checked, repair with guarantees, formal
  explanations, global and relational properties, verification of transformers, RNNs, GNNs, tree ensembles,
  language and vision-language models, quantized and binarized networks, soundness of verifiers, benchmarks, tools
  and surveys of NNV. Out: DNN testing and fuzzing (coverage criteria, mutation testing), empirical attacks and
  defences without a certificate, using neural networks or LLMs to verify ordinary programs, checking code that an
  LLM wrote, generalization bounds, safe RL without formal verification of the network.
- **Areas** (the maintainer approved these on 2026-11-26; `AREAS` in `common.py`): `complete`, `bounds`,
  `probabilistic`, `training`, `repair`, `explanations`, `control`, `relational`, `architectures`, `quantized`,
  `other` (Lipschitz certification, soundness, proofs, tools, benchmarks, surveys). One primary area per paper,
  used for every count, so area totals add up; secondary tags are shown and counted separately ("Also tagged").
  Choose the primary area by the paper's main contribution: a verifier for transformers is `architectures`, a
  certified-training method for controllers is `training` with the tag `control`.
- **Name matches** (conference-site papers have no dblp pid): an author counts for a listed researcher when the
  printed name equals the roster `name`, an `aliases` entry or the dblp name of one of their pids. Every such match is
  listed in `build_report.txt` ("name match to check"): check the co-authors and institution, and add a namesake's
  printed form nowhere (a wrong match is removed by renaming in `aliases`, never by editing the data). Example: two
  different Thanh Le are on the NeurIPS 2026 list; only "Verifying Neural Networks with Reinforcement Learning" is
  the maintainer's.
- **arXiv links:** `fetch_citations.py` keeps the arXiv id of the OpenAlex preprint it adds up (`arxiv` in
  `citations.json`), shown as an "arXiv" link next to the title.
- **People:** every author with `TRACK_MIN` (2) or more NNV papers is listed (the maintainer's rule,
  2026-11-26), students and industry researchers included. Roster rows below the threshold are kept (with their
  group) but shown only on the local Candidates page; they reappear on the site once they reach 2. Identity is the
  DBLP pid (`dblp_pids`), never a name match, for DBLP papers; conference-site papers are matched by name (below).
  The maintainer also names people to track by hand ("Track X"): add them with `approved` = `yes` and a group.
- **Areas line chart** (`multi_lines` in `charts.py`, Areas page): one line per area. Only blue, orange and aqua
  pass the palette validator all-pairs in both themes, so colour and line style combine: `line` in `AREAS`
  (`common.py`) fixes each area's (hue, style), styles solid, dashed, dotted and dash-dot by size tier (chosen
  2026-11-26 from that day's order; keep them fixed so areas are never repainted). Keys are line samples; points
  show only on the highlighted line; hovering a line, its label or an Areas table row highlights it.
- **Collaboration graph marks:** every group with `LABEL_MIN` (4, `common.py`) or more shown researchers, and every
  group with `legend` = `yes`, gets a mark: one of the 8 validated categorical hues (`.hue1`-`.hue8` in
  `style.css`, light and dark steps from the dataviz palette) times 4 shapes (circle, square, diamond, triangle,
  equal area). `assign_marks` in `build_site_data.py` gives the largest groups circles first and picks, within a
  shape, the free hue that shares the fewest papers with groups already on it. Groups of `LABEL_MIN` or more are
  filled, smaller ones hollow; unlabelled groups are hollow grey circles. Same-group links are drawn shorter
  (`component_layout` in `graph.py`) so groups form clusters. Hovering a node or a legend entry shows a card next
  to the mouse with the researcher, then the group's description, tools and counts (`group-info` JSON in the page).
- **Leading researchers and groups** (area and conference pages, Areas list): at least 2 papers there
  (`LEADING_MIN`), top 10 plus anyone tied with the tenth when the tenth has more than 2; ties broken by score.
- **Collaboration zoom** (`site.js`, last block): the SVG `viewBox` is rewritten, never the data; Ctrl/⌘ + wheel
  (and trackpad pinch) zooms about the pointer, plain wheel scrolls the page, +/−/Reset buttons appear only with
  JavaScript, zoom 1–6×, pan clamped to the drawing; a drag pans only after 4 px and only when zoomed, so clicks
  on nodes still open the researcher's page.
- **Groups, not institutions** (the maintainer's choice): each person belongs to one research group named by its
  signature tool or line of work; the institution is shown only as information. A person's papers all count for
  their current group.
- **Citations** (the maintainer's request, 2026-11-26): per paper from OpenAlex; a researcher's total adds
  their NNV papers, a group's total counts each paper once. Citations are shown, never part of the score. A paper
  without a match shows a dash and adds nothing. Refresh them with `make citations` (add `--refresh` in the script
  call to re-read every paper) before a publish when they are more than a month old.
- **Score:** a researcher's score is the CSRankings adjusted count over all fields: each NNV paper is worth
  1 / (number of authors). A group's score is the geometric mean over ML, CV, PL, SE and LV of (sum of its members'
  adjusted counts + 1), as CSRankings ranks institutions. Group paper counts count a shared paper once.

## Paper dates

Papers are ordered newest first by the month of their conference (`conference_month` in `common.py`:
`VENUE_MONTH`, the venue's usual month, and `MONTH_EXCEPTIONS` for years that differ). dblp and the conference
lists give no dates; the months were written from memory on 2026-11-26 and may be off by a month for some years, so
correct them from the conference sites when a paper's order looks wrong, and add each new venue-year's month when it
is not the usual one. The Papers page shows the month in its Date column.

## Paper ids

Every counted paper has a Google Scholar-style id (the maintainer's request, 2026-11-26): the first author's family
name, the year and the first title word that is not a stop word (`TITLE_STOPWORDS`), all lower case ASCII, e.g.
`katz2017reluplex`, `singh2019abstract`. Ids are assigned among the counted papers in order of year and DBLP key;
a clash takes `b`, `c`, ... (`assign_ids` in `common.py`). The maintainer refers to papers by these ids: find the
DBLP `key` in `frontend/data/papers.json`, then edit that row of `topics.csv`. Pages link to a paper as `#<id>`.

## Labelling topics

`scan_topics.py` is deliberately broad (`MODEL` and `CHECK` patterns both in the title, or a `STRONG` pattern). Read
each undecided row and fill `decision`, `area`, `tags` and a dated `note`
(e.g. `title, Claude 2026-11-26`). When the title is not enough, read the abstract (DOI page, arXiv, OpenReview)
and say so in the note. Prefilter recall was checked against the maintainer's own NNV reading list (kept outside this
repository; never commit it): look at any paper it misses and widen the patterns rather than adding rows by hand.
A row added by hand needs `prefilter manual` in its note.

## Deciding people

`find_candidates.py --promote` adds every undecided author with `TRACK_MIN`+ NNV papers to `roster.csv`, in the
group of the listed researcher they share the most NNV papers with, or in a new group of their own when they share
none; every promoted row says so in `to_confirm`. Run it after each topic labelling. The local Candidates page lists
the roster people below the threshold and any undecided author with 2+ papers. Check promoted rows with the
maintainer: their group, their post (`institution`, `institution_short`) and their role; a person who should not be
listed gets `approved` = `no` with the reason. Mark anything unconfirmed in `to_confirm` (shown only locally).

## Public and local values

- `to_confirm` is shown only in the local build. When it contains `current post`, or `institution` is empty, the
  public site shows DBLP's primary affiliation instead of the roster's `institution` (`institution()` in
  `build_site_data.py`); the local build shows the roster's value. Clear `current post` once the post is checked.
- `role` is shown only in the local build. Group names and descriptions are public: state no unchecked post or claim
  in them.

## Coverage

`fetch_dblp.py` reuses the cache in `backend/data/raw/dblp/`; the current and previous year are downloaded again
when their cache is more than 7 days old (`stale`), every year with `--refresh`. A table of contents whose parsed
papers fall under 80% of the count DBLP lists is downloaded again, then reported as a warning (a table of contents once came
back empty). DBLP adds proceedings some weeks after a conference. The front page and Conferences page list the venue-years not
yet in DBLP (`gaps` in `meta.json`); run `make refresh` after a conference's proceedings appear.

## Git and publishing

- Commit only when the maintainer asks ("ship" means commit, push and publish). Commit with the repository's own
  identity, `thanhlexyz <thanhlexyz@users.noreply.github.com>` (repo-local config), and a UTC date
  (`TZ=UTC git commit ...`). End the message with the attribution trailer your harness gives.
- `make publish` builds with `frontend/publish.toml` and force-pushes the built site to the `gh-pages` branch
  (GitHub Pages, "Deploy from a branch"). Publish only when the maintainer says so in the current request.
- The repository is public: no private files, local paths, e-mails or credentials in commits.
