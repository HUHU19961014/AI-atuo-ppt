# Diagnostic Action Plan

## Scope

Source report: `C:\Users\CHENHU\Documents\xwechat_files\wxid_wkw77j4n8lp329_a45c\msg\file\2026-04\DIAGNOSTIC_REPORT.md`

This checklist translates the report into concrete repo work and marks what is already true in the current branch versus what needed additional cleanup.

## Already Landed In Current Code

- `clarify_web.py` exists and `clarify-web` no longer crashes the CLI on import.
- V2 supports `quick` and `deep` generation modes.
- `prompts/system/v2_strategy.md` has been added and wired into the V2 generation path.
- Structured context extraction is implemented in [`tools/sie_autoppt/v2/services.py`](./../tools/sie_autoppt/v2/services.py).
- Semantic deck schema supports `anti_argument` and `data_sources`.
- Semantic layout compilation is content-driven and no longer title-keyword-only.

## Fixed In This Pass

- Added a real `demo` command so a new user can render a bundled sample deck without any API key.
- Added a dedicated CLI reference document so command discovery is no longer spread across code comments and README fragments.
- Added this diagnostic action plan so the report items can be tracked inside the repo.
- Updated `README.md` quick-start entry points to surface `demo`, `make`, and the new docs.
- Updated `web/clarifier.html` to recommend `v2-plan` / `make` instead of removed legacy commands.
- Updated `web/demo.html` to preview current `make` usage with `--theme` instead of removed `--template`.
- Cleaned outdated compatibility guidance that still referenced historical external planner tests.
- Extended V2 quality gate with narrative checks for generic background opening pages, generic thanks closing pages, missing next-step / decision ending, repeated titles, and repeated adjacent content.
- Extended visual review prompts with rule-based quality-gate findings so review now checks narrative closure and evidence issues alongside layout stability.
- Extended `content_rewriter` with safe narrative auto-fixes: generic opening titles can be rewritten from existing subtitles, repeated titles can be differentiated from on-slide content, adjacent repeated content fragments can be removed, and obvious title-only closing pages can be converted into a concrete `next step` ending using existing prior-slide evidence.

## Intentionally Not Reintroduced In This Pass

- Historical external planner hook (`--planner-command` / `SIE_AUTOPPT_EXTERNAL_PLANNER_CMD`)

Reason:
- It is not part of the current V2 CLI surface.
- Reintroducing it cleanly now would require a fresh protocol design for outline, strategy, semantic deck, validation, and failure handling.
- Shipping protocol docs without the feature, or the feature without docs/tests, would recreate the same “report says one thing, product does another” problem.

## Remaining Or Partial Items From The Report

- `--planner-command` ecosystem is still not shipped.
  Missing artifacts if this comes back: `docs/planner-protocol.md`, `examples/external_planner.py` or equivalent runnable sample, CLI exposure in the V2 path, and tests.
- `CONTRIBUTING.md` still does not exist, so the “CLI change must update command docs” rule is not yet encoded as repo policy.
- README now has quick-start and command guidance, but it does not yet include the exact newcomer decision tree proposed in the report (`HTML / deck.json / API key / no API key`).
- `clarify-web` is fixed as a usable lightweight web clarifier, but it is not the full Phase 3 inline web editor envisioned in the report.
- The rewrite pipeline is stronger, but still deterministic-only.
  It can rewrite titles and obvious closing pages from existing deck evidence, but it cannot invent a new recommendation when the deck itself contains no actionable material.
- Some older internal docs and tooling still mention legacy template-era concepts such as `--template`.
  These are no longer on the primary user path, but they are still cleanup debt.
- The report proposed `examples/demo_deck/` as a concrete artifact.
  Current branch solves the same user problem with bundled sample deck rendering via `python .\main.py demo`, so the exact file path from the report was superseded rather than implemented literally.

## Next Backlog After This Cleanup

1. Decide whether external planner extensibility is still a product requirement for V2.
2. If yes, add it back as a first-class V2 feature with protocol doc, example implementation, and tests in one change.
3. Decide whether the rewrite pipeline should stay deterministic-only, or add an LLM-backed fix pass for cases where no safe next-step wording can be derived from the existing deck content.
4. Continue pruning stale legacy command references from older documents that are no longer entry-point docs.
