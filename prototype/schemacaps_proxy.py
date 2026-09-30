#!/usr/bin/env python3
"""SchemaCaps client-side proxy (research prototype), revision 2.

A stdio MCP proxy between an agent client and one tool server. For every approved tool it keeps a capability

    c = (id_srv, t, h_S, h_A, U, P)

  id_srv  server identity: SHA-256 of the canonical launch command, plus the serverInfo.name the server reports;
  t       the tool name;
  h_S     SHA-256 of the canonical input schema the capability is bound to;
  h_A     SHA-256 of the role-manifest entry in force for t. The manifest labels declared paths `authority` or
          `inert`; a path it does not list is UNKNOWN and is treated as authority-bearing (confirm, never assume safe).
          Without a manifest every path is unknown: the rule is then label-free;
  U       the capability's coordinates: every declared path with its role, one star entry per object (closed or
          open). U is cumulative: a coordinate stays in U once the delegator has consented to it;
  P       the delegator's policy for t: constraints on effective authority values; h_P is its SHA-256.

Rules applied when the server publishes a tool list:
  pin     any change of a tool definition suspends the tool;
  compat  a schema change suspends the tool unless the guarded subschema check proves backward compatibility;
  nonamp  SchemaCaps: a change re-binds silently iff it admits no new value on any authority coordinate (unknown
          roles included) or on any star coordinate; otherwise the tool is suspended until the delegator approves.
          Compatibility plays no part in this decision (an incompatible narrowing re-binds, a compatible widening asks).
A change of server identity suspends every tool of that server; a manifest change that relabels an authority path
as inert suspends the tool (relaxing the labelling needs consent); a tightening re-binds with a receipt.

Calls: refused unless the tool is bound; validated against the bound schema (JSON Schema validator of its dialect);
P evaluated on effective values (given value, else the declared default, else absent), on nested paths (a.b) and on
every array element (a[].b); JSON null is a value, never confused with absence.

Receipts: every grant, re-bind, suspension, approval and manifest or policy change appends a receipt carrying an
explicit sequence number, the server identity, full SHA-256 digests (h_S before and after, h_A, h_U, h_P), the
verdict, the reasons, the digest of the previous receipt and an Ed25519 signature. `verify` checks the whole chain.
The signing key is kept in <state>.key with mode 0600 (a deployment would use an OS keystore). NOT implemented:
publication to a transparency log; the receipts are a local, verifiable audit trail.

Usage:
  schemacaps_proxy.py --state S.json [--rule nonamp|pin|compat] [--trust-first-use] [--policy P.json]
                      [--roles MANIFEST.json] [--labeller free|lexical] [--log L.jsonl] -- <server command...>
  schemacaps_proxy.py approve --state S.json (--tool NAME | --all) [--policy P.json] [--roles MANIFEST.json]
  schemacaps_proxy.py verify  --state S.json
"""
import sys, os, json, time, subprocess, hashlib, argparse, re

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
import classify2                                                     # the rule of the paper (deviation 10)
from classify2 import analyse, walk, leaf, LEXICAL, LABEL_FREE, norm_schema
from classify import resolve_local_refs, clean, canon
import jsonschema
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives import serialization
from cryptography.exceptions import InvalidSignature

FORMAT = "schemacaps-state/2"
ABSENT = object()                                                    # the absent value (⊥)


def sha(o):
    """Full SHA-256 (256 bits) of the canonical JSON form."""
    return hashlib.sha256(canon(o).encode()).hexdigest()


def schema_of(tool):
    return resolve_local_refs(norm_schema((tool or {}).get("inputSchema")))


def h_schema(tool):
    return sha(clean(schema_of(tool)))


# ---------------------------------------------------------------------------------------------- role manifest
class Manifest:
    """{"manifest_version": n, "tools": {tool: {"authority": [paths], "inert": [paths]}}}.
    Legacy prototype format {"authority_leaves": [...]} is read as authority leaf names for every tool."""

    def __init__(self, path=None, fallback="free"):
        d = json.load(open(path)) if path else {}
        self.version = d.get("manifest_version", 0)
        self.tools = d.get("tools", {})
        self.legacy = sorted(d.get("authority_leaves", []))
        self.fallback = fallback

    def entry(self, tool):
        e = self.tools.get(tool, {})
        return {"manifest_version": self.version, "tool": tool, "authority": sorted(e.get("authority", [])),
                "inert": sorted(e.get("inert", [])), "legacy_authority_leaves": self.legacy,
                "unknown_is": "authority" if self.fallback == "free" else "lexical"}

    def h_A(self, tool):
        return sha(self.entry(tool))

    @staticmethod
    def role_in(entry, p):
        if p in entry["authority"] or leaf(p) in entry["legacy_authority_leaves"]:
            return "authority"
        if p in entry["inert"]:
            return "inert"
        return "unknown"

    @staticmethod
    def labeller_for(entry):
        fb = LABEL_FREE if entry["unknown_is"] == "authority" else LEXICAL
        def lab(p):
            r = Manifest.role_in(entry, p)
            return True if r == "authority" else (False if r == "inert" else fb(p))
        return lab


def coordinates(tool, entry):
    """U for one schema: declared paths with role and authority flag, plus one star coordinate per object."""
    decl, objs = walk(schema_of(tool))[:2]
    lab = Manifest.labeller_for(entry)
    u = [{"path": p, "role": Manifest.role_in(entry, p), "authority": bool(lab(p))} for p in sorted(decl)]
    u += [{"path": (o or "<root>") + ".*", "closed": bool(c)} for o, c in sorted(objs.items())]
    return u


def merge_U(old, new):
    """Cumulative U: coordinates stay once consented; the current schema's view of each path wins."""
    by = {c["path"]: c for c in (old or [])}
    by.update({c["path"]: c for c in new})
    return [by[k] for k in sorted(by)]


# ---------------------------------------------------------------------------------------------- the rules
def decide(rule, old_tool, new_tool, labeller=LABEL_FREE):
    """Returns (verdict, reasons): verdict in {'unchanged', 'rebind', 'suspend'}."""
    a = analyse(old_tool, new_tool, labeller)
    changed = a["schema_changed"] or a["desc_changed"] or a["title_changed"] or a["annot_changed"]
    if not changed:
        return "unchanged", []
    if rule == "pin":
        return "suspend", ["definition_changed"]
    if rule == "compat":
        if not a["schema_changed"]:
            return "rebind", ["description_only"]
        return ("rebind", ["backward_compatible"]) if a["compatible"] is True else ("suspend", ["not_provably_compatible"])
    if a.get("amp_strict") or a.get("undecided"):
        return "suspend", a["reasons"] or ["undecided"]
    return "rebind", ["non_amplifying"] + a["reasons"]


def relaxed_paths(old_entry, new_entry, tool):
    """Paths of the bound schema that were authority-bearing and become inert under the new manifest entry."""
    lo, ln = Manifest.labeller_for(old_entry), Manifest.labeller_for(new_entry)
    decl = walk(schema_of(tool))[0]
    return sorted(p for p in decl if lo(p) and not ln(p))


# ---------------------------------------------------------------------------------------------- policy on calls
def values_at(args, path, schema):
    """Effective values of `path` in a call: the given value, else the declared default, else ABSENT.
    Array segments (name[]) yield one value per element; JSON null is returned as None (a value)."""
    segs = path.split(".")

    def rec(x, i, node):
        if i == len(segs):
            return [x]
        seg = segs[i]; arr = seg.endswith("[]"); name = seg[:-2] if arr else seg
        sub = ((node or {}).get("properties") or {}).get(name) if isinstance(node, dict) else None
        sub = norm_schema(sub) if sub is not None else None
        if isinstance(x, dict) and name in x:
            v = x[name]
        elif isinstance(sub, dict) and "default" in sub:
            v = sub["default"]
        else:
            return [ABSENT]
        if arr:
            if not isinstance(v, list):
                return [v]
            it = sub.get("items") if isinstance(sub, dict) else None
            out = []
            for el in v:
                out += rec(el, i + 1, it)
            return out
        return rec(v, i + 1, sub)

    return rec(args, 0, schema)


def satisfies(v, c):
    if v is ABSENT:
        return bool(c.get("allow_absent", False))
    if v is None:
        return bool(c.get("allow_null", False)) or ("enum" in c and None in c["enum"])
    if "const" in c and v != c["const"]:
        return False
    if "enum" in c and v not in c["enum"]:
        return False
    if "regex" in c and not (isinstance(v, str) and re.fullmatch(c["regex"], v)):
        return False
    if "prefix" in c and not (isinstance(v, str) and v.startswith(c["prefix"])):
        return False
    return True


def undeclared_keys(args, loc, schema):
    """Keys present in the call at object location `loc` ('' = root) that the bound schema does not declare."""
    node, x = schema, args
    if loc:
        for seg in loc.split("."):
            node = ((node or {}).get("properties") or {}).get(seg) if isinstance(node, dict) else None
            x = x.get(seg) if isinstance(x, dict) else None
    if not isinstance(x, dict):
        return []
    declared = set(((node or {}).get("properties") or {}).keys()) if isinstance(node, dict) else set()
    return sorted(k for k in x if k not in declared)


def check_call(cap, args, policy):
    """None if the call may be forwarded, else the refusal reason."""
    schema = schema_of(cap["tool"])
    try:
        jsonschema.validators.validator_for(schema)(schema).validate(args)
    except jsonschema.ValidationError as e:
        return f"schema_violation: {e.message}"
    except jsonschema.SchemaError as e:
        return f"invalid_bound_schema: {e.message}"
    for path, c in (policy or {}).items():
        if path == "*" or path.endswith(".*"):
            loc = "" if path == "*" else path[:-2]
            extra = undeclared_keys(args, loc, schema)
            if c.get("deny") and extra:
                return f"policy: undeclared field(s) {extra} at {loc or '<root>'} not authorised"
            continue
        for v in values_at(args, path, schema):
            if not satisfies(v, c):
                shown = "absent" if v is ABSENT else json.dumps(v)
                return f"policy: {cap['tool']['name']}.{path} = {shown} not authorised"
    return None


# ---------------------------------------------------------------------------------------------- state, receipts
class State:
    def __init__(self, path):
        self.path, self.keypath = path, path + ".key"
        self.d = json.load(open(path)) if os.path.exists(path) else {"format": FORMAT, "tools": {}, "receipts": []}
        if os.path.exists(self.keypath):
            self.key = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(open(self.keypath).read().strip()))
        else:
            self.key = Ed25519PrivateKey.generate()
            fd = os.open(self.keypath, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w") as f:
                f.write(self.key.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw,
                                               serialization.NoEncryption()).hex())
        self.d["pub"] = self.key.public_key().public_bytes(serialization.Encoding.Raw,
                                                           serialization.PublicFormat.Raw).hex()
        self.d.pop("key", None)                                       # never keep a private key in the state file

    def save(self):
        tmp = self.path + ".tmp"
        json.dump(self.d, open(tmp, "w"), indent=1, ensure_ascii=False)
        os.replace(tmp, self.path)

    def receipt(self, tool, verdict, reasons, server, h_prev=None, cap=None):
        rs = self.d["receipts"]
        body = {"seq": len(rs), "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "prev": sha(rs[-1]) if rs else None, "server": server, "tool": tool, "verdict": verdict,
                "reasons": list(reasons), "h_S_prev": h_prev,
                "h_S": cap.get("h_S") if cap else None, "h_A": cap.get("h_A") if cap else None,
                "h_U": cap.get("h_U") if cap else None, "h_P": cap.get("h_P") if cap else None}
        body["sig"] = self.key.sign(canon(body).encode()).hex()
        rs.append(body)
        return body


def verify(path):
    """Checks sequence numbers, the hash chain, every signature, and per-tool schema lineage. Returns (ok, report)."""
    d = json.load(open(path))
    pub = Ed25519PublicKey.from_public_bytes(bytes.fromhex(d["pub"]))
    prev, last = None, {}
    for i, r in enumerate(d["receipts"]):
        if r.get("seq") != i:
            return False, f"receipt {i}: sequence number {r.get('seq')}"
        if r.get("prev") != (sha(prev) if prev else None):
            return False, f"receipt {i}: broken hash chain"
        body = {k: v for k, v in r.items() if k != "sig"}
        try:
            pub.verify(bytes.fromhex(r["sig"]), canon(body).encode())
        except (InvalidSignature, ValueError):
            return False, f"receipt {i}: bad signature"
        t = r["tool"]
        if r["verdict"] == "rebind" and last.get(t) not in (None, r["h_S_prev"]):
            return False, f"receipt {i}: re-bind of {t} does not start from its bound schema"
        if r["verdict"] in ("granted", "approved", "rebind", "manifest_rebind", "policy_rebind") and r.get("h_S"):
            last[t] = r["h_S"]
        prev = r
    for name, cap in d.get("tools", {}).items():
        if cap.get("status") == "bound" and last.get(name) != cap.get("h_S"):
            return False, f"tool {name}: bound schema not covered by the receipt chain"
    return True, f"{len(d['receipts'])} receipts verified"


def new_capability(tool, entry, policy_t, server, status):
    u = coordinates(tool, entry)
    return {"tool": tool, "status": status, "reasons": [], "server": server, "h_S": h_schema(tool),
            "A_entry": entry, "h_A": sha(entry), "U": u, "h_U": sha(u), "P": policy_t or {}, "h_P": sha(policy_t or {})}


# ---------------------------------------------------------------------------------------------- proxy
class Proxy:
    def __init__(self, args):
        self.rule, self.tofu = args.rule, args.trust_first_use
        self.state = State(args.state)
        self.policy = json.load(open(args.policy)) if args.policy else {}
        self.manifest = Manifest(args.roles, fallback=args.labeller)
        self.log = open(args.log, "a") if args.log else None
        self.pending_list = {}; self.server_name = None; self.server_version = None
        self.launch = sha(args.server)
        self.srv = subprocess.Popen(args.server, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                    stderr=open(os.devnull, "w"), bufsize=0, env=dict(os.environ))

    def server_id(self):
        return {"launch": self.launch, "name": self.server_name, "version": self.server_version}

    def emit(self, o):
        sys.stdout.buffer.write((json.dumps(o, ensure_ascii=False) + "\n").encode()); sys.stdout.buffer.flush()

    def to_server(self, o):
        try:
            self.srv.stdin.write((json.dumps(o, ensure_ascii=False) + "\n").encode()); self.srv.stdin.flush()
        except (BrokenPipeError, ValueError):
            pass

    def logline(self, **kw):
        if self.log:
            self.log.write(json.dumps(kw, ensure_ascii=False) + "\n"); self.log.flush()

    # Single-threaded event loop (revision 2): the rule, the guarded checker and its timeouts run in the main
    # thread; both pipes are read with os.read and split into lines here, so no buffered line is ever stranded.
    def on_client_line(self, line):
        try:
            msg = json.loads(line)
        except Exception:
            return
        m = msg.get("method")
        if m == "tools/list" and "id" in msg:
            self.pending_list[msg["id"]] = True
        elif m == "tools/call" and "id" in msg:
            p = msg.get("params") or {}
            refused = self.refuse(p.get("name"), p.get("arguments") or {})
            if refused:
                self.emit({"jsonrpc": "2.0", "id": msg["id"],
                           "result": {"content": [{"type": "text", "text": "SchemaCaps: " + refused}], "isError": True}})
                self.logline(event="call_refused", tool=p.get("name"), reason=refused)
                return
            self.logline(event="call_forwarded", tool=p.get("name"))
        self.to_server(msg)

    def refuse(self, name, args):
        cap = self.state.d["tools"].get(name)
        if not cap:
            return f"tool '{name}' is not approved by the delegator."
        if cap["status"] != "bound":
            return f"tool '{name}' is suspended pending re-approval ({cap['status']}): " + "; ".join(cap.get("reasons", []))
        return check_call(cap, args, cap.get("P"))

    def on_server_line(self, line):
        try:
            msg = json.loads(line)
        except Exception:
            return
        if "id" in msg and msg["id"] in self.pending_list and "result" in msg:
            self.pending_list.pop(msg["id"])
            msg["result"]["tools"] = self.on_tool_list(msg["result"].get("tools") or [])
        elif "result" in msg and isinstance(msg["result"], dict) and "serverInfo" in msg["result"]:
            si = msg["result"]["serverInfo"] or {}
            self.server_name, self.server_version = si.get("name"), si.get("version")
        self.emit(msg)

    def on_tool_list(self, tools):
        if True:
            visible, srv = [], self.server_id()
            for tl in tools:
                name = tl["name"]; cap = self.state.d["tools"].get(name)
                entry = self.manifest.entry(name); pol = self.policy.get(name) or {}
                if cap is None:
                    status = "bound" if self.tofu else "pending_approval"
                    cap = new_capability(tl, entry, pol, srv, status)
                    self.state.d["tools"][name] = cap
                    if self.tofu:
                        self.state.receipt(name, "granted", ["trust_on_first_use"], srv, None, cap)
                        visible.append(tl)
                    else:
                        cap["reasons"] = ["new_tool"]
                    self.logline(event="granted" if self.tofu else "new_tool_pending", tool=name)
                    continue
                # server identity
                bound_srv = cap.get("server") or {}
                if bound_srv.get("launch") != srv["launch"] or bound_srv.get("name") != srv["name"]:
                    if cap["status"] == "bound":
                        cap.update(status="suspended", reasons=["server_identity_changed"], suspended_by="server")
                        self.state.receipt(name, "suspend", ["server_identity_changed"], srv, cap["h_S"], cap)
                    cap.update(candidate=tl, candidate_server=srv)
                    continue
                # role manifest
                if sha(entry) != cap.get("h_A"):
                    relaxed = relaxed_paths(cap["A_entry"], entry, cap["tool"])
                    if relaxed and cap["status"] == "bound":
                        cap.update(status="suspended", reasons=[f"manifest_relaxed:{p}" for p in relaxed], candidate=tl,
                                   candidate_entry=entry, suspended_by="manifest")
                        self.state.receipt(name, "suspend", cap["reasons"], srv, cap["h_S"], cap)
                        continue
                    if not relaxed:
                        u = merge_U(cap["U"], coordinates(cap["tool"], entry))
                        cap.update(A_entry=entry, h_A=sha(entry), U=u, h_U=sha(u))
                        self.state.receipt(name, "manifest_rebind", ["manifest_tightened_or_equal"], srv, cap["h_S"], cap)
                # policy (owned by the delegator)
                if sha(pol) != cap.get("h_P"):
                    cap.update(P=pol, h_P=sha(pol))
                    self.state.receipt(name, "policy_rebind", ["delegator_policy_changed"], srv, cap["h_S"], cap)
                # the rule
                verdict, reasons = decide(self.rule, cap["tool"], tl, Manifest.labeller_for(cap["A_entry"]))
                if verdict == "unchanged":
                    if cap["status"] == "bound":
                        visible.append(tl)
                    elif cap.get("suspended_by") == "rule":
                        # the server republished exactly the bound definition: nothing new is admitted
                        for k in ("candidate", "candidate_entry", "candidate_server", "suspended_by"):
                            cap.pop(k, None)
                        cap.update(status="bound", reasons=[])
                        self.state.receipt(name, "rebind", ["bound_definition_republished", "suspension_lifted"],
                                           srv, cap["h_S"], cap)
                        visible.append(tl)
                elif verdict == "rebind":
                    if cap["status"] != "bound" and cap.get("suspended_by") not in (None, "rule"):
                        continue                                    # identity/manifest suspension: consent needed
                    lifted = cap["status"] != "bound"
                    h_prev = cap["h_S"]
                    u = merge_U(cap["U"], coordinates(tl, cap["A_entry"]))
                    cap.update(tool=tl, h_S=h_schema(tl), U=u, h_U=sha(u), server=srv, status="bound")
                    for k in ("candidate", "candidate_entry", "candidate_server", "suspended_by"):
                        cap.pop(k, None)
                    cap["reasons"] = []
                    self.state.receipt(name, "rebind", reasons + (["suspension_lifted"] if lifted else []), srv, h_prev, cap)
                    visible.append(tl)
                    self.logline(event="rebind", tool=name, reasons=reasons)
                else:
                    if cap["status"] == "bound":
                        cap.update(status="suspended", reasons=reasons, suspended_by="rule")
                        self.state.receipt(name, "suspend", reasons, srv, cap["h_S"], cap)
                    cap["candidate"] = tl
                    self.logline(event="suspend", tool=name, reasons=reasons)
            self.state.save()
            return visible

    def run(self):
        import select
        cfd, sfd = sys.stdin.fileno(), self.srv.stdout.fileno()
        bufs, live = {cfd: b"", sfd: b""}, {cfd, sfd}
        handlers = {cfd: self.on_client_line, sfd: self.on_server_line}
        while live:
            ready, _, _ = select.select(list(live), [], [])
            for fd in ready:
                data = os.read(fd, 65536)
                if not data:
                    live.discard(fd)
                    if bufs[fd].strip():
                        handlers[fd](bufs[fd].decode()); bufs[fd] = b""
                    if fd == cfd:                                   # client closed: close the server's stdin
                        try:
                            self.srv.stdin.close()
                        except Exception:
                            pass
                    continue
                bufs[fd] += data
                while b"\n" in bufs[fd]:
                    line, bufs[fd] = bufs[fd].split(b"\n", 1)
                    if line.strip():
                        handlers[fd](line.decode())
        try:
            self.srv.wait(timeout=3)
        except Exception:
            self.srv.kill()


def approve(args):
    st = State(args.state)
    manifest = Manifest(args.roles, fallback=args.labeller) if args.roles else None
    policy = json.load(open(args.policy)) if args.policy else None
    for name, cap in st.d["tools"].items():
        if not (args.all or name == args.tool):
            continue
        if cap["status"] == "bound":
            continue
        h_prev = cap.get("h_S")
        tool = cap.get("candidate") or cap["tool"]
        entry = cap.get("candidate_entry") or (manifest.entry(name) if manifest else cap["A_entry"])
        pol = policy.get(name, {}) if policy is not None else cap.get("P", {})
        u = merge_U(cap.get("U"), coordinates(tool, entry))
        cap.update(tool=tool, h_S=h_schema(tool), A_entry=entry, h_A=sha(entry), U=u, h_U=sha(u), P=pol, h_P=sha(pol),
                   status="bound", reasons=[], server=cap.get("candidate_server") or cap.get("server"))
        verdict = "approved" if h_prev and h_prev != cap["h_S"] else "granted"
        st.receipt(name, verdict, ["delegator_consent"], cap.get("server"), h_prev, cap)
        for k in ("candidate", "candidate_entry", "candidate_server", "suspended_by"):
            cap.pop(k, None)
    st.save()


def main():
    if len(sys.argv) > 1 and sys.argv[1] in ("approve", "verify"):
        p = argparse.ArgumentParser(); p.add_argument("cmd"); p.add_argument("--state", required=True)
        p.add_argument("--tool"); p.add_argument("--all", action="store_true")
        p.add_argument("--policy"); p.add_argument("--roles"); p.add_argument("--labeller", default="free",
                                                                              choices=["free", "lexical"])
        a = p.parse_args()
        if a.cmd == "approve":
            approve(a); return 0
        ok, rep = verify(a.state); print(("OK: " if ok else "FAILED: ") + rep); return 0 if ok else 1
    p = argparse.ArgumentParser()
    p.add_argument("--state", required=True)
    p.add_argument("--rule", default="nonamp", choices=["nonamp", "pin", "compat"])
    p.add_argument("--trust-first-use", action="store_true"); p.add_argument("--policy"); p.add_argument("--log")
    p.add_argument("--roles"); p.add_argument("--labeller", default="free", choices=["free", "lexical"])
    p.add_argument("server", nargs=argparse.REMAINDER)
    a = p.parse_args()
    if a.server and a.server[0] == "--":
        a.server = a.server[1:]
    Proxy(a).run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
