# HTML Visual Draft Layer Design

## 背景

当前 SIE PPT 生成路径已经能把内容放进真实模板，但视觉效果仍然偏机械。最近生成的“为什么选择 SiE 赛意”销售页暴露了几个典型问题：

- 版式像系统自动排版，不像商务演示页。
- 主结论不够强，视觉焦点弱。
- 文本层级、字号、间距和留白不稳定。
- 直接用 `python-pptx` renderer 塞内容，审美上限偏低。
- 等 PPTX 生成后再发现“丑”，返工成本高。

因此后续方向不是继续给每个 renderer 手工调坐标，而是新增一个视觉中间层，让系统先能生成、预览、评分和修正视觉稿，再进入 PPTX 交付。

## 参考项目启发

### ppt-master

参考点：

- 采用“设计规格 -> 画布表达 -> PPTX”的分层思路。
- 强调最终 PPTX 应该可编辑，而不是简单截图。
- SVG 比 HTML 更接近 PPT，因为两者都是固定画布和绝对定位。

对本项目的启发：

- HTML 适合预览和评审，但不宜作为唯一长期中间层。
- 长期应以 `VisualSpec` 或 SVG-like 结构作为核心视觉中间层。
- PPTX renderer 应成为最终执行器，不承担全部设计判断。

参考链接：

- https://github.com/hugohe3/ppt-master
- https://raw.githubusercontent.com/hugohe3/ppt-master/main/docs/technical-design.md

### frontend-slides

参考点：

- 先生成可视化 HTML 预览，让用户和 AI 能直接判断风格。
- 每页按固定 viewport 设计，避免滚动。
- 强调风格预设、内容密度控制和避免通用 AI 视觉风格。

对本项目的启发：

- 先做 HTML 视觉稿，可以快速提升审美反馈速度。
- 可在正式生成 PPTX 前做截图评分和人工 review。
- 可支持同一页生成 2-3 个视觉方向供选择。

参考链接：

- https://github.com/lu920115/frontend-slides-skill
- https://raw.githubusercontent.com/lu920115/frontend-slides-skill/main/SKILL.md
- https://raw.githubusercontent.com/lu920115/frontend-slides-skill/main/STYLE_PRESETS.md

### chat-excel

参考点：

- AI 负责生成计划和操作意图，程序负责执行、校验和结果管理。
- 不让 AI 直接随意改最终文件，避免不可控输出。

对本项目的启发：

- AI 应输出 `VisualSpec`，而不是直接自由写复杂 PPT 坐标。
- 程序负责校验、渲染、评分和保留中间产物。
- 评分不过关时，AI 根据结构化反馈修正 `VisualSpec`。

参考链接：

- https://github.com/cosimo17/chat-excel
- https://github.com/oujiangping/chat-excel

## 目标

新增 v0.3.0 能力：`HTML Visual Draft + Scoring`。

一句话目标：

> 在生成 PPTX 之前，先生成一份可预览、可评分、可迭代修改的 HTML 视觉稿，让系统先判断“美不美、为什么丑、怎么改”，再进入 PPTX 渲染。

## 非目标

v0.3.0 不做以下事情：

- 不完整替换现有 SIE renderer。
- 不直接实现任意 HTML 到可编辑 PPTX 的通用转换。
- 不承诺所有 CSS 都能转 PPT。
- 不引入复杂前端框架作为第一版依赖。
- 不把截图版 PPT 当成长期唯一交付方式。

这些可以放到 v0.4.0 和 v0.5.0。

## 推荐架构

```text
User Brief
  ↓
StructureSpec
  ↓
DeckSpec
  ↓
VisualSpec
  ↓
HTML Preview / SVG Preview
  ↓
Visual Scoring
  ↓
Revision Loop
  ↓
PPTX Renderer
```

各层职责：

- `StructureSpec`：负责用户意图、受众、页数、用途、章节。
- `DeckSpec`：负责讲什么，包括页面主题、观点、证据、客户收益。
- `VisualSpec`：负责怎么表达，包括布局、层级、组件、颜色、字号、留白。
- `HTML Preview`：负责让人和 AI 看见页面效果。
- `Visual Score`：负责判断视觉稿是否值得进入 PPTX。
- `PPTX Renderer`：负责最终交付，优先保持可编辑。

## VisualSpec 概念

`VisualSpec` 是新中间层，建议按“页”组织。

示例字段：

```json
{
  "schema_version": "0.1",
  "slide_id": "why_sie_choice",
  "canvas": {
    "width": 1280,
    "height": 720,
    "safe_area": {"left": 72, "top": 92, "right": 72, "bottom": 54}
  },
  "brand": {
    "template": "sie",
    "primary_color": "#AD053D",
    "font_family": "Microsoft YaHei"
  },
  "intent": {
    "audience": "客户决策人",
    "occasion": "销售介绍",
    "core_message": "选择赛意，是选择更低风险的追溯合规落地路径"
  },
  "layout": {
    "type": "sales_proof",
    "visual_focus": "center_claim",
    "density": "medium"
  },
  "components": [
    {
      "type": "headline",
      "role": "main_claim",
      "text": "选择赛意，是选择更低风险的追溯合规落地路径"
    },
    {
      "type": "proof_card",
      "label": "认证经验",
      "value": "TUV / SGS",
      "detail": "熟悉第三方审核关注点"
    }
  ]
}
```

第一版不需要一次覆盖所有页面类型，只需要支持销售说服页所需的组件：

- `headline`
- `subheadline`
- `hero_claim`
- `proof_card`
- `risk_card`
- `value_band`
- `footer_note`

## HTML Preview 约束

HTML 是视觉预览层，不是任意网页。

第一版约束：

- 单页固定 16:9 画布，默认 `1280x720`。
- 不允许页面滚动。
- 不允许复杂交互。
- 不允许外部网络资源。
- CSS 写在单文件内，便于归档。
- 每个元素使用稳定 class 和 `data-role`。
- 所有元素必须在 SIE 安全区内，页眉、logo、页码区域不能被正文占用。

HTML 示例骨架：

```html
<section class="slide" data-layout="sales-proof" data-template="sie">
  <header class="sie-header">
    <h1 data-role="title">为什么选择 SiE 赛意？</h1>
    <div data-role="logo">SiE 赛意</div>
  </header>
  <main class="slide-body">
    <div class="hero-claim" data-role="main-claim">更低风险的追溯合规落地路径</div>
    <div class="proof-grid" data-role="proof-grid">
      <article class="proof-card" data-role="proof-card">
        <p class="label">认证经验</p>
        <p class="value">TUV / SGS</p>
        <p class="detail">熟悉第三方审核关注点</p>
      </article>
    </div>
  </main>
</section>
```

## 评分机制

评分分两层：规则评分和 AI 视觉评分。

### 规则评分

规则评分用于发现客观问题：

- 最小字号是否小于阈值。
- 文本是否溢出元素框。
- 元素是否超出画布或 SIE 安全区。
- 页面是否出现滚动。
- 是否存在过多元素。
- 关键主张是否缺失。
- 是否使用超过限制的颜色数量。
- 是否缺少视觉焦点。

建议输出：

```json
{
  "score": 82,
  "level": "pass_with_notes",
  "issues": [
    {
      "severity": "medium",
      "dimension": "readability",
      "message": "Two proof-card details use 10px text, below the 12px recommendation."
    }
  ]
}
```

### AI 视觉评分

AI 视觉评分用于判断主观质量：

- 是否像客户商务汇报页。
- 是否有销售说服力。
- 是否一眼能看到主结论。
- 是否显得廉价、机械、拥挤或空洞。
- 是否符合赛意品牌气质。
- 是否比当前 PPT renderer 输出更好。

建议 AI 返回结构化结果：

```json
{
  "score": 78,
  "decision": "revise",
  "summary": "主张明确，但右侧证据卡片过密，视觉重心偏散。",
  "fixes": [
    "Reduce proof cards from 4 to 3 or enlarge the top two proofs.",
    "Move the main claim higher and increase contrast."
  ]
}
```

## 迭代闭环

第一版建议最多迭代 2 次：

```text
Generate VisualSpec
  ↓
Render HTML
  ↓
Capture Screenshot
  ↓
Rule Score + AI Score
  ↓
If score < 80: revise VisualSpec
  ↓
Final HTML Draft
```

默认阈值：

- `>= 85`：通过。
- `75-84`：可用，但带改进建议。
- `< 75`：不建议进入 PPTX。

## 与 SIE 模板模式的关系

已有的 SIE adaptive template mode 继续保留：

- 少于 10 页：正文页 body-only。
- 10 页及以上：可使用封面、目录、结尾页。

新增视觉中间层后：

- SIE 模板负责品牌固定区域：标题、logo、页码、页眉线、安全区。
- AI 视觉层负责正文区域：主张、卡片、对比、数据、图形。
- renderer 负责把合格的视觉设计落地到 PPTX。

## 版本路线

### v0.3.0

HTML Visual Draft + Scoring。

目标是先解决“看起来丑但系统不知道”的问题。

交付物：

- `VisualSpec` schema。
- VisualSpec -> HTML renderer。
- HTML screenshot capture。
- 规则评分。
- AI 视觉评分接口。
- 一页销售型样例回归：为什么选择 SiE 赛意。

### v0.4.0

HTML Snapshot PPT delivery。

目标是快速交付高保真视觉效果。

交付物：

- HTML 截图嵌入 PPTX。
- 输出 `.html`、`.png`、`.pptx`、评分报告。
- 清楚标记此 PPTX 不可编辑。

### v0.5.0

VisualSpec/SVG to editable PPTX。

目标是长期正确的可编辑商务 PPT 生成。

交付物：

- VisualSpec -> SVG-like absolute layout。
- SVG/VisualSpec -> python-pptx shape renderer。
- 文本、卡片、色块、图标尽可能可编辑。
- SIE body renderer 逐步迁移到 VisualSpec renderer。

## 当前建议

下一步不要继续手调单页 PPT。应优先开 v0.3.0：

1. 固化 VisualSpec。
2. 生成 HTML 视觉稿。
3. 截图并评分。
4. 用“为什么选择 SiE 赛意”作为第一条质量回归样例。

这样可以先证明：系统生成的视觉稿明显比当前 PPT renderer 好，再决定是否进入 HTML/SVG -> PPTX 转换。

## Decision Log (2026-04-11 Implementation Update)

- `visual-draft` now supports three layouts in v0.3.0:
  - `sales_proof`
  - `risk_to_value`
  - `executive_summary`
- Rule scoring remains the primary gate in all runs.
- AI visual review is optional (enabled via CLI flag `--with-ai-review`), so the workflow can run without API keys.
- Auto-revision loop runs once only when AI review is enabled and first-round rule score is below `75`.
- If AI review is disabled and rule score is below `75`, command exits with an actionable error.
