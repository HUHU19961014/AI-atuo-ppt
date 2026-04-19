# Architecture

This document describes the **current** runtime architecture of `Enterprise-AI-PPT`.
It is aligned with the active CLI surface in `tools/sie_autoppt/cli.py`.

## Active Entry Surface

Current main commands:

- `make`: V2 semantic generation + SVG-primary render + PPTX export.
- `batch-make`: run-scoped internal batch pipeline (`input -> preprocess -> bridge -> tuning -> QA`).
- `onepage`: agent-driven one-page SIE slide generation from `StructureSpec`.
- `review` / `iterate`: aliases of `v2-review` / `v2-iterate`.
- `v2-*`: advanced explicit V2 stages (`v2-outline`, `v2-plan`, `v2-compile`, `v2-patch`, `v2-render`, `v2-make`).
- `clarify`, `clarify-web`, `ai-check`, `visual-draft`.

Removed from primary CLI surface:

- standalone `svg-pipeline`
- standalone `svg-export`
- legacy template render primary command

## System Map

```mermaid
flowchart LR
    U[User Input] --> CLI[tools/sie_autoppt/cli.py]

    CLI --> CLARIFY[clarifier.py / clarify_web.py]
    CLI --> ONEPAGE[scenario_generators/sie_onepage_designer.py]
    CLI --> V2[v2/services.py + v2/ppt_engine.py]
    CLI --> BATCH[batch/orchestrator.py]

    CLARIFY --> LLM[LLM Provider]
    V2 --> LLM
    BATCH --> PRE[batch/preprocess.py]
    BATCH --> BRIDGE[batch/pptmaster_bridge.py]
    BATCH --> TUNE[batch/tuning.py]
    BATCH --> QA[batch/qa_router.py]

    V2 --> OUT1[output/*.json + *.pptx (compat mode)]
    BATCH --> OUT2[output/runs/<run_id>/*]
```

## Runtime Flows

### V2 Semantic Flow (`make` / `v2-make`)

1. Generate outline and semantic payload with AI.
2. Compile payload into validated deck JSON.
3. Run quality gate and deterministic rewrite.
4. Generate SVG project and export PPTX.

Main files:

- `tools/sie_autoppt/v2/services.py`
- `tools/sie_autoppt/v2/deck_director.py`
- `tools/sie_autoppt/v2/ppt_engine.py`

### Internal Batch Flow (`batch-make`)

1. Validate and normalize inputs into `input/input_envelope.json`.
2. Build `preprocess/content_bundle.json`.
3. Bridge to external `pptmaster` (configured by `--pptmaster-root` or `SIE_PPTMASTER_ROOT`).
4. Verify export manifests and hashes.
5. Apply deterministic tuning.
6. Run post-export QA routing.
7. Optional: run review patch stage (`--with-ai-review`) and persist review artifacts.
8. Produce `final/final.pptx` and `final/run_summary.json`.

Main files:

- `tools/sie_autoppt/batch/orchestrator.py`
- `tools/sie_autoppt/batch/pptmaster_bridge.py`
- `tools/sie_autoppt/batch/export.py`
- `tools/sie_autoppt/batch/tuning.py`
- `tools/sie_autoppt/batch/qa_router.py`

## Internal Batch Artifact Layout

Each run is isolated under `output/runs/<run_id>/`:

- `input/input_envelope.json`
- `preprocess/content_bundle.json`
- `bridge/svg_manifest.json`
- `bridge/export_manifest.json`
- `tune/tune_report.json`
- `qa/qa_report.json`
- `qa/pre_export_qa_report.json`
- `qa/review_patch/review_once.json` (optional)
- `qa/review_patch/patches_review_once.json` (optional)
- `qa/review_patch/patched.deck.json` (optional)
- `final/final.pptx`
- `final/run_summary.json`
- `logs/spans.jsonl`, `logs/usage.jsonl`, `logs/errors.jsonl`

## Module Boundary Rules

- `batch/*` owns runtime state, retries, artifact contracts, and failure handling.
- `v2/*` owns semantic generation, deck compilation, and render logic.
- `batch-make` must not route through legacy HTML/template orchestration modules.

Compatibility-only legacy modules (not default batch path):

- `tools/sie_autoppt/generator.py`
- `tools/sie_autoppt/body_renderers.py`
- `tools/sie_autoppt/pipeline.py`
- `tools/sie_autoppt/planning/legacy_html_planner.py`

## Current Technical Debt

- `v2/services.py` still contains mixed orchestration responsibilities for compatibility commands.
- Some docs/tests still include historical fixtures and legacy compatibility assumptions.
- Scenario generator scripts need ongoing archive-vs-product boundary cleanup.
