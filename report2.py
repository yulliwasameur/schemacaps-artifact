#!/usr/bin/env python3
"""Rend RESULTATS_v2.md à partir de results/v2_* (aucun chiffre tapé à la main)."""
import csv, json, collections, os
R = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
S = json.load(open(os.path.join(R, "v2_summary.json"))); T = S["totals"]; P = S["per_strate"]
W = json.load(open(os.path.join(R, "v2_witness_summary.json")))
TM = json.load(open(os.path.join(R, "v2_timing.json")))
rows = list(csv.DictReader(open(os.path.join(R, "v2_changes.csv"))))
sc = [r for r in rows if r["schema_changed"] == "True"]; comp = [r for r in sc if r["compatible"] == "True"]
ks = lambda r: {x.split(":")[0] for x in r["reasons"].split(";") if x}
kc = collections.Counter(k for r in comp for k in ks(r))
core_pk = collections.Counter(r["package"] for r in comp if r["amp_core"] == "True")
pct = lambda a, b: f"{100*a/b:.1f} %"
L = ["# SchemaCaps — résultats du pilote, classement v2 (écarts 8 et 9 ; générés par report2.py)\n",
     "| Strate | Paires | Schémas modifiés | Compatibles | CA noyau | CA strict | Accept-all | Épinglage | Compat | Non-amp |",
     "|---|---|---|---|---|---|---|---|---|---|"]
for name, c in (("A", P["A"]), ("B", P["B"]), ("Total", T)):
    L.append(f"| {name} | {c['pairs']} | {c['schema_changed']} | {c['compatible']} | {c['ca_core']} | {c['ca_strict']} | 0 | "
             f"{c['def_changed']} | {c['rq_compat']} | {c['rq_strict']} |")
L += ["",
      f"- Noyau (argument d'autorité déclaré ajouté ou élargi) : {T['ca_core']} des {T['compatible']} évolutions compatibles ({pct(T['ca_core'], T['compatible'])}) ; "
      "répartition : " + ", ".join(f"{k} ({v})" for k, v in core_pk.most_common()) + ".",
      f"- Strict (définition 1) : {T['ca_strict']} évolutions compatibles. Raisons parmi les compatibles : " + ", ".join(f"{k} {v}" for k, v in kc.most_common()) + ".",
      f"- Ré-approbations : épinglage {T['def_changed']} ; compatibilité {T['rq_compat']} ; non-amplification stricte {T['rq_strict']} "
      f"({pct(T['def_changed']-T['rq_strict'], T['def_changed'])} de moins que l'épinglage) ; noyau seul {T['rq_core']}.",
      f"- Indécis (règle d'amplification) : {T['undecided']}. Outils ajoutés : {T['added']} (dont {T['added_auth']} avec un chemin d'autorité).",
      f"- Témoins sur le noyau : {W['ca_core_witness']} ; contrôle de correction sur les « compatible = oui » : {W['soundness_check_on_compatible_yes']}.",
      f"- Temps de classement d'un outil modifié : médiane {TM['median_ms']} ms, p99 {TM['p99_ms']} ms.",
      "",
      "**Réserve.** Rôles d'autorité par règle lexicale ; validation humaine en cours (176 cas, `agreement.py`)."]
open(os.path.join(os.path.dirname(R), "RESULTATS_v2.md"), "w").write("\n".join(L) + "\n"); print("\n".join(L))
