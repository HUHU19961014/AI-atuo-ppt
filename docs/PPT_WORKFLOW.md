# PPT Workflow

When a PPT request is still vague, do not jump straight into layout generation.

## 1. Clarify First

Use the built-in clarification flow before generation whenever the audience, purpose, angle, or visible scope is still unclear.

```powershell
python -m sie_autoppt clarify --topic "帮我做一页PPT介绍内部追溯"
python -m sie_autoppt clarify-web
```

At minimum, freeze these inputs first:

- who will see the slide
- what decision / action / understanding the slide should create
- what angle should be emphasized
- what content is presenter guidance only and should stay off the slide
- how many pages are actually needed

## 2. Let Content Drive Layout

Choose layout from narrative shape, not by habit.

- process / mechanism topics: prefer flow or staged narrative layouts
- comparison topics: prefer side-by-side contrast layouts
- capability or value topics: prefer modular cards
- only use summary strips or presenter labels when they are audience-facing content, not internal narration

## 3. Review the Generated Artifact

One-page outputs should run a post-generation review, not just a pre-save geometry check.

```powershell
python tools/scenario_generators/review_onepage_slide.py .\output\example.pptx --review-json .\output\example.review.json --export-previews
```

The review step should at least check:

- out-of-bounds or unstable layout
- text density and likely overflow risk
- audience-inappropriate meta guidance phrases
- main card balance and page symmetry
- preview export availability for manual inspection

For DeckSpec-based V2 testing, use the built-in automated loop:

```powershell
python -m sie_autoppt v2-review --deck-json .\output\generated_deck.json
python -m sie_autoppt v2-iterate --deck-json .\output\generated_deck.json --max-rounds 2
```

The reviewer now scores exactly these 9 dimensions:

- structure
- title_quality
- content_density
- layout_stability
- deliverability
- brand_consistency
- data_visualization
- info_hierarchy
- audience_fit

And the auto-fix loop now follows this guardrail:

- if blocker issues still exist, patch generation must produce concrete DeckSpec patches
- if blockers remain but no patches are generated, the loop fails fast instead of pretending to converge
