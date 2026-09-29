#!/usr/bin/env python3
"""Seconde passe (écart n° 6) : pour les versions en échec « no_response », client JSON-RPC brut, sans validation
stricte des modèles du SDK Python (qui rejette des définitions d'outils pourtant servies aux clients réels)."""
import json, os, sys, time, glob, shutil, tempfile, hashlib, subprocess, select
import extract

ROOT = os.path.dirname(os.path.abspath(__file__))
W = os.path.join(ROOT, "work"); os.makedirs(W, exist_ok=True)
EXTRA = {"@azure/mcp": [["server", "start", "--transport", "stdio"]]}

def rpc_list(cmd, args, env, cwd, timeout=35):
    p = subprocess.Popen([cmd] + args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                         text=True, env=env, cwd=cwd, bufsize=1)
    def send(o): p.stdin.write(json.dumps(o) + "\n"); p.stdin.flush()
    deadline = time.time() + timeout
    buf, info, proto, tools, cursor, want = "", None, None, [], None, 1
    try:
        send({"jsonrpc": "2.0", "id": 1, "method": "initialize",
              "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "schemacaps", "version": "1"}}})
        while time.time() < deadline:
            r, _, _ = select.select([p.stdout], [], [], 1.0)
            if not r:
                if p.poll() is not None: break
                continue
            line = p.stdout.readline()
            if not line: break
            try: msg = json.loads(line)
            except Exception: continue
            if not isinstance(msg, dict) or msg.get("id") != want: continue
            if "error" in msg: raise RuntimeError(str(msg["error"])[:200])
            res = msg.get("result") or {}
            if want == 1:
                info, proto = res.get("serverInfo"), res.get("protocolVersion")
                send({"jsonrpc": "2.0", "method": "notifications/initialized"})
                want = 2; send({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
            else:
                tools += res.get("tools") or []
                cursor = res.get("nextCursor")
                if not cursor: return info, proto, tools
                want += 1; send({"jsonrpc": "2.0", "id": want, "method": "tools/list", "params": {"cursor": cursor}})
        raise TimeoutError("no tools/list response")
    finally:
        try: p.kill()
        except Exception: pass

def main():
    corpus = json.load(open(os.path.join(ROOT, "corpus_versions.json")))
    for f in sorted(glob.glob(os.path.join(ROOT, "raw", "*.json"))):
        rec = json.load(open(f))
        if rec["status"] != "no_response" or "error_pass2" in rec: continue
        pkg, ver, eco = rec["package"], rec["version"], rec["ecosystem"]
        d = tempfile.mkdtemp(prefix="r2_", dir=W); tmp = tempfile.mkdtemp(prefix="run_", dir=W)
        try:
            ok, err, _ = extract.install(pkg, eco, ver, d, rec["published"])
            if not ok:
                continue
            cmd, pre, extra = extract.command_for(pkg, eco, d)
            env = dict(os.environ, **extract.DUMMY, **extra, HOME=tmp)
            variants = EXTRA.get(pkg, []) + [extract.base_args(pkg, tmp)] + [v for v in extract.VARIANTS if v is not None]
            last = None
            for a in variants:
                try:
                    info, proto, tools = rpc_list(cmd, pre + a, env, tmp)
                    rec.update(status="ok", variant=[x.replace(tmp, "{TMP}") for x in a], serverInfo=info, protocolVersion=proto,
                               tools=tools, client="raw_jsonrpc_pass2",
                               tools_sha256=hashlib.sha256(extract.canon(sorted(tools, key=lambda t: t["name"])).encode()).hexdigest())
                    rec.pop("error", None)
                    break
                except Exception as e:
                    last = f"{type(e).__name__}: {str(e)[:200]}"
            if rec["status"] != "ok":
                rec["error_pass2"] = last
            json.dump(rec, open(f, "w"), indent=1, ensure_ascii=False)
            print(pkg, ver, rec["status"], len(rec.get("tools", [])), flush=True)
        finally:
            shutil.rmtree(d, ignore_errors=True); shutil.rmtree(tmp, ignore_errors=True)
            for pid in subprocess.run(["pgrep", "-f", "agent-device/dist/src/daemon.js"], capture_output=True, text=True).stdout.split():
                subprocess.run(["kill", pid])

if __name__ == "__main__":
    main()
