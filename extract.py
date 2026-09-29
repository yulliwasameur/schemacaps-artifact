#!/usr/bin/env python3
"""Extraction des schémas tools/list pour chaque version échantillonnée (voir PROTOCOLE.md, DEVIATIONS.md)."""
import logging
logging.disable(logging.CRITICAL)
import asyncio, json, os, shutil, subprocess, sys, tempfile, time, hashlib, traceback
from concurrent.futures import ProcessPoolExecutor
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "raw")
os.makedirs(OUT, exist_ok=True)
CAP = 20

DUMMY = {
    "GITHUB_PERSONAL_ACCESS_TOKEN": "ghp_dummy", "GITHUB_TOKEN": "ghp_dummy",
    "GITLAB_PERSONAL_ACCESS_TOKEN": "glpat-dummy", "GITLAB_API_URL": "https://gitlab.example.invalid/api/v4",
    "SLACK_BOT_TOKEN": "xoxb-dummy", "SLACK_TEAM_ID": "T000", "NOTION_TOKEN": "ntn_dummy",
    "OPENAPI_MCP_HEADERS": '{"Authorization": "Bearer ntn_dummy", "Notion-Version": "2022-06-28"}',
    "FIRECRAWL_API_KEY": "fc-dummy", "API_TOKEN": "dummy", "HOSTINGER_API_TOKEN": "dummy",
    "SENTRY_ACCESS_TOKEN": "dummy", "FIGMA_API_KEY": "dummy", "MCP_MODE": "stdio",
    "AWS_ACCESS_KEY_ID": "AKIADUMMY", "AWS_SECRET_ACCESS_KEY": "dummy", "AWS_REGION": "us-east-1",
    "REDIS_URL": "redis://127.0.0.1:6379", "N8N_API_URL": "", "DISABLE_TELEMETRY": "true",
    "NO_UPDATE_NOTIFIER": "1", "npm_config_update_notifier": "false", "DO_NOT_TRACK": "1",
    "PUPPETEER_SKIP_DOWNLOAD": "1", "LOG_LEVEL": "error",
}

def base_args(pkg, tmp):
    return {
        "@modelcontextprotocol/server-filesystem": [tmp],
        "@modelcontextprotocol/server-redis": ["redis://127.0.0.1:6379"],
        "figma-developer-mcp": ["--figma-api-key=dummy", "--stdio"],
        "@azure/mcp": ["server", "start"],
        "@sentry/mcp-server": ["--access-token=dummy"],
        "nx-mcp": [tmp],
        "agent-device": ["mcp"],
        "mcp-server-sqlite": ["--db-path", os.path.join(tmp, "t.db")],
        "mcp-server-git": ["--repository", tmp],
    }.get(pkg, [])

VARIANTS = [None, [], ["--stdio"], ["stdio"], ["mcp"], ["--transport", "stdio"]]

def sample(vs):
    if len(vs) <= CAP:
        return list(range(len(vs)))
    n = len(vs)
    return sorted({round(i * (n - 1) / (CAP - 1)) for i in range(CAP)})

def canon(o):
    return json.dumps(o, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

async def list_tools(cmd, args, env, cwd, timeout):
    params = StdioServerParameters(command=cmd, args=args, env=env, cwd=cwd)
    async def go():
        with open(os.devnull, "w") as devnull:
            async with stdio_client(params, errlog=devnull) as (r, w):
                async with ClientSession(r, w) as s:
                    init = await s.initialize()
                    tools, cursor = [], None
                    for _ in range(50):
                        res = await s.list_tools(cursor) if cursor else await s.list_tools()
                        tools += [t.model_dump(mode="json", exclude_none=True) for t in res.tools]
                        cursor = getattr(res, "nextCursor", None)
                        if not cursor:
                            break
                    return init.serverInfo.model_dump(mode="json"), init.protocolVersion, tools
    return await asyncio.wait_for(go(), timeout)

def install(pkg, eco, ver, d, published):
    t0 = time.time()
    if eco == "npm":
        r = subprocess.run(["npm", "install", "--prefix", d, f"{pkg}@{ver}", "--ignore-scripts", "--no-audit",
                            "--no-fund", "--omit=dev", "--loglevel=error", f"--before={cutoff(published)}"], capture_output=True, text=True, timeout=420)
    else:
        r = subprocess.run(["uv", "pip", "install", "--quiet", "--python", sys.executable, "--target", d,
                            "--exclude-newer", cutoff(published), f"{pkg}=={ver}"], capture_output=True, text=True, timeout=420)
    return r.returncode == 0, (r.stderr or "")[-600:], round(time.time() - t0, 1)

def cutoff(published):
    """Résolution des dépendances telle qu'au jour de publication (+ 1 jour de marge)."""
    import datetime
    d = datetime.datetime.fromisoformat(published.replace("Z", "+00:00")) + datetime.timedelta(days=1)
    return d.strftime("%Y-%m-%dT%H:%M:%SZ")

def command_for(pkg, eco, d):
    if eco == "pypi":
        mod = pkg.replace("-", "_")
        return sys.executable, ["-m", mod], {"PYTHONPATH": d}
    pj = json.load(open(os.path.join(d, "node_modules", pkg, "package.json")))
    b = pj.get("bin")
    if isinstance(b, dict):
        short = pkg.split("/")[-1]
        rel = b.get(short) or b.get(pj.get("name", "")) or next(iter(b.values()))
    elif isinstance(b, str):
        rel = b
    else:
        rel = pj.get("main", "index.js")
    path = os.path.join(d, "node_modules", pkg, rel)
    return "node", [path], {}

def do_package(item):
    pkg, meta = item
    eco, vs, dates = meta["eco"], meta["versions"], meta["dates"]
    idx = sample(vs)
    good_variant = None
    results = []
    safe = pkg.replace("/", "__").replace("@", "")
    for k, i in enumerate(idx):
        ver = vs[i]
        outf = os.path.join(OUT, f"{safe}@{ver}.json")
        if os.path.exists(outf):
            rec = json.load(open(outf))
            if rec.get("status") == "ok":
                good_variant = [x.replace("/home/claude/schemacaps/work/", "{TMPDIR}/") for x in rec.get("variant")]
                good_variant = ["{TMP}" if x.startswith("{TMPDIR}/run_") else x for x in good_variant]
            results.append(rec["status"]); continue
        rec = {"package": pkg, "ecosystem": eco, "strate": meta["strate"], "version": ver, "published": dates[i],
               "index_in_window": i, "sampled_rank": k, "extracted_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
        d = tempfile.mkdtemp(prefix="sc_", dir="/home/claude/schemacaps/work")
        tmp = tempfile.mkdtemp(prefix="run_", dir="/home/claude/schemacaps/work")
        try:
            ok, err, secs = install(pkg, eco, ver, d, dates[i])
            rec["deps_resolved_before"] = cutoff(dates[i])
            rec["install_seconds"] = secs
            if not ok:
                rec.update(status="install_failed", error=err)
            else:
                cmd, pre, extra = command_for(pkg, eco, d)
                env = dict(os.environ, **DUMMY, **extra, HOME=tmp)
                variants = []
                if good_variant is not None:
                    variants.append([tmp if x == "{TMP}" else x.replace("{TMP}", tmp) for x in good_variant])
                for v in VARIANTS:
                    a = base_args(pkg, tmp) if v is None else v
                    if a not in variants:
                        variants.append(a)
                last = None
                for a in variants:
                    try:
                        info, proto, tools = asyncio.run(list_tools(cmd, pre + a, env, tmp, 45))
                        sym = [x.replace(tmp, "{TMP}") for x in a]
                        rec.update(status="ok", variant=sym, serverInfo=info, protocolVersion=proto, tools=tools,
                                   tools_sha256=hashlib.sha256(canon(sorted(tools, key=lambda t: t["name"])).encode()).hexdigest())
                        good_variant = sym
                        break
                    except Exception as e:
                        last = f"{type(e).__name__}: {str(e)[:300]}"
                if rec.get("status") != "ok":
                    rec.update(status="no_response", error=last)
        except Exception as e:
            rec.update(status="error", error=traceback.format_exc()[-600:])
        finally:
            shutil.rmtree(d, ignore_errors=True); shutil.rmtree(tmp, ignore_errors=True)
        json.dump(rec, open(outf, "w"), indent=1, ensure_ascii=False)
        results.append(rec["status"])
        print(f"{pkg}@{ver}: {rec['status']} ({len(rec.get('tools', []))} tools)", flush=True)
    return pkg, results

if __name__ == "__main__":
    os.makedirs("/home/claude/schemacaps/work", exist_ok=True)
    corpus = json.load(open(os.path.join(ROOT, "corpus_versions.json")))
    items = [(p, m) for p, m in corpus.items() if m["versions"]]
    only = sys.argv[1:]
    if only:
        items = [x for x in items if x[0] in only]
    with ProcessPoolExecutor(max_workers=int(os.environ.get("W", "3"))) as ex:
        for pkg, res in ex.map(do_package, items):
            print("DONE", pkg, {s: res.count(s) for s in set(res)}, flush=True)
