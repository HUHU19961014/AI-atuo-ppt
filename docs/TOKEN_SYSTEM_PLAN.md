# Theme And Layout Token Plan

This document records the current boundary decision. The goal is not to build a full token platform immediately, but to remove double sources of truth before larger theme/layout token work starts.

## Current Layers

- `tools/sie_autoppt/v2/theme_loader.py`
  - Owns V2 visual theme tokens such as colors, fonts, font sizes, spacing, and page settings.
- `tools/sie_autoppt/v2/renderers/layout_constants.py`
  - Owns V2 renderer geometry constants for now.
- `assets/templates/*.manifest.json`
  - Owns SIE template facts: selectors, render layout geometry, slide pools, and now pattern variant catalogs.
- `tools/sie_autoppt/planning/layout_policy.py`
  - Owns local selection logic: content density -> desired capacity -> layout variant.

## Decision

Do not merge V1 manifest, V2 theme, V2 renderer constants, and one-page presets into one large JSON now.

The stable split is:

- `theme` describes visual brand.
- `layout` describes renderer geometry.
- `density` and `variant` describe capacity changes within a layout family.
- `template manifest` remains the source of truth for concrete PPT template support.

## Variant Ownership

Pattern variants are now template-owned:

- `pattern_variants` lives in the template manifest.
- `TemplateManifest.pattern_variants` exposes the normalized catalog.
- `layout_policy` uses the manifest catalog when available.
- If no manifest catalog is available, `layout_policy` records `desired_capacity` but does not invent a variant name.

This prevents code from inventing unsupported names such as `org_governance_5` when the template does not define that layout.

## Recommended Next Steps

1. Keep adding new V1/SIE layout variants only through manifest-backed geometry and tests.
2. Extract a small V2 layout token bridge after the V2 renderer constants stabilize.
3. Only after V2 is stable, decide whether V1 reads token defaults through a bridge or remains manifest-driven long term.

## Do Not Do Yet

- Do not make the LLM output PowerPoint coordinates.
- Do not add renderer variants without template geometry and tests.
- Do not force V1 manifest selectors into a generic theme token schema.
- Do not migrate every renderer constant at once.
