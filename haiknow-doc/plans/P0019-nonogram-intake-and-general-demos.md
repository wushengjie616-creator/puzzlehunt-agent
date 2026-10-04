---
id: P0019
title: 数织提交链路修复与三道普通谜题演示
status: completed
created_at: 2026-10-04
plan_completed_at: 2026-10-04
paired_task: T0018
acceptance_contract: v1
related_docs:
  - ../docs/01-puzzle-agent-architecture.md
  - ../docs/02-agent-design-journey.md
  - ../docs/03-ccbc16-24-case-solution-guide.md
  - P0015-ccbc-reasoning-operationalization.md
  - P0017-newcomer-readme-and-document-index.md
evidence:
  - "项目根存在含 DEEPSEEK_* 键的 .env，但不存在 .env.local；src/puzzle_agent/config.py 当前只读取 .env.local"
  - "前端选择数织时会向 /api/intakes 发送 preferred_kind=nonogram，后端也会把该值传给 normalizer"
  - "用户要求修复手动提交数织的 DeepSeek 解析，并新增三道 CCBC 风格、处于当前 Agent 能力范围内的普通谜题"
---

# P0019 · 数织提交链路修复与三道普通谜题演示

> 用户已明确要求开始两个任务，按 skip-review 执行。
>
> <!-- 一旦执行此 plan 即冻结；偏差只写到 T0018 的“与计划的偏差”章节，不回改本 plan -->

## 1. 背景 / evidence

当前产品契约要求文字与图片入口都先经过 DeepSeek。现有前端和 `/api/intakes` 已正确携带 `preferred_kind=nonogram`；可复现的启动差异是用户配置写在项目根 `.env`，而启动代码只加载 `.env.local`，导致没有外部 shell 注入时 DeepSeek 被判为未配置。

修复后还需用真实数织图片走一次 `提交 → DeepSeek → READY_FOR_CONFIRMATION`，避免 fake normalizer 测试掩盖模型或响应格式的第二层问题。

三道普通谜题不复刻 CCBC 原题或答案，只吸收其“表面属性第二信道、中间答案仍是载体、排序与提取分层、异常必须全局验证”等机制。每题必须能映射到现有 ToolRegistry，且以独立 oracle 验证中间物和答案。

## 2. 范围 / 方案

| # | 项 | 文件 | 改动 |
|---|---|---|---|
| 1 | 配置基线 | `config.py`、Web 测试 | 让 `.env` 成为默认配置，`.env.local` 可覆盖；进程环境仍保持最高优先级 |
| 2 | 数织真实链路 | normalizer/Web 测试与必要实现 | 锁定 `preferred_kind=nonogram`、图片输入、模型响应校验及可诊断错误 |
| 3 | 三道普通谜题 | `examples/general-puzzle-demos/` | 新增原创题面、可上传图片、输入文本、oracle、工具轨迹、walkthrough 与 manifest |
| 4 | 演示导航 | README、examples 索引、文档索引 | 说明三题适用能力、演示步骤与真实模型/确定性证据边界 |
| 5 | 回归合同 | `tests/` | 验证配置优先级、数织真实入口的可替换边界、三题工具轨迹与资源完整性 |

### 2.1 Contract impact map

| 维度 | 结果 |
|---|---|
| canonical SSOT | `load_env_local` 的配置加载语义；普通谜题工具真相源为 `ToolRegistry` |
| active consumers | Web normalizer、复杂 Agent provider、README 启动说明、`.env.example` |
| templates / generators | 三题图片生成器；不修改历史 benchmark generator |
| mechanical checks | config/Web API 测试、普通谜题 demo contract、文档链接测试 |
| historical snapshots（明确不改） | 已 completed 的 P0009/T0008 与旧任务证据不回写 |
| repo-wide search terms | `.env.local`、`load_env_local`、`DEEPSEEK_API_KEY`、`preferred_kind`、`nonogram`、`general-puzzle-demos` |

## 3. 验证方式

1. RED：新增配置回归测试，证明仅存在 `.env` 时当前 Web 仍显示未配置。
2. GREEN：聚焦 config/Web/normalizer suite 通过，并验证 `.env.local` 与进程环境优先级。
3. 使用仓库 10×10 数织图片，经真实本地 Web API 提交，确认至少进入 `READY_FOR_CONFIRMATION` 且 kind 为 `nonogram`；若外部服务不可达，保留精确 blocker，不以 fake provider 代替该结论。
4. 每道普通谜题用现有 ToolRegistry 重算固定轨迹，逐项核对中间物、答案、线索消费与工具参数。
5. 生成并人工检查三张题图；运行文档链接、相关 suite、全量测试、mutation probe 与 HAiKnow 文档门禁。

## 🔴 红线 / 风险

- `.env` 和 `.env.local` 均不得提交；测试只写临时目录和假 key。
- 真实 DeepSeek 验证限定为数织链路的最少调用，不运行批量 benchmark。
- CCBC 材料只作为机制研究来源；不复制题面、答案或受版权保护的完整解析。
- 不扩大 ToolRegistry 或承诺当前 Agent 不具备的视觉拼合、开放知识库或大型 CSP 能力。
- 当前工作树含上一轮未提交改动；本任务在原地追加，不提交、不 reset、不覆盖。

## 4. 验收标准

| ID | 必需 | 适用范围 | 可观察结果 |
|---|---|---|---|
| A01 | yes | source | 项目仅配置 `.env` 时，Web bootstrap 报告 DeepSeek configured=true |
| A02 | yes | source | 配置优先级为进程环境 > `.env.local` > `.env`，且不泄露 key |
| A03 | yes | external | 10×10 数织图片通过真实 `/api/intakes` 链路得到 `READY_FOR_CONFIRMATION`、kind=nonogram 和合法行列线索 |
| A04 | yes | source | 三道原创普通谜题分别包含题面、图片、oracle、工具轨迹和讲解，且机制不互为简单换皮 |
| A05 | yes | source | 三题全部只调用当前 ToolRegistry 已注册工具，确定性轨迹重算与独立 oracle 一致 |
| A06 | yes | source | 每题 walkthrough 清楚分开观察、假设、工具验证、中间物、提取与终局核验 |
| A07 | yes | source | README/示例索引能让运营同事按步骤演示三题，并标明真实 DeepSeek 与离线证据边界 |
| A08 | yes | source | 聚焦测试、全量回归、mutation probe、图片视觉检查和文档门禁通过 |

## 5. 成稿自审记录

- 日期 / 审核者：2026-10-04 / 主 Agent 自审
- 实际上下文 / 能力降级原因（如有）：当前策略禁止主动委派子 Agent，因此使用同一 Agent 从落盘文件完整重读；不声称独立审核。
- 被审版本：P0019 初稿正文，排除本自审记录本身。
- 维度结论 / 证据：意图覆盖用户两个目标；配置根因由 `.env`/`.env.local` 文件事实与调用链支撑；三题限制在现有工具；外部真实调用单独标识；不提交密钥或未经授权提交 Git。
- 完整 findings / 处理 / 修订后复核：发现 preflight 因上一轮未提交工作返回 stop-and-ask；用户本轮已明确要求开始，方案改为原地保留并在 task 记录偏差。发现真实调用可能受网络/模型端约束，因此 A03 保留 external 身份，禁止用 fake 测试冒充。
- 最终结论 / 剩余 blocker / 局限：成稿无实施 blocker；真实 DeepSeek 结果只有实际调用后才能判定，失败时必须如实保留外部 blocker。
