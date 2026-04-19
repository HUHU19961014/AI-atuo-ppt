# Enterprise-AI-PPT Vibecoding Quality Roadmap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不打断当前交付节奏的前提下，先解决命令契约漂移和工程一致性问题，再完成架构解耦与质量门禁升级。

**Architecture:** 采用“先对齐、再收敛、后增强”的三段式路线。先把 CLI 行为与文档对齐，再用类型/风格门禁降低回归风险，最后把 bridge/QA/traceability 做成更稳的可演进架构。

**Tech Stack:** Python 3.11, python-pptx, Pydantic v2, pytest, ruff, mypy, PowerShell.

---

## Vibecoding 执行总则（先看）

### AI 能力边界（要利用，也要防坑）

- AI 强项：
  - 快速生成样板代码、测试骨架、文档草稿。
  - 小范围重构（单模块、单责任变更）。
  - 把重复操作脚本化（检查、格式化、回归命令）。
- AI 弱项：
  - 跨文件隐式契约一致性（最容易漏改）。
  - 历史语义与业务“潜规则”保持。
  - 大改动下的边界条件覆盖。

### 统一执行规则

- 每个任务都先写“最小失败测试”，再改实现。
- 单次 AI 变更范围控制在 2-4 个文件，避免大面积漂移。
- 每个任务结束必须留下“可验证证据”：
  - 通过的测试命令输出。
  - 文档或契约文件更新。
  - 变更说明（为什么改、影响什么、没改什么）。
- 每个任务独立提交，提交信息必须含任务编号（如 `TASK-03`）。

## 时间总览（明确到日期）

| Phase | 日期范围 | 目标 |
|---|---|---|
| Phase A | 2026-04-20 ~ 2026-04-23 | 消除 P0 契约漂移，统一命令语义 |
| Phase B | 2026-04-24 ~ 2026-05-08 | 收敛工程质量债（mypy/ruff） |
| Phase C | 2026-05-09 ~ 2026-05-30 | 架构解耦（bridge 单一职责 + 输出隔离） |
| Phase D | 2026-05-31 ~ 2026-06-14 | QA 与 traceability 增强，接入发布门禁 |

---

### Task 1: 统一 `v2-render` 契约（P0）

**Why:** 代码要求 AI 才能 `v2-render`，但 README/CLI 文档仍写“无需 AI”，这是当前最直接的使用风险。

**What:**
- 明确并固定 `v2-render` 契约（推荐：保留 AI 必需）。
- 更新所有命令矩阵与说明文本，避免用户误操作。
- 加入契约漂移测试，防止未来再次反复。

**How:**
- [ ] **Step 1: 补充契约决策记录**
  - Create: `docs/superpowers/specs/2026-04-20-v2-render-contract-decision.md`
  - 内容包含：决策、备选方案、选择理由、兼容影响。
- [ ] **Step 2: 更新用户可见文档**
  - Modify: `README.md`
  - Modify: `docs/CLI_REFERENCE.md`
  - Modify: `docs/ARCHITECTURE.md`
  - 把 `v2-render` 的 “Needs AI” 标记与文案改成一致。
- [ ] **Step 3: 加入防漂移测试**
  - Modify: `tests/test_doc_drift.py`
  - 增加断言：`v2-render` 的文档描述必须与 CLI 实际行为一致。
- [ ] **Step 4: 运行回归**
  - Run: `python -m pytest tests/test_v2_cli.py tests/test_cli.py tests/test_doc_drift.py -q`
  - Expected: 全部通过。
- [ ] **Step 5: 提交**
  - Run: `git add README.md docs/CLI_REFERENCE.md docs/ARCHITECTURE.md tests/test_doc_drift.py docs/superpowers/specs/2026-04-20-v2-render-contract-decision.md`
  - Run: `git commit -m "fix(TASK-01): align v2-render AI contract across code and docs"`

**When:** 2026-04-20（1天）。

**注意事项（AI 相关）:**
- AI 很容易只改一个文档，漏掉另一个文档和测试。
- 本任务禁止“先改代码再补文档”，必须文档和测试同批提交。

**验收标准:**
- 文档中不再出现 `v2-render` “No AI”描述。
- `tests/test_doc_drift.py` 增加并通过新断言。

**回滚策略:**
- 如果契约变更引发外部工具不兼容，先回滚文档变更并保留决策记录，开分支继续讨论是否改回“可离线模式”。

---

### Task 2: 建立 CLI 单一事实源（Command Contract Registry）

**Why:** 当前命令能力散落在 CLI 代码和文档里，靠人工对齐不可靠。

**What:**
- 引入一个机器可读契约清单，作为文档和测试的共同来源。
- 让文档漂移检查从“硬编码字符串”升级为“契约驱动”。

**How:**
- [ ] **Step 1: 新建契约清单**
  - Create: `docs/CLI_CONTRACTS.json`
  - 包含字段：`command`, `needs_ai`, `primary_output`, `status`。
- [ ] **Step 2: 升级 doc drift 测试**
  - Modify: `tests/test_doc_drift.py`
  - 读取 `docs/CLI_CONTRACTS.json`，检查 README 和 CLI reference 的命令矩阵一致性。
- [ ] **Step 3: 文档引用契约清单**
  - Modify: `docs/CLI_REFERENCE.md`
  - 增加说明：“命令契约以 `docs/CLI_CONTRACTS.json` 为准。”
- [ ] **Step 4: 运行测试**
  - Run: `python -m pytest tests/test_doc_drift.py -q`
  - Expected: 通过。
- [ ] **Step 5: 提交**
  - Run: `git add docs/CLI_CONTRACTS.json docs/CLI_REFERENCE.md tests/test_doc_drift.py`
  - Run: `git commit -m "feat(TASK-02): add CLI contract registry and drift guard"`

**When:** 2026-04-21（1天）。

**注意事项（AI 相关）:**
- AI 生成 JSON 时常见字段命名漂移，必须固定 schema。
- 测试里不要再手写重复命令列表，避免第二个真相源。

**验收标准:**
- 新增 `docs/CLI_CONTRACTS.json`。
- doc drift 测试依赖该文件运行且通过。

**回滚策略:**
- 若契约文件格式引发现有测试冲突，保留文件，先降级为“只验证关键命令”（`make`, `batch-make`, `v2-render`）。

---

### Task 3: 输出目录隔离默认化（防覆盖）

**Why:** `v2/io.py` 默认仍写共享文件名，容易互相覆盖，影响可追溯与并行运行。

**What:**
- 让 `v2-make` 默认落到 run-scope 目录，减少人工传参依赖。
- 保留兼容开关，避免旧脚本立刻失效。

**How:**
- [ ] **Step 1: 定义默认策略**
  - Modify: `tools/sie_autoppt/cli_routing.py`
  - 新增环境变量策略（例：`SIE_AUTOPPT_DEFAULT_ISOLATED_OUTPUT=1` 默认开启）。
- [ ] **Step 2: CLI 参数说明补齐**
  - Modify: `tools/sie_autoppt/cli_parser.py`
  - 更新 `--isolate-output` 和 `--run-id` help 文案。
- [ ] **Step 3: 文档同步**
  - Modify: `README.md`
  - Modify: `docs/CLI_REFERENCE.md`
  - 增加 run-scope 输出示例。
- [ ] **Step 4: 测试覆盖**
  - Modify: `tests/test_v2_cli.py`
  - 增加“默认隔离输出”和“显式关闭隔离”的行为测试。
- [ ] **Step 5: 运行测试**
  - Run: `python -m pytest tests/test_v2_cli.py tests/test_cli.py -q`
  - Expected: 通过。
- [ ] **Step 6: 提交**
  - Run: `git add tools/sie_autoppt/cli_routing.py tools/sie_autoppt/cli_parser.py README.md docs/CLI_REFERENCE.md tests/test_v2_cli.py`
  - Run: `git commit -m "feat(TASK-03): make run-scoped output isolation default"`

**When:** 2026-04-22 ~ 2026-04-23（2天）。

**注意事项（AI 相关）:**
- AI 容易遗漏“兼容模式”。必须保留可关闭隔离的路径，减少旧流水线中断风险。
- 变更后要验证 Windows 路径拼接行为。

**验收标准:**
- 不传 `--isolate-output` 也能写入 run-scope（在开关默认开启时）。
- 文档、help、测试全部一致。

**回滚策略:**
- 如果影响范围超预期，回退默认策略，但保留实现和测试，通过环境变量灰度开启。

---

### Task 4: 把 SVG bridge 收敛为单一职责模块

**Why:** `v2/services.py` 与 `batch/pptmaster_bridge.py` 有重复导出逻辑，后续维护成本高。

**What:**
- 建立统一 bridge 入口，减少“同逻辑两处维护”。
- `v2/services.py` 不再直接持有外部脚本细节。

**How:**
- [ ] **Step 1: 新建 bridge 执行器**
  - Create: `tools/sie_autoppt/batch/bridge_runner.py`
  - 抽出共用能力：脚本解析、命令执行、超时处理、错误包装。
- [ ] **Step 2: 迁移 batch 侧调用**
  - Modify: `tools/sie_autoppt/batch/pptmaster_bridge.py`
  - 调用新执行器，保持行为不变。
- [ ] **Step 3: 瘦身 v2 services**
  - Modify: `tools/sie_autoppt/v2/services.py`
  - 删除重复命令执行细节，改为调用 bridge 执行器或兼容包装。
- [ ] **Step 4: 回归测试**
  - Run: `python -m pytest tests/test_batch_bridge.py tests/test_v2_services.py tests/test_v2_cli.py -q`
  - Expected: 通过。
- [ ] **Step 5: 提交**
  - Run: `git add tools/sie_autoppt/batch/bridge_runner.py tools/sie_autoppt/batch/pptmaster_bridge.py tools/sie_autoppt/v2/services.py tests/test_batch_bridge.py tests/test_v2_services.py`
  - Run: `git commit -m "refactor(TASK-04): centralize pptmaster bridge execution logic"`

**When:** 2026-04-24 ~ 2026-04-28（5天）。

**注意事项（AI 相关）:**
- AI 做重构时容易“看起来能跑，边角错误丢失”。必须保留原始错误信息（stderr/stdout）。
- 不要在同一提交中改变业务流程，仅做职责迁移。

**验收标准:**
- `v2/services.py` 不再保留重复 bridge 命令实现。
- batch 与 v2 路径均通过现有桥接测试。

**回滚策略:**
- 保留原入口函数签名，必要时可快速回挂旧实现。

---

### Task 5: Post-export QA 增强（从轻量到可交付）

**Why:** 当前 post-export QA 主要关注字体与 shape_map，缺少布局稳定性等更关键风险检测。

**What:**
- 新增可解释的 post-export 规则：最小字体、空标题、文本块异常密集、潜在遮挡。
- 规则结果接入现有 `route_qa_issues` 路由。

**How:**
- [ ] **Step 1: 扩展 QA 规则函数**
  - Modify: `tools/sie_autoppt/batch/qa_router.py`
  - 新增规则函数并统一输出 `QaIssue`。
- [ ] **Step 2: 规则分级与路由**
  - 修改 severity 与 repair_route 判定：
  - `warning` -> `tune`
  - `high` -> `regenerate`
  - `error` -> `stop`
- [ ] **Step 3: 测试覆盖**
  - Modify: `tests/test_batch_tuning.py`
  - Modify: `tests/test_batch_orchestrator.py`
  - 新增规则命中场景 fixture。
- [ ] **Step 4: 运行测试**
  - Run: `python -m pytest tests/test_batch_tuning.py tests/test_batch_orchestrator.py tests/test_batch_contracts.py -q`
  - Expected: 通过。
- [ ] **Step 5: 提交**
  - Run: `git add tools/sie_autoppt/batch/qa_router.py tests/test_batch_tuning.py tests/test_batch_orchestrator.py`
  - Run: `git commit -m "feat(TASK-05): strengthen post-export QA rules and routing"`

**When:** 2026-04-29 ~ 2026-05-03（5天）。

**注意事项（AI 相关）:**
- AI 容易过度加规则导致“误报雪崩”。每条新规则都要有明确阈值和测试样本。
- 不做“黑盒魔法评分”，必须输出可解释 issue 文本。

**验收标准:**
- post-export QA 能识别新增风险类型。
- 不影响现有通过路径（回归测试稳定）。

**回滚策略:**
- 对误报高的规则可通过配置开关临时关闭，不影响主流程。

---

### Task 6: `source_refs` 从页级粗粒度升级到块级

**Why:** 当前 `story_plan` 多数使用同一组 `source_refs`，追溯价值有限。

**What:**
- 在 `content_bundle` 中引入更细粒度 source 关联。
- 为后续“页面结论可解释性”打基础。

**How:**
- [ ] **Step 1: 扩展 bundle 结构（保持向后兼容）**
  - Modify: `tools/sie_autoppt/batch/contracts.py`
  - 给 `StoryPlanEntry` 增加可选字段（例如 `block_refs` / `evidence_refs`）。
- [ ] **Step 2: 预处理映射策略**
  - Modify: `tools/sie_autoppt/batch/preprocess.py`
  - 根据输入类型和 slide 内容生成更细粒度 source 映射；保留旧 `source_refs` 字段。
- [ ] **Step 3: 测试覆盖**
  - Modify: `tests/test_batch_contracts.py`
  - Modify: `tests/test_batch_preprocess.py`
- [ ] **Step 4: 运行测试**
  - Run: `python -m pytest tests/test_batch_contracts.py tests/test_batch_preprocess.py tests/test_batch_orchestrator.py -q`
  - Expected: 通过。
- [ ] **Step 5: 提交**
  - Run: `git add tools/sie_autoppt/batch/contracts.py tools/sie_autoppt/batch/preprocess.py tests/test_batch_contracts.py tests/test_batch_preprocess.py`
  - Run: `git commit -m "feat(TASK-06): add finer-grained source traceability in content bundle"`

**When:** 2026-05-04 ~ 2026-05-07（4天）。

**注意事项（AI 相关）:**
- AI 可能生成“看起来细粒度、实则没语义”的映射。要优先保证可解释，不追求字段花哨。
- 任何新字段必须是可选，避免破坏旧工件读取。

**验收标准:**
- 新工件包含块级/证据级引用。
- 旧工件仍可被解析并通过测试。

**回滚策略:**
- 若新字段导致下游不兼容，保留字段但不强制填充（降级为可空）。

---

### Task 7: Mypy 债务收敛（从 37 到 0）

**Why:** 类型错误集中且可修复，先清掉能显著提升后续重构安全性。

**What:**
- 清理 `template_manifest.py`, `inputs/html_parser.py`, `planning/layout_policy.py` 的类型错误。
- 把 `mypy` 结果纳入稳定门禁。

**How:**
- [ ] **Step 1: 分文件修复（先 `template_manifest.py`）**
  - Modify: `tools/sie_autoppt/template_manifest.py`
  - 修正 `dict/object` 泛型和 `int()` 入参校验。
- [ ] **Step 2: 修复 HTML parser 类型推断**
  - Modify: `tools/sie_autoppt/inputs/html_parser.py`
  - 规范 BeautifulSoup `class` 读取的类型处理。
- [ ] **Step 3: 修复 layout_policy 类型告警**
  - Modify: `tools/sie_autoppt/planning/layout_policy.py`
- [ ] **Step 4: 运行类型检查**
  - Run: `python -m mypy tools/sie_autoppt/v2/ tools/sie_autoppt/reference_styles.py tools/sie_autoppt/planning/deck_planner.py tools/sie_autoppt/planning/payload_builders.py tools/sie_autoppt/llm_openai.py tools/sie_autoppt/cli_v2_commands.py tools/sie_autoppt/language_policy.py`
  - Expected: 0 errors。
- [ ] **Step 5: 提交**
  - Run: `git add tools/sie_autoppt/template_manifest.py tools/sie_autoppt/inputs/html_parser.py tools/sie_autoppt/planning/layout_policy.py`
  - Run: `git commit -m "chore(TASK-07): resolve mypy type errors in core modules"`

**When:** 2026-05-08 ~ 2026-05-12（5天）。

**注意事项（AI 相关）:**
- AI 可能用 `Any` 暴力消错，禁止此做法。
- 每个修复都要保持运行语义不变，优先“类型收敛而非行为改写”。

**验收标准:**
- 目标 mypy 命令输出 0 errors。
- 关键回归测试保持通过。

**回滚策略:**
- 若某个类型修复引发运行回归，先局部回滚该块并保留错误注释，后续分支继续处理。

---

### Task 8: Ruff 债务治理（分层清理，避免停工）

**Why:** 全量 613 条一次性清理成本过高，需要“增量门禁 + 存量燃尽”双轨策略。

**What:**
- 将 ruff 从一次性清零改为“新增代码必须干净”。
- 按模块燃尽历史问题，优先核心路径。

**How:**
- [ ] **Step 1: 收敛门禁策略**
  - Modify: `scripts/quality_gate.ps1`
  - 改成“关键规则全量 + 其余规则变更集检查”。
- [ ] **Step 2: 核心模块优先清理**
  - 优先路径：`tools/sie_autoppt/v2/*`、`tools/sie_autoppt/batch/*`、`tools/sie_autoppt/cli*.py`。
- [ ] **Step 3: 每轮清理后回归**
  - Run: `python -m ruff check tools/sie_autoppt/v2 tools/sie_autoppt/batch tools/sie_autoppt/cli.py tools/sie_autoppt/cli_v2_commands.py`
  - Expected: 指定路径告警持续下降，且不引入新告警。
- [ ] **Step 4: 提交**
  - 每批独立提交，提交信息标注批次，如 `chore(TASK-08.2): ruff cleanup for v2 visual review`。

**When:** 2026-05-13 ~ 2026-05-21（9天）。

**注意事项（AI 相关）:**
- AI 自动格式化后容易改出“非必要语义变更”，必须限制在风格级改动。
- 每一批只做一个目录，避免回归定位困难。

**验收标准:**
- 关键路径 ruff 告警显著下降（目标：先降到 < 120）。
- 质量门禁脚本能阻止“新告警进入主分支”。

**回滚策略:**
- 任一批引发异常，整批回滚，不做人工半回滚。

---

### Task 9: 发布门禁与运行指标落地

**Why:** 现在有日志和工件，但缺统一发布判定与趋势可视化，不利于稳定迭代。

**What:**
- 固化发布门禁清单（测试、类型、ruff、doc drift）。
- 增加 run 级指标汇总（失败率、重试次数、degraded 占比）。

**How:**
- [ ] **Step 1: 增加指标汇总脚本**
  - Create: `tools/sie_autoppt/batch/report_metrics.py`
  - 读取 `output/runs/*/final/run_summary.json` 和日志，输出汇总 JSON/Markdown。
- [ ] **Step 2: 接入 quality gate**
  - Modify: `scripts/quality_gate.ps1`
  - 增加固定顺序：doc drift -> batch/v2 回归 -> mypy -> ruff（或指定关键规则）。
- [ ] **Step 3: 文档更新**
  - Modify: `docs/TESTING.md`
  - Modify: `docs/ONCALL_RUNBOOK.md`
  - 写明门禁失败的处理流程。
- [ ] **Step 4: 运行验证**
  - Run: `powershell -ExecutionPolicy Bypass -File .\\scripts\\quality_gate.ps1`
  - Expected: 成功，且生成指标输出。
- [ ] **Step 5: 提交**
  - Run: `git add tools/sie_autoppt/batch/report_metrics.py scripts/quality_gate.ps1 docs/TESTING.md docs/ONCALL_RUNBOOK.md`
  - Run: `git commit -m "feat(TASK-09): add release gate metrics and runbook integration"`

**When:** 2026-05-22 ~ 2026-05-30（9天）。

**注意事项（AI 相关）:**
- AI 会倾向加复杂指标，严格遵循 YAGNI：先做 4-6 个核心指标。
- 报表脚本必须可在本地离线跑通，不依赖外部服务。

**验收标准:**
- 发布门禁具备可执行脚本化流程。
- 能生成最近 N 次 run 的质量趋势报告。

**回滚策略:**
- 若门禁过严影响交付，先降级为 warning 模式并记录偏差，下一迭代再收紧。

---

## 依赖关系（执行顺序）

1. `TASK-01` -> `TASK-02`（先统一契约，再建单一事实源）
2. `TASK-03` 可与 `TASK-02` 并行
3. `TASK-04` 依赖 `TASK-01`（避免边改架构边改契约）
4. `TASK-05` 依赖 `TASK-04`
5. `TASK-06` 可与 `TASK-05` 并行
6. `TASK-07`、`TASK-08` 在 Phase B/C 穿插推进
7. `TASK-09` 在前面任务稳定后收口

## 风险清单（vibecoding 特别版）

- 风险 1：AI 一次改太多文件，导致隐藏回归。
  - 应对：限制每次变更范围；每任务至少 1 个针对性测试。
- 风险 2：AI“修测试”而不是“修问题”。
  - 应对：测试失败原因必须记录；不得删除失败断言掩盖问题。
- 风险 3：文档更新滞后于代码。
  - 应对：把文档更新作为每个任务的必选步骤，不允许后补。
- 风险 4：静态检查一次性清理失败导致团队停工。
  - 应对：增量门禁 + 存量燃尽双轨执行。

## 完成定义（Definition of Done）

- `TASK-01` 到 `TASK-09` 对应提交全部完成。
- 关键回归测试稳定通过。
- mypy 目标路径无报错。
- ruff 新增告警被门禁阻断。
- 文档、CLI 行为、测试契约三者一致。

