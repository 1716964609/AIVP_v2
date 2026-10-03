#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || {
  echo "ERROR: not inside a Git repository" >&2
  exit 1
}

cd "$ROOT"

STATE="docs/PROJECT_STATE.json"
AGENTS="AGENTS.md"

if [[ ! -f "$AGENTS" ]]; then
  echo "ERROR: $AGENTS not found" >&2
  exit 1
fi

if [[ ! -f "$STATE" ]]; then
  echo "ERROR: $STATE not found" >&2
  exit 1
fi

python -m json.tool "$STATE" >/dev/null

ACTIVE_PLAN="$(
python - "$STATE" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as f:
    state = json.load(f)

print(state.get("current", {}).get("active_plan", ""))
PY
)"

RECORDED_BRANCH="$(
python - "$STATE" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as f:
    state = json.load(f)

print(state.get("current", {}).get("branch", ""))
PY
)"

LIVE_BRANCH="$(git branch --show-current)"
LIVE_HEAD="$(git rev-parse --short HEAD)"

echo "============================================================"
echo " AIVP v2 CONTEXT BOOTSTRAP"
echo "============================================================"
echo

echo "=== LIVE GIT STATE ==="
echo "repository: $ROOT"
echo "branch:     $LIVE_BRANCH"
echo "HEAD:       $LIVE_HEAD"
echo
git status --short --branch

if [[ -n "$RECORDED_BRANCH" && "$RECORDED_BRANCH" != "$LIVE_BRANCH" ]]; then
  echo
  echo "WARNING:"
  echo "PROJECT_STATE recorded branch = $RECORDED_BRANCH"
  echo "live Git branch               = $LIVE_BRANCH"
fi

echo
echo "=== RECENT HISTORY ==="
git log -8 --oneline --decorate

echo
echo "=== PROJECT STATE SUMMARY ==="
python - "$STATE" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as f:
    state = json.load(f)

current = state.get("current", {})
memory = state.get("repository_memory", {})

print(f"project:           {state.get('project')}")
print(f"milestone:         {current.get('milestone')} — {current.get('name')}")
print(f"phase:             {current.get('phase')}")
print(f"recorded branch:   {current.get('branch')}")
print(f"active plan:       {current.get('active_plan')}")
print(f"base commit:       {memory.get('implementation_base_commit')}")
print(f"base tag:          {memory.get('implementation_base_tag')}")

print()
print("completed milestones:")
for name, value in state.get("completed_milestones", {}).items():
    print(
        f"  {name}: "
        f"{value.get('commit')} / "
        f"{value.get('tag')}"
    )

print()
print("current implementation status:")
for key, value in state.get("m7_implementation_status", {}).items():
    print(f"  {key}: {value}")

print()
print("next action:")
print(f"  {state.get('next_action')}")
PY

echo
echo "============================================================"
echo " MANDATORY AGENT OPERATING GUIDE"
echo "============================================================"
cat "$AGENTS"

echo
echo "============================================================"
echo " ACTIVE EXECUTION PLAN"
echo "============================================================"

if [[ -n "$ACTIVE_PLAN" && -f "$ACTIVE_PLAN" ]]; then
  cat "$ACTIVE_PLAN"
else
  echo "ERROR: active plan is missing or unreadable: $ACTIVE_PLAN" >&2
  exit 1
fi

echo
echo "============================================================"
echo " OPTIONAL DEEPER MEMORY"
echo "============================================================"
echo
echo "Capability ledger:"
echo "  docs/CAPABILITY_LEDGER.json"
echo
echo "Previous milestone:"
echo "  docs/milestones/M6.md"
echo
echo "Older milestone history:"
echo "  docs/milestones/M0.md ... M6.md"
echo
echo "Evidence:"
find docs/evidence \
  -maxdepth 2 \
  -type f \
  -print \
  2>/dev/null \
  | sort || true

echo
echo "============================================================"
echo " CURRENT M7 PHYSICAL PRESENCE"
echo "============================================================"

if [[ -d src/aivp/eval ]]; then
  echo
  echo "src/aivp/eval:"
  find src/aivp/eval -maxdepth 2 -type f -print | sort
else
  echo "src/aivp/eval: NOT PRESENT"
fi

if [[ -d evals ]]; then
  echo
  echo "evals:"
  find evals -maxdepth 3 -type f -print | sort
else
  echo "evals/: NOT PRESENT"
fi

echo
echo "============================================================"
echo " BOOTSTRAP COMPLETE"
echo "============================================================"
echo
echo "Use this output as the initial context packet for a new AI session."
echo "Read deeper milestone/evidence files only when the active task requires them."
echo "Live Git state overrides stale runtime facts in documentation."
