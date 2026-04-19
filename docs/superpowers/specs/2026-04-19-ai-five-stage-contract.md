# AI Five-Stage Command Contract (A01 + A07)

Date: 2026-04-19  
Status: Drafted for implementation alignment

## Goal

Unify command-level contract semantics for the five-stage AI pipeline and remove ambiguity between Agent-First and Runtime-API execution modes.

## Stage Keys

The canonical stage keys are fixed to:

- `clarify`
- `outline`
- `semantic_deck`
- `quality_rewrite`
- `review_patch`

All command contracts must use only these keys in `primary_stage` and `stage_chain`.

## Command Contract Schema

`docs/CLI_CONTRACTS.json` is the single source of truth for command behavior. Each command entry must contain:

- `command`
- `canonical_command`
- `primary_stage`
- `stage_chain`
- `input_schema`
- `output_schema`
- `ai_execution_mode`
- `requires_api_key`
- `fallback_mode`
- `retry_policy`

### Alias Rule

User-facing aliases (for example `review`, `iterate`) must have dedicated entries and set `canonical_command` to the executed command.

### Cross-Stage Rule

Commands spanning multiple stages must define:

- one `primary_stage` for indexing and ownership,
- one ordered `stage_chain` for runtime semantics.

## AI Execution Modes

### `agent_first` (default)

- Used unless explicitly overridden by `--llm-mode runtime_api`.
- Local API-key precheck is skipped.
- Missing/invalid credentials are surfaced by upstream runtime response instead of local pre-validation.

### `runtime_api`

- Explicit compatibility mode.
- Enforces endpoint/API-key pre-validation behavior for remote endpoints.
- Keeps strict local config checks before request dispatch.

## API-Key Contract

`requires_api_key` is mode-aware:

- `agent_first`: false
- `runtime_api`: true for AI commands
- `none`: false

For non-AI commands (`ai_execution_mode = none`), all `requires_api_key` flags remain false.

## Special Case: `visual-draft`

`visual-draft` defaults to non-AI flow (`ai_execution_mode = none`). AI is only activated with `--with-ai-review`; this is modeled through `fallback_mode` instead of changing the default execution mode.

## Acceptance Criteria

1. Contract entries cover all `WORKFLOW_COMMANDS` in `tools/sie_autoppt/cli.py`.
2. Alias canonical mapping matches `COMMAND_ALIASES`.
3. `--llm-mode` is available in CLI and propagated to `SIE_AUTOPPT_LLM_MODE`.
4. `load_openai_responses_config()` enforces key checks only in `runtime_api` mode for remote endpoints.
5. README and CLI reference explicitly document Agent-First vs Runtime-API behavior.
6. `batch-make` preprocess artifacts include `preprocess/clarify_result.json` for traceability.

## A03 Outline Strategy Contract (Incremental)

The outline stage extends its contract for strategist-style planning:

- `OutlineGenerationRequest` accepts optional strategy controls:
  - `chapter_count`
  - `audience_tier` (`executive | management | practitioner | mixed | general`)
  - `narrative_pacing` (`fast | balanced | deep`)
- Outline response schema now requires:
  - `pages`
  - `story_rationale`
  - `outline_strategy`
- `outline_strategy` must include:
  - `chapter_count`
  - `audience_tier`
  - `narrative_pacing`
- Validation now blocks outlines with:
  - page count out of bounds,
  - missing strategy/rationale fields,
  - generic or low-readability titles,
  - missing opening/closing narrative structure.

### A03 Acceptance Additions

1. Outline prompt carries conclusion-led + pacing controls with validation feedback retry.
2. Structure issues are intercepted at outline stage and retried before semantic deck generation.
3. `generated_outline.json` retains strategy/rationale metadata for traceability.

## A04 Semantic Candidate + SourceRefs Granularity (Incremental)

Semantic stage now supports candidate scoring/selection and finer evidence linkage:

- `v2-plan` and `batch-make preprocess` accept candidate count via `--batch-size`.
- Semantic generation prefers batch candidate path (including `batch-size=1`), with fallback to sequential generation if batch API is unavailable.
- Candidate scoring dimensions:
  - structural consistency (expected outline pages vs semantic slides),
  - evidence coverage (`data_sources` + block density),
  - renderability (semantic payload can compile to validated deck).
- Highest-scored candidate is selected as the primary semantic payload.
- Batch `story_plan.outline[*]` now includes `argument_refs`:
  - `argument`
  - `source_refs`
  - optional `block_ref`

### A04 Acceptance Additions

1. Semantic stage supports multi-candidate generation and deterministic best-candidate selection.
2. `--batch-size=1` remains compatible while still using candidate batch path when available.
3. Batch planning artifacts preserve argument-level traceability via `argument_refs`.
