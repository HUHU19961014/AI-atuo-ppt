# SIE AutoPPT 项目代码审查报告

> 版本：v1.0  
> 审查日期：2026-04-05  
> 状态：待开发小组逐步落地

---

## 背景

本报告针对 [AI-atuo-ppt](https://github.com/HUHU19961014/AI-atuo-ppt) 项目进行系统性代码审查，涵盖架构可行性、代码逻辑质量、安全性、可维护性等维度。所有改进建议已经过业务方确认，开发小组请按优先级逐步落地。

---

## 一、架构总体评价

项目的核心架构思路是 **正确且有价值的**：

```
AI 规划层（智能内容）  →  DeckSpec JSON 合约层  →  Python 渲染层（确定性排版）
     LLM 输出结构化 JSON          中间表示           模板坐标驱动生成 .pptx
```

这种三层分离的设计让 AI 只负责"内容决策"，排版渲染完全由确定性程序完成，避免了让 AI 直接操控坐标的失控问题。这是工程上成熟的路径，整体设计值得肯定。

---

## 二、改进任务清单

### 🔴 P0 — 高优先级（必须修复）

---

#### 任务 1：页面数量改为内容驱动 + 用户可选范围

**问题位置：**
- `tools/sie_autoppt/config.py` → `MAX_BODY_CHAPTERS = 3`
- `tools/sie_autoppt/planning/ai_planner.py` → `clamp_requested_chapters()`
- `tools/sie_autoppt/planning/deck_planner.py` → `clamp_requested_chapters()`

**当前行为：**  
所有生成路径（`ai-plan`、`ai-make`）均将正文页数强制截断为最多 3 页，无论用户输入的内容量多大。

**改进方向（已确认）：**

1. **支持用户在生成前指定页数范围**  
   在 CLI 入口（`cli.py`）和配置层新增 `--min-slides` / `--max-slides` 两个可选参数，用于告诉 AI 规划器生成多少页范围内的 PPT：
   ```bash
   sie-autoppt ai-make --topic "季度汇报" --min-slides 6 --max-slides 12
   ```

2. **根据内容量动态推断页数**  
   当用户不指定范围时，由 AI 规划器根据输入内容的字数/结构自动决定合理页数，不再强制截断。参考逻辑：
   - 输入内容较少（< 500 字）→ 建议 3-5 页
   - 输入内容中等（500-2000 字）→ 建议 6-10 页
   - 输入内容较多（> 2000 字）→ 建议 10-20 页，或由用户显式指定上限

3. **移除 `MAX_BODY_CHAPTERS = 3` 硬上限**  
   将其改为一个可配置的软上限（例如默认 `MAX_BODY_CHAPTERS = 20`），并在 prompt 模板中传入用户指定的 `min_slides`/`max_slides`，让 AI 在范围内自行决策。

**相关文件清单：**
```
config.py                         # 修改 MAX_BODY_CHAPTERS
planning/ai_planner.py            # 修改 clamp_requested_chapters()，传入用户范围参数
planning/deck_planner.py          # 同上
cli.py                            # 新增 --min-slides / --max-slides 参数
docs/AI_PLANNER.md                # 更新文档说明
```

---

#### 任务 2：修复 external planner command 的命令注入风险

**问题位置：**  
`tools/sie_autoppt/planning/ai_planner.py`

**当前代码：**
```python
result = subprocess.run(
    planner_command,
    input=json_input,
    capture_output=True,
    text=True,
    shell=True,   # ← 危险
    check=False,
)
```

**风险说明：**  
`shell=True` 会将 `planner_command` 作为 shell 字符串执行。若该值来自用户配置文件、环境变量或 CLI 参数，攻击者可以注入 `;rm -rf /` 之类的命令。即使是企业内部工具，这也是不应出现的实践。

**修复方案：**

```python
import shlex

# 将字符串命令解析为参数列表，不走 shell
cmd_args = shlex.split(planner_command) if isinstance(planner_command, str) else planner_command

result = subprocess.run(
    cmd_args,
    input=json_input,
    capture_output=True,
    text=True,
    shell=False,   # ← 安全
    check=False,
)
```

**注意事项：**  
- Windows 下 `shlex.split` 行为与 Unix 一致，但需确认路径中含空格时是否被正确引用
- 若 `planner_command` 是列表，直接传入，无需 split

**相关文件清单：**
```
planning/ai_planner.py    # 修复 subprocess.run 调用
tests/test_ai_planner.py  # 补充注入场景的安全测试用例
```

---

### 🟠 P1 — 中优先级（本轮迭代内完成）

---

#### 任务 3：接受 pattern 解析低置信度路由（已确认接受）

**问题位置：**  
`tools/sie_autoppt/patterns.py` → `_score_patterns()`

**现状说明：**  
关键词打分阈值（`DEFAULT_PATTERN_LOW_CONFIDENCE_SCORE = 4`、`DEFAULT_PATTERN_MARGIN_THRESHOLD = 1`）是经验值，无数据支撑。但在 AI 规划路径（`ai-plan` / `ai-make`）下，AI 会直接指定 `pattern_id`，这套打分逻辑会被完全绕过——只在 HTML 遗留输入路径中生效。

**建议操作：**
- 在代码注释中明确说明该模块只在 HTML 遗留路径下激活
- 在 `patterns.py` 顶部添加 `# NOTE: This module is only used in legacy HTML input path.`
- 无需修改打分逻辑本身，但若后续出现误判反馈，可收集实际数据后重新标定阈值

---

#### 任务 4：封装 manifest 字段读取，统一错误处理（已确认接受）

**问题位置：**  
`tools/sie_autoppt/body_renderers.py`（8 个渲染器均存在此问题）

**当前代码（各渲染器中重复出现）：**
```python
x0 = int(spec["origin_left"])
y0 = int(spec["origin_top"])
card_w = int(spec["card_width"])
```

**问题：** manifest 字段缺失或类型错误时直接抛出 `KeyError`/`ValueError`，无任何上下文信息，调试极为困难。

**修复方案：**  
在 `body_renderers.py` 或单独的 `renderer_utils.py` 中封装工具函数：

```python
def _get_int(spec: dict, key: str, context: str = "") -> int:
    """从 manifest spec 中安全读取整型字段，报错时带上字段名和调用上下文。"""
    if key not in spec:
        raise KeyError(
            f"[渲染器错误] manifest 缺少必要字段 '{key}'"
            + (f"（来自：{context}）" if context else "")
        )
    try:
        return int(spec[key])
    except (TypeError, ValueError) as e:
        raise ValueError(
            f"[渲染器错误] manifest 字段 '{key}' 无法转换为整型，值为：{spec[key]!r}"
            + (f"（来自：{context}）" if context else "")
        ) from e
```

然后将所有 `int(spec["xxx"])` 替换为 `_get_int(spec, "xxx", context="渲染器名称")`。

**相关文件清单：**
```
body_renderers.py    # 全文替换裸 int() 调用
renderer_utils.py    # 新建工具函数文件（或合入 body_renderers.py）
```

---

#### 任务 5：明确 legacy clone 路径为 deprecated，移除静默 fallback（已确认接受）

**问题位置：**  
`tools/sie_autoppt/generator.py` → `_refresh_legacy_directory_clones()`

**当前问题：**
```python
for _ in range(3):
    ...
    time.sleep(1.0)   # 单线程程序中无意义的重试等待
```

这段代码通过暴力重试掩盖了 legacy clone 路径下图片资产复制不稳定的问题。静默 fallback 导致生成结果中出现图片缺失而用户不知情。

**修复方案：**
1. 在函数头部添加 `DeprecationWarning`，明确告知这是遗留路径
2. 若重试全部失败，抛出明确异常而非静默忽略：
   ```python
   raise RuntimeError(
       f"Legacy clone 路径图片资产复制失败（已重试 3 次）：{src_path} → {dst_path}。"
       "请迁移至 preallocated pool 模板路径。"
   )
   ```
3. 在 README 和 TESTING.md 中标注 legacy clone 路径为 deprecated

---

#### 任务 6：修正默认 AI 模型名称（已确认接受）

**问题位置：**  
`tools/sie_autoppt/config.py`

**当前代码：**
```python
DEFAULT_AI_MODEL = os.environ.get("SIE_AUTOPPT_LLM_MODEL", "gpt-5.4-mini")
```

**问题：** OpenAI 目前没有 `gpt-5.4-mini` 这个模型，这很可能是 `gpt-4o-mini` 或 `gpt-4.1-mini` 的笔误。所有未设置 `SIE_AUTOPPT_LLM_MODEL` 环境变量的用户会直接因模型不存在而报错。

**修复方案：**  
核实当前 OpenAI 可用模型，将默认值改为正确的模型名：
```python
# 建议使用 gpt-4o-mini 或 gpt-4.1-mini，请核实后更新
DEFAULT_AI_MODEL = os.environ.get("SIE_AUTOPPT_LLM_MODEL", "gpt-4o-mini")
```

---

#### 任务 7：修复 Unicode 转义中文字符串（已确认接受）

**问题位置：**  
`tools/sie_autoppt/generator.py`（以及其他含 `\uXXXX` 中文字符串的文件）

**当前代码：**
```python
raise ValueError(
    f"\u6a21\u677f\u9875\u6570\u4e0d\u8db3..."   # Unicode 转义的"模板页数不足..."
)
```

**问题：** 用 Unicode 码点转义来写中文是反模式，严重降低代码可读性，维护人员无法直接阅读错误信息内容。

**修复方案：**  
确保所有 `.py` 文件以 UTF-8 编码保存，将 Unicode 转义直接改写为中文：
```python
raise ValueError(
    f"模板页数不足..."
)
```

**操作步骤：**
1. 全局搜索 `\u` 出现位置：`grep -rn '\\u[0-9a-f]\{4\}' tools/`
2. 逐一还原为可读中文
3. 确认文件编码头为 UTF-8

---

### 🟡 P2 — 低优先级（有余力时跟进）

---

#### 任务 8：补充 `requirements.txt` 或 `pyproject.toml`（已确认接受）

**问题：** 项目缺少依赖声明文件，新加入成员无法快速搭建环境。根据代码推断，至少需要声明以下依赖：

```
python-pptx>=0.6.21
openai>=1.0.0
beautifulsoup4>=4.12.0
lxml>=4.9.0
```

**建议操作：**
- 新增 `requirements.txt`（简单快速）
- 或新增 `pyproject.toml` + `[project.dependencies]`（更规范，适合打包发布）

---

## 三、不纳入本轮改进的项目

以下问题已经过业务方确认，**本轮暂不调整**：

| 编号 | 问题描述 | 确认原因 |
|------|---------|---------|
| 主题色硬编码 | `config.py` 中颜色和字体写死 | 当前为公司品牌定制版，暂不需要多模板切换 |
| HTML 解析路径 | `deck_planner.py` 中 CSS class 强耦合解析 | 遗留兼容路径，暂不调整 |
| 输出默认路径 | 输出到桌面的逻辑 | 当前使用场景为本地桌面端，适合现状 |

---

## 四、任务优先级总览

| 优先级 | 任务 | 关联文件 | 难度估计 |
|--------|------|----------|---------|
| 🔴 P0 | 页面数量改为内容驱动 + 用户可选范围 | config.py, ai_planner.py, deck_planner.py, cli.py | 中（1-2天） |
| 🔴 P0 | 修复 shell=True 命令注入风险 | ai_planner.py | 小（< 1小时） |
| 🟠 P1 | 封装 manifest 字段读取，统一报错 | body_renderers.py | 小（半天） |
| 🟠 P1 | 修正默认模型名 gpt-5.4-mini | config.py | 极小（5分钟） |
| 🟠 P1 | 修复 Unicode 转义中文字符串 | generator.py 等 | 小（1小时） |
| 🟠 P1 | legacy clone 路径添加 deprecated 声明 + 明确报错 | generator.py | 小（1小时） |
| 🟠 P1 | patterns.py 添加注释说明适用范围 | patterns.py | 极小（10分钟） |
| 🟡 P2 | 补充 requirements.txt | 项目根目录 | 极小（15分钟） |

---

## 五、架构优点（保留现状）

以下是代码审查中发现的亮点，开发过程中请注意保持：

- **DeckSpec JSON 中间合约**：AI 层与渲染层完全解耦，中间格式稳定，是整个系统的核心资产，任何改动都需要同步更新 `DECK_JSON_SPEC.md`
- **外部 planner command 接口**：stdin/stdout 的外部命令接口设计有前瞻性，无需修改代码即可接入任意 LLM，请确保在改进过程中不破坏此接口
- **DeckRenderTrace 渲染追踪**：每次生成的 fallback 链路都有记录，请保留此机制并在新增渲染器时同步补充 trace 节点
- **slide_ops.py ZIP 级别操作**：直接操作 pptx 包的代码质量较高，改动时注意 content_types 和关系图的完整性

---

*本报告由代码审查生成，如有疑问请联系审查方确认。*
