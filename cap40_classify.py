#!/usr/bin/env python3
"""Sensibilité au plafond : reclasse agent-device et @sentry/mcp-server avec 40 releases (raw40/) et compare
le nombre de cas compatibles-et-amplifiants (noyau) au pilote à 20 releases."""
import json, glob, os, collections, csv
import classify2
from classify import resolve_local_refs
ROOT=os.path.dirname(os.path.abspath(__file__))
def recs(d,pkgs):
    out=collections.defaultdict(list)
    for f in glob.glob(os.path.join(ROOT,d,"*.json")):
        r=json.load(open(f))
        if r["status"]=="ok" and r["package"] in pkgs: out[r["package"]].append(r)
    return out
def core(rs):
    n=0
    for pkg,items in rs.items():
        items.sort(key=lambda r:r["published"])
        for o,nx in zip(items,items[1:]):
            to={t["name"]:t for t in o["tools"]}; tn={t["name"]:t for t in nx["tools"]}
            for name in set(to)&set(tn):
                a=classify2.analyse(to[name],tn[name])
                if a["schema_changed"] and a["compatible"] is True and a.get("amp_core"): n+=1
    return n
pkgs=["agent-device","@sentry/mcp-server"]
r20=recs("raw",pkgs); r40=recs("raw40",pkgs)
res={"cap20":{p:core({p:r20[p]}) for p in pkgs},"cap40":{p:core({p:r40[p]}) for p in pkgs},
     "n20":{p:len(r20[p]) for p in pkgs},"n40":{p:len(r40[p]) for p in pkgs}}
json.dump(res,open("results/cap_sensitivity.json","w"),indent=1); print(json.dumps(res,indent=1))
