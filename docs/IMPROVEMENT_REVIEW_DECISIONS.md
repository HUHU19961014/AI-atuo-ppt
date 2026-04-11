# Improvement Review Decisions

Source: external `IMPROVEMENT_PLAN.md`, reviewed on 2026-04-11.

## Accepted

- Pattern variants are useful, but they must be template-backed.
- Layout diversity guidance is useful, but the LLM should express semantic variety rather than PowerPoint coordinates.
- Layout capacity should be explicit so planning can reason about density without inventing unsupported renderer names.
- V1/SIE template behavior should remain manifest-driven until a V2 token bridge is stable.

## Implemented

- `assets/templates/*.manifest.json` can define `pattern_variants`.
- `TemplateManifest.pattern_variants` loads inherited variant catalogs.
- Manifest loading rejects a variant whose `id` is not present in `render_layouts`.
- `layout_policy` uses manifest variants as the only variant source.
- `layout_hints["desired_capacity"]` records capacity even when no variant exists.
- V2 slide prompt now asks for semantic structure variety across neighboring slides.
- V2 semantic compilation now applies a conservative local diversity pass for adjacent generic layouts.

## Rejected For Now

- Do not revive or extend the removed `ai_planner.py` path.
- Do not ask the LLM to output raw coordinates or CSS-like positions.
- Do not add renderer variants such as `gb_1plus3`, `gb_3plus1`, or radial layouts unless the manifest has concrete geometry and tests.
- Do not merge V1 manifest, V2 themes, renderer constants, and one-page presets into a single token schema yet.

## Local Diversity Rule

The compiler may adjust adjacent generic layouts only when the alternative is schema-safe:

- consecutive `title_content` can switch the latter to `two_columns` when it has enough content to split;
- consecutive fallback `two_columns` can switch the latter back to `title_content`;
- strong semantic layouts such as `timeline`, `matrix_grid`, `stats_dashboard`, `cards_grid`, `title_image`, and comparison-driven `two_columns` are preserved.

## Follow-Up Gate

Any future layout variant must include:

- A `pattern_variants` entry in the template manifest.
- A matching `render_layouts.<variant_id>` entry.
- A planner or renderer regression test proving the variant is selectable and renderable.
