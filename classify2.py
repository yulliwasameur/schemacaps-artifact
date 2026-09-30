#!/usr/bin/env python3
"""Classement v2 (écart n° 8, après relecture adversariale du 29/09/2026).
Corrige classify.py sur les points relevés : chemins imbriqués (propriétés et items), `required` (valeur absente),
valeurs par défaut (valeur effective), ouverture d'objet (coordonnée ⋆), retrait d'une déclaration sur objet ouvert,
objets sans argument (bogue declared_old), null traité comme absent, précondition « produit » (combinateurs dans
l'ANCIEN schéma sur le chemin d'un argument d'autorité => indécis), indices de l'outil (annotations MCP).
Produit results/v2_changes.csv, results/v2_pairs.csv, results/v2_summary.json. classify.py (v1) est conservé tel quel."""
import json, glob, os, csv, collections, copy
from classify import is_authority, sub as _raw_sub, resolve_local_refs, clean, h, ROOT

# ---- Vérificateur d'inclusion gardé (écart n° 10) -------------------------------------------------------------
# jsonsubschema répond « ⊆ » pour {type: boolean} face à un booléen restreint par enum/const (3 sondes sur 20,
# tests/test_checker.py) : un élargissement d'un drapeau booléen passerait inaperçu. Deux gardes :
#  (1) normalisation exacte : un booléen sans enum/const est réécrit en enum [true, false] (jsonsubschema traite
#      correctement cette forme) ;
#  (2) contre-exemple : tout verdict « ⊆ » entre schémas différents est confronté à une recherche bornée et
#      déterministe (Hypothesis, graine fixe) d'une valeur admise à gauche et refusée à droite ; si elle existe, le
#      verdict devient « ⊄ ». C'est une défense en profondeur, pas une preuve : un défaut du vérificateur qu'aucun
#      témoin généré n'expose resterait possible (le papier le dit).
_SCHEMA_DICTS = ("properties", "patternProperties", "$defs", "definitions", "dependentSchemas")
_SCHEMA_ONE = ("additionalProperties", "items", "not", "if", "then", "else", "contains", "propertyNames",
               "unevaluatedProperties", "unevaluatedItems", "additionalItems")
_SCHEMA_LISTS = ("anyOf", "oneOf", "allOf", "prefixItems")

def bool_norm(s):
    if not isinstance(s, dict):
        return s
    s = dict(s)
    for k in _SCHEMA_DICTS:
        if isinstance(s.get(k), dict): s[k] = {n: bool_norm(v) for n, v in s[k].items()}
    for k in _SCHEMA_ONE:
        if isinstance(s.get(k), dict): s[k] = bool_norm(s[k])
    for k in _SCHEMA_LISTS:
        if isinstance(s.get(k), list): s[k] = [bool_norm(v) for v in s[k]]
    if isinstance(s.get("items"), list): s["items"] = [bool_norm(v) for v in s["items"]]
    t = s.get("type")
    if "enum" not in s and "const" not in s:
        if t == "boolean":
            s["enum"] = [True, False]
        elif isinstance(t, list) and "boolean" in t:
            others = [x for x in t if x != "boolean"]
            if all(x == "null" for x in others):
                s["enum"] = [True, False] + ([None] if others else [])
            else:
                base = {k: v for k, v in s.items() if k != "type"}
                s = {"anyOf": [dict(base, type="boolean", enum=[True, False])] + [dict(base, type=x) for x in others]}
    return s

_NOCEX = object()
_GCACHE = {}
GUARD_BUDGET = 60
GUARD_SECONDS = 2
GUARD_STATS = {"calls": 0, "overturned": 0, "gen_errors": 0}

class _GuardTimeout(Exception): pass
class _Found(Exception): pass


def counterexample(a, b, n=GUARD_BUDGET, secs=GUARD_SECONDS):
    """Value admitted by a and refused by b (sentinel _NOCEX if none was generated; 'gen_error' if a cannot be
    generated). No signals: the test body checks a wall-clock deadline, so the bound holds in any thread and is never
    swallowed by a garbage-collection callback; generation only (no shrinking), stopping at the first witness."""
    import time as _t
    import jsonschema
    from hypothesis import given, settings, HealthCheck, Phase
    from hypothesis_jsonschema import from_schema
    vb = jsonschema.validators.validator_for(b)(b); found = []; deadline = _t.monotonic() + secs
    try:
        @settings(max_examples=n, suppress_health_check=list(HealthCheck), database=None, deadline=None,
                  derandomize=True, phases=[Phase.generate])
        @given(from_schema(a))
        def t(x):
            if _t.monotonic() > deadline:
                raise _GuardTimeout()
            if not vb.is_valid(x):
                found.append(x); raise _Found()
        t()
    except (_GuardTimeout, _Found):
        pass
    except Exception:
        return found[0] if found else "gen_error"
    return found[0] if found else _NOCEX


def sub(a, b, guard=True):
    """a ⊆ b ?  True / False / None (indécis). Vérificateur jsonsubschema + gardes (1) et (2)."""
    a1, b1 = bool_norm(clean(a)), bool_norm(clean(b))
    r = _raw_sub(a1, b1)
    if r is True and guard and h(a1) != h(b1):
        key = (h(a1), h(b1))
        if key not in _GCACHE:
            GUARD_STATS["calls"] += 1
            c = counterexample(a1, b1)
            if c == "gen_error": GUARD_STATS["gen_errors"] += 1
            _GCACHE[key] = c
        c = _GCACHE[key]
        if c is not _NOCEX and not (isinstance(c, str) and c == "gen_error"):
            GUARD_STATS["overturned"] += 1
            return False
    return r

RES = os.path.join(ROOT, "results")
COMB = ("anyOf", "oneOf", "allOf", "if", "not", "dependentRequired", "dependentSchemas", "dependencies",
        "minProperties", "maxProperties", "propertyNames", "patternProperties")
BRANCH = ("anyOf", "oneOf", "allOf")
STRICT = ("new_authority_arg", "widened", "became_optional", "default_changed", "constraint_dropped",
          "object_opened", "object_introduced_open", "nullable_on_required", "nullable", "hint_raised",
          "shape_changed")
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

# Labellers (écart n° 10). Un labeller décide, pour un chemin déclaré, s'il est porteur d'autorité.
#   LEXICAL    : règle lexicale sur le nom de la feuille (heuristique ; rappel mesuré au §7).
#   LABEL_FREE : tout chemin est porteur d'autorité (défaut du proxy sans manifeste : « rôle inconnu => confirmer ») ;
#                la règle est alors correcte sans aucune hypothèse d'étiquetage.
def LEXICAL(p): return is_authority(leaf(p))
def LABEL_FREE(p): return True
def manifest_labeller(authority=(), inert=()):
    """Manifeste versionné : chemins déclarés 'authority' ou 'inert' ; tout chemin non listé est INCONNU => autorité."""
    A, I = set(authority), set(inert)
    return lambda p: p in A or p not in I

def norm_schema(s):
    """Schémas booléens (JSON Schema 2019+) : true == {} (tout), false == {"not": {}} (rien)."""
    if s is True or s is None: return {}
    if s is False: return {"not": {}}
    return s

def node_at(s, path):
    """Sous-schéma au chemin `path` (propriétés et items), sans suivre les combinateurs ; None si non atteignable."""
    s = norm_schema(s)
    if not isinstance(s, dict): return None
    if path == "": return s
    cur = s
    for seg in path.split("."):
        arr = seg.endswith("[]"); name = seg[:-2] if arr else seg
        if name:
            if not isinstance(cur, dict): return None
            pr = cur.get("properties") or {}
            if name not in pr: return None
            cur = norm_schema(pr[name])
        if arr:
            if not isinstance(cur, dict): return None
            it = cur.get("items")
            if it is None or it is True: return {}
            if not isinstance(it, dict): return None
            cur = it
    return cur if isinstance(cur, dict) else None

_CONSTRAINING = ("type", "properties", "additionalProperties", "patternProperties", "enum", "const", "not",
                 "anyOf", "oneOf", "allOf", "$ref", "items", "if", "required")

def child_decl(anc, path):
    """Chemin déclaré de l'enfant direct de `anc` sur le chemin vers `path` (sans le suffixe [])."""
    segs = path.split("."); k = 0 if anc == "" else len(anc.split("."))
    c = ".".join(segs[:k + 1])
    return c[:-2] if c.endswith("[]") else c
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

def analyse(o, n, labeller=None):
    lab = labeller or LEXICAL
    so = resolve_local_refs(norm_schema(o.get("inputSchema")))
    sn = resolve_local_refs(norm_schema(n.get("inputSchema")))
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
    auth = sorted({p for p in set(do) | set(dn) if lab(p)})
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
            # Écart n° 10 : l'ancienne version ferme cet objet (⋆ n'admet rien) ; la nouvelle ne l'expose plus comme
            # objet. Trois cas : retiré d'un parent resté fermé (restriction, rien à demander) ; devenu {} / true /
            # non contraint (⋆ admet tout : ouverture) ; changé de forme ou masqué par un combinateur (conservateur).
            if not closed:
                continue
            nn = node_at(sn, path)
            if nn is None:
                anc = parent(path) if "." in path else ("" if path else None)
                while anc is not None and anc not in on:
                    anc = None if anc == "" else (parent(anc) if "." in anc else "")
                if anc is not None and on.get(anc) is True and child_decl(anc, path) not in dn:
                    continue                                        # retiré d'un objet fermé : restriction
                reasons.append(f"object_opened:{path or '<root>'}")
            elif not any(k in nn for k in _CONSTRAINING):
                reasons.append(f"object_opened:{path or '<root>'}")  # {} / true : tout est admis
            else:
                t = nn.get("type"); ts = t if isinstance(t, list) else ([t] if t else [])
                if ts and "object" not in ts:
                    reasons.append(f"shape_changed:{path or '<root>'}")
                else:
                    r = sub(clean(nn), clean(node_at(so, path) or {}))
                    if r is None: und = True; reasons.append(f"undecided_object:{path or '<root>'}")
                    elif r is False: reasons.append(f"object_opened:{path or '<root>'}")
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
            st["added_auth"] = sum(1 for t in added if any(LAB(p) for p in walk(resolve_local_refs(norm_schema(tn[t].get("inputSchema"))))[0]))
            for name in sorted(set(to) & set(tn)):
                a = analyse(to[name], tn[name], LAB)
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
    for name, rr in ((PREFIX + "changes.csv", rows), (PREFIX + "pairs.csv", prow)):
        keys = list(dict.fromkeys(k for r in rr for k in r))
        with open(os.path.join(RES, name), "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=keys, restval=0); w.writeheader(); w.writerows(rr)
    tot = collections.Counter(); per = collections.defaultdict(collections.Counter)
    for p in prow:
        for k, v in p.items():
            if isinstance(v, int) and k != "gap": tot[k] += v; per[p["strate"]][k] += v
    tot["pairs"] = len(prow)
    for s in per: per[s]["pairs"] = sum(1 for p in prow if p["strate"] == s)
    json.dump({"totals": dict(tot), "per_strate": {k: dict(v) for k, v in per.items()},
               "labeller": "label_free" if LAB is LABEL_FREE else "lexical", "checker_guard": dict(GUARD_STATS)},
              open(os.path.join(RES, PREFIX + "summary.json"), "w"), indent=1)
    print(json.dumps(dict(tot), indent=0)); print({k: dict(v) for k, v in per.items()})

LAB, PREFIX = LEXICAL, "v2_"
if __name__ == "__main__":
    import sys
    if "--label-free" in sys.argv:
        LAB, PREFIX = LABEL_FREE, "free_"
    main()
