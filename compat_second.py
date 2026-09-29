#!/usr/bin/env python3
"""Second vérificateur pour les compatibilités indécises (jsonsubschema en échec) : recherche d'un contre-exemple
(instance valide pour l'ancienne version, invalide pour la nouvelle) par génération hypothesis-jsonschema.
Contre-exemple trouvé = incompatible prouvé ; sinon 'indécis, aucun contre-exemple sur N essais'."""
import csv, json, os, warnings, collections
warnings.filterwarnings("ignore")
import jsonschema
from hypothesis import given, settings, HealthCheck
from hypothesis_jsonschema import from_schema
from classify import resolve_local_refs, clean
from witness import load

N = 120

def counterexample(s_old, s_new):
    v_new = jsonschema.validators.validator_for(s_new)(s_new)
    found = []
    @settings(max_examples=N, suppress_health_check=list(HealthCheck), database=None, deadline=None)
    @given(from_schema(s_old))
    def t(x):
        if not found and not v_new.is_valid(x):
            found.append(x)
    t()
    return found[0] if found else None

rows = list(csv.DictReader(open("results/changes.csv")))
out, stat = [], collections.Counter()
for r in rows:
    if r["schema_changed"] != "True" or r["compatible"] not in ("", "None"):
        continue
    o = [t for t in load(r["package"], r["from"])["tools"] if t["name"] == r["tool"]][0]
    n = [t for t in load(r["package"], r["to"])["tools"] if t["name"] == r["tool"]][0]
    so, sn = clean(resolve_local_refs(o.get("inputSchema") or {})), clean(resolve_local_refs(n.get("inputSchema") or {}))
    try:
        ce = counterexample(so, sn); verdict = "incompatible_witness" if ce is not None else "no_counterexample"
    except Exception as e:
        ce, verdict = None, f"generator_failed:{type(e).__name__}"
    stat[verdict.split(":")[0]] += 1
    out.append({**{k: r[k] for k in ("package", "from", "to", "tool", "amplifying")}, "verdict": verdict,
                "counterexample": json.dumps(ce, ensure_ascii=False)[:200] if ce is not None else ""})
with open("results/compat_second.csv", "w", newline="") as f:
    if out:
        w = csv.DictWriter(f, fieldnames=list(out[0])); w.writeheader(); w.writerows(out)
json.dump(dict(stat), open("results/compat_second_summary.json", "w"), indent=1)
print(len(out), dict(stat))
