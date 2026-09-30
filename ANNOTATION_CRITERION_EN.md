# Annotation guide — "authority-bearing argument" (English translation)

> Translation for reviewers of `CRITERES_annotation.md`, the French guide the annotators used. The French text is
> authoritative. Annotator names are replaced by roles in the anonymised artefact.

**Goal.** For each case (package, tool, argument), decide whether the argument is *authority-bearing*:
`oui` (yes) / `non` (no) / `incertain` (unsure). Judge the argument's **semantic role**, not whether a vulnerability
exists.

**Rule (one sentence).** An argument is authority-bearing if the value supplied by the caller lets the agent
**(a)** redefine the **target** of the action, **(b)** **exfiltrate** or send data to an **external destination**,
**(c)** change the **principal / tenant** on whose behalf the action runs, or **(d)** change the **mode or means of
execution**. Otherwise, `non`.

| Mark `oui` if the value designates… | Mark `non` if the value only… |
|---|---|
| a **resource** acted upon: path, file, repository, project, database, record, id of an object created/modified/deleted | **filters / searches / sorts**: `query`, `q`, `search`, `filter`, `sort`, `order` |
| a **destination**: URL, webhook, e-mail, endpoint, host, channel, bucket | **paginates**: `limit`, `cursor`, `page`, `per_page`, `offset` |
| a **principal / tenant**: account, owner, tenant, namespace, organisation | carries free **content**: `body`, `text`, `message`, `content`, `title`, `description` |
| an **executable / mode**: interpreter (`shell`), executed script, local→remote switch (`isUrl`) | is a **concurrency or control token**: `sha`, `last_commit_id`, read-only `ref` |
| | is **metadata** without a target effect: `labels`, `milestone`, `is_private`, `encoding` |

**Consistency — the point that derailed the pilot pass.** Apply the rule **the same way to all comparable cases**.
If `webhookUrl` is `oui` (destination), then `bundleUrl`, `destination`, `metroHost`, `profileUrl` are too. If `path`
(gitlab) is `oui` (resource), then `path` (agent-device), `iosXctestrunFile`, `saveScript` are too. A case is not
treated differently because it is "interesting" for the paper.

**Procedure per case.** 1) Read package / tool / argument. 2) If the name is not enough, consult the schema or the
documentation of the given version. 3) Choose `oui` / `non` / `incertain`. 4) Short justification (one line) + source
consulted. `incertain` is a legitimate choice for borderline cases (e.g. an id that can be read-only or a write
target depending on the tool) — state what is missing to decide.

**Independence (required for kappa to mean anything).**
- **Two distinct people**, **each on their own**, without consulting each other and without looking at the other's
  answers or at any automatic suggestion.
- **No target result** (neither a kappa, nor a precision, nor "saving" an example). Annotate and accept the outcome.
- **Disagreements are normal and expected** (typically 10–20% of cases); they give kappa and adjudication their value.
- **Adjudication** by the third person only on the cases where the two differ, afterwards.

**What the script then produces** (`agreement.py`, from the two completed sheets): raw agreement, **Cohen's kappa**,
the lexical rule's **precision** (among flagged arguments, how many are confirmed) and above all its **recall** (among
arguments judged authority-bearing, how many the rule had flagged — the critical direction for security), plus the
validated count after adjudication. These numbers — whatever they are — replace the provisional lexical count.
