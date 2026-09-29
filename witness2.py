#!/usr/bin/env python3
"""Témoins v2 (écart n° 8).
(1) Pour chaque changement compatible ET amplifiant (règle « core » : nouvel argument d'autorité sur objet fermé,
    domaine élargi), cherche un APPEL COMPLET admis par la nouvelle version, refusé par l'ancienne, et qui porte
    l'argument en cause. Sentinelle explicite pour « non trouvé » (corrige le bogue v1 où le témoin null était perdu).
(2) Contrôle de correction du vérificateur : pour chaque « compatible = oui » de jsonsubschema, cherche un appel
    admis par l'ancienne version et refusé par la nouvelle. Tout contre-exemple contredirait la correction revendiquée.
Produit results/v2_witnesses.csv et results/v2_witness_summary.json."""
import csv, json, os, warnings, collections
warnings.filterwarnings("ignore")
import jsonschema
from hypothesis import given, settings, HealthCheck
from hypothesis_jsonschema import from_schema
from classify import resolve_local_refs, clean
from witness import load
NF = object()

def get(x, path):
    cur = x
    for seg in path.split("."):
        if seg.endswith("[]"):
            seg = seg[:-2]
            if not isinstance(cur, dict) or not isinstance(cur.get(seg), list) or not cur[seg]: return NF
            cur = cur[seg][0]
        else:
            if not isinstance(cur, dict) or seg not in cur: return NF
            cur = cur[seg]
    return cur

def search(gen_schema, keep, n=150):
    found = []
    @settings(max_examples=n, suppress_health_check=list(HealthCheck), database=None, deadline=None)
    @given(from_schema(gen_schema))
    def t(x):
        if not found and keep(x): found.append(x)
    try: t()
    except Exception as e: return ("error", type(e).__name__)
    return ("found", found[0]) if found else ("not_found", None)

def schemas(r):
    o = [t for t in load(r["package"], r["from"])["tools"] if t["name"] == r["tool"]][0]
    n = [t for t in load(r["package"], r["to"])["tools"] if t["name"] == r["tool"]][0]
    return clean(resolve_local_refs(o.get("inputSchema") or {})), clean(resolve_local_refs(n.get("inputSchema") or {}))

rows = [r for r in csv.DictReader(open("results/v2_changes.csv")) if r["schema_changed"] == "True"]
out, st = [], collections.Counter()
for r in rows:
    if not (r["compatible"] == "True" and r["amp_core"] == "True"): continue
    so, sn = schemas(r); vo = jsonschema.validators.validator_for(so)(so)
    for reason in r["reasons"].split(";"):
        k, _, p = reason.partition(":")
        if k not in ("new_authority_arg", "widened"): continue
        verdict, w = search(sn, lambda x, p=p: get(x, p) is not NF and not vo.is_valid(x))
        st[(k, verdict)] += 1
        out.append({"package": r["package"], "from": r["from"], "to": r["to"], "tool": r["tool"], "kind": k, "path": p,
                    "verdict": verdict, "witness": json.dumps(w, ensure_ascii=False)[:200] if verdict == "found" else ""})
snd = collections.Counter(); bad = []
for r in rows:
    if r["compatible"] != "True": continue
    so, sn = schemas(r); vn = jsonschema.validators.validator_for(sn)(sn)
    verdict, w = search(so, lambda x: not vn.is_valid(x), n=80)
    snd[verdict] += 1
    if verdict == "found": bad.append({**{k: r[k] for k in ("package", "from", "to", "tool")}, "counterexample": json.dumps(w)[:200]})
with open("results/v2_witnesses.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(out[0])); w.writeheader(); w.writerows(out)
summ = {"ca_core_witness": {f"{a}:{b}": c for (a, b), c in st.items()}, "soundness_check_on_compatible_yes": dict(snd),
        "soundness_counterexamples": bad}
json.dump(summ, open("results/v2_witness_summary.json", "w"), indent=1)
print(json.dumps(summ, indent=1)[:1500])
