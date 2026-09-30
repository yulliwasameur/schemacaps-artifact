#!/usr/bin/env python3
"""Schema-level replay of the six hand-verified REAL evolutions (Table 5) through the proxy's decision function.

Revision 2: each case replays the EXACT release pair in which the widening appears -- the last release without the
argument and the first release with it (dated from the intermediate extractions in raw_intermediates/) -- and
asserts that the announced reason is produced. No server is installed or executed: the tool lists were captured
at extraction time (dependencies resolved at the publication date). Rules compared: pin, compat, and SchemaCaps
with each labeller (label-free = proxy default, lexical = heuristic). Output: results/proto_replay_real.json
"""
import os, sys, json
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE); sys.path.insert(0, ROOT)
from schemacaps_proxy import decide
from classify2 import LEXICAL, LABEL_FREE


def load(pkg, ver):
    safe = pkg.replace("/", "__").replace("@", "")
    for d in ("raw", "raw_intermediates"):
        p = os.path.join(ROOT, d, f"{safe}@{ver}.json")
        if os.path.exists(p):
            r = json.load(open(p))
            if r.get("status", "ok") == "ok":
                return {t["name"]: t for t in r["tools"]}, d
    raise FileNotFoundError(f"{pkg}@{ver}")


# (package, last release without the argument, first release with it, tool, announced reason)
CASES = [
    ("@wonderwhy-er/desktop-commander", "0.1.34", "0.1.35", "execute_command", "new_authority_arg:shell"),
    ("@wonderwhy-er/desktop-commander", "0.1.31", "0.1.32", "read_file", "new_authority_arg:isUrl"),
    ("firecrawl-mcp", "3.18.0", "3.19.0", "firecrawl_monitor_create", "new_authority_arg:webhookUrl"),
    ("@zereight/mcp-gitlab", "1.0.74", "1.0.75", "create_merge_request", "new_authority_arg:target_project_id"),
    ("@sentry/mcp-server", "0.4.0", "0.5.0", "begin_autofix", "new_authority_arg:regionUrl"),
    ("@notionhq/notion-mcp-server", "1.1.0", "1.2.0", "API-post-page", "object_opened:parent"),
]


def main():
    out, failures = [], []
    for pkg, a, b, tool, expected in CASES:
        to, src_a = load(pkg, a); tn, src_b = load(pkg, b)
        row = {"package": pkg, "from": a, "to": b, "tool": tool, "expected_reason": expected,
               "sources": [src_a, src_b], "tool_in_both": tool in to and tool in tn}
        if not row["tool_in_both"]:
            row["error"] = "tool absent from one release"; failures.append(row); out.append(row); continue
        for rule, lab, key in (("pin", LABEL_FREE, "pin"), ("compat", LABEL_FREE, "compat"),
                               ("nonamp", LABEL_FREE, "schemacaps_label_free"), ("nonamp", LEXICAL, "schemacaps_lexical")):
            v, reasons = decide(rule, to[tool], tn[tool], lab)
            row[key] = {"verdict": v, "reasons": reasons}
        row["expected_reason_produced"] = {k: expected in row[k]["reasons"]
                                           for k in ("schemacaps_label_free", "schemacaps_lexical")}
        if not all(row["expected_reason_produced"].values()):
            failures.append(row)
        out.append(row)
    os.makedirs(os.path.join(ROOT, "results"), exist_ok=True)
    json.dump({"cases": out, "all_expected_reasons_produced": not failures},
              open(os.path.join(ROOT, "results", "proto_replay_real.json"), "w"), indent=1, ensure_ascii=False)
    for r in out:
        if "error" in r:
            print(f"{r['package']:32s} {r['from']}->{r['to']} {r['tool']}: {r['error']}"); continue
        print(f"{r['package'].split('/')[-1]:18s} {r['from']:>7s}->{r['to']:<7s} {r['tool']:26s} "
              f"pin={r['pin']['verdict']:7s} compat={r['compat']['verdict']:7s} "
              f"SC-free={r['schemacaps_label_free']['verdict']:7s} SC-lex={r['schemacaps_lexical']['verdict']:7s} "
              f"expected={r['expected_reason_produced']}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
