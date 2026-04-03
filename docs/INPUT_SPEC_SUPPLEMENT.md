# 输入字段补充说明

本文补充 `docs/INPUT_SPEC.md` 中尚未展开说明的 ERP/方案型正文字段。

## 标题覆盖字段

- `scope-title`
  - 用途：覆盖正文第 2 页标题。
  - 是否必填：否。
  - 默认值：`测试范围与关键场景`

- `scope-subtitle`
  - 用途：覆盖正文第 2 页副标题。
  - 是否必填：否。
  - 默认值：根据输入场景自动归纳测试覆盖范围。

- `focus-title`
  - 用途：覆盖正文第 3 页标题。
  - 是否必填：否。
  - 默认值：`测试关注点与验收标准`

- `focus-subtitle`
  - 用途：覆盖正文第 3 页副标题。
  - 是否必填：否。
  - 默认值：优先使用该字段，否则回退到 `footer` 或默认说明。

## 示例

```html
<div class="title">制造业 ERP 一体化蓝图</div>
<div class="subtitle">以 ERP 为核心连接供应链、生产制造、仓储执行与经营分析。</div>
<div class="scope-title">关键业务链路与系统协同</div>
<div class="scope-subtitle">围绕销售、采购、计划、生产、仓储和财务梳理端到端业务闭环。</div>
<div class="focus-title">实施重点与治理要求</div>
<div class="focus-subtitle">从主数据、接口治理、上线切换与组织协同四个方面控制实施风险。</div>
```
