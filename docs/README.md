# 文档索引

这里保留当前项目仍在使用的说明文档，优先围绕 V2 语义链路组织。

## 快速入口

- [仓库 README](../README.md)
- [CLI Reference](./CLI_REFERENCE.md)
- [Diagnostic Action Plan](./DIAGNOSTIC_ACTION_PLAN.md)

## 推荐阅读

- [项目一页介绍](./PROJECT_OVERVIEW_CN.md)
- [Deck JSON 规范](./DECK_JSON_SPEC.md)
- [输入规范](./INPUT_SPEC.md)
- [PPT 工作流](./PPT_WORKFLOW.md)
- [测试说明](./TESTING.md)
- [兼容性说明](./COMPATIBILITY.md)

## 进阶文档

- [输入规范补充](./INPUT_SPEC_SUPPLEMENT.md)
- [人工视觉检查](./HUMAN_VISUAL_QA.md)
- [LLM 兼容说明](./LLM_COMPATIBILITY.md)
- [参考样式库](./REFERENCE_STYLE_LIBRARY.md)
- [外部模板融合方案](./TEMPLATE_FUSION_PLAN.md)
- [结构质量测试集](./STRUCTURE_QUALITY_TESTSET.md)
- [深度调优说明](./DEEP_TUNING.md)

## 当前约定

- 新功能优先进入 V2 语义流程，而不是 legacy 模板链路。
- 推荐命令入口是 `demo`、`make`、`review`、`iterate`。
- 已下线的 legacy CLI 命令不再作为对外主路径保留在文档主入口中。
- legacy HTML / template 文档只作为兼容说明保留，不再与主路径并列展示。
