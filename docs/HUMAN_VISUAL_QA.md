# Human Visual QA

这部分测试需要人工参与，当前阶段不建议完全自动化。

## 我已经能自动完成的

- `unittest` 纯逻辑测试
- 最小生成链路测试
- `warnings.json` / `rewrite_log.json` 结构检查
- 全量回归脚本检查

## 需要你配合的

### 1. 黄金样例视觉验收

默认视觉验收会准备这 5 组：

- `management_report`
- `project_solution`
- `training_deck`
- `industry_analysis`
- `monthly_business_review`

运行：

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\prepare_visual_review.ps1
```

脚本会读取 `samples/visual_review_cases.json`，并在 `projects/visual_review/visual_review_<timestamp>/` 下生成：

- 待检查的 `.pptx`
- 对应 `warnings.json`
- 对应 `rewrite_log.json`
- 对应 `render.log.txt`
- 可用时导出的预览图目录
- `VISUAL_REVIEW_CHECKLIST.md`

说明：

- 当前批处理基于仓库内置的 V2 `deck.json` 回归样例，不再依赖旧的 HTML 输入。
- 如果当前机器拿不到预览图，检查单里会明确标注 `content-only manual review`，表示这轮只能做内容保守验收，不能替代最终视觉签收。

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
management_report: PASS
project_solution: WARN，路线图页底部文字偏挤
industry_analysis: PASS
monthly_business_review: FAIL，第二页有溢出
```

我再根据你的结论去补自动规则、修版式或调整模板语义。

## Visual Draft QA (v0.3.0)

For `visual-draft` outputs, review these artifacts together:

- `*.visual_spec.json`
- `*.preview.html`
- `*.preview.png`
- `*.visual_score.json`
- `*.ai_visual_review.json` (optional when AI review is enabled)

Manual checks:

- Main claim is visible at first glance.
- No text clipping or unsafe overlap with header/footer zones.
- Density is readable on a single 16:9 page.
- Rule score level matches what you visually observe.
