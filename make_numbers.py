#!/usr/bin/env python3
"""numbers.tex: every number the paper cites, generated from results/ (no number in the paper is typed by hand).

  python3 make_numbers.py > numbers.tex        generate
  python3 make_numbers.py --check numbers.tex  exit 1 if any regenerated value differs from the given file
Macros are named \\nX; the demonstration matrix body is \\DemoRows.
"""
import csv, glob, json, os, re, sys

R = "results"
J = lambda f: json.load(open(os.path.join(R, f)))
M = {}


def fmt(v, d=None):
    if isinstance(v, float) and d is not None:
        return f"{v:.{d}f}"
    if isinstance(v, int) and abs(v) >= 1000:
        return f"{v:,}".replace(",", "{,}")
    return str(v)


def put(name, v, d=None):
    assert re.fullmatch(r"[A-Za-z]+", name), name
    M[name] = fmt(v, d)


def pct(a, b, d=1):
    return 100.0 * a / b


# ---- corpus ---------------------------------------------------------------------------------------------
cv = json.load(open("corpus_versions.json"))
put("WindowVersions", sum(len(v["versions"]) for v in cv.values()))
put("WindowPackages", sum(1 for v in cv.values() if v["versions"]))
raw = [json.load(open(f)) for f in glob.glob("raw/*.json")]
ok = [r for r in raw if r["status"] == "ok"]
put("Releases", len(raw)); put("ReleasesOK", len(ok)); put("PctOK", pct(len(ok), len(raw)), 1)
put("PackagesOK", len({r["package"] for r in ok}))
put("ReleasesOKA", sum(r["strate"] == "A" for r in ok)); put("ReleasesOKB", sum(r["strate"] == "B" for r in ok))
put("NoResponse", sum(r["status"] == "no_response" for r in raw)); put("InstallFailed", sum(r["status"] == "install_failed" for r in raw))
put("PassTwo", sum(r.get("client") == "raw_jsonrpc_pass2" for r in raw))
rel = J("releases_meta.json"); put("ManifestRows", rel["releases"]); put("ManifestHashed", rel["with_registry_hash"])

# ---- classification, both labellings --------------------------------------------------------------------
for lab, f in (("", "v2_summary.json"), ("Free", "free_summary.json")):
    s = J(f); T, P = s["totals"], s["per_strate"]
    for k, key in (("Pairs", "pairs"), ("Changed", "schema_changed"), ("Compat", "compatible"), ("Incompat", "incompatible"),
                   ("CompatUnd", "compat_undecided"), ("CACore", "ca_core"), ("CAStrict", "ca_strict"), ("Undecided", "undecided"),
                   ("AskPin", "def_changed"), ("AskCompat", "rq_compat"), ("AskSC", "rq_strict"), ("AskCore", "rq_core"),
                   ("Added", "added")):
        put(k + lab, T.get(key, 0))
        for st in ("A", "B"):
            put(k + lab + st, P[st].get(key, 0))
    g = s.get("checker_guard", {})
    put("GuardCalls" + lab, g.get("calls", 0)); put("GuardOverturned" + lab, g.get("overturned", 0))
    put("GuardGenErr" + lab, g.get("gen_errors", 0))
T, F = J("v2_summary.json")["totals"], J("free_summary.json")["totals"]
changes = list(csv.DictReader(open(os.path.join(R, "v2_changes.csv"))))
put("DescOnly", sum(r["desc_only"] == "True" for r in changes))
put("AddedAuth", T["added_auth"])
pin, comp, lex, free = T["def_changed"], T["rq_compat"], T["rq_strict"], F["rq_strict"]
put("LexBelowPin", pct(pin - lex, pin), 0); put("LexBelowCompat", pct(comp - lex, comp), 0)
put("FreeBelowPin", pct(pin - free, pin), 0); put("FreeAboveCompat", pct(free - comp, comp), 1)
put("FreeMinusCompat", free - comp)
# plain integers (no thousands separator) for chart lengths in the slides and the poster
M["AskPinPlain"], M["AskCompatPlain"], M["AskSCFreePlain"] = str(pin), str(comp), str(free)
add = T["added"]
put("TotPin", pin + add); put("TotCompat", comp + add); put("TotLex", lex + add); put("TotFree", free + add)
put("TotFreeBelowPin", pct(pin - free, pin + add), 0)
put("PctCAStrictFree", pct(F["ca_strict"], F["compatible"]), 0)
put("PctCACore", pct(T["ca_core"], T["compatible"]), 1)

# ---- taxonomy (Table 3) ---------------------------------------------------------------------------------
tx = J("taxonomy.json")
for k, name in (("new_authority_arg", "TxNewArg"), ("widened", "TxWidened"), ("became_optional", "TxOptional"),
                ("constraint_dropped", "TxDropped"), ("object_opened", "TxOpened"), ("object_introduced_open", "TxIntroOpen"),
                ("default_changed", "TxDefault"), ("nullable", "TxNullable"), ("shape_changed", "TxShape")):
    put(name, tx["lexical"][k]); put(name + "Free", tx["label_free"][k])
put("TxNarrow", tx["strict_narrowings_all_changes"]); put("TxHints", tx["tools_with_raised_hint"])

# ---- robustness -----------------------------------------------------------------------------------------
rb = J("robustness.json")
put("CoreServers", len(rb["by_package"]))
pairs = list(csv.DictReader(open(os.path.join(R, "v2_pairs.csv"))))
put("CorePairs", sum(int(p["ca_core"]) > 0 for p in pairs)); put("PairsB", sum(p["strate"] == "B" for p in pairs))
t1, t2 = rb["top2"]
put("TopTwo", rb["by_package"][t1] + rb["by_package"][t2])
put("LooTopOne", rb["leave_one_package_out"][t1]); put("LooTopTwo", rb["leave_one_package_out"][t2])
put("WithoutTopTwo", rb["without_top2"])
put("CILow", 100 * rb["bootstrap_interval_95"][0], 1); put("CIHigh", 100 * rb["bootstrap_interval_95"][1], 1)
put("BootDraws", rb["bootstrap_draws"])
rf = J("robustness_free_strict.json")
put("CIFreeLow", 100 * rf["bootstrap_interval_95"][0], 0); put("CIFreeHigh", 100 * rf["bootstrap_interval_95"][1], 0)
cs = J("cap_sensitivity.json")
put("CapPlusA", cs["cap40"]["agent-device"] - cs["cap20"]["agent-device"])
put("CapPlusB", cs["cap40"]["@sentry/mcp-server"] - cs["cap20"]["@sentry/mcp-server"])

# ---- oracle, checker, witnesses -------------------------------------------------------------------------
for lab, f in (("Lex", "oracle2_lexical.json"), ("Free", "oracle2_label_free.json")):
    o = J(f)
    put("OrSilent" + lab, o["silent_rebinds"]); put("OrSame" + lab, o["identical_schema"]); put("OrSchema" + lab, o["schema_rebinds"])
    put("OrCompat" + lab, o.get("compatible", 0)); put("OrIncompat" + lab, o.get("incompatible", 0))
    put("OrUnd" + lab, o.get("compat_undecided", 0)); put("OrGen" + lab, o["generated_checks"])   # label-free: generated calls; lexical: marginal checks tested
    put("OrGenErr" + lab, o.get("gen_error", 0)); put("OrWitness" + lab, len(o["unsound"])); put("OrN", o["samples_per_check"])
cp = J("checker_probes.json")
put("Probes", cp["probes"]); put("ProbesRawUnsound", len(cp["raw_unsound"])); put("ProbesGuardUnsound", len(cp["guarded_unsound"]))
w = J("v2_witness_summary.json")
put("CompatYesChecked", w["soundness_check_on_compatible_yes"].get("not_found", 0))

# ---- annotation -----------------------------------------------------------------------------------------
a = J("agreement.json"); fr = J("annotation_frame.json")
put("AnnCases", a["n"]); put("AnnFlagged", a["flagged"]); put("AnnUnflagged", a["unflagged"])
put("AnnAgree", 100 * a["percent_agreement"], 0); put("Kappa", a["cohen_kappa"], 2)
put("KappaCollapsed", a["cohen_kappa_unsure_as_no"], 2); put("KappaSure", a["cohen_kappa_excluding_unsure"], 2)
put("AnnSure", a["n_excluding_unsure"]); put("AnnUnsure", max(a["unsure_counts"].values()))
put("AnnDisagree", len(a["disagreements"])); put("AnnHard", len(a["hard_disagreements"]))
put("AnnUnresolved", len(a["unresolved_disagreements"]))
put("Precision", a["lexical_rule_precision"], 2); put("Recall", a["lexical_rule_recall"], 2)
put("GoldYes", a["gold_yes"]); put("KCore", a["K_final_core"]); put("KStrict", a["K_final_strict_args"])
put("FrameFlagged", fr["flagged_frame"]); put("FrameMissing", len(fr["flagged_not_annotated"]))
put("FrameMissingCore", sum(x["has_core_reason"] for x in fr["flagged_not_annotated"]))

# ---- prototype ------------------------------------------------------------------------------------------
ov = J("proto_overhead.json")
put("OvCall", ov["added_call_ms"]["median"], 2); put("OvCallMin", ov["added_call_ms"]["min"], 2); put("OvCallMax", ov["added_call_ms"]["max"], 2)
put("OvList", ov["added_list_ms"]["median"], 1); put("OvListMin", ov["added_list_ms"]["min"], 1); put("OvListMax", ov["added_list_ms"]["max"], 1)
put("OvRuns", ov["runs"]); put("OvIter", ov["iterations_per_run"])
tm = J("v2_timing.json")
for lab, k in (("Lex", "lexical"), ("Free", "label_free")):
    put("TmMed" + lab, tm[k]["median_ms"], 0); put("TmNinety" + lab, tm[k]["p90_ms"], 0)
    put("TmPNN" + lab, tm[k]["p99_ms"] / 1000.0, 1); put("TmMax" + lab, tm[k]["max_ms"] / 1000.0, 1)
rp = J("proto_replay_real.json")
put("ReplayCases", len(rp["cases"])); put("ReplayOK", sum(all(c.get("expected_reason_produced", {}).values()) for c in rp["cases"]))
put("ReplayCompatRebind", sum(c["compat"]["verdict"] == "rebind" for c in rp["cases"]))
sc = J("proto_scenarios.json")["results"]
conf = ["accept-all", "pin", "compat", "SchemaCaps (label-free)", "SchemaCaps (manifest)", "SchemaCaps (lexical)"]
names = {"destination widening (cc added)": "Destination widened (\\code{cc})",
         "two-step laundering (open, then declare)": "Two-step laundering",
         "undeclared field after opening (bcc)": "Undeclared field after opening",
         "enum widening (env: test -> any)": "Enum widened (\\code{env})",
         "benign change (priority enum added)": "Benign change (\\code{priority})",
         "behaviour change, identical schema": "Behaviour change, same schema"}
rows = []
for s_name, label in names.items():
    cells = []
    for c in conf:
        r = sc[s_name][c]
        if s_name.startswith("benign"):
            cells.append("asks" if r["asked"] else "silent")
        else:
            cells.append("\\textbf{succeeds}" if r["effect"] else ("blocked" if r["asked"] else "no effect"))
    rows.append(label + " & " + " & ".join(cells) + "\\\\")
M["DemoRows"] = "\n".join(rows)
put("ReceiptsVerified", sum(1 for s in sc.values() for c, r in s.items() if r.get("receipts_verified")))

# ---- change kinds added by deviation 11, over all changes (label-free classification)
_fc = list(csv.DictReader(open(os.path.join(R, "free_changes.csv"))))
put("TxRemovedBottom", sum("removed_to_bottom:" in r["reasons"] for r in _fc))
put("TxBeyondStar", sum("declared_beyond_star:" in r["reasons"] for r in _fc))

# ---- adversarial benchmark (camera-ready, deviation 11) ---------------------------------------------------
B = J("adversarial_bench.json"); BC, BR = B["checker"], B["rule"]
put("BenchCheckPairs", BC["pairs"]); put("BenchCheckNotIncl", BC["raw"]["not_included"])
put("BenchRawFA", BC["raw"]["false_accept"]); put("BenchNormFA", BC["norm"]["false_accept"])
put("BenchGuardFA", BC["guarded"]["false_accept"])
put("BenchRulePairs", BR["pairs"]); put("BenchRuleAmp", BR["amplifying"]); put("BenchRuleCompatAmp", BR["compatible_amplifying"])
put("BenchVthreeSilent", BR["v3_false_silent"]); put("BenchVthreeRemoved", BR["v3_false_silent_by_kind"]["removed_to_bottom"]); put("BenchVthreeStar", BR["v3_false_silent_by_kind"]["declared_beyond_star"]); put("BenchFalseSilent", BR["guarded"]["false_silent"])
put("BenchAsksNonAmp", BR["guarded"]["asks_non_amplifying"]); put("BenchPinAsksNonAmp", BR["pin"]["asks_non_amplifying"])
put("BenchCompatFalseSilent", BR["compat"]["false_silent"])
put("BenchGenerated", BR["generated"]); put("BenchDiscarded", BR["discarded"])
put("BenchSiblingAsk", BR["sibling_old"]); put("BenchSiblingSilent", BR["sibling_old_silent"])
put("BenchRuleNonAmp", BR["non_amplifying"]); put("BenchUnnecPct", pct(BR["guarded"]["asks_non_amplifying"], BR["non_amplifying"]), 0)
put("BenchGuardOverRule", BR["guard_overturned_rule_phase"])
B2 = J("adversarial_bench_seed2.json"); C2, R2 = B2["checker"], B2["rule"]
put("BenchSeedTwo", B2["seed"]); put("BenchTwoPairs", R2["pairs"]); put("BenchTwoAmp", R2["amplifying"])
put("BenchTwoFalseSilent", R2["guarded"]["false_silent"]); put("BenchTwoVthreeSilent", R2["v3_false_silent"])
put("BenchTwoRawFA", C2["raw"]["false_accept"]); put("BenchTwoNormFA", C2["norm"]["false_accept"])
put("BenchTwoGuardFA", C2["guarded"]["false_accept"]); put("BenchTwoCheckNotIncl", C2["raw"]["not_included"])
for k, n in (("conditional", "BenchCond"), ("anyOf", "BenchAnyOf"), ("ref", "BenchRef"), ("not", "BenchNot"), ("nested", "BenchNested")):
    put(n, BR["features"][k])

# ---- survey, tests, proof -------------------------------------------------------------------------------
sv = J("client_survey.json")
put("SurveyProducts", len(sv["products"])); put("SurveyTested", sum("tested" in p["evidence"] for p in sv["products"]))
put("SurveyConfigs", len(sv["runtime_tests"]))
put("Tests", sum(len(re.findall(r"^def test_", open(f).read(), re.M)) for f in glob.glob("tests/test_*.py")))
put("CoqLines", sum(1 for _ in open("proof/NonAmplification.v")))


# Machine-dependent values (timing, overhead, per-check sample counts under a wall-clock cap): reported, not failed on.
VOLATILE_PREFIXES = ("Ov", "Tm", "OrGen")


def emit():
    out = ["% Generated by make_numbers.py from results/ -- do not edit by hand."]
    for k in sorted(M):
        if k != "DemoRows":
            out.append(f"\\newcommand{{\\n{k}}}{{{M[k]}}}")
    out.append(f"\\newcommand{{\\DemoRows}}{{%\n{M['DemoRows']}}}")          # last: its body spans lines
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    text = emit()
    if "--check" in sys.argv:
        shipped = open(sys.argv[sys.argv.index("--check") + 1]).read()
        pat = re.compile(r"\\newcommand\{\\n([A-Za-z]+)\}\{(.*?)\}$", re.M)
        old = dict(pat.findall(shipped)); new = dict(pat.findall(text))
        demo_old = shipped.split("\\newcommand{\\DemoRows}{%")[-1] if "DemoRows" in shipped else ""
        demo_new = text.split("\\newcommand{\\DemoRows}{%")[-1]
        bad, vol = [], []
        for k in sorted(set(old) | set(new)):
            if old.get(k) != new.get(k):
                (vol if k.startswith(VOLATILE_PREFIXES) else bad).append((k, old.get(k), new.get(k)))
        if demo_old.strip() != demo_new.strip():
            bad.append(("DemoRows", "shipped", "regenerated differs"))
        for k, a, b in vol:
            print(f"machine-dependent  \\n{k}: paper {a}  here {b}")
        for k, a, b in bad:
            print(f"MISMATCH           \\n{k}: paper {a}  regenerated {b}")
        if bad:
            print(f"CHECK FAILED: {len(bad)} deterministic value(s) differ"); sys.exit(1)
        print(f"CHECK OK: {len(new) - len(vol)} deterministic values match ({len(vol)} machine-dependent differ, listed above)")
        sys.exit(0)
    sys.stdout.write(text)
