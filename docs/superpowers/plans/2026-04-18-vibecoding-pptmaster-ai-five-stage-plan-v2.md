# Enterprise-AI-PPT Pptmaster-Style AI 五阶段改造实施计划（V2）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把当前项目的“需求澄清、大纲、语义 deck、质量重写、review patch”统一改造成与 `pptmaster` 同类的 AI 主导流水线，同时保留企业场景必须的可追溯与确定性护栏。

**Architecture:** 采用“AI 负责设计与生成，工程负责约束与验收”的双层架构。上层是五阶段 AI 编排链路（Clarify -> Outline -> Semantic Deck -> Rewrite -> Review Patch），下层是契约校验、回退策略、质量闸门与运行工件管理，保证可复现与可运维。

**Tech Stack:** Python 3.11, Pydantic v2, Agent workflow（Cursor/Claude/Copilot）, python-pptx, pytest, ruff, mypy, PowerShell（保留 OpenAI-compatible API 作为可选兼容模式）.

---

## 0. 为什么要重写旧任务清单

旧清单的问题不是“错”，而是“重心不再匹配当前目标”：

1. 旧清单包含大量工程债务任务（例如 mypy/ruff 全量清理），对提升“AI 五阶段能力”帮助间接。
2. 新目标已经明确为“对齐 pptmaster 的 AI 使用方式”，需要先把阶段编排和契约打通，再做大规模工程清理。
3. 当前 `v2-*` 与 `batch-make` 两条链路阶段定义不一致，继续按旧清单推进会出现重复建设。

### 0.1 旧任务调整结论（必须先对齐）

| 旧任务 | 处理方式 | 调整原因 |
|---|---|---|
| TASK-01 `v2-render` 契约统一 | **保留并升级为 TASK-A07** | 要扩展成“全命令 AI 阶段契约矩阵”，不只 `v2-render` |
| TASK-02 CLI Contract Registry | **保留并并入 TASK-A01/A07** | 契约登记仍然关键，但要覆盖五阶段 |
| TASK-03 输出目录隔离默认化 | **保留（顺位后移）** | 是运行稳定性需求，不是五阶段核心阻塞 |
| TASK-04 Bridge 单一职责 | **保留并并入 TASK-A06** | review patch 与桥接要合并考虑 |
| TASK-05 Post-export QA 强化 | **保留并并入 TASK-A05/A06** | QA 要前后两段化（语义前置 + 导出后） |
| TASK-06 source_refs 细粒度 | **保留并并入 TASK-A04** | 是语义 deck 可追溯核心能力 |
| TASK-07 mypy 债务 | **后置到 TASK-A10** | 当前非 P0，先保证业务链路 |
| TASK-08 ruff 债务 | **后置到 TASK-A10** | 同上 |
| TASK-09 发布闸门与指标 | **保留并升级为 TASK-A08/A09** | 与新流水线质量回归强相关 |

---

## 1. Vibecoding 执行总策略（结合 AI 优缺点）

### 1.1 AI 强项（要利用）

- 需求理解、多候选方案生成、语义组织速度快。
- 在统一 schema 约束下，能稳定产出结构化 JSON。
- 适合做“先生成再筛选”的候选并行（例如 semantic candidate）。

### 1.2 AI 弱项（要防范）

- 隐式契约容易漂移：同一个字段在不同阶段命名变体。
- 输出稳定性随 prompt/模型轻微变化而波动。
- 容易“看起来合理”但与来源证据脱钩（幻觉）。

### 1.3 统一防护规则（所有任务遵守）

- 每个阶段必须有独立 artifact（JSON）和 schema 校验。
- 每次改动先补失败测试，再改实现，再跑回归。
- 每个任务单次改动建议 2-5 文件，避免 vibecoding 大范围漂移。
- 所有 AI 阶段都要输出 `why_trace`（为什么这么生成）和 `source_refs`（基于哪些输入）。

### 1.4 运行模式约束（关键纠偏）

- 默认模式：`Agent-First`（参考 `pptmaster`），项目运行链路不直接调用 LLM API，因此不要求用户额外配置 API Key。
- 兼容模式：`Runtime-API`，仅用于脱离 Agent 的自动化执行场景，此时才需要 API endpoint / API Key。
- 文档与命令行都必须标明当前模式，禁止“看起来是 Agent 模式，实际偷偷走 API 调用”。

---

## 2. 时间计划（明确到日期）

| Wave | 日期 | 目标 |
|---|---|---|
| Wave 1 | 2026-04-19 ~ 2026-04-21 | 固化五阶段契约与命令行为矩阵 |
| Wave 2 | 2026-04-22 ~ 2026-04-27 | 完成 Clarify / Outline / Semantic Deck 对齐 |
| Wave 3 | 2026-04-28 ~ 2026-05-02 | 完成 Quality Rewrite / Review Patch 对齐 |
| Wave 4 | 2026-05-03 ~ 2026-05-08 | 完成回归、灰度、runbook 与指标闭环 |
| Wave 5 | 2026-05-09 ~ 2026-05-12 | 处理静态检查存量债务（mypy/ruff） |

---

## 3. 调整后的任务清单（V2）

### Task A01: 五阶段统一契约与工件模型（P0）

**目标：** 给五个阶段建立统一 I/O 契约、阶段状态和工件命名，消除 `v2-*` 与 `batch-make` 的语义偏差。

**Why：** 如果没有统一契约，AI 阶段越多，漂移越快；后续 QA 和回放都会失真。

**What：**

- 新增或升级以下契约文档/配置：
  - `docs/CLI_CONTRACTS.json`
  - `docs/superpowers/specs/2026-04-19-ai-five-stage-contract.md`
- 约束字段：`stage`, `input_schema`, `output_schema`, `ai_execution_mode`, `requires_api_key`, `fallback_mode`, `retry_policy`。

**How（步骤）：**

- [ ] Step 1: 盘点现有命令与阶段映射（`v2-outline/v2-plan/v2-make/v2-render/batch-make/v2-review/v2-patch`）。
- [ ] Step 2: 输出统一阶段表（Clarify/Outline/Semantic/Rewrite/ReviewPatch）。
- [ ] Step 3: 在 `docs/CLI_CONTRACTS.json` 增加阶段字段与执行模式字段（`agent_first` / `runtime_api` / `none`）。
- [ ] Step 4: 新增 drift 测试，确保 README/CLI_REFERENCE 与契约同步。
- [ ] Step 5: 提交文档与测试。

**When：** 2026-04-19。

**注意事项（AI优缺点）：**

- AI 容易把 `review` 和 `rewrite` 混成一阶段，命名必须硬约束。
- 同义词（review_patch/reviewpatch/review-patch）必须映射到同一标准键。

**完成标准：**

- 所有相关命令都能在契约表中定位到五阶段之一。
- 契约漂移测试通过。

---

### Task A02: 需求澄清（Clarify）阶段 AI 化对齐（P0）

**目标：** 把当前“topic/brief 直接进入 outline”的路径升级为“先 AI 澄清，再生成大纲”的标准入口。

**Why：** pptmaster 风格的核心是先确定设计意图，不是直接开画布。

**What：**

- 统一使用澄清产物（受众、目标、风格约束、章节深度）作为 Outline 输入。
- 在 `batch-make` 路径补齐 Clarify 阶段产物 `clarify_result.json`。

**How（步骤）：**

- [ ] Step 1: 抽取 Clarify 公共服务层（避免 `cli.py` 与 `v2/services.py` 各写一套）。
- [ ] Step 2: 在 `batch/preprocess.py` 接入 Clarify 输出，替代纯 topic/brief 直连。
- [ ] Step 3: 产出 `preprocess/clarify_result.json`，写入关键决策字段。
- [ ] Step 4: 为“澄清失败/字段缺失”补充失败测试与默认降级值。
- [ ] Step 5: 回归 `v2-plan` 与 `batch-make` 路径。

**When：** 2026-04-20 ~ 2026-04-21。

**注意事项（AI优缺点）：**

- AI 在澄清阶段容易过度发挥，必须限制输出 schema，禁止自由散文。
- 缺字段时要可降级（默认 audience/theme），不能全链路中断。

**完成标准：**

- Clarify 工件在 `v2` 和 `batch` 路径都可追溯。
- Outline 入参来自 Clarify 工件而非裸 topic。

---

### Task A03: 大纲（Outline）阶段策略化（P0）

**目标：** 让大纲阶段具备“策略约束 + 页数边界 + 结构质量校验”，对齐 pptmaster strategist 思路。

**Why：** 结构错了，后面语义 deck 再好也只能返工。

**What：**

- 强化 `OutlineGenerationRequest`：明确章节、页数范围、听众层级、叙事节奏。
- 大纲输出增加 `story_rationale` 字段，说明结构依据。

**How（步骤）：**

- [ ] Step 1: 在 `v2/services.py` 的 outline schema 中新增策略字段。
- [ ] Step 2: 更新 outline prompt，加入“结论导向 + 节奏控制”约束。
- [ ] Step 3: 增加大纲质量检查（页数、章节完整性、标题可读性）。
- [ ] Step 4: 失败时走一次自动修复重试（带 validation feedback）。
- [ ] Step 5: 为边界案例补测试（最小页数、最大页数、空 brief）。

**When：** 2026-04-22。

**注意事项（AI优缺点）：**

- AI 可能产出“看起来高级但不可执行”的标题，需规则拦截。
- 不要在 outline 阶段预埋具体视觉布局，避免越界到 semantic 阶段。

**完成标准：**

- 大纲阶段失败率下降，并可解释每页设置原因。
- 结构异常可在阶段内被拦截，不流入后续阶段。

---

### Task A04: 语义 Deck 阶段候选化 + 可追溯化（P0）

**目标：** 用候选并行 + 自动选择替代单次生成，提升质量上限与稳定性。

**Why：** 单次语义生成波动大；候选机制更符合 AI 统计特性。

**What：**

- 使用 `generate_semantic_decks_with_ai_batch` 作为默认路径（可配置候选数）。
- 扩展 `source_refs` 到块级或论点级（不是仅页级）。

**How（步骤）：**

- [ ] Step 1: 定义 candidate 评分指标（结构一致性、证据覆盖、可渲染性）。
- [ ] Step 2: 在 `v2-plan` / `batch-preprocess` 接入候选选择逻辑。
- [ ] Step 3: 扩展 `content_bundle.story_plan` 的引用粒度字段。
- [ ] Step 4: 新增“多候选中选优”回归测试。
- [ ] Step 5: 保留 `--batch-size=1` 兼容模式。

**When：** 2026-04-23 ~ 2026-04-24。

**注意事项（AI优缺点）：**

- 候选数量不是越多越好；先默认 2-3，控制 token 成本。
- AI 可能在候选中“形式不同但错误相同”，评分需覆盖硬规则。

**完成标准：**

- 默认可产生候选并稳定选优。
- 语义 deck 能追溯到输入证据块。

---

### Task A05: 质量重写（Quality Rewrite）阶段分层化（P0）

**目标：** 把质量重写从“单次尝试”升级为“规则判定 + 有限重写回路 + 失败分流”。

**Why：** 当前一次 rewrite 不通过就失败，易导致可修问题被误判为硬失败。

**What：**

- 预渲染 QA 与重写形成可重试闭环。
- 明确 `warning/high/error` 对应路由（tune/regenerate/stop）。

**How（步骤）：**

- [ ] Step 1: 拆分 pre-export QA 规则与 rewrite 执行器。
- [ ] Step 2: 增加重写轮次上限（例如 2 轮）和每轮变更报告。
- [ ] Step 3: 将路由结果标准化写入 `qa/pre_export_qa_report.json`。
- [ ] Step 4: 新增“可修复问题最终通过”的集成测试。
- [ ] Step 5: 新增“不可修复问题快速停止”的测试。

**When：** 2026-04-25 ~ 2026-04-27。

**注意事项（AI优缺点）：**

- AI 重写容易“修 A 破 B”，每轮都必须做回归检查。
- 限制每轮改动范围，避免全盘重写导致信息丢失。

**完成标准：**

- 可修复问题能在有限轮次内收敛。
- 不可修复问题能明确报错原因并停止。

---

### Task A06: Review Patch 阶段统一化（P0）

**目标：** 把 `v2-render` 的 AI review patch 能力下沉成公共阶段，`v2` 与 `batch` 共享。

**Why：** 现在 review patch 只在部分命令前置，导致不同路径交付质量不一致。

**What：**

- 抽出统一 ReviewPatch 服务（生成评审 + patch + 应用 + 校验）。
- 把 patch 应用前后对比工件写入 run 目录。

**How（步骤）：**

- [ ] Step 1: 从 `v2/visual_review.py` 抽取公共 API（review_once / generate_patch / apply_patch）。
- [ ] Step 2: 在 `batch` 流水线导出后引入同样 review patch 入口（可开关）。
- [ ] Step 3: 加入 patch 冲突与旧值不匹配保护。
- [ ] Step 4: 统一输出 `review_once.json`、`patches_review_once.json`、`patched.deck.json`。
- [ ] Step 5: 做端到端回归（v2-render 与 batch-make 两条路径）。

**When：** 2026-04-28 ~ 2026-04-30。

**注意事项（AI优缺点）：**

- AI 生成 patch 有概率指向错误字段，必须严格 JSONPath/字段校验。
- patch 只能改 blocker 问题，warning 不自动改，避免过度编辑。

**完成标准：**

- ReviewPatch 成为标准阶段，可在两条主链路复用。
- patch 应用失败时能给出精确冲突信息。

---

### Task A07: Agent 模式与 API 模式契约化（P0）

**目标：** 明确“默认 Agent-First 免 key、Runtime-API 才需要 key”的双模式契约，并写死到命令行为与文档。

**Why：** 当前最大误解点是“用了 agent 还被要求 key”；需要一次性消除歧义。

**What：**

- 输出命令级执行矩阵：`agent_first / runtime_api / none`。
- 默认 `agent_first` 路径不要求 API Key；保留 `runtime_api` 兼容开关。
- 保留 `batch-make --content-bundle-json` 的无 API 快速通道。

**How（步骤）：**

- [ ] Step 1: 在 `docs/CLI_CONTRACTS.json` 为每个命令增加 `ai_execution_mode` 与 `requires_api_key`。
- [ ] Step 2: CLI 默认走 `agent_first`；仅当显式 `--llm-mode runtime_api` 时校验 key。
- [ ] Step 3: 更新 `README.md` 与 `docs/CLI_REFERENCE.md` 的“Agent 模式 vs API 模式”章节。
- [ ] Step 4: 增加契约测试，防止文档与行为再次漂移。
- [ ] Step 5: 对 `v2-render` / `v2-make` / `batch-make` 做行为验收。

**When：** 2026-05-01。

**注意事项（AI优缺点）：**

- Agent 模式下，AI 质量依赖你使用的 IDE/平台模型能力，不由项目内 key 决定。
- Runtime-API 模式才需要关心 key/endpoint；两种模式的日志要可区分。

**完成标准：**

- 用户可一眼看懂每个命令默认运行模式。
- Agent 模式下不再出现“强制配置 API Key”报错。

---

### Task A08: 五阶段回归基线与指标（P1）

**目标：** 建立一组固定样本，让五阶段改造有客观对比，不靠体感。

**Why：** 没有 baseline，AI 迭代只能“看起来变好了”。

**What：**

- 建立 10-20 个固定输入样本（文字/图片/附件/结构化数据）。
- 统计指标：成功率、平均重试次数、平均 token、平均总时延、degraded 占比。

**How（步骤）：**

- [ ] Step 1: 建立 `tests/fixtures/batch/ai_five_stage_baseline/`。
- [ ] Step 2: 编写回放脚本，批量执行并输出对比表。
- [ ] Step 3: 将指标写入 `output/runs/*/final/run_summary.json` 聚合。
- [ ] Step 4: 接入 `scripts/quality_gate.ps1`，设定最低通过阈值。
- [ ] Step 5: 在文档中记录“基线版本 -> 当前版本”变化。

**When：** 2026-05-02 ~ 2026-05-05。

**注意事项（AI优缺点）：**

- AI 模型版本变更会影响结果，必须记录 model/version。
- 不要只看通过率，要同时看成本与时延。

**完成标准：**

- 每次改动都可对照 baseline 报表。
- 关键指标可追踪趋势，不再黑箱。

---

### Task A09: 上线策略与运行手册（P1）

**目标：** 用可控方式切换到新五阶段，不一次性冒险替换全量流量。

**Why：** 这是生产链路，必须灰度和可回滚。

**What：**

- 增加 feature flag：`SIE_AUTOPPT_AI_FIVE_STAGE_ENABLED`。
- 先内部灰度，再全量切换；失败自动回退旧路径。

**How（步骤）：**

- [ ] Step 1: 新旧流水线并存，默认旧路径。
- [ ] Step 2: 10% 灰度（内部任务）观察 2 天。
- [ ] Step 3: 50% 灰度观察 2 天。
- [ ] Step 4: 达标后全量，并保留一键回退开关。
- [ ] Step 5: 更新 `docs/ONCALL_RUNBOOK.md` 与应急流程。

**When：** 2026-05-06 ~ 2026-05-08。

**注意事项（AI优缺点）：**

- AI 相关故障通常是“间歇性”，灰度观察窗口不能太短。
- 回退不能依赖人工改代码，必须配置化。

**完成标准：**

- 灰度过程有日志、有阈值、有回退记录。
- 运维可独立执行故障处理，不依赖开发在线排障。

---

### Task A10: 存量工程债务收口（P2）

**目标：** 在五阶段稳定后，再统一收敛 mypy/ruff 存量问题。

**Why：** 先业务链路后工程洁癖，符合当前阶段收益最大化。

**What：**

- 处理当前已识别的核心类型错误路径。
- 执行增量 ruff 门禁，避免新增告警。

**How（步骤）：**

- [ ] Step 1: 修复 `template_manifest.py`, `inputs/html_parser.py`, `planning/layout_policy.py` 的类型错误。
- [ ] Step 2: 关键路径先清理 ruff（`v2/`, `batch/`, `cli*`）。
- [ ] Step 3: 门禁设置为“新增问题阻断，存量分批治理”。
- [ ] Step 4: 每批次回归测试后再提交。
- [ ] Step 5: 更新质量趋势记录。

**When：** 2026-05-09 ~ 2026-05-12。

**注意事项（AI优缺点）：**

- 禁止用 `Any` 大面积消错。
- 代码风格清理不得改变业务语义。

**完成标准：**

- mypy 核心路径归零。
- ruff 新增告警可被门禁阻断。

---

## 4. 执行顺序与依赖

1. `A01` 是所有任务前置。
2. `A02 -> A03 -> A04` 是前半段主链路。
3. `A05` 依赖 `A04`（有语义 deck 才能稳定重写）。
4. `A06` 依赖 `A05`（review patch 要接在质量重写之后）。
5. `A07` 可与 `A05/A06` 并行，但上线前必须完成。
6. `A08` 在 `A06` 后启动，作为灰度前门槛。
7. `A09` 依赖 `A08`。
8. `A10` 最后做。

---

## 5. 风险清单（Vibecoding + AI 版本）

- 风险 1：跨阶段字段漂移导致后续阶段解析失败。  
  应对：所有阶段输出先过 schema，再落盘。

- 风险 2：AI 重写导致语义偏移。  
  应对：重写前后做关键字段 diff 与 source_refs 保留检查。

- 风险 3：review patch 误改字段。  
  应对：old_value 必须匹配，否则拒绝 patch。

- 风险 4：模型波动导致回归不稳定。  
  应对：固定 baseline 样本与版本记录，超阈值自动回退。

---

## 6. Definition of Done（新版）

- 五阶段契约落地并在命令层可见。
- `v2-*` 与 `batch-make` 在阶段语义上对齐。
- Agent 模式与 API 模式有统一文档、统一契约、统一报错。
- ReviewPatch 成为可复用标准阶段。
- 回归基线与灰度机制可运行。
- 旧清单中的高价值任务已并入新版，低优先级债务已后置且有明确时间窗。
