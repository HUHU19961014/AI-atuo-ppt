# Legacy Boundary

## Current Position

- Primary path is SVG-first: `make -> v2-make -> svg_output -> svg_final -> pptx`.
- Legacy template rendering is compatibility-only and is not the default entry path.

## Main-Flow Rules

- CLI startup must not eagerly import legacy renderer implementations.
- `batch-make` must not import or route through `generator.py`, `body_renderers.py`, or `planning/legacy_html_planner.py`.
- Main generation path must not depend on:
  - `legacy.body_renderers`
  - legacy text-normalization helpers
- `sie-render` remains available only for backward compatibility scenarios.
- Legacy modules remain compatibility-only and are not part of the internal batch control plane.

## Compatibility Facades

The following modules are lazy facades for existing integrations:

- `tools/sie_autoppt/generator.py`
- `tools/sie_autoppt/body_renderers.py`
- `tools/sie_autoppt/pipeline.py`
- `tools/sie_autoppt/slide_ops.py`
- `tools/sie_autoppt/reference_styles.py`

## Verification

Use these checks before merge:

```powershell
rg -n "from \\.legacy|legacy text-normalization helpers|sie-render" tools/sie_autoppt docs README.md
```

Expected:

- no `from .legacy` in primary startup path modules
- no legacy text-normalization helper usage in primary generation path
- `sie-render` appears only in compatibility docs/command description
