# Compatibility & Upgrade Policy

这份文档用于管理 `SIE-autoppt` 与外部依赖、模板资产之间的兼容关系，避免“某次升级后本地流程失效”。

## 当前边界

- 外部依赖层
  - `ppt-master`
  - 本机 PowerPoint COM 环境

- 本地固化层
  - `assets/templates/sie_template.pptx`
  - `skills/sie-autoppt/*`
  - `tools/sie_autoppt/*`
  - `docs/*`

## 当前约束

- 标准模板入口固定为 `assets/templates/sie_template.pptx`
- 更换模板后必须同步更新 `assets/templates/sie_template.version.txt`
- 生成目录页图片修复时依赖 PowerPoint COM，若环境缺失则会跳过 COM 修复流程

## 升级建议

### 升级模板

1. 替换 `assets/templates/sie_template.pptx`
2. 执行 `tools/update_template_version.ps1`
3. 执行 `tools/regression_check.ps1`
4. 检查生成结果和 QA 报告

### 升级外部依赖

1. 先确认 `python-pptx` 可正常导入
2. 再确认 PowerPoint 可以正常打开本地模板
3. 最后跑一遍回归检查

## 通过标准

- 模板文件存在且指纹一致
- CLI 可以正常执行
- 能生成 `.pptx` 和 `_QA.txt`
- QA 中目录页和结束页检查通过

## 常见风险

- 模板结构变化后，模板页索引不再匹配
- HTML 输入结构变化后，正文页内容为空
- 没有 PowerPoint COM 时，目录页复制效果可能与目标模板略有差异
