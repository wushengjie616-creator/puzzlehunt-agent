---
id: P0001
title: Puzzle 解题 Agent MVP
status: in_progress
created_at: 2026-08-28
mode: review
paired_task: T0001
related_docs: []
evidence:
  - "haiknow task preflight --root $PWD --intent new-task => baseline_decision use-current; decision_reason non-git-project"
  - "项目根仅有 .haiknow.yml；不存在既有代码、测试入口或 durable owner"
  - "DeepSeek 官方文档当前给出 OpenAI 兼容 Chat Completions、base_url=https://api.deepseek.com，并支持 JSON Output"
---

# P0001 · Puzzle 解题 Agent MVP

> **触发**：用户希望制作一个根据标题、风味文本和题目内容推理答案的 puzzle agent，内置常用密码转换能力，记录 agent 框架学习过程，通过 DeepSeek 官方 API 完成单次语言对话，并提供可测试体验方式。
> **模式**：review
>
> <!-- 一旦执行此 plan 即冻结；偏差只写到对应 task 的“与计划的偏差”章节，不回改本 plan -->

## 1. 背景 / evidence

当前项目是一个已启用 HAiKnow、但尚无实现的非 Git 空项目。不存在需要兼容的运行时、接口或测试框架，因此本计划拥有首版架构边界。

DeepSeek 官方 API 当前提供 OpenAI 兼容的 Chat Completions 接口。严格的“每次解题只发起一次模型请求”与经典 ReAct 工具循环存在结构性冲突：ReAct 至少需要一次模型工具请求和一次携带工具结果的后续请求。因此 MVP 将确定性密码分析前置到本地，再把候选结果和原题一次性提交给 DeepSeek。

### 1.1 已确认与假设

| 状态 | 前提 | 影响 |
|---|---|---|
| confirmed | 单次解题只调用一次 DeepSeek Chat Completions | 用请求计数测试锁定；不实现模型驱动的多轮工具循环 |
| confirmed | 输入包含标题、风味文本、题目内容 | 建立稳定的 `PuzzleInput` 数据契约 |
| confirmed | 密码转换需要可复用、可独立验证 | 作为纯函数工具库，并由项目本地 skill 薄封装 |
| assumption | 首版输入以文本为主，不处理图片、PDF、音频 | 多模态/OCR 明确列为非目标 |
| assumption | 默认中文界面与中文分析，题目可含英文 | prompt 保留原文并要求识别跨语言线索 |
| confirmed | 体验入口只采用 CLI | 用户选择减少依赖，不实现 Web UI |

## 2. 目标与非目标

### 2.1 目标

1. 接收结构化的标题、风味文本、题目正文，以及可选备注。
2. 在本地、无模型调用的条件下生成受预算约束的常见密码/编码候选。
3. 将原题、候选、解题方法约束组装成一次请求，调用 DeepSeek 官方 API。
4. 返回结构化结果：候选答案、置信度、关键证据、推理摘要、已尝试方法、仍缺信息。
5. 提供 CLI、离线示例与自动测试；无 API Key 时仍可体验数据流和密码工作台。
6. 用学习文档持续记录采用的架构模式、被拒方案、取舍和升级条件。

### 2.2 非目标

- 不在 MVP 中做多轮自主规划、人工确认回合、联网搜索或动态工具调用。
- 不支持图片识别、版式定位、音频、文件上传和团队题库。
- 不承诺一次调用必然解出所有 puzzle；结果必须允许 `unknown`，不得伪造确定答案。
- 不把 Codex `SKILL.md` 当作 DeepSeek 运行时能力；实际 agent 使用 Python 密码工具库。skill 只作为开发者/Codex 可复用入口。

## 3. 方案比较与选择

### 3.1 推荐：本地预处理 + 单次模型推理

数据流：

```text
PuzzleInput
  -> 文本规范化与特征探测
  -> 密码候选工作台（纯本地、有限预算）
  -> PromptBuilder
  -> DeepSeekClient（恰好一次请求）
  -> 结构化 SolveResult
  -> CLI 展示
```

采用的常见模式：

- **Pipeline**：每阶段有清晰输入输出，便于单测和替换。
- **Ports and Adapters / Hexagonal**：领域解题流程不依赖 UI 或具体 API SDK；DeepSeek、假客户端、CLI、Web UI 都是适配器。
- **Strategy + Registry**：每种密码转换是一个策略，由注册表选择和限额执行。
- **Structured Output**：使用 JSON Output，并在 prompt 中显式要求 JSON；应用层再做 schema 校验和一次本地容错解析。
- **Dependency Injection**：测试注入 Fake LLM，证明核心流程无网络可测，并断言每次 solve 最多调用一次 provider。

不采用完整 agent 框架。首版以 Python 标准库 HTTPS 客户端直接调用官方 OpenAI 兼容端点，避免 LangChain/PydanticAI 和额外 SDK 在单节点单请求场景增加依赖与调试面。这里的“agent”指拥有目标、领域策略、工具预处理和结构化决策输出的受约束 agent，而非无限自治循环。

### 3.2 替代：LangChain/PydanticAI 工具 Agent

优点是工具声明、追踪和未来多轮扩展更现成；缺点是典型 tool calling 需要多次 API 往返，违背当前单次请求约束。若未来允许多轮、需要模型主动选择参数化工具，再评估引入。

### 3.3 替代：纯 Prompt 单请求

依赖最少，但 Base 编码、凯撒枚举、摩斯等确定性任务交给模型既浪费 token，又难以稳定回归。仅适合极小 demo，不作为 MVP 架构。

## 4. 运行时设计

### 4.1 数据契约

`PuzzleInput`：

- `title: str`
- `flavor_text: str`
- `content: str`
- `notes: str | None`

`CipherCandidate`：

- `method`、`source_segment`、`parameters`、`output`、`score`、`warnings`

`SolveResult`：

- `answer: str | null`
- `confidence: low | medium | high`
- `reasoning_summary: list[str]`
- `key_evidence: list[str]`
- `methods_tried: list[str]`
- `alternatives: list[object]`
- `missing_information: list[str]`

应用只展示可审查的解题摘要与证据，不依赖或承诺暴露模型私有思维链。

### 4.2 密码工作台

首批实现并单测：

- Caesar/ROT 全移位、ROT13、Atbash
- Base16/Base32/Base64
- 二进制/十六进制到文本
- Morse
- A1Z26（含常见分隔符）
- 字符串反转、奇偶位拆分
- 首字母/尾字母提取、逐行索引辅助
- Vigenere（仅当用户备注或题面提供候选 key，避免无界爆破）
- Rail Fence（限制合理层数）

所有策略遵守候选数、单候选长度和总字符预算。候选通过可打印比例、语言特征、重复/去重规则排序；低质量候选保留统计而不全部灌入 prompt。

项目本地 `.agents/skills/puzzle-cipher-workbench/` 提供简短 `SKILL.md`，其脚本调用同一运行时工具库，避免维护两份算法实现。

### 4.3 DeepSeek 适配器

- 只使用 Python 标准库实现 HTTPS 请求，保持零第三方运行时依赖。
- 从 `DEEPSEEK_API_KEY` 读取密钥，禁止写入仓库或默认日志。
- `base_url` 默认 `https://api.deepseek.com`，允许环境变量覆盖以便测试。
- 模型名配置化；实现时根据官方当前模型设置默认值，不在领域层硬编码。
- 非流式调用，默认开启 thinking，并配置 reasoning effort；UI 不依赖供应商专有 reasoning 字段。
- 使用 `response_format={"type":"json_object"}`，prompt 同时明确 JSON schema 要求。
- 设置超时、最大输出 token；错误分为认证、限流、网络、供应商响应、结构校验，不自动发起第二次模型请求。
- 每次 `solve()` 恰好零或一次外部请求：输入校验失败为零次，进入 provider 后为一次；失败直接返回可操作错误。

### 4.4 Prompt 设计

系统提示要求模型：

1. 联合使用标题、风味文本、正文，区分线索与装饰。
2. 先形成多个假设，再用证据排除；不得因某个解码结果“像单词”就直接定案。
3. 密码候选只是工具证据，可能是假阳性。
4. 找不到充分证据时返回 `answer=null` 和所缺信息。
5. 只输出约定 JSON；推理字段只给可复核摘要，不索取隐式思维链。

## 5. 项目结构与交付拆分

```text
pyproject.toml
.env.example
README.md
src/puzzle_agent/
  domain.py
  cipher_workbench.py
  prompt.py
  solver.py
  providers/deepseek.py
  cli.py
examples/
  sample_puzzle.json
tests/
  test_ciphers.py
  test_prompt.py
  test_solver.py
  test_cli.py
  test_deepseek_contract.py
.agents/skills/puzzle-cipher-workbench/
  SKILL.md
  scripts/analyze.py
haiknow-doc/docs/
  index-by-topic.md
  01-puzzle-agent-architecture.md
  02-agent-design-journey.md
```

实施阶段：

1. 建 Python 包、数据契约和可运行测试入口。
2. 以测试先行实现密码策略、排序和预算。
3. 实现 prompt、solver 与 Fake provider，锁定单请求不变量。
4. 实现 DeepSeek 适配器与 opt-in API smoke test。
5. 实现 CLI、示例题和离线演示。
6. 创建项目本地 skill，验证脚本和 skill metadata。
7. 补齐 README、架构当前文档与设计学习日志，运行 fresh verification。

## 6. Contract impact map

| 维度 | 结果 |
|---|---|
| canonical SSOT | `domain.py` 的输入/输出模型；`solver.py` 的单请求流程；架构 living doc 解释契约 |
| active consumers | DeepSeek adapter、Fake provider、CLI、tests、skill script |
| templates / generators | 无代码生成器；示例 JSON 与 `.env.example` 消费公开字段 |
| mechanical checks | schema round-trip、provider call-count、cipher vectors、CLI smoke、offline UI import、opt-in live API smoke |
| historical snapshots | 本 draft 获批后冻结；实施偏差写配对 task，不回改 plan |
| repo-wide search terms | `PuzzleInput|SolveResult|solve\(|DEEPSEEK_|chat.completions|response_format|cipher` |

## 7. 验证方式

- `python -m pytest`：离线单元/集成测试全部通过。
- `python -m puzzle_agent.cli solve --file examples/sample_puzzle.json --offline`：无需密钥即可展示完整流程。
- `python -m puzzle_agent.cli ciphers --text ...`：独立体验密码工具。
- `RUN_DEEPSEEK_SMOKE=1 python -m pytest -m live`：用户显式开启后进行一次真实、可能计费的 API 冒烟测试。
- skill-creator 的 `quick_validate.py`：验证项目本地 skill 结构；其脚本用已知密码向量实跑。

## 8. 风险与控制

- **单次请求限制解题能力**：用本地预处理提高信息密度；未来若放宽约束，再升级模型选工具循环。
- **候选爆炸/token 成本**：严格预算、排序、去重，prompt 中只放高质量候选和摘要。
- **误解题与假阳性**：结构化输出包含证据、替代答案和缺失信息；不强迫给答案。
- **官方模型/API 漂移**：provider 配置化，契约测试隔离；README 链接官方资料并记录核验日期。
- **密钥泄露**：只读环境变量；`.env` 忽略；异常与日志不包含密钥。
- **真实 API 测试产生费用**：默认跳过，只有显式环境开关才运行。

## 9. 验收标准

- [ ] 给定完整三段输入，离线 pipeline 能生成密码候选和固定格式的模拟解题结果。
- [ ] 配置有效 API Key 后，每次求解只产生一次 DeepSeek 请求并得到可校验结构化结果。
- [ ] 至少覆盖 10 类常用转换，具备已知向量、异常输入和预算边界测试。
- [ ] CLI 可体验离线与真实 API 两种模式；未配置 Key 时给出清晰指引且不崩溃。
- [ ] Fake provider 测试证明成功、API 错误、非法 JSON、超时路径和 call-count 不变量。
- [ ] skill 能被验证并复用同一密码实现，无算法分叉。
- [ ] README 与两份 living docs 能回答：怎么运行、采用了什么框架模式、为何不选完整 agent 框架、何时升级。

## 10. 已确认决策

用户选择 **纯 CLI + 静态示例**，以减少依赖；MVP 不实现 Web UI，并进一步采用 Python 标准库 HTTP 客户端保持零第三方运行时依赖。
