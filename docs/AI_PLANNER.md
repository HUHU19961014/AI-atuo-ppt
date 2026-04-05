# AI Planner

`SIE AutoPPT` now supports an AI planning stage that converts a natural-language topic into `DeckSpec JSON`.

## Commands

Generate `DeckSpec JSON` from a topic:

```powershell
python .\tools\sie_autoppt_cli.py ai-plan `
  --topic "制造业 ERP 智能化升级方案汇报" `
  --brief "重点突出现状痛点、目标架构和分阶段落地路径" `
  --plan-output .\projects\generated\erp_ai.deck.json
```

Generate PPT directly from a topic:

```powershell
python .\tools\sie_autoppt_cli.py ai-make `
  --topic "制造业 ERP 智能化升级方案汇报" `
  --brief "重点突出现状痛点、目标架构和分阶段落地路径" `
  --output-name ERP_AI_AutoPPT `
  --output-dir .\projects\generated
```

Add extra context from a file:

```powershell
python .\tools\sie_autoppt_cli.py ai-plan `
  --topic "供应链协同平台建设建议" `
  --brief-file .\input\brief.txt
```

Run a live AI planner connectivity check:

```powershell
python .\tools\sie_autoppt_cli.py ai-check `
  --topic "AI AutoPPT 健康检查"
```

If `OPENAI_API_KEY` is missing, the command exits with a clear `AI healthcheck blocked` message instead of a traceback.
If the key is valid but the project has no remaining quota, the command reports a quota-specific error so you can distinguish platform billing issues from local code bugs.

## Required Environment Variables

- `OPENAI_API_KEY`: required for remote HTTP providers unless you use a local gateway or an external planner command

## Optional Environment Variables

- `OPENAI_BASE_URL`: defaults to `https://api.openai.com/v1`
- `SIE_AUTOPPT_LLM_MODEL`: defaults to `gpt-5.4-mini`
- `SIE_AUTOPPT_LLM_TIMEOUT_SEC`: defaults to `90`
- `SIE_AUTOPPT_LLM_REASONING_EFFORT`: defaults to `low`
- `SIE_AUTOPPT_LLM_VERBOSITY`: defaults to `low`
- `SIE_AUTOPPT_LLM_API_STYLE`: `responses` or `chat_completions`
- `SIE_AUTOPPT_EXTERNAL_PLANNER_CMD`: optional external planner command that reads JSON from stdin and prints JSON to stdout
- `SIE_AUTOPPT_ALLOW_EMPTY_API_KEY`: set to `true` if your local gateway does not require a bearer token

## SiliconFlow

`SIE AutoPPT` now supports OpenAI-compatible `chat/completions` providers such as SiliconFlow.

Example PowerShell session:

```powershell
$env:OPENAI_API_KEY = "your_siliconflow_key"
$env:OPENAI_BASE_URL = "https://api.siliconflow.cn/v1"
$env:SIE_AUTOPPT_LLM_API_STYLE = "chat_completions"
$env:SIE_AUTOPPT_LLM_MODEL = "deepseek-ai/DeepSeek-V3"

python .\tools\sie_autoppt_cli.py ai-check `
  --topic "硅基流动连通性检查"
```

If `OPENAI_BASE_URL` points at SiliconFlow and you do not set `SIE_AUTOPPT_LLM_API_STYLE`, the project will auto-switch to `chat_completions`.

## Other Providers

Recommended compatibility strategy:

- Official OpenAI: use `Responses API`
- OpenAI-compatible hosted providers: prefer `chat_completions`
- Local gateways such as LiteLLM or agent hubs: point `OPENAI_BASE_URL` to the local endpoint and allow empty API keys when appropriate

Example local gateway session:

```powershell
$env:OPENAI_API_KEY = ""
$env:OPENAI_BASE_URL = "http://localhost:4000/v1"
$env:SIE_AUTOPPT_ALLOW_EMPTY_API_KEY = "true"
$env:SIE_AUTOPPT_LLM_MODEL = "deepseek-chat"

python .\tools\sie_autoppt_cli.py ai-check `
  --topic "Local gateway healthcheck"
```

## Existing Agent Integration

If you already have an agent tool such as OpenClaw, there are two clean ways to avoid a second API key inside this project:

1. Let the agent produce `DeckSpec JSON`, then call:

```powershell
python .\tools\sie_autoppt_cli.py render `
  --deck-json .\projects\generated\planned.deck.json
```

2. Let the agent act as an external planner command:

```powershell
python .\tools\sie_autoppt_cli.py ai-check `
  --planner-command "your-agent-bridge-command"
```

The external command receives a JSON payload on stdin containing:

- `request`
- `developer_prompt`
- `user_prompt`
- `outline_schema`

It must print JSON to stdout. Accepted outputs:

- a top-level outline object with `cover_title` and `body_pages`
- `{ "outline": { ... } }`
- `{ "deck_spec": { ... } }`

## Planning Contract

- AI only outputs structured content choices.
- AI does not generate coordinates or `python-pptx` code.
- AI planning is constrained to stable renderer-friendly patterns:
  - `general_business`
  - `solution_architecture`
  - `process_flow`
  - `org_governance`

Any unsupported pattern choice is normalized locally before rendering.

## Reference Style Import

- Reference-style body pages now use a native PPTX package merge path by default.
- The bundled `reference_body_style.pptx` carries slide metadata names such as `comparison_upgrade_reference`.
- Reference lookup order is: slide metadata name -> text markers -> fallback page number.
