#!/usr/bin/env python3
"""Écart n° 10 : extraction des versions intermédiaires (non échantillonnées) entre les deux versions de chaque cas
du tableau des cas réels, pour dater exactement l'apparition du changement. Sortie : raw_intermediates/.
Ne modifie pas raw/ ni les paires du pilote."""
import json, os, sys, tempfile, shutil, asyncio, hashlib, time, traceback
import extract
from extract_raw import rpc_list
ROOT = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(ROOT, "raw_intermediates"); os.makedirs(OUT, exist_ok=True)
W = os.path.join(ROOT, "work"); os.makedirs(W, exist_ok=True)
CASES = {"@wonderwhy-er/desktop-commander": ("0.1.30", "0.1.35"), "firecrawl-mcp": ("3.18.0", "3.20.3"),
         "@zereight/mcp-gitlab": ("1.0.69", "2.0.3"), "@sentry/mcp-server": ("0.4.0", "0.6.0"),
         "agent-device": ("0.17.0", "0.17.10")}
corpus = json.load(open(os.path.join(ROOT, "corpus_versions.json")))
def variant_of(pkg):
    import glob
    safe = pkg.replace("/", "__").replace("@", "")
    for f in glob.glob(os.path.join(ROOT, "raw", f"{safe}@*.json")):
        r = json.load(open(f))
        if r["status"] == "ok": return r.get("variant") or []
    return []
for pkg, (a, b) in CASES.items():
    m = corpus[pkg]; vs, ds = m["versions"], m["dates"]
    i, j = vs.index(a), vs.index(b)
    for k in range(i + 1, j):
        ver = vs[k]; safe = pkg.replace("/", "__").replace("@", ""); outf = os.path.join(OUT, f"{safe}@{ver}.json")
        if os.path.exists(outf): continue
        rec = {"package": pkg, "ecosystem": m["eco"], "strate": m["strate"], "version": ver, "published": ds[k], "index_in_window": k}
        d = tempfile.mkdtemp(prefix="im_", dir=W); tmp = tempfile.mkdtemp(prefix="run_", dir=W)
        try:
            ok, err, secs = extract.install(pkg, m["eco"], ver, d, ds[k])
            if not ok: rec.update(status="install_failed", error=err)
            else:
                cmd, pre, extra = extract.command_for(pkg, m["eco"], d)
                env = dict(os.environ, **extract.DUMMY, **extra, HOME=tmp)
                gv = [tmp if x == "{TMP}" else x for x in variant_of(pkg)]
                last = None
                for args in [gv] + [extract.base_args(pkg, tmp)] + [v for v in extract.VARIANTS if v is not None]:
                    try:
                        info, proto, tools = rpc_list(cmd, pre + args, env, tmp, timeout=45)
                        rec.update(status="ok", variant=[x.replace(tmp, "{TMP}") for x in args], serverInfo=info, protocolVersion=proto, tools=tools,
                                   tools_sha256=hashlib.sha256(extract.canon(sorted(tools, key=lambda t: t["name"])).encode()).hexdigest()); break
                    except Exception as e: last = f"{type(e).__name__}: {str(e)[:200]}"
                if rec.get("status") != "ok": rec.update(status="no_response", error=last)
        except Exception: rec.update(status="error", error=traceback.format_exc()[-500:])
        finally: shutil.rmtree(d, ignore_errors=True); shutil.rmtree(tmp, ignore_errors=True)
        json.dump(rec, open(outf, "w"), indent=1, ensure_ascii=False); print(pkg, ver, rec["status"], len(rec.get("tools", [])), flush=True)
