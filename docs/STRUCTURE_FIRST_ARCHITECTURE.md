# 结构优先架构图

## 当前架构

```text
用户输入
  -> CLI / Services
  -> Prompt 组装
  -> LLM 直接生成整页内容 / DeckSpec
  -> DeckSpec 解析
  -> PPT Render Service
  -> 导出
```

当前直接调用 LLM 生成整页内容的主要位置：

- `tools/sie_autoppt/planning/ai_planner.py`
- `tools/sie_autoppt/services.py` 中的 `generate_plan_with_ai()` / `render_from_ai_plan()`

## 目标架构

```text
用户输入
  -> Clarifier（可选）
  -> Structure Service
  -> Structure JSON
  -> Content Service
  -> Slide Schema Mapping
  -> DeckSpec JSON
  -> Render Service
  -> 导出
```

## 模块职责

### Structure Service

位置：

- `tools/sie_autoppt/structure_service.py`

职责：

- 只生成结构，不生成 PPT
- 输出 `core_message + structure_type + sections`
- 对输出做代码级硬校验
- 校验失败自动重试，最多 3 次

### Content Service

位置：

- `tools/sie_autoppt/content_service.py`

职责：

- 按结构逐页生成内容
- 将 `StructureSpec` 转为 `DeckSpec`
- 通过 `map_structure_to_slide_schema()` 将页面映射到 4 类基础表达方式

### Render Service

保留位置：

- `tools/sie_autoppt/generator.py`
- `tools/sie_autoppt/body_renderers.py`

职责：

- 只负责把 `DeckSpec` 渲染成 PPT
- 不再承担结构决策职责

## 保留与删除策略

保留：

- 现有模板与渲染器
- `DeckSpec` 导出链路
- `clarifier` 作为输入补全层

逐步降级旧逻辑：

- “Topic -> LLM -> 直接整页 DeckSpec” 不再是首选主链路
- 旧 `ai_planner` 保留兼容入口，但新主线优先使用 `Structure Service`

## 本轮新增入口

- `sie_autoppt structure`
- `sie_autoppt structure-plan`
- `sie_autoppt structure-make`
