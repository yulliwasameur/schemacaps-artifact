#!/usr/bin/env python3
"""Steady-state overhead of the proxy on tools/list and tools/call (revision 2).
Staged server (v1, unchanged tools), rule nonamp label-free, call validated and checked against a policy.
R runs x N iterations per configuration, direct and proxied runs interleaved; per-run medians are reported and the
headline is the median of the per-run differences, with min and max across runs. Output: results/proto_overhead.json"""
import os, sys, json, time, statistics, tempfile, shutil, platform
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from rawclient import Client
PY = sys.executable; PROXY = os.path.join(HERE, "schemacaps_proxy.py"); SERVER = os.path.join(HERE, "staged_server.py")
N, R = 500, 5
POLICY = {"send_report": {"to": {"regex": r"[a-z]+@corp\.example"}}}


def run(direct):
    work = tempfile.mkdtemp(); env = dict(os.environ, STAGED_VERSION="v1", STAGED_OUTBOX=os.path.join(work, "o.jsonl"))
    pol = os.path.join(work, "p.json"); json.dump(POLICY, open(pol, "w"))
    cmd = [PY, SERVER] if direct else [PY, PROXY, "--state", os.path.join(work, "s.json"), "--rule", "nonamp",
                                        "--trust-first-use", "--policy", pol, "--", PY, SERVER]
    c = Client(cmd, env=env); c.initialize(); c.list_tools()
    for _ in range(20):                                              # warm-up
        c.list_tools(); c.call("send_report", {"to": "team@corp.example", "body": "x"})
    lst, cal = [], []
    for _ in range(N):
        t0 = time.perf_counter(); c.list_tools(); lst.append((time.perf_counter() - t0) * 1000)
        t0 = time.perf_counter(); c.call("send_report", {"to": "team@corp.example", "body": "x"}); cal.append((time.perf_counter() - t0) * 1000)
    c.close(); shutil.rmtree(work, ignore_errors=True)
    return statistics.median(lst), statistics.median(cal)


runs = []
for k in range(R):
    order = (True, False) if k % 2 == 0 else (False, True)
    m = {d: run(d) for d in order}
    runs.append({"direct_list": m[True][0], "proxied_list": m[False][0], "direct_call": m[True][1], "proxied_call": m[False][1]})
dl = [r["proxied_list"] - r["direct_list"] for r in runs]; dc = [r["proxied_call"] - r["direct_call"] for r in runs]
res = {"iterations_per_run": N, "runs": R, "per_run_medians_ms": runs,
       "added_list_ms": {"median": round(statistics.median(dl), 3), "min": round(min(dl), 3), "max": round(max(dl), 3)},
       "added_call_ms": {"median": round(statistics.median(dc), 3), "min": round(min(dc), 3), "max": round(max(dc), 3)},
       "machine": {"cpu": platform.processor() or platform.machine(), "cores": os.cpu_count(),
                   "python": platform.python_version(), "os": platform.platform()}}
json.dump(res, open(os.path.join(HERE, "..", "results", "proto_overhead.json"), "w"), indent=1)
print(json.dumps({k: v for k, v in res.items() if k != "per_run_medians_ms"}, indent=1))
