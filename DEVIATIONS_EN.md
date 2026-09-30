# Deviations from the protocol (English translation of `DEVIATIONS.md`, with a status table)

Times are UTC, reconstructed from file modification times and from the `extracted_at` field recorded in every
release record (`TIMELINE.md`). "Pre-classification" means decided before any schema was classified;
"post hoc" means decided after inspecting extraction or classification results, or after a review.

| # | When (UTC, 29–30 Sept 2026) | What | Status | Effect on reported numbers |
|---|---|---|---|---|
| 1 | 29/09 during extraction, before classification | at most 20 versions per package, evenly spaced, first and last included | pre-classification | defines the corpus |
| 2 | idem | 4 packages without a stable version in the window excluded | pre-classification | defines the corpus |
| 3 | idem | application skeletons excluded from stratum A | pre-classification | defines the corpus |
| 4 | idem | stratum B: the 15 packages listed, by weekly downloads | pre-classification | defines the corpus |
| 5 | 29/09 15:33, after a first run of 73 releases | dependencies resolved at publication date (`--before`, `--exclude-newer`); first run discarded | post hoc (measurement fix) | removes spurious empty schemas |
| 6 | 29/09 17:29 | second extraction pass with a minimal JSON-RPC client for SDK-validation failures | post hoc (measurement fix) | +27 releases recovered |
| 7 | 29/09 17:40 | a parameter removed from an open object reported apart | post hoc | superseded by 8 |
| 8 | 29/09 21:17, after an adversarial review | classifier v2: `required`, defaults, nested paths, openings, product condition, tool hints | post hoc | defines the reported rule |
| 9 | 29/09 evening, after a second review | ⋆ under closed ancestors, typed `additionalProperties`, branch descent, unresolved `$ref` | post hoc | re-approvals 343 → 395 |
| 10 | 30/09, revision 2 | see below | post hoc | lexical counts unchanged; label-free mode added |

Deviation 10 in detail (previous versions archived: `classify2_dev9.py`, `results/v2_dev9_*`, `prototype/archive/`):

- **(a)** 30/09 06:07 — *not logged at the time, logged here:* `nullable` added to the ask set (`null` is not
  absence) and the oracle's sentinel fixed (a `null` witness was discarded). Re-approvals 395 → 412; compatible
  strict amplifications 257 → 274.
- **(b)** A closed object that becomes `{}`, `true` or unconstrained is an opening; removal from a parent that stays
  closed is a restriction; a change of shape asks. No effect on the corpus counts.
- **(c)** `jsonsubschema` returns ⊆ for an unrestricted boolean against an `enum`/`const`-restricted boolean (3 of 20
  probes, `tests/test_checker.py`). Booleans are normalised and every ⊆ verdict between different schemas is guarded
  by a counterexample search (Hypothesis, at most 60 draws and 2 s, fixed seed). On the corpus the guard ran 407 times (lexical) and
  467 times (label-free), overturned no verdict and never failed to generate (signal-free guard: the time bound is checked inside the test body).
- **(d)** A label-free mode (unknown role ⇒ authority; the proxy's default) is added; costs are reported for both
  labellings; the lexical rule is kept as a heuristic whose recall is measured.
- **(e)** Oracle v2 audits every silent re-bind (compatible, incompatible, compatibility undecided); draws are
  deterministic and generation failures are counted; in label-free mode it tests whole-schema inclusion and defaults.
- **(f)** Incompatible changes, decided explicitly: the rule is orthogonal to compatibility; an incompatible,
  non-amplifying change is re-bound without asking (calls may fail; no authority is gained).
- **(g)** Proxy revision 2: versioned role manifest and h_A, cumulative U, P and h_P, server identity, call
  validation, policy on nested paths and array elements, `null` distinct from absence, declared defaults,
  receipts with full SHA-256, sequence numbers and a hash chain, a `verify` command, a single-threaded event loop (no races between list and call handling on the capability state).
- **(h)** Real replay on the exact release pairs of Table 5; overhead re-measured.
- **(i)** `robustness.py` added (regenerates the package-level bootstrap with a fixed seed: [3.5, 25.2]% against
  the published [3.4, 25.2]%, whose seed was not recorded).
- **(j)** Independent double annotation completed (176 cases) and the 29 disagreements adjudicated.
- **(k)** Per-release manifest with registry hashes (`results/releases.csv`).

What was pre-specified is the corpus, the window, the extraction procedure, the two questions and the three rules
compared. The classifier, and hence every count it produces, is post hoc; the paper says so.
