# HTML Visual Draft Layer Action Plan

> **For future sessions:** This document is the continuity anchor for the HTML visual draft work. Read the design spec first: `docs/superpowers/specs/2026-04-11-html-visual-draft-layer-design.md`.

**Goal:** Build v0.3.0 so AI-generated PPT pages get an HTML visual draft and scoring pass before PPTX rendering.

**Architecture:** Keep `DeckSpec` as the content planning layer. Add `VisualSpec` as the visual planning layer. Render `VisualSpec` to a constrained single-slide HTML preview, capture a screenshot, score the draft, and only then decide whether to continue toward PPTX output.

**Tech Stack:** Python, dataclasses or Pydantic-style validation already used in the repo, BeautifulSoup if needed, Edge/Chrome headless screenshot path from `tools/scenario_generators/html_snapshot_to_ppt.py`, existing OpenAI client path from `tools/sie_autoppt/v2/visual_review.py`.

---

## Development Principles

- Do not replace the current SIE renderer in v0.3.0.
- Do not build a generic HTML-to-PPT converter in v0.3.0.
- Do not allow arbitrary HTML/CSS as the long-term interface.
- Preserve current `DeckSpec` behavior.
- Make every intermediate artifact inspectable: `.visual_spec.json`, `.preview.html`, `.preview.png`, `.visual_score.json`.
- Use the “为什么选择 SiE 赛意” one-page sales slide as the first regression sample.

## Proposed File Map

Create:

- `tools/sie_autoppt/visual_spec.py`  
  Data models and validation helpers for `VisualSpec`.

- `tools/sie_autoppt/visual_html_renderer.py`  
  Deterministic renderer from `VisualSpec` to single-slide HTML.

- `tools/sie_autoppt/visual_screenshot.py`  
  Browser screenshot capture, adapted from `tools/scenario_generators/html_snapshot_to_ppt.py`.

- `tools/sie_autoppt/visual_score.py`  
  Rule-based scoring for HTML/VisualSpec and screenshot metadata.

- `tools/sie_autoppt/visual_service.py`  
  Orchestrates DeckSpec -> VisualSpec -> HTML -> screenshot -> score.

- `tests/test_visual_spec.py`

- `tests/test_visual_html_renderer.py`

- `tests/test_visual_score.py`

- `samples/visual_draft/why_sie_choice.deck_spec.json`

Modify:

- `tools/sie_autoppt/cli.py`  
  Add a command or flag for visual draft generation.

- `docs/CLI_REFERENCE.md`  
  Document the new command.

- `README.md`  
  Mention the v0.3 visual draft flow.

Do not modify in v0.3.0 unless necessary:

- `tools/sie_autoppt/legacy/body_renderers.py`
- `tools/sie_autoppt/legacy/generator.py`
- `tools/sie_autoppt/v2/ppt_engine.py`

## Review Checkpoints

Review should happen after each checkpoint:

1. **Checkpoint A:** VisualSpec schema and sample approved.
2. **Checkpoint B:** HTML preview looks materially better than current PPT renderer output.
3. **Checkpoint C:** Rule scoring catches obvious ugly cases.
4. **Checkpoint D:** AI scoring returns actionable design feedback.
5. **Checkpoint E:** CLI produces all artifacts for the sample slide.

## v0.3.0 Tasks

### Task 1: Add VisualSpec Models

**Goal:** Define the minimum schema needed for one-page sales slides.

**Files:**

- Create: `tools/sie_autoppt/visual_spec.py`
- Test: `tests/test_visual_spec.py`

**Implementation notes:**

Define lightweight dataclasses:

- `VisualCanvas`
- `VisualBrand`
- `VisualIntent`
- `VisualLayout`
- `VisualComponent`
- `VisualSpec`

First supported component types:

- `headline`
- `subheadline`
- `hero_claim`
- `proof_card`
- `risk_card`
- `value_band`
- `footer_note`

Validation rules:

- Canvas defaults to `1280x720`.
- Slide id cannot be empty.
- Layout type must be one of `sales_proof`, `risk_to_value`, `executive_summary`.
- Component type must be supported.
- Required text fields cannot be empty.

Tests:

- Valid sample parses.
- Empty slide id fails.
- Unknown component type fails.
- Default canvas is `1280x720`.

Review output:

- Show the JSON sample and explain whether it is expressive enough for the SiE sales page.

### Task 2: Build DeckSpec to VisualSpec Mapper

**Goal:** Convert a one-page `DeckSpec` body page into a first-pass `VisualSpec`.

**Files:**

- Create or extend: `tools/sie_autoppt/visual_service.py`
- Test: `tests/test_visual_spec.py`

**Implementation notes:**

Add `build_visual_spec_from_deck_spec(deck_spec, page_index=0, layout_hint="auto")`.

Mapping logic for first version:

- If page has `pattern_id` in `claim_breakdown`, `kpi_dashboard`, or `comparison_upgrade`, choose `sales_proof`.
- If bullets contain pain/risk language, choose `risk_to_value`.
- Main title becomes `headline`.
- Subtitle or payload headline becomes `subheadline`.
- Payload metrics/claims become `proof_card`.
- Bullets containing risk terms become `risk_card`.
- Payload band/footer becomes `value_band` or `footer_note`.

Tests:

- The sample SiE page maps to a `VisualSpec`.
- `TUV / SGS`, `96.5%`, and “追溯合规” are preserved.
- Mapper does not mutate the input DeckSpec.

Review output:

- Compare original DeckSpec and generated VisualSpec side by side.

### Task 3: Render VisualSpec to HTML

**Goal:** Generate a constrained, single-file HTML slide preview.

**Files:**

- Create: `tools/sie_autoppt/visual_html_renderer.py`
- Test: `tests/test_visual_html_renderer.py`

**Implementation notes:**

HTML constraints:

- Single document.
- Fixed slide canvas: `1280px x 720px`.
- No scrolling.
- Inline CSS only.
- No external assets.
- SIE header area preserved.
- Body safe area starts below header.

Supported layouts:

- `sales_proof`: strong claim plus 3-4 proof cards.
- `risk_to_value`: left risk column, center claim, right value column.
- `executive_summary`: top claim, large metric row, bottom conclusion.

Style baseline:

- SIE red: `#AD053D`.
- Dark text: `#1F2933`.
- Muted text: `#52616B`.
- Light panel: `#F5F7FA`.
- Minimum body font: `18px`.
- Minimum detail font: `16px`.

Tests:

- HTML contains exactly one `.slide`.
- HTML contains no remote `http` assets.
- HTML contains expected `data-role` attributes.
- HTML includes key Chinese text from sample.
- HTML includes `overflow: hidden`.

Review output:

- Open the HTML in browser and compare against current PPT screenshot.

### Task 4: Capture HTML Screenshot

**Goal:** Generate a PNG preview from the HTML file.

**Files:**

- Create: `tools/sie_autoppt/visual_screenshot.py`
- Test: `tests/test_visual_score.py` or a dedicated screenshot test with mocks.

**Implementation notes:**

Reuse ideas from:

- `tools/scenario_generators/html_snapshot_to_ppt.py`

Functions:

- `resolve_browser_path(explicit_path="")`
- `html_file_to_url(html_path)`
- `capture_html_screenshot(html_path, screenshot_path, width=1280, height=720, browser_path="")`

Tests:

- URL conversion handles Windows paths.
- Browser command includes `--headless`, `--screenshot`, `--window-size=1280,720`, `--hide-scrollbars`.
- If browser is missing, error message is actionable.

Review output:

- Confirm sample HTML produces a PNG on the developer machine.

### Task 5: Add Rule-Based Visual Scoring

**Goal:** Catch objective layout problems before asking AI.

**Files:**

- Create: `tools/sie_autoppt/visual_score.py`
- Test: `tests/test_visual_score.py`

**Implementation notes:**

Input:

- `VisualSpec`
- HTML string
- Optional screenshot path

Rule dimensions:

- `readability`
- `density`
- `brand`
- `layout_balance`
- `safe_area`
- `message_clarity`
- `conversion_readiness`

Initial rules:

- Penalize if no `headline` component.
- Penalize if no `hero_claim` or `value_band`.
- Penalize if more than 8 cards.
- Penalize if detail text is too long.
- Penalize if unsupported component types appear.
- Penalize if HTML lacks `.slide`.
- Penalize if HTML references external assets.
- Penalize if layout type is unknown.

Output:

```json
{
  "score": 86,
  "level": "pass",
  "issues": []
}
```

Level thresholds:

- `pass`: `>= 85`
- `pass_with_notes`: `75-84`
- `revise`: `< 75`

Tests:

- Good sample scores at least 85.
- Missing headline lowers score.
- Too many cards lowers score.
- External asset reference lowers score.
- Unknown layout lowers score.

Review output:

- Show scoring JSON for good sample and intentionally bad sample.

### Task 6: Add AI Visual Review Interface

**Goal:** Let AI review the screenshot and return structured design feedback.

**Files:**

- Create or extend: `tools/sie_autoppt/visual_score.py`
- Create or extend: `tools/sie_autoppt/visual_service.py`
- Test: `tests/test_visual_score.py`

**Implementation notes:**

Reuse existing client patterns from:

- `tools/sie_autoppt/v2/visual_review.py`

Function:

- `review_visual_draft_with_ai(visual_spec, html_path, screenshot_path, model="")`

Schema fields:

- `score`
- `decision`
- `summary`
- `strengths`
- `issues`
- `fixes`

Dimensions:

- 商务感
- 客户说服力
- 主结论可见性
- 视觉层级
- 投影可读性
- SIE 品牌一致性
- 是否显得机械或廉价

Tests:

- Mock AI client returns structured JSON.
- Missing screenshot falls back to HTML/content-only review.
- Invalid AI response is normalized into actionable failure.

Review output:

- Run AI review once on the sample if API config is available.

### Task 7: Add Visual Draft CLI

**Goal:** Provide a stable command to generate all visual draft artifacts.

**Files:**

- Modify: `tools/sie_autoppt/cli.py`
- Test: `tests/test_cli.py`
- Docs: `docs/CLI_REFERENCE.md`

**Proposed command:**

```powershell
python .\main.py visual-draft `
  --deck-spec-json .\samples\visual_draft\why_sie_choice.deck_spec.json `
  --output-dir .\output\visual_draft `
  --output-name why_sie_choice `
  --capture-screenshot `
  --with-ai-review
```

Expected outputs:

- `why_sie_choice.visual_spec.json`
- `why_sie_choice.preview.html`
- `why_sie_choice.preview.png`
- `why_sie_choice.visual_score.json`
- `why_sie_choice.ai_visual_review.json` when enabled

Tests:

- CLI calls service with correct paths.
- CLI prints artifact paths.
- CLI works without AI review.
- CLI handles missing screenshot capability gracefully.

Review output:

- User opens the generated `.preview.html` and `.preview.png`.

### Task 8: Add Sample Regression Case

**Goal:** Lock in the SiE sales page as the first quality sample.

**Files:**

- Create: `samples/visual_draft/why_sie_choice.deck_spec.json`
- Test: `tests/test_visual_html_renderer.py`

Sample content:

- Theme: 为什么选择 SiE 赛意
- Audience: 客户销售说服
- Core claim: 选择赛意，是选择更低风险的追溯合规落地路径
- Proofs:
  - TUV / SGS / Sedex / EcoVadis
  - 晶澳、天合、正泰、横店东磁等案例
  - 多轮迭代成熟产品
  - 96.5% 客户保有率
- Customer value:
  - 少走弯路
  - 降低试错
  - 加快审核准备
  - 确保项目落地

Tests:

- Generated HTML contains all proof points.
- Rule score for sample is not below 85.
- No external assets are referenced.

Review output:

- Compare against `output/sales/why_sie_choice_sales_v3_sie_body_only.pptx`.

### Task 9: Documentation

**Goal:** Make the new flow understandable without reading code.

**Files:**

- Modify: `README.md`
- Modify: `docs/CLI_REFERENCE.md`
- Create or update: `docs/HUMAN_VISUAL_QA.md`

Docs should explain:

- What VisualSpec is.
- Why HTML preview exists.
- What score thresholds mean.
- When to use visual draft before PPTX.
- Difference between editable PPTX and screenshot PPTX.

Review output:

- User can understand v0.3 without knowing code.

## v0.4.0 Follow-Up Tasks

Goal: Produce a high-fidelity snapshot PPTX from approved HTML.

Tasks:

- Add `visual-snapshot-pptx` command.
- Reuse existing `tools/scenario_generators/html_snapshot_to_ppt.py` as implementation reference.
- Generate PPTX with screenshot as full-slide image.
- Mark output as non-editable in metadata/report.
- Output `.html`, `.png`, `.pptx`, `.visual_score.json`.

Important constraint:

- This is a fast delivery path, not the long-term editable renderer.

## v0.5.0 Follow-Up Tasks

Goal: Convert approved VisualSpec/SVG-like layout into editable PPTX.

Tasks:

- Add absolute-position layout model.
- Add VisualSpec -> SVG-like primitive compiler.
- Add primitive -> python-pptx shape renderer.
- Support text boxes, rectangles, lines, icons, metric cards, simple charts.
- Preserve SIE title, logo, page number, and safe area.
- Gradually migrate selected legacy body renderers to VisualSpec renderer.

Important constraint:

- Do not try to support arbitrary CSS. Support a finite design component set.

## Open Questions For Review

1. v0.3.0 是否只做单页销售型页面，还是同时支持 2-3 种页面类型？
2. 第一版 AI review 是否必须接真实模型，还是先做 mock + 可选真实调用？
3. HTML 预览是否需要用户手动选择 2-3 个风格版本？
4. v0.4.0 截图版 PPT 是否接受“不可编辑但好看”的临时交付？
5. v0.5.0 是否以 SVG primitive 为核心，还是直接 VisualSpec -> python-pptx？

## Decision Status (Resolved 2026-04-11)

- Q1 resolved: v0.3.0 supports three layout types (`sales_proof`, `risk_to_value`, `executive_summary`).
- Q2 resolved: AI review is optional and can be enabled with `--with-ai-review`; no API key is required for the base visual-draft workflow.
- Q3 deferred: multi-style variant generation is out of scope for v0.3.0.
- Q4 deferred to v0.4.0 as planned.
- Q5 deferred to v0.5.0 as planned.

## Recommended Next Step

Start v0.3.0 with a narrow vertical slice:

```text
why_sie_choice.deck_spec.json
  ↓
VisualSpec
  ↓
preview.html
  ↓
preview.png
  ↓
visual_score.json
```

Success criteria for the slice:

- User can open the HTML and see a materially better visual design than the current PPTX.
- Rule score catches at least three intentional bad cases.
- AI review, if configured, returns actionable feedback rather than generic praise.
- No current SIE renderer behavior is changed.
