# Deck JSON Spec

`SIE AutoPPT` now supports a structured `DeckSpec JSON` workflow:

1. `plan`: convert HTML input into a canonical deck spec
2. `render`: render PPTX from deck spec JSON
3. `make`: keep the original one-step HTML -> PPTX workflow

## Schema

```json
{
  "schema_version": "1.0",
  "cover_title": "Project Title",
  "body_pages": [
    {
      "page_key": "overview",
      "title": "Overview",
      "subtitle": "Optional subtitle",
      "bullets": ["Point A", "Point B"],
      "pattern_id": "solution_architecture",
      "nav_title": "Overview",
      "reference_style_id": null,
      "payload": {
        "layers": [
          { "label": "L01", "title": "Layer 1", "detail": "..." }
        ]
      }
    }
  ]
}
```

## CLI

Plan HTML into `DeckSpec JSON`:

```powershell
python .\tools\sie_autoppt_cli.py plan `
  --html .\input\uat_plan_sample.html `
  --plan-output .\projects\generated\planned.deck.json
```

Render PPTX from `DeckSpec JSON`:

```powershell
python .\tools\sie_autoppt_cli.py render `
  --deck-json .\projects\generated\planned.deck.json `
  --output-name SIE_Rendered_From_Json
```

Keep the original one-step flow:

```powershell
python .\tools\sie_autoppt_cli.py `
  --html .\input\uat_plan_sample.html `
  --output-name SIE_AutoPPT
```

## Notes

- `pattern_id` is the requested layout decision.
- `payload` is render-ready structured data used by Python renderers.
- QA output now records `render_trace` so every page shows its actual render route and fallback reason.
- `html_parser.py` remains a compatibility input adapter; `DeckSpec JSON` is the preferred machine-facing contract for future AI integration.
- Reference-style pages are imported through a native PPTX merge path, and the bundled reference deck is metadata-aware rather than page-number-only.
