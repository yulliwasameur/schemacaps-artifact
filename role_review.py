#!/usr/bin/env python3
"""Recompte de la revue des rôles (un auteur) à partir de la feuille remplie, et du sous-ensemble confirmé.
Produit results/role_review.json. NB : la revue a porté sur les 65 (paquet, argument) signalés par le PREMIER
classifieur (classify.py) ; le pilote rapporté utilise classify2.py. La thèse ne dépend pas de ces étiquettes."""
import openpyxl, json, csv, sys, collections
SHEET = sys.argv[1]  # path to a filled review sheet
rows = list(openpyxl.load_workbook(SHEET, data_only=True)["Annotation"].iter_rows(values_only=True))
h = next(i for i, r in enumerate(rows) if r and r[0] == "ID cas")
dec = collections.Counter(); labels = {}
for r in rows[h+1:]:
    if not r or not r[0]: continue
    d = (str(r[6]).strip().lower() if r[6] else ""); dec[d] += 1; labels[(r[1], r[4])] = d
# confirmed core change-instances in the v2 pipeline whose argument the author judged authority-bearing
yes = {k for k, v in labels.items() if v == "oui"}
comp = [r for r in csv.DictReader(open("results/v2_changes.csv"))
        if r["schema_changed"] == "True" and r["compatible"] == "True" and r["amp_core"] == "True"]
rows_hit = 0; args = set()
for r in comp:
    hit = False
    for x in r["reasons"].split(";"):
        k, _, p = x.partition(":")
        if k in ("new_authority_arg", "widened") and (r["package"], p) in yes:
            args.add((r["package"], p)); hit = True
    rows_hit += hit
res = {"reviewed_pairs_first_classifier": sum(dec.values()), "authority": dec.get("oui", 0),
       "not_authority": dec.get("non", 0), "uncertain": dec.get("incertain", 0),
       "confirmed_compatible_changes_v2": rows_hit, "confirmed_arguments_v2": len(args)}
json.dump(res, open("results/role_review.json", "w"), indent=1, ensure_ascii=False)
print(json.dumps(res, indent=1))
