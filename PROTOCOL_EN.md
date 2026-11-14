# SchemaCaps — pilot protocol (English translation)

> **This is a translation for reviewers.** The authoritative, pre-registered text is `PROTOCOLE.md` (French),
> written on 29 Sept 2026 at 15:25:05 UTC and hashed ten seconds later (`PROTOCOLE.sha256`), before the corpus
> was enumerated (15:25:44–15:26:15 UTC) and extracted (15:29–16:14 UTC). The ordering is recorded in the
> artefact (file times and the `extracted_at` field of every release record, see `TIMELINE.md`); it is
> self-attested — the protocol was not deposited with a third-party registry. The copy of `PROTOCOLE.md` in this
> artefact has two annotator names replaced by roles (see `REDACTIONS.md`), so its hash differs from the recorded
> one; the original file is kept by the authors and available on request, so the recorded hash can be checked then.

## Question
Among the real evolutions of the input schemas (`inputSchema`) of the tools of published MCP servers, how many
are *compatible* (every old call remains valid) while *widening* authority on an authority-bearing argument? How
many re-approvals does a non-amplification rule save compared with fingerprint pinning?

## Corpus (rule written before mining)
- **Stratum A — official reference servers.** Every npm package `@modelcontextprotocol/server-*` that is an
  executable MCP server (excluding SDKs, libraries and skeletons), and the official PyPI packages
  `mcp-server-fetch`, `mcp-server-git`, `mcp-server-time`, `mcp-server-sqlite`.
- **Stratum B — most adopted third-party servers.** The 15 most downloaded npm packages (weekly downloads,
  npm search API on 29 Sept 2026) carrying the keyword `mcp-server` or `mcp` that are MCP stdio servers launchable
  without an account (excluding SDKs, frameworks, clients, proxies).
- **Window:** every stable version (no pre-release suffix) published from 1 Jan 2025 to 29 Sept 2026.

## Extraction
- Each version is installed in isolation (`npm install <pkg>@<v>` or `pip install <pkg>==<v>` in a venv),
  launched over stdio with neutral arguments (temporary directory, dummy tokens), queried with `initialize` then
  `tools/list` (60 s timeout).
- Schemas are archived as returned, with the SHA-256 of their canonical JSON form.
- A version that does not start or does not answer is **counted and excluded**, never reconstructed.

## Classification of a pair of successive versions (per tool)
- Tool added / removed / unchanged (identical fingerprint) / changed.
- For a changed tool: `compatible` if S_old ⊆ S_new (every old call valid); `narrowed` if S_new ⊆ S_old;
  decided by `jsonsubschema` (sound but incomplete: "undecided" when it fails).
- **Amplifying** if, on at least one authority-bearing argument, S_new admits values S_old refused (projection of
  the schema on that argument, S_new_a ⊄ S_old_a), or if a new authority-bearing argument appears.
- Authority-bearing roles: **provisional** annotation by a lexical rule (recipient, path, URL, repository,
  account, command, SQL query, resource identifier, ...), published in full, **to be validated by two human
  annotators** (two of the authors) before any use in the paper.

## Rules compared
1. Fingerprint pinning (ETDI / Vercel `detectToolDrift` style): any changed tool ⇒ re-approval.
2. Compatibility: a compatible changed tool passes without re-approval.
3. Non-amplification (SchemaCaps): re-approval iff amplifying or undecided.

## Measures
Pairs, changed tools, compatible, compatible-and-amplifying, re-approvals per rule, undecided rate, extraction
failures. All numbers are produced by the repository's scripts, never typed by hand.

## Stopping criterion
If no compatible-and-amplifying evolution is found, the result is reported as is.

---
*Note added in revision 2 (not part of the pre-registered text):* the protocol calls `jsonsubschema` "sound".
Revision 2 found it unsound on one pattern (an unrestricted boolean compared with an enum- or const-restricted
boolean; `tests/test_checker.py`). The classifier now normalises that pattern and guards every inclusion
verdict with a counterexample search (deviation 10).
