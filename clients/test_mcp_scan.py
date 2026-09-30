#!/usr/bin/env python3
"""Client survey, mcp-scan (the last release under that name with local tool pinning): does a schema-only
widening raise its change warning W003? Control: a description-only change.

mcp-scan's full `scan` aborts when its remote analysis server is unreachable, and we do not send tool data to a
third party. So this test drives mcp-scan's OWN pipeline in-process, minus the remote analysis: its own client
(mcp_client.check_server) launches the drift server and fetches the tools, and its own storage
(Storage.check_and_update, which the scanner's check_server_changed calls to emit W003) decides whether an entity
changed. Prints one JSON object.   Usage: .venv-scan/bin/python test_mcp_scan.py
"""
import asyncio, json, os, sys, tempfile
import importlib.metadata as md
from mcp_scan.mcp_client import check_server
from mcp_scan.models import StdioServer, hash_entity
from mcp_scan.Storage import Storage

HERE = os.path.dirname(os.path.abspath(__file__))


async def scan_once(store_path, env):
    cfg = StdioServer(command=sys.executable, args=[os.path.join(HERE, "drift_server.py")], env=env)
    sig, _ = await check_server(cfg, 30)
    st = Storage(store_path)
    out = {}
    for e in sig.entities:
        changed, _ = st.check_and_update("drift", e)
        out[e.name] = {"W003": changed, "hash": hash_entity(e),
                       "schema": json.dumps(getattr(e, "inputSchema", None), sort_keys=True)[:80]}
    st.save()
    return out


async def main():
    with tempfile.TemporaryDirectory() as tmp:
        store = os.path.join(tmp, "store.json")
        base = await scan_once(store, {"DRIFT_START": "v1", "DRIFT_OUTBOX": os.path.join(tmp, "o")})
        widen = await scan_once(store, {"DRIFT_START": "v2", "DRIFT_OUTBOX": os.path.join(tmp, "o")})
        ctrl = await scan_once(store, {"DRIFT_START": "v2", "DRIFT_DESC": "Read any file on the host.",
                                       "DRIFT_OUTBOX": os.path.join(tmp, "o")})
    print(json.dumps({"client": "mcp-scan", "version": md.version("mcp-scan"), "pinned_hash": "md5(description)",
                      "read_file_schema_changed": base["read_file"]["schema"] != widen["read_file"]["schema"],
                      "W003_on_schema_only_widening": widen["read_file"]["W003"],
                      "W003_on_description_change": ctrl["read_file"]["W003"]}))


asyncio.run(main())
