# LLM 兼容性说明（增补）

## Visual Review Provider Switching

`review` / `iterate` 支持：

- `--vision-provider auto`（默认，按模型自动判断）
- `--vision-provider openai`
- `--vision-provider claude`

示例：

```powershell
python .\main.py review --deck-json .\output\generated_deck.json --vision-provider claude --llm-model claude-3-7-sonnet-latest
```

### Claude Vision 必需环境变量

```powershell
$env:ANTHROPIC_API_KEY="your-anthropic-key"
# 可选
$env:ANTHROPIC_BASE_URL="https://api.anthropic.com/v1"
```

---
# LLM 兼容性指南

## 概述

SIE AutoPPT 的 AI 规划功能支持多种 LLM 提供商和模型。本文档说明如何配置不同的模型，以及已知的兼容性问题。

## 支持的 API 风格

### 1. OpenAI Responses API（推荐）

**适用场景：** OpenAI 官方 API、OpenRouter

**配置示例：**
```bash
export OPENAI_API_KEY="sk-..."
export OPENAI_BASE_URL="https://api.openai.com/v1"
export SIE_AUTOPPT_LLM_MODEL="gpt-4o-mini"
```

说明：
- 默认不强制本地 `OPENAI_API_KEY`（便于 Codex/Claude Code/网关注入鉴权场景）。
- 若你的上游端点要求显式 key，请自行设置 `OPENAI_API_KEY`。
- 若你要恢复“必须有 key”策略，可设置 `SIE_AUTOPPT_REQUIRE_API_KEY=1`。

**特点：**
- 支持 JSON Schema strict mode
- 支持 reasoning effort 和 text verbosity 控制
- 最佳的结构化输出质量

### 2. Chat Completions API

**适用场景：** 国内模型提供商（SiliconFlow、智谱、百川等）

**配置示例：**
```bash
export OPENAI_API_KEY="sk-..."
export OPENAI_BASE_URL="https://api.siliconflow.cn/v1"
export SIE_AUTOPPT_LLM_MODEL="deepseek-ai/DeepSeek-V3"
export SIE_AUTOPPT_LLM_API_STYLE="chat_completions"
```

**特点：**
- 使用 `response_format: {"type": "json_object"}` 而非 JSON Schema
- 不保证严格的 schema 遵从
- 需要在 prompt 中明确要求 JSON 格式

## 国内模型兼容性

### SiliconFlow + DeepSeek-V3

**状态：** ✅ 基本可用，但需注意以下问题

**已知问题：**
1. **JSON Schema 支持不完整**
   - DeepSeek-V3 的 `response_format: json_object` 不保证严格遵从 schema
   - 可能返回额外字段或缺少必需字段
   - 建议在生产环境中增加额外的 JSON 验证

2. **字段类型不稳定**
   - `bullets` 数组可能包含非字符串元素
   - `pattern_id` 可能返回不在枚举列表中的值
   - 代码已通过 `normalize_ai_bullets()` 和 `normalize_ai_pattern_id()` 处理这些情况

**推荐配置：**
```bash
export OPENAI_BASE_URL="https://api.siliconflow.cn/v1"
export SIE_AUTOPPT_LLM_MODEL="deepseek-ai/DeepSeek-V3"
export SIE_AUTOPPT_LLM_API_STYLE="chat_completions"
export SIE_AUTOPPT_LLM_TIMEOUT_SEC="120"  # 国内网络可能需要更长超时
```

### 其他国内模型

**智谱 GLM-4：**
```bash
export OPENAI_BASE_URL="https://open.bigmodel.cn/api/paas/v4"
export SIE_AUTOPPT_LLM_MODEL="glm-4"
```

**百川 Baichuan-4：**
```bash
export OPENAI_BASE_URL="https://api.baichuan-ai.com/v1"
export SIE_AUTOPPT_LLM_MODEL="Baichuan4"
```

**注意：** 这些模型的 JSON 输出质量未经充分测试，建议先在测试环境验证。

## 网络环境配置

### 中国大陆企业环境

**问题：** 直连 OpenAI API 通常不可行

**解决方案：**

1. **使用国内代理服务（推荐）**
   ```bash
   export OPENAI_BASE_URL="https://api.siliconflow.cn/v1"
   ```

2. **使用企业代理**
   ```bash
   export HTTPS_PROXY="http://proxy.company.com:8080"
   export OPENAI_BASE_URL="https://api.openai.com/v1"
   ```

3. **使用 OpenRouter（需要稳定国际网络）**
   ```bash
   export OPENAI_BASE_URL="https://openrouter.ai/api/v1"
   export OPENAI_API_KEY="sk-or-..."
   ```

### 超时和重试

代码已实现基础重试机制：
- 自动重试 HTTP 429, 500, 502, 503, 504 错误
- 自动重试网络连接错误
- 最多重试 3 次

如果网络不稳定，可以增加超时时间：
```bash
export SIE_AUTOPPT_LLM_TIMEOUT_SEC="180"
```

## 验证模型兼容性

### 运行 AI 健康检查

```bash
python .\main.py ai-check --topic "测试主题"
```

**成功输出示例：**
```json
{
  "status": "ok",
  "model": "deepseek-ai/DeepSeek-V3",
  "base_url": "https://api.siliconflow.cn/v1",
  "api_style": "chat_completions",
  "topic": "测试主题",
  "cover_title": "测试主题方案",
  "page_count": 3,
  "first_page_title": "现状与挑战"
}
```

### 运行真实 AI smoke test

日常 `pytest` 默认不会调用真实模型；如需做一次小样本端到端验证，可执行：

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\run_real_ai_smoke.ps1
```

如需更接近正式交付链路：

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\run_real_ai_smoke.ps1 -GenerationMode deep -WithRender
```

建议：

- 默认先跑 `quick`，它已经能覆盖真实模型的 outline/deck 生成。
- 只有在排查渲染或本机依赖问题时，再加 `-WithRender`。
- 真实 smoke test 应只作为补充质量门，不替代常规单元测试和 V2 deck 回归。

### 常见错误诊断

**错误：`OPENAI_API_KEY is required`**
- 仅在你显式启用 `SIE_AUTOPPT_REQUIRE_API_KEY=1` 时会出现。
- 处理方式：设置 `OPENAI_API_KEY`，或关闭 `SIE_AUTOPPT_REQUIRE_API_KEY`，或改用 localhost 网关。

**错误：`401 Unauthorized` / `invalid_api_key`**
- 这通常表示上游服务需要鉴权，但当前请求没有有效凭据。
- 若你不是走“平台自动注入鉴权”，请设置 `OPENAI_API_KEY`。
- 若你在 Codex/Claude Code/代理网关环境，确认 `OPENAI_BASE_URL` 指向正确的可鉴权入口。

**错误：`Responses API quota exceeded`**
- API key 余额不足或配额用尽
- 检查平台账单和项目配额

**错误：`Responses API returned non-JSON text`**
- 模型不支持 JSON 输出
- 尝试切换到 `chat_completions` API 风格

**错误：`AI planner returned X body pages, expected Y`**
- 模型未遵守页数约束
- 检查 prompt 是否正确传递
- 考虑使用更强的模型（如 GPT-4）

## 生产环境建议

### 模型选择

**国际环境：**
- 首选：`gpt-4o-mini`（性价比高）
- 备选：`gpt-4o`（质量最高）

**中国大陆环境：**
- 首选：`deepseek-ai/DeepSeek-V3` via SiliconFlow
- 备选：`glm-4` via 智谱 AI

### 监控和日志

建议监控以下指标：
- AI 调用成功率
- 平均响应时间
- JSON schema 验证失败率
- Pattern 归一化触发率

### 降级策略

如果 AI 规划失败，可以：
1. 回退到现成的 deck JSON 或 outline JSON
2. 使用仓库内置 `demo` 命令先验证渲染链路
3. 必要时再定位 legacy HTML 兼容路径是否单独失效

## 测试覆盖

当前测试覆盖：
- ✅ OpenAI Responses API mock 测试
- ✅ Chat Completions API mock 测试
- ✅ JSON 解析和归一化
- ✅ OpenAI / Chat Completions 兼容接入
- ✅ 真实模型 smoke test 可通过 `tools/run_real_ai_smoke.ps1` 手动执行

运行测试：
```bash
python -m pytest tests/test_v2_services.py -v
python -m pytest tests/test_llm_openai.py -v
```

## 更新日志

**2026-04-05：**
- 添加 HTTP 重试机制（429, 5xx 错误）
- 添加网络连接错误重试
- 完善 DeepSeek-V3 兼容性说明
- 添加国内模型配置示例

