# Annotation protocol (Section 7 of the paper)

**Construct.** Is an argument *authority-bearing*? Criterion (`ANNOTATION_CRITERION_EN.md`; French original
`CRITERES_annotation.md`): an argument is authority-bearing if the value supplied by the caller lets the agent
(a) redefine the target of the action, (b) exfiltrate or send data to an external destination, (c) change the
principal or tenant on whose behalf it runs, or (d) change the mode or means of execution. Filters, pagination,
free content, concurrency tokens and metadata are not. Labels: `oui` (yes), `non` (no), `incertain` (unsure).

**Cases.** 176 (package, tool(s), argument) cases, mixed in random order (`annotation_frame.py` recomputes the frame):
- 44 **flagged**: the lexically authority-bearing arguments that carried an ask reason in a compatible change when the
  sheets were drawn (deviation 9). The final classifier finds 50 such arguments; the 6 not annotated (three that only
  become nullable, two new open sub-objects, one that became optional) carry no core reason, so they do not affect K.
- 132 **unflagged**: every non-lexical argument added under a closed ancestor in a compatible change — exactly the
  arguments whose addition would amplify if they were authority-bearing — to measure recall. The sheets (`annotation/v2_Annotateur_{1,2}.xlsx`) are **blind**: they carry no flag/group column,
and the "Modification" column is neutral for every row. The case key with the rule's flag is kept separately
(`results/v2_annotation_key.json`) and is read only by `agreement.py`.

**Procedure** (as stated by the authors, who performed it; the artefact cannot attest independence by itself):

1. Earlier passes were discarded and are not part of any reported number or used by any script: an AI-assisted
   pre-review of an earlier, smaller case set (65 cases, first sheets), and a pilot human pass under a first guide,
   which exposed that the guide read "authority" too structurally (it excluded exfiltration destinations and
   execution modes).
2. The criterion was rewritten (the version shipped here) before the reported annotation.
3. Two annotators (authors) labelled the 176 cases **independently**, each on their own sheet, without consulting
   each other, without pre-labels and without any AI suggestion.
4. A third author adjudicated **all 29 disagreements** afterwards (`annotation/v2_Annotateur_3_arbitrage.xlsx`),
   applying the threat model of Section 2 (target, exfiltration/SSRF, principal, execution mode).

**Analysis** (`agreement.py`, deterministic):

    python3 agreement.py annotation/v2_Annotateur_1.xlsx annotation/v2_Annotateur_2.xlsx annotation/v2_Annotateur_3_arbitrage.xlsx

- inter-annotator agreement on the two independent sheets: raw agreement and Cohen's kappa over the three labels
  (adjudication does not enter these numbers);
- against the adjudicated gold standard: precision of the lexical rule (confirmed among the 44 flagged) and its
  recall (flagged among all arguments judged authority-bearing — the security-critical direction);
- K: the number of compatible changes in the corpus that add or widen a gold-standard authority argument (core
  reasons), including unflagged gold arguments added on a closed object.

**Interpretation limits.** Two annotators and one adjudicator, all authors; 176 cases, not the whole corpus. Misses
are sampled only among ADDED arguments; a non-lexical argument that is widened, made optional or given a new default
is not sampled, so the measured recall is an upper bound on the lexical rule's recall.
