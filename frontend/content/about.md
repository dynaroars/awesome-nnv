---
title: "About"
toc: true
---

Research grows through communities of people building on each other's work. **Awesome NNV** helps you find papers in **neural-network verification (NNV)** and see how the researchers behind them collaborate. It tracks NNV papers across 25 top conferences and maps co-authorship links between researchers. Everything is open source, and you can browse the code, data tables, and scripts on [GitHub](https://github.com/dynaroars/awesome-nnv).

## Venues

Conferences are grouped into eight fields, following [CSRankings](https://csrankings.org/):

| Field | Venues |
|:---|:---|
| ML, machine learning | ICML, ICLR, NeurIPS |
| CV, computer vision | CVPR, ICCV, ECCV |
| PL, programming languages | PLDI, POPL, ICFP, OOPSLA |
| SE, software engineering | FSE, ICSE, ASE, ISSTA |
| LV, logic and verification | CAV, LICS |
| AI, artificial intelligence | AAAI, IJCAI |
| Sec, computer security | CCS, S&P, USENIX Security, NDSS |
| Rob, robotics | ICRA, IROS, RSS |

Coverage starts in 2017, the year Reluplex appeared at CAV, and includes accepted papers of upcoming conferences. Following CSRankings, we only include main-track papers that are at least six pages long. We leave out workshops, companion volumes, demos, position papers, Tiny Papers, new-ideas and industry tracks, Datasets & Benchmarks tracks, and keynotes and invited talks, including those printed in the main proceedings. At AAAI and IJCAI, only the main technical track counts: special tracks (such as AAAI's Safe, Robust and Responsible AI and AI Alignment tracks, and IJCAI's AI for Good), survey, journal, demo, student and senior-member papers are left out, following the section lists on `ojs.aaai.org` and `ijcai.org`. Journal-style conference tracks (POPL, OOPSLA, ICFP, and PLDI in PACMPL, plus FSE and ISSTA in PACMSE) are included.

Most paper lists come from [dblp](https://dblp.org) (CC0) via its SPARQL service. Because dblp can take a few weeks to index new proceedings, we temporarily pull recent ICML, NeurIPS, and ICLR papers from the official conference sites (`icml.cc`, `neurips.cc`, `iclr.cc`) and match authors by name until dblp catches up. For the software-engineering and programming-languages conferences, we read the accepted-paper lists on the conferences' own pages (`conf.researchr.org`) the same way. Robotics years that dblp has not indexed are read from the RSS proceedings (`roboticsproceedings.org`) and, for IROS, from OpenAlex's record of the IEEE proceedings. A paper whose acceptance is confirmed only on an author's page is counted too and marked *unofficial* until an official list includes it. Any other recent conference years missing from dblp are noted on the [Conferences](../conferences/) page. When OpenAlex has an arXiv record for a paper, we link to it next to the title.

## What counts as an NNV paper

A paper counts if its main goal is to verify, certify, or give formal guarantees about a neural network. Papers about other learned models, such as tree ensembles, nearest-neighbour classifiers or linear models, are not included. Specifically, we include:

- Complete and incomplete verifiers, bound propagation, and abstract interpretation
- Certified training, randomized smoothing, probabilistic certification, and Lipschitz bounds
- Neural controllers, closed-loop systems, and formally checked neural certificates (such as barrier and Lyapunov functions)
- Provable repair, formal explanations, and global or relational properties
- Verification of quantized networks and non-feed-forward models (transformers, RNNs, GNNs, and language models)
- Specifications beyond the usual ones: input sets other than an ℓp ball (geometric, semantic and structural transformations, patches, text edits) and output properties that are not linear (IoU for object detection, segmentation, pose, confidence)
- Verifier soundness, proof checking, tools, benchmarks, and surveys

We leave out DNN testing and fuzzing, empirical attacks or defenses without formal guarantees, and papers that use neural networks or LLMs to verify ordinary programs.

To find these papers, a broad keyword filter scans titles across all 25 conferences. Each match is then reviewed (with AI assistance) and logged with a dated note in `topics.csv`, and we continue to review and fix edge cases over time. Every included paper is assigned one primary [area](../areas/) and optional secondary tags. If you spot a mistake, please let us know (see [Corrections](#corrections)).

## Researchers and groups

Every author with at least two NNV papers at the tracked venues is listed, from students to senior faculty and industry researchers; authors with a single paper are added once they reach two. Every researcher is matched by their dblp ID so authors with the same name do not get mixed up. Institutions come from manual checks or dblp profiles, and new researchers are first placed in the group of the listed co-author they share the most NNV papers with, then checked by hand.

Rather than ranking by university, we organize people by **research group**, named after their signature tool or research focus (similar to how teams compete at [VNN-COMP](https://sites.google.com/view/vnn2025)). Institutions are shown for context only, and all of a researcher's papers count toward their current group.

## Monthly digest

The [Monthly digest](../digest/) lists the NNV papers accepted each month, with a short summary of each written from its abstract. Papers are dated by their conference's acceptance notification, taken from the conference's own pages, because that is when most papers are shared.

## Scores

Individual scores follow the CSRankings adjusted count: a paper with `N` authors gives `1 / N` credit to each listed author.

Group scores mirror how CSRankings ranks institutions. For each of the eight fields (ML, CV, PL, SE, LV, AI, Sec, and Rob), we sum the adjusted counts of all group members and take the geometric mean of `(field count + 1)` across the eight fields. Adding 1 prevents a zero in one field from zeroing out the whole score, while the geometric mean rewards groups that publish across multiple communities. In a group's total paper count, a paper co-authored by several members is counted only once. To follow active teams, the group leaderboard is ordered by each group's NNV papers in the current year, then by its score over that year's papers alone (the same formula); the all-year paper count and score are shown next to them.

## Citations

Citation counts are pulled from [OpenAlex](https://openalex.org/). Because OpenAlex often stores a preprint and its published version as separate entries, we sum citations across all records that match the paper's DOI or have the same title within a nearby year. A researcher's citation total sums their NNV papers, and a group's total counts each shared paper once. Citations are shown for reference only and do not affect rankings.

## Corrections

Spot something missing or wrong? Use the [Feedback](../feedback/) page or open an issue on [GitHub](https://github.com/dynaroars/awesome-nnv/issues) to suggest a researcher, recategorize a paper, or flag a paper that should or shouldn't be included.
