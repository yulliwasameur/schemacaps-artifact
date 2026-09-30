#!/usr/bin/env python3
"""Differential soundness oracle, v2 (deviation 10). Audits EVERY silent re-bind of the rule, compatible or not.

A silent re-bind is any changed tool (schema, description, title or annotations) on which the rule neither asks
(amp_strict) nor abstains (undecided). For each one:

  label-free mode (every coordinate is authority-bearing; the proxy default without a manifest):
      Definition 1 + the product condition imply that every call admitted by the new schema was admitted by the
      old one, with unchanged declared defaults. We test that directly on the WHOLE schema: N values generated from
      the new schema must all validate against the old one, and no declared default may differ.
  lexical mode (only lexically authority-bearing coordinates count):
      (a) each lexical-authority path present in both versions: N values generated from the new marginal must
          validate against the old marginal;
      (b) openings, checked semantically and independently of the classifier: N values generated from the whole
          new schema must not carry, at a location where the old schema had a closed object, a key the old schema
          did not declare there (an undeclared field, or a newly declared lexical-authority argument).

Generation is deterministic (Hypothesis derandomize=True) and bounded; generation failures are counted and
reported. A clean run is evidence, not proof: it shows that no generated witness contradicts a silent re-bind.
Usage: python3 oracle2.py [--label-free] [--n N]      -> results/oracle2_<mode>.json
"""
import csv, glob, json, os, sys, time, collections, warnings
warnings.filterwarnings("ignore")
import jsonschema
from hypothesis import given, settings, HealthCheck
from hypothesis_jsonschema import from_schema
import classify2
from classify2 import analyse, walk, leaf, LEXICAL, LABEL_FREE, norm_schema, closed_ancestor
from classify import resolve_local_refs, clean, h

MODE = "label_free" if "--label-free" in sys.argv else "lexical"
LAB = LABEL_FREE if MODE == "label_free" else LEXICAL
N = int(sys.argv[sys.argv.index("--n") + 1]) if "--n" in sys.argv else 100
classify2.GUARD_BUDGET = 60
NOCEX = object()


class Timeout(Exception):
    pass


def generate(schema, n=N, secs=60):
    """Up to n values from `schema`, in a fixed order (deterministic). Returns ('ok', values) or ('gen_error', reason).
    Wall-clock bound checked in the test body (no signals); generation only."""
    import time as _t
    from hypothesis import Phase
    out = []; deadline = _t.monotonic() + secs
    try:
        @settings(max_examples=n, suppress_health_check=list(HealthCheck), database=None, deadline=None,
                  derandomize=True, phases=[Phase.generate])
        @given(from_schema(schema))
        def t(x):
            if _t.monotonic() > deadline:
                raise Timeout()
            out.append(x)
        t()
    except Timeout:
        pass
    except Exception as e:
        if not out:
            return "gen_error", type(e).__name__
    return ("ok", out) if out else ("gen_error", "no_value")


def validator(s):
    return jsonschema.validators.validator_for(s)(s)


def closed_locations(schema):
    """Old closed objects: {path: set(declared keys)} (paths as produced by classify2.walk)."""
    decl, objs = walk(schema)[:2]
    res = {}
    for p, closed in objs.items():
        if closed:
            pre = f"{p}." if p else ""
            res[p] = {q[len(pre):] for q in decl if q.startswith(pre) and "." not in q[len(pre):].replace("[]", "")
                      and not q[len(pre):].endswith("[]")}
    return res


def locations(value, path=""):
    """Yield (path, dict) for every object inside a JSON value, with array elements under path[]."""
    if isinstance(value, dict):
        yield path, value
        for k, v in value.items():
            yield from locations(v, f"{path}.{k}" if path else k)
    elif isinstance(value, list):
        for v in value:
            yield from locations(v, f"{path}[]")


def audit_label_free(so, sn):
    """Whole-schema differential: new ⊆ old on generated values, and identical declared defaults."""
    issues = []
    do, dn = walk(so)[0], walk(sn)[0]
    for p in set(do) & set(dn):
        if do[p][2] != dn[p][2]:
            issues.append(("default_changed", p, json.dumps([do[p][2], dn[p][2]])[:80]))
    st, vals = generate(sn)
    if st != "ok":
        return issues, "gen_error", 0
    vo = validator(so)
    for x in vals:
        if not vo.is_valid(x):
            issues.append(("admitted_now_refused_before", "<call>", json.dumps(x)[:120]))
            break
    return issues, "ok", len(vals)


def audit_lexical(so, sn):
    issues, gen_err, tested = [], 0, 0
    do, dn = walk(so)[0], walk(sn)[0]
    for p in sorted(set(do) & set(dn)):
        if not LEXICAL(p):
            continue
        a, b = clean(dn[p][0]), clean(do[p][0])
        if h(a) == h(b):
            continue
        st, vals = generate(a)
        if st != "ok":
            gen_err += 1; continue
        tested += 1
        vb = validator(b)
        bad = next((x for x in vals if not vb.is_valid(x)), NOCEX)
        if bad is not NOCEX:
            issues.append(("widened", p, json.dumps(bad)[:120]))
    closed = closed_locations(so)
    if closed:
        st, vals = generate(sn)
        if st != "ok":
            gen_err += 1
        else:
            tested += 1
            for x in vals:
                for loc, obj in locations(x):
                    if loc in closed:
                        for k in obj:
                            if k in closed[loc]:
                                continue
                            q = f"{loc}.{k}" if loc else k
                            declared_new = q in dn
                            if not declared_new or LEXICAL(q):
                                issues.append(("opened" if not declared_new else "new_authority_arg", q,
                                               json.dumps(x)[:120]))
                                break
                if issues and issues[-1][0] in ("opened", "new_authority_arg"):
                    break
    return issues, ("gen_error" if gen_err and not tested else "ok"), tested


def main():
    t0 = time.time()
    recs = collections.defaultdict(list)
    for f in glob.glob("raw/*.json"):
        r = json.load(open(f))
        if r["status"] == "ok":
            recs[r["package"]].append(r)
    stats = collections.Counter(); unsound = []
    for pkg, items in sorted(recs.items()):
        items.sort(key=lambda r: r["published"])
        for o, n in zip(items, items[1:]):
            to = {t["name"]: t for t in o["tools"]}; tn = {t["name"]: t for t in n["tools"]}
            for name in sorted(set(to) & set(tn)):
                a = analyse(to[name], tn[name], LAB)
                changed = a["schema_changed"] or a["desc_changed"] or a["title_changed"] or a["annot_changed"]
                if not changed:
                    continue
                if a.get("amp_strict") or a.get("undecided"):
                    stats["asked"] += 1; continue
                stats["silent_rebinds"] += 1
                if not a["schema_changed"]:
                    stats["identical_schema"] += 1; continue          # description/title/annotation change only
                stats["schema_rebinds"] += 1
                stats["compatible" if a["compatible"] is True else ("incompatible" if a["compatible"] is False
                                                                    else "compat_undecided")] += 1
                so = resolve_local_refs(norm_schema(to[name].get("inputSchema")))
                sn = resolve_local_refs(norm_schema(tn[name].get("inputSchema")))
                issues, st, k = (audit_label_free if MODE == "label_free" else audit_lexical)(so, sn)
                stats["gen_error" if st == "gen_error" else "tested"] += 1
                stats["generated_checks"] += k
                for kind, p, cex in issues:
                    unsound.append({"package": pkg, "from": o["version"], "to": n["version"], "tool": name,
                                    "kind": kind, "path": p, "witness": cex,
                                    "compatible": a["compatible"]})
    res = {"mode": MODE, "samples_per_check": N, "deterministic_seed": True, **dict(stats),
           "unsound": unsound, "seconds": round(time.time() - t0, 1),
           "conclusion": ("no generated witness contradicts a silent re-bind" if not unsound
                          else f"{len(unsound)} witnesses found")}
    os.makedirs("results", exist_ok=True)
    json.dump(res, open(f"results/oracle2_{MODE}.json", "w"), indent=1, ensure_ascii=False)
    print(json.dumps({k: v for k, v in res.items() if k != "unsound"}, indent=1))
    for u in unsound[:10]:
        print("UNSOUND:", u)


if __name__ == "__main__":
    main()
