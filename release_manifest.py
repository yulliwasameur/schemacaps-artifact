#!/usr/bin/env python3
"""Per-release manifest of the corpus (revision 2): one row per extracted release, with the registry artefact.

For every record in raw/ and raw_intermediates/ it writes the release's identity (package, ecosystem, stratum,
version, publication date, position in the window), how it was extracted (install command with the dependency
cut-off, launch variant, client, time), the outcome (status, error and cause), what the server reported at
initialize (serverInfo, protocolVersion), what tools/list returned (tool count and the SHA-256 of the captured list),
and the registry artefact (npm dist.tarball + dist.integrity + dist.shasum; PyPI file URL + SHA-256), fetched from
the public registries. Output: results/releases.csv and results/releases_meta.json.
Registry documents are cached under cache/registry/ so a re-run is offline.
"""
import csv, glob, json, os, time, urllib.parse, urllib.request

CACHE = os.path.join("cache", "registry"); os.makedirs(CACHE, exist_ok=True)


def cutoff(published):
    from extract import cutoff as c                                    # same function the extractor used
    return c(published)


def fetch(url, name):
    p = os.path.join(CACHE, name)
    if os.path.exists(p):
        return json.load(open(p))
    req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "schemacaps-artefact"})
    with urllib.request.urlopen(req, timeout=60) as r:
        d = json.load(r)
    json.dump(d, open(p, "w"))
    return d


def npm_doc(pkg):
    return fetch("https://registry.npmjs.org/" + urllib.parse.quote(pkg, safe="@"),
                 "npm__" + pkg.replace("/", "__").replace("@", "") + ".json")


def pypi_doc(pkg, ver):
    return fetch(f"https://pypi.org/pypi/{pkg}/{ver}/json", f"pypi__{pkg}__{ver}.json")


def main():
    rows = []
    for src in ("raw", "raw_intermediates"):
        for f in sorted(glob.glob(os.path.join(src, "*.json"))):
            r = json.load(open(f))
            pkg, eco, ver = r["package"], r.get("ecosystem", "npm"), r["version"]
            row = {"package": pkg, "ecosystem": eco, "stratum": r.get("strate", ""), "version": ver,
                   "published": r.get("published", ""), "index_in_window": r.get("index_in_window", ""),
                   "sampled_rank": r.get("sampled_rank", ""), "record": f, "extracted_at": r.get("extracted_at", ""),
                   "deps_resolved_before": r.get("deps_resolved_before", ""), "status": r.get("status", ""),
                   "error": r.get("error", "") or "", "error_pass2": r.get("error_pass2", "") or "",
                   "client": r.get("client", "mcp_python_sdk"), "launch_variant": json.dumps(r.get("variant", "")),
                   "server_name": (r.get("serverInfo") or {}).get("name", ""),
                   "server_version": (r.get("serverInfo") or {}).get("version", ""),
                   "protocol_version": r.get("protocolVersion", ""), "n_tools": len(r.get("tools") or []),
                   "tools_sha256": r.get("tools_sha256", "")}
            if eco == "npm":
                row["install_command"] = (f"npm install --prefix <dir> {pkg}@{ver} --ignore-scripts --no-audit --no-fund "
                                          f"--omit=dev --before={r.get('deps_resolved_before', '')}")
                try:
                    dist = npm_doc(pkg)["versions"][ver]["dist"]
                    row.update(artefact_url=dist.get("tarball", ""), artefact_integrity=dist.get("integrity", ""),
                               artefact_sha1=dist.get("shasum", ""))
                except Exception as e:
                    row.update(artefact_url="", artefact_integrity=f"unavailable: {type(e).__name__}", artefact_sha1="")
            else:
                row["install_command"] = (f"uv pip install --target <dir> --exclude-newer "
                                          f"{r.get('deps_resolved_before', '')} {pkg}=={ver}")
                try:
                    files = pypi_doc(pkg, ver)["urls"]
                    whl = next((u for u in files if u["packagetype"] == "bdist_wheel"), files[0])
                    row.update(artefact_url=whl["url"], artefact_integrity="sha256-" + whl["digests"]["sha256"],
                               artefact_sha1="")
                except Exception as e:
                    row.update(artefact_url="", artefact_integrity=f"unavailable: {type(e).__name__}", artefact_sha1="")
            rows.append(row)
    keys = list(dict.fromkeys(k for r in rows for k in r))
    with open(os.path.join("results", "releases.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys); w.writeheader(); w.writerows(rows)
    meta = {"releases": len(rows), "ok": sum(r["status"] == "ok" for r in rows),
            "with_registry_hash": sum(bool(r["artefact_integrity"]) and not r["artefact_integrity"].startswith("unavailable")
                                      for r in rows),
            "status_counts": {s: sum(r["status"] == s for r in rows) for s in sorted({r["status"] for r in rows})},
            "registry_fetched": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    json.dump(meta, open(os.path.join("results", "releases_meta.json"), "w"), indent=1)
    print(json.dumps(meta, indent=1))


if __name__ == "__main__":
    main()
