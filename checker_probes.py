#!/usr/bin/env python3
"""Soundness probes of the inclusion checker (tests/test_checker.py PROBES): raw jsonsubschema vs the guarded checker.
A verdict is unsound when it claims a ⊆ b although a counterexample (valid under a, invalid under b) is found.
Output: results/checker_probes.json"""
import json, sys, os, warnings
warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "tests"))
from test_checker import PROBES, _has_cex
from classify import sub as raw
from classify2 import sub as guarded
rows = []
for name, a, b in PROBES:
    c = _has_cex(a, b)
    rows.append({"probe": name, "counterexample_exists": c, "raw": raw(a, b), "guarded": guarded(a, b)})
res = {"probes": len(rows), "raw_unsound": [r["probe"] for r in rows if r["raw"] is True and r["counterexample_exists"]],
       "guarded_unsound": [r["probe"] for r in rows if r["guarded"] is True and r["counterexample_exists"]], "rows": rows}
json.dump(res, open("results/checker_probes.json", "w"), indent=1)
print(json.dumps({k: v for k, v in res.items() if k != "rows"}, indent=1))
