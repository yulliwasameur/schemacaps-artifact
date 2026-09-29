import csv,json,time,statistics,glob,os
from classify2 import analyse as analyse_tool
from witness import load
ch=[r for r in csv.DictReader(open("results/v2_changes.csv")) if r["schema_changed"]=="True"]
ts=[]
for r in ch:
    o=[t for t in load(r["package"],r["from"])["tools"] if t["name"]==r["tool"]][0]
    n=[t for t in load(r["package"],r["to"])["tools"] if t["name"]==r["tool"]][0]
    t0=time.perf_counter(); analyse_tool(o,n); ts.append(time.perf_counter()-t0)
ts.sort()
q=lambda p: ts[int(p*(len(ts)-1))]*1000
json.dump({"n":len(ts),"median_ms":round(q(.5),1),"p90_ms":round(q(.9),1),"p99_ms":round(q(.99),1),"max_ms":round(ts[-1]*1000,1)},open("results/v2_timing.json","w"),indent=1)
print(open("results/v2_timing.json").read())
