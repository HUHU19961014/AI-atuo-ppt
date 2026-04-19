# CLI Reference

## Recommended Commands

| Command | Use case | Needs AI | Main output |
|---|---|---|---|
| `make` | Default one-shot generation (`AI -> SVG -> PPTX`) | Yes | outline + semantic deck + compiled deck + `.pptx` |
| `batch-make` | Internal batch pipeline (`input -> clarify -> content bundle -> pptmaster -> tuning -> QA`) | Yes | `output/runs/<run-id>/preprocess/clarify_result.json` + `output/runs/<run-id>/final/final.pptx` (+ review patch artifacts when `--with-ai-review`) |
| `review` | One-pass visual review for a deck JSON | Yes | review JSON + patch JSON + `.pptx` |
| `iterate` | Multi-round visual review and auto-fix loop | Yes | final review JSON + patch JSON + `.pptx` |

## Compatibility / Advanced

| Command | Description |
|---|---|
| `onepage` | One-page SIE slide generation (agent-driven) |
| `v2-outline` | Outline generation only (with strategy controls and rationale) |
| `v2-plan` | Outline + semantic candidates + selected compiled deck |
| `v2-compile` | Compile semantic deck JSON to renderable deck JSON |
| `v2-patch` | Apply incremental JSON patch set to an existing compiled deck |
| `v2-render` | Generic renderer command (non-primary path) |
| `v2-make` | Explicit name of the same make pipeline |
| `v2-review` | Explicit name of `review` |
| `v2-iterate` | Explicit name of `iterate` |
| `ai-check` | AI connectivity and pipeline healthcheck |
| `clarify`, `clarify-web` | Requirement clarification flows |
| `visual-draft` | HTML visual draft generation with optional AI review pass |

## Examples

```powershell
python .\main.py make --topic "浼佷笟 AI 鎴樼暐姹囨姤"
```

```powershell
python .\main.py review --deck-json .\output\generated_deck.json --llm-model gpt-4o-mini
```

```powershell
python .\main.py v2-patch --deck-json .\output\generated_deck.json --patch-json .\output\patches_round_1.json --plan-output .\output\generated_deck.patched.json
```

## Notes

- Default `make` is SVG-primary and should produce PPTX exported from `svg_final`.
- `batch-make` is the isolated internal control-plane entrypoint for run-scoped artifacts and `pptmaster` bridge execution.
- Standalone `svg-pipeline` / `svg-export` are not main CLI commands in the current parser surface.
- Add `--progress` to long-running commands (`make`, `batch-make`, `v2-plan`, `v2-render`, `ai-check`) to print stage markers to stderr.
- Agent-First vs Runtime-API: default mode is `--llm-mode agent_first` (`SIE_AUTOPPT_LLM_MODE=agent_first`): skip local API-key precheck and rely on upstream auth response.
- Use `--llm-mode runtime_api` for strict remote endpoint/API-key validation before request dispatch.
- `OPENAI_API_KEY` is required in `runtime_api` mode for remote endpoints; optional in `agent_first` mode.
- `batch-make --content-bundle-json` can bypass AI preprocess calls and run without preprocessing API credentials.
- `batch-make --with-ai-review` enables post-export review patch stage and writes `qa/review_patch/review_once.json`, `qa/review_patch/patches_review_once.json`, `qa/review_patch/patched.deck.json`.
- A09 rollout flags:
  - `SIE_AUTOPPT_AI_FIVE_STAGE_ENABLED` (`0/1`) controls legacy vs five-stage path for `batch-make`.
  - `SIE_AUTOPPT_AI_FIVE_STAGE_ROLLOUT_PERCENT` controls canary percentage (0-100) by deterministic run-id bucket.
  - `SIE_AUTOPPT_AI_FIVE_STAGE_AUTO_ROLLBACK=1` allows automatic fallback to legacy path when five-stage run fails.
- `--batch-size` applies to both `v2-plan` and `batch-make` for semantic candidate generation; the highest-scored candidate is selected automatically.
- Use root `.env.example` as baseline for environment configuration.
- Language alias normalization is enabled for generation (`en` -> `en-US`, `zh` -> `zh-CN`).
- `v2-outline` output is an object with `pages`, `story_rationale`, `outline_strategy` (`chapter_count`, `audience_tier`, `narrative_pacing`).
- Batch `story_plan.outline[*]` now includes argument-level references (`argument_refs`) for finer `source_refs` traceability.
- Plugin-based extension is supported through `SIE_AUTOPPT_PLUGIN_MODULES` and optional `SIE_AUTOPPT_MODEL_ADAPTER`.
- Command/stage/mode contract matrix is tracked in `docs/CLI_CONTRACTS.json`.

