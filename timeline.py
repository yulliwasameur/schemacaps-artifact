#!/usr/bin/env python3
"""TIMELINE.md: when the protocol, the corpus, the extraction and each classifier version were produced (UTC).
Sources: file modification times (preserved in the artefact with cp -p and in the zip) and the extracted_at field
recorded in every release record, which does not depend on file times."""
import datetime, glob, json, os
mt = lambda p: datetime.datetime.utcfromtimestamp(os.path.getmtime(p)).strftime("%Y-%m-%d %H:%M:%S") if os.path.exists(p) else "-"
rows = [("PROTOCOLE.md written (pre-registered protocol)", mt("PROTOCOLE.md")),
        ("PROTOCOLE.sha256 written (hash + date line)", mt("PROTOCOLE.sha256")),
        ("npm search snapshot (stratum B candidates)", mt("npm_search_2026-09-29.json")),
        ("corpus_versions.json (window enumerated)", mt("corpus_versions.json"))]
for d, label in (("raw_run1", "first extraction run (discarded, deviation 5)"), ("raw", "main extraction"),
                 ("raw_intermediates", "intermediate releases (dating)")):
    ts = sorted(t for t in (json.load(open(f)).get("extracted_at") for f in glob.glob(d + "/*.json")) if t)
    if ts:
        rows.append((f"{label}: {len(ts)} records, first", ts[0].replace("T", " ").rstrip("Z")))
        rows.append((f"{label}: last", ts[-1].replace("T", " ").rstrip("Z")))
for f, label in (("classify.py", "first classifier"), ("classify2_dev8.py", "classifier v2 (deviation 8)"),
                 ("classify2.py", "classifier, revision 2 (deviation 10)"), ("DEVIATIONS.md", "deviation log, last edit")):
    rows.append((label + f" ({f})", mt(f)))
rows.sort(key=lambda r: r[1])
out = ["# Timeline (UTC)", "", "Self-attested: file times and recorded extraction times; nothing was deposited with a third party.", "",
       "| When (UTC) | Event |", "|---|---|"] + [f"| {w} | {e} |" for e, w in rows]
out += ["", "The protocol hash in PROTOCOLE.sha256 is that of the original file; the artefact copy of PROTOCOLE.md is",
        "anonymised (REDACTIONS.md), so its own hash is given there as well."]
open("TIMELINE.md", "w").write("\n".join(out) + "\n"); print("\n".join(out))
