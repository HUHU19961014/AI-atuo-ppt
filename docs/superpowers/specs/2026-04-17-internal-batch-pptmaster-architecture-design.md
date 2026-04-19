# Internal Batch PPTMaster Pipeline Architecture Design

Date: 2026-04-17  
Status: Proposed  
Scope: `Enterprise-AI-PPT` internal batch tool v1  
Primary audience: repository maintainers and future implementers

## 1. Background And Decision

This document formalizes the target architecture discussed in recent design reviews:

1. Users provide text, links, images, attachments, and optional structured data.
2. AI performs content understanding, including summary, key-point extraction, OCR, image description, and slide-story planning.
3. `pptmaster` is used as the primary SVG generation engine.
4. SVG output is converted to editable PPTX.
5. Python performs deterministic second-pass tuning and quality checks before final delivery.

The repository already has a strong V2 semantic pipeline, but the current implementation is not yet aligned with this target:

- `tools/sie_autoppt/v2/services.py` is still a large orchestration function that mixes AI generation, content rewrite, local SVG project generation, and external command execution.
- `tools/sie_autoppt/v2/io.py` still defaults to shared filenames such as `generated_deck.json` and `Enterprise-AI-PPT_Presentation.pptx`, which is unfriendly for batch isolation and idempotent reruns.
- `tools/sie_autoppt/generator.py`, `body_renderers.py`, and the legacy planning helpers remain as compatibility-heavy modules and still leak conceptual complexity into the repo.
- `docs/TESTING.md` and several workflow assumptions drift away from the actual filesystem and active runtime behavior.
- The current `pptmaster` bridge in `v2/services.py` probes repo-relative script paths that do not exist in the current `Enterprise-AI-PPT/` tree, so the integration boundary is not yet production-ready.

For the current phase, the product is an internal batch tool, not a distributed platform. The architecture must therefore prioritize:

- deterministic execution
- artifact traceability
- low operator burden
- incremental migration from existing V2 code
- future commercial readiness without forcing premature service decomposition

## 2. Scope, Goals, And Non-Goals

### 2.1 Goals

1. Establish a single internal batch pipeline that produces reproducible run artifacts and a final editable PPTX.
2. Keep AI responsible for semantic understanding and layout intent, while keeping Python responsible for deterministic validation and tuning.
3. Isolate `pptmaster` behind a formal bridge so that the rest of the repo depends on a stable local contract instead of its internal scripts.
4. Reduce current orchestration coupling in `v2/services.py` and make the batch workflow testable as a state machine.
5. Define a cleanup and technical debt plan so the repo can be maintained as one coherent product instead of a mixed set of experiments.

### 2.2 Non-Goals For This Phase

1. No distributed queue, worker farm, or message bus.
2. No multi-tenant online service design.
3. No mandatory human-in-the-loop gate in the default path.
4. No full rewrite of V2 rendering logic before the batch orchestrator exists.
5. No attempt to merge every historical scenario generator into the new path on day one.

## 3. Approaches Considered

### Approach A: Continue Extending The Current V2 Monolith

Description:
Keep `make_v2_ppt()` as the central entrypoint and gradually add more branches for OCR, content bundles, `pptmaster` export, shape mapping, and second-pass tuning.

Pros:

- lowest short-term code churn
- reuses the current CLI and tests directly
- minimal file movement

Cons:

- orchestration complexity keeps accumulating in one file
- difficult to test retry semantics, timeouts, idempotency, and artifact integrity
- batch-specific concerns stay mixed with semantic generation logic
- long-term technical debt grows faster than delivered capability

Assessment:
Rejected as the primary target. Acceptable only as a short-lived transitional state.

### Approach B: Internal Batch Orchestrator + Artifact Contracts + PPTMaster Bridge

Description:
Introduce a new internal batch subsystem that owns run directories, state transitions, retry policy, artifact hashes, and external `pptmaster` invocation. Reuse existing V2 generation and quality logic as isolated modules behind this orchestrator.

Pros:

- matches the intended internal batch operating model
- keeps runtime traceable and testable
- limits future migration cost toward a service model
- lets existing V2 modules survive as reusable building blocks

Cons:

- requires moderate refactor of orchestration code
- requires new schemas and new integration tests
- needs explicit migration of CLI and docs

Assessment:
Recommended. This is the target architecture for v1.

### Approach C: Immediate Service-Oriented Agent Platform

Description:
Split preprocessing, planning, SVG generation, export, tuning, and QA into separate workers with asynchronous queues and persistent state storage.

Pros:

- future-ready for commercialization
- high theoretical throughput and scalability

Cons:

- over-designed for internal batch usage
- high operational complexity
- larger testing surface and slower delivery
- too many moving parts before contracts are mature

Assessment:
Rejected for the current phase. Revisit only after the internal batch tool stabilizes.

## 4. Recommended Architecture

## 4.1 High-Level Shape

The system should be refactored into three major concerns:

1. Control plane
2. Data plane
3. Compatibility boundary

### Control Plane

The control plane owns runtime behavior:

- run creation
- state transitions
- retry budget
- timeout policy
- artifact registration
- logging and metrics
- failure classification

This should live inside the repository and should not depend on `pptmaster` internals.

### Data Plane

The data plane owns content artifacts:

- validated input envelope
- content bundle
- planning outputs
- SVG project
- export manifest
- tuned PPTX
- QA reports

Each artifact must be immutable once written for a specific `run_id` and `stage`.

### Compatibility Boundary

The compatibility boundary isolates historical or external systems:

- V2 semantic generation
- `pptmaster`
- legacy SIE template rendering
- optional visual review

The orchestrator may call these systems, but the rest of the architecture must only consume normalized contracts.

## 4.2 Layer Model

### Layer 1: Input And Safety Layer

Responsibilities:

- file type whitelist
- file size checks
- link safety checks
- prompt injection screening for imported text and OCR results
- input normalization into one `input_envelope.json`

This layer is deterministic and must not call LLMs.

### Layer 2: AI Understanding Layer

Responsibilities:

- text summary and key-point extraction
- OCR and image description
- narrative planning and page outline generation
- output of a structured `content_bundle.json`

Important rule:
This layer must keep references back to original material. It must not collapse all source data into one lossy summary. Every generated block must retain `source_ref`, `source_hash`, and where relevant `page_ref` or `image_ref`.

### Layer 3: PPTMaster Bridge Layer

Responsibilities:

- translate `content_bundle.json` and planning metadata into `pptmaster` consumable input
- invoke `pptmaster`
- validate SVG project completeness
- export SVG to PPTX
- generate `export_manifest.json` with `shape_map` and hash binding

This is the primary layout generation layer.

### Layer 4: Deterministic Tuning And QA Layer

Responsibilities:

- brand palette enforcement
- fonts and spacing normalization
- alignment corrections
- dynamic data injection that does not require a layout reflow
- rule-based QA and final acceptance checks

Important rule:
Layer 4 may only perform safe deterministic edits. If an issue requires layout reflow, it must fail back to Layer 3 regeneration rather than mutating slide structure blindly.

## 4.3 Runtime State Machine

The batch tool should be implemented as an explicit state machine:

| State | Meaning | Output |
|---|---|---|
| `INIT` | run created, workspace initialized | `run.json` |
| `INPUT_VALIDATED` | input envelope created and accepted | `input_envelope.json` |
| `PREPROCESSING` | OCR, extraction, and AI understanding running | partial spans only |
| `BUNDLE_READY` | semantic preprocessing complete | `content_bundle.json` |
| `SVG_GENERATING` | `pptmaster` generation in progress | `svg_request.json` |
| `SVG_READY` | SVG project passes structural checks | `svg_manifest.json` |
| `EXPORTING` | SVG to PPTX export in progress | exporter logs |
| `EXPORT_READY` | PPTX exported and map verified | `export_manifest.json`, intermediate `.pptx` |
| `TUNING` | deterministic second-pass edits running | `tune_report.json` |
| `QA_CHECKING` | rule checks and repair routing | `qa_report.json` |
| `SUCCEEDED` | final output accepted | `final.pptx`, `run_summary.json` |
| `FAILED` | terminal failure after retry budget exhausted | `dead_letter.json` |

### Retry Policy

Retry must be finite and state-aware:

| Stage | Max Retry | Retry On | Do Not Retry On |
|---|---|---|---|
| Input validation | 0 | none | invalid file type, oversized attachment |
| AI preprocessing | 2 | transient provider error, parse failure | unsupported input schema |
| SVG generation | 3 | malformed SVG, missing asset refs, transient tool failure | contract mismatch, unsupported layout intent |
| SVG export | 2 | exporter transient failure | manifest-hash mismatch after repeated regeneration |
| Tuning | 1 | deterministic operation failure after known safe fix | missing `shape_map`, export hash mismatch |
| QA repair loop | 1 for tuning-only issues, 2 for regeneration issues | style defects or recoverable layout defects | blocker schema errors |

After retry budget is exhausted, the run must write `dead_letter.json` and stop.

## 5. Artifact Contracts

## 5.1 Workspace Layout

Each run must live under:

```text
output/runs/<run_id>/
  run.json
  input/
    input_envelope.json
    source/
  preprocess/
    content_bundle.json
    ocr.json
    image_descriptions.json
    planning.json
  bridge/
    svg_request.json
    svg_project/
    svg_manifest.json
    export_manifest.json
    exported_raw.pptx
  tune/
    tuned.pptx
    tune_report.json
  qa/
    qa_report.json
  final/
    final.pptx
    run_summary.json
  logs/
    spans.jsonl
    usage.jsonl
    errors.jsonl
```

No stage may write directly into another stage's directory except through the orchestrator.

## 5.2 `input_envelope.json`

Minimum fields:

```json
{
  "run_id": "20260417_143000_001",
  "created_at": "2026-04-17T14:30:00+08:00",
  "mode": "internal_batch",
  "inputs": [
    {
      "type": "text|link|image|attachment|structured_data",
      "path": "relative/original/path",
      "content_hash": "sha256:...",
      "mime_type": "...",
      "size_bytes": 123,
      "safe": true
    }
  ]
}
```

## 5.3 `content_bundle.json`

This is the central semantic contract. It must contain both derived understanding and original source references.

Minimum fields:

```json
{
  "run_id": "...",
  "bundle_version": 1,
  "bundle_hash": "sha256:...",
  "language": "zh-CN",
  "topic": "...",
  "audience": "...",
  "source_index": [
    {
      "source_ref": "src-001",
      "type": "text",
      "content_hash": "sha256:..."
    }
  ],
  "text_summary": {
    "summary": "...",
    "key_points": ["..."],
    "source_refs": ["src-001"]
  },
  "images": [
    {
      "image_ref": "img-001",
      "content_hash": "sha256:...",
      "ocr_text": "...",
      "description": "...",
      "source_refs": ["src-002"]
    }
  ],
  "story_plan": {
    "outline": [
      {
        "slide_ref": "s-001",
        "intent": "executive_summary",
        "title": "...",
        "source_refs": ["src-001", "img-001"]
      }
    ]
  }
}
```

Critical constraint:
`story_plan` may depend on the summary and image analysis, but it must still preserve source linkage so later QA can trace where content came from.

## 5.4 `svg_manifest.json`

This contract records the SVG project produced by `pptmaster`.

Minimum fields:

```json
{
  "run_id": "...",
  "bundle_hash": "sha256:...",
  "svg_bundle_hash": "sha256:...",
  "project_root": "bridge/svg_project",
  "pages": [
    {
      "page_ref": "s-001",
      "svg_path": "bridge/svg_project/svg_final/slide_01.svg",
      "svg_hash": "sha256:..."
    }
  ]
}
```

## 5.5 `export_manifest.json`

This is the only valid bridge between export and Python tuning.

Minimum fields:

```json
{
  "run_id": "...",
  "bundle_hash": "sha256:...",
  "svg_bundle_hash": "sha256:...",
  "export_hash": "sha256:...",
  "exporter_version": "pptmaster-bridge-v1",
  "pptx_path": "bridge/exported_raw.pptx",
  "shape_map": [
    {
      "page_ref": "s-001",
      "svg_node_id": "node-123",
      "ppt_shape_name": "Shape 9",
      "ppt_shape_index": 9,
      "role": "title"
    }
  ]
}
```

Rule:
Layer 4 must refuse to run if `svg_bundle_hash` or `export_hash` no longer matches the actual exported file set.

## 5.6 `qa_report.json`

QA output must be machine-readable and repair-routable.

Minimum fields:

```json
{
  "run_id": "...",
  "status": "passed|repairable|failed",
  "issues": [
    {
      "issue_id": "qa-001",
      "class": "style|layout|schema|mapping|content",
      "severity": "warning|high|error",
      "repair_route": "tune|regenerate|stop",
      "page_ref": "s-001",
      "message": "..."
    }
  ]
}
```

## 6. Proposed Code Structure

## 6.1 New Modules To Add

Create a new package:

```text
tools/sie_autoppt/batch/
  __init__.py
  orchestrator.py
  state.py
  workspace.py
  contracts.py
  hashing.py
  logging.py
  input_guard.py
  preprocess.py
  planning.py
  pptmaster_bridge.py
  export.py
  tuning.py
  qa_router.py
  dead_letter.py
```

### Responsibilities

| Module | Responsibility |
|---|---|
| `orchestrator.py` | state machine entrypoint for internal batch runs |
| `state.py` | run states, transitions, retry policy, failure codes |
| `workspace.py` | create run directories and artifact paths |
| `contracts.py` | Pydantic models for envelope, bundle, manifests, reports |
| `hashing.py` | file and bundle content hash helpers |
| `logging.py` | span logging, usage accounting, structured run logs |
| `input_guard.py` | deterministic validation and safety checks |
| `preprocess.py` | OCR, summary, image description, bundle creation |
| `planning.py` | optional narrative planning adapter if split from preprocess |
| `pptmaster_bridge.py` | invoke external `pptmaster` and produce SVG bundle |
| `export.py` | wrap SVG-to-PPTX export and `export_manifest` creation |
| `tuning.py` | deterministic PPTX edits based on `shape_map` |
| `qa_router.py` | classify issues into tune vs regenerate vs terminal failure |
| `dead_letter.py` | serialize terminal failures for operator triage |

## 6.2 Existing Files To Keep But Re-Scope

### Keep As Core Reusable Logic

- `tools/sie_autoppt/llm_openai.py`
- `tools/sie_autoppt/prompting.py`
- `tools/sie_autoppt/language_policy.py`
- `tools/sie_autoppt/v2/schema.py`
- `tools/sie_autoppt/v2/semantic_schema_builder.py`
- `tools/sie_autoppt/v2/deck_director.py`
- `tools/sie_autoppt/v2/quality_checks.py`
- `tools/sie_autoppt/v2/content_rewriter.py`

These stay useful, but they must stop acting as the only orchestration surface.

### Keep But Thin Down

- `tools/sie_autoppt/cli.py`
- `tools/sie_autoppt/cli_v2_commands.py`
- `tools/sie_autoppt/v2/services.py`
- `tools/sie_autoppt/v2/io.py`

These should become thin composition layers, not feature accumulation points.

### Keep As Compatibility-Only

- `tools/sie_autoppt/generator.py`
- `tools/sie_autoppt/body_renderers.py`
- `tools/sie_autoppt/generation_runtime.py`
- `tools/sie_autoppt/generation_support.py`
- `tools/sie_autoppt/pipeline.py`
- `tools/sie_autoppt/openxml_slide_ops.py`
- `tools/sie_autoppt/presentation_ops.py`
- `tools/sie_autoppt/reference_styles.py`
- `tools/sie_autoppt/planning/legacy_html_planner.py`
- `tools/sie_autoppt/planning/legacy_html_support.py`

These must remain outside the default internal batch path.

## 7. Detailed Code Adjustment Plan

## 7.1 CLI And Entry Surface

### Current Situation

- `main.py` is a simple passthrough to `tools.sie_autoppt.cli:main`.
- `cli.py` currently owns command parsing, environment patching, clarification, and direct wiring into V2 command handlers.
- `cli_parser.py` already contains `--isolate-output` and `--run-id`, which is a useful starting point for batch isolation.

### Required Changes

1. Keep `main.py` unchanged.
2. Add a new primary command, for example `batch-make`, or redefine `make` to use the batch orchestrator once stable.
3. Move batch-specific run lifecycle logic out of `cli.py` and into `batch/orchestrator.py`.
4. Keep `cli.py` responsible only for:
   - parse args
   - resolve command
   - create command context
   - call orchestrator or legacy/V2 compatibility functions

### Concrete Refactor

- `tools/sie_autoppt/cli.py`
  - remove direct orchestration branching for the future batch path
  - call `batch.orchestrator.run_batch_make(...)`
- `tools/sie_autoppt/cli_v2_commands.py`
  - keep V2 compatibility commands
  - add explicit internal-batch command wiring

## 7.2 V2 Services Refactor

### Current Situation

`make_v2_ppt()` in `tools/sie_autoppt/v2/services.py` currently does all of the following in one function:

- normalize arguments
- generate context
- generate outline
- generate semantic deck
- compile semantic deck
- run quality gate
- run rewrite pass
- write artifacts
- create local SVG project
- invoke external SVG pipeline
- write a text log

This is too much responsibility for one function.

### Required Changes

Split `v2/services.py` into reusable pure functions:

- `generate_outline_with_ai(...)`
- `generate_semantic_deck_with_ai(...)`
- `compile_semantic_payload(...)`
- `run_pre_render_quality_gate(...)`
- `build_svg_project_from_deck(...)`

Then remove orchestration from `make_v2_ppt()` and either:

- deprecate it in favor of the batch orchestrator
- or keep it as a thin wrapper over batch mode for backward compatibility

## 7.3 Output And Workspace Management

### Current Situation

`tools/sie_autoppt/v2/io.py` still defaults to shared output filenames such as:

- `generated_outline.json`
- `generated_semantic_deck.json`
- `generated_deck.json`
- `Enterprise-AI-PPT_Presentation.pptx`

This is not safe for repeated internal batch runs.

### Required Changes

1. Introduce run-scoped workspaces under `output/runs/<run_id>/`.
2. Treat the existing default filenames as compatibility-only output aliases, not primary runtime storage.
3. Add immutable artifact naming plus symlink-like or copy-based convenience outputs only when explicitly requested.

### Concrete Refactor

- extend `v2/io.py` or replace it for batch mode with `batch/workspace.py`
- `default_*_output_path()` remains for compatibility commands only
- batch mode never writes directly to shared top-level `output/*.json`

## 7.4 PPTMaster Integration

### Current Situation

`v2/services.py` probes repo-relative `pptmaster` scripts via:

- `projects/ppt-master/...`
- `skills/ppt-master/...`

These paths do not exist in the current `Enterprise-AI-PPT/` subproject tree. The actual reference project currently lives outside this repo.

### Required Changes

1. Stop probing ad hoc relative paths in core orchestration.
2. Introduce one explicit configuration source:
   - env var `SIE_PPTMASTER_ROOT`
   - or CLI option `--pptmaster-root`
3. Validate the external bridge on startup and fail fast with a clear error if the required scripts are missing.
4. Wrap all external calls in `batch/pptmaster_bridge.py`.

### Concrete Refactor

- remove direct script path probing from `v2/services.py`
- add bridge config model in `batch/contracts.py`
- add bridge validation function:
  - check presence of `total_md_split.py`
  - check presence of `finalize_svg.py`
  - check presence of `svg_to_pptx.py`

## 7.5 Shape Map And Export Integrity

### Current Situation

The current pipeline writes a final PPTX, but the future second-pass tuning architecture requires a formal map between SVG nodes and PPT shapes. That map does not exist today as a first-class contract.

### Required Changes

1. Define `export_manifest.json` as mandatory.
2. Include:
   - `run_id`
   - `bundle_hash`
   - `svg_bundle_hash`
   - `export_hash`
   - `exporter_version`
   - `shape_map`
3. Require tuning to verify hash consistency before applying any edit.

### Design Rule

No deterministic tuning step may operate only by "find title-ish text box" heuristics when a shape map exists. Heuristics may be used only as a fallback mode and must be reported as degraded operation.

## 7.6 Deterministic Tuning

### Scope Of Layer 4

Allowed in Layer 4:

- font family replacement
- font size clamp within tolerance
- color token normalization
- alignment and spacing normalization
- footer/header normalization
- chart label and numeric fill when shape placeholders already exist

Not allowed in Layer 4:

- regenerate page composition
- add arbitrary new layout sections
- move large content blocks across page regions
- fix semantic page ordering

If any of those are required, QA must route back to Layer 3 regeneration.

### Proposed Module

`batch/tuning.py` should expose:

- `verify_export_manifest(...)`
- `apply_brand_tuning(...)`
- `apply_safe_spacing_tuning(...)`
- `apply_dynamic_data_fill(...)`
- `write_tune_report(...)`

## 7.7 QA Routing

### Current Situation

`v2/quality_checks.py` and `content_rewriter.py` already provide a rule-based quality gate and a fixable rewrite pass. These are valuable, but they currently operate on deck JSON before SVG export, not on the full layered pipeline you now want.

### Required Changes

Split QA into two moments:

1. Pre-export semantic QA
2. Post-tuning output QA

And classify issues into three routes:

- `tune`
- `regenerate`
- `stop`

### Example Routing Rules

| Issue Class | Route |
|---|---|
| brand color drift | `tune` |
| font mismatch | `tune` |
| minor spacing violation | `tune` |
| missing section or content overflow caused by layout choice | `regenerate` |
| invalid artifact hash | `stop` |
| missing shape map for required tuning action | `stop` |

## 8. Testing Strategy

## 8.1 Testing Principles

The new architecture must be tested at five levels:

1. unit tests
2. contract tests
3. workflow integration tests
4. regression tests
5. operator acceptance checks

The current repo already has strong V2 and quality-gate test coverage. The new system should reuse that base, not replace it.

## 8.2 Unit Tests

Add focused tests for:

- `batch/input_guard.py`
- `batch/hashing.py`
- `batch/workspace.py`
- `batch/contracts.py`
- `batch/qa_router.py`
- `batch/dead_letter.py`
- `batch/tuning.py`

Specific examples:

- reject oversized files
- compute stable hash for identical content
- create isolated run workspace
- fail if `export_manifest.json` hash does not match actual exported file
- classify QA issue into `tune` vs `regenerate`

## 8.3 Contract Tests

Every artifact contract must have schema validation tests:

- `input_envelope.json`
- `content_bundle.json`
- `svg_manifest.json`
- `export_manifest.json`
- `qa_report.json`
- `run_summary.json`

Use Pydantic models and fixture roundtrips:

- valid fixture loads successfully
- missing required field fails
- mismatched hash is rejected
- unexpected enum values fail with clear messages

## 8.4 Integration Tests

Introduce integration tests that do not require the real external `pptmaster` repo:

- fake bridge returns deterministic SVG project
- fake exporter returns deterministic PPTX and shape map
- orchestrator runs full state machine in a temp workspace
- retry budget stops after configured attempts
- dead letter is written on repeated failure

These tests must be fast and fully local.

## 8.5 External Bridge Tests

Create opt-in bridge tests for the real `pptmaster` dependency:

- validate configured `SIE_PPTMASTER_ROOT`
- verify required script presence
- run one small SVG export smoke case

These tests must be marked optional and skipped by default in normal unit runs.

## 8.6 Regression Tests

Maintain three regression layers:

### Semantic Regression

Re-use and extend:

- `tests/test_v2_services.py`
- `tests/test_v2_schema.py`
- `tests/test_v2_render.py`

### Batch Pipeline Regression

Add new regression fixtures under a dedicated folder, for example:

```text
tests/fixtures/batch/
  text_only/
  text_plus_image/
  structured_data/
```

Each fixture should assert:

- final state
- expected artifact files exist
- manifest hashes match
- no duplicate outputs are produced for one run

### QA Regression

Add fixtures that intentionally trigger:

- tune-route issues
- regenerate-route issues
- terminal stop issues

## 8.7 Documentation Drift Tests

The repo currently shows signs of doc/runtime drift. Add a small test suite that verifies documented scripts and paths actually exist.

Examples:

- if `docs/TESTING.md` mentions a required script, the script must exist
- if `README.md` advertises a command, the parser must still support it
- if the bridge requires `pptmaster`, the docs must state how it is configured

This can be implemented as a lightweight file existence and command-surface test.

## 8.8 Performance And Reliability Checks

Add lightweight internal checks for:

- max runtime per stage
- number of retries used
- token usage budget per run
- number of generated files per run
- no shared-output collisions across two parallel runs

Because this is an internal batch tool, this level of observability is sufficient for now. No distributed tracing system is required.

## 9. Cleanup And Garbage Code Plan

## 9.1 Immediate Cleanup Candidates

These should be removed from versioned source control or explicitly ignored:

- `.tmp_ppt_master_research/`
- `.tmp_pytest_cache/`
- `.tmp_test_runtime/`
- `.tmp_test_workspace/`
- `.mypy_cache/`
- `.ruff_cache/`
- `__pycache__/`

These are runtime or research artifacts, not product code.

## 9.2 Repo Hygiene Actions

1. Update `.gitignore` to ensure all temporary research and cache directories are excluded.
2. Move one-off exploratory research outside the product repo or under an explicit `research/` area with documentation.
3. Keep `output/` runtime artifacts out of source control except curated examples.

## 9.3 Scenario Generator Review

`tools/scenario_generators/` currently contains many one-off scripts. Not all of them belong in the long-term product surface.

Classify them into:

### Keep

- `sie_onepage_designer.py` if it remains a supported workflow
- `build_onepage_from_json.py` if still used for reproducible internal demos

### Archive

Domain-specific one-off scripts that are no longer part of the main product path should move to `tools/archive/scenario_generators/` or a similar archive location.

Examples likely suitable for archive review:

- `build_sie_battery_passport_slide.py`
- `build_equipment_mfg_digital_solution_slide.py`
- `build_internal_traceability_uat_logic_slide.py`
- other customer- or topic-specific builders

Rule:
If a script is not part of the default CLI, not used by tests, and not required for demos, it should not stay in the active top-level tool surface.

## 9.4 Legacy Module Quarantine

The following modules should be explicitly documented as compatibility-only and eventually moved under a stronger quarantine boundary:

- `generator.py`
- `body_renderers.py`
- `generation_runtime.py`
- `generation_support.py`
- `pipeline.py`
- `openxml_slide_ops.py`
- `presentation_ops.py`
- `reference_styles.py`

They do not need to be deleted immediately, but they must not keep influencing the active internal batch architecture.

## 9.5 Documentation Cleanup

The current doc set is valuable but too large and partly stale. Do not delete aggressively. Instead:

1. Keep these as product-facing core docs:
   - `README.md`
   - `docs/ARCHITECTURE.md`
   - `docs/CLI_REFERENCE.md`
   - `docs/API_REFERENCE.md`
   - `docs/TESTING.md`
   - `docs/TROUBLESHOOTING.md`
   - `docs/LEGACY_BOUNDARY.md`

2. Move design-history documents and temporary reports under a clearly labeled `docs/archive/` or `docs/history/`.
3. Update `docs/ARCHITECTURE.md` so it distinguishes:
   - current architecture
   - target internal batch architecture

## 10. Technical Debt Register

| Priority | Debt | Evidence | Impact | Resolution |
|---|---|---|---|---|
| P0 | monolithic orchestration in `v2/services.py` | `make_v2_ppt()` owns full pipeline | hard to test and evolve | extract batch orchestrator and pure service helpers |
| P0 | shared default output filenames | `v2/io.py` default paths | batch collisions, poor idempotency | run-scoped workspace |
| P0 | missing formal `pptmaster` bridge config | current script probing paths do not exist locally | fragile external dependency | `SIE_PPTMASTER_ROOT` and bridge validation |
| P0 | no first-class shape map contract | required by target tuning architecture | unsafe deterministic edits | mandatory `export_manifest.json` |
| P0 | QA route ambiguity | current design mixes tune and regenerate concerns | wrong repair strategy | issue routing by class |
| P1 | doc/runtime drift | `docs/TESTING.md` references absent scripts | operator confusion | doc drift tests and documentation cleanup |
| P1 | oversized compatibility modules | `body_renderers.py`, `generator.py`, `services.py` are large | maintenance burden | quarantine legacy and split orchestration |
| P1 | scenario generator sprawl | many domain-specific scripts | noisy repo surface | classify keep vs archive |
| P1 | mixed artifact semantics | V2 JSON, deck JSON, SVG project, PPTX lack unified manifest chain | hard debugging | explicit contracts and hash propagation |
| P2 | optional visual review coupled to active docs | useful but not central to internal batch v1 | distracts scope | keep as optional workflow |

## 11. Phased Delivery Plan

## Phase 1: Establish Control Plane

Deliverables:

- `batch/workspace.py`
- `batch/contracts.py`
- `batch/hashing.py`
- `batch/input_guard.py`
- `batch/orchestrator.py` skeleton
- run-scoped output directories

Exit criteria:

- one run creates isolated workspace
- one invalid input fails before LLM use
- contracts validate and write correctly

## Phase 2: Refactor Semantic And Bridge Integration

Deliverables:

- pure helper extraction from `v2/services.py`
- `batch/preprocess.py`
- `batch/pptmaster_bridge.py`
- explicit `SIE_PPTMASTER_ROOT`

Exit criteria:

- semantic generation can be called without invoking full pipeline
- missing `pptmaster` root fails fast with a clear message
- one fake bridge integration test passes end to end

## Phase 3: Export Manifest And Deterministic Tuning

Deliverables:

- `export_manifest.json`
- `batch/export.py`
- `batch/tuning.py`
- hash-bound shape map verification

Exit criteria:

- tuning refuses stale export artifacts
- one style-only defect is repaired through Layer 4
- one layout defect is correctly routed away from Layer 4

## Phase 4: QA Routing, Cleanup, And Documentation

Deliverables:

- `batch/qa_router.py`
- dead letter handling
- cleanup of temp dirs and archived scripts
- updated architecture and testing docs

Exit criteria:

- QA can route issues to `tune`, `regenerate`, or `stop`
- docs match real commands and scripts
- temp research and cache directories are out of version control

## 12. Definition Of Done For Internal Batch v1

The architecture is considered successfully implemented when all of the following are true:

1. `make` or `batch-make` runs through a run-scoped orchestrator rather than a monolithic inline function.
2. Every stage writes a typed artifact with a content hash.
3. `pptmaster` is integrated through explicit configuration and a stable bridge module.
4. Python second-pass tuning only runs when `export_manifest.json` verifies successfully.
5. QA failures are classified into deterministic tuning, regeneration, or terminal stop.
6. Default internal regression tests cover the full local batch pipeline without requiring the real external `pptmaster` repo.
7. Temporary research and cache directories are removed from tracked source.
8. `docs/ARCHITECTURE.md` and `docs/TESTING.md` are aligned with the code that actually runs.

## 13. Immediate Next Steps

1. Implement Phase 1 before touching `pptmaster` bridge details.
2. Extract orchestration out of `v2/services.py` before adding more feature branches to it.
3. Treat `export_manifest.json` as mandatory before any serious Layer 4 tuning work starts.
4. Freeze new scenario-specific scripts until the active and archived tool boundary is decided.
5. Clean the repo surface so future architectural work happens on a trustworthy baseline.

## 14. Summary

The correct target for the current product stage is not a distributed agent platform. It is a disciplined internal batch pipeline with:

- one explicit orchestrator
- immutable run artifacts
- AI-first semantic understanding
- `pptmaster` as the primary SVG layout engine
- deterministic Python tuning after export
- clear compatibility quarantine for historical modules

This design preserves the strongest parts of the current codebase, removes the most dangerous orchestration debt, and creates a clean migration path from the existing V2 pipeline to the user-proposed layered architecture without forcing premature platform complexity.
