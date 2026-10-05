PYTHON ?= python3
AIVP = PYTHONPATH=src $(PYTHON) -c 'from aivp.cli import main; main()'

DEMO_TASK = evals/inputs/tasks/controlled-fault-repair.json
DEMO_CONFIG = evals/inputs/configs/controlled-fault-repair.json
DEMO_REPORTS = .aivp/demo/reports
DEMO_STATE = .aivp/demo/state.db
FIXED_SUITE = evals/suites/m7-fixed.json

.PHONY: doctor test demo eval benchmark help

help:
	@echo "AIVP v2 public commands"
	@echo
	@echo "  make doctor     Validate the local Python/AIVP environment"
	@echo "  make test       Run the 415-test stdlib unittest regression suite"
	@echo "  make demo       Run a deterministic scripted generate/repair/verify demo"
	@echo "  make benchmark  Validate frozen public benchmark JSON evidence"
	@echo "  make eval       Run the full frozen M7 suite; MAY USE LIVE PROVIDERS"
	@echo
	@echo "make demo does not require live Codex or Claude provider calls."

doctor:
	@$(PYTHON) -c 'import sys; assert sys.version_info >= (3, 11), sys.version; print("Python:", sys.version.split()[0])'
	@PYTHONPATH=src $(PYTHON) -c 'import aivp; from aivp.cli import build_parser; h=build_parser().format_help(); assert all(x in h for x in ("run","eval","gc","resume")); print("AIVP import/CLI: PASS")'
	@test -f "$(DEMO_TASK)"
	@test -f "$(DEMO_CONFIG)"
	@test -f "$(FIXED_SUITE)"
	@test -f "evals/tools/scripted_codex.py"
	@test -f "evals/tools/scripted_claude.py"
	@echo "Deterministic demo inputs: PASS"
	@echo "Doctor: PASS"

test:
	@PYTHONPATH=src $(PYTHON) -m unittest discover -s tests/unit -p 'test_*.py'

demo: doctor
	@mkdir -p "$(DEMO_REPORTS)"
	@echo "Running deterministic AIVP demo."
	@echo "Models: scripted Codex + scripted Claude"
	@echo "Scenario: controlled verification failure -> bounded repair -> re-verification"
	@$(AIVP) run \
		--repo . \
		--task "$(DEMO_TASK)" \
		--config "$(DEMO_CONFIG)" \
		--reports "$(DEMO_REPORTS)" \
		--state-db "$(DEMO_STATE)" \
		--yes
	@echo
	@echo "Demo: PASS"
	@echo "Generated evidence is under $(DEMO_REPORTS)"

benchmark:
	@$(PYTHON) -m json.tool docs/evidence/m6-cache-latency.json >/dev/null
	@$(PYTHON) -m json.tool docs/evidence/m6-provider-cache.json >/dev/null
	@$(PYTHON) -m json.tool docs/evidence/m7-eval-summary.json >/dev/null
	@$(PYTHON) -m json.tool docs/evidence/m8-routing-economics-summary.json >/dev/null
	@echo "Frozen benchmark JSON: PASS"
	@echo "See docs/BENCHMARK.md for interpretation and caveats."

eval:
	@echo "WARNING: the frozen M7 suite includes configurations that may invoke live Codex/Claude providers."
	@echo "This target can consume provider quota."
	@$(AIVP) eval run "$(FIXED_SUITE)" --yes
