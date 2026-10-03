#!/usr/bin/env bash
set -euo pipefail

ROOT="$(
  git rev-parse --show-toplevel 2>/dev/null
)"

cd "$ROOT"

STATE="docs/PROJECT_STATE.json"

if [[ ! -f "AGENTS.md" ]]; then
  echo "ERROR: AGENTS.md not found" >&2
  exit 1
fi

if [[ ! -f "$STATE" ]]; then
  echo "ERROR: $STATE not found" >&2
  exit 1
fi

echo "============================================================"
echo " AIVP v2 CONTEXT BOOTSTRAP"
echo "============================================================"
echo

echo "=== LIVE GIT STATE ==="
echo "repo:   $ROOT"
echo "branch: $(git branch --show-current)"
echo "HEAD:   $(git rev-parse --short HEAD)"
echo

git status --short --branch

echo
echo "=== RECENT HISTORY ==="
git log -8 --oneline --decorate

echo
echo "=== CANONICAL PROJECT STATE ==="
python - "$STATE" <<'PY'
import json
import sys

path = sys.argv[1]

with open(path, encoding="utf-8") as f:
    state = json.load(f)

current = state.get("current", {})
memory = state.get("repository_memory", {})
sot = state.get("source_of_truth", {})

print(f"project:             {state.get('project')}")
print(f"current milestone:   {current.get('milestone')} — {current.get('name')}")
print(f"current phase:       {current.get('phase')}")
print(f"recorded branch:     {current.get('branch')}")
print(f"active plan:         {current.get('active_plan')}")
print(f"implementation base: {memory.get('implementation_base_commit')}")
print(f"base tag:            {memory.get('implementation_base_tag')}")

print()
print("Source-of-Truth model:")
for key, value in sot.items():
    print(f"  {key}: {value}")

print()
print("Completed milestones:")
for name, value in state.get("completed_milestones", {}).items():
    print(
        f"  {name}: "
        f"{value.get('commit')} / "
        f"{value.get('tag')}"
    )

print()
print("Current M7 implementation status:")
for key, value in state.get("m7_implementation_status", {}).items():
    print(f"  {key}: {value}")

print()
print("Next action:")
print(f"  {state.get('next_action')}")
PY

ACTIVE_PLAN="$(
python - "$STATE" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as f:
    state = json.load(f)

print(
    state
    .get("current", {})
    .get("active_plan", "")
)
PY
)"

echo
echo "=== MANDATORY CONTEXT FILES ==="
echo "1. AGENTS.md"
echo "2. docs/PROJECT_STATE.json"

if [[ -n "$ACTIVE_PLAN" ]]; then
  echo "3. $ACTIVE_PLAN"
fi

echo
echo "=== ACTIVE PLAN ==="
if [[ -n "$ACTIVE_PLAN" && -f "$ACTIVE_PLAN" ]]; then
  cat "$ACTIVE_PLAN"
else
  echo "No readable active plan."
fi

echo
echo "=== RELEVANT HISTORICAL POINTERS ==="
echo "Previous completed milestone:"
echo "  docs/milestones/M6.md"
echo
echo "Capability ledger:"
echo "  docs/CAPABILITY_LEDGER.json"

echo
echo "=== EVIDENCE INDEX ==="
find docs/evidence \
  -maxdepth 2 \
  -type f \
  -print \
  2>/dev/null \
  | sort || true

echo
echo "=== M7 CODE PRESENCE ==="
if [[ -d src/aivp/eval ]]; then
  find src/aivp/eval -maxdepth 2 -type f -print | sort
else
  echo "src/aivp/eval: not present"
fi

if [[ -d evals ]]; then
  find evals -maxdepth 3 -type f -print | sort
else
  echo "evals/: not present"
fi

echo
echo "============================================================"
echo " BOOTSTRAP COMPLETE"
echo
echo " Read historical milestone files only when required."
echo " Live Git state overrides stale runtime facts in documentation."
echo "============================================================"
