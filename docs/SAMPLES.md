# Samples Policy

`samples/` is intentionally retained as a regression fixture set.

## Why It Stays

- `demo` command depends on `samples/sample_deck_v2.json`.
- V2 render/review tests use sample decks and visual fixtures.
- Visual review prep scripts read `samples/visual_review_cases.json`.

## Scope

- `samples/sample_deck_v2.json`, `samples/sample_outline_v2.json`: CLI and renderer smoke fixtures.
- `samples/input/`: legacy/compatibility and reference-style fixture inputs.
- `samples/visual_draft/`: visual-draft fixture inputs.
- `samples/visual_review_cases.json`: visual review batch fixture registry.

## Rules

- Keep fixtures deterministic and small.
- Do not store customer data or confidential content.
- When changing or removing a sample, update the tests/scripts that reference it in the same change.
