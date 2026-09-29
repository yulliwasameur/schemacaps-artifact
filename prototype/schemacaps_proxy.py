#!/usr/bin/env python3
"""SchemaCaps client-side proxy (prototype).

A stdio MCP proxy between an agent client and a tool server. It keeps, per tool, the input schema under which the
delegator approved the tool (the capability's schema fingerprint), and applies one of three rules whenever the
server publishes a tool list:

  pin     : any change to a tool definition suspends the tool until re-approval (ETDI / drift detection);
  compat  : a schema change suspends the tool unless jsonsubschema proves it backward compatible;
  nonamp  : the SchemaCaps rule: a schema change re-binds the capability silently iff it is non-amplifying on
            authority-bearing paths and undeclared fields (classify2.analyse: not amp_strict, not undecided);
            a description-only change is ignored; a raised tool hint suspends.

Suspended or not-yet-approved tools are removed from the list returned to the client and their calls are refused
with an isError result naming the reason. Every re-binding is recorded as a signed migration receipt (Ed25519,
prototype key) in the state file: the capability's lineage.

Usage:  schemacaps_proxy.py --state S.json [--rule nonamp|pin|compat] [--trust-first-use] [--policy P.json]
                            -- <server command...>
        schemacaps_proxy.py approve --state S.json [--tool NAME | --all]
"""
import sys, os, json, time, threading, subprocess, hashlib, argparse, re
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import classify2                                   # the rule of the paper (deviation 9 version)
from classify import sub, resolve_local_refs, clean, canon
import jsonschema
import classify as _classify
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

def fp(schema):
    return hashlib.sha256(canon(clean(resolve_local_refs(schema or {}))).encode()).hexdigest()[:16]

class State:
    def __init__(self, path):
        self.path = path
        self.d = json.load(open(path)) if os.path.exists(path) else {"tools": {}, "receipts": [], "key": None}
        if not self.d.get("key"):
            k = Ed25519PrivateKey.generate()
            self.d["key"] = k.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw,
                                            serialization.NoEncryption()).hex()
        self.key = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(self.d["key"]))
    def save(self):
        json.dump(self.d, open(self.path, "w"), indent=1, ensure_ascii=False)
    def receipt(self, tool, h_prev, h_new, version, verdict, reasons):
        body = {"tool": tool, "h_prev": h_prev, "h_new": h_new, "server_version": version, "verdict": verdict,
                "reasons": reasons, "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "prev_receipt": hashlib.sha256(canon(self.d["receipts"][-1]).encode()).hexdigest()[:16] if self.d["receipts"] else None}
        body["sig"] = self.key.sign(canon(body).encode()).hex()
        self.d["receipts"].append(body)

def decide(rule, old_tool, new_tool):
    """Returns (verdict, reasons): verdict in {'unchanged', 'rebind', 'suspend'}."""
    a = classify2.analyse(old_tool, new_tool)
    def_changed = a["schema_changed"] or a["desc_changed"] or a["title_changed"] or a["annot_changed"]
    if not def_changed:
        return "unchanged", []
    if rule == "pin":
        return "suspend", ["definition_changed"]
    if rule == "compat":
        if not a["schema_changed"]:
            return "rebind", ["description_only"]
        return ("rebind", ["backward_compatible"]) if a["compatible"] is True else ("suspend", ["not_provably_compatible"])
    # nonamp
    if a.get("amp_strict") or a.get("undecided"):
        return "suspend", a["reasons"] or ["undecided"]
    return "rebind", ["non_amplifying"] + a["reasons"]

class Proxy:
    def __init__(self, args):
        self.rule, self.tofu = args.rule, args.trust_first_use
        self.state = State(args.state)
        self.policy = json.load(open(args.policy)) if args.policy else {}
        if args.roles:                               # role manifest (prototype: extra authority-bearing leaf names)
            extra = set(json.load(open(args.roles)).get("authority_leaves", []))
            base = _classify.is_authority
            classify2.is_authority = lambda name, _b=base, _e=extra: _b(name) or name in _e
        self.log = open(args.log, "a") if args.log else None
        self.pending_list = {}; self.server_version = None; self.lock = threading.Lock()
        self.srv = subprocess.Popen(args.server, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                    stderr=open(os.devnull, "w"), text=True, bufsize=1, env=dict(os.environ))
        self.out = sys.stdout
    def emit(self, o):
        self.out.write(json.dumps(o, ensure_ascii=False) + "\n"); self.out.flush()
    def to_server(self, o):
        self.srv.stdin.write(json.dumps(o, ensure_ascii=False) + "\n"); self.srv.stdin.flush()
    def logline(self, **kw):
        if self.log: self.log.write(json.dumps(kw, ensure_ascii=False) + "\n"); self.log.flush()

    # ---- client -> server -------------------------------------------------------------------------------------
    def client_loop(self):
        for line in sys.stdin:
            line = line.strip()
            if not line: continue
            try: msg = json.loads(line)
            except Exception: continue
            m = msg.get("method")
            if m == "tools/list" and "id" in msg:
                self.pending_list[msg["id"]] = True
            elif m == "tools/call" and "id" in msg:
                refused = self.check_call(msg)
                if refused:
                    self.emit({"jsonrpc": "2.0", "id": msg["id"],
                               "result": {"content": [{"type": "text", "text": refused}], "isError": True}})
                    self.logline(event="call_refused", tool=msg["params"].get("name"), reason=refused); continue
                self.logline(event="call_forwarded", tool=msg["params"].get("name"))
            self.to_server(msg)
        try: self.srv.stdin.close()
        except Exception: pass

    def check_call(self, msg):
        name = (msg.get("params") or {}).get("name"); args = (msg.get("params") or {}).get("arguments") or {}
        t = self.state.d["tools"].get(name)
        if not t: return f"SchemaCaps: tool '{name}' is not approved by the delegator."
        if t["status"] != "bound":
            return f"SchemaCaps: tool '{name}' is suspended pending re-approval ({t['status']}): " + "; ".join(t.get("reasons", []))
        # policy P on effective authority values
        pol = self.policy.get(name) or {}
        props = (t["tool"].get("inputSchema") or {}).get("properties") or {}
        for path, cons in pol.items():
            v = args.get(path, (props.get(path) or {}).get("default"))
            if v is None:
                if cons.get("allow_absent", False): continue
                return f"SchemaCaps policy: '{name}.{path}' must be given."
            ok = (re.fullmatch(cons["regex"], str(v)) is not None) if "regex" in cons else (v in cons.get("enum", []))
            if not ok: return f"SchemaCaps policy: '{name}.{path}' = {json.dumps(v)} is not authorised."
        return None

    # ---- server -> client -------------------------------------------------------------------------------------
    def server_loop(self):
        for line in self.srv.stdout:
            line = line.strip()
            if not line: continue
            try: msg = json.loads(line)
            except Exception: continue
            if "id" in msg and msg["id"] in self.pending_list and "result" in msg:
                self.pending_list.pop(msg["id"])
                msg["result"]["tools"] = self.on_tool_list(msg["result"].get("tools") or [])
            elif "result" in msg and isinstance(msg["result"], dict) and "serverInfo" in msg["result"]:
                self.server_version = (msg["result"]["serverInfo"] or {}).get("version")
            self.emit(msg)

    def on_tool_list(self, tools):
        with self.lock:
            visible = []
            for tl in tools:
                name = tl["name"]; h_new = fp(tl.get("inputSchema"))
                t = self.state.d["tools"].get(name)
                if t is None:
                    if self.tofu:
                        self.state.d["tools"][name] = {"h": h_new, "tool": tl, "status": "bound", "reasons": [], "approved_version": self.server_version}
                        self.state.receipt(name, None, h_new, self.server_version, "granted", ["trust_on_first_use"])
                        visible.append(tl); self.logline(event="granted", tool=name)
                    else:
                        self.state.d["tools"][name] = {"h": h_new, "tool": tl, "status": "pending_approval", "reasons": ["new_tool"]}
                        self.logline(event="new_tool_pending", tool=name)
                    continue
                verdict, reasons = decide(self.rule, t["tool"], tl)
                if verdict == "unchanged":
                    if t["status"] == "bound": visible.append(tl)
                elif verdict == "rebind":
                    self.state.receipt(name, t["h"], h_new, self.server_version, "rebind", reasons)
                    t.update(h=h_new, tool=tl);
                    if t["status"] == "bound": visible.append(tl)
                    self.logline(event="rebind", tool=name, reasons=reasons)
                else:
                    t.update(status="suspended", reasons=reasons, candidate=tl, candidate_h=h_new)
                    self.state.receipt(name, t["h"], h_new, self.server_version, "suspend", reasons)
                    self.logline(event="suspend", tool=name, reasons=reasons)
            self.state.save()
            return visible

    def run(self):
        threading.Thread(target=self.server_loop, daemon=True).start()
        self.client_loop()
        try: self.srv.wait(timeout=3)
        except Exception: self.srv.kill()

def approve(args):
    st = State(args.state)
    for name, t in st.d["tools"].items():
        if args.all or name == args.tool:
            if t["status"] == "suspended" and t.get("candidate"):
                t.update(h=t["candidate_h"], tool=t["candidate"]); st.receipt(name, None, t["h"], None, "approved", ["delegator_consent"])
            elif t["status"] == "pending_approval":
                st.receipt(name, None, t["h"], None, "granted", ["delegator_consent"])
            t.update(status="bound", reasons=[]); t.pop("candidate", None); t.pop("candidate_h", None)
    st.save()

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "approve":
        p = argparse.ArgumentParser(); p.add_argument("cmd"); p.add_argument("--state", required=True)
        p.add_argument("--tool"); p.add_argument("--all", action="store_true"); approve(p.parse_args()); sys.exit(0)
    p = argparse.ArgumentParser()
    p.add_argument("--state", required=True); p.add_argument("--rule", default="nonamp", choices=["nonamp", "pin", "compat"])
    p.add_argument("--trust-first-use", action="store_true"); p.add_argument("--policy"); p.add_argument("--log")
    p.add_argument("--roles")
    p.add_argument("server", nargs=argparse.REMAINDER)
    a = p.parse_args()
    if a.server and a.server[0] == "--": a.server = a.server[1:]
    Proxy(a).run()
