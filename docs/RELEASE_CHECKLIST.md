# SIE AutoPPT Release Checklist

用于正式交付前 5 到 10 分钟的快速检查。

## 环境检查

- [ ] `python --version` 可正常执行
- [ ] `python -c "import pptx"` 可正常执行
- [ ] 本机 PowerPoint 可打开模板

## 资产检查

- [ ] 标准模板存在：`assets/templates/sie_template.pptx`
- [ ] 模板指纹文件存在：`assets/templates/sie_template.version.txt`
- [ ] 若模板刚替换，已执行 `tools/template_utils/update_template_version.ps1`
- [ ] 本次主发布验证基于 SIE 模板，而不是其他 theme 的替代结果

## 回归检查

- [ ] 已执行 `tools/run_unit_tests.ps1`
- [ ] 已执行 `tools/v2_regression_check.ps1`
- [ ] 如本次变更涉及真实 AI 生成链路，已执行 `python .\main.py ai-check --with-render`
- [ ] 如本次变更涉及 legacy HTML/template 兼容路径，已执行 `tools/legacy_html_regression_check.ps1`
- [ ] 控制台未出现阻断性失败

## 生成检查

- [ ] 已执行本次实际交付命令（通常是 `python .\main.py make ...` 或对应 `review` / `iterate`）
- [ ] 如仅做本机冒烟，已执行 `python .\main.py demo`
- [ ] 成功生成 `.pptx`
- [ ] 成功生成 rewrite log 与 `warnings.json`
- [ ] 如启用 QA 报告，成功生成 `_QA.txt`
- [ ] 如启用 QA 报告，成功生成 `_QA.json`

## 视觉验收

- [ ] 主题页、目录页、结束页顺序正确
- [ ] 目录页高亮章节正确
- [ ] 正文页无明显文本溢出、遮挡、错位
- [ ] 模板关键视觉元素没有丢失
- [ ] 如本次涉及视觉风险较高的模板或布局改动，已执行 `tools/prepare_visual_review.ps1`

## 归档

- [ ] 记录本次模板指纹
- [ ] 记录输出文件名
- [ ] 如发现问题，补充更新文档和规则
