"""Minimal newline-delimited JSON-RPC MCP client over stdio, with per-request timing (no SDK validation)."""
import subprocess, json, time, select, os

class Client:
    def __init__(self, cmd, env=None, cwd=None, timeout=60):
        self.p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=open(os.devnull, "w"),
                                  text=True, bufsize=1, env=env, cwd=cwd)
        self.n = 0; self.timeout = timeout; self.timings = []
    def _send(self, o):
        self.p.stdin.write(json.dumps(o) + "\n"); self.p.stdin.flush()
    def request(self, method, params=None):
        self.n += 1; i = self.n; t0 = time.perf_counter()
        self._send({"jsonrpc": "2.0", "id": i, "method": method, "params": params or {}})
        deadline = time.time() + self.timeout
        while time.time() < deadline:
            r, _, _ = select.select([self.p.stdout], [], [], 0.5)
            if not r:
                if self.p.poll() is not None: raise RuntimeError("server exited")
                continue
            line = self.p.stdout.readline()
            if not line: raise RuntimeError("eof")
            try: msg = json.loads(line)
            except Exception: continue
            if msg.get("id") == i:
                self.timings.append((method, time.perf_counter() - t0)); return msg
        raise TimeoutError(method)
    def initialize(self):
        r = self.request("initialize", {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "demo", "version": "1"}})
        self._send({"jsonrpc": "2.0", "method": "notifications/initialized"}); return r
    def list_tools(self):
        return self.request("tools/list")["result"]["tools"]
    def call(self, name, args):
        return self.request("tools/call", {"name": name, "arguments": args})
    def close(self):
        try: self.p.stdin.close()
        except Exception: pass
        try: self.p.wait(timeout=3)
        except Exception: self.p.kill()
