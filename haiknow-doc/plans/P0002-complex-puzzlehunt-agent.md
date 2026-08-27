---
id: P0002
title: 可复用 PuzzleHunt 多阶段解题 Agent
status: completed
created_at: 2026-08-28
plan_completed_at: 2026-08-28
paired_task: T0002
related_docs:
  - ../docs/01-puzzle-agent-architecture.md
  - ../docs/02-agent-design-journey.md
evidence:
  - "现有 P0001 是单次请求、文本输入、无持久 session 的 MVP；src/puzzle_agent/solver.py 每次 solve 恰好调用 provider 一次"
  - "CCBC16 官方数据覆盖普通题、分区 meta、交互题和最终 meta；抽查题目 5/13/29/32/42/47/55 后归纳出映射、联想图、异构子题、逆向提取、递归 meta、机制复用和约束组合"
  - "用户确认 CCBC16 仅作为离线学习材料，必须由项目自行构造派生测试集，不把官方题面或题解直接交给 DeepSeek"
  - "用户确认复杂模式必须按流程进行多次推理；每次 DeepSeek API 交互仍是独立的单轮请求"
  - "DeepSeek 官方 API 当前不支持 image/file input；V4 Pro/Flash 的 Chat Completions 为 text-only"
  - "LangGraph 官方将 StateGraph、checkpoint、interrupt、subgraph 和 durable execution 定位为长运行有状态 agent 的低层编排能力，且不强制使用 LangChain"
---

# 可复用 PuzzleHunt 多阶段解题 Agent

> **触发**：用户要求通过学习 PuzzleHunt/CCBC16，设计能复用于复杂谜题的解题 plan、阶段性 memory、风味文本解读、联想、确定性工具和评测框架。
> **模式**：approved；已进入执行并冻结
>
> <!-- 获批并开始执行后冻结；偏差只写入配对 task，不回写正式 plan。 -->

## 1. 目标、边界与成功定义

目标不是“让模型一次猜中答案”，而是建立可观察、可暂停、可回溯、可测试的 CLI 解题系统：

```text
题面/人工转写 artifact
        ↓
结构化观察 → 多候选假设 → 判别实验 → 确定性工具
        ↑                         ↓
  阶段 memory ← 结果评价/反证 ← 中间结果
        ↓
分层提取 → 答案验证 → meta/依赖合并 → 最终答案
```

第一闭环为 **text-first + 人工可补 artifact 描述**：

- 只接 DeepSeek 官方 API；不引入第二个模型供应商。
- 复杂模式必须经过多个 LLM 推理节点；每个节点只进行一次 stateless、single-turn API 请求。
- 本地结构化 state 负责跨请求连续性，不依赖服务端 conversation。
- 图片、音频、交互网页和复杂排版记录为 artifact；缺少 OCR、表格或人工描述时进入 `BLOCKED_INPUT`，不假装读到了内容。
- 不保存或索取模型私有思维链，只保存结论、证据、候选、实验与可复现的推理摘要。
- 原有 `solve` 保留为 simple mode；新的 session graph 是 complex mode。

复杂模式成功不只看 final answer，还要求机制识别、证据来源、提取链、失败恢复和调用成本可审计。

## 2. 框架决策：领域核心与编排运行时解耦

采用 **框架中立领域核心 + LangGraph 编排适配器**：

| 层 | 职责 | 依赖策略 |
|---|---|---|
| `puzzle_core` | state schema、事件、证据、工具协议、验证规则、prompt/response contract | Python 标准库 |
| `deepseek_provider` | 单轮 JSON 请求、超时、错误归一化、usage | 延续标准库 HTTP 实现 |
| `graph_runtime` | StateGraph、条件边、subgraph、checkpoint、interrupt | complex extra：`langgraph` |
| `checkpoint` | CLI 本地暂停/恢复、历史和分叉 | complex extra：`langgraph-checkpoint-sqlite` |
| `cli` | init/run/step/status/resume/tool/finalize/benchmark | 基础 CLI 不依赖 LangChain |

推荐这一组合而不是自己重写图引擎，因为节点 checkpoint、恢复、人工中断、状态历史和子图本身就是复杂 agent 的核心风险。领域对象、prompt 和工具不继承 LangGraph 类型，因此未来可以替换运行时。安装方式规划为：

```powershell
pip install -e .               # simple solve/ciphers，维持最小依赖
pip install -e ".[complex]"   # session graph + SQLite checkpoint
```

实现前做一个版本兼容 spike，再在 lock/metadata 中固定已验证版本；不把整个 LangChain agent 栈带入项目。

## 3. 顶层 StateGraph

```text
START → INTAKE → ARTIFACT_INVENTORY
                    ├─ missing essential → HUMAN_INTERRUPT ─┐
                    └─ ready → OBSERVE_CLASSIFY              │
                                  ↓                          │
                           HYPOTHESIZE_PLAN ←────────────┐    │
                                  ↓                     │    │
                            ROUTE_SUBGRAPH              │    │
                 ┌────────┬────────┬─────────┬────────┐ │    │
               CIPHER   WORD    GRID/LOGIC  META    RESEARCH│
                 └────────┴────────┴─────────┴────────┘ │    │
                                  ↓                     │    │
                         EVALUATE_EVIDENCE              │    │
                    ┌─────────────┼──────────────┐      │    │
               disproved      missing input   progress │    │
                    └─────────────┘       │        ↓    │    │
                                         └→ EXTRACT ────┘    │
                                               ↓             │
                                         VERIFY_ANSWER       │
                                  ┌────────────┼─────────┐    │
                                fail       intermediate  solved│
                                  └→ HYPOTHESIZE_PLAN     END ←┘
```

### 3.1 节点职责

1. `INTAKE`：冻结标题、风味文本、正文、答案格式、语言、题组/meta 上下文。
2. `ARTIFACT_INVENTORY`：枚举表格、图片、字体、颜色、布局、音频、网页交互等信息是否已被可靠转写。
3. `OBSERVE_CLASSIFY`（LLM）：事实观察与初步题型分类，禁止直接锁死单一机制。
4. `HYPOTHESIZE_PLAN`（LLM）：分别维护机制、领域映射、提取法候选，选择判别力最高的下一实验。
5. `ROUTE_SUBGRAPH`：纯本地路由，不调用模型。
6. 专用 subgraph：执行该类谜题的局部循环，并把结果写成统一 evidence。
7. `EVALUATE_EVIDENCE`（LLM）：根据工具输出支持、削弱或淘汰假设；标记失败尝试。
8. `EXTRACT`：建立逐项 extraction ledger；能确定计算的部分使用本地工具。
9. `VERIFY_ANSWER`（LLM + deterministic checks）：检查格式、题面覆盖、标题/风味回扣、meta 兼容性和替代解释。
10. `MEMORY_COMPACT`：节点边界压缩 active state，原始事件保留在 checkpoint/history。
11. `HUMAN_INTERRUPT`：请求缺失 artifact、歧义选择或用户修正；保存状态后可跨进程恢复。

### 3.2 专用 subgraph

- `cipher_encoding`：古典密码、编码、转置、索引和组合变换。
- `word_association`：双关、同音、语义场、分类、词链、外部作品/知识映射。
- `grid_logic`：网格、路径、邻接、填字、约束满足和局部搜索。
- `extraction_reverse`：从答案长度、空格、索引槽和 meta 结构逆推所缺步骤。
- `meta_dependency`：子题 DAG、递归输入、跨题回调、答案 provenance 与终止条件。
- `knowledge_research`：只有谜题确需外部事实时启用；所有事实带来源，不把搜索结果当答案。
- `artifact_clarification`：生成最小、可回答的转写请求，不反复索取整个附件。

每个 subgraph 共用 evidence/hypothesis/attempt 协议；新增题型只注册 subgraph 和工具，不改顶层状态语义。

## 4. 强制多轮推理协议

complex session 在非阻塞情况下至少包含三次相互独立的 DeepSeek 单轮调用：

1. **观察与分类轮**：只产出事实、异常与题型分布，不提交最终答案。
2. **假设与实验计划轮**：至少保留两个可区分候选，产出下一实验及其预期结果。
3. **证据评价与验证轮**：必须消费前一轮之后产生的工具/人工结果，才能支持答案。

复杂题可重复 2–3；`VERIFY_ANSWER` 不能与第一次观察合并。若在第 1/2 轮发现关键 artifact 缺失，可先 interrupt，不为了凑调用次数浪费 API。

每个 LLM 节点：输入为当前阶段所需的最小 state，输出为严格 JSON delta；schema 失败不静默重试、不部分提交。调用预算含 `max_calls`、`max_rounds`、`max_tokens`、`max_tool_runs` 和 wall-clock deadline。达到预算返回 `EXHAUSTED`，而不是编造答案。

## 5. 风味文本、标题与联想框架

风味文本既不是必然指令，也不是默认装饰。分析输出分为 `observation`、`association`、`mechanism_hypothesis`：

| 视角 | 检查内容 |
|---|---|
| literal | 表层叙事、角色、动作、时间和目标 |
| lexical | 双关、同音、多义、大小写、奇怪措辞、跨语言词形 |
| thematic | 作品、人物、学科、文化对象指向的知识域 |
| operational | 方位、移动、重复、翻转、顺序、时间是否暗示操作 |
| anomalous | 不协调、过度具体、异常重复、刻意遗漏 |
| structural | 标题/风味中的数量和句法是否映射题面结构 |
| callback | 候选能否在提取或答案处回扣，而非仅“有点像” |

联想必须带触发词和 source locator；获得题面第二条独立证据或一个可判别实验后，才可进入 active plan。系统保留 competing hypotheses，避免风味文本导致过早收敛。

## 6. 状态、记忆与证据模型

LangGraph checkpoint 是运行状态的 SSOT；导出的 JSON/JSONL 用于阅读、迁移和 benchmark，而不是另建一套相互竞争的写入系统：

```text
.puzzle-agent/sessions/<session-id>/
  checkpoint.sqlite   # LangGraph SQLite checkpointer
  puzzle.json         # immutable 输入与 artifact manifest
  events.jsonl        # 面向人的追加式审计事件
  artifacts/          # OCR、表格、描述、工具输入/输出摘要
  snapshots/          # 可选的可移植 state 导出
  final.json          # 仅验证通过后生成
```

`PuzzleState` 至少包含：

- `puzzle`、`artifacts`、`constraints`、`stage`、`status`、`revision`
- `observations[]`：事实、source locator、采集方式、可靠度
- `flavor_associations[]`：触发词、联想、支持/反证、状态
- `hypotheses[]`：类别、置信度、evidence ids、判别实验、状态
- `plan[]`：依赖、成本、预期判别力、完成条件
- `attempts[]`：工具、参数、input fingerprint、输出摘要、outcome
- `intermediate_answers[]`：值、来源、依赖、置信度
- `extractions[]`：source、排序、mapping/index、输出与校验
- `answer_candidates[]`：验证矩阵而非单一自由文本答案
- `open_questions[]`、`missing_artifacts[]`、`blockers[]`
- `budget`、`usage`、`last_node`、`next_node`

安全约束：持久化值只用受限 JSON 兼容类型，不启用 pickle fallback；checkpoint 不记录 API key；人工修正形成新事件和 checkpoint，不覆盖历史。CLI 支持查看历史 checkpoint，并从指定 checkpoint 分叉实验路线。

## 7. 工具协议与能力库

复用现有 `CipherWorkbench`，以 `ToolSpec(name, input_schema, output_schema, deterministic, cost)` 注册工具。所有工具只产出候选和 evidence，不自行宣布 final answer。

第一批工具族：

- Caesar/ROT、Atbash、Base、Morse、A1Z26、Vigenere（已知 key）、Rail Fence、reverse、odd/even、acrostic。
- nth/首尾/对角线/路径/坐标提取，排序、字母差、词长、频次、anagram delta。
- ASCII、Unicode、二进制、电话九键、键盘邻接、NATO。
- 可文本化 Braille、Semaphore、Pigpen 表示与验证。
- 网格邻接、连通性、路径验证、简单 CSP/backtracking。
- meta answer table、依赖 DAG、递归/循环检测。

密码自动扫描只负责召回；评分候选不能当成证明。拼音、笔画、作品资料等若没有可靠数据源，返回 `missing_capability`。每次工具调用用 fingerprint 去重，防止循环重复。

## 8. CLI 测试体验

```powershell
# 基础能力，无网络
puzzle-agent ciphers --text "..."
puzzle-agent solve --offline --file examples/puzzle.json

# 复杂模式
puzzle-agent session init --file examples/complex-puzzle.json
puzzle-agent session status <id>
puzzle-agent session step <id> --offline           # 只推进一个 graph node
puzzle-agent session run <id> --offline --max-calls 6
puzzle-agent session add-artifact <id> --file grid.txt --kind table
puzzle-agent session resume <id> --response-file artifact-answer.json
puzzle-agent session history <id>
puzzle-agent session branch <id> --checkpoint <checkpoint-id>
puzzle-agent session finalize <id>

# opt-in live DeepSeek
puzzle-agent session run <id> --max-calls 6
puzzle-agent benchmark run --suite derived-dev --provider offline
puzzle-agent benchmark run --suite derived-blind --provider deepseek
```

- `step` 是学习/调试入口；一次最多一个可能计费的 LLM node。
- `run` 是完整体验入口；自动推进本地节点和多轮 LLM 节点，但绝不超过显式预算。
- 每次 live run 前显示最大调用数、模型和输入规模；状态页显示阶段、证据、待验证假设、缺失 artifact 和累计 usage。
- offline scripted provider 验证图行为；live benchmark 才评价模型能力，并默认不运行。

## 9. CCBC16 方法蒸馏与派生测试集工厂

CCBC16 **不进入运行时 prompt，也不作为直接 live benchmark 题库**。它只用于设计阶段学习常见复杂解题结构。流程为：

1. `CURATE`：开发者阅读官方题面与题解，选取具有代表性的机制。
2. `DISTILL`：写 `MechanismGraph`，只记录必要观察类型、知识/工具、操作序列、提取链、验证点和常见失败，不复制原文。
3. `REAUTHOR`：换主题、数据、表面形式和最终答案，制作机制同构但内容原创的 synthetic puzzle。
4. `SOLVE_INDEPENDENTLY`：由确定性脚本或人工从输入独立解出，确认答案唯一且步骤闭合。
5. `ISOLATE`：agent 只可读取 `input.json` 和公开 artifacts；`oracle.json`、rubric 和官方学习笔记由 evaluator 单独加载。
6. `LEAK_CHECK`：扫描标题、答案、题解关键词和 source id；prompt capture 测试证明 oracle 没有进入模型输入。
7. `SPLIT`：`derived-dev` 可用于调试，`derived-blind` 只由 evaluator 解封，防止针对样例过拟合。

```text
benchmarks/
  mechanisms/                  # CCBC16 学到的抽象机制图；不供 runtime 读取
  derived/
    dev/<case-id>/
      input.json
      artifacts/
      oracle.json
      rubric.json
      provenance.json          # 来源 URL、学习日期、相似性审查，不含于 prompt
    blind/<case-id>/...
```

第一批至少覆盖 8 个原创 case：对象→编码映射、异常联想图、异构子题 DAG、缺信息反推、提取逆推、多层 meta/递归、机制回调复用、最终约束组合。每个 case 记录“受哪个机制启发”，但不沿用官方题目文本、实体、数据或答案。

评价维度：final correctness、机制识别 milestone、evidence grounding、extraction provenance、错误假设恢复、artifact interrupt 质量、阶段纪律、调用/token 成本。离线 scripted fixtures 验证状态机，不冒充真实模型能力。

## 10. 实施顺序（TDD）

1. **兼容 spike**：验证最小 StateGraph + 直接 DeepSeek provider + SQLite checkpoint，不引入 LangChain agents；记录依赖决策。
2. **RED/GREEN：领域 state**：schema、reducer、evidence provenance、预算和非法 transition。
3. **RED/GREEN：graph skeleton**：节点顺序、条件边、至少三轮协议、budget exhaustion、interrupt/resume、checkpoint branch。
4. **RED/GREEN：LLM contracts**：逐节点 prompt/JSON delta、无部分写入、无自动 schema 重试、每节点 call-count。
5. **RED/GREEN：tools/subgraphs**：CipherWorkbench 适配、提取 ledger、去重、meta DAG 和基础 grid/CSP。
6. **RED/GREEN：CLI**：init/step/run/status/add-artifact/resume/history/branch/finalize；simple mode 回归不受 complex extra 影响。
7. **测试集工厂**：先写 leak sentinel 和 evaluator isolation，再创建 8 个 CCBC16 机制启发的原创 dev/blind case。
8. **验证**：全量离线测试、安装矩阵（base/complex）、故障恢复、secret scan；经用户显式选择后才运行付费 live benchmark。
9. **学习记录**：更新 README、架构文档、设计旅程和 puzzle skill，明确采用/借鉴了哪些 LangGraph 概念及实际差异。

## 11. Contract impact map

| 维度 | 结果 |
|---|---|
| canonical SSOT | `PuzzleState` + LangGraph checkpoint；P0001 的 `PuzzleInput/SolveResult` 保留为 simple solve 契约 |
| active consumers | CLI、DeepSeek provider、node prompts、tool registry、subgraphs、checkpoint、benchmark evaluator、skill、docs |
| dependency boundary | base 零第三方 runtime 依赖；complex extra 仅 LangGraph + SQLite checkpointer，不引入 LangChain agent abstraction |
| generated/test data | 原创 derived fixture factory；input/oracle 物理分层；blind split 不被 prompt builder 访问 |
| mechanical checks | state reducer、transition、call-count、budget、resume/branch、secret exclusion、answer leak sentinel、CLI exit code |
| historical snapshots | P0001/T0001 保持历史；本 draft 获批后分配新的 P/T，正式 plan 冻结 |
| repo-wide search terms | `PuzzleSolver|PuzzleState|StateGraph|session|checkpoint|interrupt|memory|stage|answer|solution|ccbc16|DEEPSEEK_API_KEY` |

## 12. 风险与控制

- **框架依赖膨胀**：LangGraph/SQLite 只在 `[complex]` extra；核心与 provider 不使用 LangChain 类型。
- **模型过早收敛**：观察轮不得提交 final，计划轮保留 competing hypotheses，验证轮必须消费新 evidence。
- **循环与费用失控**：所有 run 必须有预算；重复 tool fingerprint、无新 evidence 和低信息增益触发停止。
- **memory 污染**：事实、联想、假设、工具输出分层；人工修正留历史；答案候选不覆盖旧候选。
- **视觉能力缺口**：DeepSeek text-only；缺可靠转写即 interrupt，不把 placeholder 当 artifact 内容。
- **答案泄漏/benchmark 污染**：不直接测试 CCBC16；原创 input 与 oracle 分层，prompt capture + sentinel 双重检查。
- **checkpoint 反序列化**：只持久化 JSON 兼容 state，不启用 pickle fallback；数据库按本地敏感运行数据处理。
- **上下文膨胀**：按节点选择 state slice，压缩已关闭假设；完整历史留 checkpoint，不重复注入 API。
- **外部知识幻觉**：知识事实必须有来源；无研究能力或无证据时保持 unknown。

## 13. 验收标准

- [ ] base 安装仍可运行 simple solve/ciphers；complex extra 可单独安装并启动 graph session。
- [ ] complex session 可创建、自动运行、单步、暂停、跨进程恢复、查看历史和从 checkpoint 分叉。
- [ ] 非阻塞复杂题至少经历观察分类、假设计划、证据评价/验证三次独立 DeepSeek 单轮调用。
- [ ] observation/association/hypothesis/plan/attempt/extraction/answer candidate 均有独立 schema 与 provenance。
- [ ] 每个 LLM node 最多一次请求；本地 node/tool 零请求；预算耗尽安全返回 `EXHAUSTED`。
- [ ] 非法 JSON、API 错误和进程中断不产生部分 state；interrupt 后可准确恢复。
- [ ] `.env.local` Key 不进入 checkpoint、event、artifact、prompt dump 或错误输出。
- [ ] 至少 8 个由 CCBC16 机制启发、但题面/数据/答案原创的 derived case；官方内容不进入 runtime prompt。
- [ ] dev/blind 的 input/oracle 隔离通过 leak sentinel 与 prompt capture 测试。
- [ ] offline tests 覆盖 graph 路由、回放、分叉、call-count、预算、工具去重和 CLI；live benchmark 明确 opt-in。
- [ ] 文档记录框架选型、CCBC16 蒸馏方法、视觉边界、评测局限和 agent 设计学习过程。

## 14. 已确认决策与最终审批点

已确认：

- CCBC16 仅供我们离线学习；测试题由项目重新设计，不把官方题面/题解直接发送给 DeepSeek。
- complex mode 必须按照阶段进行多次推理；每次 DeepSeek API 请求仍是独立单轮对话。
- 关键决策允许由 agent 在候选、证据、预算约束内作出，并留下可审计记录。

待用户对本 plan 作最终审批：采用“**标准库领域核心 + 可选 LangGraph/SQLite complex runtime**”。获批后将本草案提升为新的正式 P，创建配对 T，并按第 10 节执行；届时正式 plan 冻结。
