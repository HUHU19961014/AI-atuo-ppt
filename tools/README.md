# Tools Index

The `tools/` directory now separates day-to-day entrypoints from archived one-off helpers.

## Primary Entry Points

- `main.py` from the repo root is the preferred no-install local entrypoint
- `run_unit_tests.ps1`: unit and light integration tests
- `v2_regression_check.ps1`: V2 deck regression
- `run_real_ai_smoke.ps1`: optional real-model smoke test, disabled by default unless the environment is configured
- `prepare_visual_review.ps1`: internal no-AI V2 visual review batch wrapper
- `prepare_visual_review.py`: internal no-AI V2 visual review batch generator
- `regression_check.ps1`: deprecated compatibility wrapper for legacy HTML regression

## Compatibility Wrappers

- `sie_autoppt_cli.py`: deprecated wrapper kept for older local commands
- `legacy_html_regression_check.ps1`: legacy HTML sample regression kept only for compatibility validation

## Template and Reference Utilities

- Template and reference utilities now live in [`tools/template_utils`](./template_utils/README.md)
- `tools/template_utils/import_external_pptx_template.py`: export assets and fusion hints from external PPTX templates
- `tools/template_utils/catalog_external_templates.py`: batch-scan a template directory and rank fusion candidates
- `review_scoring.py`

## Scenario Generators

- Domain-specific generators now live in [`tools/scenario_generators`](./scenario_generators/README.md)

## Archive

- `tools/archive/` is kept only as an empty placeholder for historical snapshots.
