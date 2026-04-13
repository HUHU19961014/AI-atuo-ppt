# Testing

## Local Quality Gate (CI-aligned)

Run the local CI-aligned gate:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\quality_gate.ps1
```

Execution order:

1. Targeted `ruff --select F` checks (same scope as CI quality-gates).
2. Targeted `mypy` checks (release target files only).
3. Legacy boundary guard (`tools/check_legacy_boundary.py`).
4. Release subset test suite.
5. Coverage gate for CLI entry surfaces (`--fail-under=80`).

## Performance And Concurrency Checks

- Long-run stress batching (120-slide synthetic input):

```powershell
python .\tools\stress_test_v2.py
```

- Timeout graceful degradation check:

```powershell
python .\main.py v2-make --topic "timeout fallback check" --graceful-timeout-fallback
```

- Concurrent output collision isolation:

```powershell
python .\main.py v2-make --topic "run A" --isolate-output --run-id run-a
python .\main.py v2-make --topic "run B" --isolate-output --run-id run-b
```

`SIE-autoppt` 当前建议分成 4 类主测试与 1 类条件性兼容测试：

1. 单元测试
2. 轻量集成测试
3. `python .\main.py demo` 无 AI 冒烟回归
4. `tools/v2_regression_check.ps1` V2 deck 回归
5. 兼容测试：`tools/legacy_html_regression_check.ps1` legacy HTML 样例回归

## 基线原则

- 只要测试会落到实际渲染、视觉检查、发布验收，就优先使用仓库内的 SIE 模板基线：`assets/templates/sie_template.pptx`。
- 生产链路主题固定为 `sie_consulting_fixed`；测试样例如果使用其他主题，仅可用于兼容/实验，不作为主回归签收依据。
- 其他 theme、外部模板、参考样式更适合作为补充覆盖，不应替代 SIE 模板的主回归。
- 如果某条测试没有直接显式传模板，也应确认它最终走的是当前默认的 SIE 模板链路。

## 当前硬门禁（测试必须覆盖）

- 主题必须为 `sie_consulting_fixed`
- 目录式标题（例如“建设背景”“现状介绍”）按错误级别处理
- `title_content` 要点数量必须在 `1-6` 之间

## 推荐安装

优先使用可安装包方式：

```bash
python -m venv .venv
. .venv/Scripts/activate
python -m pip install --upgrade pip
python -m pip install -e .[dev]
```

如果只走兼容路径：

```bash
python -m pip install -r requirements.txt
python -m pip install pytest
```

## 自动化部分

这些可以直接由代码和本机环境完成，不需要人工逐页确认：

- HTML 解析与输入校验
- Deck planning 与章节钳制
- 模板 manifest 加载
- 最小生成链路
- 条件性 `QA.txt` / `QA.json` 结构与关键字段
- `demo` 无 API 冒烟路径

优先运行方式：

```bash
python -m pytest tests -q
```

兼容运行方式：

```bash
python -m unittest discover -s tests -v
```

PowerShell 快捷入口：

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\run_unit_tests.ps1
```

推荐先跑的主路径检查：

```powershell
python -m pytest tests -q
python .\main.py demo
powershell -ExecutionPolicy Bypass -File .\tools\v2_regression_check.ps1
```

这些主路径检查应默认视为 SIE 模板基线回归。

可选真实 AI 小样本回归：

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\run_real_ai_smoke.ps1
```

说明：

- 这个 smoke test 默认不参与常规回归，只有显式设置 `OPENAI_API_KEY` 并运行脚本时才执行。
- 默认使用 `quick` 模式控制成本和时延；如需更接近正式主链路，可传 `-GenerationMode deep`。
- 如需把 smoke test 跑到实际 PPT 渲染阶段，可传 `-WithRender`，但这会增加耗时和本机依赖。

兼容层回归，仅在修改 legacy HTML/template 路径时需要：

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\legacy_html_regression_check.ps1
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
- 如果 legacy clone 目录页资源修复连续失败，生成流程会明确报错，而不是静默继续
- 新模板应优先维护 `manifest.slide_pools`

可直接生成视觉验收批次：

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\prepare_visual_review.ps1
```

说明：

- `prepare_visual_review.ps1` 属于内部辅助脚本，不是普通用户主路径。
- 它会使用仓库内置的 V2 `deck.json` 回归样例，而不是旧的 HTML 样例。
- 这批视觉验收默认也应以当前 SIE 模板输出作为签收基线。
- 视觉复核若拿不到 PNG 预览，会退化成基于 Deck 内容的保守评审。

人工验收说明见 [docs/HUMAN_VISUAL_QA.md](./HUMAN_VISUAL_QA.md)。

## 当前测试入口

- 单元与轻集成测试：`tests/`
- 自动化运行入口：[tools/run_unit_tests.ps1](../tools/run_unit_tests.ps1)
- V2 回归入口：[tools/v2_regression_check.ps1](../tools/v2_regression_check.ps1)
- 真实 AI smoke 入口（按需执行）：[tools/run_real_ai_smoke.ps1](../tools/run_real_ai_smoke.ps1)
- Legacy HTML 回归入口（兼容层，仅按需执行）：[tools/legacy_html_regression_check.ps1](../tools/legacy_html_regression_check.ps1)
