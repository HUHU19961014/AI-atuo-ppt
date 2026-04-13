# 模板融合方案

当前本地外部模板来源为 `D:\template`。这批素材整体质量不错，但它们和当前仓库的模板体系不是同一种“模板单位”，不能直接整包拷进 `assets/templates/` 就完成接入。

## 现状判断

当前项目主要有两套复用机制：

1. `tools/sie_autoppt/v2/themes/*.json`
   - 负责 V2 流程的整体视觉主题
   - 适合沉淀颜色、字体、间距、卡片气质这类“全局风格”
2. `reference_style`
   - 负责正文页型复用
   - 适合沉淀某一页的成熟构图，比如矩阵、路线图、能力环、KPI 仪表板

`D:\template` 下的大部分目录包含：

- `design_spec.md`
- 成品 `pptx`
- 多页 `svg_final` / `svg_output`
- 部分项目额外带 `README.md`、图片素材、逐页备注

这说明它们更像“高保真案例库”，不是当前仓库可直接加载的 manifest 模板。

## 已完成的第一步融合

本次先把外部模板里最稳定、最容易抽象的“全局视觉风格”接入到 V2 主题体系（作为样式资产保留）：

- `google_brand_light`
  - 来源：`ppt169_谷歌风_google_annual_report`
- `anthropic_orange`
  - 来源：`ppt169_顶级咨询风_构建有效AI代理_Anthropic`
- `mckinsey_blue`
  - 来源：`ppt169_麦肯锡风_kimsoong_customer_loyalty`
- `consulting_navy`
  - 来源：`ppt169_高端咨询风_汽车认证五年战略规划`

说明：

- 当前生产链路已固定主题为 `sie_consulting_fixed`，上述主题暂不作为生产命令默认入口。
- 这些主题保留为后续实验与样式资产，不参与当前主发布门禁。

当前生产命令应使用：

```powershell
enterprise-ai-ppt v2-make --topic "企业 AI 战略汇报" --theme sie_consulting_fixed
```

同时，V2 主题校验已改成从 `tools/sie_autoppt/v2/themes/` 动态发现，后续继续加主题时不需要再修改 schema 白名单。

## 推荐的后续融合路径

### 一类：适合继续沉淀为 V2 主题

- `ppt169_谷歌风_google_annual_report`
  - 强项是品牌色、留白、数据卡片气质
  - 更适合作为轻品牌化主题
- `ppt169_顶级咨询风_构建有效AI代理_Anthropic`
  - 强项是科技主题的咨询表达
  - 适合作为技术分享型主题
- `ppt169_麦肯锡风_kimsoong_customer_loyalty`
  - 强项是经典咨询图表配色和案例叙事
  - 适合作为通用战略分析主题

### 二类：更适合沉淀为 reference style 页型

- `ppt169_高端咨询风_汽车认证五年战略规划`
  - 候选页型：`roadmap_timeline`、`kpi_dashboard`、`policy_matrix`
- `ppt169_高端咨询风_南欧江水电站战略评估`
  - 候选页型：`executive_summary_kpi`、`claim_breakdown`、`geo_risk_map`
- `ppt169_顶级咨询风_重庆市区域报告_ppt169_20251213`
  - 候选页型：`regional_scorecard`、`industry_snapshot`
- `ppt169_顶级咨询风_甘孜州经济财政分析`
  - 候选页型：`fiscal_dashboard`、`trend_comparison`

这类模板的价值主要在“页构图”，不是单一主题色。后续应优先把单页拆成可复用页型，而不是整套复刻。

### 三类：保留为案例库，不建议先做通用化

- `ppt169_顶级咨询风_心理治疗中的依恋`
  - 图片和专题内容绑定过深
  - 更适合做灵感库或定制项目素材

## 下一步建议

建议按下面顺序继续：

1. 从 `汽车认证五年战略规划` 提炼 `roadmap_timeline`
2. 从 `Kimsoong` 或 `重庆区域报告` 提炼 `kpi_dashboard`
3. 从 `南欧江水电站战略评估` 提炼 `risk_matrix` / `claim_breakdown`
4. 再考虑把多份外部 `pptx` 扩展进 `reference_style` 的导入链路

这样做的原因很直接：

- 先沉淀主题，可以马上改善 V2 的整体观感
- 再沉淀页型，可以逐步提升正文质量
- 最后再扩展多源 `pptx` 导入，工程改动最值当

## 当前进度

第二步已开始落地：

- 已新增原生页型 `roadmap_timeline`
- 已新增原生页型 `kpi_dashboard`
- 已新增原生页型 `risk_matrix`
- 已新增原生页型 `claim_breakdown`
- 已接入 legacy planner、AI planner、structure -> deck 路径

这些页型当前已经不依赖 `D:\template` 运行时存在，可以直接通过 `pattern_id` 使用。
