# Human Visual QA

这部分测试需要人工参与，当前阶段不建议完全自动化。

## 我已经能自动完成的

- `unittest` 纯逻辑测试
- 最小生成链路测试
- `QA.txt` / `QA.json` 结构检查
- 全量回归脚本检查

## 需要你配合的

### 1. 黄金样例视觉验收

建议固定看这 4 组：

- `uat_plan_sample.html`
- `default_erp_blueprint.html`
- `ai_pythonpptx_strategy.html`
- `vendor_launch_sample.html`

运行：

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\prepare_visual_review.ps1
```

脚本会在 `projects/visual_review/visual_review_<timestamp>/` 下生成：

- 待检查的 `.pptx`
- 对应 `QA.txt`
- 对应 `QA.json`
- `VISUAL_REVIEW_CHECKLIST.md`

### 2. 你需要重点确认的内容

- 哪些视觉问题算 blocker
- 哪些只是可接受的小偏差
- 模板升级后哪些页面必须人工抽检

建议你看 PPT 时按下面标准给结论：

- `PASS`
  页面可直接交付，没有明显视觉问题
- `WARN`
  有轻微瑕疵，但不影响交付
- `FAIL`
  有明显错位、溢出、资产丢失或内容错误

### 3. 最值得你先看的页面

- 目录页
- 第一张正文页
- 参考样式导入页
- 长文本页
- 结束页

## 推荐协作方式

你只需要把每个黄金样例回我一句即可：

```text
uat_plan_sample: PASS
default_erp_blueprint: WARN，治理页底部文字偏挤
ai_pythonpptx_strategy: PASS
vendor_launch_sample: FAIL，第二页有溢出
```

我再根据你的结论去补自动规则、修版式或调整模板语义。
