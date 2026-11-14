#!/usr/bin/env python3
"""Analyse de sensibilité au plafond (non numérotée comme écart) : sensibilité au plafond d'échantillonnage. Ré-extraction des deux paquets dominants avec CAP=40
(agent-device, @sentry/mcp-server) dans raw40/, en réutilisant les extractions existantes quand la version coïncide."""
import json, os, shutil, glob
import extract
extract.CAP = 40
ROOT = os.path.dirname(os.path.abspath(__file__))
extract.OUT = os.path.join(ROOT, "raw40"); os.makedirs(extract.OUT, exist_ok=True)
corpus = json.load(open(os.path.join(ROOT, "corpus_versions.json")))
PKGS = ["agent-device", "@sentry/mcp-server"]
for pkg in PKGS:
    m = corpus[pkg]; idx = extract.sample(m["versions"]); safe = pkg.replace("/", "__").replace("@", "")
    for i in idx:
        v = m["versions"][i]; src = os.path.join(ROOT, "raw", f"{safe}@{v}.json")
        if os.path.exists(src) and not os.path.exists(os.path.join(extract.OUT, f"{safe}@{v}.json")):
            shutil.copy(src, extract.OUT)
for pkg in PKGS:
    print(extract.do_package((pkg, corpus[pkg])), flush=True)
