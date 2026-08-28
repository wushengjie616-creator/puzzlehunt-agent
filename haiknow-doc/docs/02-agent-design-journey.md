# Agent 设计学习日志

## 第 1 站：先定义“agent”

本项目中的 agent 是一个受约束的目标执行系统：它理解 puzzle 输入、运行领域工具、组织推理请求并校验结果。它不等于必须采用某个 agent 框架，也不等于无限自治循环。

这个定义避免了一个常见误区：为了叫 agent 就引入 LangChain、图编排或多轮 ReAct，即使产品只有一个模型节点。

## 第 2 站：单次请求改变了工具架构

经典 ReAct 流程通常是：

```text
模型决定调用工具 → 应用执行工具 → 工具结果回传模型 → 模型给答案
```

这至少需要两次模型请求。项目要求单次语言对话，因此选择：

```text
应用预先运行有限工具 → 候选随原题一起发送 → 模型一次完成综合判断
```

代价是模型不能动态选工具或调整参数；收益是请求数、成本、延迟和测试边界都可预测。

## 第 3 站：采用的通用模式

### Pipeline

输入校验、密码分析、prompt 构建、provider 调用、输出校验按阶段串联。每一段都能独立测试。

### Ports and Adapters

`PuzzleSolver` 只依赖 `CompletionProvider` 协议。DeepSeek 和离线 provider 是适配器；未来更换供应商不应改密码库或输入模型。

### Strategy + Registry

每类密码转换是确定性策略，工作台负责统一执行、评分、去重和预算。未来增加新密码时，应扩策略而不是把判断堆进 CLI。

### Dependency Injection

测试把 recording provider 注入 solver，直接观察调用次数。它能抓住“错误时偷偷重试”这类真实成本回归。

### Structured Output

prompt 明确 JSON contract，同时 API 使用 JSON Object 模式。应用仍进行本地 schema 校验，因为“合法 JSON”不等于“字段语义合法”。

## 第 4 站：MVP 为什么没有采用常见框架

| 方案 | 当前判断 |
|---|---|
| LangChain / LangGraph | 多节点、工具循环、持久状态出现后才有价值；当时的 MVP 会增加依赖和追踪层 |
| PydanticAI | 结构化模型和 provider 抽象很好，但当前标准库 dataclass 足够，零依赖更符合选择 |
| ReAct | 与严格单请求冲突 |
| 纯 Prompt | 无依赖但机械解码不稳定、难回归，未采用 |
| 自定义单程管线 | 当前推荐；最贴合约束，测试面最小 |

“没套框架”不是缺少设计。这里实际采用了 pipeline、hexagonal architecture、strategy 和 dependency injection，只是没有引入框架包。

## 第 5 站：skill 与运行时工具不是一回事

Codex skill 的 `SKILL.md` 能改变开发 assistant 的工作方式，但 DeepSeek Chat Completions 不会自动读取项目 skill。若只写 skill，线上 agent 实际没有密码能力。

因此 canonical 实现在 `puzzle_agent.cipher_workbench`。项目 skill 的脚本只调用该实现，使开发体验和产品行为共享同一事实源。

## 第 6 站：测试如何证明设计

测试不检查源码是否写了某个词，而观察：

- 已知密码向量能否正确解码；
- 错误输入是否被拒绝；
- 候选是否遵守数量和字符预算；
- CLI exit code 和 JSON 输出是否可用；
- solver 在成功和非法 JSON 时是否都只调用一次 provider；
- DeepSeek adapter 是否发往官方路径并带正确 payload；
- skill 脚本是否得到与运行时相同的候选。

## 升级触发条件

满足以下任一真实需求时，再评估 agent 框架：

- 用户允许多轮调用，且模型需要动态选工具或参数；
- 需要暂停、人工确认、恢复和持久状态；
- 需要联网检索、OCR、题库或多 agent 分工；
- 分支和循环多到自定义编排难以审计。

升级时保留 `PuzzleInput`、`SolveResult` 与密码策略，将 solver 编排替换为图或工具循环，而不是推倒领域层。

## 第 7 站：升级触发条件真的出现了

复杂 PuzzleHunt 带来了 MVP 没有的真实需求：

- 一道题需要观察、假设、实验、评价和验证多次反馈；
- 工具结果和新 artifact 必须进入后续推理；
- 图片/表格转写可能在运行中缺失，需要暂停等待；
- meta 题存在子题依赖、递归、回溯和替代路线；
- 用户希望看到阶段 memory，并把搭建过程作为 agent 设计学习材料。

因此引入图编排不是为了“看起来更 agent”，而是升级触发条件已经满足。

## 第 8 站：采用 LangGraph，但没有把领域交给框架

最终选择是：

```text
标准库领域核心
  + 直接 DeepSeek provider
  + 可选 LangGraph orchestration
  + 可选 SQLite checkpointer
```

实际采用的 LangGraph 概念：

- `StateGraph`：命名节点与条件边；
- checkpoint/thread：节点边界状态和历史；
- `interrupt`/`Command(resume=...)`：artifact 人工补充；
- `interrupt_after="*"`：CLI 单步学习；
- state history：分叉实验路线。

没有采用的部分：

- LangChain agent abstraction；
- LangChain model/tool adapter；
- LangSmith 托管服务；
- 自动无限 ReAct loop；
- 把 message history 当作唯一 memory。

这叫“framework-neutral core + orchestration adapter”：框架负责耐久执行，不拥有谜题语义。

## 第 9 站：单轮 API 与多轮 Agent 并不矛盾

这里的“单轮”指每次 DeepSeek API 请求都是独立 Chat Completions 调用；“多阶段”指一道复杂题会发出多个这样的独立请求：

```text
call 1: OBSERVE_CLASSIFY
call 2: HYPOTHESIZE_PLAN
local:  deterministic tools
call 3: EVALUATE_EVIDENCE
call 4: VERIFY_ANSWER
```

跨调用连续性来自本地 `PuzzleState`，不是供应商会话。每个节点最多一次请求；达到 `max_calls` 后安全停止。这同时满足可观测性、成本控制和复杂反馈。

## 第 10 站：Memory 应保存什么

没有保存模型私有思维链。可持续协作真正需要的是：

- 可定位的观察事实；
- 风味联想的触发词和反证；
- competing hypotheses；
- 为什么选择某个判别实验；
- 工具参数、fingerprint 和结果；
- 失败 attempt；
- extraction provenance；
- 候选答案的验证矩阵。

LangGraph checkpoint 保存机器恢复状态，`events.jsonl` 保存人类审计摘要。两者职责不同，避免双 SSOT。

## 第 11 站：从 CCBC16 学机制，而不是背答案

抽查 CCBC16 代表题后，提炼出对象映射、异常联想图、异构子题 DAG、缺信息反推、逆向提取、递归 meta、机制回调和最终约束组合等模式。

官方内容没有进入 DeepSeek prompt。测试集采用重新出题流程：

```text
CURATE → DISTILL → REAUTHOR → SOLVE_INDEPENDENTLY
       → ISOLATE → LEAK_CHECK → DEV/BLIND SPLIT
```

每个 case 的 `input.json` 与 `oracle.json` 物理分离。validator 会拒绝答案字段和字面泄漏；benchmark runtime 只加载 input，评分结束也不输出期望答案。

## 第 12 站：这次测试证明了什么

TDD 不只检查类名或 prompt 文本，而观察现实行为：

- graph 是否按顺序发生四次独立调用；
- 预算 2 是否严格停在两次调用；
- SQLite manager 重新打开后能否恢复状态和历史；
- `step` 是否恰好推进一个节点；
- 缺 artifact 时是否零模型调用并真正 interrupt；
- resume 后是否从 checkpoint 继续；
- branch 是否使用指定 checkpoint；
- 非 `SOLVED` 是否拒绝 finalize；
- 模型计划是否能调度注册工具；
- base 安装是否仍然零依赖；
- dev/blind input 是否与 oracle 隔离；
- benchmark 输出是否不包含 oracle。

兼容 spike 还发现一个实践事实：LangGraph 会传递依赖 Pydantic 2，而共享 Conda 中已有工具要求 Pydantic 1。最终通过可选 extra + 项目 `.venv` 隔离，而不是污染基础安装。

## 下一站

当前优先级是用 opt-in DeepSeek benchmark 观察真实模型在 10 个原创 case 上的阶段表现，再依据失败证据选择扩展：知识检索、更多 grid/CSP、中文拼音/笔画权威数据或视觉 provider。没有 benchmark 证据前，不因为“可能有用”继续堆依赖。

## 第 13 站：从题解集合蒸馏方法，而不是堆 prompt 技巧

三个只读研究流分别检查机制、工具边界和原创评测设计。交集被命名为 TRACE-LIFT：保真转写、线索登记、竞争假设、有界计算、证据审计、层级检查、未消费项、不变量反证和终局验证。它记录的是可复验产物，不要求或保存模型私有思维链。

## 第 14 站：为什么工具必须能报告歧义

CCBC16 多次把“不唯一”本身用作机制。如果 solver 只返回第一个解，它会把搜索顺序伪装成事实。因此新增约束工具区分 `SAT/UNSAT/AMBIGUOUS`；未来小型 solver 还要统一 `BUDGET_EXHAUSTED`、solution count 和 truncated。确定性不等于确定答案，确定性只表示同输入同参数得到同一可审计结果。

## 第 15 站：周期评测如何避免边做边改

同一批五题先冻结 Git commit，再并发启动独立 worker；evaluation lock 期间 watcher 延后提交。每个 worker 逐节点 step 以获得真实耗时和 state delta，父进程最后才加载 oracle。框架改进只允许发生在批次之间，并必须指向某个失败、冗余节点或未消费线索的实证。

## 第 16 站：全量审计改变了哪些判断

全 55 ID 审计没有按网页 `type` 猜 Meta，而按官方 `answer_type` 和是否消费赛事其他题答案分类。结果排除 6 道赛事 Meta，保留了题内递归 Meta、micro-meta 和终章 feeder；这些题恰好能训练层级检查，却不污染“非-meta”定义。

49 题说明复杂 puzzle 更像“载体切换图”：文本可能变网格，答案可能变 emoji，两个解的差异可能变旗语，循环可能被时间状态打破。于是框架没有扩成一个更长的万能 prompt，而是加强了 artifact、dependency DAG、ambiguity、state version、unused inventory 和 terminal verification 的结构化字段。

## 第 17 站：为什么 hard set 要一次性且短暂存在

原创测试反复运行用于迭代，官方 hard set 用于测泛化，二者必须隔离。hard runner 在网络请求前落下一次性 marker；官方题面、答案、checkpoint 和模型输出只进入 ignored cache，评分后清理。Git 只保存题号、正确性、耗时、调用数与错误类别。这样防止框架针对 hard set 反复调参，也避免把整站内容变成项目副本。

## 第 18 站：多次推理必须由证据触发

固定四阶段对简单题足够，但第一次工具实验失败时直接 verify 会浪费失败证据。现在 `evaluate_evidence` 可以选择一次 `replan`；第二轮规划看到前一轮 attempts/evidence，必须提出不同的有界实验。路由器只有在还能预留“规划、评估、终局验证”三次调用时才接受该决定。它是证据驱动的有限回路，不是无界 ReAct。

## 第 19 站：工具名不是工具契约

第二个正式周期让 14 个工具调用全部失败：模型知道该用哪一类工具，却猜了 `moves`、`numbers`、`strings` 等不存在的参数。于是工具目录从“名字列表”升级为从 callable 自动生成的精确签名；这比手写第二份 JSON schema 更不易漂移。同时终局增加机器门：计划过确定性实验但全部失败时，模型不能自行把 evidence check 标真。

## 第 20 站：签名也不是完整输入契约

第三周期把未知参数错误清零，30 次工具调用中 20 次完成；剩余失败转成容器类型、枚举或前置条件不满足。ToolSpec 因此在同一注册点附加简短契约，告知模型坐标基准、嵌套对象形状和等长要求。另一个失败是计划只做五次 Caesar 却忘了最终索引，所以 planning 现在必须覆盖 carrier 到 final extraction 的整条链，并限制无关 shotgun。

## 第 21 站：已有能力必须进入 Agent 的可见行动空间

机制审计发现简单模式的密码工作台早已实现 Atbash、Base、标准 Morse、已知 key 的 Vigenère 和已知栏数的 Rail Fence，但复杂模式只看 ToolRegistry，实际无法选择它们。框架因此用有界 wrapper 将这些能力注册到复杂图：严格失败而不是返回模糊空值，保留最大输入长度，并禁止在工具内部猜 key 或栏数。代码复用不等于能力复用；只有进入当前编排器的可见契约才算 Agent 能力。
