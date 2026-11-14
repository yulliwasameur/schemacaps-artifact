#!/usr/bin/env python3
"""Adversarial benchmark of the inclusion checker and of the re-binding rule (camera-ready, review R1.3).

Schema pairs are generated deterministically (fixed seed) in a finite-domain fragment of JSON Schema where
inclusion and amplification can be decided EXACTLY by enumeration, independently of jsonsubschema:
  leaves     boolean, string enum/const/unrestricted, integer ranges/unrestricted, nullable variants,
             arrays of string enums with maxItems;
  objects    properties, required, additionalProperties (false / true / a leaf schema), declared defaults,
             one level of nesting;
  combinators anyOf (alternative required fields), allOf + if/then (conditional constraints), not, $defs/$ref.
In this fragment membership depends only on equality with mentioned constants, on integer bounds, on the presence of
named keys and on the (uniform) treatment of undeclared keys; hence a finite universe built from the constants of both
schemas, one fresh string, fresh integers outside every mentioned bound, one fresh key per object and arrays up to the
largest maxItems + 1 contains a witness for every non-inclusion (no minProperties, patternProperties, uniqueItems,
floats or string formats are generated). The reference is exhaustive enumeration over that universe.

Two levels:
  (1) checker:  a ⊆ b ? for raw jsonsubschema, jsonsubschema after boolean normalisation (no guard), and the guarded
      checker C of the paper. False acceptance = "yes" while a witness exists.
  (2) rule:     S -> S' (one or two mutations of the kinds seen in the pilot, including narrowing and equivalent
      rewritings) through classify2.analyse in label-free mode, against the exact effective-value amplification
      (∃ x' ∈ [[S']] whose effective value, declared defaults filled in, is not that of any x ∈ [[S]]). Also reported:
      pinning (asks on any change) and compatibility (re-binds when [[S]] ⊆ [[S']]).
Output: results/adversarial_bench.json"""
import copy, itertools, json, os, random, sys, time, warnings
warnings.filterwarnings("ignore")
import jsonschema

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import classify2
from classify import sub as raw_sub, clean, h

SEED = int(os.environ.get("BENCH_SEED", "20261114"))
OUT = os.environ.get("BENCH_OUT", "adversarial_bench.json")
N_RULE = 600        # S -> S' pairs for the rule
N_CHECK = 600       # marginal pairs for the checker
MAX_UNIVERSE = 150000
STRS = ["a", "b", "c"]
FRESH_STR = "zz"
FRESH_KEY = "zz_extra"
ABSENT = "\x00<absent>"

# ------------------------------------------------------------------------------------------------- generator
def leaf(r):
    k = r.choice(["bool", "boolenum", "senum", "sconst", "sany", "irange", "iany", "arr"])
    if k == "bool": s = {"type": "boolean"}
    elif k == "boolenum": s = {"type": "boolean", "enum": [r.choice([True, False])]}
    elif k == "senum": s = {"type": "string", "enum": sorted(r.sample(STRS, r.randint(1, 2)))}
    elif k == "sconst": s = {"type": "string", "const": r.choice(STRS)}
    elif k == "sany": s = {"type": "string"}
    elif k == "irange":
        lo = r.randint(0, 2); s = {"type": "integer", "minimum": lo, "maximum": r.randint(lo, 3)}
    elif k == "iany": s = {"type": "integer"}
    else: s = {"type": "array", "items": {"type": "string", "enum": sorted(r.sample(STRS, 2))}, "maxItems": r.randint(1, 2)}
    if r.random() < 0.12 and k not in ("arr",):
        s = nullable(s)
    return s

def nullable(s):
    s = dict(s)
    if "enum" in s: s["enum"] = list(s["enum"]) + [None]
    elif "const" in s: s = {"enum": [s["const"], None]}
    t = s.get("type")
    if t and "enum" not in s: s["type"] = [t, "null"] if isinstance(t, str) else list(t) + ["null"]
    elif "enum" in s and t: s["type"] = [t, "null"] if isinstance(t, str) else list(t)
    return s

def default_for(s, r):
    if "enum" in s: return r.choice([v for v in s["enum"] if v is not None] or [None])
    if "const" in s: return s["const"]
    t = s.get("type"); t = t[0] if isinstance(t, list) else t
    return {"boolean": r.choice([True, False]), "string": r.choice(STRS),
            "integer": s.get("minimum", 0)}.get(t)

def obj(r, depth=0, names=("p", "q", "s")):
    props = {}
    for n in names[: r.randint(2, len(names))]:
        if depth == 0 and r.random() < 0.25:
            props[n] = obj(r, 1, ("u", "v"))
        else:
            props[n] = leaf(r)
            if r.random() < 0.15 and props[n].get("type") != "array":
                props[n]["default"] = default_for(props[n], r)
    req = sorted(n for n in props if r.random() < 0.5 and "default" not in props[n])
    s = {"type": "object", "properties": props}
    if req: s["required"] = req
    ap = r.random()
    s["additionalProperties"] = False if ap < 0.7 else (True if ap < 0.85 else leaf(r))
    return s

def wrap(s, r):
    """Optionally add a combinator or a reference to a top-level object schema."""
    k = r.random(); names = list(s["properties"])
    leaves = [n for n in names if s["properties"][n].get("type") != "object"]
    if k < 0.15 and len(leaves) >= 2:                       # anyOf: one of two fields must be present
        a, b = leaves[:2]; s["anyOf"] = [{"required": [a]}, {"required": [b]}]
    elif k < 0.30 and len(leaves) >= 2:                     # conditional constraint
        a, b = leaves[:2]; pa = s["properties"][a]
        cv = (pa.get("enum") or [pa.get("const", "a")])[0] if ("enum" in pa or "const" in pa) else \
             (True if pa.get("type") == "boolean" else ("a" if "string" in str(pa.get("type")) else 1))
        s["allOf"] = [{"if": {"properties": {a: {"const": cv}}, "required": [a]},
                       "then": {"properties": {b: {"not": {"type": "null"}}}, "required": [b]}}]
    elif k < 0.40 and leaves:                               # not on a leaf
        n = r.choice(leaves); p = s["properties"][n]
        if "string" in str(p.get("type")) and "enum" not in p and "const" not in p:
            s["properties"][n] = dict(p, **{"not": {"enum": [r.choice(STRS)]}})
    elif k < 0.55 and names:                                # $defs / $ref
        n = r.choice(names); s.setdefault("$defs", {})["D"] = s["properties"][n]; s["properties"][n] = {"$ref": "#/$defs/D"}
    return s

def gen_schema(r):
    return wrap(obj(r), r)

# ------------------------------------------------------------------------------------------------- mutations
def _leaf_paths(s):
    out = []
    for n, p in s.get("properties", {}).items():
        if "$ref" in p: out.append(("ref", n))
        elif p.get("type") == "object": out += [("nested", n, m) for m in p.get("properties", {})]
        else: out.append(("leaf", n))
    return out

def _get(s, path):
    if path[0] == "leaf": return s["properties"][path[1]]
    if path[0] == "ref": return s["$defs"]["D"]
    return s["properties"][path[1]]["properties"][path[2]]

def _set(s, path, v):
    if path[0] == "leaf": s["properties"][path[1]] = v
    elif path[0] == "ref": s["$defs"]["D"] = v
    else: s["properties"][path[1]]["properties"][path[2]] = v

def widen_leaf(p, r):
    p = dict(p)
    if p.get("type") == "object":
        p["additionalProperties"] = True; return p
    if "enum" in p:
        vals = [v for v in p["enum"]]
        rest = [x for x in STRS + [True, False] if x not in vals and type(x) == type(next((v for v in vals if v is not None), "a"))]
        if rest and r.random() < 0.6: p["enum"] = vals + [rest[0]]
        else: p.pop("enum")
        return p
    if "const" in p: return {k: v for k, v in p.items() if k != "const"}
    if "maximum" in p: p["maximum"] = p["maximum"] + 2; return p
    if "maxItems" in p: p["maxItems"] += 1; return p
    if "not" in p: p.pop("not"); return p
    return nullable(p)

def narrow_leaf(p, r):
    p = dict(p)
    t = p.get("type")
    if p.get("type") == "object": p["additionalProperties"] = False; return p
    if "enum" in p and len(p["enum"]) > 1: p["enum"] = p["enum"][:-1]; return p
    if t == "string": p["enum"] = ["a", "b"]; return p
    if t == "boolean": p["enum"] = [False]; return p
    if t == "integer": p["minimum"], p["maximum"] = p.get("minimum", 0), p.get("minimum", 0) + 1; return p
    if "maxItems" in p and p["maxItems"] > 0: p["maxItems"] -= 1; return p
    return p

MUTS = ["widen", "narrow", "add_closed", "remove", "drop_required", "add_required", "default", "open", "close",
        "anyof_relax", "cond_drop", "cond_add", "ref_widen", "nested_add", "equiv"]

def mutate(s, r):
    s = copy.deepcopy(s); k = r.choice(MUTS); paths = _leaf_paths(s)
    if k in ("widen", "narrow") and paths:
        pth = r.choice(paths); f = widen_leaf if k == "widen" else narrow_leaf; _set(s, pth, f(_get(s, pth), r))
    elif k == "add_closed":
        s["properties"]["w"] = leaf(r)
    elif k == "remove" and len(s["properties"]) > 1:
        n = r.choice(list(s["properties"])); s["properties"].pop(n)
        if "required" in s:
            s["required"] = [x for x in s["required"] if x != n]
            if not s["required"]: s.pop("required")
        _scrub(s, n)
    elif k == "drop_required" and s.get("required"):
        s["required"] = s["required"][1:]
        if not s["required"]: s.pop("required")
    elif k == "add_required":
        cand = [n for n in s["properties"] if n not in s.get("required", []) and "default" not in s["properties"][n]]
        if cand: s["required"] = sorted(s.get("required", []) + [r.choice(cand)])
    elif k == "default":
        cand = [n for n in s["properties"] if "$ref" not in s["properties"][n] and s["properties"][n].get("type") not in ("object", "array")]
        if cand:
            n = r.choice(cand); p = dict(s["properties"][n]); old = p.get("default")
            nv = default_for(p, r)
            if nv == old: p.pop("default", None)
            else: p["default"] = nv
            s["properties"][n] = p
            if "default" in p and n in s.get("required", []):
                s["required"] = [x for x in s["required"] if x != n]
                if not s["required"]: s.pop("required")
    elif k == "open": s["additionalProperties"] = True
    elif k == "close": s["additionalProperties"] = False
    elif k == "anyof_relax" and "anyOf" in s: s.pop("anyOf")
    elif k == "cond_drop" and "allOf" in s: s.pop("allOf")
    elif k == "cond_add" and "allOf" not in s: s = wrap_force_cond(s)
    elif k == "ref_widen" and "$defs" in s: s["$defs"]["D"] = widen_leaf(s["$defs"]["D"], r)
    elif k == "nested_add":
        nest = [n for n, p in s["properties"].items() if p.get("type") == "object"]
        if nest: s["properties"][nest[0]]["properties"]["x"] = leaf(r)
    elif k == "equiv":
        if "$defs" in s:                                    # inline the reference
            n = next(n for n, p in s["properties"].items() if "$ref" in p); s["properties"][n] = s.pop("$defs")["D"]
        else:
            for n, p in s["properties"].items():
                if "enum" in p and len(p["enum"]) > 1: s["properties"][n] = dict(p, enum=list(reversed(p["enum"]))); break
    return s, k

def wrap_force_cond(s):
    leaves = [n for n in s["properties"] if s["properties"][n].get("type") not in ("object", None) and "$ref" not in s["properties"][n]]
    if len(leaves) >= 2:
        a, b = leaves[:2]
        s["allOf"] = [{"if": {"properties": {a: {"const": "a"}}, "required": [a]}, "then": {"required": [b]}}]
    return s

def _scrub(s, n):
    if "anyOf" in s: s.pop("anyOf")
    if "allOf" in s and n in json.dumps(s["allOf"]): s.pop("allOf")

# ------------------------------------------------------------------------------------------------- exact reference
def _consts(s, acc):
    if isinstance(s, dict):
        for k, v in s.items():
            if k in ("enum",): acc["vals"].update(json.dumps(x) for x in v)
            elif k in ("const", "default"): acc["vals"].add(json.dumps(v))
            elif k in ("minimum", "maximum"): acc["ints"].update({v - 1, v, v + 1})
            elif k == "maxItems": acc["len"] = max(acc["len"], v + 1)
            else: _consts(v, acc)
    elif isinstance(s, list):
        for v in s: _consts(v, acc)

def _resolve(s, root):
    if isinstance(s, dict) and "$ref" in s:
        return root["$defs"][s["$ref"].split("/")[-1]]
    return s

def _shape(s, root, acc):
    """Shape template: union over both schemas of declared keys per object path, nested objects, keys that some
    schema declares as arrays, and whether every occurrence of the object is closed (additionalProperties: false)."""
    s = _resolve(s, root)
    if not isinstance(s, dict): return
    if s.get("type") == "object" or "properties" in s:
        acc.setdefault("keys", set()).update(s.get("properties", {}))
        if s.get("additionalProperties", True) is not False: acc["open"] = True
        ap = s.get("additionalProperties")
        if isinstance(ap, dict) and "array" in str(ap.get("type")): acc.setdefault("arr", set()).add(FRESH_KEY)
        for n, p in s.get("properties", {}).items():
            p = _resolve(p, root)
            if isinstance(p, dict) and "array" in str(p.get("type")): acc.setdefault("arr", set()).add(n)
            if isinstance(p, dict) and (p.get("type") == "object" or "properties" in p):
                _shape(p, root, acc.setdefault("sub", {}).setdefault(n, {}))
    for k in ("anyOf", "allOf", "oneOf"):
        for b in s.get(k, []): _shape(b, root, acc)
    for k in ("if", "then", "else", "not"):
        if k in s: _shape(s[k], root, acc)

def universe(a, b):
    acc = {"vals": set(), "ints": set(), "len": 2}
    _consts(a, acc); _consts(b, acc)
    scal = {json.dumps(x) for x in (None, True, False, FRESH_STR, -100, 100)} | acc["vals"] | {json.dumps(i) for i in acc["ints"]}
    scal = [json.loads(x) for x in sorted(scal)]
    strs = [x for x in scal if isinstance(x, str)]
    arrays = [list(t) for L in range(acc["len"] + 1) for t in itertools.product(strs, repeat=L)]
    shp = {}; _shape(a, a, shp); _shape(b, b, shp)
    def objects(sh, depth):
        # One representative per JSON type suffices where no schema constrains that type at that key: arrays are
        # enumerated only for keys some schema declares as arrays, the fresh key only for objects not closed in
        # every occurrence (a closed object rejects any undeclared key in both schemas).
        keys = sorted(sh.get("keys", set())) + ([FRESH_KEY] if sh.get("open") else [])
        choices = []
        for k in keys:
            opts = [ABSENT] + scal + (arrays if k in sh.get("arr", set()) else [[]]) + [{}]
            if k in sh.get("sub", {}) and depth < 2:
                opts = opts + objects(sh["sub"][k], depth + 1)
            choices.append(opts)
        total = 1
        for c in choices: total *= len(c)
        if total > MAX_UNIVERSE: raise OverflowError(total)
        out = []
        for combo in itertools.product(*choices):
            out.append({k: v for k, v in zip(keys, combo) if not (isinstance(v, str) and v == ABSENT)})
        return out
    return objects(shp, 0)

def leaf_universe(a, b):
    acc = {"vals": set(), "ints": set(), "len": 2}
    _consts(a, acc); _consts(b, acc)
    scal = {json.dumps(x) for x in (None, True, False, FRESH_STR, -100, 100)} | acc["vals"] | {json.dumps(i) for i in acc["ints"]}
    scal = [json.loads(x) for x in sorted(scal)]
    strs = [x for x in scal if isinstance(x, str)]
    arrays = [list(t) for L in range(acc["len"] + 1) for t in itertools.product(strs, repeat=L)]
    objs = [{}, {"u": "a"}, {FRESH_KEY: "a"}]
    return scal + arrays + objs

def _validator(s):
    return jsonschema.Draft202012Validator(s)

def _eff(x, s, root):
    """Effective value: declared defaults filled in for absent keys (recursively on present objects)."""
    s = _resolve(s, root)
    if not isinstance(x, dict) or not isinstance(s, dict): return x
    out = dict(x)
    for n, p in s.get("properties", {}).items():
        p = _resolve(p, root)
        if n not in out and isinstance(p, dict) and "default" in p: out[n] = p["default"]
        elif n in out: out[n] = _eff(out[n], p, root)
    return out

def exact_amplifies(old, new):
    U = universe(old, new)
    vo, vn = _validator(old), _validator(new)
    eo = {json.dumps(_eff(x, old, old), sort_keys=True) for x in U if vo.is_valid(x)}
    for x in U:
        if vn.is_valid(x) and json.dumps(_eff(x, new, new), sort_keys=True) not in eo:
            return True, len(U)
    return False, len(U)

def exact_included(a, b, U):
    va, vb = _validator(a), _validator(b)
    return not any(va.is_valid(x) and not vb.is_valid(x) for x in U)

def exact_schema_included(a, b):
    U = universe(a, b)
    return exact_included(a, b, U)

# ------------------------------------------------------------------------------------------------- checker level
def gen_marginal(r):
    kind = r.random()
    if kind < 0.55:
        a = leaf(r); b = widen_leaf(a, r) if r.random() < 0.5 else narrow_leaf(a, r)
        if r.random() < 0.5: a, b = b, a
    elif kind < 0.75:
        a = {"type": "object", "properties": {"u": leaf(r)}, "additionalProperties": r.random() < 0.3}
        b = copy.deepcopy(a); b["properties"]["u"] = widen_leaf(b["properties"]["u"], r) if r.random() < 0.5 else narrow_leaf(b["properties"]["u"], r)
        if r.random() < 0.3: b["additionalProperties"] = not a["additionalProperties"]
        if r.random() < 0.5: a, b = b, a
    elif kind < 0.9:
        x = leaf(r); y = leaf(r)
        a = {"anyOf": [x, y]} if r.random() < 0.5 else {"not": x}
        b = x if r.random() < 0.5 else {"anyOf": [x, widen_leaf(y, r)]}
        if r.random() < 0.5: a, b = b, a
    elif kind < 0.93:
        x = leaf(r)
        a = {"$defs": {"D": x}, "$ref": "#/$defs/D"}
        b = widen_leaf(x, r) if r.random() < 0.5 else x
        if r.random() < 0.5: a, b = b, a
    elif kind < 0.965:                                  # typed additionalProperties against false / true / another type
        base = {"type": "object", "properties": {"u": leaf(r)}}
        a = dict(base, additionalProperties=leaf(r))
        b = dict(base, additionalProperties=r.choice([False, True, leaf(r)]))
        if r.random() < 0.5: a, b = b, a
    else:                                               # conditional constraint between two fields
        u, v = leaf(r), {"type": "string", "enum": ["a", "b"]}
        cond = {"if": {"properties": {"v": {"const": "a"}}, "required": ["v"]}, "then": {"required": ["u"]}}
        a = {"type": "object", "properties": {"u": u, "v": v}, "additionalProperties": False, "allOf": [cond]}
        b = {"type": "object", "properties": {"u": u, "v": v}, "additionalProperties": False}
        if r.random() < 0.5: a, b = b, a
    return a, b

def run_checker(r):
    rows = []
    for i in range(N_CHECK):
        a, b = gen_marginal(r)
        try:
            U = leaf_universe(a, b) if "properties" not in json.dumps(a) + json.dumps(b) else universe(
                {"type": "object", "properties": {"m": a}, "additionalProperties": False},
                {"type": "object", "properties": {"m": b}, "additionalProperties": False})
            if "properties" in json.dumps(a) + json.dumps(b):
                U = [x["m"] for x in U if "m" in x] + [x for x in U]
            truth = exact_included(a, b, U)
        except OverflowError:
            continue
        def safe(f):
            try: return f()
            except Exception: return None
        rr = safe(lambda: raw_sub(clean(a), clean(b)))
        rn = safe(lambda: classify2.sub(a, b, guard=False))
        rg = safe(lambda: classify2.sub(a, b, guard=True))
        rows.append({"a": a, "b": b, "truth": truth, "raw": rr, "norm": rn, "guarded": rg})
    def stats(key):
        fa = sum(1 for x in rows if x[key] is True and not x["truth"])
        fr = sum(1 for x in rows if x[key] is False and x["truth"])
        unk = sum(1 for x in rows if x[key] is None)
        return {"false_accept": fa, "false_reject": fr, "unknown": unk,
                "not_included": sum(1 for x in rows if not x["truth"])}
    return rows, {k: stats(k) for k in ("raw", "norm", "guarded")}

# ------------------------------------------------------------------------------------------------- rule level
def run_rule(r):
    rows = []; kinds = {}
    tries = 0; discarded = 0
    while len(rows) < N_RULE and tries < N_RULE * 5:
        tries += 1
        old = gen_schema(r)
        new, k1 = mutate(old, r)
        k2 = None
        if r.random() < 0.3: new, k2 = mutate(new, r)
        if h(old) == h(new): continue
        try:
            jsonschema.Draft202012Validator.check_schema(old); jsonschema.Draft202012Validator.check_schema(new)
            amp, usize = exact_amplifies(old, new)
            compat = exact_schema_included(old, new)
        except OverflowError:
            discarded += 1
            continue
        except jsonschema.exceptions.SchemaError:
            continue
        rows.append({"old": old, "new": new, "mutations": [k1] + ([k2] if k2 else []), "amplifies": amp,
                     "compatible": compat, "universe": usize})
    g0 = dict(classify2.GUARD_STATS)
    variants = {"guarded": True, "unguarded": False}
    out = {}
    for name, guard in variants.items():
        orig = classify2.sub
        classify2.sub = (lambda a, b, guard=guard, _o=orig: _o(a, b, guard=guard))
        try:
            for x in rows:
                try:
                    res = classify2.analyse({"inputSchema": x["old"]}, {"inputSchema": x["new"]}, labeller=classify2.LABEL_FREE)
                    silent = not (res["amp_strict"] or res["undecided"])
                    v3_kinds = {q.split(":")[0] for q in res["reasons"]} - {"removed_to_bottom", "declared_beyond_star"}
                    x["silent_v3_" + name] = not (bool(v3_kinds & set(classify2.STRICT)) or res["undecided"])
                    x["fix_kinds_" + name] = sorted({q.split(":")[0] for q in res["reasons"]} & {"removed_to_bottom", "declared_beyond_star"})
                except Exception as e:
                    silent = False
                x["silent_" + name] = silent
        finally:
            classify2.sub = orig
        out[name] = {"false_silent": sum(1 for x in rows if x["silent_" + name] and x["amplifies"]),
                     "asks": sum(1 for x in rows if not x["silent_" + name]),
                     "asks_non_amplifying": sum(1 for x in rows if not x["silent_" + name] and not x["amplifies"])}
    out["generated"] = len(rows) + discarded
    out["discarded"] = discarded
    sib = [x for x in rows if any(k in x["old"] for k in ("anyOf", "allOf", "oneOf", "not", "if"))]
    out["sibling_old"] = len(sib)
    out["sibling_old_silent"] = sum(1 for x in sib if x["silent_guarded"])
    out["guard_overturned_rule_phase"] = classify2.GUARD_STATS["overturned"] - g0["overturned"]
    out["v3_false_silent"] = sum(1 for x in rows if x.get("silent_v3_guarded") and x["amplifies"])
    out["v3_false_silent_by_kind"] = {k: sum(1 for x in rows if x.get("silent_v3_guarded") and x["amplifies"]
                                             and k in x.get("fix_kinds_guarded", [])) for k in ("removed_to_bottom", "declared_beyond_star")}
    out["pin"] = {"false_silent": 0, "asks": len(rows), "asks_non_amplifying": sum(1 for x in rows if not x["amplifies"])}
    out["compat"] = {"false_silent": sum(1 for x in rows if x["compatible"] and x["amplifies"]),
                     "asks": sum(1 for x in rows if not x["compatible"]),
                     "asks_non_amplifying": sum(1 for x in rows if not x["compatible"] and not x["amplifies"])}
    feats = {"conditional": sum(1 for x in rows if "allOf" in json.dumps(x["old"]) + json.dumps(x["new"])),
             "anyOf": sum(1 for x in rows if "anyOf" in json.dumps(x["old"]) + json.dumps(x["new"])),
             "ref": sum(1 for x in rows if "$ref" in json.dumps(x["old"]) + json.dumps(x["new"])),
             "nested": sum(1 for x in rows if '"properties": {"u"' in json.dumps(x["old"]) + json.dumps(x["new"])),
             "not": sum(1 for x in rows if '"not"' in json.dumps(x["old"]) + json.dumps(x["new"]))}
    return rows, out, feats

def main():
    t0 = time.time()
    r = random.Random(SEED)
    crows, cstats = run_checker(r)
    rrows, rstats, feats = run_rule(r)
    res = {"seed": SEED, "checker": {"pairs": len(crows), **cstats},
           "rule": {"pairs": len(rrows), "amplifying": sum(x["amplifies"] for x in rrows),
                    "non_amplifying": sum(not x["amplifies"] for x in rrows),
                    "compatible_amplifying": sum(x["amplifies"] and x["compatible"] for x in rrows),
                    "features": feats, **rstats},
           "guard": dict(classify2.GUARD_STATS), "seconds": round(time.time() - t0, 1)}
    os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
    json.dump({**res, "checker_rows": crows, "rule_rows": rrows},
              open(os.path.join(HERE, "results", OUT), "w"), indent=1, default=str)
    print(json.dumps(res, indent=1))

if __name__ == "__main__":
    main()
