#!/usr/bin/env python3
"""Overhead of the proxy on tools/call and tools/list, staged server, 200 iterations. Output: results/proto_overhead.json"""
import os, sys, json, time, statistics, tempfile, shutil
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from rawclient import Client
PY = sys.executable; PROXY = os.path.join(HERE, "schemacaps_proxy.py"); SERVER = os.path.join(HERE, "staged_server.py")
N = 200
def bench(direct):
    work = tempfile.mkdtemp(); env = dict(os.environ, STAGED_VERSION="v1", STAGED_OUTBOX=os.path.join(work, "o.jsonl"))
    cmd = [PY, SERVER] if direct else [PY, PROXY, "--state", os.path.join(work, "s.json"), "--rule", "nonamp", "--trust-first-use", "--", PY, SERVER]
    c = Client(cmd, env=env); c.initialize(); c.list_tools()
    lst, cal = [], []
    for _ in range(N):
        t0 = time.perf_counter(); c.list_tools(); lst.append((time.perf_counter()-t0)*1000)
        t0 = time.perf_counter(); c.call("send_report", {"to": "team@corp.example", "body": "x"}); cal.append((time.perf_counter()-t0)*1000)
    c.close(); shutil.rmtree(work, ignore_errors=True)
    q = lambda a, p: sorted(a)[int(p*(len(a)-1))]
    return {"list_p50": round(q(lst,.5),3), "list_p95": round(q(lst,.95),3), "call_p50": round(q(cal,.5),3), "call_p95": round(q(cal,.95),3)}
d, p = bench(True), bench(False)
res = {"direct": d, "proxied": p,
       "added_call_p50_ms": round(p["call_p50"]-d["call_p50"],3), "added_list_p50_ms": round(p["list_p50"]-d["list_p50"],3)}
json.dump(res, open(os.path.join(HERE, "..", "results", "proto_overhead.json"), "w"), indent=1)
print(json.dumps(res, indent=1))
