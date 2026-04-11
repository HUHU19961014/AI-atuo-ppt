# Contributing

## Working Rules

- 当前对外主路径是 V2：`demo`、`make`、`review`、`iterate`、`v2-*`。
- legacy HTML / template 相关能力仅作为兼容层维护，不要把它们重新放回主入口文档。
- 涉及渲染、视觉复核、回归验收时，优先以仓库内 `assets/templates/sie_template.pptx` 作为主测试基线；其他 theme 或外部模板只做补充验证。
- 改 CLI 或默认工作流时，必须同步更新：
  - `README.md`
  - `docs/CLI_REFERENCE.md`
  - 相关测试
- 新增用户可见命令、参数或输出物时，必须补自动化测试。
- 新功能默认进入 `tools/sie_autoppt/v2/`，除非明确是在修兼容层。

## Release Baseline

提交前至少执行：

```powershell
python -m pytest tests -q
python .\main.py demo
```

说明：

- 上述主路径检查默认应落在 SIE 模板基线上，不要拿其他 theme 的偶然通过替代 SIE 模板回归。

涉及 V2 生成/渲染改动时，额外执行：

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\v2_regression_check.ps1
```

涉及 legacy 兼容改动时，再执行：

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\legacy_html_regression_check.ps1
```
