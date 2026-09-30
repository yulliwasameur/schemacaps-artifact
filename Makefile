# SchemaCaps artefact — one command per claim of the paper.
#   make reproduce   regenerate every number from the archived corpus and check them against the shipped numbers.tex
#   make numbers     (authors) rewrite numbers.tex from results/
#   make proof       check the Coq development (Coq 8.18.0)        make proof-docker   same, in coqorg/coq:8.18.0
#   make survey      client survey test protocol (needs node>=20, npm, uv, network)
#   make extract     re-mine the corpus from the registries (long; needs requirements-extract.txt, node, npm, uv)
PY ?= python3

.PHONY: reproduce env test pilot oracle annotation robustness demo bench numbers check proof proof-docker survey manifest extract

reproduce: test pilot oracle annotation robustness demo bench check

env:
	$(PY) -m pip install -r requirements.lock

test:                     ## regression tests: classifier, checker, oracle, proxy
	$(PY) -m pytest -q tests

pilot:                    ## classification (both labellings), taxonomy, witnesses, decision cost, report
	$(PY) classify2.py
	$(PY) classify2.py --label-free
	$(PY) taxonomy.py
	$(PY) checker_probes.py
	$(PY) release_manifest.py
	$(PY) witness2.py
	$(PY) timing2.py
	$(PY) report2.py

oracle:                   ## differential oracle over every silent re-bind (lexical, then label-free)
	$(PY) oracle2.py
	$(PY) oracle2.py --label-free

annotation:               ## agreement, precision/recall against the adjudicated gold standard, K, sampling frame
	$(PY) agreement.py annotation/v2_Annotateur_1.xlsx annotation/v2_Annotateur_2.xlsx annotation/v2_Annotateur_3_arbitrage.xlsx
	$(PY) annotation_frame.py

robustness:               ## package bootstrap, leave-one-out, cap sensitivity (raw40/)
	$(PY) robustness.py
	$(PY) robustness.py --label-free --kind strict
	$(PY) cap40_classify.py

demo:                     ## staged scenario matrix and exact-pair replay of the six real cases
	$(PY) prototype/demo_scenarios.py
	$(PY) prototype/replay_real.py

bench:                    ## proxy overhead (5 runs x 500 iterations)
	$(PY) prototype/bench_overhead.py

numbers:                  ## numbers.tex: every number cited by the paper, generated from results/
	$(PY) make_numbers.py > numbers.tex

check:                    ## fails if a deterministic number differs from the shipped numbers.tex; machine-dependent ones are reported
	$(PY) make_numbers.py --check numbers.tex

proof:
	coqc proof/NonAmplification.v

proof-docker:
	docker run --rm -v "$$(pwd)/proof:/proof" -w /proof coqorg/coq:8.18.0 coqc NonAmplification.v

survey:
	sh clients/run_survey.sh

manifest:                 ## per-release manifest with registry hashes (cached under cache/registry/)
	$(PY) release_manifest.py

extract:
	$(PY) -m pip install -r requirements-extract.txt
	$(PY) extract.py && $(PY) extract_raw.py && $(PY) extract_intermediates.py
