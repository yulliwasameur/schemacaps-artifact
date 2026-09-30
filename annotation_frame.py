#!/usr/bin/env python3
"""Sampling frame of the annotation (revision 2): documents how the 176 cases relate to the corpus.

  flagged frame   : lexically authority-bearing paths that carry an ask reason (STRICT) in a compatible change;
  unflagged frame : non-lexical paths ADDED under a closed ancestor in a compatible change (a new coordinate that
                    would amplify if it were authority-bearing) -- the population on which recall is measured.
The sheets were drawn during deviation 9. This script recomputes both frames with the final classifier and lists
the flagged-frame arguments that were not annotated. Because misses are sampled only among ADDED arguments, the
measured recall is an upper bound on the lexical rule's recall over all changes of unflagged arguments.
Output: results/annotation_frame.json
"""
import csv, json, warnings
warnings.filterwarnings("ignore")
import classify2
from classify2 import walk, LEXICAL, STRICT, CORE, norm_schema
from classify import resolve_local_refs
from witness import load as ld

key = json.load(open("results/v2_annotation_key.json"))
F = {(k["pkg"], k["path"]) for k in key if k["group"] == "F"}
U = {(k["pkg"], k["path"]) for k in key if k["group"] == "U"}
rows = [r for r in csv.DictReader(open("results/v2_changes.csv")) if r["schema_changed"] == "True" and r["compatible"] == "True"]
flag, reasons_of, unflag = set(), {}, set()
for r in rows:
    for x in r["reasons"].split(";"):
        k, _, p = x.partition(":")
        if p and not p.startswith("<") and LEXICAL(p) and k in STRICT:
            flag.add((r["package"], p)); reasons_of.setdefault((r["package"], p), set()).add(k)
    o = [t for t in ld(r["package"], r["from"])["tools"] if t["name"] == r["tool"]][0]
    n = [t for t in ld(r["package"], r["to"])["tools"] if t["name"] == r["tool"]][0]
    so = resolve_local_refs(norm_schema(o.get("inputSchema"))); sn = resolve_local_refs(norm_schema(n.get("inputSchema")))
    do, oo = walk(so)[:2]; dn = walk(sn, branches=True)[0]
    for p in set(dn) - set(do):
        if not LEXICAL(p) and classify2.closed_ancestor(p, oo, do):
            unflag.add((r["package"], p))
missing = sorted(flag - F)
res = {"flagged_frame": len(flag), "flagged_annotated": len(F & flag), "flagged_not_in_frame": len(F - flag),
       "flagged_not_annotated": [{"package": p, "path": q, "reasons": sorted(reasons_of[(p, q)]),
                                  "has_core_reason": bool(reasons_of[(p, q)] & set(CORE))} for p, q in missing],
       "unflagged_frame": len(unflag), "unflagged_annotated": len(U & unflag), "unflagged_not_in_frame": len(U - unflag),
       "recall_note": "misses are sampled among added arguments only: measured recall is an upper bound"}
json.dump(res, open("results/annotation_frame.json", "w"), indent=1)
print(json.dumps(res, indent=1))
