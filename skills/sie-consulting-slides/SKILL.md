---
name: sie-consulting-slides
description: >
  SIE 咨询风固定流程（AI 生成 SVG -> 脚本转 PPTX）。
  用于企业咨询型演示文稿生产，强制遵循固定配色、字体、密度和页面节奏规范。
---

# SIE Consulting Slides Skill

## 目标

- 以 `AI -> SVG -> PPTX` 作为默认主链路。
- 固化 SIE 咨询风视觉规范，不允许随意漂移。
- 保留现有 V2 语义规划与质量门禁能力。

## 固定规范（必须遵守）

- 主题色：`#AD053D`、`#932341`
- 正文体系：`#2C3E50`、`#4A5558`、`#6B7E85`
- 结构线条：`#7C969D`、`#B4C6CA`
- 页面背景：`#F2F6F6`，卡片背景：`#FFFFFF`
- 字体：`Microsoft YaHei` / `Microsoft YaHei Light`
- 正文字号：`12-14pt`，标题 `20-44pt` 分级

禁止：

- Inter / Roboto / Arial
- 大面积空白页
- 60pt+ 数字炸弹
- 无结论描述性标题

## 六阶段工作流

1. Phase 1 内容发现
- 明确受众、目的、页数、输入来源。

2. Phase 2 风格确认
- 固定使用 SIE 咨询风，不再让用户二选三配色。

3. Phase 3 内容规划
- 复用 V2 语义链路：`Context -> Strategy -> Outline -> Deck`。

4. Phase 4 SVG 生成
- 依据 `references/executor-consulting.md` 生成咨询风 SVG。

5. Phase 5 SVG 后处理
- 执行 `finalize_svg`（图标嵌入、图片裁剪、文本整理）。

6. Phase 6 导出 PPTX
- 执行 `svg_to_pptx -s final` 导出可编辑 PPTX。

## 工程落地映射

- 语义规划：`tools/sie_autoppt/v2/*`
- 固定主题：`tools/sie_autoppt/v2/themes/sie_consulting_fixed.json`
- SVG 转 PPTX 桥接：CLI 命令 `svg-export`
- 视觉规范：`STYLE_PRESETS.md`

## 建议命令

```powershell
python .\main.py make --topic "主题" --theme sie_consulting_fixed
python .\main.py svg-export --svg-project-path <project_path> --svg-stage final
```
