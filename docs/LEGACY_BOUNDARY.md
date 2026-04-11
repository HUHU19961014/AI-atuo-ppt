# Legacy Boundary

当前仓库对外已经是 `V2-first`，但仍保留一条实际在用的 SIE 模板兼容链路。
这条链路不是死代码，所以要显式隔离，而不是继续和主路径混放。

## 已完成的边界整理

- 新增 `tools/sie_autoppt/legacy/`，承接 V1/SIE 模板链路实现。
- 顶层兼容 facade 已固定，外部 import 不需要改：
  - `tools/sie_autoppt/generator.py`
  - `tools/sie_autoppt/pipeline.py`
  - `tools/sie_autoppt/slide_ops.py`
  - `tools/sie_autoppt/reference_styles.py`
  - `tools/sie_autoppt/body_renderers.py`

## 已明确归入 `legacy/` 的实现

- `legacy/generator.py`
  - SIE 模板生成总编排
  - preallocated slide pool / legacy clone 切换
  - reference body import 与 render trace 生成
- `legacy/pipeline.py`
  - `html/json -> DeckPlan` 的兼容编排
- `legacy/presentation_ops.py`
  - `python-pptx` 侧的 slide clone / reorder / remove
- `legacy/openxml_slide_ops.py`
  - PPTX zip 包级 slide import / metadata / asset repair
- `legacy/reference_styles.py`
  - reference style registry
  - reference body slide 定位
  - reference page 回填
- `legacy/body_renderers.py`
  - 模板链路正文页、目录页、主题页渲染
  - pattern renderer 注册与布局选择

## planning 层当前拆分

### legacy planning 入口

- `planning/legacy_html_planner.py`
  - `infer_legacy_requested_chapters`
  - `build_legacy_page_specs`
- `planning/legacy_card_analysis.py`
  - 承接 `ai_pythonpptx_strategy.html` 一类 legacy card-analysis 分支

### shared support 层

- `planning/text_utils.py`
  - `compact_text / concise_text / shorten_for_nav / split_title_detail / short_stage_label`
- `planning/legacy_html_support.py`
  - legacy HTML 专用文案整理与 pattern hint 逻辑
- `planning/payload_builders.py`
  - `process_flow / roadmap / kpi / risk / claim / governance` 等 payload 生成 helper

### 主文件保留内容

- `planning/deck_planner.py`
  - 仍然是 planning 主入口
  - 现在主要保留 shared orchestration、layout/pagination 决策、兼容 wrapper
  - legacy HTML 与 card-analysis 入口、文本 helper、payload helper 已基本外提

## 暂时不要直接迁移的部分

- `tools/sie_autoppt/planning/deck_planner.py`
  - 继续按 helper 级别收敛，不做整文件搬迁
- `tools/sie_autoppt/template_manifest.py`
  - 目前仍承载模板事实源，等 token schema 方向明确后再判断是否需要再分层

## 下一步建议

1. 继续清理 `deck_planner.py` 中仍偏兼容层的 wrapper，确认哪些值得继续保留在主入口。
2. 评估 `template_manifest.py`、layout policy、pattern catalog 在未来 token 体系中的职责边界。
3. 等 V2 token schema 定下来后，再决定 V1 是接 bridge 还是继续停留在兼容域。
