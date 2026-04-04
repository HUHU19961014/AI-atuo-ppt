# SIE AutoPPT Release Checklist

用于正式交付前 5 到 10 分钟的快速检查。

## 环境检查

- [ ] `python --version` 可正常执行
- [ ] `python -c "import pptx"` 可正常执行
- [ ] 本机 PowerPoint 可打开模板

## 资产检查

- [ ] 标准模板存在：`assets/templates/sie_template.pptx`
- [ ] 模板指纹文件存在：`assets/templates/sie_template.version.txt`
- [ ] 若模板刚替换，已执行 `tools/update_template_version.ps1`

## 回归检查

- [ ] 已执行 `tools/run_unit_tests.ps1`
- [ ] 已执行 `tools/regression_check.ps1`
- [ ] 控制台出现 `Regression check passed`

## 生成检查

- [ ] 已执行 `run_sie_autoppt.ps1`
- [ ] 成功生成 `.pptx`
- [ ] 成功生成 `_QA.txt`
- [ ] 成功生成 `_QA.json`

## 视觉验收

- [ ] 主题页、目录页、结束页顺序正确
- [ ] 目录页高亮章节正确
- [ ] 正文页无明显文本溢出、遮挡、错位
- [ ] 模板关键视觉元素没有丢失

## 归档

- [ ] 记录本次模板指纹
- [ ] 记录输出文件名
- [ ] 如发现问题，补充更新文档和规则
