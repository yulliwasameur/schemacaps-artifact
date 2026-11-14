# SchemaCaps — artefact

Yulliwas Ameur (Efrei Research Lab, Université Paris-Panthéon-Assas; CEDRIC, Cnam), Samia Bouzefrane (CEDRIC, Cnam),
Soumya Banerjee (Inria). Licence: MIT (code), CC BY 4.0 (data and documents); see `LICENSE`, `LICENSE-DATA`,
`CITATION.cff`. Archived on Zenodo, all versions: [10.5281/zenodo.24224247](https://doi.org/10.5281/zenodo.24224247); the paper cites
the version of tag `v1.0.1-camera-ready` (its DOI is shown on the Zenodo page of that release).

Artefact of *SchemaCaps: When a Compatible Tool Update Silently Widens an AI Agent's Authority* (ICAART 2027,
SciTePress). Everything the paper reports is regenerated from the archived corpus by scripts; `numbers.tex`, which
the paper `\input`s, is itself generated, and `make check` fails if any regenerated deterministic number differs from it
(machine-dependent values — timing `Tm*`, overhead `Ov*`, time-bounded sample counts `OrGenLex`/`OrGenFree` and the
benchmark's timeout count `BenchChkUnknown` — are reported, not failed on; `make reproduce` re-measures timing on your
machine, whereas the shipped `results/v2_timing.json` is the original 2-core x86-64 measurement cited by the paper).

## Quick start

    docker build -t schemacaps . && docker run --rm schemacaps          # offline: make reproduce
    # or, without Docker (Python 3.11):
    python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.lock && make reproduce
    make proof            # Coq 8.18.0 (or: make proof-docker)
    make survey           # client survey test protocol (node >= 20, npm, uv, network)

`make reproduce` = `test pilot oracle annotation robustness demo adversarial bench check`: it regenerates every result, then checks
it against the shipped `numbers.tex` (`make numbers` rewrites that file). About an hour on 2 cores; the
oracle and the decision-time measurement dominate.

## Claims, evidence levels, and how to check them

| Claim (paper section) | Level | Command | Output |
|---|---|---|---|
| Per-step non-amplification composes along a chain (§4) | mechanised | `make proof` | `proof/NonAmplification.v` (Print Assumptions: closed) |
| The rule decides Definition 1 conservatively (§4) | tested | `make test` | 48 tests in `tests/` |
| The subschema checker is unsound on boolean enums; the guard fixes the probes (§4) | tested | `python3 checker_probes.py` | `results/checker_probes.json` |
| Exact-reference benchmark of the checker and of the rule; the two gaps it exposed are fixed (§4, deviation 11) | tested | `make adversarial` | `results/adversarial_bench.json` |
| No generated witness contradicts any silent re-bind (§7) | measured | `make oracle` | `results/oracle2_{label_free,lexical}.json` |
| The proxy enforces the rule; overhead (§5) | prototype | `make test`, `make bench` | `tests/test_proxy.py`, `results/proto_overhead.json`, `results/v2_timing.json` |
| Staged attacks blocked; six real cases (§6) | prototype | `make demo` | `results/proto_scenarios.json`, `results/proto_replay_real.json` |
| Compatible widenings exist; cost per rule (§7, Tables 3 and 7) | measured | `make pilot robustness` | `results/v2_summary.json`, `results/free_summary.json`, `results/taxonomy.json`, `results/robustness*.json`, `results/cap_sensitivity.json` |
| Annotation: kappa, precision, recall, K (§7) | measured | `make annotation` | `results/agreement.json`, `results/annotation_frame.json` |
| Deployed clients do not re-check (§7, Table 8) | measured | `make survey` | `results/client_survey.json`, `results/client_survey_tests.json` |

## Layout

- `classify2.py` — the rule (deviation 10): coordinates, effective values, product condition, guarded checker,
  labellers (`LABEL_FREE` default, `LEXICAL`, `manifest_labeller`). `classify.py` is the first classifier (kept).
- `oracle2.py` — differential oracle over every silent re-bind; `checker_probes.py`; `taxonomy.py`; `robustness.py`;
  `witness2.py` (witnesses for core cases, reverse search on compatibility verdicts); `timing2.py`; `report2.py`
  (writes `RESULTS.md`); `make_numbers.py` (writes `numbers.tex`).
- `prototype/` — `schemacaps_proxy.py` (stdio proxy: capability tuple, manifest, cumulative U, call validation,
  policy on effective values, signed hash-chained receipts, `verify`), `staged_server.py`, `demo_scenarios.py`,
  `replay_real.py`, `bench_overhead.py`, `rawclient.py`; `prototype/archive/` holds the revision-1 proxy.
- `clients/` — drift server and one driver per surveyed client; `run_survey.sh` pins every version.
- `raw/` (657 release records), `raw_intermediates/` (27, for dating), `raw40/` (cap sensitivity), `raw_run1/`
  (discarded first run, deviation 5); `results/releases.csv` — per-release manifest (install command, registry
  artefact and integrity hash, outcome, `serverInfo`, protocol version, SHA-256 of the tool list);
  `cache/registry/` — the registry documents it was built from.
- `annotation/` — the two independent sheets and the adjudication sheet; `results/v2_annotation_key.json` — case
  metadata with the lexical flag (read only by `agreement.py`). Protocol: `ANNOTATION_PROTOCOL.md`; criterion:
  `CRITERES_annotation.md` (French, used by the annotators) and `ANNOTATION_CRITERION_EN.md`.
- `PROTOCOLE.md` (pre-registered, French) and `PROTOCOL_EN.md`; `DEVIATIONS.md` and `DEVIATIONS_EN.md` (dated,
  pre-classification vs post hoc); `TIMELINE.md`; `REDACTIONS.md` (annotator names replaced by roles, and hashes).
- `logs/` — extraction logs (`extract.log`, `extract_raw.log`, `intermediates.log`) and the logs of the last run.

## What the artefact does not establish

The independence of the two annotators is stated by the authors (`ANNOTATION_PROTOCOL.md`); the sheets cannot prove
it. The oracle and the checker guard are randomised tests with fixed seeds: a clean run is evidence, not proof. The
staged planner is scripted and the six real cases are replayed on extracted schemas, without executing the servers.
The receipt chain is a local audit log; publication to a transparency log is not implemented.
