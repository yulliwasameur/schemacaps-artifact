#!/usr/bin/env python3
"""Robustness of the pilot's amplification count (revision 2: this script regenerates robustness*.json).

For a labelling (lexical: results/v2_pairs.csv; label-free: results/free_pairs.csv) it reports:
  - the compatible-and-amplifying count per package and its rate over compatible changes;
  - leave-one-package-out counts and the count without the two largest contributors;
  - a package-level cluster bootstrap of the rate (packages resampled with replacement, B draws, fixed seed).
The corpus is not a random sample of MCP servers (top downloads + the official reference servers), so the bootstrap
is a stability check of the rate under package resampling, not an estimate of an ecosystem-wide rate.
Usage: python3 robustness.py [--label-free] [--kind core|strict] -> results/robustness[_free][_strict].json
"""
import csv, json, os, random, sys, collections

FREE = "--label-free" in sys.argv
KIND = sys.argv[sys.argv.index("--kind") + 1] if "--kind" in sys.argv else "core"
B, SEED = 10000, 20260929
src = os.path.join("results", ("free_" if FREE else "v2_") + "pairs.csv")
col = "ca_core" if KIND == "core" else "ca_strict"

per = collections.defaultdict(lambda: [0, 0])                  # package -> [amplifying, compatible]
for r in csv.DictReader(open(src)):
    per[r["package"]][0] += int(r[col]); per[r["package"]][1] += int(r["compatible"])
pk = sorted(per)
tot_a = sum(per[p][0] for p in pk); tot_c = sum(per[p][1] for p in pk)
by_pkg = {p: per[p][0] for p in pk if per[p][0]}
top = sorted(by_pkg, key=lambda p: -by_pkg[p])[:2]
rng = random.Random(SEED); rates = []
for _ in range(B):
    s = [pk[rng.randrange(len(pk))] for _ in pk]
    a = sum(per[p][0] for p in s); c = sum(per[p][1] for p in s)
    if c:
        rates.append(a / c)
rates.sort()
q = lambda f: rates[int(f * (len(rates) - 1))]
res = {"labelling": "label_free" if FREE else "lexical", "kind": KIND, "source": src,
       "packages_resampled": len(pk), "bootstrap_draws": B, "seed": SEED,
       "total": tot_a, "compatible": tot_c, "rate": tot_a / tot_c, "by_package": by_pkg,
       "leave_one_package_out": {p: tot_a - by_pkg[p] for p in by_pkg},
       "top2": top, "without_top2": tot_a - sum(by_pkg[p] for p in top),
       "bootstrap_interval_95": [q(0.025), q(0.975)],
       "note": "package-level resampling stability check; the corpus is not a random sample of servers"}
out = os.path.join("results", "robustness" + ("_free" if FREE else "") + ("" if KIND == "core" else "_strict") + ".json")
json.dump(res, open(out, "w"), indent=1)
print(json.dumps({k: v for k, v in res.items() if k not in ("by_package", "leave_one_package_out")}, indent=1))
