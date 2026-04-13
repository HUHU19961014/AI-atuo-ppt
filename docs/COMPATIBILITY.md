# Compatibility & Upgrade Policy

这份文档用于管理 `Enterprise-AI-PPT` 当前主链路与模板资产、可选本机能力之间的兼容关系，避免升级后本地流程失效。

## 当前边界

- 主链路：
  - `tools/sie_autoppt/*`
  - `assets/templates/sie_template.pptx`
  - `main.py`
  - 推荐命令：`make`、`review`、`iterate`、`demo`、`ai-check`
- 仓库内固定资产：
  - `skills/sie-autoppt/*`
  - `docs/*`
  - `assets/templates/*`
- 可选本机能力：
  - PowerPoint COM 环境
- 历史兼容资产：
  - `run_sie_autoppt.ps1`（已 retired，只保留明确的迁移提示）
  - `tools/legacy_html_regression_check.ps1`
  - `tools/regression_check.ps1`
  - 旧的外部 `ppt-master` 工作区说明

## 兼容原则

- 当前默认流程不再把外部 `ppt-master` 作为硬依赖。
- 当前默认交付路径是 V2 语义工作流；legacy HTML/template 只保留兼容性用途。
- 缺少 PowerPoint COM 时，允许跳过部分本机修复步骤，但主生成链路应仍可运行。
- 模板入口固定为 `assets/templates/sie_template.pptx`，变更模板时必须同步校验 manifest 与版本指纹。
- skill 文档中的默认策略应与实际实现保持一致，尤其是页数范围、输出目录和配色约束。

## 当前约束

- 标准模板入口固定为 `assets/templates/sie_template.pptx`
- 模板版本指纹文件为 `assets/templates/sie_template.version.txt`
- 默认输出目录为仓库内 `output/`
- 默认页数策略为内容驱动，而不是固定 `8-12` 页
- 默认品牌强调色为 SIE 红 `RGB(173, 5, 61)`，非激活目录色为 `RGB(184, 196, 201)`

## 升级建议

### 升级模板

1. 替换 `assets/templates/sie_template.pptx`
2. 执行 `tools/template_utils/update_template_version.ps1`
3. 执行 `tools/run_unit_tests.ps1`
4. 执行 `tools/v2_regression_check.ps1`
5. 如本次变更影响 legacy HTML/template 兼容路径，再执行 `tools/legacy_html_regression_check.ps1`
6. 如本次变更涉及视觉结构或模板细节，再执行 `tools/prepare_visual_review.ps1`
7. 检查生成结果、`warnings.json` 和必要的 QA 报告

### 升级本机依赖

1. 先确认 `python-pptx` 可以正常导入
2. 再确认 PowerPoint 能正常打开本地模板
3. 最后至少跑一轮 `tools/run_unit_tests.ps1` 和 `tools/v2_regression_check.ps1`

## 通过标准

- 模板文件存在且指纹一致
- CLI 可以正常执行
- 能生成 `.pptx`、rewrite log、`warnings.json`
- 如启用 QA 报告，能生成对应 `_QA.txt` / `_QA.json`
- 目录页激活样式与结尾页结构通过检查

## 常见风险

- 模板结构变化后，manifest 中的页索引不再匹配
- HTML 输入结构变化后，正文抽取质量下降
- skill 文案滞后于实现，导致 agent 误以为需要外部 `ppt-master`
- 缺少 PowerPoint COM 时，局部修复效果可能与目标模板略有差异
- 文档把兼容脚本写成默认入口，导致团队误把 legacy 回归当成主发布阻断
