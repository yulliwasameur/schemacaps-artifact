#!/usr/bin/env python3
"""Table 3 of the paper (revision 2): schema changes on the two axes, counted by script for both labellings.

Rows count CHANGED TOOLS (not reasons) among the compatible changes whose reasons include the kind, under the
lexical labelling (v2_changes.csv) and the label-free labelling (free_changes.csv); plus, over ALL schema changes,
the strict narrowings (the guarded checker proves new ⊆ old and not old ⊆ new) and raised tool hints.
Output: results/taxonomy.json
"""
import csv, json, warnings
warnings.filterwarnings("ignore")
from classify2 import sub, norm_schema
from classify import resolve_local_refs
from witness import load

KINDS = ["new_authority_arg", "widened", "became_optional", "constraint_dropped", "object_opened",
         "object_introduced_open", "shape_changed", "default_changed", "nullable", "nullable_on_required"]


def counts(path):
    rows = [r for r in csv.DictReader(open(path)) if r["schema_changed"] == "True" and r["compatible"] == "True"]
    kinds = lambda r: {x.split(":")[0] for x in r["reasons"].split(";") if x}
    return {k: sum(1 for r in rows if k in kinds(r)) for k in KINDS}, len(rows)


lex, n_comp = counts("results/v2_changes.csv")
free, _ = counts("results/free_changes.csv")
allrows = [r for r in csv.DictReader(open("results/v2_changes.csv")) if r["schema_changed"] == "True"]
narrow = undecided = 0
for r in allrows:
    o = [t for t in load(r["package"], r["from"])["tools"] if t["name"] == r["tool"]][0]
    n = [t for t in load(r["package"], r["to"])["tools"] if t["name"] == r["tool"]][0]
    so = resolve_local_refs(norm_schema(o.get("inputSchema"))); sn = resolve_local_refs(norm_schema(n.get("inputSchema")))
    a, b = sub(sn, so), (r["compatible"] == "True")
    if a is True and not b:
        narrow += 1
    elif a is None:
        undecided += 1
hints = sum(1 for r in csv.DictReader(open("results/v2_changes.csv")) if r.get("hints"))
res = {"compatible_changes": n_comp, "lexical": lex, "label_free": free, "strict_narrowings_all_changes": narrow,
       "narrowing_check_undecided": undecided, "tools_with_raised_hint": hints}
json.dump(res, open("results/taxonomy.json", "w"), indent=1)
print(json.dumps(res, indent=1))
