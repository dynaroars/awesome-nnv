# Awesome NNV

An open-source, data-driven static site that counts **neural-network verification (NNV)** papers of the field's
leading researchers at thirty-two top venues, grouped as [CSRankings](https://csrankings.org/) groups them:

- **ML:** ICML, ICLR, NeurIPS
- **CV:** CVPR, ICCV, ECCV
- **PL:** PLDI, POPL, ICFP, OOPSLA
- **SE:** FSE, ICSE, ASE, ISSTA
- **LV** (logic and verification): CAV, LICS
- **AI:** AAAI, IJCAI
- **Sec** (computer security): CCS, S&P (IEEE Symposium on Security and Privacy), USENIX Security, NDSS
- **Rob** (robotics): ICRA, IROS, RSS
- **NLP**: ACL, EMNLP, NAACL
- **DA** (design automation): DAC, ICCAD
- **DM** (data mining): KDD
- **Emb** (embedded and real-time systems): EMSOFT

Papers are counted from 2017 (Reluplex) onward, main track only, from [dblp](https://dblp.org) (CC0). Only papers
about verifying, certifying or formally guaranteeing the behaviour of neural networks count (not tree ensembles, nearest
neighbours or other non-neural models).
Each paper has one primary **area** (complete verification, bound propagation & abstract interpretation,
probabilistic certification, certified training, repair, formal explanations, NN control systems, global &
relational properties, beyond feed-forward nets, quantized & bit-level, other, beyond ℓp input properties,
beyond linear output properties). Researchers are grouped by
**research group**, named by its signature tool (α,β-CROWN, Marabou, NNV, ...), as at VNN-COMP.

## How to maintain

The site is maintained with an AI coding agent through plain requests; all rules and workflows are in
[AGENT.md](AGENT.md). Typical requests:

- *"Refresh the data: CAV 2027 is in dblp."*
- *"Label the new topic candidates."*
- *"Add `<dblp link>` to the list, in the `<group>` group."*
- *"Move `<paper>` to the certified-training area."*

## Requirements

- Python 3.10+ with `networkx`
- Hugo extended 0.156+

```bash
make fetch       # download the venues' main tracks from dblp (SPARQL)
make topics      # add new prefilter hits to topics.csv
make candidates  # rank undecided authors of NNV papers
make data        # rebuild frontend/data and the page stubs
make run         # local server with drafts at http://localhost:1212
make build       # production build (must show no warnings)
make test        # unit tests
```

## Licence

The code and data are released into the public domain (Unlicense). The group logos in
`frontend/static/img/groups/` belong to their owners and are not covered by the licence; their sources are listed
in `backend/data/csv/images.csv`.

Country flags in `frontend/static/img/flags/` are from [flag-icons](https://github.com/lipis/flag-icons) (MIT licence).
