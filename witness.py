#!/usr/bin/env python3
"""Vérification indépendante : pour chaque argument jugé élargi, cherche une valeur témoin admise par la nouvelle
version et refusée par l'ancienne (hypothesis-jsonschema + jsonschema). Produit results/witnesses.csv."""
import csv, json, os, glob, re, warnings
warnings.filterwarnings("ignore")
import jsonschema
from hypothesis import given, settings, HealthCheck, strategies as st
from hypothesis_jsonschema import from_schema
from classify import resolve_local_refs, props, clean

ROOT = os.path.dirname(os.path.abspath(__file__))

def load(pkg, ver):
    safe = pkg.replace("/", "__").replace("@", "")
    return json.load(open(os.path.join(ROOT, "raw", f"{safe}@{ver}.json")))

CANDIDATES = [0, -1, 3.5, True, None, "", "x", "../../etc/passwd", "/", "http://attacker.example/x",
              "attacker@evil.example", "a" * 5000, [], ["x"], {}, {"x": 1}]

def find_witness(s_new, s_old, tries=300):
    s_new, s_old = clean(s_new), clean(s_old)
    v_new = jsonschema.validators.validator_for(s_new)(s_new) if isinstance(s_new, dict) else None
    v_old = jsonschema.validators.validator_for(s_old)(s_old)
    ok_new = (lambda x: True) if not s_new else (lambda x: v_new.is_valid(x))
    for c in CANDIDATES:
        if ok_new(c) and not v_old.is_valid(c):
            return c
    found = []
    strat = from_schema(s_new) if s_new else st.from_type(object)
    @settings(max_examples=tries, suppress_health_check=list(HealthCheck), database=None, deadline=None)
    @given(strat)
    def t(x):
        if not found and not v_old.is_valid(x):
            found.append(x)
    try:
        t()
    except Exception:
        pass
    return found[0] if found else None

def main():
    rows = list(csv.DictReader(open(os.path.join(ROOT, "results", "changes.csv"))))
    out = []
    for r in rows:
        for reason in (r["reasons"] or "").split(";"):
            if not reason or reason.split(":")[0] not in ("widened", "constraint_dropped"):
                continue
            arg = reason.split(":", 1)[1]
            o = [t for t in load(r["package"], r["from"])["tools"] if t["name"] == r["tool"]][0]
            n = [t for t in load(r["package"], r["to"])["tools"] if t["name"] == r["tool"]][0]
            so, sn = resolve_local_refs(o.get("inputSchema") or {}), resolve_local_refs(n.get("inputSchema") or {})
            s_old = props(so).get(arg, {}); s_new = props(sn).get(arg, {})
            try:
                w = find_witness(s_new, s_old)
            except Exception as e:
                w = None
            out.append({**{k: r[k] for k in ("package", "from", "to", "tool")}, "argument": arg, "kind": reason.split(":")[0],
                        "old_schema": json.dumps(clean(s_old), ensure_ascii=False)[:400],
                        "new_schema": json.dumps(clean(s_new), ensure_ascii=False)[:400],
                        "witness_found": w is not None, "witness": json.dumps(w, ensure_ascii=False)[:200]})
    with open(os.path.join(ROOT, "results", "witnesses.csv"), "w", newline="") as f:
        if out:
            wr = csv.DictWriter(f, fieldnames=list(out[0])); wr.writeheader(); wr.writerows(out)
    print(len(out), "arguments élargis ;", sum(o["witness_found"] for o in out), "avec témoin")

if __name__ == "__main__":
    main()
