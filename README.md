# SIE AutoPPT

`SIE AutoPPT` is an `AI planning + deterministic PPTX rendering` pipeline for enterprise slides.

It is designed for a practical workflow:

1. use AI to explore a topic, brief, image, or source material
2. converge on structure and layout intent
3. convert that intent into `DeckSpec JSON` or structured HTML
4. render a `.pptx` against an enterprise template
5. do final human polish inside PowerPoint

The project no longer assumes that users hand-write compliant HTML first. It supports:

- classic HTML -> PPTX rendering
  - legacy `phase-*` / `scenario` / `note` blocks
  - explicit `<slide data-pattern="...">...</slide>` pages
- requirement clarification for fuzzy requests
- `DeckSpec JSON` planning and rendering
- AI topic -> `DeckSpec JSON` -> PPTX
- OpenAI-compatible hosted providers
- local gateways and external agent planners

## V2 Recommended Workflow

The repository now also includes a `V2 structure-first pipeline` that is closer to the rebuild PRD:

1. AI generates `outline JSON`
2. AI generates `deck JSON`
3. local schema validates the deck
4. fixed Python renderers generate `.pptx`

Recommended local entrypoint without package installation:

```bash
python main.py v2-render --deck-json ./samples/sample_deck_v2.json
```

Recommended one-shot AI flow:

```bash
python main.py v2-make \
  --topic "AI Auto PPT V2 重构方案" \
  --theme business_red
```

Default V2 outputs now align to the repo-local `output/` directory:

- `output/generated_outline.json`
- `output/generated_deck.json`
- `output/generated.pptx`
- `output/log.txt`

## Quickstart

### 1. Install

```bash
python -m venv .venv
. .venv/Scripts/activate
python -m pip install --upgrade pip
python -m pip install -e .[dev]
```

If your shell does not support editable installs with extras, you can still use:

```bash
python -m pip install -r requirements.txt
python -m pip install pytest
```

### 2. Smoke test the local codebase

```bash
python -m pytest tests -q
python -m sie_autoppt ai-check --topic "AI AutoPPT 健康检查"
```

### 3. Generate your first deck

Plan from topic:

```bash
python -m sie_autoppt ai-plan \
  --topic "制造企业 AI AutoPPT 方案汇报" \
  --brief "突出项目现状、三层架构、实施路径和风险控制" \
  --min-slides 6 \
  --max-slides 10 \
  --plan-output ./projects/generated/first.deck.json
```

Render from DeckSpec JSON:

```bash
python -m sie_autoppt render \
  --deck-json ./projects/generated/first.deck.json \
  --output-name First_Render
```

One-step HTML -> PPTX:

```bash
python -m sie_autoppt make \
  --html ./input/uat_plan_sample.html \
  --output-name Html_Render
```

Compatibility script entrypoint still works:

```powershell
python .\tools\sie_autoppt_cli.py
```

Clarify a fuzzy request before planning:

```powershell
python -m sie_autoppt clarify `
  --topic "帮我做一个给管理层看的 Q2 汇报" `
  --clarifier-state-file .\projects\generated\clarifier_state.json
```

## Architecture

The current workflow is split into four layers:

1. `Clarifier layer`
   Collects missing user intent when the request is still fuzzy.
2. `Structure layer`
   Converts a topic into `core_message + sections` before any page writing starts.
3. `Content + rendering layer`
   Maps structure into `DeckSpec`, then renders deterministic `.pptx`.
4. `Human polish layer`
   Final visual tuning, alignment, animation, and client-facing refinement.

## Main commands

- `make`: one-step HTML -> PPTX
- `plan`: HTML -> `DeckSpec JSON`
- `render`: `DeckSpec JSON` -> PPTX
- `ai-plan`: topic -> `DeckSpec JSON`
- `ai-make`: topic -> PPTX
- `ai-check`: planner connectivity smoke test
- `clarify`: fuzzy request -> structured clarification state
- `structure`: topic -> `Structure JSON`
- `structure-plan`: topic / `Structure JSON` -> `DeckSpec JSON`
- `structure-make`: topic / `Structure JSON` -> PPTX

Structure-first example:

```powershell
python -m sie_autoppt structure `
  --topic "做一个 AI 行业趋势汇报" `
  --structure-output .\projects\generated\trend.structure.json

python -m sie_autoppt structure-plan `
  --structure-json .\projects\generated\trend.structure.json `
  --plan-output .\projects\generated\trend.deck.json

python -m sie_autoppt structure-make `
  --structure-json .\projects\generated\trend.structure.json `
  --output-name Trend_Structure_Render
```

## HTML and planning examples

```powershell
python .\tools\sie_autoppt_cli.py plan `
  --html .\input\uat_plan_sample.html `
  --plan-output .\projects\generated\planned.deck.json
```

```html
<div class="title">Supply Chain Compliance Program</div>

<slide data-pattern="overview">
  <h2>Global regulation trend</h2>
  <ul>
    <li>GDPR and cross-border data controls</li>
    <li>Supply-chain due diligence requirements</li>
  </ul>
</slide>

<slide data-pattern="process_flow">
  <h2>Implementation roadmap</h2>
  <ul>
    <li>Assess</li>
    <li>Design</li>
    <li>Launch</li>
  </ul>
</slide>
```

```powershell
python .\tools\sie_autoppt_cli.py render `
  --deck-json .\projects\generated\planned.deck.json `
  --output-name Rendered_From_Json
```

```powershell
python .\tools\sie_autoppt_cli.py ai-make `
  --topic "制造企业 AI AutoPPT 方案汇报" `
  --brief "突出项目现状、三层架构、实施路径和风险控制" `
  --min-slides 6 `
  --max-slides 10
```

AI planning page-count options:

- `--chapters`: exact body-page count
- `--min-slides` / `--max-slides`: let AI choose inside a range
- if none are provided, the planner infers a reasonable range from source density instead of forcing 3 pages

HTML planning/rendering page-count options:

- if `--chapters` is omitted, legacy HTML keeps all detected legacy sections and `<slide>` HTML keeps all detected slide tags
- `--chapters` still works as an explicit cap for both `plan` and `make`

## Provider compatibility

The planner supports multiple backend patterns:

- `Responses API` for official OpenAI-style providers
- `chat/completions` for OpenAI-compatible providers
- local gateways with optional empty API keys
- external planner commands that read JSON from stdin and write JSON to stdout

### OpenAI-compatible provider

```powershell
$env:OPENAI_API_KEY = "your_key"
$env:OPENAI_BASE_URL = "https://api.siliconflow.cn/v1"
$env:SIE_AUTOPPT_LLM_API_STYLE = "chat_completions"
$env:SIE_AUTOPPT_LLM_MODEL = "deepseek-ai/DeepSeek-V3.2"

python -m sie_autoppt ai-check --topic "provider healthcheck"
```

### Local gateway

```powershell
$env:OPENAI_API_KEY = ""
$env:OPENAI_BASE_URL = "http://localhost:4000/v1"
$env:SIE_AUTOPPT_ALLOW_EMPTY_API_KEY = "true"
$env:SIE_AUTOPPT_LLM_MODEL = "deepseek-chat"

python -m sie_autoppt ai-check --topic "local gateway healthcheck"
```

### Existing agent or external planner integration

If another agent already owns model access, you do not need a second API key inside this project.

Option A:

- let the external agent produce `DeckSpec JSON`
- call `render`

Option B:

- let the external agent act as a planner command
- call `ai-plan`, `ai-make`, or `ai-check` with `--planner-command`

Example:

```powershell
python -m sie_autoppt ai-check `
  --planner-command "python .\your_agent_bridge.py" `
  --topic "external planner check"
```

## Template and reference slides

Canonical template files:

- `assets/templates/sie_template.pptx`
- `assets/templates/sie_template.manifest.json`

Additional template variants:

- `assets/templates/business_gold/template.pptx`
- `assets/templates/minimal_gray/template.pptx`

Each variant now carries its own `manifest.json` and `style_guide.md`. The manifest loader supports folder-level manifests plus `extends`, so new template families can inherit the base pool and only override style-specific settings.

Recommended `style_guide.md` format is a small YAML-like subset:

```md
theme_name: Executive Gold
accent_rgb: [168, 126, 33]
preferred_item_counts: [3, 4, 6]
renderer_hints:
  section_kicker_case: uppercase
prompt_notes:
- Keep titles boardroom-ready.
summary: |
  Multi-line notes stay on separate lines.
```

Supported patterns now include:

- heading lines such as `# Business Gold`
- `key: value`
- JSON-style arrays and objects such as `[168, 126, 33]`
- `key:` followed by indented nested keys
- `key:` followed by bullet lists
- block text with `|` and folded text with `>`
- inline comments after values, while preserving literal color strings such as `#AD053D`

Reference-style body pages now use native PPTX package merge by default. The bundled reference deck carries slide metadata names, so lookup order is:

1. slide metadata name
2. text marker match
3. fallback page number

Templates without `slide_pools` still have a legacy runtime clone path, but it is explicitly deprecated. New templates should migrate to preallocated pools.
The bundled default template ships with a 20-pair preallocated slide pool, so classic HTML decks are no longer limited to three body pages.

`tools/upgrade_template_pool.py` runs on the Python/OpenXML path and does not require PowerPoint or COM. After every upgrade it validates slide count, ending slide position, and cloned directory-slide assets, so the CLI is not a blind best-effort operation.

## Testing

Preferred commands:

```bash
python -m pytest tests -q
```

```bash
python -m unittest discover -s tests -v
```

PowerShell helpers:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\run_unit_tests.ps1
powershell -ExecutionPolicy Bypass -File .\tools\regression_check.ps1
```

## Docs

- [AI planner](./docs/AI_PLANNER.md)
- [Deck JSON spec](./docs/DECK_JSON_SPEC.md)
- [Input spec](./docs/INPUT_SPEC.md)
- [Testing](./docs/TESTING.md)
- [Human visual QA](./docs/HUMAN_VISUAL_QA.md)
- [Project direction confirmation](./docs/PROJECT_DIRECTION_CONFIRMATION.md)
- [Structure-first architecture](./docs/STRUCTURE_FIRST_ARCHITECTURE.md)
- [Structure quality test set](./docs/STRUCTURE_QUALITY_TESTSET.md)

## Current status

Already solid in the current codebase:

- AI planning entrypoint
- structure-first generation entrypoint
- structure validation with retry
- `DeckSpec JSON` contract
- `plan/render/make` split workflow
- render trace and QA transparency
- BeautifulSoup HTML parser
- typed payload models
- `cm` unit support in manifest geometry
- native reference slide import
- external planner command support
- safe external planner execution
- SiliconFlow / OpenAI-compatible provider support
- template style-guide markdown parsing
- multi-template variants and demo page prototype

Still in progress:

- packaging and end-user workflow hardening
- richer preflight/content QA for delivery confidence
- further modularization of planning/rendering internals
