#!/usr/bin/env python3
"""Accord inter-annotateurs et chiffres validés (feuilles v2, 176 cas : 44 signalés par la règle lexicale,
132 arguments ajoutés non signalés, mélangés sans indication).
Usage : python3 agreement.py A1.xlsx A2.xlsx [arbitrage.xlsx]
Produit results/agreement.json : kappa de Cohen, précision et rappel de la règle lexicale, nombre validé K de
changements compatibles et amplifiants (bas : les deux « oui » ; haut : au moins un « oui »)."""
import sys, csv, json, collections, openpyxl

def load(p):
    ws = openpyxl.load_workbook(p, data_only=True)["Annotation"]
    rows = list(ws.iter_rows(values_only=True))
    h = next(i for i, r in enumerate(rows) if r and r[0] == "ID cas")
    return {r[0]: (str(r[6]).strip().lower() if r[6] else "") for r in rows[h + 1:] if r and r[0]}

key = {k["id"]: k for k in json.load(open("results/v2_annotation_key.json"))}
a, b = load(sys.argv[1]), load(sys.argv[2])
arb = load(sys.argv[3]) if len(sys.argv) > 3 else {}
ids = sorted(key)
missing = [i for i in ids if a.get(i) not in ("oui", "non", "incertain") or b.get(i) not in ("oui", "non", "incertain")]
if missing:
    print(f"ANNOTATION INCOMPLÈTE : {len(missing)} cas sur {len(ids)} sans décision valide chez l'un des annotateurs.")
    sys.exit(1)
n = len(ids); labs = ("oui", "non", "incertain")
po = sum(a[i] == b[i] for i in ids) / n
ca, cb = collections.Counter(a[i] for i in ids), collections.Counter(b[i] for i in ids)
pe = sum(ca[l] * cb[l] for l in labs) / n ** 2
kappa = (po - pe) / (1 - pe) if pe < 1 else 1.0
dis = [i for i in ids if a[i] != b[i]]
final = {i: (a[i] if a[i] == b[i] else arb.get(i, "")) for i in ids}          # consensus, sinon arbitrage
F = [i for i in ids if key[i]["group"] == "F"]; U = [i for i in ids if key[i]["group"] == "U"]
yes = {i for i in ids if final[i] == "oui"}
prec = len(yes & set(F)) / len(F); rec = len(yes & set(F)) / len(yes) if yes else float("nan")
both = {(key[i]["pkg"], key[i]["path"]) for i in ids if a[i] == b[i] == "oui"}
one = {(key[i]["pkg"], key[i]["path"]) for i in ids if "oui" in (a[i], b[i])}
fin = {(key[i]["pkg"], key[i]["path"]) for i in yes}
STRICT = ("new_authority_arg", "widened", "became_optional", "default_changed", "constraint_dropped", "nullable_on_required")
rows = [r for r in csv.DictReader(open("results/v2_changes.csv")) if r["schema_changed"] == "True" and r["compatible"] == "True"]
def paths(r, kinds): return {p for k, _, p in (x.partition(":") for x in r["reasons"].split(";")) if k in kinds}
def count(S, kinds): return sum(1 for r in rows if any((r["package"], p) in S for p in paths(r, kinds)))
# arguments non signalés jugés porteurs d'autorité : ajoutés sur objet fermé dans une évolution compatible
from classify2 import walk, closed_ancestor, leaf, is_authority
from classify import resolve_local_refs
from witness import load as ld
def missed(S, kinds=None):
    # Écart n° 11 (audit du 14/11/2026) : un changement compte s'il ajoute un argument d'autorité non signalé et
    # n'est pas déjà compté par un argument confirmé des « kinds » visés ; la version relue excluait à tort tout
    # changement portant une autre raison STRICT (3 changements perdus pour K cœur).
    kinds = STRICT if kinds is None else kinds
    c = 0
    for r in rows:
        o = [t for t in ld(r["package"], r["from"])["tools"] if t["name"] == r["tool"]][0]
        nw = [t for t in ld(r["package"], r["to"])["tools"] if t["name"] == r["tool"]][0]
        do, oo, _ = walk(resolve_local_refs(o.get("inputSchema") or {}))[:3]; dn, _, _ = walk(resolve_local_refs(nw.get("inputSchema") or {}))[:3]
        new = {p for p in set(dn) - set(do) if closed_ancestor(p, oo, do) and not is_authority(leaf(p))}
        if any((r["package"], p) in S for p in new) and not any((r["package"], p) in S for p in paths(r, kinds)):
            c += 1
    return c
def kappa_of(pairs, labs_):
    m = len(pairs)
    if not m: return float("nan")
    p_o = sum(x == y for x, y in pairs) / m
    c1, c2 = collections.Counter(x for x, _ in pairs), collections.Counter(y for _, y in pairs)
    p_e = sum(c1[l] * c2[l] for l in labs_) / m ** 2
    return (p_o - p_e) / (1 - p_e) if p_e < 1 else 1.0
coll = lambda v: "non" if v == "incertain" else v
kappa_collapsed = kappa_of([(coll(a[i]), coll(b[i])) for i in ids], ("oui", "non"))
sure = [i for i in ids if "incertain" not in (a[i], b[i])]
kappa_excluding_unsure = kappa_of([(a[i], b[i]) for i in sure], ("oui", "non"))
hard = [i for i in dis if "incertain" not in (a[i], b[i])]
res = {"n": n, "percent_agreement": round(po, 3), "cohen_kappa": round(kappa, 3),
       "cohen_kappa_unsure_as_no": round(kappa_collapsed, 3), "cohen_kappa_excluding_unsure": round(kappa_excluding_unsure, 3),
       "n_excluding_unsure": len(sure), "hard_disagreements": hard, "unsure_counts": {"A1": ca["incertain"], "A2": cb["incertain"]},
       "flagged": len(F), "unflagged": len(U), "gold_yes": len(yes), "disagreements": dis,
       "unresolved_disagreements": [i for i in dis if not arb.get(i)],
       "lexical_rule_precision": round(prec, 3), "lexical_rule_recall": round(rec, 3),
       "K_final_core": count(fin, ("new_authority_arg", "widened")) + missed(fin, ("new_authority_arg", "widened")),
       "K_final_core_flagged": count(fin, ("new_authority_arg", "widened")),
       "K_final_core_missed": missed(fin, ("new_authority_arg", "widened")),
       "K_final_core_reviewed_version": count(fin, ("new_authority_arg", "widened")) + missed(fin),
       "K_final_strict_args": count(fin, STRICT) + missed(fin),
       "K_low_both_yes": count(both, ("new_authority_arg", "widened")) + missed(both, ("new_authority_arg", "widened")),
       "K_high_one_yes": count(one, ("new_authority_arg", "widened")) + missed(one, ("new_authority_arg", "widened")),
       "compatible_total": len(rows)}
json.dump(res, open("results/agreement.json", "w"), indent=1, ensure_ascii=False)
print(json.dumps(res, indent=1, ensure_ascii=False))
