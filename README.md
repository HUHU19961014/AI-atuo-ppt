# SIE AutoPPT

`SIE AutoPPT` is now an `AI planning + deterministic PPTX rendering` pipeline for enterprise slides.

The project no longer assumes that users hand-write compliant HTML first. It supports:

- classic HTML -> PPTX rendering
- `DeckSpec JSON` planning and rendering
- AI topic -> `DeckSpec JSON` -> PPTX
- OpenAI-compatible hosted providers
- local gateways and external agent planners

## Architecture

The current workflow is split into three layers:

1. `AI planning layer`
   Converts a topic, brief, or source document into a structured deck outline.
2. `Python rendering layer`
   Maps structured pages into deterministic template coordinates and outputs `.pptx`.
3. `Human polish layer`
   Final visual tuning, alignment, animation, and client-facing refinement.

## Commands

Main CLI:

```powershell
python .\tools\sie_autoppt_cli.py
```

Supported workflow stages:

- `make`: legacy one-step HTML -> PPTX
- `plan`: HTML -> `DeckSpec JSON`
- `render`: `DeckSpec JSON` -> PPTX
- `ai-plan`: topic -> `DeckSpec JSON`
- `ai-make`: topic -> PPTX
- `ai-check`: planner connectivity smoke test

Examples:

```powershell
python .\tools\sie_autoppt_cli.py plan `
  --html .\input\uat_plan_sample.html `
  --plan-output .\projects\generated\planned.deck.json
```

```powershell
python .\tools\sie_autoppt_cli.py render `
  --deck-json .\projects\generated\planned.deck.json `
  --output-name Rendered_From_Json
```

```powershell
python .\tools\sie_autoppt_cli.py ai-make `
  --topic "制造企业 AI AutoPPT 方案汇报" `
  --brief "突出项目现状、三层架构、实施路径和风险控制"
```

## Provider Compatibility

The planner now supports multiple backend patterns:

- `Responses API` for official OpenAI-style providers
- `chat/completions` for OpenAI-compatible providers
- local gateways with optional empty API keys
- external planner commands that read JSON from stdin and write JSON to stdout

Examples:

### OpenAI-compatible provider

```powershell
$env:OPENAI_API_KEY = "your_key"
$env:OPENAI_BASE_URL = "https://api.siliconflow.cn/v1"
$env:SIE_AUTOPPT_LLM_API_STYLE = "chat_completions"
$env:SIE_AUTOPPT_LLM_MODEL = "deepseek-ai/DeepSeek-V3.2"

python .\tools\sie_autoppt_cli.py ai-check `
  --topic "provider healthcheck"
```

### Local gateway

```powershell
$env:OPENAI_API_KEY = ""
$env:OPENAI_BASE_URL = "http://localhost:4000/v1"
$env:SIE_AUTOPPT_ALLOW_EMPTY_API_KEY = "true"
$env:SIE_AUTOPPT_LLM_MODEL = "deepseek-chat"

python .\tools\sie_autoppt_cli.py ai-check `
  --topic "local gateway healthcheck"
```

### Existing agent or OpenClaw-style integration

If another agent already owns model access, you do not need a second API key inside this project.

Option A:

- let the external agent produce `DeckSpec JSON`
- call `render`

Option B:

- let the external agent act as a planner command
- call `ai-plan`, `ai-make`, or `ai-check` with `--planner-command`

Example:

```powershell
python .\tools\sie_autoppt_cli.py ai-check `
  --planner-command "python .\your_agent_bridge.py" `
  --topic "external planner check"
```

## Template and Reference Slides

Canonical template files:

- `assets/templates/sie_template.pptx`
- `assets/templates/sie_template.manifest.json`

Reference-style body pages now use native PPTX package merge by default. The bundled reference deck carries slide metadata names, so lookup order is:

1. slide metadata name
2. text marker match
3. fallback page number

## Docs

- [AI planner](./docs/AI_PLANNER.md)
- [Deck JSON spec](./docs/DECK_JSON_SPEC.md)
- [Input spec](./docs/INPUT_SPEC.md)
- [Testing](./docs/TESTING.md)

## Testing

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\run_unit_tests.ps1
```

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\regression_check.ps1
```

## Current Status

Already fixed in the current codebase:

- AI planning entrypoint
- `DeckSpec JSON` contract
- `plan/render/make` split workflow
- render trace and QA transparency
- BeautifulSoup HTML parser
- typed payload models
- `cm` unit support in manifest geometry
- native reference slide import
- external planner command support
- SiliconFlow / OpenAI-compatible provider support

Still not fully finished:

- optional COM helper scripts still exist for a few template-maintenance workflows
- full web-service-grade packaging and auth management are not done
- external agent bridges are generic, but no OpenClaw-specific bridge script is bundled yet
