# Enterprise-AI-PPT 现状诊断报告

> 生成日期：2026-04-10
> 诊断对象：`C:\Users\CHENHU\Documents\cursor\project\AI-atuo-ppt`
> 诊断方式：代码审查 + CLI 实测 + 测试回归
> 基线结果：
> - `pytest -q`：`226 passed`
> - `python .\main.py --help`：成功
> - `python .\main.py demo`：成功，生成实际 `.pptx`

---

## 1. 执行摘要

### 总体判断

当前项目已经不是“启动即崩”的状态，而是一个**可运行、可测试、主链路可交付**的 V2 语义化 PPT 生成系统。

它当前最主要的问题，不再是 P0 级“不能用”，而是以下三类：

1. **产品表面已经 V2-first，但仓库内部仍保留较多 legacy 路径，导致认知和维护成本偏高。**
2. **澄清、文档、工具链之间仍有局部错配，容易把用户带入当前主流程不支持的选项。**
3. **自动化测试覆盖很强，但对“真实模型 + 真实环境 + 最终成稿质量”的验证仍然偏弱。**

### 结论分级

- **已确认事实**
  - V2 CLI 主路径可用。
  - `demo` 无 API 模式可用。
  - 深度模式已落地，不是仅存在于文档中的设想。
  - 质量门禁、自动改写、视觉复核链路已接入。
- **高概率推断**
  - 当前项目的主要风险已经从“功能缺失”转向“边界不清”和“兼容层债务”。
  - 如果不继续收敛 legacy 入口，后续文档和协作成本会持续上升。
- **待验证假设**
  - 真实线上模型在复杂主题下的“讲得对、讲得深”质量，仍需独立样本回归验证。

### 建议优先级

- **P1**：清理澄清器和文档中的 legacy 误导项。
- **P1**：把 V2 主路径、兼容路径、实验路径明确隔离。
- **P2**：补齐真实 LLM 端到端回归，而不只依赖 mocked tests。
- **P2**：把视觉复核对 PowerPoint / LibreOffice 的环境依赖显式化。

---

## 2. 当前项目状态

## 2.1 系统类型

这是一个**模块化单体 Python 项目**，当前对外主路径是：

`Topic / Brief -> Clarify -> V2 Outline -> Semantic Deck -> Compiled Deck -> PPTX -> Review / Iterate`

主要模块分层如下：

- `tools/sie_autoppt/cli.py`
  - 统一命令入口和工作流分发。
- `tools/sie_autoppt/clarifier.py`
  - 需求澄清、上下文补全、主题/页数/受众解析。
- `tools/sie_autoppt/v2/services.py`
  - V2 的 AI 规划主服务，负责结构化上下文、战略分析、outline、semantic deck 生成。
- `tools/sie_autoppt/v2/deck_director.py`
  - 语义 deck 到可渲染 deck 的本地编译层。
- `tools/sie_autoppt/v2/ppt_engine.py`
  - 质量门禁、自动改写、渲染输出。
- `tools/sie_autoppt/v2/visual_review.py`
  - 视觉复核和多轮自动修正。
- `tools/sie_autoppt/generator.py`、`tools/sie_autoppt/structure_service.py`
  - 保留中的 legacy HTML / 模板生成兼容路径。

## 2.2 当前已经确认可用的能力

以下能力已由代码和实测确认：

- `make / v2-make / v2-plan / v2-render / review / iterate / demo / clarify / clarify-web / ai-check` 均已在 CLI 中注册。
- `clarify_web.py` 存在，`clarify-web` 不再因导入缺失而崩溃。
- `--generation-mode deep` 已接入：
  - 结构化上下文提取
  - 战略分析 prompt
  - 基于分析的 outline / semantic deck 生成
- semantic deck 已支持：
  - `anti_argument`
  - `data_sources`
- quality gate 已不仅检查格式，还覆盖：
  - generic opening / closing
  - 重复标题
  - 邻近重复内容
  - 缺少下一步 / 决策页
- `demo` 已能在无 API key 条件下渲染样例 PPT。

## 2.3 当前最真实的项目定位

当前最准确的定位，不是“模板驱动 PPT 生成器”，而是：

**AI 规划 + 本地语义编译 + 稳定 PPTX 渲染 + 自动复核的企业汇报系统**

legacy 模板/HTML 仍存在，但已经不应再被视为对外主路径。

---

## 3. 已确认问题

## 3.1 P1：澄清器仍会主动提供当前 V2 主流程不支持的 legacy 模板选项

### 证据

- `tools/sie_autoppt/clarifier.py`
  - `template_theme` 维度会同时列出 `theme:*` 和 `template:*`
  - 文案明确写着“`template:*` is legacy only”
- 实测：
  - `python .\main.py clarify --topic "帮我做PPT"` 返回的问题列表中，仍给出 `template:sie_template`、`template:business_gold`、`template:minimal_gray`
- `tools/sie_autoppt/cli.py`
  - V2 CLI 明确拒绝 `--template`
  - V2 规划上下文若带 `template`，会直接退出并提示 “V2 workflows do not support PPTX templates”

### 问题本质

前置澄清层允许用户朝 legacy 模板方向回答，但后续主执行链路是 V2-only。  
这会形成典型的“前面能选，后面不能跑”的产品错配。

### 影响

- 新用户会误以为模板是当前主能力。
- 澄清结果无法稳定映射到推荐工作流。
- 后续如果接入 Web clarifier，这类错配会更明显。

### 解决方案

**推荐方案 A：收敛为 V2-only**

- 从 `clarifier.py` 中移除 `template:*` 选项。
- 把 `template_theme` 改名为 `theme`，避免继续混合旧术语。
- 在澄清消息中只暴露 V2 themes。

**备选方案 B：显式双轨**

- 保留 `template:*`，但必须在 CLI 中增加独立 legacy 入口。
- 文档明确写成：
  - `theme:*` -> V2 主路径
  - `template:*` -> 兼容路径，不保证新功能覆盖

当前更建议方案 A。

---

## 3.2 P1：仓库仍在同时讲两套故事，文档和工具链存在明显的 legacy 残留

### 证据

- `README.md`
  - 仍使用“模板驱动渲染”表述。
- `docs/TESTING.md`
  - 把 `legacy_html_regression_check.ps1` 放在推荐测试分类中。
- `prompts/system/default.md`
  - 仍写着 `template-driven renderer`。
- `tools/prepare_visual_review.py`
  - 仍保留 `--template` 参数。
- `tools/README.md`、`docs/COMPATIBILITY.md`、`docs/RELEASE_CHECKLIST.md`
  - 仍把 legacy 回归入口暴露为常规项目动作。

### 问题本质

当前项目对外已经是 V2-first，但仓库内部仍把一部分 legacy 子系统当作“并列主路径”在描述。  
这不是代码不能运行的问题，而是**边界定义不清**的问题。

### 影响

- 新人 onboarding 成本高。
- 文档维护会反复漂移。
- 用户很难判断哪些入口是主路径、哪些只是兼容保留。
- 测试与发布 checklist 会被兼容层绑架。

### 解决方案

**推荐方案：做一次“路径分层”清理**

1. 在 `README.md`、`docs/README.md`、`docs/TESTING.md` 中明确三层：
   - 主路径：`demo / make / review / iterate / v2-*`
   - 兼容路径：legacy HTML / template
   - 实验或内部工具：辅助脚本、迁移脚本、导入脚本
2. 把 legacy 文档集中到单独分组，例如：
   - `docs/legacy/`
   - 或 `docs/compatibility/legacy-*`
3. 在主入口文档中只保留一句兼容说明，不再展开 legacy 操作细节。
4. 把 `prepare_visual_review.py` 这类内部工具在文档中标成“internal tool”。

---

## 3.3 P1：legacy 兼容子系统仍然活着，但没有被明确隔离成“边缘模块”

### 证据

- `tools/sie_autoppt/generator.py`
  - 仍维护 template manifest、slide pool、legacy clone 路径。
- `tools/sie_autoppt/planning/deck_planner.py`
  - 仍保留 `build_legacy_page_specs`。
- `tools/sie_autoppt/structure_service.py`
  - 仍维护独立结构生成链路。
- 测试中仍有：
  - `tests/test_structure_service.py`
  - `tests/test_deck_planner.py`

### 问题本质

这说明 legacy 不是“死代码”，而是**仍在兼容职责范围内**。  
真正的问题不是要不要立刻删除，而是它当前没有被组织成一个清晰的边界。

### 影响

- 主系统演进时，很容易同时背上兼容层负担。
- 文档和代码读者不容易判断哪些模块可以自由重构，哪些不能。
- 每次改 CLI、澄清器或输入规范时，都会被 legacy 语义牵连。

### 解决方案

**推荐方案：隔离，而不是马上硬删**

1. 在目录和文档层明确标注：
   - `v2/` 为主产品线
   - `legacy/` 或 `compat/` 为兼容线
2. 为 legacy 模块单独写一页边界文档：
   - 仍支持什么
   - 不再新增什么
   - 哪些测试必须保留
3. 未来新增功能默认只允许进入 V2。
4. 如果 1-2 个版本后不再需要兼容，再做彻底删除。

---

## 3.4 P2：自动化测试强，但“真实模型 + 真实输出质量”的验证仍偏弱

### 证据

- `pytest -q` 当前为 `226 passed`，说明代码层回归良好。
- 但 `tests/test_llm_openai.py`、`tests/test_healthcheck.py` 主要是 mocked / patched 测试。
- `tools/sie_autoppt/healthcheck.py` 只验证：
  - 配置可加载
  - outline 可生成
  - deck 可生成
  - 不包含最终渲染与视觉复核

### 问题本质

当前测试更擅长回答“代码接口是否工作”，但不擅长回答：

- 某个真实模型是否仍能稳定产出合格结构
- 某个代理网关是否会突然改变 JSON 兼容性
- 某类真实业务主题是否会生成“结构对但内容空”的 deck

### 影响

- 代码稳定不代表产品质量稳定。
- 更换模型、代理、base URL 后，风险主要会出现在集成层和内容层。
- `ai-check` 名称容易让人误以为它覆盖了完整交付链路。

### 解决方案

**推荐方案：增加一层“真实 AI 小样本回归”**

1. 新增 `ai-e2e` 或 `v2-smoke-live`：
   - 跑 2-3 个固定主题
   - 生成 outline / semantic deck / compiled deck / pptx
   - 输出质量门禁摘要
2. 把这类回归标记为：
   - 非默认
   - 需要 API key
   - 发布前或模型切换前执行
3. 扩展 `ai-check`：
   - 增加可选参数 `--with-render`
   - 或新增 `--with-review`
4. 建立一套最小黄金样例：
   - 经营汇报
   - 解决方案提案
   - 行业分析

---

## 3.5 P2：视觉复核依赖外部桌面软件，环境差异会直接影响评审可信度

### 证据

- `tools/sie_autoppt/v2/visual_review.py`
  - Windows 依赖 PowerPoint COM 导出 PNG
  - 其他环境依赖 `soffice`
  - 如果拿不到预览图，会退化成基于 deck 内容的 review，并明确提示可靠性下降

### 问题本质

视觉复核并不是纯 Python、自包含链路，而是**部分依赖宿主机桌面能力**。  
这在本机开发时可接受，但在 CI、服务器、容器环境里会变成稳定性变量。

### 影响

- 同一份 deck，在不同机器上 review 质量不同。
- “通过 review” 不等于真的看过页面图像。
- 远程环境或无 Office 环境下，布局判断能力会明显下降。

### 解决方案

1. 在 `docs/TESTING.md` 和 `docs/HUMAN_VISUAL_QA.md` 中把该依赖写成显式前置条件。
2. review 输出里单独增加一个字段，例如：
   - `preview_mode: powerpoint|soffice|content_only`
3. CI 中默认只跑 content-only review，不把它当作最终视觉验收。
4. 如果后续要做稳定自动化视觉回归，考虑固定统一预览渲染环境。

---

## 3.6 P3：缺少显式协作规则文件，文档漂移问题还会重复出现

### 证据

- 当前仓库没有 `CONTRIBUTING.md`。
- 但项目已经出现过：
  - CLI 主路径变化
  - legacy 命令下线
  - 文档与代码不一致的历史问题

### 问题本质

不是技术难题，而是**协作约束未落盘**。

### 影响

- 命令变了，文档未必同步。
- 新增脚本和兼容入口时，容易再次侵入主入口文档。
- 维护者对“哪些变更必须补测试 / 补文档”没有统一约束。

### 解决方案

新增一个简短的 `CONTRIBUTING.md`，至少写清：

- 改 CLI 时必须同步更新 `README.md` 和 `docs/CLI_REFERENCE.md`
- 新增用户入口时必须补测试
- legacy 兼容改动不得默认进入主入口文档
- 发布前必须跑：
  - `pytest -q`
  - `python .\main.py demo`
  - 必要时 `tools/v2_regression_check.ps1`

---

## 4. 不是问题、但需要明确认知的点

以下内容不应再被当作“缺陷”写进新报告：

- `clarify_web.py` 缺失：**已修复**
- `python main.py --help` 启动崩溃：**当前不存在**
- V2 没有深度模式：**当前不存在**
- `anti_argument` / `data_sources` 未落地：**当前不存在**
- 没有开箱即用 demo：**当前不存在**

换句话说，当前项目的诊断不能再沿用旧版“工程止血期”的叙事。

---

## 5. 分阶段整改建议

## Phase 1：一周内可完成的收敛项

目标：让对外主路径和对内描述一致。

1. 从澄清器中移除 `template:*` 选项，或显式切到单独 legacy 路径。
2. 重写 `README.md` 的流程图和“当前能力”描述，避免继续把主流程写成 template-driven。
3. 重写 `docs/TESTING.md` 的结构：
   - 默认测试只保留 V2 主链路
   - legacy 回归移到兼容章节
4. 新增 `CONTRIBUTING.md`。

## Phase 2：两周内补齐的质量保障

目标：让“代码通过”更接近“产品可交付”。

1. 增加真实 LLM 小样本回归命令。
2. 扩展 `ai-check`，可选包含 render / review。
3. 为 review 结果增加 `preview_mode`。
4. 建立最小黄金案例集。

## Phase 3：中期架构治理

目标：把兼容层从主系统认知中剥离。

1. 把 legacy 模块显式隔离到单独目录或单独文档域。
2. 对兼容层做“支持边界声明”。
3. 决策：
   - 继续保留兼容层
   - 冻结兼容层
   - 分版本逐步删除兼容层

---

## 6. 推荐决策

### 决策 1：当前产品主线是否继续坚持 V2-only

**建议：是。**

理由：

- 当前 V2 主链路已经可用、可测、可演进。
- 继续混合 legacy 表面能力，只会增加协作噪音。

### 决策 2：legacy 兼容层是“继续建设”还是“仅维持”

**建议：仅维持，不再扩展。**

理由：

- 现阶段主要价值在于兼容历史输入，而不是作为新能力承载点。
- 新功能应全部落在 V2。

### 决策 3：下一阶段优先级放哪里

**建议顺序：**

1. 收敛澄清器和文档
2. 补真实 AI 回归
3. 隔离 legacy 兼容层

---

## 7. 结论

这套系统现在的真实状态是：

**主产品线已经站住，但仓库边界还没完全收干净。**

如果继续沿用旧报告那种“先止血”的判断，会低估当前进展；  
如果因为测试全绿就认为问题已经解决，也会低估 legacy 残留和真实内容质量验证的风险。

最合适的下一步，不是大改架构，而是做一次明确的产品面收敛：

- 统一主路径
- 隔离兼容层
- 补齐真实 AI 回归

这三件事做完后，这个项目才算真正从“能跑”进入“可持续交付”。
