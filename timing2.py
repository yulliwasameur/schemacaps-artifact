#!/usr/bin/env python3
"""Decision cost of the rule per changed tool (revision 2): cold decisions (the checker's guard cache is cleared
before each one, as a tool change is decided once in deployment), for both labellings. Output: results/v2_timing.json"""
import csv, json, time, platform, os
import classify2
from classify2 import analyse, LEXICAL, LABEL_FREE
from witness import load

ch = [r for r in csv.DictReader(open("results/v2_changes.csv")) if r["schema_changed"] == "True"]
pairs = []
for r in ch:
    o = [t for t in load(r["package"], r["from"])["tools"] if t["name"] == r["tool"]][0]
    n = [t for t in load(r["package"], r["to"])["tools"] if t["name"] == r["tool"]][0]
    pairs.append((o, n))
res = {"n": len(pairs), "cpu": platform.processor() or platform.machine(), "python": platform.python_version(),
       "cores": os.cpu_count()}
for name, lab in (("lexical", LEXICAL), ("label_free", LABEL_FREE)):
    ts = []
    for o, n in pairs:
        classify2._GCACHE.clear()
        t0 = time.perf_counter(); analyse(o, n, lab); ts.append(time.perf_counter() - t0)
    ts.sort(); q = lambda p: ts[int(p * (len(ts) - 1))] * 1000
    res[name] = {"median_ms": round(q(.5), 1), "p90_ms": round(q(.9), 1), "p99_ms": round(q(.99), 1),
                 "max_ms": round(ts[-1] * 1000, 1)}
json.dump(res, open("results/v2_timing.json", "w"), indent=1)
print(json.dumps(res, indent=1))
