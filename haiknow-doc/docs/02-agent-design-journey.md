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

## 第 22 站：声明了状态字段不等于拥有阶段记忆

早期 state 已预留 `intermediate_answers`、`extractions` 和 `open_questions`，但没有全部传进下一阶段，评价节点也没有写回中间载体与未决问题。这种“类型上存在、运行时失忆”会让终局跳过最后提取。现在每轮评价显式维护 carrier、未决问题和未消费元素，所有后续节点都能读取完整账本；终局还有独立机器门，推理债务未清零时即使模型把检查项全写成 true 也不能判定 solved。

## 第 23 站：节点作用要报告行为，不能拿正确率冒充因果

早期节点报告在答对时标 helpful，在答错时统一标 unassessable；它避免了伪因果，却不能说明错误过程中节点做了什么。新 trace 只采集公开状态差分，报告观察数、计划数、工具成败、提取增量、replan、memory 债务和终局状态。这样既不暴露思维链，也能区分“节点没激活”“激活但无输出”“工具全部失败”“产生证据但最终错”等真实运行角色。

## 第 24 站：机制选择之前必须有本体发现

用户指出 v1 风味文本把操作步骤写得过明，暴露了旧图把“观察后猜机制”压缩成一步的问题。CCBC12/15/16 共 37 道人类路径复核显示，真正 aha 往往是表示空间或知识本体切换。图中因此新增 `ASSOCIATE_THEME`：先列 surface tension，再维护 3–5 个 ontology/bridge 候选、holdout prediction 与 falsifier；这个阶段看不到工具目录。只有 bridge 能解释至少两个独立信号并通过廉价预测后，下一节点才选择工具。默认预算由 6 提到 8，正常路径五次模型调用，仍只允许一次证据驱动 replan。

## 第 25 站：中间答案不能只存在，必须被独立验证

首次 v2 完整流程中，模型正确联想到国际象棋，却没有物化棋子分配、谢幕顺序或提取载体；旧图仍直接从 evidence evaluation 跳到 final verify。新增 `VERIFY_INTERMEDIATES` 后，原始 carrier 必须引用真实 evidence ID，并通过 evidence-backed、reproducible、distinct-from-final、extraction-ready 四项检查。最终机器门要求该阶段通过；“猜中 final 但没有中间链”不再能进入 `SOLVED`。正常路径因此由五次变为六次，单次 replan 路径正好使用八次预算。

## 第 26 站：官方题面转换必须读取玩家真正看到的 HTML

旧 hard converter 只读取 `content/extend_content`，但 CCBC16 一些纯文本题（例如 #3）的主体只在 `html`，导致旧“28 道文本题”统计把空题面也算可运行。转换器现在读取 `html + content + extend_content`，并扫描内联图片、脚本及空 surface。按可直接运行的严格门，49 道非 Meta 当前有 10 道无需图片/交互；其余题保持 excluded reason，等待保真 artifact 转写，URL placeholder 不冒充文本题面。

## 第 27 站：先把子题变成对象，再谈机制与工具

15:00 的 10 道真实题评测把同一种失败暴露得很清楚：面对 35 个词条、127 条阶段线索或 192 条分组线索时，模型仍把整页内容当作一个字符串，然后在 Unicode、Base、Caesar 等通用工具间游走。`ASSOCIATE_THEME` 能提出本体，却没有强迫 Agent 把题面变成可跟踪的工作单元。

因此图中新增 `MATERIALIZE_SUBPROBLEMS`。它必须记录结构类型、总单元数、分组、依赖、原文 excerpt 和 representative results；20 个以内全部枚举，超过 20 个至少保留总数并物化三个高杠杆代表单元。候选局部解仍然不是 evidence，只有后续工具或证据评价能推动它通过中间验证。

同一轮还移除了空计划自动调用 `cipher_workbench` 的隐藏 fallback。计划为空意味着“目前没有合适的确定性实验”，而不是授权密码 shotgun；计划中的每次工具调用必须引用 signal，并给出 prediction 与 falsifier。replan 的 tool+arguments fingerprint 若与历史相同则只记 `duplicate_skipped`。这让有限循环真正意味着新实验，而不是重复消耗模型和工具预算。

## 第 28 站：完整题面包含解锁时已知状态，不只是当前网页

人工转写 #52–#54 时发现，图片本身虽然可以无损变成文本，却仍不足以让独立 Agent 获得与现场玩家相同的信息。#52 明确消费印刷区 Meta 答案，#53 要把当前字母矩阵与已经解出的火药 Meta 颜色网格求交，#54 回调更早题目中 `〔〕` 的同音操作符。只转写当前图片会制造一种隐蔽的 missing-input benchmark，然后错误地把失败归因于推理能力。

因此 suite 的“surface fidelity”升级为“unlock-state fidelity”：当前题面、静态 artifact、已知上游答案、已解出的上游结构和已学习操作符都要作为带 provenance 的运行时输入；当前题目的 solution 与 final answer 仍严格留在 evaluator 侧。#52–#54 由此成为首批 `human-reviewed-static-plus-upstream-state` case，均保存官方源 hash、零未表示通道和独立中间 checkpoint。

## 第 29 站：JSON 合法不等于响应完整

真实 DeepSeek 单题在 `ASSOCIATE_THEME` 连续遇到 output length 截断。仅收紧 prompt 字符预算不能保证服务端完整返回，因此 provider 现在同时检查 `finish_reason=length`，拒绝把截断 JSON 写进 state，并把 DeepSeek 输出上限提高到 16384。复跑后 9/9 次调用成功，完整经过一次 replan 并诚实停在 `NEEDS_REVIEW`。这说明模型 transport、阶段 schema 与解题正确性必须分别验收。

## 第 30 站：局部解答必须经过证据提升

16:00 的 13 题批次中，`MATERIALIZE_SUBPROBLEMS` 生成 89 个局部单元和 33 个非空局部结果，却没有一个进入正式 evidence。#3 的八个近乎正确 clue answer 因此在后续阶段大量丢失，计划退化到 Caesar/Atbash。新增 `VALIDATE_SUBPROBLEMS` 后，每个非空结果必须唯一落入 supported、contradicted 或 needs-test；supported 值不能被改写，必须引用 signal 并给出 prediction/falsifier。忠实转录与语义解答也分开标记，避免把“抄对题面”误报成“解出题目”。

## 第 31 站：评分器的字符观也属于 Agent 契约

人工转写 #15 暴露了旧归一化只保留拉丁字母、数字和 CJK 的问题：韩文答案 `안녕` 与标点串都会被归一化为空，产生假阳性，并使韩文 checkpoint 被静默丢弃。评分器改为 Unicode NFKC + casefold，并保留所有 `isalnum()` 字符。benchmark 不只是题目集合；它的等价关系本身也是需要测试的判断节点。

## 第 32 站：节点数据必须进入人类报告

`node-summary.json` 已记录节点激活和效果，但旧小时报告只输出总体失败文字，无法满足每轮逐节点复盘。公开报告现在直接列出激活题数、激活次数、耗时、可观察效果、作用标签和问题，并明确 `UNASSESSABLE` 不是“无用”。这样每小时的优化假设可以由节点证据驱动，而不是依赖人工翻找内部 JSON。

## 第 33 站：结构化输出必须可保守总化

17:00 的真实批次首次运行局部验证节点时，10 个执行题中有 8 个不是因为不会解题而失败，而是因为严格 schema 把漏判、冲突 verdict 和 accepted value 漂移当成不可恢复异常。对 Agent 而言，LLM JSON 合法仍不意味着分类完备；验证节点必须能把不确定输出转成安全状态。

运行时现在只对真正越界的未知 result ID 硬失败。已知候选的遗漏、冲突或无效 accepted 记录一律降级为 `needs_test`，并由机器重算 unresolved coverage。这样既不把模型错误冒充证据，也不让一个局部格式问题杀死整条推理链。

## 第 34 站：验证器也会制造假答案

中间答案评分曾把单字符别名 `i` 匹配到无关长文本 `MOVIE BLUE CIRCLE`；中间验证节点也曾接受模型凭空创建、但 evidence ID 真实存在的 value。两者都说明“引用了证据”不等于“值来自证据”。现在中间验证要求 value 精确存在于上一阶段，引用只能取自该源值已有 evidence；评分的子串等价至少需要两个归一化字符。验收同时覆盖节点行为与 evaluator 行为，避免用有漏洞的尺子证明 Agent 已经进步。

## 第 35 站：复杂题门禁不能否定原子题

真实 DeepSeek CLI 样例把 `uryyb` 正确识别为 ROT13，局部语义验证、Caesar 工具、evidence evaluation 与最终六项检查全部通过，却因 `hello` 同时是解码产物和最终答案、没有“不同于最终答案”的中间载体而停在 `NEEDS_REVIEW`。这不是谨慎，而是把复杂题拓扑错误地强加给一步题。

修复没有移除中间验证节点，而是加入机器可证的 direct-answer 窄路：仅限 atomic 单子题、无 unresolved、同值 semantic derivation、同值 answer candidate、成功工具复现且引用链完整。真实 checkpoint 分支随后只重跑两个验证节点，得到 `SOLVED/hello` 并成功 finalize；复杂结构和缺证据反例仍被拒绝。

## 第 36 站：复制 checkpoint state 不等于复制执行位置

第一次从 evidence evaluation 后 checkpoint 建分支时，新 session 虽然带着全部 state，却从 `START` 重新执行，最终重复观察、联想和局部验证并耗尽预算。原因是旧 `branch` 只把 snapshot 写成 `initial_state`，没有在新 LangGraph thread 中重建游标。

现在 branch 以原 snapshot 的 `last_node` 调用 `update_state`，并强制核对新旧 `next`。回归测试证明分支 provider 只收到 `VERIFY_INTERMEDIATES`、`VERIFY_ANSWER` 两次调用；真实 DeepSeek 分支也从 calls=6 继续到 calls=8，而不是重跑入口节点。

## 第 37 站：结构化协议恢复后，失败重心才会显露

18:00 批次把上一轮 8 个局部验证协议错误全部消除，17/20 题安全到达两层验证门；剩余 3 题分别在 observe、plan、evaluate 遭遇 TLS EOF 或响应体不完整。这说明 schema 容错已经生效，网络抖动也不应继续与推理失败混为一类。

cycle worker 因此只对明确的 transport exception 做一次同 checkpoint、同节点重试，并在 trace 中记录 `PROVIDER_RETRY`。普通 `RuntimeError`、非法 JSON、schema 和协议错误仍立即失败。重试是可观察的恢复动作，不改变已提交 state，也不会扩成通用重试循环。

## 第 38 站：工具重规划不能修复尚未形成的语义载体

18:00 的 17 个安全完成题中，14 题进入旧的 evaluate→tool replan，14 题都没有形成 final candidate；其中 10 次第二轮工具实验没有增加任何 extraction。失败分组显示 11 题所有局部结果为空，另外 4 题只有零散 needs-test。此时增加密码工具或再规划工具调用，是在错误层级上优化。

图中因此增加一次计划前 semantic refinement：首轮验证覆盖不足 50%、尚未恢复且至少剩余 6 次调用时，重新进入 materialize→validate。已有 supported 结果按 ID、subproblem 和 value 作为不可变锚点合并回来；零锚点时只提出 1–3 个由原文支撑的高杠杆候选。恢复轮用掉原先 replan 的两次预算，并禁止二者叠加，从而仍保持最多 10 个模型节点。它不是让模型“再想一次”，而是针对缺失语义载体的有界修复路径。

独立反例审查又证明，仅在 materialize 阶段合并锚点仍不够：第二次 validator 若漏报旧锚点，会让 accepted state 撤销、旧 evidence 却残留。运行时现在把 prior accepted 作为机器不可撤销基线，第二轮全量重建 semantic evidence；覆盖率也按唯一 subproblem ID 而不是结果条数计算，防止同一子题多个候选虚增覆盖。

## 第 39 站：恢复轮的第一份实证既不是成功，也不是零作用

19:00 批次中 16/21 题进入 semantic refinement。#10 的受验证局部结果从 0 增到 5，证明“先补语义载体再计划”至少能在真实题上改变证据状态；其余多数题仍是 0→0，说明一次恢复 prompt 不能替代实际的 clue solving。框架因此保留该路径，但不把激活次数当作效果。

同批次还暴露两个可安全总化的协议缺口：#18/#22 的第二次 validator 附带未知 result ID，#29 的终局响应漏了 required checks。未知 ID 没有合法载体，本就不能进入 evidence；缺失 check 也只能解释为 false。运行时现在分别记录后忽略、补 false 并进入 `NEEDS_REVIEW`，避免用异常终止冒充严格验证。

## 第 40 站：文本化视觉题要保存歧义，而不是替它做决定

#9 的三角图不是把 28 个汉字抄下来就完成。source-only 复核把 43 条可独立确认的有向边、3 条额外可见但重数不确定的路径、两个 shared-terminal group、两条同点自环以及三个非标准字形分别编码。无法从像素证明的边重数保留为 `multiplicity_unresolved`，没有用题解反向修图。

三个非标准字形使用源坐标 bbox、逐行 GRAY8 RLE、RGB/灰度 hash 和可读 preview，独立审查逐字节重建一致。只有通过这层复核后，#9 才从 queue 移入 reviewed；解后填字图与“三个角红框字”只进入 evaluator checkpoint。v17 因此扩为 22 题，而不是用摘要冒充完整题面。
