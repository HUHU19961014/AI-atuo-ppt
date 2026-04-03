# SIE AutoPPT

`SIE-autoppt` 是一个基于企业模板的 PPT 自动生成项目。当前主流程是：

1. 从 HTML 输入中提取标题、阶段、场景和关注点。
2. 将内容映射到模板中的主题页、目录页和正文页。
3. 根据语义关键词选择合适的正文版式。
4. 输出原生 `.pptx` 和一份 QA 报告。

## 目录结构

```text
SIE-autoppt/
├─ assets/templates/          # 标准模板入口与模板指纹
├─ input/                     # HTML 输入样例
├─ projects/generated/        # 默认输出目录
├─ skills/sie-autoppt/        # 规则、参考资料、检查清单
├─ tools/sie_autoppt/         # 模块化生成逻辑
├─ run_sie_autoppt.ps1        # 一键生成入口
└─ tools/regression_check.ps1 # 回归检查入口
```

## 标准模板入口

项目统一使用下面这个模板路径：

`assets/templates/sie_template.pptx`

根目录不再保留重复模板。后续如果替换模板，只更新这一份，并执行：

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\update_template_version.ps1
```

## 快速开始

```powershell
python .\tools\sie_autoppt_cli.py `
  --template .\assets\templates\sie_template.pptx `
  --html .\input\uat_plan_sample.html `
  --output-name SIE_AutoPPT `
  --output-dir .\projects\generated `
  --chapters 3 `
  --active-start 0
```

或者直接执行：

```powershell
powershell -ExecutionPolicy Bypass -File .\run_sie_autoppt.ps1
```

## 输入规范

输入 HTML 的详细字段说明见：

[`docs/INPUT_SPEC.md`](./docs/INPUT_SPEC.md)

当前生成器默认识别这些 class：

- `title`
- `subtitle`
- `scope-title`
- `scope-subtitle`
- `focus-title`
- `focus-subtitle`
- `phase-time`
- `phase-name`
- `phase-code`
- `phase-func`
- `phase-owner`
- `scenario`
- `note`
- `footer`

其中 `scope-*` 和 `focus-*` 可选，用于覆盖第 2 / 3 个正文页的标题与副标题。
扩展字段说明见 [`docs/INPUT_SPEC_SUPPLEMENT.md`](./docs/INPUT_SPEC_SUPPLEMENT.md)。

如果 HTML 中完全缺少这些内容，程序会直接报错，而不是生成一份空 PPT。

## 当前实现思路

1. 模板页索引由 `tools/sie_autoppt/config.py` 统一管理。
2. HTML 内容先在 `tools/sie_autoppt/generator.py` 中解析为输入载荷，再组装为页面规格。
3. 页面规格与 PPT 渲染已解耦，后续扩页型时优先改页面构造层，不要直接堆到渲染函数里。
4. 模式识别配置位于 `skills/sie-autoppt/references/business-slide-patterns.json`。
5. QA 检查会输出结束页、目录页和潜在文本溢出风险。

## 回归检查

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\regression_check.ps1
```

默认会批量执行 `input/*.html` 下的所有样例。
其中 `*.fail.html` 会被当作预期失败样例，用来验证输入校验。

## 版本管理建议

当前项目已经启用 Git。建议后续按下面方式迭代：

1. 改模板单独提交。
2. 改输入规则或关键词规则单独提交。
3. 改生成逻辑单独提交。
4. 每次正式交付前跑一遍回归检查。
