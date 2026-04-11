# Scoring System Review Decisions

评审来源：`SCORING_SYSTEM_IMPROVEMENT.md`

## Accepted

- 视觉评分维度应有单一事实源。已将 5 维硬编码 scorecard 收敛为 `VISUAL_REVIEW_DIMENSIONS`，并扩展到 9 维：`structure`、`title_quality`、`content_density`、`layout_stability`、`deliverability`、`brand_consistency`、`data_visualization`、`info_hierarchy`、`audience_fit`。
- 视觉评分的 schema、prompt 和总分计算必须从同一维度注册表派生，避免继续出现 prompt 9 维、schema 5 维、total 仍按 5 维计算的漂移。
- 视觉评审不应强绑定 OpenAI client。当前先提供 `StructuredJsonProvider` 注入点和 `OpenAIVisualReviewProvider` 默认实现，允许测试或后续 provider 复用同一接口。
- Quality gate 结果需要区分硬阻塞和软问题统计。`errors` 是硬阻塞；`warnings` 和 `high` 仍进入统计和评审上下文，但不会被误读成 `blocking`。

## Partially Accepted

- “SmartGate = 检测 + 自动修复”方向合理，但项目已经有 `quality_checks.py` + `content_rewriter.py` + `ppt_engine.py` 的自动改写链路。当前不新建并行 `smart_gate/` 模块，避免双门禁和双修复器。
- “Warning/High 改为统计指标”方向合理。当前保留 `review_required` 兼容既有视觉评审流程，同时新增 `blocking` 和 `statistics.soft_issue_count` 明确表达硬门禁与软信号的区别。
- “Provider 抽象”方向合理，但不先创建 Claude/Gemini/Ollama 空实现。只有在真实接入、配置和测试存在时再增加具体 provider。

## Rejected For Now

- 不接受把自动修复简化成纯截断。现有 `content_rewriter.py` 会尝试压缩、合并、标题改写和结构修复；机械截断会降低语义质量。
- 不接受新增 `scoring_config.yaml` 作为第二套配置事实源。当前规则配置已由 `v2/default_rules.toml` 和 `rule_config.py` 承载；后续若扩展配置，应优先复用这条链路。
- 不接受一次性重写视觉评审目录结构。当前先完成接口与事实源收敛，后续再按真实 provider 需求拆分模块。
