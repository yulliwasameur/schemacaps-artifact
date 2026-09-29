# SchemaCaps artefact (anonymised for double-blind review)

Reproduce the pilot:  python3 classify2.py && python3 witness2.py && python3 timing2.py && python3 report2.py
Robustness:           python3 cap40_classify.py   (needs raw40/, produced by cap40.py)
Check the proof:      coqc proof/NonAmplification.v         (Coq 8.18; Print Assumptions = closed)
# Soundness oracle:     python3 oracle.py     (differential test of silent re-binds vs Definition 1)
# Role recount:         python3 role_review.py
Run the demos:        cd prototype && python3 demo_staged.py && python3 demo_scenarios.py && python3 replay_real.py && python3 bench_overhead.py

- PROTOCOLE.md (frozen, hashed before mining) + DEVIATIONS.md (dated log, 9 entries + erratum).
- classify.py = first classifier (kept); classify2.py = classifier of the paper (deviations 8-9).
- prototype/ = the client-side proxy (schemacaps_proxy.py), a staged vulnerable server, the end-to-end
  attack scenarios, the real-evolution replay, and the overhead benchmark. results/proto_*.json are their outputs.
- proof/NonAmplification.v = machine-checked definition, product lemma, chain proposition, effect corollary.
- annotation/ = two BLIND sheets (176 cases, 44 flagged + 132 unflagged) for an independent double annotation;
  agreement.py computes kappa, precision, recall and K. results/evidence_sheet.json = per-case evidence for the
  author-reviewed confirmed cases. results/client_survey.json = deployed-client behaviour survey (Sept 2026).
- Numbers in the paper come from results/v2_summary.json, robustness.json, cap_sensitivity.json, proto_*.json.
