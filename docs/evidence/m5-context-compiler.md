# M5 Context Compiler — Exit Evidence

## Status

M5 Exit Gate: **PASS**

Source commit:

`c609b6414d02d41edd1d9d45a507be838d473bb7`

Context Compiler refinement commit:

`c609b64 Improve context retrieval precision`

## Exit Gate

The M5 Master Implementation Plan requires:

1. At least one case that maintains the same Eval Quality with fewer tokens than full context.
2. Context-selection reasons must be traceable from an Artifact.

Both conditions were demonstrated.

---

## Retrieval Refinement

### Initial realistic preflight

The first realistic self-hosted preflight produced:

- Full eligible files: 267
- Full content: 828,872 chars
- Compiled files: 8
- Compiled content: 28,369 chars
- Character reduction: 96.58%

However, manifest inspection revealed a retrieval defect:

- `src/aivp/panel/config.py`, the primary target file, was omitted.
- Historical `reports/.../run-*` task artifacts were selected.

The result was rejected despite the high compression ratio.

### Corrective changes

The selector was refined to:

- preserve snake_case and camel/Pascal-style identifiers,
- assign strong weight to exact identifier matches,
- expose `exact_identifier:<identifier>` as an auditable reason,
- exclude generated `reports/.../run-*` directories from the repository map.

Focused tests were added for both behaviors.

### Refined preflight

After refinement:

- Full eligible files: 129
- Full content: 608,715 chars
- Compiled files: 8
- Compiled content: 27,272 chars
- Character reduction: 95.52%

All retrieval conditions passed:

- reduction > 90%: PASS
- primary target selected: PASS
- `exact_identifier:context_budget_from`: PASS
- relevant context test selected: PASS
- historical run artifacts absent: PASS

Preflight manifest hash:

`df9821b6e11c425afb0bfbd5cdd9cb557e694706b3b76ee21e6983fda0719140`

After refinement, the full regression suite passed:

- Unit: 197 / 197
- Integration: 11 / 11

---

## Controlled Real-Model A/B Experiment

### Task

Change the default `context.max_files` returned by
`context_budget_from()` from 20 to 18 while preserving:

- default `max_chars == 120000`,
- explicit `max_files`,
- absent-context behavior,
- disabled-context behavior,
- unrelated behavior.

### Experimental control

Both arms used:

- identical source commit,
- identical task,
- identical Codex CLI,
- identical `workspace-write` sandbox,
- identical `approval_policy="never"`,
- identical `model_reasoning_effort="low"`,
- identical external hidden gate,
- identical focused test gate,
- identical full unit suite,
- identical diff/scope checks.

The independent variable was the repository context injected into the initial generator prompt.

### Context

| Metric | FULL | COMPILED |
| --- | ---: | ---: |
| Files | 124 | 8 |
| Content chars | 606,698 | 27,272 |
| Rendered prompt-context chars | 619,393 | 34,016 |
| Total generator prompt chars | 620,558 | 35,181 |

Content character reduction:

**95.50%**

Compiled-context manifest hash:

`2ec43176509c3637a62a39d2badc7964759fb7d6f9cb134980f8a7d208937979`

### Provider-reported token usage

| Metric | FULL | COMPILED |
| --- | ---: | ---: |
| `input_tokens` | 413,779 | 110,790 |
| `cached_input_tokens` | 288,000 | 89,728 |
| `output_tokens` | 477 | 561 |
| `input + cached` diagnostic | 701,779 | 200,518 |

Provider-reported `input_tokens` reduction:

**73.22%**

The `input + cached` value is retained only as a diagnostic.
It is not treated as canonical provider token accounting because
pricing semantics may define `input_tokens` as either including or
excluding cached input.

### Quality gates

| Gate | FULL | COMPILED |
| --- | --- | --- |
| Codex exit | PASS | PASS |
| Hidden behavioral gate | PASS | PASS |
| Focused context tests | PASS | PASS |
| Full unit suite | PASS | PASS |
| `git diff --check` | PASS | PASS |
| Scope guard | PASS | PASS |

Changed paths were identical:

- `src/aivp/panel/config.py`
- `tests/unit/test_context_prompt_contract.py`

The production change was identical in both arms:
the default `max_files` changed from 20 to 18.

The generated tests were semantically equivalent.
The only material textual difference was that the FULL arm sampled
explicit values `(1, 20, 25)` while the COMPILED arm sampled
`(1, 20, 30)`.

### Latency

- FULL: 40.307 s
- COMPILED: 43.661 s

This experiment does **not** demonstrate a latency improvement.
The compiled arm was slower in this single trial.

---

## Exit Decision

M5 Exit Gate is satisfied for this controlled case.

The Context Compiler reduced the initial repository context by
95.50% and reduced provider-reported generator input tokens by
73.22%, while both arms passed the same deterministic quality gates
and stayed within the same change scope.

The Context Artifact also preserved auditable selection reasons and
a deterministic manifest hash.

---

## Limitations

This evidence is intentionally narrow.

It demonstrates one controlled task and one trial per arm.

It does not establish that:

- the same token reduction applies to every task,
- latency is improved,
- the Context Compiler always finds sufficient context,
- quality is unchanged across all repository shapes,
- the reported percentage generalizes to other models.

Codex retained repository access in both arms and could inspect files
beyond the initially injected context. Therefore the measured
provider token counts include the model's subsequent agent activity,
which is desirable for this experiment: the comparison measures
end-to-end model input consumption rather than prompt size alone.

---

## Local Raw Evidence

Raw evidence is intentionally retained under the Git-ignored path:

`reports/m5-exit/context-ab/`

Key artifact SHA-256 values captured at preservation time:

- `compiled-result.json`
  - `25d21204b1e80013c67d8d39f1864f3e5c6ac85a291aecbdccf241c5d95ee60e`
- `compiled.diff`
  - `5f8c1d301eacfad6d3b9f50818df6e49bdd322a0a4c9b6d104ee58ae6ae1f346`
- `context-manifest.json`
  - `49ffc848fa92be03ab9f4a7b280c49c28890aacbc9373f642b922c517a38e3f1`
- `full-result.json`
  - `c6f28bdbdb18434781b821e63a197c83e25977519ad449ca1ce9f710ec0c6d3b`
- `full.diff`
  - `b7e041e7bd8419a87e32e2d9ca09b8f00473f856a73ff8aba54dbbec11059b18`
- `summary.json`
  - `f6b254b2af69640281e24380907c9acc29f18fbda2f8ea8934705003d0ab0a65`

The raw artifacts remain local to avoid committing full repository
context, model transcripts, or other unnecessarily sensitive data.
