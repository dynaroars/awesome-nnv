---
title: "About"
toc: true
---

**Awesome NNV** counts papers on **neural-network verification** (NNV) by the field's leading researchers at
seventeen top venues. It is open source; the code, the hand-kept tables and the generated data are on
[GitHub](https://github.com/thanhlexyz/awesome-nnv).

## Venues

Venues are grouped into fields as [CSRankings](https://csrankings.org/) groups them:

| Field | Venues | Scored |
|:---|:---|:---|
| ML, machine learning | ICML, ICLR, NeurIPS | yes |
| CV, computer vision | CVPR, ICCV, ECCV | yes |
| PL, programming languages | PLDI, POPL, ICFP, OOPSLA | yes |
| SE, software engineering | FSE, ICSE, ASE, ISSTA | yes |
| LV, logic and verification | CAV, LICS | yes |
| Other FM | NASA Formal Methods (NFM) | no, not a CSRankings venue |

Papers count from 2017, the year of Reluplex (CAV 2017), onward. Only main-track papers count: companion volumes,
workshops, new-ideas and industry tracks, demos, Tiny Papers, position papers and Datasets & Benchmarks tracks are
left out, as are papers shorter than six pages, as CSRankings does. POPL, OOPSLA, ICFP and PLDI papers published in
PACMPL, and FSE and ISSTA papers published in PACMSE, count as conference papers.

Paper lists come from [dblp](https://dblp.org) (CC0), read through its SPARQL service. dblp adds proceedings some
weeks after a conference; until it does, ICML, NeurIPS and ICLR papers come from the accepted-paper lists of the
conference sites (icml.cc, neurips.cc, iclr.cc), with their authors matched by name. The other recent venue-years
not yet in dblp are marked on the [Conferences](../conferences/) page. Each paper links to its preprint on arXiv when
OpenAlex knows one.

## What counts as an NNV paper

A paper counts when its main contribution is to verify, certify or give formal guarantees about the behaviour of a
neural network or another learned model. This includes complete and incomplete verifiers, bound propagation and
abstract interpretation, certified training, randomized smoothing and other probabilistic certificates, Lipschitz
certification, verification of neural controllers and closed-loop systems, formally checked neural certificates,
repair with guarantees, formal explanations, global and relational properties, verification of transformers,
recurrent and graph networks, tree ensembles and language models, quantized networks, and work on the soundness,
tools and benchmarks of verifiers.

DNN testing and fuzzing, empirical attacks and defences without a certificate, and the use of neural networks or
language models to verify ordinary programs do not count.

A broad keyword filter on titles finds the candidate papers in every venue. Each candidate was then judged from its
title, with the help of an AI assistant, and the decision recorded with a dated note in `topics.csv`; the decisions
are being reviewed and corrected over time. Each counted paper gets one primary [area](../areas/) and may carry
secondary tags. If a paper is in the wrong place, please say so (see Corrections).

## Researchers and groups

The list holds faculty and senior researchers at companies and labs, plus a few early-career researchers whose
work is central to the field. It started from the authors with the most NNV papers and is still being completed and
checked. Authors are identified by their dblp person record, so namesakes do not mix. Institutions come from the
maintainer's checks or from dblp.

Researchers are grouped by **research group**, named by the group's signature tool or line of work, as teams are
known at [VNN-COMP](https://sites.google.com/view/vnn2025). The institution is shown as information only. All of a
person's papers count for their current group.

## Scores

A researcher's score is the CSRankings adjusted count: each NNV paper at a CSRankings venue is worth
`1 / N` to each listed author, where `N` is the number of authors. A group adds up its members' adjusted counts in
each of the five scored fields; its score is the geometric mean over ML, CV, PL, SE and LV of `(field count + 1)`, as
CSRankings ranks institutions. Adding 1 keeps a field with no papers from zeroing the score, and the geometric mean
rewards groups that publish across communities. A paper with several members of one group counts once in that
group's paper count.

## Citations

Citation counts come from [OpenAlex](https://openalex.org/). OpenAlex often keeps a preprint and its published
version as separate records, so a paper's count adds the citations of every record with exactly the same title and a
nearby year, and of the record of its DOI. A researcher's total
adds the citations of their NNV papers; a group's total counts each paper once. Citations are shown for information
and do not enter any score.

## Corrections

Open an issue on [GitHub](https://github.com/thanhlexyz/awesome-nnv/issues) to add a researcher, move a paper to
another area, or report a paper that should (not) count.
