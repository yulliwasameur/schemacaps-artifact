#!/usr/bin/env python3
"""Classement des évolutions de schémas (PROTOCOLE.md). Produit results/pairs.csv, results/changes.csv, results/summary.json."""
import json, glob, os, re, csv, hashlib, signal, copy, collections
import logging; logging.disable(logging.CRITICAL)
from jsonsubschema import isSubschema

ROOT = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(ROOT, "results"); os.makedirs(RES, exist_ok=True)

# Règle lexicale PROVISOIRE des rôles porteurs d'autorité (à valider par deux annotateurs humains).
AUTH_PATTERNS = [
    r"path", r"paths", r"file", r"filename", r"files", r"dir", r"directory", r"folder", r"destination", r"source", r"target",
    r"url", r"urls", r"uri", r"endpoint", r"host", r"hostname", r"domain", r"origin", r"port", r"server",
    r"to", r"cc", r"bcc", r"recipient", r"recipients", r"email", r"emails", r"channel", r"channel_?id", r"chat_?id",
    r"repo", r"repository", r"owner", r"org", r"organization", r"project", r"project_?id", r"branch", r"ref",
    r"workspace", r"team", r"space", r"account", r"user", r"username", r"user_?id", r"assignee", r"assignees", r"reviewers?",
    r"command", r"cmd", r"script", r"code", r"args", r"shell", r"query", r"sql", r"database", r"db", r"table", r"schema",
    r"subscription", r"resource_?group", r"tenant", r"namespace", r"cluster", r"bucket", r"key", r"page_?id", r"parent",
    r"database_?id", r"issue_?id", r"merge_?request_?iid", r"pid",
]
AUTH_RE = re.compile(r"^(" + "|".join(AUTH_PATTERNS) + r")$", re.I)
ID_RE = re.compile(r"(_id|Id|_ids|Ids|_iid)$")

def is_authority(name):
    n = name.strip()
    snake = re.sub(r"(?<!^)(?=[A-Z])", "_", n).lower()
    return bool(AUTH_RE.match(n) or AUTH_RE.match(snake) or ID_RE.search(n)
                or any(snake.endswith("_" + s) for s in ("path", "url", "dir", "directory", "email", "command", "query", "repo", "host")))

class Timeout(Exception): pass
def _alarm(*_): raise Timeout()
signal.signal(signal.SIGALRM, _alarm)

def canon(o): return json.dumps(o, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
def h(o): return hashlib.sha256(canon(o).encode()).hexdigest()[:16]

ANNOT = ("$schema", "description", "title", "examples", "example", "$comment", "deprecated",
         "readOnly", "writeOnly", "default", "markdownDescription", "$id")
NAMEMAPS = ("properties", "patternProperties", "$defs", "definitions", "dependentSchemas")

def clean(s):
    """Retire les annotations sans effet sur les valeurs admises. Les NOMS de propriétés ne sont jamais filtrés."""
    if isinstance(s, dict):
        out = {}
        for k, v in s.items():
            if k in NAMEMAPS and isinstance(v, dict):
                out[k] = {name: clean(sch) for name, sch in v.items()}
            elif k in ANNOT:
                continue
            else:
                out[k] = clean(v)
        return out
    if isinstance(s, list): return [clean(x) for x in s]
    return s

def sub(a, b, secs=20):
    """a ⊆ b ? True/False, ou None si indécis (non pris en charge par jsonsubschema ou délai)."""
    try:
        signal.alarm(secs)
        r = bool(isSubschema(clean(a), clean(b)))
        return r
    except Exception:
        return None
    finally:
        signal.alarm(0)

def props(s):
    return (s or {}).get("properties", {}) if isinstance(s, dict) else {}

def resolve_local_refs(s):
    """Déplie les $ref locaux (#/$defs/..., #/definitions/...) — un niveau de profondeur suffit en pratique ici."""
    defs = {}
    for k in ("$defs", "definitions"):
        if isinstance(s, dict) and isinstance(s.get(k), dict):
            for n, v in s[k].items(): defs[f"#/{k}/{n}"] = v
    def rec(x, depth=0):
        if isinstance(x, dict):
            if "$ref" in x and x["$ref"] in defs and depth < 8:
                return rec(copy.deepcopy(defs[x["$ref"]]), depth + 1)
            return {k: rec(v, depth) for k, v in x.items() if k not in ("$defs", "definitions")}
        if isinstance(x, list): return [rec(v, depth) for v in x]
        return x
    return rec(s)

def analyse_tool(old, new):
    so, sn = resolve_local_refs(old.get("inputSchema") or {}), resolve_local_refs(new.get("inputSchema") or {})
    out = {"schema_changed": h(so) != h(sn),
           "desc_changed": (old.get("description") or "") != (new.get("description") or ""),
           "title_changed": (old.get("title") or "") != (new.get("title") or "")}
    if not out["schema_changed"]:
        out.update(compatible=True, tightened=True, amplifying=False, undecided=False, reasons=[]); return out
    comp = sub(so, sn); tight = sub(sn, so)
    reasons, undecided = [], False
    po, pn = props(so), props(sn)
    open_new = sn.get("additionalProperties", True) is not False if isinstance(sn, dict) else True
    declared_old = bool(po)
    # 1) arguments porteurs d'autorité déclarés dans l'ancienne version
    for a, sa_old in po.items():
        if not is_authority(a):
            continue
        if a in pn:
            sa_new = pn[a]
        elif open_new:
            sa_new = {}          # l'argument n'est plus contraint : toute valeur est admise
            reasons.append(f"constraint_dropped:{a}")
            continue
        else:
            continue             # l'argument n'est plus accepté : resserrement
        r = sub(sa_new, sa_old)
        if r is None:
            undecided = True; reasons.append(f"undecided:{a}")
        elif r is False:
            reasons.append(f"widened:{a}")
        d_o = sa_old.get("default") if isinstance(sa_old, dict) else None
        d_n = sa_new.get("default") if isinstance(sa_new, dict) else None
        if d_n is not None and d_o != d_n:
            reasons.append(f"default_changed:{a}")
    # 2) nouveaux arguments porteurs d'autorité (seulement si l'ancienne interface était déclarée)
    for a in pn:
        if is_authority(a) and a not in po:
            reasons.append(f"new_authority_arg:{a}" if declared_old else f"declaration_restored:{a}")
    # 3) ouverture formelle de l'objet (sans argument d'autorité nommé) : comptée à part
    ao = so.get("additionalProperties", True) if isinstance(so, dict) else True
    if ao is False and open_new:
        reasons.append("object_opened")
    amplifying = any(r.split(":")[0] in ("new_authority_arg", "widened") for r in reasons)  # constraint_dropped : compté à part (paramètre retiré d'un objet ouvert, effet serveur inconnu)
    out.update(compatible=comp, tightened=tight, amplifying=amplifying, undecided=undecided and not amplifying,
               default_changed=any(r.startswith("default_changed") for r in reasons),
               object_opened="object_opened" in reasons, reasons=reasons)
    return out

def main():
    recs = collections.defaultdict(list)
    status = collections.Counter(); per_pkg_status = collections.defaultdict(collections.Counter)
    for f in glob.glob(os.path.join(ROOT, "raw", "*.json")):
        r = json.load(open(f)); status[r["status"]] += 1; per_pkg_status[r["package"]][r["status"]] += 1
        if r["status"] == "ok": recs[r["package"]].append(r)
    pairs_rows, change_rows = [], []
    agg = collections.Counter()
    for pkg, rs in sorted(recs.items()):
        rs.sort(key=lambda r: r["published"])
        for o, n in zip(rs, rs[1:]):
            to = {t["name"]: t for t in o.get("tools", [])}; tn = {t["name"]: t for t in n.get("tools", [])}
            added, removed = sorted(set(tn) - set(to)), sorted(set(to) - set(tn))
            stats = collections.Counter(added=len(added), removed=len(removed))
            for name in sorted(set(to) & set(tn)):
                a = analyse_tool(to[name], tn[name])
                defchg = a["schema_changed"] or a["desc_changed"] or a["title_changed"]
                if not defchg:
                    stats["unchanged"] += 1; continue
                stats["def_changed"] += 1
                if not a["schema_changed"]:
                    stats["desc_only"] += 1
                else:
                    stats["schema_changed"] += 1
                    stats["compatible"] += a["compatible"] is True
                    stats["incompatible"] += a["compatible"] is False
                    stats["compat_undecided"] += a["compatible"] is None
                    stats["tightened"] += a["tightened"] is True
                    stats["amplifying"] += a["amplifying"]
                    stats["auth_undecided"] += a["undecided"]
                    stats["compatible_and_amplifying"] += (a["compatible"] is True and a["amplifying"])
                    stats["object_opened_only"] += (a.get("object_opened", False) and not a["amplifying"])
                change_rows.append({"package": pkg, "strate": o["strate"], "from": o["version"], "to": n["version"],
                                    "tool": name, **{k: a.get(k) for k in ("schema_changed", "desc_changed", "compatible", "tightened",
                                                                           "amplifying", "undecided", "default_changed", "object_opened")},
                                    "reasons": ";".join(a.get("reasons", []))})
            # règles de ré-approbation (unité : outil ; un outil ajouté est une nouvelle autorité)
            rows = [r for r in change_rows if r["package"] == pkg and r["from"] == o["version"] and r["to"] == n["version"]]
            pin = stats["def_changed"] + len(added)
            compat = sum(1 for r in rows if r["schema_changed"] and r["compatible"] is not True)
            caps = sum(1 for r in rows if r["schema_changed"] and (r["amplifying"] or r["undecided"])) + len(added)
            new_auth_tools = sum(1 for t in added if any(is_authority(p) for p in props(tn[t].get("inputSchema"))))
            pairs_rows.append({"package": pkg, "strate": o["strate"], "from": o["version"], "to": n["version"],
                               "from_date": o["published"][:10], "to_date": n["published"][:10],
                               "versions_between": n["index_in_window"] - o["index_in_window"],
                               "tools_from": len(to), "tools_to": len(tn), **stats,
                               "reapprove_pin": pin, "reapprove_compat": compat, "reapprove_schemacaps": caps,
                               "added_with_authority_args": new_auth_tools,
                               "added_tools": ",".join(added), "removed_tools": ",".join(removed)})
            agg.update(stats); agg["pairs"] += 1; agg["reapprove_pin"] += pin; agg["reapprove_compat"] += compat
            agg["reapprove_schemacaps"] += caps; agg["added_with_authority_args"] += new_auth_tools
    for name, rows in (("pairs.csv", pairs_rows), ("changes.csv", change_rows)):
        if rows:
            keys = sorted({k for r in rows for k in r}, key=lambda k: list(rows[0]).index(k) if k in rows[0] else 99)
            with open(os.path.join(RES, name), "w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=keys); w.writeheader(); w.writerows(rows)
    summary = {"extraction_status": dict(status), "packages_with_ok": len(recs),
               "per_package_status": {k: dict(v) for k, v in per_pkg_status.items()}, "totals": dict(agg)}
    json.dump(summary, open(os.path.join(RES, "summary.json"), "w"), indent=1)
    print(json.dumps(summary["totals"], indent=1)); print(dict(status))

if __name__ == "__main__":
    main()
