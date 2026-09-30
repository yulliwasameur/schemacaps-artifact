#!/usr/bin/env python3
"""Rend RESULTATS.md à partir des fichiers de results/ (aucun chiffre tapé à la main)."""
import csv, json, collections, os
R = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
S = json.load(open(os.path.join(R, "summary.json")))
pairs = list(csv.DictReader(open(os.path.join(R, "pairs.csv"))))
ch = list(csv.DictReader(open(os.path.join(R, "changes.csv"))))
wit = list(csv.DictReader(open(os.path.join(R, "witnesses.csv"))))
corpus = json.load(open(os.path.join(os.path.dirname(R), "corpus_versions.json")))
I = lambda x: int(x or 0)
T = S["totals"]; st = S["extraction_status"]
pct = lambda a, b: f"{100*a/b:.1f} %" if b else "—"

def agg(filter_fn):
    c = collections.Counter()
    for p in pairs:
        if not filter_fn(p): continue
        c["pairs"] += 1
        for k in ("def_changed", "desc_only", "schema_changed", "compatible", "incompatible", "compat_undecided", "amplifying",
                  "auth_undecided", "compatible_and_amplifying", "object_opened_only", "added", "removed", "added_with_authority_args",
                  "reapprove_pin", "reapprove_compat", "reapprove_schemacaps"):
            c[k] += I(p.get(k))
        c["pairs_ca"] += I(p.get("compatible_and_amplifying")) > 0
    return c

A = agg(lambda p: p["strate"] == "A"); B = agg(lambda p: p["strate"] == "B"); ALL = agg(lambda p: True)
heavy = {"agent-device", "hostinger-api-mcp"}
SENS = agg(lambda p: p["package"] not in heavy)
pk = collections.Counter(r["package"] for r in ch if r["compatible"] == "True" and r["amplifying"] == "True")
wdedup = {(x["package"], x["from"], x["to"], x["tool"], x["argument"]): x for x in wit}
wf = sum(1 for x in wdedup.values() if x["witness_found"] == "True")
sampled = sum(min(20, len(m["versions"])) for m in corpus.values())
pk_ok = S["packages_with_ok"]

def row(name, c):
    mod = c["def_changed"]
    return (f"| {name} | {c['pairs']} | {mod} | {c['schema_changed']} | {c['compatible']} | {c['amplifying']} | "
            f"**{c['compatible_and_amplifying']}** | {c['pairs_ca']} | {c['added']} ({c['added_with_authority_args']}) | "
            f"{c['reapprove_pin']} | {c['reapprove_compat']} | {c['reapprove_schemacaps']} |")

L = []
L.append("# SchemaCaps — résultats du pilote (générés par report.py)\n")
L.append(f"Corpus : {len(corpus)} paquets ({sum(1 for m in corpus.values() if m['versions'])} avec des versions dans la fenêtre), "
         f"{sum(len(m['versions']) for m in corpus.values())} versions publiées, {sampled} échantillonnées. "
         f"Extraction : {st.get('ok',0)} réussies ({pct(st.get('ok',0), sampled)}), {st.get('no_response',0)} sans réponse, "
         f"{st.get('install_failed',0)} échecs d'installation ; {pk_ok} paquets avec au moins une extraction réussie.\n")
L.append("| Périmètre | Paires | Outils modifiés | Schéma modifié | Compatibles | Amplifiants | Compatibles ET amplifiants | Paires touchées | Outils ajoutés (dont avec argument d'autorité) | Ré-approbations épinglage | Ré-approb. compatibilité | Ré-approb. SchemaCaps |")
L.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
L.append(row("Strate A (officiels)", A)); L.append(row("Strate B (tiers)", B)); L.append(row("Total", ALL))
L.append(row("Sensibilité : sans agent-device ni hostinger", SENS))
L.append("")
L.append(f"- Parmi les {ALL['compatible']} évolutions de schéma compatibles, **{ALL['compatible_and_amplifying']} ({pct(ALL['compatible_and_amplifying'], ALL['compatible'])}) élargissent un argument porteur d'autorité** : la règle de compatibilité les laisse passer sans consentement.")
L.append(f"- La règle de compatibilité laisse aussi entrer {ALL['added']} outils nouveaux, dont {ALL['added_with_authority_args']} avec un argument porteur d'autorité.")
L.append(f"- Sur les outils existants modifiés, l'épinglage demande {ALL['def_changed']} ré-approbations ; SchemaCaps en demande {ALL['amplifying']+ALL['auth_undecided']} (amplifiants + indécis), soit {pct(ALL['def_changed']-(ALL['amplifying']+ALL['auth_undecided']), ALL['def_changed'])} de moins, sans laisser passer d'amplification détectée.")
L.append(f"- {ALL['desc_only']} modifications ne touchent que la description ou le titre : l'épinglage les compte, la non-amplification les laisse passer (hors portée : injection par description).")
cd = sum(1 for r in ch if r["compatible"] == "True" and r["amplifying"] != "True" and "constraint_dropped" in (r["reasons"] or ""))
L.append(f"- Borne haute : {cd} autres évolutions compatibles retirent la déclaration d'un argument porteur d'autorité d'un objet resté ouvert (effet serveur inconnu, écart n° 7) ; non comptées ci-dessus.")
cs = json.load(open(os.path.join(R, "compat_second_summary.json"))) if os.path.exists(os.path.join(R, "compat_second_summary.json")) else {}
if cs: L.append(f"- Second vérificateur sur les compatibilités indécises : {cs.get('incompatible_witness',0)} incompatibles prouvées par contre-exemple, {cs.get('no_counterexample',0)} sans contre-exemple trouvé.")
L.append(f"- Compatibilité indécidée par jsonsubschema : {ALL['compat_undecided']} cas ; rôle d'autorité indécis : {ALL['auth_undecided']}.")
L.append(f"- Vérification indépendante : {len(wdedup)} arguments élargis, {wf} avec une valeur témoin concrète (admise par la nouvelle version, refusée par l'ancienne).")
L.append(f"- Concentration : les compatibles-et-amplifiants se répartissent sur {len(pk)} paquets : " + ", ".join(f"{k} ({v})" for k, v in pk.most_common()) + ".")
L.append("\n**Réserve majeure.** Les rôles « porteur d'autorité » viennent d'une règle lexicale provisoire ; les arguments en cause sont listés dans `ANNOTATION_roles_a_valider.csv` pour double annotation humaine. Aucun chiffre ne doit entrer dans le papier avant cette validation.")
open(os.path.join(os.path.dirname(R), "RESULTATS.md"), "w").write("\n".join(L) + "\n")
print("\n".join(L))
