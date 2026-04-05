# Testing

`SIE-autoppt` 当前建议分成 4 层测试：

1. `unittest` 单元测试
2. 轻量集成测试
3. `tools/regression_check.ps1` 全量回归
4. 少量人工视觉验收

## 自动化部分

这些可以直接由代码和本机环境完成，不需要人工逐页确认：

- HTML 解析与输入校验
- Deck planning 与章节钳制
- 模板 manifest 加载
- 最小生成链路
- `QA.txt` / `QA.json` 结构与关键字段

运行方式：

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\run_unit_tests.ps1
```

或：

```powershell
python -m unittest discover -s .\tests -v
```

全量回归：

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\regression_check.ps1
```

## 需要人工配合的部分

这些测试不适合完全自动化，或者至少在当前阶段不值得优先自动化：

- 模板换版后的视觉验收
- 新业务样例是否“讲得对、排得顺”
- 不同模板是否已经迁移到 preallocated slide pool
- 最终交付前的黄金样例抽检

建议最少保留 3 个黄金样例做人眼验收：

- 通用业务页
- ERP / 架构页
- 参考样式导入页

## 运行时注意事项

- `legacy clone` 路径已经标记为 deprecated，仅用于没有 slide pool 的旧模板兜底
- 如果 legacy clone 目录页资源修复连续失败，生成流程现在会明确报错，而不是静默继续
- 新模板应优先维护 `manifest.slide_pools`

可直接生成视觉验收批次：

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\prepare_visual_review.ps1
```

人工验收说明见 [`docs/HUMAN_VISUAL_QA.md`](./HUMAN_VISUAL_QA.md)。

## 当前测试入口

- 单元与轻集成测试：`tests/`
- 自动化运行入口：[tools/run_unit_tests.ps1](/C:/Users/CHENHU/Documents/cursor/project/AI-atuo-ppt/tools/run_unit_tests.ps1)
- 全量回归入口：[tools/regression_check.ps1](/C:/Users/CHENHU/Documents/cursor/project/AI-atuo-ppt/tools/regression_check.ps1)
