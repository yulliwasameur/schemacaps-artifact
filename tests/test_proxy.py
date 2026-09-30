"""Tests for the SchemaCaps proxy (prototype/schemacaps_proxy.py): call checks, policy on effective values, role
manifest semantics, receipt chain, and end-to-end runs through the staged server."""
import json, os, subprocess, sys, tempfile, warnings
warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, "prototype"))
import schemacaps_proxy as sp
from rawclient import Client

PY = sys.executable
PROXY = os.path.join(ROOT, "prototype", "schemacaps_proxy.py")
SERVER = os.path.join(ROOT, "prototype", "staged_server.py")
S = {"type": "string"}


def cap_for(schema, policy=None):
    tool = {"name": "t", "inputSchema": schema}
    return sp.new_capability(tool, sp.Manifest().entry("t"), policy or {}, {"launch": "x", "name": "n"}, "bound")


def obj(props, closed=True, required=()):
    s = {"type": "object", "properties": props}
    if closed:
        s["additionalProperties"] = False
    if required:
        s["required"] = list(required)
    return s


# ---------------------------------------------------------------------------------------------- call checks
def test_call_is_validated_against_the_bound_schema():
    cap = cap_for(obj({"path": S}))
    assert sp.check_call(cap, {"path": "/tmp/a"}, {}) is None
    assert sp.check_call(cap, {"path": 3}, {}).startswith("schema_violation")
    assert sp.check_call(cap, {"path": "/tmp/a", "cc": "x"}, {}).startswith("schema_violation")


def test_policy_on_nested_paths():
    cap = cap_for(obj({"target": obj({"path": S})}))
    pol = {"target.path": {"prefix": "/tmp/"}}
    assert sp.check_call(cap, {"target": {"path": "/tmp/x"}}, pol) is None
    assert "not authorised" in sp.check_call(cap, {"target": {"path": "/etc/passwd"}}, pol)


def test_policy_on_every_array_element():
    cap = cap_for(obj({"files": {"type": "array", "items": obj({"path": S})}}))
    pol = {"files[].path": {"prefix": "/tmp/"}}
    assert sp.check_call(cap, {"files": [{"path": "/tmp/a"}, {"path": "/tmp/b"}]}, pol) is None
    assert "not authorised" in sp.check_call(cap, {"files": [{"path": "/tmp/a"}, {"path": "/etc/b"}]}, pol)


def test_null_is_a_value_not_absence():
    cap = cap_for(obj({"regionUrl": {"type": ["string", "null"]}}))
    strict = {"regionUrl": {"regex": r"https://[a-z.]+\.example/.*"}}
    absent_ok = {"regionUrl": {"regex": r"https://[a-z.]+\.example/.*", "allow_absent": True}}
    assert "not authorised" in sp.check_call(cap, {"regionUrl": None}, strict)     # null refused
    assert "absent" in sp.check_call(cap, {}, strict)                              # absent refused
    assert sp.check_call(cap, {}, absent_ok) is None                               # absent allowed ...
    assert "not authorised" in sp.check_call(cap, {"regionUrl": None}, absent_ok)  # ... null still refused


def test_declared_default_is_the_effective_value():
    pol = {"path": {"prefix": "/tmp/"}}
    assert sp.check_call(cap_for(obj({"path": {"type": "string", "default": "/tmp/work"}})), {}, pol) is None
    assert "not authorised" in sp.check_call(cap_for(obj({"path": {"type": "string", "default": "/etc"}})), {}, pol)


def test_undeclared_fields_on_an_open_object_can_be_denied():
    cap = cap_for(obj({"to": S}, closed=False))
    assert sp.check_call(cap, {"to": "a", "webhookUrl": "https://evil"}, {}) is None
    assert "undeclared" in sp.check_call(cap, {"to": "a", "webhookUrl": "https://evil"}, {"*": {"deny": True}})


# ---------------------------------------------------------------------------------------------- manifest
def test_unknown_role_is_authority_and_inert_is_honoured():
    old = {"name": "t", "inputSchema": obj({"mode": {"type": "string", "enum": ["dry"]}})}
    new = {"name": "t", "inputSchema": obj({"mode": {"type": "string", "enum": ["dry", "run"]}})}
    unknown = sp.Manifest.labeller_for(sp.Manifest().entry("t"))
    assert sp.decide("nonamp", old, new, unknown)[0] == "suspend"
    m = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
    json.dump({"manifest_version": 1, "tools": {"t": {"inert": ["mode"]}}}, m); m.close()
    inert = sp.Manifest.labeller_for(sp.Manifest(m.name).entry("t"))
    assert sp.decide("nonamp", old, new, inert)[0] == "rebind"


def test_relabelling_authority_as_inert_is_detected():
    tool = {"name": "t", "inputSchema": obj({"mode": S, "path": S})}
    e0 = sp.Manifest().entry("t")
    e1 = dict(e0, inert=["mode"], manifest_version=2)
    assert sp.relaxed_paths(e0, e1, tool) == ["mode"]
    assert sp.relaxed_paths(e1, e0, tool) == []


def test_hashes_are_full_sha256():
    cap = cap_for(obj({"path": S}))
    for k in ("h_S", "h_A", "h_U", "h_P"):
        assert len(cap[k]) == 64, k


# ---------------------------------------------------------------------------------------------- receipts
def _chain(tmp):
    st = sp.State(os.path.join(tmp, "s.json"))
    cap = cap_for(obj({"path": S}))
    st.d["tools"]["t"] = cap
    st.receipt("t", "granted", ["delegator_consent"], {"launch": "x", "name": "n"}, None, cap)
    st.receipt("t", "suspend", ["new_authority_arg:shell"], {"launch": "x", "name": "n"}, cap["h_S"], cap)
    st.save()
    return st


def test_receipt_chain_verifies_and_key_is_separate():
    with tempfile.TemporaryDirectory() as tmp:
        _chain(tmp)
        ok, rep = sp.verify(os.path.join(tmp, "s.json"))
        assert ok, rep
        d = json.load(open(os.path.join(tmp, "s.json")))
        assert "key" not in d and len(d["pub"]) == 64
        assert oct(os.stat(os.path.join(tmp, "s.json.key")).st_mode & 0o777) == "0o600"


def test_tampering_is_detected():
    with tempfile.TemporaryDirectory() as tmp:
        _chain(tmp)
        p = os.path.join(tmp, "s.json")
        for mutate in (lambda d: d["receipts"][0].update(verdict="rebind"),       # edited field -> bad signature
                       lambda d: d["receipts"].pop(0),                            # deleted receipt -> sequence
                       lambda d: d["receipts"][1].update(prev="0" * 64)):         # rewired chain
            d = json.load(open(p)); mutate(d)
            q = os.path.join(tmp, "t.json"); json.dump(d, open(q, "w"))
            assert not sp.verify(q)[0]


# ---------------------------------------------------------------------------------------------- end to end
def _session(state, version, extra=(), tofu=False, launch=(PY, SERVER)):
    env = dict(os.environ, STAGED_VERSION=version, STAGED_OUTBOX=state + ".outbox")
    cmd = [PY, PROXY, "--state", state, "--rule", "nonamp"] + (["--trust-first-use"] if tofu else []) + list(extra) \
        + ["--"] + list(launch)
    c = Client(cmd, env=env); c.initialize()
    return c, {t["name"] for t in c.list_tools()}


def test_end_to_end_widening_suspends_then_consent_rebinds():
    with tempfile.TemporaryDirectory() as tmp:
        st = os.path.join(tmp, "s.json")
        c, names = _session(st, "v1", tofu=True); c.close()
        assert "send_report" in names
        c, names = _session(st, "v2")                                            # adds cc (any string)
        r = c.call("send_report", {"to": "team@corp.example", "body": "x", "cc": "attacker@evil.example"}); c.close()
        assert "send_report" not in names and r["result"]["isError"]
        subprocess.run([PY, PROXY, "approve", "--state", st, "--tool", "send_report"], check=True)
        c, names = _session(st, "v2"); c.close()
        assert "send_report" in names
        assert sp.verify(st)[0]


def test_end_to_end_benign_change_rebinds_silently():
    with tempfile.TemporaryDirectory() as tmp:
        st = os.path.join(tmp, "s.json")
        c, _ = _session(st, "v1", tofu=True); c.close()
        c, names = _session(st, "v3"); c.close()                                 # adds priority: enum low|high
        # label-free: a new declared argument on a closed object is a new coordinate -> the rule asks
        assert "send_report" not in names
        d = json.load(open(st))
        assert "new_authority_arg:priority" in d["tools"]["send_report"]["reasons"]


def test_end_to_end_enum_widening_caught_without_manifest():
    with tempfile.TemporaryDirectory() as tmp:
        st = os.path.join(tmp, "s.json")
        c, _ = _session(st, "v1", tofu=True); c.close()
        c, names = _session(st, "e2"); c.close()                                 # env: enum [test] -> any string
        assert "deploy" not in names


def test_end_to_end_server_identity_change_suspends():
    with tempfile.TemporaryDirectory() as tmp:
        st = os.path.join(tmp, "s.json")
        c, _ = _session(st, "v1", tofu=True); c.close()
        c, names = _session(st, "v1", launch=(PY, "-u", SERVER)); c.close()      # different launch command
        assert names == set()
        d = json.load(open(st))
        assert all(t["reasons"] == ["server_identity_changed"] for t in d["tools"].values())


def test_end_to_end_suspension_lifted_when_bound_definition_returns():
    with tempfile.TemporaryDirectory() as tmp:
        st = os.path.join(tmp, "s.json")
        c, _ = _session(st, "v1", tofu=True); c.close()
        c, names = _session(st, "v2"); c.close()                                 # widening: suspended
        assert "send_report" not in names
        c, names = _session(st, "v1"); c.close()                                 # bound definition again
        assert "send_report" in names
        d = json.load(open(st))
        assert d["tools"]["send_report"]["status"] == "bound" and sp.verify(st)[0]
