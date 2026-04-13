# CLI Reference

## Recommended Commands

| Command | Use case | Needs AI | Main output |
|---|---|---|---|
| `make` | Default one-shot generation (`AI -> SVG -> PPTX`) | Yes | outline + semantic deck + compiled deck + `.pptx` |
| `review` | One-pass visual review for a deck JSON | No | review JSON + patch JSON + `.pptx` |
| `iterate` | Multi-round visual review and auto-fix loop | No | final review JSON + patch JSON + `.pptx` |
| `svg-pipeline` | Run `total_md_split -> finalize_svg -> svg_to_pptx` | No | `svg_final` + exported `.pptx` |
| `svg-export` | Export existing SVG project directly | No | native `.pptx` + `_svg.pptx` |

## Compatibility / Advanced

| Command | Description |
|---|---|
| `sie-render` | Legacy compatibility path (not default) |
| `v2-outline` | Outline generation only |
| `v2-plan` | Outline + semantic + compiled deck |
| `v2-compile` | Compile semantic deck JSON to renderable deck JSON |
| `v2-patch` | Apply incremental JSON patch set to an existing compiled deck |
| `v2-render` | Generic renderer command (non-primary path) |
| `v2-make` | Explicit name of the same make pipeline |
| `v2-review` | Explicit name of `review` |
| `v2-iterate` | Explicit name of `iterate` |
| `ai-check` | AI connectivity and pipeline healthcheck |
| `clarify`, `clarify-web` | Requirement clarification flows |

## Examples

```powershell
python .\main.py make --topic "企业 AI 战略汇报"
```

```powershell
python .\main.py svg-pipeline --svg-project-path .\projects\ppt-master\examples\demo_project_intro_ppt169_20251211
```

```powershell
python .\main.py review --deck-json .\output\generated_deck.json --vision-provider claude --llm-model claude-3-7-sonnet-latest
```

```powershell
python .\main.py v2-patch --deck-json .\output\generated_deck.json --patch-json .\output\patches_round_1.json --plan-output .\output\generated_deck.patched.json
```

## Notes

- Default `make` is SVG-primary and should produce PPTX exported from `svg_final`.
- `sie-render` is kept for compatibility and should not be used as the default production entry.
- `review/iterate` support `--vision-provider auto|openai|claude`.
- Add `--progress` to long-running commands (`make`, `v2-plan`, `v2-render`, `sie-render`, `ai-check`) to print stage markers to stderr.
- `OPENAI_API_KEY` is optional by default; set it when your provider requires direct API-key auth.
- To enforce strict local key requirement, set `SIE_AUTOPPT_REQUIRE_API_KEY=1`.
- Use root `.env.example` as baseline for environment configuration.
- Language alias normalization is enabled for generation (`en` -> `en-US`, `zh` -> `zh-CN`).
- Plugin-based extension is supported through `SIE_AUTOPPT_PLUGIN_MODULES` and optional `SIE_AUTOPPT_MODEL_ADAPTER`.
