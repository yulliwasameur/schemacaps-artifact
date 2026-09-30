#!/usr/bin/env python3
"""Classement v2 (écart n° 8, après relecture adversariale du 29/09/2026).
Corrige classify.py sur les points relevés : chemins imbriqués (propriétés et items), `required` (valeur absente),
valeurs par défaut (valeur effective), ouverture d'objet (coordonnée ⋆), retrait d'une déclaration sur objet ouvert,
objets sans argument (bogue declared_old), null traité comme absent, précondition « produit » (combinateurs dans
l'ANCIEN schéma sur le chemin d'un argument d'autorité => indécis), indices de l'outil (annotations MCP).
Produit results/v2_changes.csv, results/v2_pairs.csv, results/v2_summary.json. classify.py (v1) est conservé tel quel."""
import json, glob, os, csv, collections, copy
from classify import is_authority, sub, resolve_local_refs, clean, h, ROOT

RES = os.path.join(ROOT, "results")
COMB = ("anyOf", "oneOf", "allOf", "if", "not", "dependentRequired", "dependentSchemas", "dependencies",
        "minProperties", "maxProperties", "propertyNames", "patternProperties")
BRANCH = ("anyOf", "oneOf", "allOf")
STRICT = ("new_authority_arg", "widened", "became_optional", "default_changed", "constraint_dropped",
          "object_opened", "object_introduced_open", "nullable_on_required", "nullable", "hint_raised")
CORE = ("new_authority_arg", "widened")

def walk(s, path="", out=None, objs=None, comb=None, aps=None, branches=False, refs=None):
    """Déclarations par chemin : {path: (schema, required, default)} ; objets : {path: closed} ; combinateurs : {path} ;
    aps : additionalProperties typés ; refs : chemins portant un $ref non résolu. Avec branches=True (nouvelle version),
    descend dans anyOf/oneOf/allOf et prend l'union des branches (sur-approximation, donc correcte)."""
    out = {} if out is None else out; objs = {} if objs is None else objs; comb = set() if comb is None else comb
    aps = {} if aps is None else aps; refs = set() if refs is None else refs
    if not isinstance(s, dict):
        return out, objs, comb, aps, refs
    if "$ref" in s:
        refs.add(path)
    if any(k in s for k in COMB):
        comb.add(path)
    if "properties" in s or s.get("type") == "object" or "additionalProperties" in s:
        ap = s.get("additionalProperties", True)
        closed = ap is False and not s.get("patternProperties")
        objs[path] = objs.get(path, True) and closed if path in objs else closed
        if isinstance(ap, dict): aps[path] = ap
        req = set(s.get("required") or [])
        for name, sub_s in (s.get("properties") or {}).items():
            p = f"{path}.{name}" if path else name
            d = sub_s.get("default") if isinstance(sub_s, dict) else None
            ss = sub_s if isinstance(sub_s, dict) else {}
            if p in out:                                    # déclaré dans plusieurs branches : union
                s0, r0, d0 = out[p]
                out[p] = ({"anyOf": [s0, ss]}, r0 and name in req, d0 if d0 == d else "__multi__")
            else:
                out[p] = (ss, name in req, d)
            walk(sub_s, p, out, objs, comb, aps, branches, refs)
    it = s.get("items")
    if isinstance(it, dict):
        walk(it, f"{path}[]", out, objs, comb, aps, branches, refs)
    if branches:
        for k in BRANCH:
            brs = [b for b in (s.get(k) or []) if isinstance(b, dict)]
            seen = []
            for b in brs:
                if ("properties" in b or b.get("type") == "object") and path not in objs:
                    objs[path] = False
                before = set(out)
                walk(b, path, out, objs, comb, aps, branches, refs)
                pre = f"{path}." if path else ""
                seen.append({q for q in (b.get("properties") or {})})
            if k != "allOf" and seen:                      # absent d'une branche => la valeur peut manquer
                every = set.intersection(*seen)
                for name in set.union(*seen) - every:
                    q = f"{path}.{name}" if path else name
                    if q in out:
                        s0, _, d0 = out[q]; out[q] = (s0, False, d0)
    return out, objs, comb, aps, refs

def leaf(p): return p.split(".")[-1].replace("[]", "")
def parent(p): return p.rsplit(".", 1)[0] if "." in p else ""
def ancestors(p):
    a, cur = {""}, ""
    for seg in p.split(".")[:-1]:
        cur = f"{cur}.{seg}" if cur else seg
        a.add(cur); a.add(cur[:-2] if cur.endswith("[]") else cur)
    return a

def strip_null(s):
    s = copy.deepcopy(s)
    t = s.get("type")
    if isinstance(t, list) and "null" in t:
        t = [x for x in t if x != "null"]; s["type"] = t[0] if len(t) == 1 else t
    for k in ("anyOf", "oneOf"):
        if isinstance(s.get(k), list):
            br = [b for b in s[k] if b != {"type": "null"}]
            if len(br) == 1 and len(s) == 1:
                return br[0]
            s[k] = br
    return s

def admits_null(s):
    t = s.get("type")
    return (t == "null" or (isinstance(t, list) and "null" in t)
            or any(b == {"type": "null"} for k in ("anyOf", "oneOf") for b in (s.get(k) or [])))

def closed_ancestor(p, objs_old, decl_old):
    """Le plus proche ancêtre objet existant dans l'ancienne version est-il fermé ?"""
    cur = parent(p)
    while True:
        if cur in objs_old:
            return objs_old[cur]
        if cur == "":
            return False
        cur = parent(cur) if not cur.endswith("[]") else cur[:-2]

def hint_raised(o, n):
    ao, an = o.get("annotations") or {}, n.get("annotations") or {}
    r = []
    if ao.get("readOnlyHint") is True and an.get("readOnlyHint") is not True: r.append("readOnly_dropped")
    if ao.get("destructiveHint") is False and an.get("destructiveHint") is not False: r.append("destructive_raised")
    if ao.get("openWorldHint") is False and an.get("openWorldHint") is not False: r.append("openWorld_raised")
    return r

def analyse(o, n):
    so, sn = resolve_local_refs(o.get("inputSchema") or {}), resolve_local_refs(n.get("inputSchema") or {})
    res = {"schema_changed": h(so) != h(sn),
           "desc_changed": (o.get("description") or "") != (n.get("description") or ""),
           "title_changed": (o.get("title") or "") != (n.get("title") or ""),
           "annot_changed": (o.get("annotations") or {}) != (n.get("annotations") or {}),
           "output_changed": h(o.get("outputSchema") or {}) != h(n.get("outputSchema") or {}),
           "hints": hint_raised(o, n), "reasons": [], "undecided": False, "compatible": True}
    if not res["schema_changed"]:
        res.update(reasons=[f"hint_raised:{x}" for x in res["hints"]], amp_core=False, amp_strict=bool(res["hints"]))
        return res
    res["compatible"] = sub(so, sn)
    do, oo, co, apo, ro = walk(so); dn, on, _, apn, rn = walk(sn, branches=True)
    reasons, und = [f"hint_raised:{x}" for x in res["hints"]], False
    if ro or rn:                                            # $ref non résolu : on ne sait pas ce qu'il déclare
        und = True; reasons.append("unresolved_ref")
    auth = sorted({p for p in set(do) | set(dn) if is_authority(leaf(p))})
    for p in auth:
        if any(a in co for a in ancestors(p)):              # précondition produit violée dans l'ancien schéma
            und = True; reasons.append(f"cross_constraint:{p}"); continue
        if p in do and p in dn:
            (s0, r0, d0), (s1, r1, d1) = do[p], dn[p]
            c0, c1 = clean(s0), clean(s1)
            if h(c0) != h(c1):
                r = sub(c1, c0)
                if r is False and admits_null(c1) and not admits_null(c0) and sub(strip_null(c1), c0) is True:
                    reasons.append(("nullable_on_required:" if r0 else "nullable:") + p)   # null distinct de l'absence (§2) : conservateur -> demander
                elif r is None:
                    und = True; reasons.append(f"undecided:{p}")
                elif r is False:
                    reasons.append(f"widened:{p}")
            if r0 and not r1:
                reasons.append(f"became_optional:{p}")
            if d1 != d0 and not (d1 is None and d0 is None):
                reasons.append(f"default_changed:{p}")
        elif p in dn:
            reasons.append(("new_authority_arg:" if closed_ancestor(p, oo, do) else "declaration_restored:") + p)
        else:
            par_new_open = not on.get(parent(p), False) if parent(p) in on else not closed_ancestor(p, on, dn)
            reasons.append(("constraint_dropped:" if par_new_open else "removed:") + p)
    for path, closed in oo.items():
        if path not in on:
            continue
        if closed and not on[path]:
            reasons.append(f"object_opened:{path or '<root>'}")
        elif not closed and not on[path] and path in apo:   # ⋆ typé : comparer les schémas des champs non déclarés
            r = sub(clean(apn[path]), clean(apo[path])) if path in apn else False
            if r is False: reasons.append(f"object_opened:{path or '<root>'}")
            elif r is None: und = True; reasons.append(f"undecided_star:{path or '<root>'}")
    for path, closed in on.items():                         # objet nouveau et ouvert sous un ancêtre fermé : nouveau ⋆
        if not closed and path not in oo and path != "" and closed_ancestor(path + ".\x00", oo, do):
            reasons.append(f"object_introduced_open:{path}")
    kinds = {r.split(":")[0] for r in reasons}
    res.update(reasons=reasons,
               amp_core=bool(kinds & set(CORE)), amp_strict=bool(kinds & set(STRICT)),
               undecided=und and not (kinds & set(STRICT)))
    return res

def main():
    recs = collections.defaultdict(list)
    for f in glob.glob(os.path.join(ROOT, "raw", "*.json")):
        r = json.load(open(f))
        if r["status"] == "ok": recs[r["package"]].append(r)
    rows, prow = [], []
    for pkg, rs in sorted(recs.items()):
        rs.sort(key=lambda r: r["published"])
        for o, n in zip(rs, rs[1:]):
            to = {t["name"]: t for t in o.get("tools", [])}; tn = {t["name"]: t for t in n.get("tools", [])}
            added = sorted(set(tn) - set(to))
            st = collections.Counter(added=len(added), removed=len(set(to) - set(tn)))
            st["added_auth"] = sum(1 for t in added if any(is_authority(leaf(p)) for p in walk(resolve_local_refs(tn[t].get("inputSchema") or {}))[0]))
            for name in sorted(set(to) & set(tn)):
                a = analyse(to[name], tn[name])
                d = a["schema_changed"] or a["desc_changed"] or a["title_changed"]
                if d: st["def_changed"] += 1
                if a["annot_changed"]: st["annot_changed"] += 1
                if a["hints"]: st["hint_raised"] += 1
                if a["output_changed"]: st["output_changed"] += 1
                if not (d or a["annot_changed"] or a["output_changed"]):
                    continue
                sc = a["schema_changed"]
                if sc:
                    st["schema_changed"] += 1
                    st["compatible"] += a["compatible"] is True
                    st["incompatible"] += a["compatible"] is False
                    st["compat_undecided"] += a["compatible"] is None
                    st["amp_core"] += a["amp_core"]; st["amp_strict"] += a["amp_strict"]
                    st["undecided"] += a["undecided"]
                    st["ca_core"] += a["compatible"] is True and a["amp_core"]
                    st["ca_strict"] += a["compatible"] is True and a["amp_strict"]
                    st["rq_compat"] += a["compatible"] is not True
                    st["rq_core"] += a["amp_core"] or a["undecided"]
                    st["rq_strict"] += a["amp_strict"] or a["undecided"]
                elif a["hints"]:
                    st["rq_strict"] += 1; st["rq_hint_only"] += 1
                rows.append({"package": pkg, "strate": o["strate"], "from": o["version"], "to": n["version"], "tool": name,
                             "schema_changed": sc, "compatible": a["compatible"] if sc else "", "amp_core": a.get("amp_core", False),
                             "amp_strict": a.get("amp_strict", False), "undecided": a["undecided"], "def_changed": d,
                             "desc_only": d and not sc, "annot_changed": a["annot_changed"], "hints": ";".join(a["hints"]),
                             "reasons": ";".join(a["reasons"])})
            prow.append({"package": pkg, "strate": o["strate"], "from": o["version"], "to": n["version"],
                         "gap": n["index_in_window"] - o["index_in_window"], **st})
    for name, rr in (("v2_changes.csv", rows), ("v2_pairs.csv", prow)):
        keys = list(dict.fromkeys(k for r in rr for k in r))
        with open(os.path.join(RES, name), "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=keys, restval=0); w.writeheader(); w.writerows(rr)
    tot = collections.Counter(); per = collections.defaultdict(collections.Counter)
    for p in prow:
        for k, v in p.items():
            if isinstance(v, int) and k != "gap": tot[k] += v; per[p["strate"]][k] += v
    tot["pairs"] = len(prow)
    for s in per: per[s]["pairs"] = sum(1 for p in prow if p["strate"] == s)
    json.dump({"totals": dict(tot), "per_strate": {k: dict(v) for k, v in per.items()}},
              open(os.path.join(RES, "v2_summary.json"), "w"), indent=1)
    print(json.dumps(dict(tot), indent=0)); print({k: dict(v) for k, v in per.items()})

if __name__ == "__main__":
    main()
