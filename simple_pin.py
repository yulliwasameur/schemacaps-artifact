#!/usr/bin/env python3
"""Simplest alternative to SchemaCaps (camera-ready, audit request): 'pin unless the new input schema is included in
the old one' -- re-bind silently iff C(S', S) = yes (guarded checker, whole schema), ask otherwise; descriptions and
effective values (absence, declared defaults) are ignored.

Pilot: on every changed input schema of the label-free classification, count the questions of this rule and the
changes it re-binds silently although the label-free SchemaCaps rule asks (default changes, removals to bottom, ...).
Benchmark: on both seeds of adversarial_bench, count its silent re-binds of changes that amplify exactly.
Output: results/simple_pin.json"""
import csv, json, os, sys, warnings
warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import classify2
from classify import resolve_local_refs
from witness import load


def simple_silent(old, new):
    so = resolve_local_refs(classify2.norm_schema(old))
    sn = resolve_local_refs(classify2.norm_schema(new))
    return classify2.sub(sn, so) is True


def pilot():
    rows = [r for r in csv.DictReader(open(os.path.join(HERE, "results", "free_changes.csv"))) if r["schema_changed"] == "True"]
    asks = silent_where_rule_asks = 0
    for r in rows:
        o = [t for t in load(r["package"], r["from"])["tools"] if t["name"] == r["tool"]][0]
        n = [t for t in load(r["package"], r["to"])["tools"] if t["name"] == r["tool"]][0]
        s = simple_silent(o.get("inputSchema"), n.get("inputSchema"))
        if not s:
            asks += 1
        elif r["amp_strict"] == "True" or r["undecided"] == "True":
            silent_where_rule_asks += 1
    return {"changes": len(rows), "asks": asks, "silent_where_schemacaps_asks": silent_where_rule_asks}


def bench(fname):
    d = json.load(open(os.path.join(HERE, "results", fname)))
    rows = d["rule_rows"]
    false_silent = sum(1 for x in rows if x["amplifies"] and simple_silent(x["old"], x["new"]))
    return {"pairs": len(rows), "amplifying": sum(x["amplifies"] for x in rows), "false_silent": false_silent}


if __name__ == "__main__":
    res = {"pilot": pilot(), "bench_seed1": bench("adversarial_bench.json"),
           "bench_seed2": bench("adversarial_bench_seed2.json")}
    json.dump(res, open(os.path.join(HERE, "results", "simple_pin.json"), "w"), indent=1)
    print(json.dumps(res, indent=1))
