---
name: sie-autoppt
description: >
  SIE 专属 AutoPPT 流程入口。优先复用当前仓库内置的 `tools/sie_autoppt`
  引擎，完成从源内容到可编辑 PPTX 的生产，并固化 SIE 风格规范。
  历史上的外部 `ppt-master` 仅作为兼容参考，不再视为默认硬依赖。
---

# SIE AutoPPT Skill

## 目标

- 使用当前仓库内置的 `tools/sie_autoppt` 流程稳定产出可编辑 PPTX
- 在规划和渲染阶段持续应用 SIE 风格与页面质量约束
- 支持 HTML 参考重建、结构化规划、DeckSpec JSON 渲染
- 保留对历史流程的兼容认知，但避免把外部脚本引擎当作前置条件

## 当前引擎边界

- 默认执行引擎：
  - `python main.py`
  - `python -m sie_autoppt`
  - `run_sie_autoppt.ps1`
- 当前仓库内置能力：
  - `tools/sie_autoppt/*`
  - `assets/templates/sie_template.pptx`
  - `skills/sie-autoppt/references/*`
- 可选兼容项：
  - PowerPoint COM：用于少量本机修复/预览场景，缺失时允许降级
- 非默认硬依赖：
  - 外部 `ppt-master` 工作区

## 规则入口

- 硬规则：`rules/python_pptx_hard_rules.md`
- HTML 重建规则：`rules/html_to_ppt_rebuild.md`
- 页面质检：`checklists/page_qa_checklist.md`
- 模板生成规范：`references/template-driven-generation.md`
- 商务页型模式库：`references/business-slide-patterns.json`

执行要求：

1. 任何页面生成前先加载硬规则。
2. 输入为 HTML 或用户要求“参考网页重建”时，额外加载 HTML 重建规则。
3. 每轮生成后都要执行页面级 QA，并记录是否需要修复。
4. 如果用户指定企业模板或参考模板，优先按模板角色和版式约束执行。

## 输出路径与命名

1. 默认输出目录为仓库内 `output/`，除非用户显式指定 `--output-dir`。
2. 默认文件名前缀可使用 CLI 参数 `--output-name` 覆盖。
3. 输出文件应带时间戳，避免覆盖历史版本。

## 标准执行流

1. 源内容解析：topic / brief / HTML / structure / deck json
2. 结构澄清：补齐受众、目标、页数范围、风格等缺口
3. 结构规划：生成 outline / structure / DeckSpec
4. 模板与风格约束注入
5. 确定性渲染为 PPTX
6. QA / visual review / 人工微调

## HTML 重建模式

触发条件：

- 用户提供 HTML 文件或网页 URL
- 用户明确要求“复刻”“参考这个网页做 PPT”

执行原则：

1. 先抽取可分析内容与页面结构，不要求依赖外部 `web_to_md.py`。
2. 先做“页面目标 + 元素映射 + 信息优先级”判断，再进入排版。
3. 输出页级说明，标明哪些内容忠实保留、哪些内容为 PPT 化优化。
4. 生成后执行至少一轮 QA；必要时补做修复。

## 模板驱动模式

触发条件：

- 用户提供 `.pptx` 模板
- 用户要求“首尾固定，中间按内容生成”

执行原则：

1. 固定页保留结构角色，不强行改写模板意图。
2. 主题页、目录页、正文页、结尾页按模板角色处理。
3. 目录激活色使用 `RGB(173, 5, 61)`，非激活项使用 `RGB(184, 196, 201)`。
4. 正文页优先从模板或预分配页池生成，避免破坏模板结构。
5. 保证收尾页逻辑完整。

## SIE 策略约束（默认）

1. 画幅：`ppt169`
2. 页数：默认按内容密度动态推断；短内容通常 `3-5` 页，中等内容 `6-10` 页，长内容 `10-20` 页；若用户明确指定，则以用户范围为准
3. 受众：管理层 + 业务负责人
4. 风格：高端咨询风 + 商务克制
5. 配色：以蓝灰中性色为底，品牌强调色使用 SIE 红 `RGB(173, 5, 61)`；弱化信息使用灰色 `RGB(184, 196, 201)`
6. 图标：优先线性图标，整套风格统一
7. 字体：标题与正文分层，正文可读性优先
8. 图片：优先业务实景、数据示意、结构图，避免装饰性空图

## 强制质量门槛

- 每页至少一个视觉锚点：图表、图标、卡片、流程或结构图
- 避免纯文字堆叠页
- 封面、目录、正文、结尾风格要前后一致
- 输出前必须完成基础 QA；如启用 V2，可进一步执行 visual review

## 使用建议

- 优先走当前仓库主流程，不默认依赖外部 `ppt-master`
- 需要兼容旧流程时，优先使用 `tools/legacy_html_regression_check.ps1` 进行验证，不回退为默认主链路
- 当用户需求模糊时，先澄清“主题 / 受众 / 页数范围 / 语气 / 输出形式”
