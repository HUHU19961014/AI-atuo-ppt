# CLI Reference

## Recommended Entry Points

| Command | Use case | Needs AI | Main output |
|---|---|---|---|
| `demo` | Render the bundled sample deck and verify the environment fast | No | `.pptx` + render logs |
| `make` | Recommended one-shot semantic V2 generation | Yes | outline + semantic deck + compiled deck + `.pptx` |
| `review` | One-pass visual review for an existing deck JSON | No | review JSON + patched deck + `.pptx` |
| `iterate` | Multi-round review and auto-fix loop | No | final review + patched deck + `.pptx` |
| `visual-draft` | HTML visual draft and scoring from DeckSpec | No (AI optional) | `.visual_spec.json` + `.preview.html` + `.preview.png` + scoring JSON |

## Advanced Commands

| Command | Use case | Needs AI | Notes |
|---|---|---|---|
| `clarify` | Clarify vague requests before generation | Optional | Outputs clarifier session JSON |
| `clarify-web` | Local browser UI for the clarifier | Optional | Starts `http://127.0.0.1:8765` by default |
| `sie-render` | Render PPTX with the actual SIE PPTX template | No | Preferred for branded SIE delivery from `StructureSpec` or `DeckSpec` JSON |
| `v2-outline` | Generate outline JSON only | Yes | Best when you want to inspect storyline first |
| `v2-plan` | Generate outline + semantic deck + compiled deck | Yes | Good for step-by-step review |
| `v2-compile` | Compile semantic deck JSON into renderable deck JSON | No | Accepts semantic deck JSON |
| `v2-render` | Render PPTX from compiled or semantic deck JSON | No | Generic / dev render path, not the actual SIE template delivery path |
| `v2-make` | Same full pipeline as `make` | Yes | Kept as the explicit V2 name |
| `v2-review` | Same as `review` | No | Explicit V2 command |
| `v2-iterate` | Same as `iterate` | No | Explicit V2 command |
| `ai-check` | Connectivity and pipeline healthcheck | Yes | Verifies the AI route; add `--with-render` to include PPT render |

## Common Examples

### No-AI smoke test

```powershell
python .\main.py demo
```

### Recommended AI generation

```powershell
python .\main.py make `
  --topic "企业 AI 战略汇报" `
  --brief "面向管理层，先给出核心判断，再展开优先级和落地路径" `
  --generation-mode deep `
  --min-slides 6 `
  --max-slides 8
```

### Step-by-step generation

```powershell
python .\main.py v2-plan `
  --topic "供应链追溯体系建设方案" `
  --generation-mode deep
```

```powershell
python .\main.py v2-render `
  --deck-json .\output\generated_deck.json
```

### Clarify before generate

```powershell
python .\main.py clarify --topic "帮我做PPT"
python .\main.py clarify-web
```

### Healthcheck with render

```powershell
python .\main.py ai-check `
  --topic "企业 AI 汇报健康检查" `
  --with-render
```

### Actual SIE template render

```powershell
python .\main.py sie-render `
  --structure-json .\projects\generated\traceability.structure.json `
  --topic "供应链追溯体系建设方案"
```

### Visual draft before PPTX

```powershell
python .\main.py visual-draft `
  --deck-spec-json .\samples\visual_draft\why_sie_choice.deck_spec.json `
  --output-dir .\output\visual_draft `
  --output-name why_sie_choice `
  --page-index 0 `
  --layout-hint auto `
  --visual-rules-path .\tools\sie_autoppt\visual_default_rules.toml `
  --with-ai-review
```

## Notes

- Current CLI is `make` + `sie-render` dual-path: use `make` for semantic AI generation and `sie-render` for actual SIE template delivery.
- `v2-render` stays available as the generic renderer used for development and regression, but it should not be described as the actual SIE template path.
- Legacy `ai-plan`, `ai-make`, `plan`, and `render` commands are not part of the active user path.
- `visual-draft` always runs rule scoring. AI visual review is optional via `--with-ai-review`.
- `--generation-mode quick` skips structured context extraction and strategy analysis.
- `--generation-mode deep` adds structured context extraction and strategy analysis before outline/deck generation.
- `ai-check --with-render` runs through PPT generation and returns render quality summary fields in addition to connectivity status.
- The current V2 CLI does not expose a `--planner-command` hook. If that extension point is reintroduced later, it should land with protocol docs and tests in the same change.
