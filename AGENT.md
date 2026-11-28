# AGENT.md: how to operate and maintain this site

You are maintaining a public, English-only Hugo site that counts **neural-network verification (NNV)** papers of the
field's leading researchers at thirty-two top venues, grouped as CSRankings groups venues. The maintainer gives short
requests in plain words; this file tells you how to carry them out. Read it before changing anything. It is the only
instruction file: keep it up to date when the code or the rules change. The layout and workflow follow the sibling
project `../vn-ai-ranking` (same folder structure, same CSS and `site.js`).

## Code style (the maintainer's rules, 2026-11-27)

- Write no comments in any code: Python, JavaScript, CSS, Hugo templates and shell (no `#`, `//`, `/* */`,
  `{{/* */}}` or explanatory docstrings). Explanations belong in this file, the README or the commit message.
- Keep variable names as short as possible, to keep the code compact.

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
    `common.py` drops a site's venue-year as soon as dblp lists it; `scan_topics.py` carries each label over to the
    dblp row with the same venue and title (the old row stays, unused).
  - `fetch_researchr.py`: for ICSE, FSE, ASE, ISSTA, POPL, PLDI and OOPSLA, this year's and next year's accepted
    main-track papers from the conference's own pages on conf.researchr.org (`RESEARCHR_TRACKS` in `common.py`: track
    page and the label of the main research track on it; journal-first, earlier-venue, keynote and other talks are
    left out), into `backend/work/researchr.jsonl.gz`, keyed `researchr/<venue><year>/<event id>`. Used only for a
    venue-year dblp lists under 80% of (`COMPLETE`), and only for papers whose title dblp does not have; refreshed
    weekly. Authors are matched by name, as for the ICML/NeurIPS/ICLR sites.
  - `fetch_robotics.py`: RSS (`roboticsproceedings.org`) and IROS (OpenAlex) papers of the venue-years dblp lists
    fewer than 20 papers of, into `backend/work/robotics.jsonl.gz` (keys `rss<year>/pNNN`, `openalex/<work id>`),
    merged like the researchr lists; IROS papers under six pages are left out. Authors are matched by name.
  - `backend/data/csv/accepted.csv`: accepted papers known only from an author's page or announcement (venue, year,
    title, all authors in order, track, source_url, fetched, note), keyed `accepted/<venue><year>/<title>`. They count
    like any paper and show an "unofficial" tag (the maintainer's rule, 2026-11-26); a conference list or dblp listing
    the same title replaces the row. Record the full author list (credit is 1/N) and the exact source.
  - `fetch_pdfs.py` (`make pdfs`): a PDF of every NNV paper in `backend/data/pdf/<area>/<paper id>.pdf` (git-ignored;
    the area is the primary area, the id the Scholar-style id). Copied from the maintainer's `~/Area/llmwiki/raw` when
    a PDF there has the paper's title on its first page (matched by title, never by file name: ids clash), downloaded
    otherwise from arXiv, OpenReview, proceedings pages (PMLR, NeurIPS, CVF) or OpenAlex open-access links. Rerun after
    relabelling: a PDF moves with its paper's area.
  - `fetch_reviews.py` (`make reviews`): for ICLR, NeurIPS and ICML papers, the OpenReview decision, meta-review and
    official reviews as `backend/data/pdf/<area>/<paper id>.md` next to the PDF, only when the forum has them. Logs in
    with `OPENREVIEW_USERNAME` / `OPENREVIEW_PASSWORD` (run under `zsh -ic`, as in vn-ai-ranking); the forum is the
    conference's own submission with the exact title (`ICLR.cc/<year>/Conference` etc., never a dblp or arXiv record),
    cached in `backend/work/openreview_forums.json`. The PDFs and reviews stay local (git-ignored, the maintainer's
    rule): never commit or publish them.
  - `site_affiliations.py` (part of `make data`): each listed researcher's institution as printed on their latest
    ICML/NeurIPS/ICLR paper's conference page (cached site lists, 2020 on; a department with no university named is
    skipped), into `backend/data/json/site_affiliations.json`.
  - `fetch_photos.py`: `--profiles` finds each researcher's OpenReview profile (the author id OpenReview records on one
    of their own submissions; failing that, a profile that links their dblp pid *and* lists one of their NNV papers:
    namesakes link the wrong dblp page) and Google Scholar page (from that profile or their homepage) into
    `backend/data/json/profiles.json`, with the profile's current institution and country; `--collect` gathers photo
    candidates from their pages and Scholar into `backend/data/raw/images/people/`, `--sheets` makes contact sheets to
    check them by eye, `--apply` copies the photos recorded in `images.csv` (kind `person`) to
    `frontend/static/img/people/<slug>.jpg`; `--flags` downloads the flags shown (flag-icons, MIT) to
    `frontend/static/img/flags/`.
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
| `backend/data/csv/groups.csv` | research groups: `slug`, `name` (the signature tool or line of work, as at VNN-COMP), `tools`, `url`, `description`, `topic` (one line on what the group works on, condensed from the summary statement at the top of its lab page or its leader's homepage; shown when hovering the group name in the Groups table and on the group page; 2026-11-27), `topic_source` (that page), `legend` (`yes` gives the group its own colour on the Collaboration graph whatever its size; nnenum, CORA and Venus since 2026-11-26), `notes`. Every group with 4 or more shown researchers (`LABEL_MIN_MEMBERS`) also gets its own colour; colours come from `palette` in `build_site_data.py` (golden-angle hues), smaller groups are grey. |
| `backend/data/csv/candidates.csv` | generated by `find_candidates.py`; read by the local Candidates page. |
| `backend/data/csv/images.csv` | group logos: `kind`, `key` (group slug), `source`, `note`, `fetched`. Only a group's own mark (tool or lab logo from its repository, site or organisation avatar), never a university crest, a portrait or a generated identicon. Raw downloads in `backend/data/raw/images/`, a copy of at most 320 px in `frontend/static/img/groups/<slug>.png|jpg|svg`; the build shows any file found there. |
| `backend/data/json/people.json` | DBLP person snapshots (`fetch_people.py`), CC0. |
| `backend/data/json/citations.json` | OpenAlex citation counts per DBLP key, with the OpenAlex work ids added up, `matched` (`title` or `doi+title`) and `fetched` date (`fetch_citations.py`). |

## Counting rules (the About page states them; keep both in sync)

- **Venues**, grouped as CSRankings does (`FIELDS` in `common.py`): ML (ICML, ICLR, NeurIPS), CV (CVPR, ICCV in
  odd years, ECCV in even years; added at the maintainer's request on 2026-11-26), PL (PLDI, POPL, ICFP,
  OOPSLA), SE (FSE, ICSE, ASE, ISSTA), LV, logic and verification (CAV, LICS), AI (AAAI, IJCAI; added at the
  maintainer's request on 2026-11-27, last in the field order so the other fields keep their chart colours), Sec, computer
  security (CCS, S&P, USENIX Security, NDSS) and Rob, robotics (ICRA, IROS, RSS), both added at the maintainer's
  request on 2026-11-27 after AI, in that order (chart colours `#e07a12` and `#5a4fcf`, checked with the palette
  validator: adjacent pairs pass in both themes; `#5a4fcf` is just under 3:1 on the dark surface, as violet is,
  which the tables relieve). Security and robotics papers come from dblp (`conf/ccs/ccsYYYY`, `conf/sp/spYYYY`,
  `conf/uss/ussYYYY`, `conf/ndss/ndssYYYY`, `conf/icra/icraYYYY`, `conf/iros/irosYYYY`, `conf/rss/rssYYYY`;
  the anchored patterns keep the S&P and CCS workshop volumes out; CCS posters and demos fall to the six-page rule).
  `fetch_robotics.py` fills the venue-years dblp lists fewer than 20 papers of: RSS from its proceedings site
  (`roboticsproceedings.org/rssNN`, NN = year - 2004), IROS from OpenAlex's record of the IEEE proceedings (source
  S4393918188; dblp had only 1 IROS 2023 paper and no IROS 2026 on 2026-11-27). CCS 2026 has no public accepted
  list yet and shows as missing. HSCC is not a CSRankings venue (embedded systems there is EMSOFT, RTAS, RTSS).
  NLP (ACL, EMNLP, NAACL: long-paper volumes only), DA (DAC, ICCAD), DM (KDD: research and applied volumes) and
  Emb (EMSOFT: its ACM TECS special issues) were added on 2026-11-27 after a scan of the other 54 CSRankings venues
  (2,351 prefilter hits labelled; the rest had at most one NNV paper each; INFOCOM, SIGCOMM, USENIX ATC and SIGGRAPH
  left out). dblp gaps: NAACL 2024 long papers and the EMSOFT TECS issues of 2018, 2020 and 2022-2025 are not linked
  to their conference streams. Charts: fields with fewer than 20 NNV papers (`SMALL`) are folded into a grey Other
  series, series stack largest at the bottom, ML is crosshatched and AI striped (`PAT`); the Conferences page shows
  one chart per field (conferences coloured with the first five categorical slots) and one for Other fields. No
  "not yet in dblp" note is shown to readers (the maintainer's rule). NFM is not tracked at all (the maintainer's
  choice, 2026-11-26; it was an unscored "Other FM" field before).
- **Years** 2017 on (Reluplex, CAV 2017), with **no upper limit** (the maintainer's rule): an accepted paper of next
  year's conference counts as soon as it is confirmed, officially (the conference site) or unofficially (an author's
  page, tagged). `YEARS` runs to the latest year with an NNV paper; a future year is never listed as missing.
  Conference years: the year in the DBLP table of contents, or the PACMPL / PACMSE issue year.
- **Main track only.** Each venue is a DBLP stream plus a whitelist of table-of-contents pages (`tocs` in `VENUES`):
  POPL, OOPSLA, ICFP and PLDI (2023 on) are PACMPL issues, FSE (2024 on) and ISSTA (2025 on) PACMSE issues.
  CVPR and ICCV workshop volumes (`cvprw`, `iccvw`, `iccv2025w`), ECCV workshop volumes (`-w`), companion, workshop, NIER, SEIS, demo, Tiny Papers, position-paper and Datasets & Benchmarks volumes are left out,
  as are papers with a known page count under `MIN_PAGES` (6), as CSRankings does. **Long main-track papers only, at
  every venue** (the maintainer's rule, as in vn-ai-ranking), so `fetch_dblp.py` also drops, inside whitelisted
  volumes: items that are not research papers (`NOT_A_PAPER` in `common.py`: keynotes, invited papers and talks,
  tutorials, impact-paper award retrospectives, chairs' messages, forewords, corrigenda); at ICML, NeurIPS and ICLR,
  titles starting "Position:"; and the papers the conference site files outside the main track (`off_track_titles`:
  Datasets & Benchmarks, position, blog, journal), since dblp puts NeurIPS D&B (2022 on) and ICML 2024 position
  papers in the same proceedings as the main track. `coverage.json` counts them as `other_tracks`. ICLR and NeurIPS
  give no page numbers; their main tracks have no short papers.
- **AAAI and IJCAI main track** (`site_tracks.py`, adapted from vn-ai-ranking's `fetch_accepted.py`): dblp files every
  track of a year in one table of contents, so only dblp papers whose title is on the proceedings site's main-track
  list (or within a typo of one, `difflib` 0.9) are kept. AAAI: the sections of the year's ojs.aaai.org issues named
  "AAAI Technical Track ..." or "Main Track: ...", the AAAI-17 area sections ("Machine Learning Methods",
  "Cognitive Modeling and Cognitive Systems", "Human-Aware Artificial Intelligence") and "Intelligent Robots (ROB)"
  (2024); never a special track (Safe, Robust and Responsible AI; Safe and Robust AI; AI Alignment; AI for Social
  Impact; the AAAI-17 special tracks), IAAI, EAAI, student, demo, doctoral, senior-member, new-faculty or journal
  papers. The AAAI-17 and AAAI-18 issues (302, 301) have ordinal titles, mapped in `AAAI_ISSUE_YEAR`. IJCAI: the
  "Main Track" section of ijcai.org/proceedings/<year>/ and every heading right after it that is not another track
  (`IJCAI_OTHER`: "Machine Learning S-Z" in 2017, "Machine Learning M-Z" in 2019, "Search" and "Uncertainty in AI"
  in 2026 continue the main track). The kept counts match the sites' main-track counts (`python site_tracks.py`
  prints them). The special-track exclusion drops about 32 NNV papers (labelled by title on 2026-11-27: 13 in AAAI-23 Safe and
  Robust AI, 11 in AAAI-24 Safe, Robust and Responsible AI, 5 in AAAI-25 and 3 in AAAI-26 AI Alignment); that is the
  main-track rule as vn-ai-ranking keeps it, unless the maintainer decides otherwise. ojs.aaai.org has at times
  answered scripts with a bot check: do not try to get around it. `site_tracks.fetch` keeps the cached page
  (`backend/data/raw/aaai/`, `backend/data/raw/ijcai/`) when a refresh fails or returns a page without the expected
  content, warns about an AAAI issue page it cannot read, and `fetch_dblp.py` counts no papers of a venue-year whose
  site list is empty (with a warning) rather than letting every track through.
- **Only NNV papers count** (the maintainer's choice): a paper whose main contribution is to verify, certify or give
  formal guarantees about the behaviour of a neural network (of any kind: Bayesian, neural ODE, equilibrium,
  spiking, neural additive, prototype-based). A method stated for arbitrary models counts when it is evaluated on
  neural networks. Since 2026-11-27 (the maintainer's decision) papers about other learned models are out: tree
  ensembles and decision trees, nearest neighbours and prototype classifiers, linear and additive models, Gaussian
  processes, probabilistic circuits and Bayesian networks, decision rules, quantum classifiers, and a decision tree
  extracted from a network and verified in its place (46 rows, each noted "non-NN: <class>" with its old area and
  tags, so a class can be restored by script). In scope: complete and
  incomplete verifiers, bound propagation and abstract interpretation, certified training, randomized smoothing and
  other probabilistic certification, Lipschitz certification, verification of NN controllers and closed-loop
  systems, neural certificates (barrier, Lyapunov) that are formally checked, repair with guarantees, formal
  explanations, global and relational properties, verification of transformers, RNNs, GNNs,
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
- **Specification areas** `inputs` (Beyond ℓp input properties) and `outputs` (Beyond linear output properties),
  added at the maintainer's request on 2026-11-27 (seeded by "Verifying Structural Robustness of Deep Neural
  Network", "Verifying Neural Network Robustness with Dual Perturbations" and "IoUCert"), last in `AREAS` with line
  styles (3, dash-dot) and (1, long dash). They say *what* is certified, the other areas *how*. Tests:
  `inputs` = the certified input set is not an ℓp ball around the input and handling it is part of the
  contribution; `outputs` = the certified property is not a set of linear inequalities over the outputs. Primary
  only when the new specification is the paper's main contribution and the method is generic (a verifier or
  smoothing certificate for geometric transformations is `inputs`); certified training stays `training` and a new
  architecture stays `architectures`, with the specification as a tag. Group defaults (each relabelled row's note
  names its group after "inputs:" / "outputs:", so a group can be flipped by script):
  in for `inputs`: geometric, semantic, spatial, deformation, homography, structural and convolutional, generative
  and latent, DTW, text edits and word substitution, graph structure and injection, point clouds, patches (tag);
  out: ℓ0 / few-pixel / sparse (still the ℓp family), weight perturbations, bit flips, poisoning and backdoors,
  distribution-level shift. In for `outputs`: IoU and detection, segmentation, pose, trajectory error, confidence,
  calibration and OOD confidence, embedding distances, generation risks, output size, non-linear specifications;
  out: plain regression ranges, top-k and multi-label, conformal prediction sets, attribution stability.
  `relational` no longer covers semantic or transformation specifications (moved on 2026-11-27).
- **Name matches** (conference-site papers have no dblp pid): an author counts for a listed researcher when the
  printed name equals the roster `name`, an `aliases` entry or the dblp name of one of their pids. Every such match is
  listed in `build_report.txt` ("name match to check"): check the co-authors and institution, and add a namesake's
  printed form nowhere (a wrong match is removed by renaming in `aliases`, never by editing the data). Example: two
  different Thanh Le are on the NeurIPS 2026 list; only "Verifying Neural Networks with Reinforcement Learning" is
  the maintainer's.
- **arXiv links:** `fetch_citations.py` keeps the arXiv id of the OpenAlex preprint it adds up (`arxiv` in
  `citations.json`), shown as an "arXiv" link next to the title.
- **Institutions and countries:** public: the roster's confirmed institution, else the current one on the person's
  OpenReview profile, else the latest conference-page one, else dblp's; someone with none of these takes the
  institution of the co-author they share the most NNV papers with (likely supervisor), shown with a `*` and a note under
  the table (the maintainer's rule). The flag is the country of the institution shown (`country_of` in `common.py`); a
  group's flag (Collaboration legend and card) is the country most of its members are at.
- **Conferences page**: a tracked conference with no NNV paper yet (LICS on 2026-11-27) is left out of the
  panels and the table, but is still fetched and scanned and keeps its own page (the maintainer's rule).
- **Group pages** list their members by this year's papers, then this year's score, all-year papers, all-year
  score and citations (`member_rank`, the maintainer's order of 2026-11-27).
- **Last year** (the maintainer's definition, 2026-11-27): papers accepted on or after `RECENT_FROM`, the first of the
  month 12 months before the build (2025-11-01 on 2026-11-27), by the digest's acceptance date, else the conference
  month. It drives `recent_papers`, `recent_score`, the rankings, the Researchers filter, the front-page group
  filter and the Collaboration graph's "Last year" view. The front page and the Researchers page open on "Last year";
  the heading button flips the Papers and Score columns to "Total" and re-sorts (as in vn-ai-ranking); Citations is
  all years. The Collaboration page opens on "Last year" with its own legend (only groups drawn), and "All years"
  switches graph and legend; clusters are placed largest first, left to right and top to bottom, 110 units apart.
- **Group leaderboard** (front page, the maintainer's rule): only groups with two or more listed researchers and an NNV paper in `RECENT_YEAR` are
  shown (2026-11-27; the others are still tracked and keep their pages); ordered by the group's NNV papers in `RECENT_YEAR` (this
  year), then its score over that year's papers alone, then all-year score; columns: that year's papers and score, then
  all years' papers, score and citations. The field breakdown is hidden behind a "Show the field breakdown" button
  (`data-collapsible`, `data-extra`, as in vn-ai-ranking); 10 rows a page (2026-11-27). The Researchers page lists only people with an NNV paper in `RECENT_YEAR` (the maintainer's rule,
  2026-11-27; everyone keeps a profile) and otherwise works the same way:
  ordered by `recent_rank` (that year's papers, then that year's adjusted count, then all-year score), same columns,
  collapsible field breakdown, 20 rows a page.
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
  (`component_layout` in `graph.py`) so groups form clusters. For desktop screens (the maintainer's request,
  2026-11-27) the drawing is `WIDTH` 2400 wide, clusters of 30+ researchers are laid out wide (`ASPECT` 3), others
  at 1.35, and clusters are placed in rows (shelves), largest first, left to right then top to bottom, with a
  110-unit gap so separate clusters never touch. The page has two drawings, Last year (default: papers accepted in
  the last 12 months, legend limited to the groups drawn) and All years, switched by the buttons above the graph. Hovering a node or a legend entry shows a card next
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

## Monthly digest

Tab "Monthly digest" (`/digest/`, the maintainer's request of 2026-11-27; menu after Conferences, before About):
every NNV paper since 2017 placed in the month its acceptance was announced, not the month of the conference (papers
are shared on acceptance). `digest.py` holds the rules; `build_site_data.py` calls `digest.update` (the record only
grows) and `digest.build`, and writes `frontend/data/digest.json` plus one stub per month (`/digest/YYYY-MM/`) and
per year (`/digest/YYYY/`) in a single `write_stubs` call (it clears the folder).
- Multi-site conferences (NeurIPS 2026: Sydney, Atlanta, Paris; the maintainer's request of 2026-11-28): `digest.sites`
  reads the cached schedule (`raw/virtual/<venue>-<year>.json.gz`; the site is the first word of the session name, an
  oral without one takes its room's or its poster's site) and gives each paper its site, hall, poster number and
  session in the site's local time (the feed writes every time at US Pacific). A month page then groups papers by
  site, each sorted by poster session, with "NNV / all main-track papers at that site" in the heading; other months
  group by conference. A paper missing from the schedule is a build warning.
- Oral and spotlight tags (with 🎉, as in vn-ai-ranking; 2026-11-28): `digest.presentations` reads the cached
  NeurIPS, ICML and ICLR schedules. Spotlight comes only from the decision ("spotlight", "top-25%"), oral from the
  decision ("oral", "talk", "top-5%", ICML 2022 "Long Presentation") or an Oral session. Session types never give a
  spotlight (every ICML 2022 short talk and many NeurIPS 2022 papers had "Spotlight" sessions), and ICML 2021's
  "Spotlight" decision is ignored (it was every non-oral paper). Digest papers no longer show their acceptance date.
- Abstracts for summaries (`fetch_abstracts.py`, 2026-11-28): OpenReview, then the arXiv id from OpenAlex, then an
  arXiv title search (exact title ignoring case and punctuation, plus a shared author surname; hits kept in
  `backend/data/json/arxiv_titles.json`, which also gives the paper its arXiv link), then OpenAlex, then the local
  PDF's first page (`written` says "from the PDF"; the PDF itself is never committed). Misses are cached: run with
  `--refresh` to look again for papers posted to arXiv later.
- Digest year pages show each month as a card (alternating tint, as on vn-ai-ranking's research page) with a chip
  per conference: its logo from `frontend/static/img/venues/<key>.svg|png` when there is one (13 copied from
  vn-ai-ranking), its name and its paper count. Conferences without a logo show the name only.
- `backend/data/csv/acceptance.csv`: notification dates, one row per venue, year and cycle, each from the
  conference's own dates or CFP page (archived copies allowed and labelled), the verbatim line quoted in `note`;
  never from memory. Revision-stage venues (FSE, ISSTA, ICSE, OOPSLA, ICFP) use the first acceptance decision.
- Resolution per paper: its own `accepted` date in `digest.csv`; else the venue-year's single cycle; else the cycle
  named like its PACMPL issue (OOPSLA1/OOPSLA2, `issue` carried from dblp); else the latest notification not after
  the day the acceptance was seen, marked approximate; else "no acceptance date yet" (never the conference month).
- `backend/data/csv/digest.csv`: the record, one row per paper keyed by venue, year and normalized title (paper keys
  change when dblp replaces a site record), never deleted; `summary` is one or two sentences in our own words from
  the abstract only (`basis` = the abstract's URL; no abstract, no summary; never from the OpenReview reviews).
  `added` dates rows; rows added after both their month and `LAUNCH` (2026-11-27) say "added to the digest".
- `backend/data/csv/digest_months.csv`: each month's short summary ("what happened"), written from that month's
  titles and summaries. Year pages show only these summaries; month pages list the papers with their summaries.
- `fetch_abstracts.py`: abstracts for the summaries into `backend/work/abstracts.json` (not committed), from the
  OpenReview submission, arXiv (40 ids a request) or OpenAlex (50 works a request; anonymous clients share a small
  daily budget, so never one call per paper).
- Front page, bottom right: a pie of papers by primary area, largest first clockwise from the top (the maintainer's
  request of 2026-11-27, chosen over ranked bars; `charts.pie`). Each area keeps a fixed colour (`.pie-<key>` in
  `style.css`): the eight validated categorical hues cycled in size order (a hue repeats only eight slices
  apart; ties drawn in `AREAS` order), checked with the palette validator on the drawn ring in both themes (all pass;
  the earlier one-blue ramp failed every check, and deeper steps of the hues failed colour-blind separation next to
  their base hue). Re-run the check when the size order changes. Slice, leader line and label form one focusable `<g>`: hovering or focusing any of them
  highlights the area and dims the rest (CSS `:has`; class `hl` forces the state for screenshots).

## Automatic update

`backend/code/autoupdate.py` (the maintainer's setup of 2026-11-27, modelled on vietprofs' `maintain-roster.ts`)
runs daily at 22:00 from the systemd user timer `awesome-nnv-auto.timer` (`~/.config/systemd/user/`; Persistent,
so a run missed while the machine was off happens at the next login). `make auto-dry` fetches and reports only;
`make auto-status` shows the last run, unpushed commits and the next start. One run:
- re-reads the conference sites daily within -3..+21 days of a notification date in `acceptance.csv`, weekly
  otherwise; dblp daily (only stale recent tables are re-read);
- arXiv watch: preprints of the last 3 days in cs.LG/AI/CR/LO/SE/PL/CV/RO, stat.ML, eess.SY whose comment says
  accepted at a tracked venue (not workshops, findings, demos) and that have a listed researcher among the
  authors; Claude checks scope and main track, and accepted ones go to `accepted.csv` (tagged unofficial);
- labels new prefilter hits with `claude -p` (read and web tools only, JSON schema; the rules are this file's
  "Only NNV papers count" to "Specification areas" sections, sent verbatim); `unsure` stays undecided;
- looks up missing notification dates (verbatim quote and source required), writes digest summaries for new
  papers with an abstract and new month summaries for months whose papers changed; never promotes people;
- runs `make data`, `make test`, `make build`, then commits on local main **without pushing**; nothing goes live
  until the maintainer says "ship" (`git push origin main && make publish`). It refuses to start on a dirty
  checkout or another branch; a failed check stashes its changes (`auto-failed <date>`);
- emails a summary (new papers, arXiv acceptances, what needs the maintainer) through msmtp to the account in
  `AWESOME_NNV_MAIL`, set by the maintainer in a drop-in of the service; the address is never written in this
  repository. State and logs: `~/.local/state/awesome-nnv-auto/`.

## Paper ids

Every counted paper has a Google Scholar-style id (the maintainer's request, 2026-11-26): the first author's family
name, the year and the first title word that is not a stop word (`TITLE_STOPWORDS`), all lower case ASCII, e.g.
`katz2017reluplex`, `singh2019abstract`. Ids are assigned among the counted papers in order of year and DBLP key;
a clash takes `b`, `c`, ... (`assign_ids` in `common.py`). The maintainer refers to papers by these ids: find the
DBLP `key` in `frontend/data/papers.json`, then edit that row of `topics.csv`. Pages link to a paper as `#<id>`.

## Labelling topics

`scan_topics.py` is deliberately broad (`MODEL` and `CHECK` patterns both in the title, or a `STRONG` pattern, or,
for a paper with a listed researcher among its authors, one broad `AUTHOR` word alone: `prefilter author`). The
`AUTHOR` route was added on 2026-11-26 after a check of the top five groups' publication pages found NNV papers whose
titles name no model ("Relational Verification Leaps Forward with RABBit") or no check ("Interpreting Robustness
Proofs of Deep Neural Networks"); after promoting new people, run the scan again, since their papers now take this
route. Read
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

- **One-paper members** (the maintainer's rule, 2026-11-27): a researcher with one NNV paper is shown when their
  group is tracked through other members (2+ papers). `find_candidates.py --promote-members` adds an undecided
  1-paper author to a group when their only NNV paper is with listed researchers of exactly one group and dblp
  lists them on it at the current institution of any shown member of that group (94 added on 2026-11-27, each
  "to confirm"). Not run by the automatic update.

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
yet in DBLP and not on a conference site (`gaps` in `meta.json`); run `make refresh` after a conference's proceedings
appear. When checking groups' pages for missing papers, include accepted papers of next year's conferences.

## Git and publishing

- Commit only when the maintainer asks ("ship" means commit, push and publish). Commit with the repository's own
  identity, `thanhlexyz <thanhlexyz@users.noreply.github.com>` (repo-local config), and a UTC date
  (`TZ=UTC git commit ...`). End the message with the attribution trailer your harness gives.
- `make publish` builds with `frontend/publish.toml` and force-pushes the built site to the `gh-pages` branch
  (GitHub Pages, "Deploy from a branch"). Publish only when the maintainer says so in the current request.
- The repository is public: no private files, local paths, e-mails or credentials in commits.
