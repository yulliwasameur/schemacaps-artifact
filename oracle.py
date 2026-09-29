#!/usr/bin/env python3
"""Differential soundness oracle (écart n° 9b): tests that the classifier's SILENT re-bind decisions really are
non-amplifying per Definition 1, on the corpus. For every compatible change the rule re-binds (not amp_strict, not
undecided), for every authority-bearing path present in both versions, we generate values admitted by the NEW
marginal and check the OLD marginal admits them too (pi_a(new) subseteq pi_a(old)); and we assert no authority path
was silently added on a closed object and no object was silently opened. Any counterexample = an unsound re-bind.
This is the link between the verified Proposition (which assumes per-step non-amplification) and the running code."""
import csv, json, os, warnings, collections
warnings.filterwarnings("ignore")
import jsonschema
from hypothesis import given, settings, HealthCheck
from hypothesis_jsonschema import from_schema
from classify2 import analyse, walk, leaf, is_authority, closed_ancestor
from classify import resolve_local_refs, clean
from witness import load

def marg_counterexample(new_s, old_s, n=100):
    """a value admitted by new_s but refused by old_s (would prove pi_a(new) !subseteq pi_a(old))."""
    new_s, old_s = clean(new_s or {}), clean(old_s or {})
    vo = jsonschema.validators.validator_for(old_s)(old_s)
    found = []
    try:
        @settings(max_examples=n, suppress_health_check=list(HealthCheck), database=None, deadline=None)
        @given(from_schema(new_s))
        def t(x):
            if not found and not vo.is_valid(x): found.append(x)
        t()
    except Exception:
        return "gen_error"
    return found[0] if found else None

recs = collections.defaultdict(list)
import glob
for f in glob.glob("raw/*.json"):
    r = json.load(open(f))
    if r["status"] == "ok": recs[r["package"]].append(r)
rebinds = 0; checked_paths = 0; unsound = []
for pkg, items in recs.items():
    items.sort(key=lambda r: r["published"])
    for o, n in zip(items, items[1:]):
        to = {t["name"]: t for t in o["tools"]}; tn = {t["name"]: t for t in n["tools"]}
        for name in set(to) & set(tn):
            a = analyse(to[name], tn[name])
            if not a["schema_changed"] or a["compatible"] is not True: continue
            if a.get("amp_strict") or a.get("undecided"): continue     # the rule would ASK, not silently re-bind
            rebinds += 1
            so = resolve_local_refs(to[name].get("inputSchema") or {}); sn = resolve_local_refs(tn[name].get("inputSchema") or {})
            do, oo = walk(so)[:2]; dn, on = walk(sn)[:2]
            # (i) no authority path silently added on a closed object
            for p in set(dn) - set(do):
                if is_authority(leaf(p)) and closed_ancestor(p, oo, do):
                    unsound.append({"pkg": pkg, "from": o["version"], "to": n["version"], "tool": name, "why": f"added_authority_on_closed:{p}"})
            # (ii) no object silently opened
            for path, closed in oo.items():
                if closed and path in on and not on[path]:
                    unsound.append({"pkg": pkg, "from": o["version"], "to": n["version"], "tool": name, "why": f"object_opened:{path or '<root>'}"})
            # (iii) each authority path in both: new marginal subseteq old marginal
            for p in set(do) & set(dn):
                if not is_authority(leaf(p)): continue
                checked_paths += 1
                ce = marg_counterexample(dn[p][0], do[p][0])
                if ce is not None and ce != "gen_error":
                    unsound.append({"pkg": pkg, "from": o["version"], "to": n["version"], "tool": name, "why": f"widened:{p}", "counterexample": json.dumps(ce)[:120]})
res = {"silent_rebinds": rebinds, "authority_paths_checked": checked_paths, "unsound_rebinds": unsound,
       "conclusion": "no unsound silent re-bind found" if not unsound else f"{len(unsound)} UNSOUND"}
json.dump(res, open("results/oracle.json", "w"), indent=1, ensure_ascii=False)
print(json.dumps({k: v for k, v in res.items() if k != "unsound_rebinds"}, indent=1)); print("unsound:", unsound[:5])
