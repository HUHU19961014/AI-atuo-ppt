# Context Snapshot

Last updated: 2026-04-05

## Project Positioning

`SIE AutoPPT` is an AI-assisted enterprise slide production pipeline:

- planning layer: topic / brief / source file -> structured deck
- rendering layer: deterministic Python PPTX generation
- polish layer: human visual refinement

## Stable Entry Points

- `make`: HTML -> PPTX
- `plan`: HTML -> `DeckSpec JSON`
- `render`: `DeckSpec JSON` -> PPTX
- `ai-plan`: AI -> `DeckSpec JSON`
- `ai-make`: AI -> PPTX
- `ai-check`: AI backend smoke test

AI slide-count behavior:

- `--chapters` for exact body-page count
- `--min-slides` / `--max-slides` for bounded planning
- content-driven default range when no count is provided

## LLM Backends

Supported backend styles:

- `responses`
- `chat_completions`
- `external_command`

Compatibility notes:

- Official OpenAI defaults to `responses`
- Non-OpenAI hosts default to `chat_completions`
- Local gateways can omit bearer auth with `SIE_AUTOPPT_ALLOW_EMPTY_API_KEY=true`
- Existing agents can integrate through `--planner-command` or by producing `DeckSpec JSON` and calling `render`

## Major Completed Work

- AI planner
- DeckSpec JSON contract
- render trace / QA transparency
- BeautifulSoup HTML parsing
- source text extraction from txt/md/html/docx/pdf
- typed payload models
- manifest `cm` units
- native reference slide import
- slide metadata name lookup
- SiliconFlow / OpenAI-compatible provider support
- external planner command support
- safe external planner execution without `shell=True`
- manifest-backed renderer error context
- deprecated legacy clone path is now explicit instead of silent

## Remaining Gaps

- no bundled OpenClaw-specific bridge script yet
- deployment-grade service packaging is still out of scope

## Latest Validation

- unit tests: `59` passing after latest review fixes
- SiliconFlow live `ai-check`: passed with `deepseek-ai/DeepSeek-V3.2`
- SiliconFlow live `ai-make`: passed and produced PPT + QA output
- external planner command smoke test: passed
