# Deck JSON Spec

Current active workflow is the V2 semantic pipeline:

1. `outline.json`
2. `semantic_deck.json`
3. `compiled deck.json`
4. `.pptx`

`v2-render` accepts either:

- semantic deck JSON and compiles it on load
- compiled deck JSON and renders it directly

## Semantic Deck JSON

This is the AI-facing structure. It describes slide intent and content blocks, not final coordinates.

```json
{
  "meta": {
    "title": "Enterprise AI Strategy",
    "theme": "sie_consulting_fixed",
    "language": "zh-CN",
    "author": "AI Auto PPT",
    "version": "2.0"
  },
  "slides": [
    {
      "slide_id": "s1",
      "title": "Lead With Judgment",
      "intent": "conclusion",
      "key_message": "Start from the decision, not from background.",
      "anti_argument": "Upfront investment and change cost must be included in the ROI view.",
      "data_sources": [
        {
          "claim": "Pilot ROI",
          "source": "Internal pilot estimate",
          "confidence": "medium"
        }
      ],
      "blocks": [
        {
          "kind": "statement",
          "text": "Prioritize one core chain first, then expand."
        }
      ]
    }
  ]
}
```

## Compiled Deck JSON

This is the renderer-facing structure. Layout has already been chosen and normalized.

```json
{
  "meta": {
    "title": "Enterprise AI Strategy",
    "theme": "sie_consulting_fixed",
    "language": "zh-CN",
    "author": "AI Auto PPT",
    "version": "2.0"
  },
  "slides": [
    {
      "slide_id": "s1",
      "layout": "title_only",
      "title": "Prioritize one core chain first, then expand.",
      "anti_argument": "Upfront investment and change cost must be included in the ROI view.",
      "data_sources": [
        {
          "claim": "Pilot ROI",
          "source": "Internal pilot estimate",
          "confidence": "medium"
        }
      ]
    }
  ]
}
```

## Main Commands

Generate the full V2 pipeline:

```powershell
python .\main.py make `
  --topic "企业 AI 战略汇报"
```

Generate outline + semantic deck + compiled deck:

```powershell
python .\main.py v2-plan `
  --topic "供应链追溯体系建设方案"
```

Render from an existing deck JSON:

```powershell
python .\main.py v2-render `
  --deck-json .\output\generated_deck.json
```

Render with the actual SIE template from structured content:

```powershell
python .\main.py sie-render `
  --structure-json .\projects\generated\traceability.structure.json `
  --topic "供应链追溯体系建设方案"
```

Run a no-AI smoke test with the bundled sample:

```powershell
python .\main.py demo
```

## Notes

- Semantic deck JSON is the preferred AI contract for V2.
- Compiled deck JSON is the stable renderer contract.
- `sie-render` is a compatibility delivery path when you need the actual SIE PPTX template instead of the default SVG-primary V2 path.
- Layout selection is performed locally by the deck director, not by the LLM choosing renderer coordinates.
- The V2 compiler may diversify adjacent generic layouts, but it preserves strong semantic layouts such as timelines, matrices, stats dashboards, and explicit comparisons.
- `anti_argument` and `data_sources` are first-class fields in the V2 path and should be preserved during compilation.
- Render logs record rewrite behavior and warnings so each deck has a traceable render path.
