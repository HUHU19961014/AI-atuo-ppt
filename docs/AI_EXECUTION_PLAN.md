# AI 驱动改造执行计划

## 模板吸收现状

外部模板没有被“整包照搬”，而是被拆成了 3 层资产：

1. `v2 theme`
   - 已吸收 4 套全局风格：`google_brand_light`、`anthropic_orange`、`mckinsey_blue`、`consulting_navy`
   - 对应能力：颜色、字体气质、留白、卡片感

2. `native page pattern`
   - 已吸收 4 个高价值正文页型：`roadmap_timeline`、`kpi_dashboard`、`risk_matrix`、`claim_breakdown`
   - 对应能力：路线图、指标仪表盘、风险矩阵、金额/构成拆解

3. `template ingestion tooling`
   - 已吸收外部模板导入与目录扫描能力：
   - [import_external_pptx_template.py](../tools/template_utils/import_external_pptx_template.py)
   - [catalog_external_templates.py](../tools/template_utils/catalog_external_templates.py)
   - 对应能力：批量扫描 `D:\template`，识别资产、页型候选、融合优先级

## 吸收原则

- 抄“表达结构”，不抄整套工程
- 抄“单页构图与信息组织”，不抄死模板
- 模板负责品牌风格，AI 负责内容导演与页面编排

## 当前主问题

当前 `v2` 已经有 `outline -> semantic -> compiled -> pptx` 主链，但 semantic 编译层还偏规则驱动，动态编排能力还不够强。

## 执行队列

### P0 已开始

1. `semantic compiler` 显式化
   - 目标：把 `semantic -> compiled` 从隐式步骤变成正式命令和正式产物
   - 状态：已完成

2. `layout planner` 独立化
   - 目标：把 `deck_director` 从硬编码分支升级成显式布局决策器
   - 状态：进行中，已新增 `plan_semantic_slide_layout()`，并支持 `timeline/cards/stats` 的布局判定

### P1 紧接着做

3. `semantic block grammar` 扩展
   - 目标：补 `matrix`、`timeline`、`cards`、`stats` 这类中间表达，不让 AI 只能吐 bullets/comparison/image/statement
   - 当前进展：`timeline/cards/stats/matrix` 已接入 schema、prompt、compiler

4. `dynamic layout scoring`
   - 目标：让单页不是固定映射，而是根据内容密度、对比关系、视觉需求动态选布局

5. `review loop` 接 semantic
   - 目标：把 visual review 的修正建议反馈到 semantic 层，而不是只补 compiled deck

### P2 然后推进

6. `legacy workflow` 降级
   - 状态：legacy 模板式 CLI 入口已移除；默认主路径为 `make / review / iterate`，`v2-*` 作为显式高级命令保留

7. 第二批模板沉淀
   - 目标：继续从 `重庆市区域报告`、`南欧江水电站战略评估`、`甘孜州经济财政分析` 提炼页型
   - 候选：`policy_matrix`、`regional_scorecard`、`trend_comparison`、`geo_risk_map`

## 完成标准

- 用户直接输入主题时，系统优先生成语义 deck，而不是套固定模板
- semantic deck 可以单独审阅、编译、渲染、review、迭代
- 新模板进入项目时，先沉淀为 theme / pattern / semantic grammar，而不是复制 scenario generator
