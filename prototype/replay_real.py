#!/usr/bin/env python3
"""Schema-level replay of REAL extracted evolutions through the proxy decision function.
No server is installed or executed here: we load the tool lists already captured in raw/ (dependencies resolved at
publication date) and ask, per rule, what the client would do when the server publishes the newer release over an
existing capability. This shows that a real compatible widening is caught by SchemaCaps and waved through by
compatibility. Output: results/proto_replay_real.json"""
import os, sys, json
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, HERE); sys.path.insert(0, ROOT)
from schemacaps_proxy import decide

def load(pkg, ver):
    safe = pkg.replace("/", "__").replace("@", "")
    return json.load(open(os.path.join(ROOT, "raw", f"{safe}@{ver}.json")))["tools"]

CASES = [
    ("@wonderwhy-er/desktop-commander", "0.1.30", "0.1.35", "execute_command"),
    ("@wonderwhy-er/desktop-commander", "0.1.30", "0.1.35", "read_file"),
    ("firecrawl-mcp", "3.18.0", "3.20.3", "firecrawl_monitor_create"),
    ("@zereight/mcp-gitlab", "1.0.69", "2.0.3", "create_merge_request"),
    ("@sentry/mcp-server", "0.4.0", "0.6.0", "begin_autofix"),
    ("@notionhq/notion-mcp-server", "1.1.0", "1.2.0", "API-post-page"),
]
out = []
for pkg, a, b, tool in CASES:
    to = {t["name"]: t for t in load(pkg, a)}; tn = {t["name"]: t for t in load(pkg, b)}
    row = {"package": pkg, "from": a, "to": b, "tool": tool}
    for rule in ("pin", "compat", "nonamp"):
        v, reasons = decide(rule, to[tool], tn[tool])
        row[rule] = {"verdict": v, "reasons": reasons}
    out.append(row)
os.makedirs(os.path.join(ROOT, "results"), exist_ok=True)
json.dump(out, open(os.path.join(ROOT, "results", "proto_replay_real.json"), "w"), indent=1, ensure_ascii=False)
for r in out:
    print(f"{r['package'].split('/')[-1]:22s} {r['tool']:22s} pin={r['pin']['verdict']:8s} compat={r['compat']['verdict']:8s} nonamp={r['nonamp']['verdict']:8s} {';'.join(r['nonamp']['reasons'][:2])}")
