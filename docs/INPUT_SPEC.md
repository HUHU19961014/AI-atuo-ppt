# HTML 输入规范

这个项目当前不是“任意 HTML 都能转 PPT”，而是识别一组约定好的 class。只要你按下面结构组织内容，生成器就能稳定工作。

## 最小可用输入

至少需要满足下面任一条件：

- 提供一组 `phase-*`
- 或提供至少一个 `scenario`
- 或提供至少一个 `note`

如果三类正文内容都没有，程序会直接报错。

## 字段说明

### 1. 基础字段

- `title`
  - 用途：主题页标题、正文第一页标题。
  - 是否必填：否。
  - 默认值：`项目概览与UAT阶段计划`

- `subtitle`
  - 用途：正文第一页副标题。
  - 是否必填：否。
  - 默认值：自动补一条说明文字。

- `footer`
  - 用途：第三页副标题或补充说明。
  - 是否必填：否。

### 2. 阶段字段

这五个字段建议成组出现，按顺序一一对应：

- `phase-time`
- `phase-name`
- `phase-code`
- `phase-func`
- `phase-owner`

用途：

- 自动生成“项目概览与UAT阶段计划”页的四个卡片。

规则：

- 最多取前 4 组。
- 如果字段数量不一致，生成器会按已有内容尽量拼装，不会因为单个字段缺失而直接报错。

### 3. 场景字段

- `scenario`
  - 用途：生成“测试范围与关键场景”页。
  - 最多取前 4 条。

### 4. 关注点字段

- `note`
  - 用途：生成“测试关注点与验收标准”页。
  - 最多取前 4 条。

## 推荐 HTML 结构

```html
<div class="title">项目概览与UAT阶段计划</div>
<div class="subtitle">按阶段推进测试执行，验证核心链路并明确责任边界。</div>

<div class="phase-time">4/7-4/8</div>
<div class="phase-name">基础配置</div>
<div class="phase-code">BC-1 ~ BC-5</div>
<div class="phase-func">核心功能：类别管理 / 实体管理 / 文件类型 / 链路配置</div>
<div class="phase-owner">责任人：韩新宇、魏海明</div>

<div class="scenario">基础配置模块（BC）</div>
<div class="scenario">数据查询验证（DQ / ID）</div>

<div class="note">配置是否支持业务快速启动，并可定位异常。</div>
<div class="note">数据与文件链路是否可追溯，关键节点可回放。</div>

<div class="footer">验证目标：确保追溯链路在真实业务场景下可以稳定运行并形成闭环。</div>
```

完整样例可参考：

[`input/uat_plan_sample.html`](../input/uat_plan_sample.html)

## 当前页面映射规则

- 第 1 个正文页：
  - 标题来自 `title`
  - 副标题来自 `subtitle`
  - 卡片内容优先来自 `phase-*`

- 第 2 个正文页：
  - 标题固定为“测试范围与关键场景”
  - 内容来自 `scenario`

- 第 3 个正文页：
  - 标题固定为“测试关注点与验收标准”
  - 内容来自 `note`
  - 如果有 `footer`，会优先作为补充说明使用

## 当前不支持的情况

- 任意复杂嵌套 HTML 的精准版式还原
- 图片、表格、图表自动识别
- 超过 3 类正文页的动态扩页
- 任意 class 自动推断业务含义

如果后面要扩展输入类型，建议先更新这份文档，再改生成逻辑。
